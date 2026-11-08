"""DEMO ENVIRONMENT copilot seed: example.com accounts, isolation student, notices."""
from sqlalchemy import select

from app.models.user import User, Role
from app.models.academic import (
    StudentProfile,
    FacultyProfile,
    Course,
    AttendanceSummary,
    MarksRecord,
    HostelLeave,
)
from app.models.privacy import Announcement, Achievement, HostelProfile, UserConsent
from app.models.fees import FeePlan, StudentFee
from app.security.permissions import ALL_KEYS, CATEGORIES
from app.utils.database import AsyncSessionLocal
from app.utils.seed_academic import _hash_password, DEMO_PASSWORD

EXAMPLE_STUDENT = "student@example.com"
EXAMPLE_FACULTY = "faculty@example.com"
EXAMPLE_ADMIN = "admin@example.com"


def _purpose(key: str) -> str:
    for g in CATEGORIES.values():
        if key in g["keys"]:
            return g["purpose"]
    return "Personalized university assistance"


async def seed_copilot_layer() -> None:
    async with AsyncSessionLocal() as db:
        existing_admin = (await db.execute(select(User).where(User.email == EXAMPLE_ADMIN))).scalar_one_or_none()
        if not existing_admin:
            admin = User(
                email=EXAMPLE_ADMIN,
                hashed_password=_hash_password(DEMO_PASSWORD),
                full_name="Campus Admin (DEMO)",
                role=Role.ADMIN,
                uis_username="admin.demo",
            )
            db.add(admin)
        elif not existing_admin.uis_username:
            existing_admin.uis_username = "admin.demo"

        fac_user = (await db.execute(select(User).where(User.email == EXAMPLE_FACULTY))).scalar_one_or_none()
        arun = (await db.execute(select(FacultyProfile).where(FacultyProfile.employee_id == "KARE-FAC-1044"))).scalar_one_or_none()
        if not fac_user:
            fac_user = User(
                email=EXAMPLE_FACULTY,
                hashed_password=_hash_password(DEMO_PASSWORD),
                full_name="Prof. Arun Kumar",
                role=Role.FACULTY,
                uis_username="arun.kumar",
            )
            db.add(fac_user)
            await db.flush()
            if arun and not arun.user_id:
                arun.user_id = fac_user.id
        elif not fac_user.uis_username:
            fac_user.uis_username = "arun.kumar"

        stu_user = (await db.execute(select(User).where(User.email == EXAMPLE_STUDENT))).scalar_one_or_none()
        profile = (await db.execute(select(StudentProfile).where(StudentProfile.roll_no == "DEMO2024CSE099"))).scalar_one_or_none()
        if not stu_user:
            stu_user = User(
                email=EXAMPLE_STUDENT,
                hashed_password=_hash_password(DEMO_PASSWORD),
                full_name="Ravi Menon",
                role=Role.STUDENT,
                uis_username="student.demo",
            )
            db.add(stu_user)
            await db.flush()
        elif not stu_user.uis_username:
            stu_user.uis_username = "student.demo"
        if not profile:
            profile = StudentProfile(
                user_id=stu_user.id,
                roll_no="DEMO2024CSE099",
                full_name="Ravi Menon",
                program="B.Tech",
                department="CSE",
                semester=5,
                section="A",
                batch="2024-28",
            )
            db.add(profile)
            await db.flush()
            courses = (await db.execute(select(Course))).scalars().all()
            for i, c in enumerate(courses[:6]):
                db.add(
                    AttendanceSummary(
                        student_id=profile.id,
                        course_id=c.id,
                        conducted=40,
                        present=28 + i,
                        od=1,
                    )
                )
                db.add(
                    MarksRecord(
                        student_id=profile.id,
                        course_id=c.id,
                        assessment="CAT-1",
                        marks=30 + i,
                        max_marks=50,
                        recorded_on="2026-03-10",
                    )
                )
            db.add(
                HostelLeave(
                    student_id=profile.id,
                    from_date="2026-09-12",
                    to_date="2026-09-14",
                    reason="Family function (DEMO)",
                    destination="Coimbatore",
                    status="pending",
                )
            )
            db.add(
                HostelProfile(
                    student_id=profile.id,
                    hostel="KARE Men's Hostel (DEMO)",
                    block="C",
                    room="C-214",
                    mess="South Indian",
                )
            )
            db.add_all(
                [
                    Achievement(student_id=profile.id, kind="cert", title="AWS Cloud Practitioner (demo)", year="2026"),
                    Achievement(student_id=profile.id, kind="activity", title="College hackathon finalist (demo)", year="2026"),
                ]
            )

        # Consents for all users (allow by default in DEMO)
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            have = set(
                (await db.execute(select(UserConsent.permission_key).where(UserConsent.user_id == u.id))).scalars().all()
            )
            for key in ALL_KEYS:
                if key not in have:
                    db.add(UserConsent(user_id=u.id, permission_key=key, status="allow", purpose=_purpose(key)))

        notice_exists = (await db.execute(select(Announcement).limit(1))).scalar_one_or_none()
        if not notice_exists:
            db.add_all(
                [
                    Announcement(
                        title="Exam registration window",
                        body="End-semester exam registration closes 10 Sep 2026. Use the official examination portal only.",
                        category="examination",
                        audience="student",
                        department="CSE",
                        effective_date="2026-09-01",
                        source="Controller of Examinations — circular (DEMO)",
                        important=1,
                    ),
                    Announcement(
                        title="Hostel return timing",
                        body="Weekday return by 8:30 PM unless approved leave is on file. Verify with the warden office.",
                        category="hostel",
                        audience="student",
                        effective_date="2026-07-14",
                        source="Hostel Office rules (DEMO)",
                        important=0,
                    ),
                    Announcement(
                        title="Faculty meeting — Friday 4 PM",
                        body="Department meeting in HoD conference room. Recurring weekly.",
                        category="department",
                        audience="faculty",
                        department="CSE",
                        effective_date="2026-08-28",
                        source="CSE department notice (DEMO)",
                        important=1,
                    ),
                ]
            )

        # Hostel + achievements for legacy demo student if missing
        ananya = (await db.execute(select(StudentProfile).where(StudentProfile.roll_no == "KARE2024CSE045"))).scalar_one_or_none()
        if ananya:
            hp = (await db.execute(select(HostelProfile).where(HostelProfile.student_id == ananya.id))).scalar_one_or_none()
            if not hp:
                db.add(HostelProfile(student_id=ananya.id, hostel="KARE Women's Hostel (DEMO)", block="A", room="A-112", mess="South Indian veg"))
            ach = (await db.execute(select(Achievement).where(Achievement.student_id == ananya.id).limit(1))).scalar_one_or_none()
            if not ach:
                db.add(Achievement(student_id=ananya.id, kind="award", title="Department merit certificate (DEMO)", year="2026"))

        # Mock fee plans + student dues (hostel / day scholar / bus)
        fee_exists = (await db.execute(select(FeePlan).limit(1))).scalar_one_or_none()
        if not fee_exists:
            hostel_plan = FeePlan(
                title="Hostel semester fee (DEMO)",
                category="hostel",
                amount=55000,
                deadline="2026-10-20",
                notes="Includes room + mess",
            )
            day_plan = FeePlan(
                title="Day scholar tuition (DEMO)",
                category="day_scholar",
                amount=42000,
                deadline="2026-10-25",
                notes="Tuition installment window",
            )
            bus_plan = FeePlan(
                title="Bus transport fee (DEMO)",
                category="bus",
                amount=12000,
                deadline="2026-10-15",
                notes="Transport for bus route students",
            )
            db.add_all([hostel_plan, day_plan, bus_plan])
            await db.flush()

            students = (await db.execute(select(User).where(User.role == Role.STUDENT))).scalars().all()
            for s in students:
                profile = (
                    await db.execute(select(StudentProfile).where(StudentProfile.user_id == s.id))
                ).scalar_one_or_none()
                is_hostel = False
                if profile:
                    hp = (
                        await db.execute(select(HostelProfile).where(HostelProfile.student_id == profile.id))
                    ).scalar_one_or_none()
                    is_hostel = bool(hp)
                if is_hostel:
                    db.add(
                        StudentFee(
                            user_id=s.id,
                            plan_id=hostel_plan.id,
                            title=hostel_plan.title,
                            category="hostel",
                            total_amount=hostel_plan.amount,
                            paid_amount=0,
                            deadline=hostel_plan.deadline,
                            status="due",
                            editable_splits=3,
                        )
                    )
                else:
                    db.add(
                        StudentFee(
                            user_id=s.id,
                            plan_id=day_plan.id,
                            title=day_plan.title,
                            category="day_scholar",
                            total_amount=day_plan.amount,
                            paid_amount=0,
                            deadline=day_plan.deadline,
                            status="due",
                            editable_splits=3,
                        )
                    )
                # Assign bus fee to every other student as demo split category
                if s.id % 2 == 0:
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
                            editable_splits=2,
                        )
                    )

        await db.commit()
