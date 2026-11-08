"""Give the demo faculty the section A batch so mentoring still has a mapped advisor."""
from sqlalchemy import select

from app.database import SessionLocal
from app.models import FacultyAdvisor, FacultyProfile, User


async def ensure_advisors() -> dict:
    async with SessionLocal() as db:
        existing = (await db.execute(select(FacultyAdvisor.id).limit(1))).first()
        if existing:
            return {"ok": True, "created": 0}
        faculty = (
            await db.execute(
                select(FacultyProfile)
                .join(User, FacultyProfile.user_id == User.id)
                .where(User.username == "faculty.demo")
            )
        ).scalar_one_or_none()
        if not faculty:
            return {"ok": True, "created": 0}
        db.add(
            FacultyAdvisor(
                faculty_id=faculty.id,
                scope="section",
                section="A",
                batch="2024-28",
            )
        )
        await db.commit()
        return {"ok": True, "created": 1}
