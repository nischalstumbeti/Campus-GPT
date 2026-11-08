"""Seed 100 fake students with login access + default Campus-GPT consents."""
from __future__ import annotations

from sqlalchemy import func, select

from app.models.user import User, Role
from app.models.academic import StudentProfile, Course, AttendanceSummary, MarksRecord
from app.models.privacy import HostelProfile, UserConsent
from app.security.permissions import ALL_KEYS, CATEGORIES
from app.utils.database import AsyncSessionLocal
from app.utils.seed_academic import _hash_password, DEMO_PASSWORD

FIRST = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Ananya", "Diya", "Myra", "Aadhya", "Pari", "Anika", "Navya", "Kiara", "Saanvi", "Ira",
]
LAST = [
    "Sharma", "Patel", "Reddy", "Nair", "Iyer", "Kumar", "Singh", "Das", "Mehta", "Gupta",
    "Rao", "Pillai", "Joshi", "Chopra", "Banerjee", "Verma", "Khan", "Mishra", "Shah", "Menon",
]
DEPTS = ["CSE", "ECE", "IT", "MECH", "CIVIL"]


def _purpose(key: str) -> str:
    for g in CATEGORIES.values():
        if key in g["keys"]:
            return g["purpose"]
    return "Personalized university assistance"


async def seed_bulk_students(target: int = 100) -> dict:
    """Create up to `target` fake student accounts (idempotent by count of bulk_* emails)."""
    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(
                select(func.count()).select_from(User).where(User.email.like("bulk.student%@kare.edu"))
            )
        ).scalar() or 0
        if existing >= target:
            return {"ok": True, "created": 0, "total_bulk": existing}

        courses = (await db.execute(select(Course).limit(8))).scalars().all()
        created = 0
        for i in range(existing + 1, target + 1):
            email = f"bulk.student{i:03d}@kare.edu"
            if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
                continue
            first = FIRST[(i - 1) % len(FIRST)]
            last = LAST[(i // len(FIRST)) % len(LAST)]
            dept = DEPTS[(i - 1) % len(DEPTS)]
            section = chr(ord("A") + ((i - 1) % 3))
            name = f"{first} {last}"
            user = User(
                email=email,
                hashed_password=_hash_password(DEMO_PASSWORD),
                full_name=name,
                role=Role.STUDENT,
                uis_username=f"bulk.student{i:03d}",
            )
            db.add(user)
            await db.flush()
            profile = StudentProfile(
                user_id=user.id,
                roll_no=f"BULK2024{dept}{i:03d}",
                full_name=name,
                program="B.Tech",
                department=dept,
                semester=5,
                section=section,
                batch="2024-28",
            )
            db.add(profile)
            await db.flush()

            # Default consents allow (student can revoke Campus-GPT Consent later)
            for key in ALL_KEYS:
                db.add(
                    UserConsent(
                        user_id=user.id,
                        permission_key=key,
                        status="allow",
                        purpose=_purpose(key),
                    )
                )

            # ~40% hostel
            if i % 5 < 2:
                db.add(
                    HostelProfile(
                        student_id=profile.id,
                        hostel="KARE Hostel Block " + ("A" if i % 2 else "B"),
                        block=section,
                        room=f"{section}-{100 + (i % 40)}",
                        mess="South Indian",
                    )
                )

            for j, c in enumerate(courses[:4]):
                db.add(
                    AttendanceSummary(
                        student_id=profile.id,
                        course_id=c.id,
                        conducted=40,
                        present=26 + ((i + j) % 12),
                        od=0,
                    )
                )
                db.add(
                    MarksRecord(
                        student_id=profile.id,
                        course_id=c.id,
                        assessment="CAT-1",
                        marks=28 + ((i + j) % 20),
                        max_marks=50,
                        recorded_on="2026-03-10",
                    )
                )
            created += 1

        await db.commit()
        total = (
            await db.execute(
                select(func.count()).select_from(User).where(User.email.like("bulk.student%@kare.edu"))
            )
        ).scalar() or 0
        return {"ok": True, "created": created, "total_bulk": total, "password": DEMO_PASSWORD}
