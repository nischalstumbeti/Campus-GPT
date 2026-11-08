"""Intent classification — rules first, not the LLM."""
from __future__ import annotations

import re

from app.security.permissions import INTENT_PERMISSIONS

_GREETING_EXACT = {
    "hi",
    "hii",
    "hiii",
    "hello",
    "hey",
    "yo",
    "sup",
    "namaste",
    "hola",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "hi there",
    "hello there",
    "hey there",
    "hai",
    "helo",
}

_GREETING_PREFIX = (
    "hi ",
    "hello ",
    "hey ",
    "good morning",
    "good afternoon",
    "good evening",
    "namaste ",
)


def is_greeting(query: str) -> bool:
    q = re.sub(r"[!?.,]+$", "", (query or "").strip().lower()).strip()
    if not q:
        return False
    if q in _GREETING_EXACT:
        return True
    if len(q) <= 24 and any(q.startswith(p) for p in _GREETING_PREFIX):
        # "hi how are you" still a greeting opener
        return True
    return False


_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("overview", ("my details", "my information", "everything about me", "full profile", "all my records", "complete information", "my academic life")),
    ("attendance", ("attendance", "absent", "present", "75%", "shortage", "how many classes")),
    ("marks", ("marks", "internal", "cat-1", "cat 1", "cat-2", "score in")),
    ("grades", ("grade", "grades", "cgpa if", "what if i get")),
    ("cgpa", ("cgpa", "gpa", "grade point")),
    ("credits", ("credit", "credits completed", "credits remaining")),
    ("graduation", ("graduation", "on track", "degree progress", "requirements remaining")),
    ("timetable", ("timetable", "time table", "today's class", "todays class", "what classes", "my class")),
    ("forecast", ("forecast", "can i miss", "reach 75", "predicted")),
    ("leave", ("hostel leave", "leave approved", "apply leave", "leave status", "my leave")),
    ("hostel", ("hostel", "room number", "mess", "warden", "return timing")),
    ("complaints", ("complaint", "complaints", "grievance", "ticket status")),
    ("faculty_directory", ("faculty availability", "office hours", "which faculty", "faculty cabin", "professor available", "faculty schedule", "faculty timetable", "teaching schedule")),
    ("fees", ("fee", "fees", "tuition")),
    ("scholarship", ("scholarship", "stipend")),
    ("achievements", ("achievement", "certificate", "award", "hackathon")),
    ("career", ("internship", "resume", "career", "job ready", "cover letter")),
    ("letter", ("draft a letter", "permission letter", "hod request", "bonafide", "write an email")),
    ("workflow", ("submit leave", "raise complaint", "apply for")),
    ("knowledge", ("regulation", "minimum attendance requirement", "revaluation", "university rule", "circular", "notice")),
]


def _key_match(q: str, key: str) -> bool:
    """Avoid short substring false positives (fee⊂feedback, grade⊂undergraduate)."""
    if len(key) <= 4:
        return bool(re.search(rf"(?<!\w){re.escape(key)}(?!\w)", q))
    return key in q


def classify_intent(query: str) -> str:
    if is_greeting(query):
        return "greeting"
    q = (query or "").lower()
    # Faculty schedule / faculty timetable is directory data, not student timetable
    if "faculty" in q and any(k in q for k in ("timetable", "schedule", "availability", "office hour")):
        return "faculty_directory"
    for intent, keys in _RULES:
        if any(_key_match(q, k) for k in keys):
            return intent
    return "knowledge"


def permissions_for_intent(intent: str) -> list[str]:
    return list(INTENT_PERMISSIONS.get(intent, []))


def response_kind(intent: str) -> str:
    if intent == "greeting":
        return "greeting"
    if intent in ("forecast", "cgpa", "attendance"):
        return "calculation"
    if intent in ("career", "letter"):
        return "recommendation"
    if intent == "knowledge":
        return "knowledge"
    return "fact"


def greeting_reply(user: dict | None = None) -> str:
    name = ""
    if user:
        name = str(user.get("full_name") or "").strip().split(" ")[0]
    hello = f"Hello{(' ' + name) if name else ''}!"
    return (
        f"{hello} I'm Campus-GPT for KARE.\n\n"
        "Ask me about your timetable, attendance, marks, hostel leave, fees, faculty office hours, "
        "or campus notices. I will use authorized UIS data when your account is linked.\n\n"
        'Examples: "What is my attendance?" | "Show my timetable" | "Apply for hostel leave"'
    )
