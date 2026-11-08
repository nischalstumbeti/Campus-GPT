"""Long-term memory for a user across chat discussions."""
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import UserMemory

_TRIGGERS = (
    "remember",
    "i prefer",
    "i like",
    "i am ",
    "i'm ",
    "im ",
    "i stay",
    "i live",
    "i study",
    "i struggle",
    "i need",
    "my hostel",
    "my branch",
    "my weak",
    "weak in",
    "i belong",
    "i'm from",
    "im from",
    "i have cat",
    "i have exam",
)

_SKIP = re.compile(r"\b(password|otp|aadhaar|aadhar|bank|pin)\b", re.I)


def extract_memory_facts(text: str) -> list[str]:
    raw = (text or "").strip()
    if len(raw) < 12 or raw.endswith("?") or _SKIP.search(raw):
        return []
    lower = raw.lower()
    if not any(t in lower for t in _TRIGGERS):
        return []
    fact = re.sub(r"\s+", " ", raw)[:280].strip()
    return [fact] if fact else []


async def load_memory_facts(db: AsyncSession, user_id: int, limit: int = 20) -> list[UserMemory]:
    result = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def load_memory_text(db: AsyncSession, user_id: int) -> str:
    rows = await load_memory_facts(db, user_id)
    if not rows:
        return ""
    lines = [f"- {r.fact}" for r in reversed(rows)]
    return "Long-term memory about this user (use across all chats):\n" + "\n".join(lines)


async def save_memory_facts(
    db: AsyncSession,
    user_id: int,
    facts: list[str],
    source_session_id: str | None = None,
) -> None:
    if not facts:
        return
    existing = await db.execute(select(UserMemory.fact).where(UserMemory.user_id == user_id))
    seen = { (f or "").strip().lower() for f in existing.scalars().all() }
    for fact in facts:
        key = fact.strip().lower()
        if not key or key in seen:
            continue
        db.add(UserMemory(user_id=user_id, fact=fact.strip(), source_session_id=source_session_id))
        seen.add(key)

    all_rows = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.created_at.desc())
    )
    rows = list(all_rows.scalars().all())
    extra = rows[30:]
    for row in extra:
        await db.delete(row)
