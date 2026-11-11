"""Admin edits for class times, examination venues, office hours, and courses."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Course,
    CourseOffering,
    Department,
    ExamSchedule,
    FacultyAvailability,
    FacultyProfile,
    TimetableSlot,
    User,
)
from app.security.auth import require_roles
from app.services.acknowledge import issue_acknowledgement
from app.services.audit import write_audit
from app.services.confirm import PhraseIn, require_phrase
from app.services.payloads import DAYS, faculty_name

router = APIRouter(prefix="/api/v1/admin/records", tags=["admin-records"])
EditRoles = require_roles("university_admin", "admin", "super_admin", "developer", "operator", "coe")

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class SlotIn(BaseModel):
    offering_id: int
    day_of_week: int = Field(ge=0, le=6)
    start_time: str = Field(min_length=4, max_length=8)
    end_time: str = Field(min_length=4, max_length=8)
    room: str = Field(min_length=1, max_length=32)


class ExamIn(BaseModel):
    course_id: int
    exam_type: str = Field(min_length=1, max_length=32)
    exam_date: date
    start_time: str = Field(min_length=4, max_length=8)
    venue: str = Field(min_length=1, max_length=64)
    semester: int = Field(ge=1, le=12)
    paper_text: str = ""


class OfficeIn(BaseModel):
    faculty_id: int
    day_of_week: str = Field(min_length=3, max_length=16)
    start_time: str = Field(min_length=4, max_length=8)
    end_time: str = Field(min_length=4, max_length=8)
    kind: str = "office_hours"
    location: str = ""
    notes: str = ""


class CourseIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    title: str = Field(min_length=2, max_length=255)
    credits: int = Field(ge=0, le=30)
    department_id: int
    result_group: str = "cgpa"


def _slot(row: TimetableSlot) -> dict:
    offering = row.offering
    course = offering.course if offering else None
    return {
        "id": row.id,
        "offering_id": row.offering_id,
        "day_of_week": row.day_of_week,
        "day": DAYS[row.day_of_week] if 0 <= row.day_of_week < 7 else str(row.day_of_week),
        "start_time": row.start_time,
        "end_time": row.end_time,
        "room": row.room,
        "code": course.code if course else "",
        "title": course.title if course else "",
        "section": offering.section if offering else "",
        "semester": offering.semester if offering else None,
        "faculty": faculty_name(offering.faculty if offering else None),
    }


def _exam(row: ExamSchedule) -> dict:
    return {
        "id": row.id,
        "course_id": row.course_id,
        "code": row.course.code if row.course else "",
        "title": row.course.title if row.course else "",
        "exam_type": row.exam_type,
        "exam_date": row.exam_date.isoformat(),
        "start_time": row.start_time,
        "venue": row.venue,
        "semester": row.semester,
        "paper_text": row.paper_text or "",
    }


def _office(row: FacultyAvailability) -> dict:
    faculty = row.faculty
    return {
        "id": row.id,
        "faculty_id": row.faculty_id,
        "faculty_name": faculty_name(faculty),
        "day_of_week": row.day_of_week,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "kind": row.kind,
        "location": row.location or "",
        "notes": row.notes or "",
    }


async def _offering(db: AsyncSession, offering_id: int) -> CourseOffering:
    row = (
        await db.execute(select(CourseOffering).where(CourseOffering.id == offering_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail="Choose a class that already exists in course allocation")
    return row


async def _course(db: AsyncSession, course_id: int) -> Course:
    row = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail="Choose a course")
    return row


async def _faculty(db: AsyncSession, faculty_id: int) -> FacultyProfile:
    row = (await db.execute(select(FacultyProfile).where(FacultyProfile.id == faculty_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail="Choose a faculty member")
    return row


def _day_name(value: str) -> str:
    cleaned = value.strip()
    match = next((name for name in DAY_NAMES if name.lower() == cleaned.lower()), None)
    if not match:
        raise HTTPException(status_code=400, detail="Day must be Monday through Sunday")
    return match


async def _audit(db: AsyncSession, user: User, resource: str, action: str, purpose: str) -> None:
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource=resource,
        action=action,
        purpose=purpose,
        result="ALLOWED",
    )


@router.get("")
async def records(_: Annotated[User, Depends(EditRoles)], db: Annotated[AsyncSession, Depends(get_db)]):
    offerings = (
        await db.execute(
            select(CourseOffering)
            .options(
                selectinload(CourseOffering.course),
                selectinload(CourseOffering.faculty).selectinload(FacultyProfile.user),
            )
            .order_by(CourseOffering.semester, CourseOffering.section, CourseOffering.id)
        )
    ).scalars().all()
    courses = (await db.execute(select(Course).order_by(Course.code))).scalars().all()
    departments = (await db.execute(select(Department).order_by(Department.code))).scalars().all()
    faculty = (
        await db.execute(
            select(FacultyProfile).options(selectinload(FacultyProfile.user)).order_by(FacultyProfile.id)
        )
    ).scalars().all()
    slots = (
        await db.execute(
            select(TimetableSlot)
            .options(
                selectinload(TimetableSlot.offering).selectinload(CourseOffering.course),
                selectinload(TimetableSlot.offering).selectinload(CourseOffering.faculty).selectinload(FacultyProfile.user),
            )
            .order_by(TimetableSlot.day_of_week, TimetableSlot.start_time, TimetableSlot.id)
        )
    ).scalars().all()
    exams = (
        await db.execute(
            select(ExamSchedule)
            .options(selectinload(ExamSchedule.course))
            .order_by(ExamSchedule.exam_date, ExamSchedule.start_time, ExamSchedule.id)
        )
    ).scalars().all()
    hours = (
        await db.execute(
            select(FacultyAvailability)
            .options(selectinload(FacultyAvailability.faculty).selectinload(FacultyProfile.user))
            .order_by(FacultyAvailability.day_of_week, FacultyAvailability.start_time, FacultyAvailability.id)
        )
    ).scalars().all()
    return {
        "offerings": [
            {
                "id": row.id,
                "label": (
                    f"{row.course.code} · {row.course.title} · Sem {row.semester} {row.section}"
                    + (f" · {faculty_name(row.faculty)}" if row.faculty else "")
                ),
            }
            for row in offerings
            if row.course
        ],
        "courses": [
            {
                "id": row.id,
                "code": row.code,
                "title": row.title,
                "credits": row.credits,
                "department_id": row.department_id,
                "result_group": row.result_group or "cgpa",
            }
            for row in courses
        ],
        "departments": [{"id": row.id, "code": row.code, "name": row.name} for row in departments],
        "faculty": [
            {"id": row.id, "name": row.user.full_name if row.user else row.faculty_id}
            for row in faculty
        ],
        "timetable": [_slot(row) for row in slots],
        "exams": [_exam(row) for row in exams],
        "office_hours": [_office(row) for row in hours],
    }


@router.post("/timetable")
async def create_slot(
    body: SlotIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _offering(db, body.offering_id)
    row = TimetableSlot(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await _audit(db, user, "timetable", "CREATE", str(row.id))
    return {"ok": True, "id": row.id}


@router.patch("/timetable/{slot_id}")
async def update_slot(
    slot_id: int,
    body: SlotIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(TimetableSlot).where(TimetableSlot.id == slot_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Class period not found")
    await _offering(db, body.offering_id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await _audit(db, user, "timetable", "UPDATE", str(slot_id))
    return {"ok": True, "id": slot_id}


@router.delete("/timetable/{slot_id}")
async def delete_slot(
    slot_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(
            select(TimetableSlot)
            .where(TimetableSlot.id == slot_id)
            .options(selectinload(TimetableSlot.offering).selectinload(CourseOffering.course))
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Class period not found")
    code = row.offering.course.code if row.offering and row.offering.course else str(slot_id)
    require_phrase(body.confirm, code)
    await db.delete(row)
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="delete-timetable",
        title="Class period deleted",
        summary=f"Deleted the {code} class period from the timetable. The database row was removed.",
        email=user.email,
    )
    await _audit(db, user, "timetable", "DELETE", str(slot_id))
    return {"ok": True, "acknowledgement": ack}


@router.post("/exams")
async def create_exam(
    body: ExamIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _course(db, body.course_id)
    row = ExamSchedule(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await _audit(db, user, "exam_schedule", "CREATE", str(row.id))
    return {"ok": True, "id": row.id}


@router.patch("/exams/{exam_id}")
async def update_exam(
    exam_id: int,
    body: ExamIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(ExamSchedule).where(ExamSchedule.id == exam_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Examination not found")
    await _course(db, body.course_id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await _audit(db, user, "exam_schedule", "UPDATE", str(exam_id))
    return {"ok": True, "id": exam_id}


@router.delete("/exams/{exam_id}")
async def delete_exam(
    exam_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(
            select(ExamSchedule).where(ExamSchedule.id == exam_id).options(selectinload(ExamSchedule.course))
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Examination not found")
    code = row.course.code if row.course else str(exam_id)
    require_phrase(body.confirm, code)
    venue = row.venue
    await db.delete(row)
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="delete-exam",
        title="Examination deleted",
        summary=f"Deleted the {code} examination at {venue}. The hall ticket will no longer list it.",
        email=user.email,
    )
    await _audit(db, user, "exam_schedule", "DELETE", str(exam_id))
    return {"ok": True, "acknowledgement": ack}


@router.post("/office-hours")
async def create_office(
    body: OfficeIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _faculty(db, body.faculty_id)
    data = body.model_dump()
    data["day_of_week"] = _day_name(data["day_of_week"])
    data["kind"] = (data["kind"] or "office_hours").strip()[:32]
    data["location"] = data["location"].strip()[:80]
    data["notes"] = data["notes"].strip()[:255]
    row = FacultyAvailability(**data)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await _audit(db, user, "office_hours", "CREATE", str(row.id))
    return {"ok": True, "id": row.id}


@router.patch("/office-hours/{row_id}")
async def update_office(
    row_id: int,
    body: OfficeIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(FacultyAvailability).where(FacultyAvailability.id == row_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Office hour not found")
    await _faculty(db, body.faculty_id)
    data = body.model_dump()
    data["day_of_week"] = _day_name(data["day_of_week"])
    data["kind"] = (data["kind"] or "office_hours").strip()[:32]
    data["location"] = data["location"].strip()[:80]
    data["notes"] = data["notes"].strip()[:255]
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    await _audit(db, user, "office_hours", "UPDATE", str(row_id))
    return {"ok": True, "id": row_id}


@router.delete("/office-hours/{row_id}")
async def delete_office(
    row_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(
            select(FacultyAvailability)
            .where(FacultyAvailability.id == row_id)
            .options(selectinload(FacultyAvailability.faculty).selectinload(FacultyProfile.user))
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Office hour not found")
    expected = faculty_name(row.faculty) or "REMOVE"
    require_phrase(body.confirm, expected)
    await db.delete(row)
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="delete-office-hours",
        title="Faculty hours deleted",
        summary=f"Deleted office hours for {expected}.",
        email=user.email,
    )
    await _audit(db, user, "office_hours", "DELETE", str(row_id))
    return {"ok": True, "acknowledgement": ack}


@router.post("/courses")
async def create_course(
    body: CourseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    department = (await db.execute(select(Department).where(Department.id == body.department_id))).scalar_one_or_none()
    if not department:
        raise HTTPException(status_code=400, detail="Choose a department")
    group = body.result_group if body.result_group in {"cgpa", "non_cgpa", "mandatory"} else "cgpa"
    row = Course(
        code=body.code.strip().upper(),
        title=body.title.strip(),
        credits=body.credits,
        department_id=body.department_id,
        result_group=group,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail="That course code is already used") from exc
    await db.refresh(row)
    await _audit(db, user, "course", "CREATE", row.code)
    return {"ok": True, "id": row.id}


@router.patch("/courses/{course_id}")
async def update_course(
    course_id: int,
    body: CourseIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Course not found")
    department = (await db.execute(select(Department).where(Department.id == body.department_id))).scalar_one_or_none()
    if not department:
        raise HTTPException(status_code=400, detail="Choose a department")
    row.code = body.code.strip().upper()
    row.title = body.title.strip()
    row.credits = body.credits
    row.department_id = body.department_id
    row.result_group = body.result_group if body.result_group in {"cgpa", "non_cgpa", "mandatory"} else "cgpa"
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail="That course code is already used") from exc
    await _audit(db, user, "course", "UPDATE", row.code)
    return {"ok": True, "id": course_id}
