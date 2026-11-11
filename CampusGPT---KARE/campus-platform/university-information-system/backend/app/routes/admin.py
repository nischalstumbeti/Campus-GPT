import base64
import csv
import io
import re
from datetime import date
from typing import Annotated, Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.utils.db_status import get_database_status
from app.models import (
    Achievement,
    AttendanceRecord,
    AuditLog,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    FacultyAdvisor,
    FacultyProfile,
    Grade,
    HostelAllocation,
    Mark,
    Program,
    StudentFee,
    StudentProfile,
    User,
)
from app.routes.fees import _fee_status
from app.security.auth import hash_password, require_roles
from app.services.advisors import list_advisors
from app.services.service_monitor import check_services
from app.services.attendance_board import courses_for_student, save_session
from app.services.acknowledge import issue_acknowledgement
from app.services.audit import write_audit
from app.services.confirm import PhraseIn, require_phrase
from app.services.course_grade import GRADE_POINTS, assign_course_grade
from app.services.purge import delete_course_record, delete_offerings, delete_user_record
from app.services.user_photo import apply_photo, photo_data_url
from app.security.auth import create_access_token
from app.services import email_service as mail

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

AdminRoles = require_roles(
    "university_admin", "admin", "super_admin", "developer", "director", "coe", "operator", "hod", "school_dean"
)
EditRoles = require_roles("university_admin", "admin", "super_admin", "developer", "operator")
PhotoRoles = require_roles("university_admin", "admin", "super_admin", "developer", "operator")

_FEE_STATUS_RANK = {"overdue": 0, "due": 1, "partial": 2, "paid": 3, "none": 4}


def _overall_fee_status(fees: list[StudentFee]) -> str:
    if not fees:
        return "none"
    worst = "paid"
    worst_rank = _FEE_STATUS_RANK["paid"]
    for f in fees:
        status = _fee_status(f.total_amount or 0, f.paid_amount or 0, f.deadline or "")
        rank = _FEE_STATUS_RANK.get(status, 4)
        if rank < worst_rank:
            worst = status
            worst_rank = rank
    return worst


@router.get("/dashboard")
async def dashboard(
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    students = (await db.execute(select(func.count()).select_from(StudentProfile))).scalar() or 0
    faculty = (await db.execute(select(func.count()).select_from(FacultyProfile))).scalar() or 0
    depts = (await db.execute(select(func.count()).select_from(Department))).scalar() or 0
    courses = (await db.execute(select(func.count()).select_from(Course))).scalar() or 0
    return {
        "welcome": f"Welcome, {user.full_name}",
        "role": user.role,
        "stats": {
            "students": students,
            "faculty": faculty,
            "departments": depts,
            "courses": courses,
        },
    }


@router.get("/database-status")
async def database_status(user: Annotated[User, Depends(AdminRoles)]):
    """Live UIS database connection status for the admin dashboard."""
    return await get_database_status()


@router.get("/services/status")
async def services_status(user: Annotated[User, Depends(AdminRoles)]):
    """Live status of UIS, Campus-GPT, SmartTimetable and database services."""
    return await check_services()


class TestEmailBody(BaseModel):
    to: Optional[str] = Field(default=None, description="Recipient; defaults to SMTP_USER")


@router.get("/email-status")
async def email_status(user: Annotated[User, Depends(AdminRoles)]):
    """SMTP configuration status (no secrets)."""
    return mail.email_config_status()


@router.post("/test-email")
async def test_email(
    user: Annotated[User, Depends(AdminRoles)],
    body: TestEmailBody = TestEmailBody(),
):
    """Send a test alert email from the configured mailbox."""
    return await mail.send_test_email(body.to)


@router.get("/students/filter-options")
async def student_filter_options(
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Distinct values for admin student filter dropdowns."""
    years = [r[0] for r in (await db.execute(select(StudentProfile.year).distinct().order_by(StudentProfile.year))).all() if r[0] is not None]
    semesters = [
        r[0]
        for r in (await db.execute(select(StudentProfile.semester).distinct().order_by(StudentProfile.semester))).all()
        if r[0] is not None
    ]
    sections = [
        r[0]
        for r in (await db.execute(select(StudentProfile.section).distinct().order_by(StudentProfile.section))).all()
        if r[0]
    ]
    batches = [
        r[0] for r in (await db.execute(select(StudentProfile.batch).distinct().order_by(StudentProfile.batch))).all() if r[0]
    ]
    depts = (await db.execute(select(Department.code, Department.name).order_by(Department.code))).all()
    return {
        "years": years,
        "semesters": semesters,
        "sections": sections,
        "batches": batches,
        "departments": [{"code": c, "name": n} for c, n in depts],
        "residence": [
            {"value": "hostel", "label": "Hostel"},
            {"value": "day_scholar", "label": "Day scholar"},
        ],
        "fee_status": [
            {"value": "paid", "label": "Paid"},
            {"value": "partial", "label": "Partially paid"},
            {"value": "due", "label": "Due"},
            {"value": "overdue", "label": "Overdue"},
            {"value": "none", "label": "No fee record"},
        ],
        "fee_category": [
            {"value": "hostel", "label": "Hostel fee"},
            {"value": "day_scholar", "label": "Day scholar fee"},
            {"value": "bus", "label": "Bus fee"},
            {"value": "all", "label": "General / all"},
        ],
    }


@router.get("/students")
async def list_students(
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
    q: Optional[str] = None,
    year: Optional[int] = None,
    semester: Optional[int] = None,
    section: Optional[str] = None,
    batch: Optional[str] = None,
    department: Optional[str] = None,
    residence: Optional[str] = None,
    fee_status: Optional[str] = None,
    fee_category: Optional[str] = None,
    has_backlogs: Optional[bool] = None,
    min_attendance: Optional[float] = None,
    max_attendance: Optional[float] = None,
    is_active: Optional[bool] = None,
):
    """List students with academic, residence (hostel/day scholar), and fee filters."""
    query = (
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.id)
        .outerjoin(Program, StudentProfile.program_id == Program.id)
        .outerjoin(Department, Program.department_id == Department.id)
        .options(selectinload(StudentProfile.program))
        .order_by(StudentProfile.student_id)
    )
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            (StudentProfile.student_id.ilike(like)) | (User.full_name.ilike(like)) | (User.email.ilike(like))
        )
    if year is not None:
        query = query.where(StudentProfile.year == year)
    if semester is not None:
        query = query.where(StudentProfile.semester == semester)
    if section:
        query = query.where(StudentProfile.section == section.strip())
    if batch:
        query = query.where(StudentProfile.batch == batch.strip())
    if department:
        query = query.where(Department.code == department.strip().upper())
    if is_active is not None:
        query = query.where(User.is_active.is_(is_active))
    if has_backlogs is True:
        query = query.where(StudentProfile.backlogs > 0)
    elif has_backlogs is False:
        query = query.where(StudentProfile.backlogs == 0)
    if min_attendance is not None:
        query = query.where(StudentProfile.overall_attendance >= min_attendance)
    if max_attendance is not None:
        query = query.where(StudentProfile.overall_attendance <= max_attendance)

    # Residence: hostel allocation vs day scholar
    if residence in ("hostel", "day_scholar"):
        hostel_ids = select(HostelAllocation.student_id)
        if residence == "hostel":
            query = query.where(StudentProfile.id.in_(hostel_ids))
        else:
            query = query.where(~StudentProfile.id.in_(hostel_ids))

    rows = (await db.execute(query)).all()
    if not rows:
        return {"items": [], "total": 0, "count": 0}

    profile_ids = [sp.id for sp, _ in rows]
    user_ids = [u.id for _, u in rows]

    alloc_rows = (
        await db.execute(select(HostelAllocation.student_id).where(HostelAllocation.student_id.in_(profile_ids)))
    ).all()
    hostel_set = {r[0] for r in alloc_rows}

    fee_q = select(StudentFee).where(StudentFee.user_id.in_(user_ids))
    if fee_category:
        fee_q = fee_q.where(StudentFee.category == fee_category)
    fees = (await db.execute(fee_q)).scalars().all()
    fees_by_user: dict[int, list[StudentFee]] = {}
    for f in fees:
        fees_by_user.setdefault(f.user_id, []).append(f)

    # Department codes for profiles
    dept_map: dict[int, str] = {}
    prog_ids = {sp.program_id for sp, _ in rows if sp.program_id}
    if prog_ids:
        dept_rows = (
            await db.execute(
                select(Program.id, Department.code)
                .join(Department, Program.department_id == Department.id)
                .where(Program.id.in_(prog_ids))
            )
        ).all()
        dept_map = {pid: code for pid, code in dept_rows}

    items = []
    for sp, u in rows:
        res = "hostel" if sp.id in hostel_set else "day_scholar"
        status_fees = fees_by_user.get(u.id, [])
        overall = _overall_fee_status(status_fees)
        if fee_status:
            want = fee_status.strip().lower()
            if want == "none":
                if status_fees:
                    continue
            elif overall != want:
                continue

        paid_total = round(sum(f.paid_amount or 0 for f in status_fees), 2)
        due_total = round(sum(f.total_amount or 0 for f in status_fees), 2)
        items.append(
            {
                "student_id": sp.student_id,
                "user_id": u.id,
                "name": u.full_name,
                "email": u.email,
                "year": sp.year,
                "semester": sp.semester,
                "section": sp.section,
                "batch": sp.batch,
                "cgpa": sp.cgpa,
                "attendance": sp.overall_attendance,
                "credits_completed": sp.credits_completed,
                "credits_required": sp.credits_required,
                "backlogs": sp.backlogs,
                "program": sp.program.name if sp.program else None,
                "department_code": dept_map.get(sp.program_id) or u.department_code,
                "residence": res,
                "fee_status": overall,
                "fee_paid": paid_total,
                "fee_total": due_total,
                "is_active": u.is_active,
            }
        )

    total = len(items)
    page = items[offset : offset + max(1, min(limit, 500))]
    return {"items": page, "total": total, "count": len(page)}


async def _student_marks_and_achievements(db: AsyncSession, sp: StudentProfile) -> tuple[list[dict], list[dict]]:
    enrollments = (
        await db.execute(
            select(Enrollment)
            .where(Enrollment.student_id == sp.id)
            .options(
                selectinload(Enrollment.offering).selectinload(CourseOffering.course),
            )
        )
    ).scalars().all()
    marks_out: list[dict] = []
    for e in enrollments:
        course = e.offering.course if e.offering else None
        code = course.code if course else ""
        title = course.title if course else ""
        mark_rows = (
            await db.execute(select(Mark).where(Mark.enrollment_id == e.id).order_by(Mark.id))
        ).scalars().all()
        grade = (
            await db.execute(select(Grade).where(Grade.enrollment_id == e.id))
        ).scalar_one_or_none()
        if not mark_rows and not grade:
            continue
        marks_out.append(
            {
                "course_code": code,
                "course_title": title,
                "section": e.offering.section if e.offering else "",
                "grade": grade.letter if grade else None,
                "grade_point": grade.grade_point if grade else None,
                "assessments": [
                    {
                        "assessment": m.assessment,
                        "score": m.score,
                        "max_score": m.max_score,
                    }
                    for m in mark_rows
                ],
            }
        )
    achievements = (
        await db.execute(select(Achievement).where(Achievement.student_id == sp.id).order_by(Achievement.id.desc()))
    ).scalars().all()
    ach_out = [
        {
            "id": a.id,
            "title": a.title,
            "category": a.category,
            "description": a.description or "",
            "awarded_on": a.awarded_on.isoformat() if a.awarded_on else None,
        }
        for a in achievements
    ]
    return marks_out, ach_out


@router.get("/students/roster")
async def students_roster(
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Optional[str] = None,
    year: Optional[int] = None,
    department: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
):
    """Full student roster for admin: profile + marks + achievements."""
    query = (
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.id)
        .outerjoin(Program, StudentProfile.program_id == Program.id)
        .outerjoin(Department, Program.department_id == Department.id)
        .options(selectinload(StudentProfile.program))
        .order_by(StudentProfile.student_id)
    )
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            (StudentProfile.student_id.ilike(like)) | (User.full_name.ilike(like)) | (User.email.ilike(like))
        )
    if year is not None:
        query = query.where(StudentProfile.year == year)
    if department:
        query = query.where(Department.code == department.strip().upper())

    # Count matching profiles, then paginate before loading marks/achievements
    id_q = (
        select(StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .outerjoin(Program, StudentProfile.program_id == Program.id)
        .outerjoin(Department, Program.department_id == Department.id)
    )
    if q:
        like = f"%{q.strip()}%"
        id_q = id_q.where(
            (StudentProfile.student_id.ilike(like)) | (User.full_name.ilike(like)) | (User.email.ilike(like))
        )
    if year is not None:
        id_q = id_q.where(StudentProfile.year == year)
    if department:
        id_q = id_q.where(Department.code == department.strip().upper())
    total = (await db.execute(select(func.count()).select_from(id_q.subquery()))).scalar() or 0
    page_limit = max(1, min(limit, 100))
    page_offset = max(0, offset)
    rows = (await db.execute(query.offset(page_offset).limit(page_limit))).all()
    items = []
    for sp, u in rows:
        marks, achievements = await _student_marks_and_achievements(db, sp)
        items.append(
            {
                "student_id": sp.student_id,
                "name": u.full_name,
                "email": u.email,
                "year": sp.year,
                "semester": sp.semester,
                "section": sp.section,
                "batch": sp.batch,
                "cgpa": sp.cgpa,
                "attendance": sp.overall_attendance,
                "program": sp.program.name if sp.program else None,
                "department_code": u.department_code,
                "is_active": u.is_active,
                "marks": marks,
                "achievements": achievements,
                "marks_count": sum(len(m.get("assessments") or []) for m in marks),
                "achievements_count": len(achievements),
            }
        )
    return {"items": items, "total": total, "count": len(items), "limit": page_limit, "offset": page_offset}


@router.get("/students/{student_id}")
async def get_student(
    student_id: str,
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.student_id == student_id)
        .options(selectinload(StudentProfile.user), selectinload(StudentProfile.program))
    )
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    marks, achievements = await _student_marks_and_achievements(db, sp)
    return {
        "student_id": sp.student_id,
        "name": sp.user.full_name,
        "email": sp.user.email,
        "username": sp.user.username,
        "year": sp.year,
        "semester": sp.semester,
        "section": sp.section,
        "batch": sp.batch,
        "cgpa": sp.cgpa,
        "overall_attendance": sp.overall_attendance,
        "credits_completed": sp.credits_completed,
        "credits_required": sp.credits_required,
        "backlogs": sp.backlogs,
        "program": sp.program.name if sp.program else None,
        "is_active": sp.user.is_active,
        "photo_url": sp.photo_url or "",
        "marks": marks,
        "achievements": achievements,
    }


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    year: Optional[int] = Field(default=None, ge=1, le=6)
    semester: Optional[int] = Field(default=None, ge=1, le=12)
    section: Optional[str] = None
    batch: Optional[str] = None
    cgpa: Optional[float] = Field(default=None, ge=0, le=10)
    overall_attendance: Optional[float] = Field(default=None, ge=0, le=100)
    credits_completed: Optional[int] = Field(default=None, ge=0)
    credits_required: Optional[int] = Field(default=None, ge=1)
    backlogs: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


@router.patch("/students/{student_id}")
async def update_student(
    student_id: str,
    body: StudentUpdate,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.student_id == student_id)
        .options(selectinload(StudentProfile.user))
    )
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")

    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        sp.user.full_name = data.pop("name")
    if "email" in data:
        sp.user.email = data.pop("email")
    if "is_active" in data:
        sp.user.is_active = data.pop("is_active")
    for key, val in data.items():
        setattr(sp, key, val)

    await db.commit()
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="student",
        action="UPDATE",
        purpose=student_id,
        result="ALLOWED",
    )
    return {"ok": True, "student_id": student_id}


class MarkEntry(BaseModel):
    course_code: str = Field(min_length=1, max_length=32)
    assessment: str = Field(min_length=1, max_length=64)
    score: float = Field(ge=0)
    max_score: float = Field(default=100, gt=0)


@router.get("/students/{student_id}/marks")
async def admin_student_marks(
    student_id: str,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sp = (
        await db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id))
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    enrollments = (
        await db.execute(
            select(Enrollment)
            .where(Enrollment.student_id == sp.id)
            .options(selectinload(Enrollment.offering).selectinload(CourseOffering.course))
        )
    ).scalars().all()
    ids = [e.id for e in enrollments]
    mark_rows = []
    if ids:
        mark_rows = (await db.execute(select(Mark).where(Mark.enrollment_id.in_(ids)).order_by(Mark.id))).scalars().all()
    grouped: dict[int, list] = {}
    for mark in mark_rows:
        grouped.setdefault(mark.enrollment_id, []).append(mark)
    courses = []
    for enrollment in enrollments:
        course = enrollment.offering.course if enrollment.offering else None
        if not course:
            continue
        assessments = grouped.get(enrollment.id, [])
        courses.append(
            {
                "code": course.code,
                "name": course.title,
                "status": "ok" if assessments else "attention",
                "assessments": [
                    {"id": m.id, "assessment": m.assessment, "score": m.score, "max_score": m.max_score}
                    for m in assessments
                ],
            }
        )
    courses.sort(key=lambda row: row["code"])
    return {"student_id": student_id, "courses": courses}


async def _upsert_mark(
    db: AsyncSession,
    student_id: str,
    course_code: str,
    assessment: str,
    score: float,
    max_score: float,
) -> str:
    if max_score <= 0:
        raise HTTPException(status_code=400, detail="Maximum must be greater than zero.")
    if score < 0 or score > max_score:
        raise HTTPException(status_code=400, detail="Score cannot be higher than the maximum.")
    sp = (
        await db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id))
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    enrollment = (
        await db.execute(
            select(Enrollment)
            .join(CourseOffering)
            .join(Course)
            .where(Enrollment.student_id == sp.id, Course.code == course_code)
        )
    ).scalars().first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="That course is not on this student's record.")
    row = (
        await db.execute(
            select(Mark).where(Mark.enrollment_id == enrollment.id, Mark.assessment == assessment)
        )
    ).scalar_one_or_none()
    if row:
        row.score = score
        row.max_score = max_score
        return "updated"
    db.add(Mark(enrollment_id=enrollment.id, assessment=assessment, score=score, max_score=max_score))
    return "created"


@router.post("/students/{student_id}/marks")
async def save_student_mark(
    student_id: str,
    body: MarkEntry,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    action = await _upsert_mark(
        db,
        student_id.strip(),
        body.course_code.strip(),
        body.assessment.strip(),
        body.score,
        body.max_score,
    )
    await db.commit()
    return {"ok": True, "action": action, "assessment": body.assessment.strip(), "score": body.score, "max_score": body.max_score}


MARKS_CSV_HEADERS = ["student_id", "course_code", "assessment", "score", "max_score"]


def _mark_number(raw: str, field: str) -> float:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be a number") from exc


@router.get("/marks/template")
async def marks_import_template(user: Annotated[User, Depends(EditRoles)]):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(MARKS_CSV_HEADERS)
    writer.writerow(["KARE2024CSE045", "CSE501", "Sessional-I", "40", "50"])
    writer.writerow(["KARE2024CSE045", "CSE501", "End Semester", "72", "100"])
    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=uis_marks_import_template.csv"},
    )


@router.post("/marks/import")
async def import_marks(
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 5_000_000:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    try:
        rows = _parse_upload_rows(file.filename or "marks.csv", content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found in file")

    saved: list[dict] = []
    errors: list[dict] = []
    actor_name = user.username
    actor_role = user.role
    for idx, row in enumerate(rows, start=2):
        try:
            student_id = _row_get(row, "student_id", "student id", "roll_no", "roll", "register number")
            course_code = _row_get(row, "course_code", "course code", "code", "course")
            assessment = _row_get(row, "assessment", "assessment name", "exam")
            if not student_id or not course_code or not assessment:
                raise HTTPException(status_code=400, detail="student_id, course_code, and assessment are required")
            score = _mark_number(_row_get(row, "score", "marks", "mark"), "score")
            max_raw = _row_get(row, "max_score", "max", "maximum", default="100") or "100"
            max_score = _mark_number(max_raw, "max_score")
            action = await _upsert_mark(db, student_id, course_code, assessment, score, max_score)
            await db.commit()
            saved.append({"row": idx, "student_id": student_id, "course_code": course_code, "assessment": assessment, "action": action})
        except HTTPException as exc:
            await db.rollback()
            detail = exc.detail if isinstance(exc.detail, str) else "Could not save this row"
            errors.append({"row": idx, "error": detail})
        except Exception as exc:
            await db.rollback()
            errors.append({"row": idx, "error": str(exc)})

    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=actor_name,
        role=actor_role,
        resource="marks",
        action="BULK_IMPORT",
        purpose=f"saved={len(saved)} errors={len(errors)} file={file.filename}",
        result="ALLOWED",
    )
    await db.commit()
    return {
        "ok": True,
        "saved_count": len(saved),
        "error_count": len(errors),
        "saved": saved[:50],
        "errors": errors[:50],
        "message": f"Saved {len(saved)} mark(s); {len(errors)} row(s) failed.",
    }


class AttendanceSessionIn(BaseModel):
    course_code: str = Field(min_length=1, max_length=32)
    entry_date: date
    slot_name: str = Field(min_length=3, max_length=64)
    status: str = Field(min_length=1, max_length=8)
    session_id: Optional[int] = None


@router.get("/students/{student_id}/attendance")
async def admin_student_attendance(
    student_id: str,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sp = (
        await db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id))
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"student_id": student_id, "courses": await courses_for_student(db, sp.id)}


@router.post("/students/{student_id}/attendance")
async def save_admin_attendance(
    student_id: str,
    body: AttendanceSessionIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sp = (
        await db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id))
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    enrollment = (
        await db.execute(
            select(Enrollment)
            .join(CourseOffering)
            .join(Course)
            .where(Enrollment.student_id == sp.id, Course.code == body.course_code.strip())
        )
    ).scalars().first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="That course is not on this student's record.")
    try:
        row = await save_session(db, enrollment.id, body.entry_date, body.slot_name, body.status, body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="attendance",
        action="SESSION",
        purpose=f"student:{student_id} course:{body.course_code}",
        result="ALLOWED",
    )
    return {"ok": True, "id": row.id, "status": row.status}


@router.post("/students/{student_id}/photo")
async def upload_student_photo(
    student_id: str,
    user: Annotated[User, Depends(PhotoRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.student_id == student_id)
        .options(selectinload(StudentProfile.user))
    )
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    try:
        photo = photo_data_url(await file.read(), file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    apply_photo(sp.user, sp, photo)
    await db.commit()
    return {"ok": True, "photo_url": photo}


@router.delete("/students/{student_id}/photo")
async def remove_student_photo(
    student_id: str,
    user: Annotated[User, Depends(PhotoRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id))
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    owner = (await db.execute(select(User).where(User.id == sp.user_id))).scalar_one_or_none()
    apply_photo(owner, sp, "")
    await db.commit()
    return {"ok": True, "photo_url": ""}


@router.get("/users")
async def list_users(
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
    role: Optional[str] = None,
    q: Optional[str] = None,
):
    query = select(User).order_by(User.id.desc()).offset(offset).limit(limit)
    if role:
        query = query.where(User.role == role)
    if q:
        like = f"%{q}%"
        query = query.where(
            (User.username.ilike(like)) | (User.full_name.ilike(like)) | (User.email.ilike(like))
        )
    rows = (await db.execute(query)).scalars().all()
    return {
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "department_code": u.department_code,
                "designation": u.designation or "",
                "school": u.school or "",
                "is_active": u.is_active,
                "has_photo": bool(u.photo_url),
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in rows
        ]
    }


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str
    full_name: str
    password: str = Field(min_length=6)
    role: str = "student"
    department_code: Optional[str] = None
    # student fields
    student_id: Optional[str] = None
    year: Optional[int] = 1
    semester: Optional[int] = 1
    section: Optional[str] = "A"
    batch: Optional[str] = None
    # faculty fields
    faculty_id: Optional[str] = None
    designation: Optional[str] = ""
    school: Optional[str] = ""
    abc_id: Optional[str] = ""
    residence: Optional[str] = ""
    transport: Optional[str] = ""
    residence_detail: Optional[str] = ""


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    department_code: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)
    designation: Optional[str] = None
    school: Optional[str] = None
    office: Optional[str] = None
    cabin_block: Optional[str] = None
    abc_id: Optional[str] = None
    residence: Optional[str] = None
    transport: Optional[str] = None
    residence_detail: Optional[str] = None
    student_id: Optional[str] = None
    year: Optional[int] = None
    semester: Optional[int] = None
    section: Optional[str] = None
    batch: Optional[str] = None


STUDENT_EDIT_FIELDS = {"student_id", "year", "semester", "section", "batch"}


ALLOWED_ROLES = {
    "student",
    "faculty",
    "staff",
    "hod",
    "department_admin",
    "exam_admin",
    "hostel_admin",
    "admin",
    "university_admin",
    "school_dean",
    "director",
    "operator",
    "coe",
    "developer",
}

ROLE_ALIASES = {
    "student": "student",
    "faculty": "faculty",
    "teacher": "faculty",
    "professor": "faculty",
    "hod": "hod",
    "head of department": "hod",
    "staff": "staff",
    "hostel_admin": "hostel_admin",
    "hostel admin": "hostel_admin",
    "hostel warden": "hostel_admin",
    "warden": "hostel_admin",
    "exam_admin": "exam_admin",
    "exam admin": "exam_admin",
    "department_admin": "department_admin",
    "department admin": "department_admin",
    "admin": "admin",
    "university_admin": "university_admin",
    "university admin": "university_admin",
    "school_dean": "school_dean",
    "school dean": "school_dean",
    "dean": "school_dean",
    "director": "director",
    "operator": "operator",
    "coe": "coe",
    "principal": "coe",
    "coe / principal": "coe",
    "coe principal": "coe",
    "developer": "developer",
    "head of the department": "hod",
}

BULK_TEMPLATE_HEADERS = [
    "role",
    "username",
    "email",
    "full_name",
    "password",
    "department_code",
    "student_id",
    "year",
    "semester",
    "section",
    "batch",
    "faculty_id",
    "designation",
]


def _normalize_role(raw: str) -> str:
    key = re.sub(r"[\s\-]+", " ", (raw or "").strip().lower())
    key_us = key.replace(" ", "_")
    return ROLE_ALIASES.get(key) or ROLE_ALIASES.get(key_us) or ""


def _row_get(row: dict[str, Any], *keys: str, default: str = "") -> str:
    lower = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for key in keys:
        if key.lower() in lower and lower[key.lower()] not in (None, ""):
            return str(lower[key.lower()]).strip()
    return default


async def _create_user_record(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    full_name: str,
    password: str,
    role: str,
    department_code: Optional[str] = None,
    student_id: Optional[str] = None,
    year: Optional[int] = 1,
    semester: Optional[int] = 1,
    section: Optional[str] = "A",
    batch: Optional[str] = None,
    faculty_id: Optional[str] = None,
    designation: Optional[str] = "",
    school: Optional[str] = "",
    abc_id: Optional[str] = "",
    residence: Optional[str] = "",
    transport: Optional[str] = "",
    residence_detail: Optional[str] = "",
) -> User:
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    username = (username or "").strip()
    email = (email or "").strip().lower()
    full_name = (full_name or "").strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    if not full_name:
        raise HTTPException(status_code=400, detail="Full name required")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    exists = (
        await db.execute(select(User).where((User.username == username) | (User.email == email)))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail=f"Username or email already exists: {username}")

    new_user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
        department_code=department_code or None,
        school=(school or "").strip(),
        designation=(designation or "").strip(),
        abc_id=(abc_id or "").strip(),
        residence=(residence or "").strip(),
        transport=(transport or "").strip() if (residence or "") == "day_scholar" else "",
        residence_detail=(residence_detail or "").strip(),
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    if role == "student":
        prog = (await db.execute(select(Program).order_by(Program.id).limit(1))).scalar_one_or_none()
        if not prog:
            raise HTTPException(status_code=400, detail="No program configured — seed departments/programs first")
        sid = student_id or f"STU{new_user.id:04d}"
        if (await db.execute(select(StudentProfile).where(StudentProfile.student_id == sid))).scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"student_id already exists: {sid}")
        db.add(
            StudentProfile(
                user_id=new_user.id,
                student_id=sid,
                program_id=prog.id,
                batch=batch or "2026",
                year=year or 1,
                semester=semester or 1,
                section=section or "A",
                cgpa=0.0,
                credits_completed=0,
                credits_required=prog.total_credits,
                backlogs=0,
                overall_attendance=0.0,
            )
        )
    elif role in ("faculty", "hod", "school_dean"):
        dept = None
        if department_code:
            dept = (
                await db.execute(select(Department).where(Department.code == department_code))
            ).scalar_one_or_none()
        if not dept:
            dept = (await db.execute(select(Department).order_by(Department.id).limit(1))).scalar_one_or_none()
        if not dept:
            raise HTTPException(status_code=400, detail="No department configured")
        fid = faculty_id or f"FAC{new_user.id:04d}"
        if (await db.execute(select(FacultyProfile).where(FacultyProfile.faculty_id == fid))).scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"faculty_id already exists: {fid}")
        db.add(
            FacultyProfile(
                user_id=new_user.id,
                faculty_id=fid,
                designation=designation or "Assistant Professor",
                department_id=dept.id,
            )
        )

    await db.flush()
    if role == "student":
        from app.routes.integration import ensure_student_consents

        await ensure_student_consents(db, new_user.id, "deny")
    return new_user


@router.post("/users")
async def create_user(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    new_user = await _create_user_record(
        db,
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role=body.role,
        department_code=body.department_code,
        student_id=body.student_id,
        year=body.year,
        semester=body.semester,
        section=body.section,
        batch=body.batch,
        faculty_id=body.faculty_id,
        designation=body.designation,
        school=body.school,
        abc_id=body.abc_id,
        residence=body.residence,
        transport=body.transport,
        residence_detail=body.residence_detail,
    )
    await db.commit()
    background_tasks.add_task(
        mail.send_uis_welcome_email,
        new_user.email,
        new_user.full_name or "",
        new_user.username,
        body.password,
        new_user.role,
    )
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="user",
        action="CREATE",
        purpose=f"{body.role}:{body.username}",
        result="ALLOWED",
    )
    return {"ok": True, "id": new_user.id, "username": new_user.username, "role": new_user.role}


@router.post("/users/{user_id}/photo")
async def upload_user_photo(
    user_id: int,
    user: Annotated[User, Depends(PhotoRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    row = (
        await db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.student), selectinload(User.faculty))
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        photo = photo_data_url(await file.read(), file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    apply_photo(row, row.student, photo)
    await db.commit()
    return {"ok": True, "photo_url": photo}


@router.delete("/users/{user_id}/photo")
async def remove_user_photo(
    user_id: int,
    user: Annotated[User, Depends(PhotoRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(select(User).where(User.id == user_id).options(selectinload(User.student)))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    apply_photo(row, row.student, "")
    await db.commit()
    return {"ok": True, "photo_url": ""}


@router.get("/users/import-template")
async def users_import_template(user: Annotated[User, Depends(EditRoles)]):
    """Download CSV template (opens in Excel) for bulk user creation."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(BULK_TEMPLATE_HEADERS)
    writer.writerow(
        [
            "student",
            "ananya.k",
            "ananya.k@klu.ac.in",
            "Ananya Krishnan",
            "campus123",
            "CSE",
            "KARE2026CSE001",
            "2",
            "3",
            "A",
            "2026",
            "",
            "",
        ]
    )
    writer.writerow(
        [
            "faculty",
            "ravi.m",
            "ravi.m@klu.ac.in",
            "Dr Ravi Menon",
            "campus123",
            "CSE",
            "",
            "",
            "",
            "",
            "",
            "FACCSE001",
            "Associate Professor",
        ]
    )
    writer.writerow(
        [
            "hostel_admin",
            "warden.main",
            "warden@klu.ac.in",
            "Hostel Warden",
            "campus123",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=uis_users_import_template.csv"},
    )


def _parse_upload_rows(filename: str, content: bytes) -> list[dict[str, Any]]:
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise HTTPException(status_code=400, detail="Excel support requires openpyxl on the server") from exc
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        try:
            headers = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
        except StopIteration:
            return []
        out = []
        for raw in rows_iter:
            if not raw or all(c is None or str(c).strip() == "" for c in raw):
                continue
            item = {headers[i]: raw[i] for i in range(min(len(headers), len(raw)))}
            out.append(item)
        return out

    # CSV / Excel-saved CSV
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader if any((v or "").strip() for v in r.values())]


@router.post("/users/import")
async def import_users(
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Bulk-create users from CSV or Excel (.xlsx). Same columns as the downloadable template."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 5_000_000:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    try:
        rows = _parse_upload_rows(file.filename or "upload.csv", content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found in file")

    created: list[dict] = []
    errors: list[dict] = []

    for idx, row in enumerate(rows, start=2):  # row 1 = header
        try:
            role = _normalize_role(_row_get(row, "role", "Role", "user_role"))
            if not role:
                raise HTTPException(status_code=400, detail="Missing or unknown role")
            password = _row_get(row, "password", "Password", default="campus123") or "campus123"
            year_raw = _row_get(row, "year", "Year", default="1")
            sem_raw = _row_get(row, "semester", "Semester", default="1")
            new_user = await _create_user_record(
                db,
                username=_row_get(row, "username", "Username", "user_name"),
                email=_row_get(row, "email", "Email", "mail"),
                full_name=_row_get(row, "full_name", "full name", "name", "Full Name"),
                password=password,
                role=role,
                department_code=_row_get(row, "department_code", "department", "dept") or None,
                student_id=_row_get(row, "student_id", "student id", "roll_no", "roll") or None,
                year=int(float(year_raw)) if year_raw else 1,
                semester=int(float(sem_raw)) if sem_raw else 1,
                section=_row_get(row, "section", "Section", default="A") or "A",
                batch=_row_get(row, "batch", "Batch") or None,
                faculty_id=_row_get(row, "faculty_id", "faculty id", "employee_id") or None,
                designation=_row_get(row, "designation", "Designation", default="Assistant Professor")
                or "Assistant Professor",
            )
            await db.commit()
            created.append({"row": idx, "username": new_user.username, "role": new_user.role, "id": new_user.id})
            background_tasks.add_task(
                mail.send_uis_welcome_email,
                new_user.email,
                new_user.full_name or "",
                new_user.username,
                password,
                new_user.role,
            )
        except HTTPException as exc:
            await db.rollback()
            errors.append({"row": idx, "error": exc.detail})
        except Exception as exc:
            await db.rollback()
            errors.append({"row": idx, "error": str(exc)})

    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="user",
        action="BULK_IMPORT",
        purpose=f"created={len(created)} errors={len(errors)} file={file.filename}",
        result="ALLOWED",
    )
    await db.commit()
    return {
        "ok": True,
        "created_count": len(created),
        "error_count": len(errors),
        "created": created,
        "errors": errors[:50],
        "message": f"Imported {len(created)} user(s); {len(errors)} row(s) failed.",
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.student), selectinload(User.faculty))
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    student = row.student
    photo = row.photo_url or (student.photo_url if student else "") or ""
    return {
        "id": row.id,
        "username": row.username,
        "email": row.email,
        "full_name": row.full_name,
        "role": row.role,
        "department_code": row.department_code,
        "designation": (row.faculty.designation if row.faculty and row.faculty.designation else row.designation) or "",
        "school": row.school or "",
        "office": row.office or "",
        "cabin_block": row.cabin_block or "",
        "abc_id": row.abc_id or "",
        "residence": row.residence or "",
        "transport": row.transport or "",
        "residence_detail": row.residence_detail or "",
        "is_active": row.is_active,
        "photo_url": photo,
        "student_id": student.student_id if student else "",
        "year": student.year if student else None,
        "semester": student.semester if student else None,
        "section": student.section if student else "",
        "batch": student.batch if student else "",
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    target = (
        await db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.student), selectinload(User.faculty))
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    data = body.model_dump(exclude_unset=True)
    if "password" in data:
        target.hashed_password = hash_password(data.pop("password"))
    if "role" in data and data["role"] not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    student_data = {key: data.pop(key) for key in list(data) if key in STUDENT_EDIT_FIELDS}
    if student_data:
        if not target.student:
            raise HTTPException(status_code=400, detail="This account has no student record to edit")
        if "section" in student_data and student_data["section"] is not None:
            student_data["section"] = student_data["section"].strip()[:8]
        if "batch" in student_data and student_data["batch"] is not None:
            student_data["batch"] = student_data["batch"].strip()[:16]
        for key, val in student_data.items():
            setattr(target.student, key, val)
    if "designation" in data and target.faculty and data["designation"] is not None:
        target.faculty.designation = data["designation"]
    for key, val in data.items():
        setattr(target, key, val)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail="That email or register number is already used") from exc
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="user",
        action="UPDATE",
        purpose=str(user_id),
        result="ALLOWED",
    )
    return {"ok": True, "id": user_id}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    target = (
        await db.execute(select(User).where(User.id == user_id).options(selectinload(User.student)))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    register = target.student.student_id if target.student else ""
    typed = (body.confirm or "").strip().casefold()
    if typed not in {target.username.strip().casefold(), register.strip().casefold()} or not typed:
        require_phrase(body.confirm, target.username)
    label = target.username
    email = target.email
    await delete_user_record(db, target)
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="delete-user",
        title="Account deleted",
        summary=f"Deleted {label} and the academic, fee, hostel, and message rows linked to that account.",
        email=email,
    )
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="user",
        action="DELETE",
        purpose=label,
        result="ALLOWED",
    )
    return {"ok": True, "deleted": label, "acknowledgement": ack}


@router.post("/users/{user_id}/impersonate")
async def impersonate_user(
    user_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    require_phrase(body.confirm, target.username)
    if user.id == target.id:
        raise HTTPException(status_code=400, detail="You are already signed in as this account")
    if not target.is_active:
        raise HTTPException(status_code=400, detail="Enable the account before signing in as this user")
    token = create_access_token({"sub": target.username, "role": target.role, "uid": target.id})
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="user",
        action="IMPERSONATE",
        purpose=target.username,
        result="ALLOWED",
    )
    return {
        "access_token": token,
        "role": target.role,
        "full_name": target.full_name,
        "username": target.username,
    }


class CourseGradeIn(BaseModel):
    student_id: str = Field(min_length=1)
    course_code: str = Field(min_length=1)
    grade: str = Field(min_length=1, max_length=4)
    section: Optional[str] = None


@router.post("/students/course-grade")
async def map_student_course_grade(
    body: CourseGradeIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        result = await assign_course_grade(
            db,
            student_id=body.student_id,
            course_code=body.course_code,
            letter=body.grade,
            section=body.section,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="grade",
        action="MAP",
        purpose=f"{result['student_id']}:{result['course_code']}:{result['grade']}",
        result="ALLOWED",
    )
    return {"ok": True, **result}


@router.get("/students/course-grade/template")
async def course_grade_template(user: Annotated[User, Depends(EditRoles)]):
    text = "student_id,course_code,grade,section\n9923004001,CSE501,A,A\n"
    return StreamingResponse(
        iter([text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=course_grade_import.csv"},
    )


@router.post("/students/course-grade/import")
async def import_course_grades(
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV needs a header row: student_id, course_code, grade, section")
    saved = []
    errors = []
    for idx, row in enumerate(reader, start=2):
        lowered = {(k or "").strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()}
        student_id = lowered.get("student_id") or lowered.get("register_number") or lowered.get("roll_no") or ""
        course_code = lowered.get("course_code") or lowered.get("code") or ""
        grade = lowered.get("grade") or lowered.get("letter") or ""
        section = lowered.get("section") or None
        if not student_id and not course_code and not grade:
            continue
        try:
            result = await assign_course_grade(
                db,
                student_id=student_id,
                course_code=course_code,
                letter=grade,
                section=section,
            )
            saved.append({"row": idx, **result})
        except (ValueError, LookupError) as exc:
            errors.append({"row": idx, "error": str(exc)})
    await db.commit()
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="grade",
        action="CSV_IMPORT",
        purpose=f"saved={len(saved)} errors={len(errors)}",
        result="ALLOWED",
    )
    return {
        "ok": True,
        "saved_count": len(saved),
        "error_count": len(errors),
        "saved": saved[:50],
        "errors": errors[:50],
        "grades": list(GRADE_POINTS),
        "message": f"Mapped {len(saved)} course grade(s); {len(errors)} row(s) failed.",
    }


class AllocationIn(BaseModel):
    faculty_profile_id: Optional[int] = None


class SectionFacultyIn(BaseModel):
    section: str
    faculty_profile_id: Optional[int] = None


class AllocateCourseIn(BaseModel):
    course_id: int
    department_code: str
    batch: str
    scope: str = "batch"
    section: Optional[str] = None
    faculty_profile_id: Optional[int] = None
    faculties: list[SectionFacultyIn] = []


@router.get("/allocations")
async def list_allocations(
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    offerings = (
        await db.execute(
            select(CourseOffering)
            .options(
                selectinload(CourseOffering.course),
                selectinload(CourseOffering.faculty).selectinload(FacultyProfile.user),
            )
            .order_by(CourseOffering.semester, CourseOffering.id)
        )
    ).scalars().all()
    counts = dict(
        (
            await db.execute(select(Enrollment.offering_id, func.count()).group_by(Enrollment.offering_id))
        ).all()
    )
    faculty = (
        await db.execute(select(FacultyProfile).options(selectinload(FacultyProfile.user)).order_by(FacultyProfile.id))
    ).scalars().all()
    courses = (await db.execute(select(Course).order_by(Course.code))).scalars().all()
    departments = (await db.execute(select(Department).order_by(Department.code))).scalars().all()
    groups = (
        await db.execute(
            select(
                Department.code,
                StudentProfile.batch,
                StudentProfile.section,
                StudentProfile.semester,
                func.count(),
            )
            .join(Program, StudentProfile.program_id == Program.id)
            .join(Department, Program.department_id == Department.id)
            .group_by(Department.code, StudentProfile.batch, StudentProfile.section, StudentProfile.semester)
            .order_by(Department.code, StudentProfile.batch, StudentProfile.section)
        )
    ).all()
    return {
        "courses": [{"id": row.id, "code": row.code, "title": row.title} for row in courses],
        "departments": [{"code": row.code, "name": row.name} for row in departments],
        "groups": [
            {
                "department_code": code,
                "batch": batch,
                "section": section,
                "semester": semester,
                "students": int(count),
            }
            for code, batch, section, semester, count in groups
        ],
        "faculty": [
            {
                "id": row.id,
                "faculty_id": row.faculty_id,
                "name": row.user.full_name if row.user else row.faculty_id,
            }
            for row in faculty
        ],
        "offerings": [
            {
                "offering_id": row.id,
                "code": row.course.code if row.course else "",
                "title": row.course.title if row.course else "",
                "section": row.section,
                "semester": row.semester,
                "academic_year": row.academic_year,
                "faculty_profile_id": row.faculty_id,
                "faculty_name": row.faculty.user.full_name if row.faculty and row.faculty.user else "",
                "students": int(counts.get(row.id, 0)),
            }
            for row in offerings
            if row.course
        ],
    }


def _batch_matches(stored: str, chosen: str) -> bool:
    left = (stored or "").strip()
    right = (chosen or "").strip()
    if not left or not right:
        return False
    return left == right or left.startswith(right)


@router.post("/allocations/apply")
async def apply_allocation(
    body: AllocateCourseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    course = (await db.execute(select(Course).where(Course.id == body.course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    department = (
        await db.execute(select(Department).where(Department.code == body.department_code.strip().upper()))
    ).scalar_one_or_none()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    scope = (body.scope or "batch").strip().lower()
    if scope not in ("batch", "section"):
        raise HTTPException(status_code=400, detail="Choose the whole batch or one section")
    section_filter = (body.section or "").strip()
    if scope == "section" and not section_filter:
        raise HTTPException(status_code=400, detail="Choose the section")

    students = (
        await db.execute(
            select(StudentProfile)
            .join(Program, StudentProfile.program_id == Program.id)
            .where(Program.department_id == department.id)
        )
    ).scalars().all()
    chosen = [
        row
        for row in students
        if _batch_matches(row.batch, body.batch)
        and (scope == "batch" or (row.section or "").strip() == section_filter)
    ]
    if not chosen:
        raise HTTPException(status_code=404, detail="No students match that department, batch, and section")

    faculty_by_section = {
        (item.section or "").strip(): item.faculty_profile_id
        for item in body.faculties
        if (item.section or "").strip()
    }
    wanted_ids = {value for value in faculty_by_section.values() if value} | (
        {body.faculty_profile_id} if body.faculty_profile_id else set()
    )
    if wanted_ids:
        found = set(
            (
                await db.execute(select(FacultyProfile.id).where(FacultyProfile.id.in_(wanted_ids)))
            ).scalars().all()
        )
        if found != wanted_ids:
            raise HTTPException(status_code=404, detail="Faculty not found")

    already = set(
        (
            await db.execute(
                select(Enrollment.student_id)
                .join(CourseOffering, Enrollment.offering_id == CourseOffering.id)
                .where(CourseOffering.course_id == course.id, Enrollment.student_id.in_([row.id for row in chosen]))
            )
        ).scalars().all()
    )
    grouped: dict[tuple[str, int], list[StudentProfile]] = {}
    for row in chosen:
        grouped.setdefault(((row.section or "A").strip(), row.semester or 1), []).append(row)

    added = 0
    sections = []
    for (section, semester), members in sorted(grouped.items()):
        faculty_id = faculty_by_section.get(section, body.faculty_profile_id)
        offering = (
            await db.execute(
                select(CourseOffering).where(
                    CourseOffering.course_id == course.id,
                    CourseOffering.section == section,
                    CourseOffering.semester == semester,
                )
            )
        ).scalars().first()
        if not offering:
            offering = CourseOffering(
                course_id=course.id,
                faculty_id=faculty_id,
                semester=semester,
                academic_year=body.batch.strip(),
                section=section,
            )
            db.add(offering)
            await db.flush()
        elif faculty_id is not None:
            offering.faculty_id = faculty_id
        section_added = 0
        for student in members:
            if student.id in already:
                continue
            db.add(Enrollment(student_id=student.id, offering_id=offering.id, status="active"))
            already.add(student.id)
            section_added += 1
            added += 1
        sections.append(
            {"section": section, "semester": semester, "students": len(members), "added": section_added, "faculty_profile_id": offering.faculty_id}
        )

    actor_name = user.username
    actor_role = user.role
    await db.commit()
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=actor_name,
        role=actor_role,
        resource="allocation",
        action="APPLY",
        purpose=f"{course.code} {department.code} {body.batch} {scope} added={added}",
        result="ALLOWED",
    )
    return {"ok": True, "added": added, "course": course.code, "sections": sections}


class AdvisorIn(BaseModel):
    faculty_profile_id: int
    scope: str = "section"
    section: Optional[str] = ""
    batch: Optional[str] = ""
    student_id: Optional[str] = ""


@router.get("/advisors")
async def get_advisors(
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return {"items": await list_advisors(db)}


@router.delete("/advisors/{advisor_id}")
async def delete_advisor(
    advisor_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(
            select(FacultyAdvisor)
            .where(FacultyAdvisor.id == advisor_id)
            .options(selectinload(FacultyAdvisor.faculty).selectinload(FacultyProfile.user))
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Advisor mapping not found")
    expected = row.faculty.user.full_name if row.faculty and row.faculty.user else "REMOVE"
    require_phrase(body.confirm, expected)
    await db.delete(row)
    await db.commit()
    return {"ok": True, "items": await list_advisors(db)}


@router.post("/advisors")
async def save_advisor(
    body: AdvisorIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    scope = (body.scope or "section").strip().lower()
    if scope not in ("section", "student"):
        raise HTTPException(status_code=400, detail="Choose a section or one student")
    faculty = (
        await db.execute(select(FacultyProfile).where(FacultyProfile.id == body.faculty_profile_id))
    ).scalar_one_or_none()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")
    student_profile_id = None
    section = (body.section or "").strip()
    batch = (body.batch or "").strip()
    if scope == "student":
        register = (body.student_id or "").strip()
        student = (
            await db.execute(select(StudentProfile).where(StudentProfile.student_id == register))
        ).scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        student_profile_id = student.id
        section = student.section or ""
        batch = student.batch or ""
        row = (
            await db.execute(
                select(FacultyAdvisor).where(FacultyAdvisor.scope == "student", FacultyAdvisor.student_id == student.id)
            )
        ).scalar_one_or_none()
    else:
        if not section:
            raise HTTPException(status_code=400, detail="Choose the section")
        row = (
            await db.execute(
                select(FacultyAdvisor).where(
                    FacultyAdvisor.scope == "section",
                    FacultyAdvisor.section == section,
                    FacultyAdvisor.batch == batch,
                )
            )
        ).scalar_one_or_none()
    if row:
        row.faculty_id = faculty.id
        row.section = section
        row.batch = batch
        row.student_id = student_profile_id
    else:
        db.add(
            FacultyAdvisor(
                faculty_id=faculty.id,
                scope=scope,
                section=section,
                batch=batch,
                student_id=student_profile_id,
            )
        )
    actor_name = user.username
    actor_role = user.role
    await db.commit()
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=actor_name,
        role=actor_role,
        resource="advisor",
        action="MAP",
        purpose=f"{scope}:{section or body.student_id}:faculty:{faculty.id}",
        result="ALLOWED",
    )
    return {"ok": True, "items": await list_advisors(db)}


@router.put("/allocations/{offering_id}")
async def assign_faculty(
    offering_id: int,
    body: AllocationIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    offering = (
        await db.execute(select(CourseOffering).where(CourseOffering.id == offering_id))
    ).scalar_one_or_none()
    if not offering:
        raise HTTPException(status_code=404, detail="Course section not found")
    if body.faculty_profile_id is not None:
        faculty = (
            await db.execute(select(FacultyProfile).where(FacultyProfile.id == body.faculty_profile_id))
        ).scalar_one_or_none()
        if not faculty:
            raise HTTPException(status_code=404, detail="Faculty not found")
    offering.faculty_id = body.faculty_profile_id
    actor_name = user.username
    actor_role = user.role
    await db.commit()
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=actor_name,
        role=actor_role,
        resource="allocation",
        action="ASSIGN_FACULTY",
        purpose=f"offering:{offering_id} faculty:{body.faculty_profile_id}",
        result="ALLOWED",
    )
    return {"ok": True}


@router.post("/allocations/{offering_id}/map-section")
async def map_section_students(
    offering_id: int,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    offering = (
        await db.execute(select(CourseOffering).where(CourseOffering.id == offering_id))
    ).scalar_one_or_none()
    if not offering:
        raise HTTPException(status_code=404, detail="Course section not found")
    students = (
        await db.execute(
            select(StudentProfile).where(
                StudentProfile.section == offering.section,
                StudentProfile.semester == offering.semester,
            )
        )
    ).scalars().all()
    existing = set(
        (
            await db.execute(select(Enrollment.student_id).where(Enrollment.offering_id == offering_id))
        ).scalars().all()
    )
    added = 0
    for student in students:
        if student.id in existing:
            continue
        db.add(Enrollment(student_id=student.id, offering_id=offering_id, status="active"))
        added += 1
    actor_name = user.username
    actor_role = user.role
    await db.commit()
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=actor_name,
        role=actor_role,
        resource="allocation",
        action="MAP_SECTION",
        purpose=f"offering:{offering_id} added={added}",
        result="ALLOWED",
    )
    return {"ok": True, "added": added, "section": offering.section, "semester": offering.semester}


@router.get("/allocations/{offering_id}/students")
async def allocation_students(
    offering_id: int,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    offering = (
        await db.execute(
            select(CourseOffering)
            .where(CourseOffering.id == offering_id)
            .options(selectinload(CourseOffering.course))
        )
    ).scalar_one_or_none()
    if not offering:
        raise HTTPException(status_code=404, detail="Course section not found")
    rows = (
        await db.execute(
            select(Enrollment)
            .where(Enrollment.offering_id == offering_id)
            .options(selectinload(Enrollment.student).selectinload(StudentProfile.user))
            .order_by(Enrollment.id)
        )
    ).scalars().all()
    enrollment_ids = [row.id for row in rows]
    records = {}
    if enrollment_ids:
        for record in (
            await db.execute(select(AttendanceRecord).where(AttendanceRecord.enrollment_id.in_(enrollment_ids)))
        ).scalars().all():
            records[record.enrollment_id] = record
    students = []
    for index, row in enumerate(rows, start=1):
        record = records.get(row.id)
        conducted = record.total if record else 0
        attended = record.attended if record else 0
        students.append(
            {
                "sno": index,
                "student_id": row.student.student_id,
                "name": row.student.user.full_name if row.student and row.student.user else "",
                "section": row.student.section if row.student else "",
                "percentage": round(100.0 * attended / conducted, 1) if conducted else 0.0,
            }
        )
    return {
        "code": offering.course.code if offering.course else "",
        "section": offering.section,
        "students": students,
    }


@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    require_phrase(body.confirm, course.code)
    label = f"{course.code} {course.title}"
    code = course.code
    await delete_course_record(db, course)
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="delete-course",
        title="Course deleted",
        summary=f"Deleted {label}. Sections, enrollments, marks, attendance, timetable periods, and exam venues for {code} were removed from the database.",
        email=user.email,
    )
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="course",
        action="DELETE",
        purpose=label,
        result="ALLOWED",
    )
    return {"ok": True, "deleted": label, "acknowledgement": ack}


@router.delete("/allocations/{offering_id}")
async def delete_allocation(
    offering_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    offering = (
        await db.execute(
            select(CourseOffering).where(CourseOffering.id == offering_id).options(selectinload(CourseOffering.course))
        )
    ).scalar_one_or_none()
    if not offering:
        raise HTTPException(status_code=404, detail="Course section not found")
    code = offering.course.code if offering.course else str(offering_id)
    phrase = f"{code}-{offering.section}"
    require_phrase(body.confirm, phrase)
    label = f"{code} section {offering.section}"
    await delete_offerings(db, [offering.id])
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="delete-section",
        title="Class section deleted",
        summary=f"Deleted {label}. Enrollments, marks, and attendance for that section were removed from the database.",
        email=user.email,
    )
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="course_offering",
        action="DELETE",
        purpose=label,
        result="ALLOWED",
    )
    return {"ok": True, "deleted": label, "acknowledgement": ack}


@router.get("/audit-logs")
async def audit_logs(
    user: Annotated[User, Depends(require_roles("university_admin", "admin", "super_admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit))
    rows = result.scalars().all()
    return {
        "items": [
            {
                "timestamp": a.timestamp.isoformat(),
                "actor": a.actor,
                "user": a.user_ref,
                "role": a.role,
                "resource": a.resource,
                "action": a.action,
                "purpose": a.purpose,
                "result": a.result,
            }
            for a in rows
        ]
    }
