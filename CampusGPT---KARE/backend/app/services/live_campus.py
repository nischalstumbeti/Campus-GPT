"""Live university figures for forecast and chat. Counts and public titles only."""
from __future__ import annotations


def format_snapshot(snap: dict) -> str:
    if not snap:
        return ""
    course = snap.get("course_attendance") or {}
    overall = snap.get("student_overall_attendance") or {}
    today = snap.get("attendance_today") or {}
    fees = snap.get("fees") or {}
    by_status = fees.get("by_status") or {}
    notices = snap.get("notices") or []
    today_bits = ", ".join(f"{key} {value}" for key, value in today.items()) or "none recorded today"
    fee_bits = ", ".join(f"{key} {value}" for key, value in by_status.items()) or "none"
    notice_bits = "; ".join(str(title) for title in notices[:6]) or "none"
    return (
        f"Live university snapshot at {snap.get('counted_at') or 'unknown time'}. "
        f"Course attendance rows counted: {int(course.get('counted') or 0)}. "
        f"Below 70 percent: {int(course.get('below_70') or 0)}. "
        f"From 70 up to 75 percent: {int(course.get('watch_70_75') or 0)}. "
        f"At or above 75 percent: {int(course.get('at_or_above_75') or 0)}. "
        f"Student overall attendance rows above zero: {int(overall.get('counted') or 0)}. "
        f"Overall below 75 percent: {int(overall.get('below_75') or 0)}. "
        f"Overall at or above 75 percent: {int(overall.get('at_or_above_75') or 0)}. "
        f"Attendance marks posted today: {today_bits}. "
        f"Fee rows by status: {fee_bits}. "
        f"Unpaid fee balance: {fees.get('unpaid_balance', 0)}. "
        f"Latest public notices: {notice_bits}."
    )


async def live_records_text() -> str:
    from app.services.uis_client import get_campus_snapshot

    try:
        return format_snapshot(await get_campus_snapshot())
    except Exception:
        return ""
