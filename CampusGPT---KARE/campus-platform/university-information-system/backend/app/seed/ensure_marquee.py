"""Ensure default admin marquee items exist (idempotent)."""
from sqlalchemy import select

from app.database import SessionLocal
from app.models import MarqueeItem


async def ensure_marquee() -> dict:
    async with SessionLocal() as db:
        existing = (await db.execute(select(MarqueeItem).limit(1))).scalar_one_or_none()
        if existing:
            count = len((await db.execute(select(MarqueeItem))).scalars().all())
            return {"ok": True, "created": False, "items": count}

        defaults = [
            ("📢", "Welcome to KARE UIS admin — manage campus notices from this marquee CMS.", 0),
            ("🎓", "Fee deadlines and student messages sync with Campus-GPT.", 1),
            ("⚠️", "Keep this ticker updated for admin-only operational alerts.", 2),
        ]
        for icon, description, order in defaults:
            db.add(
                MarqueeItem(
                    icon=icon,
                    description=description,
                    active=True,
                    sort_order=order,
                    updated_by="system",
                )
            )
        await db.commit()
        return {"ok": True, "created": True, "items": len(defaults)}
