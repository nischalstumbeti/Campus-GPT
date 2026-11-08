"""Ensure demo fee plans + student dues exist in UIS (idempotent)."""
from sqlalchemy import select

from app.database import SessionLocal
from app.models import FeePlan, HostelAllocation, StudentFee, StudentProfile, User


async def ensure_fees() -> dict:
    async with SessionLocal() as db:
        hostel_plan = (
            await db.execute(select(FeePlan).where(FeePlan.category == "hostel").limit(1))
        ).scalar_one_or_none()
        day_plan = (
            await db.execute(select(FeePlan).where(FeePlan.category == "day_scholar").limit(1))
        ).scalar_one_or_none()
        bus_plan = (
            await db.execute(select(FeePlan).where(FeePlan.category == "bus").limit(1))
        ).scalar_one_or_none()

        created_plans = False
        if not hostel_plan or not day_plan or not bus_plan:
            if not hostel_plan:
                hostel_plan = FeePlan(
                    title="Hostel semester fee",
                    category="hostel",
                    amount=55000,
                    deadline="2026-10-20",
                    notes="Room + mess (UIS SoR)",
                )
                db.add(hostel_plan)
            if not day_plan:
                day_plan = FeePlan(
                    title="Day scholar tuition",
                    category="day_scholar",
                    amount=42000,
                    deadline="2026-10-25",
                    notes="Tuition (UIS SoR)",
                )
                db.add(day_plan)
            if not bus_plan:
                bus_plan = FeePlan(
                    title="Bus transport fee",
                    category="bus",
                    amount=12000,
                    deadline="2026-10-15",
                    notes="Transport (UIS SoR)",
                )
                db.add(bus_plan)
            await db.flush()
            created_plans = True

        students = (await db.execute(select(User).where(User.role == "student"))).scalars().all()
        assigned = 0
        for i, s in enumerate(students):
            existing = (
                await db.execute(select(StudentFee).where(StudentFee.user_id == s.id).limit(1))
            ).scalar_one_or_none()
            if existing:
                continue
            profile = (
                await db.execute(select(StudentProfile).where(StudentProfile.user_id == s.id))
            ).scalar_one_or_none()
            is_hostel = False
            if profile:
                alloc = (
                    await db.execute(select(HostelAllocation).where(HostelAllocation.student_id == profile.id))
                ).scalar_one_or_none()
                is_hostel = bool(alloc)
            plan = hostel_plan if is_hostel else day_plan
            cat = "hostel" if is_hostel else "day_scholar"
            db.add(
                StudentFee(
                    user_id=s.id,
                    plan_id=plan.id,
                    title=plan.title,
                    category=cat,
                    total_amount=plan.amount,
                    paid_amount=0,
                    deadline=plan.deadline,
                    status="due",
                )
            )
            assigned += 1
            if i % 2 == 0:
                db.add(
                    StudentFee(
                        user_id=s.id,
                        plan_id=bus_plan.id,
                        title=bus_plan.title,
                        category="bus",
                        total_amount=bus_plan.amount,
                        paid_amount=0,
                        deadline=bus_plan.deadline,
                        status="due",
                    )
                )
                assigned += 1
        await db.commit()
        count = len((await db.execute(select(StudentFee))).scalars().all())
        return {
            "ok": True,
            "created_plans": created_plans,
            "assigned_new": assigned,
            "student_fees": count,
        }
