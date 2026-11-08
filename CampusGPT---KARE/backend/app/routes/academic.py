"""Academic APIs — personal records from UIS database only (via API)."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.utils.database import get_db
from app.utils.auth import get_current_user
from app.services import academic_service as acad
from app.services import consent as consents
from app.services import student_context as ctx
from app.services import uis_academic as uis_acad
from app.services import uis_client
from app.services.uis_academic import LinkedStudent

router = APIRouter()


class DraftRequest(BaseModel):
    draft_type: str = "weekly_timetable"
    extra: str = ""
    save: bool = False


async def _student_or_404(db, user):
    student, source = await ctx.resolve_personal_student(db, user)
    if student:
        return student, source
    raise HTTPException(
        status_code=404,
        detail="No UIS student linked to this account. Create the student in UIS with the same email, or set UIS username in Settings.",
    )


async def _require_assist(db: AsyncSession, user: dict) -> int:
    if not str(user.get("sub", "")).isdigit():
        raise HTTPException(status_code=401, detail="Invalid session")
    uid = int(user["sub"])
    if user.get("role") == "student" and not await consents.is_allowed(db, uid, "campus_gpt.assist"):
        raise HTTPException(status_code=403, detail="Campus-GPT assistance consent is off")
    return uid


@router.get("/academic/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await _require_assist(db, user)
    student, source = await _student_or_404(db, user)
    if isinstance(student, LinkedStudent):
        uis_user = student.uis_username

        async def _or_default(coro, default):
            try:
                return await coro
            except Exception:
                return default

        att_raw, marks_raw, exams_raw, notices = await asyncio.gather(
            _or_default(uis_client.get_attendance(uis_user), {}),
            _or_default(uis_client.get_marks(uis_user), {}),
            _or_default(uis_client.get_exams(uis_user), {}),
            _or_default(uis_client.get_announcements(role=user.get("role")), []),
        )
        attendance = uis_acad.normalize_attendance(att_raw or {})
        marks = uis_acad.normalize_marks(marks_raw or {})
        exams = (exams_raw or {}).get("exams") or []
        notices = notices or []
        avg_att = (
            round(sum(a["percentage"] for a in attendance) / len(attendance), 1)
            if attendance
            else student.overall_attendance
        )
        grad = uis_acad.graduation_progress(student)
        return {
            "ok": True,
            "source": source,
            "student": ctx.serialize_any(student, source),
            "average_attendance": avg_att,
            "cgpa": student.cgpa,
            "credits": grad,
            "courses": len(attendance) or len(marks),
            "assessments": len(marks),
            "shortage_courses": [a for a in attendance if a["percentage"] < 75],
            "upcoming_exams": exams[:5],
            "announcements": notices[:5],
            "alerts": (
                [f"{len([a for a in attendance if a['percentage'] < 75])} course(s) below 75% attendance"]
                if any(a["percentage"] < 75 for a in attendance)
                else []
            ),
        }

    attendance = await acad.get_attendance(db, student)
    marks = await acad.get_marks(db, student)
    avg_att = round(sum(a["percentage"] for a in attendance) / len(attendance), 1) if attendance else 0
    return {
        "ok": True,
        "source": source,
        "student": ctx.serialize_any(student, source),
        "average_attendance": avg_att,
        "courses": len(attendance),
        "assessments": len(marks),
        "shortage_courses": [a for a in attendance if a["percentage"] < 75],
        "upcoming_exams": [],
        "announcements": [],
        "alerts": [],
    }


@router.get("/academic/timetable")
async def timetable(
    day: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = await _require_assist(db, user)
    if user.get("role") == "student" and not await consents.is_allowed(db, uid, "academic.timetable"):
        # Same permission chat uses for timetable facts
        if not await consents.is_allowed(db, uid, "academic.history"):
            raise HTTPException(
                status_code=403,
                detail="Timetable access is off. Enable Academic Timetable (or Academic History) in Privacy.",
            )
    student, source = await _student_or_404(db, user)
    rows: list[dict] = []
    note = ""
    if isinstance(student, LinkedStudent):
        try:
            raw = await uis_client.get_timetable(student.uis_username)
            rows = uis_acad.normalize_timetable(raw)
            source = "UIS"
        except uis_client.UisConsentDenied:
            raise HTTPException(
                status_code=403,
                detail="UIS timetable consent is denied. Allow academic.timetable in UIS Privacy.",
            )
        except uis_client.UisClientError as exc:
            note = f"UIS timetable unavailable ({exc})."
            if get_settings().ALLOW_LOCAL_SIS_FALLBACK:
                local_student, _ = await acad.resolve_student(db, user)
                if local_student:
                    rows = await acad.get_timetable(db, local_student, day)
                    student = local_student
                    source = "local"
                    note += " Showing local records."
            else:
                source = "UIS"
        if not rows and get_settings().ALLOW_LOCAL_SIS_FALLBACK:
            local_student, _ = await acad.resolve_student(db, user)
            if local_student:
                local_rows = await acad.get_timetable(db, local_student, day)
                if local_rows:
                    rows = local_rows
                    source = "local"
                    note = note or "UIS returned no class slots; showing Campus-GPT local timetable."
    elif get_settings().ALLOW_LOCAL_SIS_FALLBACK:
        rows = await acad.get_timetable(db, student, day)
        source = "local"
    else:
        rows = []
        source = "UIS"
        note = "Personal timetable is only available from the UIS database."

    if day and rows:
        dlow = day.lower()
        rows = [r for r in rows if (r.get("day") or "").lower().startswith(dlow[:3]) or (r.get("day") or "").lower() == dlow]

    await consents.log_access(db, uid, "Timetable", "Timetable page", "academic.timetable")
    return {
        "student": ctx.serialize_any(student, source),
        "slots": rows,
        "source": source,
        "count": len(rows),
        "note": note,
    }


@router.get("/academic/attendance")
async def attendance(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if not await consents.is_allowed(db, int(user["sub"]), "academic.attendance"):
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")
    student, source = await _student_or_404(db, user)
    if isinstance(student, LinkedStudent):
        try:
            rows = uis_acad.normalize_attendance(await uis_client.get_attendance(student.uis_username))
            source = "UIS"
        except uis_client.UisConsentDenied:
            raise HTTPException(status_code=403, detail="Attendance consent denied in UIS Privacy.")
        except uis_client.UisClientError:
            if get_settings().ALLOW_LOCAL_SIS_FALLBACK:
                local_student, _ = await acad.resolve_student(db, user)
                rows = await acad.get_attendance(db, local_student) if local_student else []
                source = "local"
            else:
                rows = []
                source = "UIS"
    elif get_settings().ALLOW_LOCAL_SIS_FALLBACK:
        rows = await acad.get_attendance(db, student)
    else:
        rows = []
    await consents.log_access(db, int(user["sub"]), "Attendance", "Attendance view", "academic.attendance")
    return {
        "student": ctx.serialize_any(student, source),
        "records": rows,
        "source": source,
        "data_used": [
            {
                "data": "Attendance",
                "source": source,
                "permission": "academic.attendance",
                "why": "Shown because you opened Attendance and Academic Records consent is allowed.",
            }
        ],
    }


@router.get("/academic/marks")
async def marks(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if not await consents.is_allowed(db, int(user["sub"]), "academic.marks"):
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")
    student, source = await _student_or_404(db, user)
    if isinstance(student, LinkedStudent):
        try:
            rows = uis_acad.normalize_marks(await uis_client.get_marks(student.uis_username))
            source = "UIS"
        except uis_client.UisConsentDenied:
            raise HTTPException(status_code=403, detail="Marks consent denied in UIS Privacy.")
        except uis_client.UisClientError:
            if get_settings().ALLOW_LOCAL_SIS_FALLBACK:
                local_student, _ = await acad.resolve_student(db, user)
                rows = await acad.get_marks(db, local_student) if local_student else []
                source = "local"
            else:
                rows = []
                source = "UIS"
    elif get_settings().ALLOW_LOCAL_SIS_FALLBACK:
        rows = await acad.get_marks(db, student)
    else:
        rows = []
    await consents.log_access(db, int(user["sub"]), "Marks", "Marks view", "academic.marks")
    return {
        "student": ctx.serialize_any(student, source),
        "records": rows,
        "source": source,
        "data_used": [
            {
                "data": "Marks",
                "source": source,
                "permission": "academic.marks",
                "why": "Shown because you opened Marks and Academic Records consent is allowed.",
            }
        ],
    }


@router.get("/academic/faculty")
async def faculty(
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    rows = await uis_client.get_faculty(q)
    source = "UIS"
    if not rows and get_settings().ALLOW_LOCAL_SIS_FALLBACK:
        rows = await acad.get_faculty_availability(db, q)
        source = "local"
    # Never expose personal emails on the public directory surface
    scrubbed = []
    for r in rows:
        item = dict(r) if isinstance(r, dict) else r
        if isinstance(item, dict):
            item.pop("email", None)
        scrubbed.append(item)
    return {"records": scrubbed, "source": source}


@router.get("/academic/calendar")
async def calendar(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    events = await acad.get_calendar(db)
    notices = await uis_client.get_announcements(role=user.get("role"))
    for n in notices[:10]:
        events.append(
            {
                "title": n.get("title"),
                "start_date": (n.get("published_at") or "")[:10],
                "end_date": "",
                "event_type": "announcement",
                "description": (n.get("body") or "")[:240],
                "source": "UIS",
            }
        )
    return {"events": events}


@router.get("/academic/plan")
async def plan(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await _require_assist(db, user)
    student, source = await _student_or_404(db, user)
    if isinstance(student, LinkedStudent):
        att = []
        try:
            att = uis_acad.normalize_attendance(await uis_client.get_attendance(student.uis_username))
        except Exception:
            pass
        fc = uis_acad.forecast_from_attendance(att)
        return {"source": source, "plan": fc, "student": ctx.serialize_any(student, source)}
    return await acad.build_week_plan(db, student)


@router.get("/academic/forecast")
async def forecast(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await _require_assist(db, user)
    student, source = await _student_or_404(db, user)
    if isinstance(student, LinkedStudent):
        rows = uis_acad.normalize_attendance(await uis_client.get_attendance(student.uis_username))
        data = uis_acad.forecast_from_attendance(rows)
        data["eligibility"] = uis_acad.exam_eligibility(rows)
        data["source"] = source
        return data
    return await acad.forecast_academics(db, student)


@router.post("/academic/drafts")
async def create_draft(
    req: DraftRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user.get("role") == "faculty":
        fac = await acad.resolve_faculty(db, user)
        if not fac:
            raise HTTPException(status_code=404, detail="No faculty profile linked")
        student = type(
            "DeptScope",
            (),
            {
                "full_name": "Assigned section",
                "roll_no": "n/a",
                "department": fac.department,
                "semester": 5,
                "section": "A",
            },
        )()
    else:
        student, _ = await _student_or_404(db, user)
    draft = await acad.generate_draft(
        db,
        req.draft_type,
        student,
        extra=req.extra,
        save=req.save,
        created_by=str(user.get("role", "user")),
    )
    return {"ok": True, "draft": draft, "types": acad.DRAFT_TYPES, "workflow": ["generate", "review", "edit", "export"]}


@router.get("/academic/draft-types")
async def draft_types(user: dict = Depends(get_current_user)):
    return {"types": acad.DRAFT_TYPES}
