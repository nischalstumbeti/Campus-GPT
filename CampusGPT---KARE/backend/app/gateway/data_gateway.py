"""
Secure Data Gateway — UIS-first.

Auth → role → intent → consent (UIS + local) → fetch authorized payload.
The LLM only receives this payload — never raw unauthorized records.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.intent import classify_intent, greeting_reply, permissions_for_intent, response_kind
from app.config import get_settings
from app.models.user import User
from app.services import consent as consents
from app.services import uis_academic as uis_acad
from app.services import uis_client
from app.services import academic_service as acad
from app.utils.table_format import (
    attendance_table,
    faculty_directory_table,
    marks_table,
    timetable_table,
)

DENIED_MESSAGE = "I can't provide that information because you don't have permission to access it."


@dataclass
class GatewayResult:
    intent: str
    text: str = ""
    denied: list[str] = field(default_factory=list)
    data_used: list[dict] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    kind: str = "knowledge"


def _uid(user: Optional[dict]) -> Optional[int]:
    if not user or not str(user.get("sub", "")).isdigit():
        return None
    return int(user["sub"])


def _used(data: str, purpose: str, permission: str, source: str = "UIS") -> dict:
    return {
        "data": data,
        "purpose": purpose,
        "source": source,
        "permission": permission,
        "access": "Authorized",
        "why": f"{data} was used because you asked about {purpose.lower()} and permission '{permission}' is allowed.",
    }


async def _uis_username(db: AsyncSession, user: Optional[dict]) -> Optional[str]:
    """Same identity rules as student_context / pages (requires student profile when resolving by email)."""
    if not user:
        return None
    from app.services.student_context import get_uis_username

    return await get_uis_username(db, user)


async def _local_faculty_rows(db: AsyncSession | None) -> list[dict]:
    if db is None:
        return []
    try:
        from app.models.academic import FacultyAvailability, FacultyProfile

        rows = (
            await db.execute(
                select(FacultyAvailability, FacultyProfile)
                .join(FacultyProfile, FacultyAvailability.faculty_id == FacultyProfile.id)
                .limit(60)
            )
        ).all()
        out = []
        for avail, fac in rows:
            out.append(
                {
                    "faculty": fac.full_name,
                    "kind": avail.kind or "availability",
                    "day": avail.day_of_week or "",
                    "start_time": avail.start_time or "",
                    "end_time": avail.end_time or "",
                    "location": avail.location or fac.cabin or "",
                }
            )
        return out
    except Exception:
        return []


async def _attach_campus_public(result: GatewayResult, query: str = "", db: AsyncSession | None = None) -> None:
    """Attach public campus data only when the user actually asked for it."""
    q = (query or "").lower()

    want_notices = any(
        k in q for k in ("announcement", "notice", "circular", "campus news", "university update", "official update")
    )
    if want_notices:
        notices = await uis_client.get_announcements(role="student")
        if notices:
            result.payload["announcements"] = notices[:8]
            result.data_used.append(_used("Announcements", "University updates", "public.announcements", "UIS"))
            lines = [f"- {n.get('title')}: {(n.get('body') or '')[:160]}" for n in notices[:6]]
            result.text = (result.text + "\n\n" if result.text else "") + "Official UIS announcements:\n" + "\n".join(lines)

    want_faculty = result.intent == "faculty_directory" or any(
        k in q
        for k in (
            "faculty",
            "office hour",
            "office hours",
            "professor",
            "cabin",
            "teaching schedule",
            "faculty timetable",
            "faculty schedule",
            "staff available",
        )
    )
    if want_faculty:
        # Prefer a name/keyword search only when the query has useful tokens
        search_q = q if len(q) > 3 and any(k in q for k in ("faculty", "professor", "dr", "prof")) else None
        fac = await uis_client.get_faculty(search_q)
        source = "UIS"
        if not fac and get_settings().ALLOW_LOCAL_SIS_FALLBACK:
            fac = await _local_faculty_rows(db)
            source = "Local SIS"
        if fac:
            result.payload["faculty_directory"] = fac[:40]
            result.data_used.append(_used("Faculty directory", "Office hours / teaching slots", "public.faculty", source))
            table = faculty_directory_table(fac[:40], title="Faculty schedule")
            result.text = table if result.intent == "faculty_directory" or "faculty" in q else (
                (result.text + "\n\n" if result.text else "") + table
            )


async def assemble(db: AsyncSession, user: Optional[dict], query: str) -> GatewayResult:
    intent = classify_intent(query)
    kind = response_kind(intent)
    uid = _uid(user)
    role = (user or {}).get("role") or "guest"
    keys = permissions_for_intent(intent)
    result = GatewayResult(intent=intent, kind=kind)

    # Greetings must never dump timetable / faculty tables
    if intent == "greeting":
        result.text = greeting_reply(user)
        return result

    # Public campus facts — only when asked (faculty directory / notices)
    if intent == "faculty_directory":
        await _attach_campus_public(result, query, db)
        if not result.text:
            result.text = "I could not load the faculty directory right now. Try again or open University notices."
        return result

    if intent == "knowledge" or not keys:
        qlow = (query or "").lower()
        personal = any(w in f" {qlow} " for w in (" my ", " mine ", " i am ", " i'm ", " me "))
        # Attach public data only if the knowledge question asks for it
        await _attach_campus_public(result, query, db)
        if not personal or uid is None:
            if not result.text:
                result.text = ""  # let RAG / demo FAQ answer general questions
            return result
        intent = "overview"
        result.intent = intent
        keys = permissions_for_intent(intent)
        kind = response_kind(intent)
        result.kind = kind

    if uid is None:
        result.denied = keys
        await _attach_campus_public(result, query, db)
        result.text = (
            (result.text + "\n\n" if result.text else "")
            + "Sign in and link your UIS account to use authorized personal records."
        ).strip()
        return result

    uis_user = await _uis_username(db, user) if role == "student" else None
    if role == "student" and uis_user:
        try:
            await consents.sync_from_uis(db, uid, uis_user)
        except Exception:
            pass

    # Master Campus-GPT assist consent — if denied, no personal records
    if role == "student" and not await consents.is_allowed(
        db, uid, "campus_gpt.assist", uis_username=uis_user
    ):
        result.denied = ["campus_gpt.assist"] + keys
        result.text = (
            "Campus-GPT assistance is turned off in your Consent settings. "
            "Enable Campus-GPT Consent (and the matching UIS permissions) to use personalized help. "
            "General campus FAQ still works without personal records."
        )
        return result

    allowed, denied = [], []
    for key in keys:
        if await consents.is_allowed(db, uid, key, uis_username=uis_user):
            allowed.append(key)
        else:
            denied.append(key)
    result.denied = denied

    # Specific intent with every required permission revoked/denied → hard stop
    if role == "student" and keys and not allowed and denied and intent not in ("knowledge", "greeting", "faculty_directory"):
        result.text = (
            "I can't help with that because consent is missing or revoked for: "
            + ", ".join(denied)
            + ". Open Campus-GPT Privacy or UIS → Consent, allow the needed permission, then ask again."
        )
        return result

    if role == "faculty":
        if intent == "faculty_directory" or "faculty" in (query or "").lower():
            await _attach_campus_public(result, query, db)
        else:
            result.text = (
                "Faculty Campus-GPT mode is ready. Ask about campus notices, draft circulars, "
                "or open KARE UIS for class roster, marks entry, leave approval, and complaints."
            )
        result.data_used.append(_used("Faculty role", "Scoped faculty assistance", "role.faculty", "Campus-GPT"))
        return result

    if role != "student":
        await _attach_campus_public(result, query, db)
        if denied and not allowed and not result.text:
            result.text = DENIED_MESSAGE
        elif not result.text:
            result.text = "Ask about campus notices, fees, or open the admin tools for management actions."
        return result

    use_uis = bool(uis_user and uis_client.uis_enabled())

    if not use_uis:
        student, _ = await acad.resolve_student(db, user)
        if not student:
            result.text = (
                "No UIS student link found for this login. "
                "Create the student in UIS with the same email, or set UIS username in Settings."
            )
            return result
        parts_local: list[str] = [
            f"Using local academic profile for {student.full_name} ({student.roll_no}). Link UIS for live SoR data."
        ]
        if any(k in allowed for k in ("academic.history", "academic.timetable")) and (
            intent in ("timetable", "overview", "letter")
            or any(k in (query or "").lower() for k in ("timetable", "time table", "class schedule", "today's class"))
        ):
            try:
                slots = await acad.get_timetable(db, student)
                parts_local.append(timetable_table(slots, title="Timetable (local)"))
                result.payload["timetable"] = slots
                result.data_used.append(_used("Timetable", "Class schedule", "academic.timetable", "Local SIS"))
            except Exception:
                pass
        if denied and not result.data_used:
            result.text = (
                "Consent is missing or revoked for: "
                + ", ".join(denied)
                + ". Allow these in Privacy / UIS Consent to use personal records."
            )
            return result
        result.text = "\n\n".join(parts_local)
        result.data_used.append(_used("Local profile", "Legacy local SIS", "academic.history", "Local SIS"))
        return result

    parts: list[str] = []
    linked = None
    header = ""
    if any(k in allowed for k in ("academic.credits", "academic.cgpa", "academic.history")):
        try:
            profile = await uis_client.get_profile(uis_user)
            linked = uis_acad.profile_to_student(profile, uis_user)
        except uis_client.UisConsentDenied:
            result.denied = list(set(result.denied + ["academic.credits"]))
            if not allowed:
                result.text = DENIED_MESSAGE
                return result
            linked = None
        except uis_client.UisClientError as exc:
            result.text = f"UIS is unavailable right now ({exc.detail or exc}). Try again shortly."
            return result

    if linked:
        header = (
            f"Authorized UIS record for {linked.full_name} ({linked.student_id}), "
            f"Year {linked.year} Sem {linked.semester} Sec {getattr(linked, 'section', '') or ''}. "
            f"Source: University Information System (mapped to Campus-GPT)."
        )
        result.payload["profile"] = uis_acad.serialize_linked(linked)

    want_overview = intent == "overview"

    if linked and any(k in allowed for k in ("academic.credits", "academic.cgpa")) and (
        want_overview
        or "academic.credits" in allowed
        or "academic.cgpa" in allowed
        or intent in ("credits", "graduation", "cgpa", "letter")
    ):
        grad = uis_acad.graduation_progress(linked)
        result.payload["graduation"] = grad
        parts.append(grad["summary"])
        result.data_used.append(_used("Credits / CGPA", "Graduation & credit progress", "academic.credits"))
        await consents.log_access(db, uid, "Credits / CGPA", "Graduation progress", "academic.credits")

    async def safe_get(perm: str, fetch):
        try:
            return await fetch()
        except uis_client.UisConsentDenied:
            result.denied.append(perm)
            return None
        except uis_client.UisClientError:
            return None

    if (want_overview or intent in ("attendance", "forecast")) and any(k in allowed for k in ("academic.attendance",)):
        raw = await safe_get("academic.attendance", lambda: uis_client.get_attendance(uis_user))
        if raw is not None:
            rows = uis_acad.normalize_attendance(raw)
            result.payload["attendance"] = rows
            parts.append(attendance_table(rows, title="Attendance"))
            if intent == "forecast" or "75" in (query or "").lower() or "how many" in (query or "").lower():
                fc = uis_acad.forecast_from_attendance(rows)
                result.payload["forecast"] = fc
                parts.append(fc["summary"])
                for d in fc["courses"]:
                    if d.get("classes_needed"):
                        parts.append(f"- {d['course']}: need ~{d['classes_needed']} more class(es) for 75% (risk: {d['risk']})")
            if intent == "attendance" and ("eligible" in (query or "").lower() or "exam" in (query or "").lower()):
                el = uis_acad.exam_eligibility(rows)
                result.payload["exam_eligibility"] = el
                parts.append(el["summary"])
            result.data_used.append(_used("Attendance", "Attendance / eligibility calculation", "academic.attendance"))
            await consents.log_access(db, uid, "Attendance", "Attendance calculation", "academic.attendance")

    if (want_overview or intent in ("marks", "grades", "cgpa", "forecast", "career")) and any(
        k in allowed for k in ("academic.marks", "academic.grades")
    ):
        raw = await safe_get("academic.marks", lambda: uis_client.get_marks(uis_user))
        if raw is not None:
            rows = uis_acad.normalize_marks(raw)
            result.payload["marks"] = rows
            parts.append(marks_table(rows, title="Marks"))
            result.data_used.append(_used("Marks", "Academic performance", "academic.marks"))
            await consents.log_access(db, uid, "Marks", "Academic performance", "academic.marks")
        grades = await safe_get("academic.grades", lambda: uis_client.get_grades(uis_user))
        if grades is not None:
            result.payload["grades"] = grades.get("grades") or []
            result.data_used.append(_used("Grades", "Grade explanation", "academic.grades"))

    if (want_overview or intent in ("timetable", "letter", "graduation", "credits", "career")) and any(
        k in allowed for k in ("academic.history", "academic.timetable", "academic.courses")
    ):
        raw = await safe_get("academic.timetable", lambda: uis_client.get_timetable(uis_user))
        slots: list[dict] = []
        if raw is not None:
            slots = uis_acad.normalize_timetable(raw)
        if not slots and db is not None and get_settings().ALLOW_LOCAL_SIS_FALLBACK:
            try:
                local_student, _ = await acad.resolve_student(db, user)
                if local_student:
                    slots = await acad.get_timetable(db, local_student)
                    if slots:
                        parts.append("(UIS had no slots — showing Campus-GPT local timetable.)")
            except Exception:
                pass
        if slots or raw is not None:
            result.payload["timetable"] = slots
            parts.append(timetable_table(slots, title="Timetable"))
            result.data_used.append(_used("Timetable", "Class schedule", "academic.timetable"))
            await consents.log_access(db, uid, "Timetable", "Class schedule", "academic.timetable")
        courses = await safe_get("academic.courses", lambda: uis_client.get_courses(uis_user))
        if courses is not None:
            result.payload["courses"] = courses.get("courses") or []
            result.data_used.append(_used("Courses", "Enrolled courses", "academic.courses"))

    if (want_overview or intent in ("leave", "hostel")) and any(
        k in allowed for k in ("hostel.room", "hostel.leave", "hostel.records")
    ):
        hostel = await safe_get("hostel.room", lambda: uis_client.get_hostel(uis_user))
        if hostel is not None:
            result.payload["hostel"] = hostel
            room = hostel.get("room")
            if room:
                parts.append(f"Hostel (UIS): {room.get('hostel')} Room {room.get('room')} Bed {room.get('bed')}")
            leaves = hostel.get("leaves") or []
            if leaves:
                parts.append(
                    "Leaves (UIS):\n"
                    + "\n".join(
                        [
                            f"- {l.get('from')} → {l.get('to')} · {l.get('status')} · {l.get('reason') or ''}"
                            for l in leaves
                        ]
                    )
                )
            result.data_used.append(_used("Hostel", "Hostel / leave assistance", "hostel.room"))
            await consents.log_access(db, uid, "Hostel", "Hostel assistance", "hostel.room")

    if (want_overview or intent == "complaints") and "hostel.records" in allowed:
        complaints = await safe_get("hostel.records", lambda: uis_client.get_complaints(uis_user))
        if complaints is not None:
            items = complaints.get("complaints") or []
            result.payload["complaints"] = items
            if items:
                parts.append(
                    "Complaints (UIS):\n"
                    + "\n".join(
                        [
                            f"- [{c.get('status')}] {c.get('category')}: {c.get('subject')}"
                            + (f" → {c.get('resolution_note')}" if c.get("resolution_note") else "")
                            for c in items[:10]
                        ]
                    )
                )
            else:
                parts.append("Complaints (UIS): none on file.")
            result.data_used.append(_used("Complaints", "Grievance status", "hostel.records"))

    if (want_overview or intent in ("achievements", "career")) and any(
        k in allowed for k in ("achievements.certs", "achievements.awards", "achievements.activities")
    ):
        ach = await safe_get("achievements.certs", lambda: uis_client.get_achievements(uis_user))
        if ach is not None:
            items = ach.get("achievements") or []
            result.payload["achievements"] = items
            parts.append(
                "Achievements (UIS):\n"
                + "\n".join([f"- [{a.get('category')}] {a.get('title')}" for a in items] or ["- none"])
            )
            result.data_used.append(_used("Achievements", "Career / profile assistance", "achievements.certs"))
            await consents.log_access(db, uid, "Achievements", "Career assistance", "achievements.certs")

    if (want_overview or intent in ("letter", "career", "forecast")) and "academic.exams" in allowed:
        exams = await safe_get("academic.exams", lambda: uis_client.get_exams(uis_user))
        if exams is not None:
            result.payload["exams"] = exams.get("exams") or []
            if result.payload["exams"]:
                exam_lines = [
                    f"- {e.get('course') or e.get('course_name')}: {e.get('type') or e.get('exam_type')} on {e.get('date')}"
                    for e in result.payload["exams"][:8]
                ]
                parts.append("Exams (UIS):\n" + "\n".join(exam_lines))
                result.data_used.append(_used("Exams", "Document / planning context", "academic.exams"))

    if intent in ("fees", "scholarship") and any(k in allowed for k in ("financial.fees", "financial.scholarship")):
        try:
            fees = await uis_client.get_student_fees(uis_user)
            items = fees.get("fees") or fees.get("items") or []
            result.payload["fees"] = items
            if items:
                lines = [
                    f"- {f.get('title') or f.get('category')}: due {f.get('remaining', f.get('total_amount'))} by {f.get('deadline') or 'n/a'} ({f.get('status')})"
                    for f in items[:12]
                ]
                parts.append("Fees (UIS):\n" + "\n".join(lines))
            else:
                parts.append("Fees (UIS): no open fee records.")
            result.data_used.append(_used("Fees", "Fee balance / deadlines", "financial.fees"))
            await consents.log_access(db, uid, "Fees", "Fee assistance", "financial.fees")
        except uis_client.UisConsentDenied:
            result.denied.append("financial.fees")
        except uis_client.UisClientError:
            parts.append("Fees (UIS): temporarily unavailable.")

    if want_overview or intent in ("knowledge", "overview", "timetable", "faculty_directory"):
        await _attach_campus_public(result, query, db)

    result.text = header + ("\n\n" + "\n\n".join([p for p in parts if p]) if parts else "")
    if denied and not parts:
        result.text = DENIED_MESSAGE
    elif denied:
        result.text += "\n\nSome categories were withheld (consent off): " + ", ".join(sorted(set(denied)))
    return result
