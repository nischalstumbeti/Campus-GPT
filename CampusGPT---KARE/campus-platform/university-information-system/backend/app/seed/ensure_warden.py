"""Ensure warden demo user + leave columns exist without wiping the UIS database."""
import asyncio
from datetime import date

from sqlalchemy import select, text

from app.database import SessionLocal, engine, Base
from app.models import HostelLeave, StudentProfile, User
from app.security.auth import hash_password


DEMO_PASSWORD = "campus123"


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        cols = await conn.run_sync(
            lambda c: {r[1] for r in c.execute(text("PRAGMA table_info(hostel_leaves)")).fetchall()}
        )
        if "destination" not in cols:
            await conn.execute(text("ALTER TABLE hostel_leaves ADD COLUMN destination VARCHAR(255) DEFAULT ''"))
        if "source" not in cols:
            await conn.execute(text("ALTER TABLE hostel_leaves ADD COLUMN source VARCHAR(32) DEFAULT 'uis'"))

    async with SessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.username == "warden.demo"))
        ).scalar_one_or_none()
        if not existing:
            db.add(
                User(
                    username="warden.demo",
                    email="warden.demo@klu.ac.in",
                    full_name="Hostel Warden",
                    hashed_password=hash_password(DEMO_PASSWORD),
                    role="hostel_admin",
                    department_code=None,
                )
            )
            print("Created warden.demo / campus123")
        else:
            print("warden.demo already exists")

        ananya = (
            await db.execute(select(StudentProfile).where(StudentProfile.student_id == "KARE2024CSE045"))
        ).scalar_one_or_none()
        if ananya:
            pending = (
                await db.execute(
                    select(HostelLeave).where(
                        HostelLeave.student_id == ananya.id,
                        HostelLeave.status == "pending",
                    )
                )
            ).scalar_one_or_none()
            if not pending:
                db.add(
                    HostelLeave(
                        student_id=ananya.id,
                        from_date=date(2026, 9, 20),
                        to_date=date(2026, 9, 22),
                        reason="Family function — pending warden approval",
                        status="pending",
                        destination="Chennai",
                        source="campus-gpt",
                    )
                )
                print("Added sample pending leave for Ananya")
        await db.commit()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
