"""Turn existing attendance totals into dated class periods, once."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import AttendanceRecord, AttendanceSession, TimetableSlot


def _clock(value: str) -> str:
    hour, minute = value.split(":")
    h = int(hour)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12:02d}.{minute} {suffix}"


def _class_dates(count: int, end: date = date(2026, 11, 6)) -> list[date]:
    found: list[date] = []
    cursor = end
    while len(found) < count:
        if cursor.weekday() != 6:
            found.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(found))


async def ensure_attendance_sessions() -> dict:
    created = 0
    async with SessionLocal() as db:
        records = (
            await db.execute(select(AttendanceRecord).options(selectinload(AttendanceRecord.enrollment)))
        ).scalars().all()
        slots = (await db.execute(select(TimetableSlot))).scalars().all()
        by_offering: dict[int, list[str]] = {}
        for slot in slots:
            by_offering.setdefault(slot.offering_id, []).append(f"{_clock(slot.start_time)} - {_clock(slot.end_time)}")
        have = set((await db.execute(select(AttendanceSession.enrollment_id).distinct())).scalars().all())
        for record in records:
            if record.total <= 0 or record.enrollment_id in have or not record.enrollment:
                continue
            names = by_offering.get(record.enrollment.offering_id) or [
                "08.00 AM - 08.50 AM",
                "05.00 PM - 05.50 PM",
            ]
            dates = _class_dates(record.total)
            present = min(record.attended, record.total)
            for index in range(record.total):
                db.add(
                    AttendanceSession(
                        enrollment_id=record.enrollment_id,
                        entry_date=dates[index],
                        slot_name=names[index % len(names)],
                        status="P" if index < present else "A",
                    )
                )
                created += 1
        await db.commit()
    return {"ok": True, "created": created}
