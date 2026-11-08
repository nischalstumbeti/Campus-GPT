"""Create the hall ticket design row. It stays closed until an admin enables it."""
from sqlalchemy import select

from app.database import SessionLocal
from app.models import HallTicketSettings


async def ensure_hall_ticket() -> dict:
    async with SessionLocal() as db:
        row = (await db.execute(select(HallTicketSettings))).scalars().first()
        if row:
            return {"ok": True, "created": False}
        db.add(
            HallTicketSettings(
                enabled=False,
                institution="Campus Information System",
                title="Hall Ticket",
                session_name="CAT-1 and End Semester Examination",
                instructions=(
                    "Bring this hall ticket and your identity card to every examination.\n"
                    "Be seated 15 minutes before the start time.\n"
                    "Electronic devices are not allowed inside the hall."
                ),
                footer="Generated from the examination schedule. Valid only while hall ticket download is enabled.",
            )
        )
        await db.commit()
    return {"ok": True, "created": True}
