"""Validate user prompts - reject unethical, abusive, or off-topic queries."""

# Phrases that indicate unethical/abusive/inappropriate prompts
BLOCKED_PATTERNS = [
    # Abusive/insulting (directed at the assistant — keep campus phrases like "not good" allowed)
    "you are bad", "you're bad", "you are stupid", "you're stupid", "you are dumb",
    "you're dumb", "you are useless", "you're useless", "you are worst", "you're worst",
    "you suck", "you stink", "stupid bot", "dumb bot", "useless bot", "worst bot",
    "stupid ai", "dumb ai", "hate you",
    # Jailbreak/Manipulation attempts
    "ignore previous", "ignore all", "forget your", "pretend you", "act as if",
    "you are now", "new instructions", "jailbreak",
    # Inappropriate content
    "how to hack", "how to cheat on exam", "write my exam", "leak the question paper",
    "question paper leak", "fake attendance", "bypass attendance", "impersonate a student",
]

# Minimum meaningful length
MIN_QUERY_LENGTH = 2

# Max length
MAX_QUERY_LENGTH = 2000


def is_valid_prompt(text: str) -> tuple[bool, str | None]:
    """
    Validate prompt. Returns (is_valid, error_message).
    If valid, error_message is None.
    """
    if not text or not isinstance(text, str):
        return False, "Please enter a valid question."

    t = text.strip().lower()

    if len(t) < MIN_QUERY_LENGTH:
        return False, "Please ask a meaningful question about campus academics, admissions, or facilities."

    if len(t) > MAX_QUERY_LENGTH:
        return False, "Your question is too long. Please shorten it."

    for pattern in BLOCKED_PATTERNS:
        if pattern in t:
            return False, "I can only help with institute matters — academics, timetable, attendance, marks, faculty, admissions, hostel, and campus services. Please ask accordingly."

    return True, None
