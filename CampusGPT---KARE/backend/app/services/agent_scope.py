"""Desk/agent topic scope: Reception answers broadly; Hostel stays hostel-only."""
from __future__ import annotations

import re

# Strong hostel / residential signals
_HOSTEL_TERMS = (
    "hostel",
    "warden",
    "mess",
    "boarding",
    "accommodation",
    "residential",
    "room allot",
    "room allocation",
    "room change",
    "room mate",
    "roommate",
    "hostel fee",
    "hostel fees",
    "hostel rule",
    "hostel leave",
    "night out",
    "outing pass",
    "gate pass",
    "hostel block",
    "boys hostel",
    "girls hostel",
    "pg hostel",
    "laundry",
    "hostel complaint",
    "hostel issue",
    "hostel facility",
    "hostel facilities",
    "bed number",
    "my room",
    "room number",
)

# Clear non-hostel campus topics (used to refuse on Hostel desk)
_OFF_HOSTEL_TERMS = (
    "timetable",
    "time table",
    "attendance",
    "internal mark",
    "marks",
    "grade",
    "cgpa",
    "sgpa",
    "exam",
    "semester fee",
    "tuition",
    "admission",
    "eligibility",
    "placement",
    "internship",
    "scholarship",
    "library",
    "faculty cabin",
    "office hours",
    "course registration",
    "revaluation",
    "arrear",
    "bus pass",
    "day scholar",
    "program",
    "programs",
    "b.tech",
    "btech",
    "m.tech",
    "mba",
    "which branch",
    "courses offered",
    "visiting hours",
    "examination branch",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def is_hostel_scoped_query(query: str) -> bool:
    """True when the question is about hostel / residential services."""
    q = _norm(query)
    if not q:
        return False
    if any(t in q for t in _HOSTEL_TERMS):
        return True
    # Short leave phrasing in hostel chat is usually hostel leave
    if re.search(r"\b(leave|outing|night out|gate pass)\b", q):
        return True
    if re.search(r"\b(room|block|mess|warden)\b", q):
        return True
    return False


def is_clearly_off_hostel(query: str) -> bool:
    q = _norm(query)
    if is_hostel_scoped_query(query):
        return False
    if any(t in q for t in _OFF_HOSTEL_TERMS):
        return True
    # Tuition / general fees without hostel context belong elsewhere
    if re.search(r"\b(fee|fees|payment|pay)\b", q) and "hostel" not in q:
        return True
    return False


def hostel_off_topic_reply() -> str:
    return (
        "This is the Hostel desk. I only help with hostel topics — rooms, blocks, mess, "
        "hostel fees, facilities, rules, leave/outing, complaints, and warden matters. "
        "For other campus questions (academics, admissions, fees, placements, directions), "
        "please switch to Reception (Front Desk) or Campus Guide."
    )


def agent_persona(agent_type: str) -> str:
    agents = {
        "admission": (
            "Admission Counselor — focused on admission procedures, eligibility, documents, "
            "program fees, deadlines, and enrollment."
        ),
        "reception": (
            "Reception / Front Desk — the main campus information desk for COMPLETE college-related "
            "information about KARE: campus identity and address, office hours, department contacts, "
            "walking directions, admissions overview, eligibility, documents, program catalogue, "
            "fee/scholarship overview, hostel overview, placements, library/labs/sports/medical/"
            "transport facilities, exam branch location, and which office to visit next. "
            "Answer every college-related question helpfully using the official campus fact sheet "
            "and knowledge base. Do not refuse campus topics. For deep personal SIS actions "
            "(apply leave, pay exact dues, detailed marks tables) give a clear summary and point "
            "the student to the matching Campus-GPT page or office."
        ),
        "hostel": (
            "Hostel Manager — ONLY hostel and residential topics: room availability/allocation, "
            "blocks, mess, hostel facilities, hostel fees, hostel rules, leave/outing, complaints "
            "to warden, and residential administration. If the question is not hostel-related, "
            "politely refuse and ask the student to use Reception or Campus Guide. Do not answer "
            "timetable, marks, attendance, admissions, or placement questions."
        ),
        "warden": (
            "Hostel Warden — ONLY hostel welfare topics: leave permissions, discipline, safety, "
            "hostel complaints, mess issues, and student residential welfare. Refuse non-hostel topics "
            "and redirect to Reception or Campus Guide."
        ),
        "academic": (
            "Academic Operations — timetable, attendance, internal marks, faculty availability, "
            "academic calendar, and study planning."
        ),
        "faculty": (
            "Faculty Desk — office hours, cabin, meeting slots, class load, and department notices."
        ),
        "general": (
            "General campus assistant for academics, timetable, attendance, marks, faculty, "
            "admissions, hostel, placements, and campus services."
        ),
    }
    return agents.get(agent_type or "general", agents["general"])


def should_enforce_hostel_only(agent_type: str) -> bool:
    return (agent_type or "").lower() in ("hostel", "warden")
