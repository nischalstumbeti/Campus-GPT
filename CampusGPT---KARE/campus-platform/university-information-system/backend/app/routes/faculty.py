from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Achievement,
    AppNotification,
    AttendanceRecord,
    AttendanceSession,
    Complaint,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    FacultyProfile,
    Grade,
    HostelAllocation,
    HostelBlock,
    HostelLeave,
    Mark,
    Room,
    StudentProfile,
    TimetableSlot,
    User,
)
from app.security.auth import require_roles
from app.services.advisors import mentee_ids
from app.services.attendance_board import courses_for_student, save_session
from app.services.audit import write_audit
from app.services.payloads import serialize_timetable_slot

router = APIRouter(prefix="/api/v1/faculty", tags=["faculty"])


class AchievementIn(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    category: str = Field(default="award", max_length=64)
    description: str = Field(default="", max_length=2000)
    awarded_on: Optional[str] = None  # YYYY-MM-DD


class AchievementPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=255)
    category: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=2000)
    awarded_on: Optional[str] = None


def _parse_award_date(raw: Optional[str]) -> Optional[date]:
    if not raw or not str(raw).strip():
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="awarded_on must be YYYY-MM-DD") from exc


def _ser_achievement(a: Achievement) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "category": a.category,
        "description": a.description or "",
        "awarded_on": a.awarded_on.isoformat() if a.awarded_on else None,
    }


async def _notify_student_achievements(
    db: AsyncSession,
    *,
    student_user_id: int,
    faculty_name: str,
    title: str,
    action: str,
) -> None:
    """Notify the student and point them to student login / achievements page only."""
    if not student_user_id:
        return
    db.add(
        AppNotification(
            user_id=student_user_id,
            kind="achievement",
            title=f"Achievement {action} by {faculty_name}",
            body=f"{title} — open Student login → Achievements to review.",
            link="/student/achievements",
            thread_id=None,
            read=False,
        )
    )


def _faculty_or_403(user: User) -> FacultyProfile:
    if not user.faculty:
        raise HTTPException(status_code=403, detail="Faculty profile required")
    return user.faculty


async def _assert_offering_access(user: User, off: CourseOffering, db: AsyncSession):
    if user.role == "faculty" and user.faculty and off.faculty_id != user.faculty.id:
        raise HTTPException(status_code=403, detail="Not assigned to this class")
    code = (user.department_code or "").strip()
    if user.role in {"hod", "school_dean"} and code:
        known = (
            await db.execute(select(Department).where(func.lower(Department.code) == code.casefold()))
        ).scalar_one_or_none()
        course = (await db.execute(select(Course).where(Course.id == off.course_id))).scalar_one_or_none()
        if known and (not course or course.department_id != known.id):
            raise HTTPException(status_code=403, detail="This class is outside your department")


async def _reject_if_marks_locked(db: AsyncSession, offering_id: int) -> None:
    off = await db.get(CourseOffering, offering_id)
    if off and off.marks_locked:
        raise HTTPException(status_code=403, detail="These marks are published. The examination controller has to reopen them before they can change.")


@router.get("/dashboard")
async def dashboard(
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    q = select(func.count()).select_from(CourseOffering)
    if user.role == "faculty":
        f = _faculty_or_403(user)
        q = q.where(CourseOffering.faculty_id == f.id)
    offerings = (await db.execute(q)).scalar() or 0

    student_count = 0
    pending_leaves = 0
    if user.role == "faculty" and user.faculty:
        offering_ids = (
            await db.execute(select(CourseOffering.id).where(CourseOffering.faculty_id == user.faculty.id))
        ).scalars().all()
        if offering_ids:
            student_ids = (
                await db.execute(
                    select(Enrollment.student_id).where(Enrollment.offering_id.in_(list(offering_ids))).distinct()
                )
            ).scalars().all()
            student_count = len(student_ids)
            if student_ids:
                pending_leaves = (
                    await db.execute(
                        select(func.count())
                        .select_from(HostelLeave)
                        .where(
                            HostelLeave.student_id.in_(list(student_ids)),
                            HostelLeave.status == "pending",
                        )
                    )
                ).scalar() or 0
    elif user.role == "hod":
        dept = (user.department_code or "").strip().upper()
        all_students = (
            await db.execute(
                select(StudentProfile).options(selectinload(StudentProfile.user))
            )
        ).scalars().all()
        dept_students = [
            s
            for s in all_students
            if dept
            and (
                ((s.user.department_code or "").upper() if s.user else "") == dept
                or (s.section or "").upper().startswith(dept)
            )
        ]
        student_count = len(dept_students) if dept else len(all_students)
        dept_ids = {s.id for s in dept_students} if dept else {s.id for s in all_students}
        pending_leaves = (
            await db.execute(
                select(func.count())
                .select_from(HostelLeave)
                .where(HostelLeave.status == "pending", HostelLeave.student_id.in_(list(dept_ids) or [-1]))
            )
        ).scalar() or 0

    open_complaints = (
        await db.execute(
            select(func.count())
            .select_from(Complaint)
            .where(
                Complaint.audience.in_(["faculty", "any"]),
                Complaint.status.in_(["open", "in_progress"]),
            )
        )
    ).scalar() or 0

    faculty = None
    if user.faculty:
        faculty = (
            await db.execute(
                select(FacultyProfile)
                .where(FacultyProfile.id == user.faculty.id)
                .options(selectinload(FacultyProfile.department))
            )
        ).scalar_one_or_none()
    department_name = faculty.department.name if faculty and faculty.department else (user.department_code or "")
    return {
        "welcome": f"Welcome, {user.full_name}",
        "role": user.role,
        "department": department_name,
        "title": faculty.designation if faculty else "Faculty",
        "faculty_id": faculty.faculty_id if faculty else "",
        "name": user.full_name,
        "email": user.email,
        "designation": faculty.designation if faculty else "",
        "assigned_offerings": offerings,
        "students_tracked": student_count,
        "pending_student_leaves": pending_leaves,
        "open_complaints": open_complaints,
        "demo": True,
    }


@router.get("/classes")
async def classes(
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    f = user.faculty
    q = select(CourseOffering).options(selectinload(CourseOffering.course), selectinload(CourseOffering.faculty))
    if user.role == "faculty":
        if not f:
            raise HTTPException(status_code=403, detail="Faculty profile required")
        q = q.where(CourseOffering.faculty_id == f.id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return {
        "classes": [
            {
                "offering_id": o.id,
                "code": o.course.code,
                "title": o.course.title,
                "section": o.section,
                "semester": o.semester,
                "academic_year": o.academic_year,
            }
            for o in rows
        ]
    }


@router.get("/timetable")
async def timetable(
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    faculty = user.faculty
    offering_query = select(CourseOffering.id)
    if user.role == "faculty":
        if not faculty:
            raise HTTPException(status_code=403, detail="Faculty profile required")
        offering_query = offering_query.where(CourseOffering.faculty_id == faculty.id)
    offering_ids = [row[0] for row in (await db.execute(offering_query)).all()]
    if not offering_ids:
        return {"faculty_id": faculty.faculty_id if faculty else "", "name": user.full_name, "slots": []}
    slots = (
        await db.execute(
            select(TimetableSlot)
            .where(TimetableSlot.offering_id.in_(offering_ids))
            .options(
                selectinload(TimetableSlot.offering).selectinload(CourseOffering.course),
                selectinload(TimetableSlot.offering).selectinload(CourseOffering.faculty).selectinload(FacultyProfile.user),
            )
        )
    ).scalars().all()
    return {
        "faculty_id": faculty.faculty_id if faculty else "",
        "name": user.full_name,
        "slots": [serialize_timetable_slot(slot) for slot in slots],
    }


@router.get("/classes/{offering_id}/students")
async def class_students(
    offering_id: int,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    off = (
        await db.execute(
            select(CourseOffering)
            .where(CourseOffering.id == offering_id)
            .options(selectinload(CourseOffering.course))
        )
    ).scalar_one_or_none()
    if not off:
        raise HTTPException(status_code=404, detail="Offering not found")
    await _assert_offering_access(user, off, db)

    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.offering_id == offering_id)
        .options(selectinload(Enrollment.student).selectinload(StudentProfile.user))
        .order_by(Enrollment.id)
    )
    rows = result.scalars().all()
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
                "enrollment_id": row.id,
                "student_id": row.student.student_id,
                "name": row.student.user.full_name if row.student.user else "",
                "section": row.student.section,
                "conducted": conducted,
                "attended": attended,
                "percentage": round(100.0 * attended / conducted, 1) if conducted else 0.0,
                "profile_path": f"/faculty/students/{row.student.student_id}",
            }
        )
    return {
        "offering_id": offering_id,
        "code": off.course.code if off.course else "",
        "section": off.section,
        "semester": off.semester,
        "students": students,
    }


async def _assert_faculty_can_view_student(user: User, sp: StudentProfile, db: AsyncSession) -> None:
    """Faculty may view students in their offerings; HoD may view students in their department."""
    if user.role == "hod":
        dept = (user.department_code or "").strip().upper()
        if not dept:
            raise HTTPException(status_code=403, detail="HoD department not configured")
        prog = sp.program
        code = ""
        if prog is not None and getattr(prog, "department", None) is not None:
            code = (prog.department.code or "").upper()
        elif prog is not None and getattr(prog, "code", None):
            # Fallback: program codes often start with dept (e.g. CSE-BTECH)
            code = (prog.code or "").split("-")[0].upper()
        if code != dept and not (sp.section or "").upper().startswith(dept):
            # Also allow match via student's user department_code if set
            stu_user = sp.user
            stu_dept = (stu_user.department_code or "").upper() if stu_user else ""
            if stu_dept != dept:
                raise HTTPException(status_code=403, detail="Student not in your department")
        return
    if user.faculty and sp.id in await mentee_ids(db, user.faculty.id):
        return
    if not user.faculty:
        raise HTTPException(status_code=403, detail="Faculty profile required")
    offering_ids = (
        await db.execute(select(CourseOffering.id).where(CourseOffering.faculty_id == user.faculty.id))
    ).scalars().all()
    if not offering_ids:
        raise HTTPException(status_code=403, detail="Student not in your classes")
    enr = (
        await db.execute(
            select(Enrollment)
            .where(
                Enrollment.student_id == sp.id,
                Enrollment.offering_id.in_(list(offering_ids)),
            )
            .limit(1)
        )
    ).scalars().first()
    if not enr:
        raise HTTPException(status_code=403, detail="Student not in your classes")


@router.get("/students/{student_id}")
async def student_dossier(
    student_id: str,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Full student record for teaching faculty: profile, marks, attendance, leave, hostel."""
    sp = (
        await db.execute(
            select(StudentProfile)
            .where(StudentProfile.student_id == student_id)
            .options(
                selectinload(StudentProfile.user),
                selectinload(StudentProfile.program),
            )
        )
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    await _assert_faculty_can_view_student(user, sp, db)

    enrollments = (
        await db.execute(
            select(Enrollment)
            .where(Enrollment.student_id == sp.id)
            .options(
                selectinload(Enrollment.offering).selectinload(CourseOffering.course),
                selectinload(Enrollment.offering).selectinload(CourseOffering.faculty).selectinload(FacultyProfile.user),
            )
        )
    ).scalars().all()

    courses = []
    for e in enrollments:
        ar = (
            await db.execute(select(AttendanceRecord).where(AttendanceRecord.enrollment_id == e.id))
        ).scalar_one_or_none()
        attended = ar.attended if ar else 0
        total = ar.total if ar else 0
        percentage = round(100 * attended / total, 1) if total else 0.0
        marks = (
            await db.execute(select(Mark).where(Mark.enrollment_id == e.id))
        ).scalars().all()
        grade = (
            await db.execute(select(Grade).where(Grade.enrollment_id == e.id))
        ).scalar_one_or_none()
        fac = e.offering.faculty if e.offering else None
        courses.append(
            {
                "code": e.offering.course.code if e.offering and e.offering.course else "",
                "title": e.offering.course.title if e.offering and e.offering.course else "",
                "section": e.offering.section if e.offering else "",
                "faculty": fac.user.full_name if fac and fac.user else "",
                "attendance": {
                    "attended": attended,
                    "total": total,
                    "percentage": percentage,
                },
                "marks": [
                    {"assessment": m.assessment, "score": m.score, "max_score": m.max_score}
                    for m in marks
                ],
                "grade": {"letter": grade.letter, "grade_point": grade.grade_point} if grade else None,
            }
        )

    leaves = (
        await db.execute(
            select(HostelLeave).where(HostelLeave.student_id == sp.id).order_by(HostelLeave.from_date.desc())
        )
    ).scalars().all()
    alloc = (
        await db.execute(
            select(HostelAllocation)
            .where(HostelAllocation.student_id == sp.id)
            .options(selectinload(HostelAllocation.room).selectinload(Room.block).selectinload(HostelBlock.hostel))
        )
    ).scalar_one_or_none()

    achievements = (
        await db.execute(
            select(Achievement).where(Achievement.student_id == sp.id).order_by(Achievement.id.desc())
        )
    ).scalars().all()

    return {
        "profile": {
            "student_id": sp.student_id,
            "name": sp.user.full_name if sp.user else "",
            "email": sp.user.email if sp.user else "",
            "program": sp.program.name if sp.program else "",
            "batch": sp.batch,
            "year": sp.year,
            "semester": sp.semester,
            "section": sp.section,
            "cgpa": sp.cgpa,
            "credits_completed": sp.credits_completed,
            "credits_required": sp.credits_required,
            "backlogs": sp.backlogs,
            "overall_attendance": sp.overall_attendance,
            "photo_url": sp.photo_url or "",
        },
        "hostel": {
            "hostel": alloc.room.block.hostel.name,
            "block": alloc.room.block.name,
            "room": alloc.room.room_number,
            "bed": alloc.bed_no,
            "status": alloc.status,
        }
        if alloc
        else None,
        "leaves": [
            {
                "id": l.id,
                "from": l.from_date.isoformat(),
                "to": l.to_date.isoformat(),
                "reason": l.reason,
                "destination": l.destination or "",
                "status": l.status,
                "source": l.source or "uis",
            }
            for l in leaves
        ],
        "courses": courses,
        "achievements": [_ser_achievement(a) for a in achievements],
        "redirect_hint": "student_login",
    }


@router.get("/students/{student_id}/achievements")
async def list_student_achievements(
    student_id: str,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sp = (
        await db.execute(
            select(StudentProfile)
            .where(StudentProfile.student_id == student_id)
            .options(selectinload(StudentProfile.user), selectinload(StudentProfile.program))
        )
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    await _assert_faculty_can_view_student(user, sp, db)
    rows = (
        await db.execute(select(Achievement).where(Achievement.student_id == sp.id).order_by(Achievement.id.desc()))
    ).scalars().all()
    return {"items": [_ser_achievement(a) for a in rows], "redirect_to": "student_login"}


@router.post("/students/{student_id}/achievements")
async def create_student_achievement(
    student_id: str,
    body: AchievementIn,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sp = (
        await db.execute(
            select(StudentProfile)
            .where(StudentProfile.student_id == student_id)
            .options(selectinload(StudentProfile.user), selectinload(StudentProfile.program))
        )
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    await _assert_faculty_can_view_student(user, sp, db)
    row = Achievement(
        student_id=sp.id,
        title=body.title.strip(),
        category=(body.category or "award").strip() or "award",
        description=(body.description or "").strip(),
        awarded_on=_parse_award_date(body.awarded_on) or date.today(),
    )
    db.add(row)
    await db.flush()
    await _notify_student_achievements(
        db,
        student_user_id=sp.user_id,
        faculty_name=user.full_name or user.username,
        title=row.title,
        action="added",
    )
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=user.username,
        role=user.role,
        resource="achievement",
        action="CREATE",
        purpose=f"{student_id}:{row.title}",
        result="ALLOWED",
    )
    await db.flush()
    await db.refresh(row)
    return {
        "ok": True,
        "item": _ser_achievement(row),
        "redirect_to": "student_login",
        "message": "Achievement saved. Student was notified to review it in Student login → Achievements.",
    }


@router.patch("/students/{student_id}/achievements/{achievement_id}")
async def update_student_achievement(
    student_id: str,
    achievement_id: int,
    body: AchievementPatch,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sp = (
        await db.execute(
            select(StudentProfile)
            .where(StudentProfile.student_id == student_id)
            .options(selectinload(StudentProfile.user), selectinload(StudentProfile.program))
        )
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    await _assert_faculty_can_view_student(user, sp, db)
    row = (
        await db.execute(
            select(Achievement).where(Achievement.id == achievement_id, Achievement.student_id == sp.id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Achievement not found")
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        row.title = data["title"].strip()
    if "category" in data and data["category"] is not None:
        row.category = data["category"].strip() or row.category
    if "description" in data and data["description"] is not None:
        row.description = data["description"].strip()
    if "awarded_on" in data:
        row.awarded_on = _parse_award_date(data["awarded_on"])
    await _notify_student_achievements(
        db,
        student_user_id=sp.user_id,
        faculty_name=user.full_name or user.username,
        title=row.title,
        action="updated",
    )
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=user.username,
        role=user.role,
        resource="achievement",
        action="UPDATE",
        purpose=f"{student_id}:{row.id}",
        result="ALLOWED",
    )
    await db.flush()
    await db.refresh(row)
    return {
        "ok": True,
        "item": _ser_achievement(row),
        "redirect_to": "student_login",
        "message": "Achievement updated. Student was notified to review it in Student login.",
    }


@router.delete("/students/{student_id}/achievements/{achievement_id}")
async def delete_student_achievement(
    student_id: str,
    achievement_id: int,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sp = (
        await db.execute(
            select(StudentProfile)
            .where(StudentProfile.student_id == student_id)
            .options(selectinload(StudentProfile.user), selectinload(StudentProfile.program))
        )
    ).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Student not found")
    await _assert_faculty_can_view_student(user, sp, db)
    row = (
        await db.execute(
            select(Achievement).where(Achievement.id == achievement_id, Achievement.student_id == sp.id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Achievement not found")
    title = row.title
    await db.delete(row)
    await _notify_student_achievements(
        db,
        student_user_id=sp.user_id,
        faculty_name=user.full_name or user.username,
        title=title,
        action="removed",
    )
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=user.username,
        role=user.role,
        resource="achievement",
        action="DELETE",
        purpose=f"{student_id}:{achievement_id}",
        result="ALLOWED",
    )
    await db.flush()
    return {"ok": True, "redirect_to": "student_login", "message": "Achievement removed. Student notified via student login."}


@router.get("/mentees")
async def faculty_mentees(
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user.role == "hod":
        dept = (user.department_code or "").strip().upper()
        students = (
            await db.execute(
                select(StudentProfile).options(selectinload(StudentProfile.user)).order_by(StudentProfile.student_id)
            )
        ).scalars().all()
        students = [
            row
            for row in students
            if row.user and ((row.user.department_code or "").upper() == dept or (row.section or "").upper().startswith(dept))
        ]
    else:
        if not user.faculty:
            return {"students": []}
        owned = await mentee_ids(db, user.faculty.id)
        students = (
            await db.execute(
                select(StudentProfile)
                .where(StudentProfile.id.in_(owned or {-1}))
                .options(selectinload(StudentProfile.user))
                .order_by(StudentProfile.student_id)
            )
        ).scalars().all()
    return {
        "students": [
            {
                "student_id": row.student_id,
                "name": row.user.full_name if row.user else "",
                "section": row.section,
                "batch": row.batch,
            }
            for row in students
        ]
    }


@router.get("/leaves")
async def faculty_student_leaves(
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[str] = None,
):
    """Leave applications for students taught by this faculty (or all for HoD)."""
    q = (
        select(HostelLeave)
        .options(selectinload(HostelLeave.student).selectinload(StudentProfile.user))
        .order_by(HostelLeave.from_date.desc())
    )
    if status:
        q = q.where(HostelLeave.status == status)
    rows = (await db.execute(q)).scalars().all()
    if user.role in ("faculty", "school_dean"):
        if not user.faculty:
            return {"leaves": []}
        owned = await mentee_ids(db, user.faculty.id)
        rows = [r for r in rows if r.student_id in owned]
    elif user.role == "hod":
        dept = (user.department_code or "").strip().upper()
        if not dept:
            raise HTTPException(status_code=403, detail="HoD department not configured")
        filtered = []
        for r in rows:
            sp = r.student
            if not sp:
                continue
            stu_dept = (sp.user.department_code or "").upper() if sp.user else ""
            if stu_dept == dept or (sp.section or "").upper().startswith(dept):
                filtered.append(r)
        rows = filtered
    return {
        "leaves": [
            {
                "id": r.id,
                "student_id": r.student.student_id if r.student else None,
                "student_name": r.student.user.full_name if r.student and r.student.user else "",
                "section": r.student.section if r.student else "",
                "from": r.from_date.isoformat(),
                "to": r.to_date.isoformat(),
                "reason": r.reason,
                "destination": r.destination or "",
                "status": r.status,
                "source": r.source or "uis",
                "decision_note": getattr(r, "decision_note", "") or "",
                "faculty_status": getattr(r, "faculty_status", "pending") or "pending",
                "hostel_status": getattr(r, "hostel_status", "pending") or "pending",
            }
            for r in rows
        ]
    }


class FacultyLeaveStatusUpdate(BaseModel):
    status: str = Field(pattern="^(approved|rejected|pending)$")
    note: str = ""


@router.post("/leaves/{leave_id}/status")
async def faculty_update_leave_status(
    leave_id: int,
    body: FacultyLeaveStatusUpdate,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Faculty/HoD approve or reject leave for students in their classes; emails the student."""
    from app.services.email_service import send_leave_status_email

    leave = (
        await db.execute(
            select(HostelLeave)
            .where(HostelLeave.id == leave_id)
            .options(selectinload(HostelLeave.student).selectinload(StudentProfile.user))
        )
    ).scalar_one_or_none()
    if not leave or not leave.student:
        raise HTTPException(status_code=404, detail="Leave not found")
    if user.role != "hod":
        if not user.faculty or leave.student.id not in await mentee_ids(db, user.faculty.id):
            raise HTTPException(status_code=403, detail="This student is not assigned to you as faculty advisor")
    else:
        await _assert_faculty_can_view_student(user, leave.student, db)

    leave.faculty_status = body.status
    if body.note:
        leave.decision_note = (body.note or "")[:500]
    fac = leave.faculty_status or "pending"
    hos = getattr(leave, "hostel_status", "pending") or "pending"
    if fac == "rejected" or hos == "rejected":
        leave.status = "rejected"
    elif fac == "approved" and hos == "approved":
        leave.status = "approved"
    else:
        leave.status = "pending"
    await db.flush()
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=user.username,
        role=user.role,
        resource="hostel.leave",
        action="STATUS",
        purpose=f"leave:{leave_id} faculty->{body.status} overall={leave.status}",
        result="ALLOWED",
    )
    student_user = leave.student.user
    email_sent = False
    if student_user and student_user.email and leave.status in ("approved", "rejected"):
        # Queue email so SMTP latency cannot hang the API worker
        import asyncio

        asyncio.create_task(
            send_leave_status_email(
                student_user.email,
                student_user.full_name or "",
                status=leave.status,
                from_date=leave.from_date.isoformat(),
                to_date=leave.to_date.isoformat(),
                reason=leave.reason,
                destination=leave.destination or "",
                decided_by=user.full_name or user.username,
                decided_role=user.role,
            )
        )
        email_sent = True
    return {
        "ok": True,
        "email_sent": email_sent,
        "leave": {
            "id": leave.id,
            "student_id": leave.student.student_id,
            "status": leave.status,
            "faculty_status": leave.faculty_status,
            "hostel_status": getattr(leave, "hostel_status", "pending"),
            "decision_note": getattr(leave, "decision_note", "") or "",
            "from": leave.from_date.isoformat(),
            "to": leave.to_date.isoformat(),
            "reason": leave.reason,
            "destination": leave.destination or "",
        },
    }


@router.get("/classes/{offering_id}/attendance")
async def class_attendance(
    offering_id: int,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    off = (
        await db.execute(
            select(CourseOffering)
            .where(CourseOffering.id == offering_id)
            .options(selectinload(CourseOffering.course))
        )
    ).scalar_one_or_none()
    if not off:
        raise HTTPException(status_code=404, detail="Offering not found")
    await _assert_offering_access(user, off, db)

    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.offering_id == offering_id)
        .options(selectinload(Enrollment.student).selectinload(StudentProfile.user))
    )
    enrollments = result.scalars().all()
    roster = []
    for e in enrollments:
        ar = (
            await db.execute(select(AttendanceRecord).where(AttendanceRecord.enrollment_id == e.id))
        ).scalar_one_or_none()
        attended = ar.attended if ar else 0
        total = ar.total if ar else 0
        pct = round(100.0 * attended / total, 1) if total else 0.0
        roster.append(
            {
                "enrollment_id": e.id,
                "attendance_id": ar.id if ar else None,
                "student_id": e.student.student_id,
                "name": e.student.user.full_name,
                "attended": attended,
                "total": total,
                "percentage": pct,
            }
        )
    return {
        "offering_id": offering_id,
        "course": off.course.title,
        "code": off.course.code,
        "roster": roster,
    }


class AttendanceUpdate(BaseModel):
    enrollment_id: int
    attended: int = Field(ge=0)
    total: int = Field(ge=0)


class AttendanceBulkUpdate(BaseModel):
    updates: list[AttendanceUpdate]


class MarkSessionRequest(BaseModel):
    """Increment total classes by 1; mark present enrollment_ids as attended +1."""
    present_enrollment_ids: list[int] = []


async def _recalc_overall(db: AsyncSession, student_id: int) -> None:
    result = await db.execute(
        select(AttendanceRecord)
        .join(Enrollment)
        .where(Enrollment.student_id == student_id)
    )
    records = result.scalars().all()
    a = sum(r.attended for r in records)
    t = sum(r.total for r in records)
    sp = (
        await db.execute(select(StudentProfile).where(StudentProfile.id == student_id))
    ).scalar_one_or_none()
    if sp and t > 0:
        sp.overall_attendance = round(100.0 * a / t, 1)


@router.put("/classes/{offering_id}/attendance")
async def update_attendance(
    offering_id: int,
    body: AttendanceBulkUpdate,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    off = (
        await db.execute(select(CourseOffering).where(CourseOffering.id == offering_id))
    ).scalar_one_or_none()
    if not off:
        raise HTTPException(status_code=404, detail="Offering not found")
    await _assert_offering_access(user, off, db)

    touched_students: set[int] = set()
    for item in body.updates:
        if item.attended > item.total:
            raise HTTPException(status_code=400, detail="attended cannot exceed total")
        enr = (
            await db.execute(
                select(Enrollment).where(
                    Enrollment.id == item.enrollment_id,
                    Enrollment.offering_id == offering_id,
                )
            )
        ).scalar_one_or_none()
        if not enr:
            raise HTTPException(status_code=404, detail=f"Enrollment {item.enrollment_id} not in class")
        ar = (
            await db.execute(select(AttendanceRecord).where(AttendanceRecord.enrollment_id == enr.id))
        ).scalar_one_or_none()
        if ar:
            ar.attended = item.attended
            ar.total = item.total
        else:
            db.add(AttendanceRecord(enrollment_id=enr.id, attended=item.attended, total=item.total))
        touched_students.add(enr.student_id)

    await db.flush()
    for sid in touched_students:
        await _recalc_overall(db, sid)
    await db.commit()
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=user.username,
        role=user.role,
        resource="attendance",
        action="UPDATE",
        purpose=f"offering:{offering_id}",
        result="ALLOWED",
    )
    return {"ok": True, "updated": len(body.updates)}


@router.post("/classes/{offering_id}/attendance/session")
async def mark_session(
    offering_id: int,
    body: MarkSessionRequest,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    off = (
        await db.execute(select(CourseOffering).where(CourseOffering.id == offering_id))
    ).scalar_one_or_none()
    if not off:
        raise HTTPException(status_code=404, detail="Offering not found")
    await _assert_offering_access(user, off, db)

    result = await db.execute(select(Enrollment).where(Enrollment.offering_id == offering_id))
    enrollments = result.scalars().all()
    present = set(body.present_enrollment_ids)
    touched: set[int] = set()

    for enr in enrollments:
        ar = (
            await db.execute(select(AttendanceRecord).where(AttendanceRecord.enrollment_id == enr.id))
        ).scalar_one_or_none()
        if not ar:
            ar = AttendanceRecord(enrollment_id=enr.id, attended=0, total=0)
            db.add(ar)
            await db.flush()
        ar.total += 1
        if enr.id in present:
            ar.attended += 1
        touched.add(enr.student_id)

    await db.flush()
    for sid in touched:
        await _recalc_overall(db, sid)
    await db.commit()
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=user.username,
        role=user.role,
        resource="attendance",
        action="SESSION",
        purpose=f"offering:{offering_id} present={len(present)}",
        result="ALLOWED",
    )
    return {"ok": True, "marked": len(enrollments), "present": len(present)}


class AttendanceSessionIn(BaseModel):
    entry_date: date
    slot_name: str = Field(min_length=3, max_length=64)
    status: str = Field(min_length=1, max_length=8)
    session_id: Optional[int] = None


@router.get("/classes/{offering_id}/students/{student_id}/attendance")
async def class_student_attendance(
    offering_id: int,
    student_id: str,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    off = (
        await db.execute(
            select(CourseOffering)
            .where(CourseOffering.id == offering_id)
            .options(selectinload(CourseOffering.course))
        )
    ).scalar_one_or_none()
    if not off:
        raise HTTPException(status_code=404, detail="Offering not found")
    await _assert_offering_access(user, off, db)
    profile = (
        await db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id))
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    enrolled = (
        await db.execute(
            select(Enrollment).where(Enrollment.offering_id == offering_id, Enrollment.student_id == profile.id)
        )
    ).scalar_one_or_none()
    if not enrolled:
        raise HTTPException(status_code=404, detail="Student is not in this class")
    courses = await courses_for_student(db, profile.id)
    mine = [row for row in courses if row["code"] == off.course.code]
    return {"student_id": student_id, "course": off.course.code, "courses": mine}


@router.post("/classes/{offering_id}/students/{student_id}/attendance")
async def save_class_student_attendance(
    offering_id: int,
    student_id: str,
    body: AttendanceSessionIn,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    off = (
        await db.execute(select(CourseOffering).where(CourseOffering.id == offering_id))
    ).scalar_one_or_none()
    if not off:
        raise HTTPException(status_code=404, detail="Offering not found")
    await _assert_offering_access(user, off, db)
    profile = (
        await db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id))
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    enrolled = (
        await db.execute(
            select(Enrollment).where(Enrollment.offering_id == offering_id, Enrollment.student_id == profile.id)
        )
    ).scalar_one_or_none()
    if not enrolled:
        raise HTTPException(status_code=404, detail="Student is not in this class")
    try:
        row = await save_session(db, enrolled.id, body.entry_date, body.slot_name, body.status, body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=user.username,
        role=user.role,
        resource="attendance",
        action="SESSION",
        purpose=f"offering:{offering_id} student:{student_id}",
        result="ALLOWED",
    )
    return {"ok": True, "id": row.id, "status": row.status, "slot_name": row.slot_name}


class RegisterRow(BaseModel):
    student_id: str
    status: str


class RegisterIn(BaseModel):
    entry_date: date
    slot_name: str = Field(min_length=3, max_length=64)
    rows: list[RegisterRow]


class MarkSheetRow(BaseModel):
    student_id: str
    score: float = Field(ge=0)


class MarkSheetIn(BaseModel):
    assessment: str = Field(min_length=1, max_length=64)
    max_score: float = Field(default=100, gt=0)
    rows: list[MarkSheetRow]


@router.get("/classes/{offering_id}/register")
async def class_register(
    offering_id: int,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    entry_date: date = Query(...),
    slot_name: str = Query(default=""),
):
    roster = await class_students(offering_id, user, db)
    slot = slot_name.strip()
    statuses: dict[str, str] = {}
    if slot:
        enrollment_ids = [row["enrollment_id"] for row in roster["students"]]
        if enrollment_ids:
            sessions = (
                await db.execute(
                    select(AttendanceSession).where(
                        AttendanceSession.enrollment_id.in_(enrollment_ids),
                        AttendanceSession.entry_date == entry_date,
                        AttendanceSession.slot_name == slot,
                    )
                )
            ).scalars().all()
            by_enrollment = {row.enrollment_id: row.status for row in sessions}
            statuses = {
                row["student_id"]: by_enrollment.get(row["enrollment_id"], "")
                for row in roster["students"]
            }
    return {
        **roster,
        "entry_date": entry_date.isoformat(),
        "slot_name": slot,
        "students": [{**row, "status": statuses.get(row["student_id"], "")} for row in roster["students"]],
    }


@router.post("/classes/{offering_id}/register")
async def save_class_register(
    offering_id: int,
    body: RegisterIn,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    roster = await class_students(offering_id, user, db)
    allowed = {row["student_id"]: row["enrollment_id"] for row in roster["students"]}
    saved = 0
    try:
        for row in body.rows:
            enrollment_id = allowed.get(row.student_id.strip())
            if not enrollment_id:
                raise HTTPException(status_code=400, detail=f"{row.student_id} is not in this section.")
            await save_session(db, enrollment_id, body.entry_date, body.slot_name, row.status)
            saved += 1
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    actor_name = user.username
    actor_role = user.role
    await db.commit()
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=actor_name,
        role=actor_role,
        resource="attendance",
        action="REGISTER",
        purpose=f"offering:{offering_id} saved={saved}",
        result="ALLOWED",
    )
    return {"ok": True, "saved": saved}


@router.get("/classes/{offering_id}/mark-sheet")
async def class_mark_sheet(
    offering_id: int,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    assessment: str = Query(default=""),
):
    roster = await class_students(offering_id, user, db)
    name = assessment.strip()
    scores: dict[int, tuple] = {}
    enrollment_ids = [row["enrollment_id"] for row in roster["students"]]
    if name and enrollment_ids:
        marks = (
            await db.execute(
                select(Mark).where(Mark.enrollment_id.in_(enrollment_ids), Mark.assessment == name)
            )
        ).scalars().all()
        scores = {row.enrollment_id: (row.score, row.max_score) for row in marks}
    return {
        **roster,
        "assessment": name,
        "students": [
            {
                **row,
                "score": scores.get(row["enrollment_id"], (None, None))[0],
                "max_score": scores.get(row["enrollment_id"], (None, None))[1],
            }
            for row in roster["students"]
        ],
    }


@router.post("/classes/{offering_id}/mark-sheet")
async def save_class_mark_sheet(
    offering_id: int,
    body: MarkSheetIn,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _reject_if_marks_locked(db, offering_id)
    roster = await class_students(offering_id, user, db)
    allowed = {row["student_id"]: row["enrollment_id"] for row in roster["students"]}
    name = body.assessment.strip()
    saved = 0
    for row in body.rows:
        if row.score > body.max_score:
            raise HTTPException(status_code=400, detail=f"Score for {row.student_id} is above the maximum.")
        enrollment_id = allowed.get(row.student_id.strip())
        if not enrollment_id:
            raise HTTPException(status_code=400, detail=f"{row.student_id} is not in this section.")
        mark = (
            await db.execute(select(Mark).where(Mark.enrollment_id == enrollment_id, Mark.assessment == name))
        ).scalar_one_or_none()
        if mark:
            mark.score = row.score
            mark.max_score = body.max_score
        else:
            db.add(Mark(enrollment_id=enrollment_id, assessment=name, score=row.score, max_score=body.max_score))
        saved += 1
    actor_name = user.username
    actor_role = user.role
    await db.commit()
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=actor_name,
        role=actor_role,
        resource="marks",
        action="SHEET",
        purpose=f"offering:{offering_id} {name} saved={saved}",
        result="ALLOWED",
    )
    return {"ok": True, "saved": saved}


class MarkEntry(BaseModel):
    assessment: str = Field(min_length=1, max_length=64)
    score: float = Field(ge=0)
    max_score: float = Field(default=100, gt=0)


async def _class_enrollment(db: AsyncSession, user: User, offering_id: int, student_id: str) -> tuple[CourseOffering, Enrollment]:
    off = (
        await db.execute(
            select(CourseOffering)
            .where(CourseOffering.id == offering_id)
            .options(selectinload(CourseOffering.course))
        )
    ).scalar_one_or_none()
    if not off:
        raise HTTPException(status_code=404, detail="Offering not found")
    await _assert_offering_access(user, off, db)
    profile = (
        await db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id))
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    enrolled = (
        await db.execute(
            select(Enrollment).where(Enrollment.offering_id == offering_id, Enrollment.student_id == profile.id)
        )
    ).scalar_one_or_none()
    if not enrolled:
        raise HTTPException(status_code=404, detail="Student is not in this class")
    return off, enrolled


@router.get("/classes/{offering_id}/students/{student_id}/marks")
async def class_student_marks(
    offering_id: int,
    student_id: str,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    off, enrolled = await _class_enrollment(db, user, offering_id, student_id)
    marks = (
        await db.execute(select(Mark).where(Mark.enrollment_id == enrolled.id).order_by(Mark.id))
    ).scalars().all()
    course = off.course
    return {
        "student_id": student_id,
        "courses": [
            {
                "code": course.code if course else "",
                "name": course.title if course else "",
                "status": "ok" if marks else "attention",
                "assessments": [
                    {"id": mark.id, "assessment": mark.assessment, "score": mark.score, "max_score": mark.max_score}
                    for mark in marks
                ],
            }
        ],
    }


@router.post("/classes/{offering_id}/students/{student_id}/marks")
async def save_class_student_mark(
    offering_id: int,
    student_id: str,
    body: MarkEntry,
    user: Annotated[User, Depends(require_roles("faculty", "hod", "school_dean"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if body.score > body.max_score:
        raise HTTPException(status_code=400, detail="Score cannot be higher than the maximum.")
    await _reject_if_marks_locked(db, offering_id)
    _off, enrolled = await _class_enrollment(db, user, offering_id, student_id)
    name = body.assessment.strip()
    row = (
        await db.execute(select(Mark).where(Mark.enrollment_id == enrolled.id, Mark.assessment == name))
    ).scalar_one_or_none()
    if row:
        row.score = body.score
        row.max_score = body.max_score
    else:
        row = Mark(enrollment_id=enrolled.id, assessment=name, score=body.score, max_score=body.max_score)
        db.add(row)
    actor_name = user.username
    actor_role = user.role
    await db.commit()
    await write_audit(
        db,
        actor="UIS Faculty",
        user_ref=actor_name,
        role=actor_role,
        resource="marks",
        action="ENTRY",
        purpose=f"offering:{offering_id} student:{student_id} {name}",
        result="ALLOWED",
    )
    return {"ok": True, "assessment": name, "score": body.score, "max_score": body.max_score}


class MarksLockIn(BaseModel):
    locked: bool


@router.post("/classes/{offering_id}/marks-lock")
async def set_marks_lock(
    offering_id: int,
    body: MarksLockIn,
    user: Annotated[User, Depends(require_roles("coe", "exam_admin", "admin", "university_admin", "super_admin", "developer", "operator"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    off = await db.get(CourseOffering, offering_id)
    if not off:
        raise HTTPException(status_code=404, detail="Class not found")
    off.marks_locked = body.locked
    await db.commit()
    return {"ok": True, "offering_id": offering_id, "locked": off.marks_locked, "by": user.username}
