from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Course,
    CourseOffering,
    Enrollment,
    ExamApplication,
    ExamApplicationWindow,
    FacultyProfile,
    Grade,
    RegistrationRequest,
    StudentProfile,
    User,
)
from app.security.auth import require_roles
from app.services.advisors import mentee_ids
from app.services.acknowledge import issue_acknowledgement
from app.services.audit import write_audit

router = APIRouter(prefix="/api/v1", tags=["exam-applications"])

KINDS = ("revaluation", "arrear", "backlog", "withdrawal")
WINDOWS = ("revaluation", "arrear", "backlog", "registration", "withdrawal")
FAIL = {"F", "RA", "U", "AB", "I"}
EditRoles = require_roles("university_admin", "admin", "super_admin", "developer", "coe", "director")


def _failed(letter: str, point: float) -> bool:
    return (letter or "").strip().upper() in FAIL


def _eligible(kind: str, student_semester: int, course_semester: int, letter: str, point: float) -> bool:
    if kind == "withdrawal":
        return True
    if kind == "revaluation":
        return bool((letter or "").strip())
    if not _failed(letter, point):
        return False
    if kind == "arrear":
        return course_semester == student_semester
    if kind == "backlog":
        return course_semester < student_semester
    return False


async def _window(db: AsyncSession, kind: str) -> ExamApplicationWindow:
    if kind not in WINDOWS:
        raise HTTPException(status_code=404, detail="Unknown application")
    row = (
        await db.execute(select(ExamApplicationWindow).where(ExamApplicationWindow.kind == kind))
    ).scalar_one_or_none()
    if not row:
        row = ExamApplicationWindow(kind=kind, enabled=False, note="", fee=0)
        db.add(row)
        await db.flush()
    return row


async def _courses(db: AsyncSession, student: StudentProfile, kind: str) -> list[dict]:
    grades = (
        await db.execute(
            select(Grade)
            .join(Enrollment)
            .where(Enrollment.student_id == student.id)
            .options(selectinload(Grade.enrollment).selectinload(Enrollment.offering).selectinload(CourseOffering.course))
        )
    ).scalars().all()
    applied = {
        row.course_id: row
        for row in (
            await db.execute(
                select(ExamApplication).where(ExamApplication.student_id == student.id, ExamApplication.kind == kind)
            )
        ).scalars().all()
    }
    items = []
    for grade in grades:
        enrollment = grade.enrollment
        offering = enrollment.offering if enrollment else None
        course = offering.course if offering else None
        if not course or not offering:
            continue
        if not _eligible(kind, student.semester, offering.semester, grade.letter, grade.grade_point):
            continue
        items.append(
            {
                "course_id": course.id,
                "code": course.code,
                "name": course.title,
                "semester": offering.semester,
                "letter": grade.letter,
                "applied": course.id in applied,
                "application_id": applied[course.id].id if course.id in applied else None,
                "status": applied[course.id].status if course.id in applied else "",
                "advisor_status": applied[course.id].advisor_status if course.id in applied else "",
                "hod_status": applied[course.id].hod_status if course.id in applied else "",
            }
        )
    items.sort(key=lambda row: (row["semester"], row["code"]))
    return items


class ApplyIn(BaseModel):
    course_id: int


class WindowIn(BaseModel):
    enabled: bool
    note: str = Field(default="", max_length=500)
    fee: float = Field(default=0, ge=0)


@router.get("/student/applications/{kind}")
async def student_application_window(
    kind: str,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    window = await _window(db, kind)
    courses = await _courses(db, user.student, kind) if window.enabled else []
    return {
        "kind": kind,
        "enabled": window.enabled,
        "note": window.note or "",
        "fee": window.fee or 0,
        "courses": courses,
    }


@router.post("/student/applications/{kind}")
async def apply_exam(
    kind: str,
    body: ApplyIn,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    window = await _window(db, kind)
    if not window.enabled:
        raise HTTPException(status_code=403, detail="Applications are closed. An administrator has not enabled this yet.")
    allowed = {row["course_id"] for row in await _courses(db, user.student, kind)}
    if body.course_id not in allowed:
        raise HTTPException(status_code=400, detail="This course is not open for that application.")
    existing = (
        await db.execute(
            select(ExamApplication).where(
                ExamApplication.student_id == user.student.id,
                ExamApplication.kind == kind,
                ExamApplication.course_id == body.course_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {"ok": True, "status": existing.status}
    application = ExamApplication(
        student_id=user.student.id,
        course_id=body.course_id,
        kind=kind,
        status="submitted",
        advisor_status="pending",
        hod_status="pending",
    )
    db.add(application)
    await db.flush()
    course = await db.get(Course, body.course_id)
    label = SERVICE_LABELS.get(kind, kind)
    code = course.code if course else str(body.course_id)
    title = course.title if course else ""
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind=kind,
        title=f"{label} application",
        summary=(
            f"Register {user.student.student_id}\n"
            f"Service: {label}\n"
            f"Course: {code} {title}\n"
            f"Status: submitted\n"
            f"Faculty advisor: pending\n"
            f"HoD: pending"
        ),
        email=user.email,
        status="submitted",
        ref_key=f"exam:{application.id}",
    )
    await write_audit(
        db,
        actor="UIS Student",
        user_ref=user.username,
        role=user.role,
        resource="exam_application",
        action="APPLY",
        purpose=f"{kind}:{body.course_id}",
        result="ALLOWED",
    )
    return {"ok": True, "status": "submitted", "acknowledgement": ack}


SERVICE_LABELS = {
    "revaluation": "Revaluation",
    "arrear": "Arrear",
    "backlog": "Backlog",
    "registration": "Course registration",
    "withdrawal": "Course withdrawal",
    "makeup": "Make-up",
}


async def _service_rows(db: AsyncSession) -> list[dict]:
    exams = (
        await db.execute(
            select(ExamApplication)
            .options(selectinload(ExamApplication.student).selectinload(StudentProfile.user), selectinload(ExamApplication.course))
            .order_by(ExamApplication.id.desc())
        )
    ).scalars().all()
    registrations = (
        await db.execute(
            select(RegistrationRequest)
            .options(selectinload(RegistrationRequest.student).selectinload(StudentProfile.user))
            .order_by(RegistrationRequest.id.desc())
        )
    ).scalars().all()
    offering_ids = set()
    for row in registrations:
        offering_ids.update(int(part) for part in (row.offering_ids or "").split(",") if part.strip().isdigit())
    titles = {}
    if offering_ids:
        for offering in (
            await db.execute(
                select(CourseOffering).where(CourseOffering.id.in_(offering_ids)).options(selectinload(CourseOffering.course))
            )
        ).scalars().all():
            if offering.course:
                titles[offering.id] = (offering.course.code, offering.course.title)
    rows = []
    for row in exams:
        student = row.student
        rows.append(
            {
                "id": row.id,
                "source": "exam",
                "kind": row.kind,
                "status": row.status,
                "advisor_status": row.advisor_status or "pending",
                "hod_status": row.hod_status or "pending",
                "student_id": student.student_id if student else "",
                "name": student.user.full_name if student and student.user else "",
                "section": student.section if student else "",
                "batch": student.batch if student else "",
                "code": row.course.code if row.course else "",
                "course": row.course.title if row.course else "",
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
        )
    for row in registrations:
        student = row.student
        chosen = [int(part) for part in (row.offering_ids or "").split(",") if part.strip().isdigit()]
        codes = [titles[item][0] for item in chosen if item in titles]
        names = [titles[item][1] for item in chosen if item in titles]
        rows.append(
            {
                "id": row.id,
                "source": "registration",
                "kind": row.kind,
                "status": row.status,
                "advisor_status": row.advisor_status or "pending",
                "hod_status": row.hod_status or "pending",
                "student_id": student.student_id if student else "",
                "name": student.user.full_name if student and student.user else "",
                "section": student.section if student else "",
                "batch": student.batch if student else "",
                "code": ", ".join(codes),
                "course": ", ".join(names),
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
        )
    rows.sort(key=lambda item: item["created_at"], reverse=True)
    return rows


@router.get("/admin/applications")
async def admin_applications(
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    windows = []
    for kind in WINDOWS:
        row = await _window(db, kind)
        windows.append({"kind": kind, "enabled": row.enabled, "note": row.note or "", "fee": row.fee or 0})
    return {"windows": windows, "applications": await _service_rows(db)}


@router.get("/admin/applications/export")
async def export_applications(
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: str = "all",
):
    rows = await _service_rows(db)
    selected = (kind or "all").strip().lower()
    if selected != "all":
        rows = [row for row in rows if row["kind"] == selected]
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Applied services"
    sheet.append(
        [
            "Service",
            "Register number",
            "Name",
            "Section",
            "Batch",
            "Course code",
            "Course",
            "Status",
            "Faculty advisor",
            "HoD",
            "Applied on",
        ]
    )
    for row in rows:
        sheet.append(
            [
                SERVICE_LABELS.get(row["kind"], row["kind"]),
                row["student_id"],
                row["name"],
                row["section"],
                row["batch"],
                row["code"],
                row["course"],
                row["status"],
                row["advisor_status"],
                row["hod_status"],
                row["created_at"][:10] if row["created_at"] else "",
            ]
        )
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = 22
    buffer = BytesIO()
    book.save(buffer)
    buffer.seek(0)
    filename = "applied-services.xlsx" if selected == "all" else f"applied-{selected}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/admin/applications/{kind}")
async def save_window(
    kind: str,
    body: WindowIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _window(db, kind)
    row.enabled = body.enabled
    row.note = body.note.strip()
    row.fee = body.fee
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="exam_application",
        action="ENABLE" if body.enabled else "DISABLE",
        purpose=kind,
        result="ALLOWED",
    )
    return {"ok": True, "kind": kind, "enabled": row.enabled}


def _advance(advisor_status: str, hod_status: str) -> str:
    if advisor_status == "rejected" or hod_status == "rejected":
        return "rejected"
    if advisor_status == "approved" and hod_status == "approved":
        return "approved"
    if advisor_status == "approved":
        return "advisor_approved"
    return "submitted"


class RegistrationIn(BaseModel):
    offering_ids: list[int] = Field(min_length=1)


async def _registration_courses(db: AsyncSession, student: StudentProfile, kind: str) -> list[dict]:
    if kind == "withdrawal":
        rows = (
            await db.execute(
                select(Enrollment)
                .where(Enrollment.student_id == student.id)
                .options(
                    selectinload(Enrollment.offering).selectinload(CourseOffering.course),
                    selectinload(Enrollment.offering).selectinload(CourseOffering.faculty).selectinload(FacultyProfile.user),
                )
            )
        ).scalars().all()
        offerings = [row.offering for row in rows if row.offering and row.offering.course]
    else:
        offerings = (
            await db.execute(
                select(CourseOffering)
                .where(
                    CourseOffering.semester == student.semester,
                    CourseOffering.section == student.section,
                    CourseOffering.faculty_id.is_not(None),
                )
                .options(
                    selectinload(CourseOffering.course),
                    selectinload(CourseOffering.faculty).selectinload(FacultyProfile.user),
                )
            )
        ).scalars().all()
    enrolled = set(
        (
            await db.execute(select(Enrollment.offering_id).where(Enrollment.student_id == student.id))
        ).scalars().all()
    )
    items = []
    for offering in offerings:
        course = offering.course
        if not course:
            continue
        faculty = offering.faculty.user.full_name if offering.faculty and offering.faculty.user else ""
        items.append(
            {
                "offering_id": offering.id,
                "code": course.code,
                "name": course.title,
                "credits": course.credits,
                "section": offering.section,
                "faculty": faculty,
                "enrolled": offering.id in enrolled,
            }
        )
    items.sort(key=lambda row: row["code"])
    return items


def _request_payload(row: RegistrationRequest, courses: list[dict]) -> dict:
    chosen = {int(part) for part in (row.offering_ids or "").split(",") if part.strip().isdigit()}
    picked = [course for course in courses if course["offering_id"] in chosen]
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "advisor_status": row.advisor_status,
        "hod_status": row.hod_status,
        "courses": picked or [{"offering_id": item, "code": str(item), "name": ""} for item in chosen],
        "slip": row.status == "approved",
    }


@router.get("/student/registration")
async def student_registration(
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: str = "registration",
):
    if kind not in ("registration", "withdrawal"):
        raise HTTPException(status_code=404, detail="Unknown registration")
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    window = await _window(db, kind)
    courses = await _registration_courses(db, user.student, kind) if window.enabled else []
    current = (
        await db.execute(
            select(RegistrationRequest)
            .where(RegistrationRequest.student_id == user.student.id, RegistrationRequest.kind == kind)
            .order_by(RegistrationRequest.id.desc())
        )
    ).scalars().first()
    return {
        "kind": kind,
        "enabled": window.enabled,
        "note": window.note or "",
        "fee": window.fee or 0,
        "courses": courses,
        "request": _request_payload(current, courses) if current else None,
    }


@router.post("/student/registration")
async def submit_registration(
    body: RegistrationIn,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: str = "registration",
):
    if kind not in ("registration", "withdrawal"):
        raise HTTPException(status_code=404, detail="Unknown registration")
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    window = await _window(db, kind)
    if not window.enabled:
        raise HTTPException(status_code=403, detail="Registration is closed. An administrator has not enabled it yet.")
    allowed = {row["offering_id"]: row for row in await _registration_courses(db, user.student, kind)}
    chosen = []
    for offering_id in body.offering_ids:
        course = allowed.get(offering_id)
        if not course:
            raise HTTPException(status_code=400, detail="One of the courses is not open for this semester.")
        if kind == "registration" and course["enrolled"]:
            raise HTTPException(status_code=400, detail=f"{course['code']} is already on this student's record.")
        chosen.append(offering_id)
    latest = (
        await db.execute(
            select(RegistrationRequest)
            .where(RegistrationRequest.student_id == user.student.id, RegistrationRequest.kind == kind)
            .order_by(RegistrationRequest.id.desc())
        )
    ).scalars().first()
    if latest and latest.status != "rejected":
        raise HTTPException(status_code=400, detail="A request is already with the faculty advisor or HoD.")
    actor_name = user.username
    actor_role = user.role
    request_row = RegistrationRequest(
        student_id=user.student.id,
        kind=kind,
        offering_ids=",".join(str(item) for item in chosen),
        status="submitted",
        advisor_status="pending",
        hod_status="pending",
    )
    db.add(request_row)
    await db.flush()
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind=kind,
        title="Registration submitted" if kind == "registration" else "Withdrawal submitted",
        summary=(
            f"Register {user.student.student_id}\n"
            f"Service: {kind}\n"
            f"Courses: {', '.join(str(item) for item in chosen)}\n"
            f"Status: submitted\n"
            f"Faculty advisor: pending\n"
            f"HoD: pending"
        ),
        email=user.email,
        status="submitted",
        ref_key=f"registration:{request_row.id}",
    )
    await write_audit(
        db,
        actor="UIS Student",
        user_ref=actor_name,
        role=actor_role,
        resource="registration",
        action="SUBMIT",
        purpose=f"{kind}:{','.join(str(item) for item in chosen)}",
        result="ALLOWED",
    )
    return {"ok": True, "status": "submitted", "acknowledgement": ack}


async def _slip_student(student: StudentProfile) -> dict:
    program = student.program
    return {
        "student_id": student.student_id,
        "name": student.user.full_name if student.user else "",
        "programme": program.name if program else "",
        "section": student.section,
        "semester": student.semester,
        "batch": student.batch,
    }


@router.get("/student/slips/exam/{application_id}")
async def exam_slip(
    application_id: int,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    row = (
        await db.execute(
            select(ExamApplication)
            .where(ExamApplication.id == application_id, ExamApplication.student_id == user.student.id)
            .options(
                selectinload(ExamApplication.course),
                selectinload(ExamApplication.student).selectinload(StudentProfile.user),
                selectinload(ExamApplication.student).selectinload(StudentProfile.program),
            )
        )
    ).scalar_one_or_none()
    if not row or row.status != "approved":
        raise HTTPException(status_code=404, detail="The acknowledgement slip is issued after the HoD approves.")
    course = row.course
    return {
        **await _slip_student(row.student),
        "kind": row.kind,
        "issued_on": row.created_at.date().isoformat() if row.created_at else "",
        "courses": [{"code": course.code, "name": course.title}] if course else [],
    }


@router.get("/student/slips/registration/{request_id}")
async def registration_slip(
    request_id: int,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    row = (
        await db.execute(
            select(RegistrationRequest)
            .where(RegistrationRequest.id == request_id, RegistrationRequest.student_id == user.student.id)
            .options(selectinload(RegistrationRequest.student).selectinload(StudentProfile.user), selectinload(RegistrationRequest.student).selectinload(StudentProfile.program))
        )
    ).scalar_one_or_none()
    if not row or row.status != "approved":
        raise HTTPException(status_code=404, detail="The acknowledgement slip is issued after the HoD approves.")
    ids = [int(part) for part in (row.offering_ids or "").split(",") if part.strip().isdigit()]
    offerings = []
    if ids:
        offerings = (
            await db.execute(
                select(CourseOffering).where(CourseOffering.id.in_(ids)).options(selectinload(CourseOffering.course))
            )
        ).scalars().all()
    return {
        **await _slip_student(row.student),
        "kind": row.kind,
        "issued_on": row.created_at.date().isoformat() if row.created_at else "",
        "courses": [{"code": item.course.code, "name": item.course.title} for item in offerings if item.course],
    }


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


@router.get("/faculty/approvals")
async def faculty_approvals(
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    exams = (
        await db.execute(
            select(ExamApplication)
            .options(selectinload(ExamApplication.student).selectinload(StudentProfile.user), selectinload(ExamApplication.course))
            .order_by(ExamApplication.id.desc())
        )
    ).scalars().all()
    registrations = (
        await db.execute(
            select(RegistrationRequest)
            .options(selectinload(RegistrationRequest.student).selectinload(StudentProfile.user))
            .order_by(RegistrationRequest.id.desc())
        )
    ).scalars().all()
    advised = await mentee_ids(db, user.faculty.id) if user.faculty else set()
    items = []
    for row in exams:
        if user.role != "hod" and (not row.student or row.student.id not in advised):
            continue
        items.append(
            {
                "source": "exam",
                "id": row.id,
                "kind": row.kind,
                "student_id": row.student.student_id if row.student else "",
                "name": row.student.user.full_name if row.student and row.student.user else "",
                "detail": f"{row.course.code} · {row.course.title}" if row.course else "",
                "status": row.status,
                "advisor_status": row.advisor_status or "pending",
                "hod_status": row.hod_status or "pending",
                "can_advise": user.role != "hod",
                "can_hod": user.role == "hod",
            }
        )
    id_set = set()
    for row in registrations:
        id_set.update(int(part) for part in (row.offering_ids or "").split(",") if part.strip().isdigit())
    code_by_id = {}
    if id_set:
        for offering in (
            await db.execute(select(CourseOffering).where(CourseOffering.id.in_(id_set)).options(selectinload(CourseOffering.course)))
        ).scalars().all():
            if offering.course:
                code_by_id[offering.id] = f"{offering.course.code} · {offering.course.title}"
    for row in registrations:
        student = row.student
        if user.role != "hod" and (not student or student.id not in advised):
            continue
        chosen = [int(part) for part in (row.offering_ids or "").split(",") if part.strip().isdigit()]
        items.append(
            {
                "source": "registration",
                "id": row.id,
                "kind": row.kind,
                "student_id": row.student.student_id if row.student else "",
                "name": row.student.user.full_name if row.student and row.student.user else "",
                "detail": ", ".join(code_by_id.get(item, str(item)) for item in chosen),
                "status": row.status,
                "advisor_status": row.advisor_status or "pending",
                "hod_status": row.hod_status or "pending",
                "can_advise": user.role != "hod",
                "can_hod": user.role == "hod",
            }
        )
    return {"items": items}


@router.post("/faculty/approvals/{source}/{request_id}")
async def decide_approval(
    source: str,
    request_id: int,
    body: DecisionIn,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if source not in ("exam", "registration"):
        raise HTTPException(status_code=404, detail="Unknown request")
    model = ExamApplication if source == "exam" else RegistrationRequest
    row = (await db.execute(select(model).where(model.id == request_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    if user.role == "hod":
        if (row.advisor_status or "pending") != "approved":
            raise HTTPException(status_code=400, detail="The faculty advisor approves this before the HoD.")
        row.hod_status = body.decision
        stage = "hod"
    else:
        if not user.faculty or row.student_id not in await mentee_ids(db, user.faculty.id):
            raise HTTPException(status_code=403, detail="This student is not assigned to you as faculty advisor")
        row.advisor_status = body.decision
        stage = "advisor"
    row.status = _advance(row.advisor_status or "pending", row.hod_status or "pending")
    student = (
        await db.execute(
            select(StudentProfile).where(StudentProfile.id == row.student_id).options(selectinload(StudentProfile.user))
        )
    ).scalar_one_or_none()
    if student and student.user:
        label = SERVICE_LABELS.get(row.kind, row.kind)
        await issue_acknowledgement(
            db,
            user=student.user,
            kind=row.kind,
            title=f"{label} application",
            summary=(
                f"Register {student.student_id}\n"
                f"Service: {label}\n"
                f"Status: {row.status}\n"
                f"Faculty advisor: {row.advisor_status}\n"
                f"HoD: {row.hod_status}"
            ),
            email=student.user.email,
            status=row.status,
            ref_key=f"{source}:{row.id}",
        )
    actor_name = user.username
    actor_role = user.role
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=actor_name,
        role=actor_role,
        resource="approval",
        action=body.decision.upper(),
        purpose=f"{source}:{request_id}:{stage}",
        result="ALLOWED",
    )
    return {"ok": True, "status": row.status}
