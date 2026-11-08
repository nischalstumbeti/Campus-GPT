from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Achievement,
    Announcement,
    AttendanceRecord,
    AttendanceSession,
    CourseOffering,
    Enrollment,
    ExamSchedule,
    FacultyProfile,
    Grade,
    HostelAllocation,
    HostelBlock,
    HostelLeave,
    Mark,
    Room,
    TimetableSlot,
    User,
)
from app.security.auth import get_current_user, require_roles
from app.services.attendance_board import course_summary
from app.services.audit import write_audit
from app.services.payloads import serialize_timetable_slot

router = APIRouter(prefix="/api/v1/student", tags=["student"])


def _student_or_403(user: User):
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    return user.student


@router.get("/dashboard")
async def dashboard(user: Annotated[User, Depends(require_roles("student"))]):
    s = _student_or_403(user)
    prog = s.program
    return {
        "welcome": f"Welcome, {user.full_name}",
        "program": prog.name if prog else "B.Tech Computer Science & Engineering",
        "year": s.year,
        "semester": s.semester,
        "section": s.section,
        "student_id": s.student_id,
        "cgpa": s.cgpa,
        "attendance": s.overall_attendance,
        "credits": f"{s.credits_completed} / {s.credits_required}",
        "credits_completed": s.credits_completed,
        "credits_required": s.credits_required,
        "backlogs": s.backlogs,
        "batch": s.batch,
        "name": user.full_name,
        "photo_url": s.photo_url or user.photo_url or "",
        "demo": True,
    }


@router.get("/courses")
async def courses(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.student_id == s.id)
        .options(selectinload(Enrollment.offering).selectinload(CourseOffering.course))
    )
    rows = result.scalars().all()
    return {
        "student_id": s.student_id,
        "courses": [
            {
                "code": e.offering.course.code,
                "title": e.offering.course.title,
                "credits": e.offering.course.credits,
                "section": e.offering.section,
                "semester": e.offering.semester,
            }
            for e in rows
        ],
    }


@router.get("/attendance")
async def attendance(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    enrollments = (
        await db.execute(
            select(Enrollment)
            .where(Enrollment.student_id == s.id)
            .options(selectinload(Enrollment.offering).selectinload(CourseOffering.course))
        )
    ).scalars().all()
    ids = [row.id for row in enrollments]
    records = {}
    sessions: dict[int, list] = {}
    if ids:
        for record in (
            await db.execute(select(AttendanceRecord).where(AttendanceRecord.enrollment_id.in_(ids)))
        ).scalars().all():
            records[record.enrollment_id] = record
        for session in (
            await db.execute(select(AttendanceSession).where(AttendanceSession.enrollment_id.in_(ids)))
        ).scalars().all():
            sessions.setdefault(session.enrollment_id, []).append(session)
    courses = []
    flat = []
    for enrollment in enrollments:
        course = enrollment.offering.course if enrollment.offering else None
        if not course:
            continue
        summary = course_summary(course.code, course.title, sessions.get(enrollment.id, []), records.get(enrollment.id))
        courses.append(summary)
        flat.append(
            {
                "course": course.title,
                "code": course.code,
                "attended": summary["attended"],
                "total": summary["conducted"],
                "percentage": summary["percentage"],
            }
        )
    courses.sort(key=lambda row: row["code"])
    return {"student_id": s.student_id, "overall": s.overall_attendance, "attendance": flat, "courses": courses}


@router.get("/marks")
async def marks(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    enrollments = (
        await db.execute(
            select(Enrollment)
            .where(Enrollment.student_id == s.id)
            .options(selectinload(Enrollment.offering).selectinload(CourseOffering.course))
        )
    ).scalars().all()
    enrollment_ids = [e.id for e in enrollments]
    mark_rows = []
    if enrollment_ids:
        mark_rows = (
            await db.execute(select(Mark).where(Mark.enrollment_id.in_(enrollment_ids)).order_by(Mark.id))
        ).scalars().all()
    by_enrollment: dict[int, list] = {}
    for mark in mark_rows:
        by_enrollment.setdefault(mark.enrollment_id, []).append(mark)
    courses = []
    flat = []
    for enrollment in enrollments:
        course = enrollment.offering.course if enrollment.offering else None
        if not course:
            continue
        assessments = by_enrollment.get(enrollment.id, [])
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
        for m in assessments:
            flat.append(
                {
                    "course": course.title,
                    "code": course.code,
                    "assessment": m.assessment,
                    "score": m.score,
                    "max_score": m.max_score,
                }
            )
    courses.sort(key=lambda row: row["code"])
    return {"student_id": s.student_id, "courses": courses, "marks": flat}


@router.get("/grades")
async def grades(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    result = await db.execute(
        select(Grade)
        .join(Enrollment)
        .where(Enrollment.student_id == s.id)
        .options(
            selectinload(Grade.enrollment).selectinload(Enrollment.offering).selectinload(CourseOffering.course)
        )
    )
    rows = result.scalars().all()
    return {
        "student_id": s.student_id,
        "cgpa": s.cgpa,
        "grades": [
            {
                "course": g.enrollment.offering.course.title,
                "code": g.enrollment.offering.course.code,
                "letter": g.letter,
                "grade_point": g.grade_point,
            }
            for g in rows
        ],
    }


def _sgpa(rows: list[dict]) -> Optional[float]:
    weighted = 0.0
    credits = 0
    for row in rows:
        if row["result_group"] != "cgpa" or row["credits"] <= 0 or row["grade_point"] is None:
            continue
        weighted += row["grade_point"] * row["credits"]
        credits += row["credits"]
    if credits <= 0:
        return None
    return round(weighted / credits, 2)


@router.get("/academics")
async def academics(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.student_id == s.id)
        .options(selectinload(Enrollment.offering).selectinload(CourseOffering.course))
    )
    enrollments = result.scalars().all()
    grades = (
        await db.execute(
            select(Grade)
            .join(Enrollment)
            .where(Enrollment.student_id == s.id)
        )
    ).scalars().all()
    grade_by_enrollment = {g.enrollment_id: g for g in grades}
    rows = []
    for enrollment in enrollments:
        course = enrollment.offering.course
        grade = grade_by_enrollment.get(enrollment.id)
        rows.append(
            {
                "code": course.code,
                "title": course.title,
                "credits": course.credits,
                "semester": enrollment.offering.semester,
                "result_group": course.result_group or "cgpa",
                "letter": grade.letter if grade else "",
                "grade_point": grade.grade_point if grade else None,
            }
        )
    semesters = []
    for semester in sorted({row["semester"] for row in rows}):
        items = [row for row in rows if row["semester"] == semester]
        cgpa_items = [row for row in items if row["result_group"] == "cgpa"]
        semesters.append(
            {
                "semester": semester,
                "courses": items,
                "credits": sum(row["credits"] for row in cgpa_items),
                "sgpa": _sgpa(items),
            }
        )
    return {
        "student_id": s.student_id,
        "cgpa": s.cgpa,
        "credits_completed": s.credits_completed,
        "credits_required": s.credits_required,
        "backlogs": s.backlogs,
        "semesters": semesters,
        "non_cgpa": [row for row in rows if row["result_group"] == "non_cgpa"],
        "mandatory": [row for row in rows if row["result_group"] == "mandatory"],
    }


@router.get("/timetable")
async def timetable(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    result = await db.execute(select(Enrollment.offering_id).where(Enrollment.student_id == s.id))
    offering_ids = [r[0] for r in result.all()]
    if not offering_ids:
        return {"student_id": s.student_id, "slots": []}
    slots_q = await db.execute(
        select(TimetableSlot)
        .where(TimetableSlot.offering_id.in_(offering_ids))
        .options(
            selectinload(TimetableSlot.offering).selectinload(CourseOffering.course),
            selectinload(TimetableSlot.offering)
            .selectinload(CourseOffering.faculty)
            .selectinload(FacultyProfile.user),
        )
    )
    slots = slots_q.scalars().all()
    return {
        "student_id": s.student_id,
        "slots": [serialize_timetable_slot(sl) for sl in slots],
    }


@router.get("/exams")
async def exams(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    result = await db.execute(
        select(Enrollment).where(Enrollment.student_id == s.id).options(selectinload(Enrollment.offering))
    )
    course_ids = [e.offering.course_id for e in result.scalars().all()]
    if not course_ids:
        return {"student_id": s.student_id, "exams": []}
    eq = await db.execute(
        select(ExamSchedule).where(ExamSchedule.course_id.in_(course_ids)).options(selectinload(ExamSchedule.course))
    )
    exams_list = eq.scalars().all()
    return {
        "student_id": s.student_id,
        "exams": [
            {
                "id": e.id,
                "course": e.course.title,
                "code": e.course.code,
                "type": e.exam_type,
                "date": e.exam_date.isoformat(),
                "start": e.start_time,
                "venue": e.venue,
                "has_paper": bool((e.paper_text or "").strip()),
            }
            for e in exams_list
        ],
    }


@router.get("/exams/{exam_id}")
async def exam_paper(
    exam_id: int,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    s = _student_or_403(user)
    enrolled = (
        await db.execute(
            select(Enrollment).where(Enrollment.student_id == s.id).options(selectinload(Enrollment.offering))
        )
    ).scalars().all()
    course_ids = {row.offering.course_id for row in enrolled if row.offering}
    exam = (
        await db.execute(
            select(ExamSchedule).where(ExamSchedule.id == exam_id).options(selectinload(ExamSchedule.course))
        )
    ).scalar_one_or_none()
    if not exam or exam.course_id not in course_ids:
        raise HTTPException(status_code=404, detail="Exam paper not found")
    if not (exam.paper_text or "").strip():
        raise HTTPException(status_code=404, detail="This paper has not been published yet.")
    return {
        "id": exam.id,
        "course": exam.course.title,
        "code": exam.course.code,
        "type": exam.exam_type,
        "date": exam.exam_date.isoformat(),
        "start": exam.start_time,
        "venue": exam.venue,
        "paper": exam.paper_text,
    }


def _leave_dict(l: HostelLeave) -> dict:
    return {
        "id": l.id,
        "from": l.from_date.isoformat(),
        "to": l.to_date.isoformat(),
        "reason": l.reason,
        "destination": l.destination or "",
        "status": l.status,
        "source": l.source or "uis",
    }


class StudentLeaveIn(BaseModel):
    from_date: date
    to_date: date
    reason: str = Field(min_length=2, max_length=255)
    destination: str = ""


@router.get("/hostel")
async def hostel(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    aq = await db.execute(
        select(HostelAllocation)
        .where(HostelAllocation.student_id == s.id)
        .options(selectinload(HostelAllocation.room).selectinload(Room.block).selectinload(HostelBlock.hostel))
    )
    alloc = aq.scalar_one_or_none()
    lq = await db.execute(
        select(HostelLeave).where(HostelLeave.student_id == s.id).order_by(HostelLeave.from_date.desc())
    )
    leaves = lq.scalars().all()
    room_info = None
    if alloc:
        room_info = {
            "hostel": alloc.room.block.hostel.name,
            "block": alloc.room.block.name,
            "room": alloc.room.room_number,
            "bed": alloc.bed_no,
            "status": alloc.status,
        }
    return {
        "student_id": s.student_id,
        "allocation": room_info,
        "leaves": [_leave_dict(l) for l in leaves],
    }


@router.post("/hostel/leave")
async def apply_hostel_leave(
    body: StudentLeaveIn,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    s = _student_or_403(user)
    if body.to_date < body.from_date:
        raise HTTPException(status_code=400, detail="to_date must be on or after from_date")
    leave = HostelLeave(
        student_id=s.id,
        from_date=body.from_date,
        to_date=body.to_date,
        reason=body.reason.strip(),
        destination=(body.destination or "").strip(),
        status="pending",
        source="uis",
    )
    db.add(leave)
    await db.commit()
    await db.refresh(leave)
    await write_audit(
        db,
        actor="UIS Student",
        user_ref=user.username,
        role=user.role,
        resource="hostel.leave",
        action="APPLY",
        purpose=f"leave:{leave.id}",
        result="ALLOWED",
    )
    return {"ok": True, "leave": _leave_dict(leave)}


@router.get("/achievements")
async def achievements(user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    s = _student_or_403(user)
    result = await db.execute(select(Achievement).where(Achievement.student_id == s.id))
    rows = result.scalars().all()
    return {
        "student_id": s.student_id,
        "achievements": [
            {
                "title": a.title,
                "category": a.category,
                "awarded_on": a.awarded_on.isoformat() if a.awarded_on else None,
                "description": a.description,
            }
            for a in rows
        ],
    }


@router.get("/announcements")
async def announcements(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Announcement).order_by(Announcement.published_at.desc()).limit(50))
    rows = result.scalars().all()
    return {
        "items": [
            {
                "id": a.id,
                "title": a.title,
                "body": a.body,
                "audience": a.audience,
                "published_at": a.published_at.isoformat(),
            }
            for a in rows
        ]
    }
