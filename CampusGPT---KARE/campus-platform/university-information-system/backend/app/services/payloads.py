"""Shared JSON shapes so UIS portal and Campus-GPT integration return the same values."""

from typing import Any, Optional

from app.models import FacultyProfile

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def faculty_name(fac: Optional[FacultyProfile]) -> str:
    if not fac:
        return ""
    if fac.user and fac.user.full_name:
        return fac.user.full_name
    return ""


def serialize_timetable_slot(sl) -> dict[str, Any]:
    course = sl.offering.course if sl.offering else None
    offering = sl.offering
    title = course.title if course else ""
    code = course.code if course else ""
    return {
        "day": DAYS[sl.day_of_week] if 0 <= sl.day_of_week < 7 else str(sl.day_of_week),
        "start": sl.start_time,
        "end": sl.end_time,
        "start_time": sl.start_time,
        "end_time": sl.end_time,
        "room": sl.room,
        "course": title,
        "course_name": title,
        "code": code,
        "course_code": code,
        "faculty": faculty_name(offering.faculty if offering else None),
        "section": offering.section if offering else "",
    }
