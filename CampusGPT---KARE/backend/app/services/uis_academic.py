"""UIS-backed personal intelligence: normalize payloads + numerical calculations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.services import uis_client


@dataclass
class LinkedStudent:
    uis_username: str
    student_id: str
    full_name: str
    year: int
    semester: int
    cgpa: float
    credits_completed: int
    credits_required: int
    overall_attendance: float
    backlogs: int
    program: str = "B.Tech"
    department: str = "CSE"
    section: str = "A"
    batch: str = ""

    @property
    def roll_no(self) -> str:
        return self.student_id


def profile_to_student(profile: dict, uis_username: str) -> LinkedStudent:
    return LinkedStudent(
        uis_username=uis_username,
        student_id=str(profile.get("student_id") or ""),
        full_name=str(profile.get("name") or ""),
        year=int(profile.get("year") or 1),
        semester=int(profile.get("semester") or 1),
        cgpa=float(profile.get("cgpa") or 0),
        credits_completed=int(profile.get("credits_completed") or 0),
        credits_required=int(profile.get("credits_required") or 160),
        overall_attendance=float(profile.get("overall_attendance") or 0),
        backlogs=int(profile.get("backlogs") or 0),
        program=str(profile.get("program") or "B.Tech"),
        department=str(profile.get("department") or "CSE"),
        section=str(profile.get("section") or "A"),
        batch=str(profile.get("batch") or ""),
    )


def serialize_linked(s: LinkedStudent) -> dict:
    return {
        "roll_no": s.roll_no,
        "full_name": s.full_name,
        "program": s.program,
        "department": s.department,
        "semester": s.semester,
        "section": s.section,
        "batch": s.batch,
        "year": s.year,
        "cgpa": s.cgpa,
        "credits_completed": s.credits_completed,
        "credits_required": s.credits_required,
        "overall_attendance": s.overall_attendance,
        "backlogs": s.backlogs,
        "source": "UIS",
    }


def normalize_attendance(payload: dict) -> list[dict]:
    rows = []
    for a in payload.get("attendance") or []:
        attended = int(a.get("attended") or 0)
        total = int(a.get("total") or 0)
        pct = float(a.get("percentage") or (round(100 * attended / total, 1) if total else 0))
        rows.append(
            {
                "course_code": a.get("code") or "",
                "course_name": a.get("course") or "",
                "present": attended,
                "conducted": total,
                "percentage": pct,
            }
        )
    return rows


def normalize_marks(payload: dict) -> list[dict]:
    return [
        {
            "course_code": m.get("code") or "",
            "course_name": m.get("course") or "",
            "assessment": m.get("assessment") or "",
            "score": m.get("score"),
            "max_score": m.get("max_score"),
            "percentage": round(100 * float(m["score"]) / float(m["max_score"]), 1)
            if m.get("max_score")
            else None,
        }
        for m in payload.get("marks") or []
    ]


def _normalize_day(day: str) -> str:
    raw = (day or "").strip()
    if not raw:
        return ""
    day_map = {
        "mon": "Monday",
        "monday": "Monday",
        "tue": "Tuesday",
        "tues": "Tuesday",
        "tuesday": "Tuesday",
        "wed": "Wednesday",
        "wednesday": "Wednesday",
        "thu": "Thursday",
        "thur": "Thursday",
        "thurs": "Thursday",
        "thursday": "Thursday",
        "fri": "Friday",
        "friday": "Friday",
        "sat": "Saturday",
        "saturday": "Saturday",
        "sun": "Sunday",
        "sunday": "Sunday",
        "0": "Monday",
        "1": "Tuesday",
        "2": "Wednesday",
        "3": "Thursday",
        "4": "Friday",
        "5": "Saturday",
        "6": "Sunday",
    }
    return day_map.get(raw.lower(), raw)


def _normalize_time(value: str) -> str:
    t = (value or "").strip()
    if not t:
        return ""
    # HH:MM:SS → HH:MM for stable grid matching
    parts = t.split(":")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    return t


def normalize_timetable(payload: dict) -> list[dict]:
    out = []
    for sl in payload.get("slots") or []:
        day = _normalize_day(str(sl.get("day") or ""))
        start = _normalize_time(str(sl.get("start_time") or sl.get("start") or ""))
        end = _normalize_time(str(sl.get("end_time") or sl.get("end") or ""))
        if not day and not start and not (sl.get("course_code") or sl.get("code")):
            continue
        out.append(
            {
                "day": day,
                "start_time": start,
                "end_time": end,
                "course_code": sl.get("course_code") or sl.get("code") or "",
                "course_name": sl.get("course_name") or sl.get("course") or "",
                "faculty": sl.get("faculty") or "",
                "room": sl.get("room") or "",
                "section": sl.get("section") or "",
            }
        )
    out.sort(key=lambda r: (["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(r["day"]) if r["day"] in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday") else 99, r["start_time"]))
    return out


def classes_needed_for_75(attended: int, total: int, target: float = 75.0) -> dict[str, Any]:
    """Backend calculation — LLM only explains the result."""
    if total <= 0:
        return {"current": 0.0, "needed": 0, "possible": True, "message": "No classes recorded yet."}
    current = 100.0 * attended / total
    if current >= target:
        return {
            "current": round(current, 1),
            "needed": 0,
            "possible": True,
            "message": f"Already at {round(current, 1)}% (target {target}%).",
        }
    # Find smallest n such that (attended+n)/(total+n)*100 >= target
    n = 0
    while n < 500:
        if 100.0 * (attended + n) / (total + n) >= target:
            return {
                "current": round(current, 1),
                "needed": n,
                "possible": True,
                "message": f"Attend the next {n} class(es) without absence to reach {target}%.",
            }
        n += 1
    return {"current": round(current, 1), "needed": None, "possible": False, "message": "Target may not be reachable soon."}


def exam_eligibility(attendance_rows: list[dict], threshold: float = 75.0) -> dict[str, Any]:
    short = [r for r in attendance_rows if float(r.get("percentage") or 0) < threshold]
    return {
        "eligible": len(short) == 0,
        "threshold": threshold,
        "shortage_courses": short,
        "summary": (
            "You meet the minimum attendance threshold across recorded courses."
            if not short
            else f"{len(short)} course(s) are below {threshold}% — confirm exam eligibility with the department."
        ),
    }


def forecast_from_attendance(rows: list[dict]) -> dict[str, Any]:
    details = []
    for r in rows:
        calc = classes_needed_for_75(int(r.get("present") or 0), int(r.get("conducted") or 0))
        details.append(
            {
                "course": r.get("course_name") or r.get("course_code"),
                "percentage": r.get("percentage"),
                "classes_needed": calc["needed"],
                "risk": "High" if float(r.get("percentage") or 0) < 70 else ("Watch" if float(r.get("percentage") or 0) < 75 else "OK"),
            }
        )
    avg = round(sum(float(r.get("percentage") or 0) for r in rows) / len(rows), 1) if rows else 0
    return {
        "average_attendance": avg,
        "courses": details,
        "summary": f"Overall attendance snapshot: {avg}%. Use course-wise 'classes needed' to plan.",
    }


def graduation_progress(profile: LinkedStudent) -> dict[str, Any]:
    req = profile.credits_required or 160
    earned = profile.credits_completed or 0
    remaining = max(0, req - earned)
    return {
        "cgpa": profile.cgpa,
        "credits_completed": earned,
        "credits_required": req,
        "credits_remaining": remaining,
        "percent": round(100 * earned / req, 1) if req else 0,
        "backlogs": profile.backlogs,
        "summary": f"{earned}/{req} credits completed ({remaining} remaining). CGPA {profile.cgpa}. Backlogs: {profile.backlogs}.",
    }


async def load_linked_student(uis_username: str) -> Optional[LinkedStudent]:
    try:
        profile = await uis_client.get_profile(uis_username)
        return profile_to_student(profile, uis_username)
    except uis_client.UisConsentDenied:
        raise
    except uis_client.UisClientError:
        return None
