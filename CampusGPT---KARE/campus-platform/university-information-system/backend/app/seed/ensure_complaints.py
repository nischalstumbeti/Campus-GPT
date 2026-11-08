"""Create sample complaints if the table is empty (no full reseed)."""
import asyncio

from sqlalchemy import func, select

from app.database import Base, SessionLocal, engine
from app.models import Complaint, StudentProfile


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(Complaint))).scalar() or 0
        if count:
            print(f"complaints already present: {count}")
            return
        ananya = (
            await db.execute(select(StudentProfile).where(StudentProfile.student_id == "KARE2024CSE045"))
        ).scalar_one_or_none()
        if not ananya:
            print("No demo student found")
            return
        db.add_all(
            [
                Complaint(
                    student_id=ananya.id,
                    category="hostel",
                    audience="hostel",
                    subject="Water leakage in bathroom",
                    description="Continuous drip from ceiling near washbasin in Block A.",
                    status="open",
                ),
                Complaint(
                    student_id=ananya.id,
                    category="academic",
                    audience="faculty",
                    subject="CAT-1 marks not reflecting",
                    description="CSE502 CAT-1 score shown blank in portal though paper was evaluated.",
                    status="open",
                ),
                Complaint(
                    student_id=ananya.id,
                    category="general",
                    audience="any",
                    subject="Wi-Fi unstable in library",
                    description="Connection drops every few minutes during evening hours.",
                    status="open",
                ),
            ]
        )
        await db.commit()
        print("Seeded 3 sample complaints")


if __name__ == "__main__":
    asyncio.run(main())
