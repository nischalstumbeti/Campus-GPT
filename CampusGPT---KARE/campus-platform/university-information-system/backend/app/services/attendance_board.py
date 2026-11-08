"""Course attendance summary built from period-level sessions."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.models import AttendanceRecord, AttendanceSession, CourseOffering, Enrollment, StudentProfile

STATUSES = ("P", "A", "OD", "ML", "RH", "EH")


def course_summary(code: str, name: str, sessions: list[AttendanceSession], fallback: AttendanceRecord | None = None) -> dict:
    if sessions:
        conducted = sum(1 for row in sessions if row.status != "EH")
        attended = sum(1 for row in sessions if row.status == "P")
        onduty = sum(1 for row in sessions if row.status == "OD")
        medical = sum(1 for row in sessions if row.status == "ML")
        restricted = sum(1 for row in sessions if row.status == "RH")
        extra = sum(1 for row in sessions if row.status == "EH")
    else:
        conducted = fallback.total if fallback else 0
        attended = fallback.attended if fallback else 0
        onduty = medical = restricted = extra = 0
    percentage = round(100.0 * attended / conducted, 1) if conducted else 0.0
    ordered = sorted(sessions, key=lambda row: (row.entry_date, row.slot_name, row.id))
    return {
        "code": code,
        "name": name,
        "status": "ok" if conducted and percentage >= 75 else "attention",
        "conducted": conducted,
        "attended": attended,
        "onduty": onduty,
        "medical": medical,
        "restricted": restricted,
        "extra": extra,
        "percentage": percentage,
        "sessions": [
            {
                "id": row.id,
                "entry_date": row.entry_date.isoformat(),
                "slot_name": row.slot_name,
                "status": row.status,
            }
            for row in ordered
        ],
    }


async def courses_for_student(db: AsyncSession, profile_id: int) -> list[dict]:
    enrollments = (
        await db.execute(
            select(Enrollment)
            .where(Enrollment.student_id == profile_id)
            .options(selectinload(Enrollment.offering).selectinload(CourseOffering.course))
        )
    ).scalars().all()
    ids = [row.id for row in enrollments]
    records = {}
    grouped: dict[int, list] = {}
    if ids:
        for record in (
            await db.execute(select(AttendanceRecord).where(AttendanceRecord.enrollment_id.in_(ids)))
        ).scalars().all():
            records[record.enrollment_id] = record
        for session in (
            await db.execute(select(AttendanceSession).where(AttendanceSession.enrollment_id.in_(ids)))
        ).scalars().all():
            grouped.setdefault(session.enrollment_id, []).append(session)
    courses = []
    for enrollment in enrollments:
        course = enrollment.offering.course if enrollment.offering else None
        if not course:
            continue
        courses.append(
            course_summary(course.code, course.title, grouped.get(enrollment.id, []), records.get(enrollment.id))
        )
    courses.sort(key=lambda row: row["code"])
    return courses


async def sync_record(db: AsyncSession, enrollment_id: int) -> None:
    sessions = (
        await db.execute(select(AttendanceSession).where(AttendanceSession.enrollment_id == enrollment_id))
    ).scalars().all()
    if not sessions:
        return
    attended = sum(1 for row in sessions if row.status == "P")
    total = sum(1 for row in sessions if row.status != "EH")
    record = (
        await db.execute(select(AttendanceRecord).where(AttendanceRecord.enrollment_id == enrollment_id))
    ).scalar_one_or_none()
    if record:
        record.attended = attended
        record.total = total
    else:
        db.add(AttendanceRecord(enrollment_id=enrollment_id, attended=attended, total=total))
    enrollment = (
        await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
    ).scalar_one_or_none()
    if not enrollment:
        return
    records = (
        await db.execute(
            select(AttendanceRecord).join(Enrollment).where(Enrollment.student_id == enrollment.student_id)
        )
    ).scalars().all()
    present = sum(row.attended for row in records)
    conducted = sum(row.total for row in records)
    profile = (
        await db.execute(select(StudentProfile).where(StudentProfile.id == enrollment.student_id))
    ).scalar_one_or_none()
    if profile and conducted > 0:
        profile.overall_attendance = round(100.0 * present / conducted, 1)


async def save_session(
    db: AsyncSession,
    enrollment_id: int,
    entry_date: date,
    slot_name: str,
    status: str,
    session_id: int | None = None,
) -> AttendanceSession:
    code = status.strip().upper()
    slot = slot_name.strip()
    if code not in STATUSES:
        raise ValueError("Status must be P, A, OD, ML, RH, or EH.")
    if len(slot) < 3:
        raise ValueError("Enter the slot name.")
    row = None
    if session_id:
        row = (
            await db.execute(
                select(AttendanceSession).where(
                    AttendanceSession.id == session_id,
                    AttendanceSession.enrollment_id == enrollment_id,
                )
            )
        ).scalar_one_or_none()
    if row is None:
        row = (
            await db.execute(
                select(AttendanceSession).where(
                    AttendanceSession.enrollment_id == enrollment_id,
                    AttendanceSession.entry_date == entry_date,
                    AttendanceSession.slot_name == slot,
                )
            )
        ).scalar_one_or_none()
    if row:
        row.entry_date = entry_date
        row.slot_name = slot
        row.status = code
    else:
        row = AttendanceSession(
            enrollment_id=enrollment_id,
            entry_date=entry_date,
            slot_name=slot,
            status=code,
        )
        db.add(row)
    await db.flush()
    await sync_record(db, enrollment_id)
    return row
