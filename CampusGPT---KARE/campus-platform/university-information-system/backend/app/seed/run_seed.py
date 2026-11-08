"""UIS demo seed. Run: python -m app.seed.run_seed

Rebuilds departments/programs/courses plus 10 students, faculty, HOD, admin,
shared CSE 5th-sem timetable, enrollments, attendance, marks, hostel, exams.
Campus-GPT must use the same emails so identity auto-links.
Password for every demo account: campus123
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from app.database import Base, SessionLocal, engine
from app.models import (
    Achievement,
    Announcement,
    AttendanceRecord,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    ExamSchedule,
    FacultyAvailability,
    FacultyProfile,
    Grade,
    Hostel,
    HostelAllocation,
    HostelBlock,
    HostelLeave,
    Mark,
    Program,
    Room,
    StudentProfile,
    TimetableSlot,
    User,
)
from app.routes.integration import ensure_student_consents
from app.security.auth import hash_password

DEMO_PASSWORD = "campus123"

# Same weekly grid Campus-GPT local SIS used — UIS is now the source of truth.
TIMETABLE = [
    (0, "09:00", "09:50", "CSE501", "LH-201"),
    (0, "10:00", "10:50", "CSE502", "LH-201"),
    (0, "11:10", "12:00", "CSE503", "LH-204"),
    (0, "14:00", "14:50", "CSE505", "LH-210"),
    (1, "09:00", "09:50", "CSE504", "LH-201"),
    (1, "10:00", "10:50", "CSE501", "LH-201"),
    (1, "11:10", "13:00", "CSE506", "Lab-CSE-2"),
    (1, "14:00", "14:50", "CSE502", "LH-201"),
    (2, "09:00", "09:50", "CSE503", "LH-204"),
    (2, "10:00", "10:50", "CSE505", "LH-210"),
    (2, "11:10", "12:00", "CSE504", "LH-201"),
    (2, "14:00", "15:50", "CSE507", "Lab-CSE-3"),
    (3, "09:00", "09:50", "CSE502", "LH-201"),
    (3, "10:00", "10:50", "CSE501", "LH-201"),
    (3, "11:10", "12:00", "CSE505", "LH-210"),
    (3, "14:00", "14:50", "CSE503", "LH-204"),
    (4, "09:00", "09:50", "CSE504", "LH-201"),
    (4, "10:00", "10:50", "CSE502", "LH-201"),
    (4, "11:10", "12:00", "CSE501", "LH-201"),
    (4, "14:00", "14:50", "CSE505", "Seminar Hall"),
]

COURSE_DEFS = [
    ("CSE501", "Database Management Systems", 4, "Dr. Priya Raman"),
    ("CSE502", "Computer Networks", 4, "Prof. Arun Kumar"),
    ("CSE503", "Theory of Computation", 3, "Dr. Meena Iyer"),
    ("CSE504", "Software Engineering", 3, "Prof. Suresh Babu"),
    ("CSE505", "Artificial Intelligence", 3, "Dr. Kavitha N"),
    ("CSE506", "DBMS Laboratory", 2, "Dr. Priya Raman"),
    ("CSE507", "Networks Laboratory", 2, "Prof. Arun Kumar"),
]

FACULTY = [
    ("faculty.demo", "faculty.demo@klu.ac.in", "Dr. Priya Raman", "FAC001", "Associate Professor", "CSE"),
    ("arun.kumar", "arun.kumar@klu.ac.in", "Prof. Arun Kumar", "FAC002", "Assistant Professor", "CSE"),
    ("meena.iyer", "meena.iyer@klu.ac.in", "Dr. Meena Iyer", "FAC003", "Professor", "CSE"),
    ("suresh.babu", "suresh.babu@klu.ac.in", "Prof. Suresh Babu", "FAC004", "Assistant Professor", "CSE"),
    ("kavitha.n", "kavitha.n@klu.ac.in", "Dr. Kavitha N", "FAC005", "Associate Professor", "CSE"),
    ("hod.demo", "hod.demo@klu.ac.in", "Dr. Ramesh Venkat", "FAC000", "Professor & Head", "CSE"),
]

STUDENTS = [
    # username, email, name, student_id, cgpa, attendance, credits, backlogs, hostel
    ("student.demo", "student.demo@klu.ac.in", "Ananya Krishnan", "KARE2024CSE045", 8.12, 88.9, 108, 0, True),
    ("rohan.mehta", "rohan.mehta@klu.ac.in", "Rohan Mehta", "KARE2024CSE012", 7.86, 82.4, 104, 0, True),
    ("priya.sharma", "priya.sharma@klu.ac.in", "Priya Sharma", "KARE2024CSE028", 9.04, 94.1, 112, 0, False),
    ("karthik.raj", "karthik.raj@klu.ac.in", "Karthik Raj", "KARE2024CSE033", 7.21, 76.8, 100, 1, True),
    ("divya.nair", "divya.nair@klu.ac.in", "Divya Nair", "KARE2024CSE041", 8.55, 91.2, 108, 0, True),
    ("arjun.patel", "arjun.patel@klu.ac.in", "Arjun Patel", "KARE2024CSE019", 6.94, 73.5, 96, 2, True),
    ("sneha.reddy", "sneha.reddy@klu.ac.in", "Sneha Reddy", "KARE2024CSE052", 8.78, 89.6, 108, 0, False),
    ("vishal.kumar", "vishal.kumar@klu.ac.in", "Vishal Kumar", "KARE2024CSE007", 7.48, 80.1, 104, 0, True),
    ("meera.iyer", "meera.iyer@klu.ac.in", "Meera Iyer", "KARE2024CSE061", 9.21, 96.4, 112, 0, False),
    ("aditya.singh", "aditya.singh@klu.ac.in", "Aditya Singh", "KARE2024CSE074", 7.65, 84.7, 104, 0, True),
]

BASE_ATTENDANCE = {
    "CSE501": (32, 29),
    "CSE502": (32, 24),
    "CSE503": (28, 26),
    "CSE504": (28, 25),
    "CSE505": (26, 22),
    "CSE506": (12, 12),
    "CSE507": (12, 10),
}

BASE_MARKS = {
    "CSE501": [("CAT-1", 42, 50), ("CAT-2", 38, 50), ("Assignment", 18, 20)],
    "CSE502": [("CAT-1", 35, 50), ("CAT-2", 31, 50), ("Assignment", 16, 20)],
    "CSE503": [("CAT-1", 44, 50), ("CAT-2", 40, 50)],
    "CSE504": [("CAT-1", 39, 50), ("CAT-2", 41, 50)],
    "CSE505": [("CAT-1", 36, 50), ("CAT-2", 33, 50)],
    "CSE506": [("Lab Internal", 42, 50)],
    "CSE507": [("Lab Internal", 38, 50)],
}


def _letter(pct: float) -> tuple[str, float]:
    if pct >= 90:
        return "O", 10.0
    if pct >= 80:
        return "A+", 9.0
    if pct >= 70:
        return "A", 8.0
    if pct >= 60:
        return "B+", 7.0
    if pct >= 50:
        return "B", 6.0
    return "C", 5.0


async def seed():
    from app.database import ensure_schema

    async with engine.begin() as conn:
        await ensure_schema(conn)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    hashed = hash_password(DEMO_PASSWORD)

    async with SessionLocal() as db:
        depts = [
            Department(code="CSE", name="Computer Science & Engineering"),
            Department(code="ECE", name="Electronics & Communication"),
            Department(code="ME", name="Mechanical Engineering"),
            Department(code="EEE", name="Electrical & Electronics"),
            Department(code="CIVIL", name="Civil Engineering"),
        ]
        db.add_all(depts)
        await db.flush()
        dept_by_code = {d.code: d for d in depts}

        programs = [
            Program(
                code=f"BTECH-{d.code}",
                name=f"B.Tech {d.name}",
                department_id=d.id,
                total_credits=160,
            )
            for d in depts
        ]
        db.add_all(programs)
        await db.flush()
        cse_program = next(p for p in programs if p.code == "BTECH-CSE")

        db.add(
            User(
                username="admin.demo",
                email="admin.demo@klu.ac.in",
                full_name="University Administrator",
                hashed_password=hashed,
                role="university_admin",
                department_code=None,
            )
        )
        db.add(
            User(
                username="warden.demo",
                email="warden.demo@klu.ac.in",
                full_name="Hostel Warden",
                hashed_password=hashed,
                role="hostel_admin",
                department_code=None,
            )
        )

        fac_profiles: dict[str, FacultyProfile] = {}
        for username, email, name, fid, designation, dept_code in FACULTY:
            role = "hod" if username == "hod.demo" else "faculty"
            user = User(
                username=username,
                email=email,
                full_name=name,
                hashed_password=hashed,
                role=role,
                department_code=dept_code,
            )
            db.add(user)
            await db.flush()
            profile = FacultyProfile(
                user_id=user.id,
                faculty_id=fid,
                designation=designation,
                department_id=dept_by_code[dept_code].id,
            )
            db.add(profile)
            await db.flush()
            fac_profiles[name] = profile

        OFFICE_HOURS = [
            ("Dr. Priya Raman", "Monday", "15:00", "16:00", "office_hours", "CSE-214", "Walk-in for DBMS doubts"),
            ("Dr. Priya Raman", "Wednesday", "16:00", "17:00", "office_hours", "CSE-214", "Project reviews"),
            ("Prof. Arun Kumar", "Tuesday", "15:00", "16:00", "office_hours", "CSE-118", "Networks / lab queries"),
            ("Prof. Arun Kumar", "Friday", "15:00", "16:00", "office_hours", "CSE-118", "Assignment discussion"),
            ("Dr. Meena Iyer", "Monday", "16:00", "17:00", "office_hours", "CSE-301", "By appointment"),
            ("Dr. Meena Iyer", "Thursday", "15:00", "16:00", "office_hours", "CSE-301", "TOC tutorials"),
            ("Prof. Suresh Babu", "Wednesday", "15:00", "16:00", "office_hours", "CSE-122", "SE mini-project"),
            ("Dr. Kavitha N", "Thursday", "16:00", "17:00", "office_hours", "CSE-220", "AI project mentoring"),
            ("Dr. Priya Raman", "Friday", "16:00", "17:00", "meeting", "HoD Conference Room", "Department faculty meeting"),
        ]
        db.add_all(
            [
                FacultyAvailability(
                    faculty_id=fac_profiles[name].id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    kind=kind,
                    location=loc,
                    notes=notes,
                )
                for name, day, start, end, kind, loc, notes in OFFICE_HOURS
            ]
        )

        courses: dict[str, Course] = {}
        offerings: dict[str, CourseOffering] = {}
        for code, title, credits, faculty_name in COURSE_DEFS:
            course = Course(code=code, title=title, credits=credits, department_id=dept_by_code["CSE"].id)
            db.add(course)
            await db.flush()
            courses[code] = course
            offering = CourseOffering(
                course_id=course.id,
                faculty_id=fac_profiles[faculty_name].id,
                semester=5,
                academic_year="2026-27",
                section="A",
            )
            db.add(offering)
            await db.flush()
            offerings[code] = offering

        for day, start, end, code, room in TIMETABLE:
            db.add(
                TimetableSlot(
                    offering_id=offerings[code].id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    room=room,
                )
            )

        hostel = Hostel(name="KARE Men's Hostel", gender="male")
        hostel_w = Hostel(name="KARE Women's Hostel", gender="female")
        db.add_all([hostel, hostel_w])
        await db.flush()
        block_m = HostelBlock(hostel_id=hostel.id, name="A-Block")
        block_w = HostelBlock(hostel_id=hostel_w.id, name="B-Block")
        db.add_all([block_m, block_w])
        await db.flush()
        rooms_m = [Room(block_id=block_m.id, room_number=f"A-{101 + i}", capacity=2) for i in range(5)]
        rooms_w = [Room(block_id=block_w.id, room_number=f"B-{201 + i}", capacity=2) for i in range(3)]
        db.add_all(rooms_m + rooms_w)
        await db.flush()

        women = {"Priya Sharma", "Divya Nair", "Sneha Reddy", "Meera Iyer", "Ananya Krishnan"}
        hostel_idx_m = 0
        hostel_idx_w = 0

        student_rows: list[tuple[User, StudentProfile]] = []
        for i, (username, email, name, sid, cgpa, att, credits, backlogs, in_hostel) in enumerate(STUDENTS):
            user = User(
                username=username,
                email=email,
                full_name=name,
                hashed_password=hashed,
                role="student",
                department_code="CSE",
            )
            db.add(user)
            await db.flush()
            sp = StudentProfile(
                user_id=user.id,
                student_id=sid,
                program_id=cse_program.id,
                batch="2024-28",
                year=3,
                semester=5,
                section="A",
                cgpa=cgpa,
                credits_completed=credits,
                credits_required=160,
                backlogs=backlogs,
                overall_attendance=att,
            )
            db.add(sp)
            await db.flush()
            student_rows.append((user, sp))

            for code, off in offerings.items():
                enr = Enrollment(student_id=sp.id, offering_id=off.id, status="active")
                db.add(enr)
                await db.flush()

                total, present = BASE_ATTENDANCE[code]
                drift = ((i % 5) - 2)
                present_i = max(0, min(total, present + drift))
                db.add(AttendanceRecord(enrollment_id=enr.id, attended=present_i, total=total))

                scores = []
                for assess, score, mx in BASE_MARKS[code]:
                    adj = max(0, min(mx, score + drift))
                    db.add(Mark(enrollment_id=enr.id, assessment=assess, score=adj, max_score=mx))
                    scores.append((adj, mx))
                if scores:
                    pct = 100.0 * sum(a for a, _ in scores) / sum(m for _, m in scores)
                    letter, gp = _letter(pct)
                    db.add(Grade(enrollment_id=enr.id, letter=letter, grade_point=gp))

            if in_hostel:
                if name in women:
                    room = rooms_w[hostel_idx_w % len(rooms_w)]
                    hostel_idx_w += 1
                else:
                    room = rooms_m[hostel_idx_m % len(rooms_m)]
                    hostel_idx_m += 1
                db.add(
                    HostelAllocation(
                        student_id=sp.id,
                        room_id=room.id,
                        bed_no="A" if i % 2 == 0 else "B",
                        status="active",
                    )
                )

            await ensure_student_consents(db, user.id, "allow")

        # Sample hostel leave + achievements for the primary demo student
        ananya = student_rows[0][1]
        db.add(
            HostelLeave(
                student_id=ananya.id,
                from_date=date(2026, 10, 1),
                to_date=date(2026, 10, 3),
                reason="Festival at hometown (Gandhi Jayanthi weekend)",
                status="approved",
                destination="Madurai",
                source="uis",
            )
        )
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
        db.add_all(
            [
                Achievement(
                    student_id=ananya.id,
                    title="Smart India Hackathon — Finalist",
                    category="technical",
                    awarded_on=date(2026, 4, 12),
                    description="National-level hardware track finalist with DBMS-backed campus app.",
                ),
                Achievement(
                    student_id=student_rows[2][1].id,
                    title="Department merit scholarship",
                    category="academic",
                    awarded_on=date(2026, 6, 1),
                    description="CGPA above 9.0 for two consecutive semesters.",
                ),
            ]
        )

        today = date(2026, 9, 15)
        db.add_all(
            [
                ExamSchedule(
                    course_id=courses["CSE501"].id,
                    exam_type="CAT-1",
                    exam_date=today,
                    start_time="09:30",
                    venue="LH-201",
                    semester=5,
                ),
                ExamSchedule(
                    course_id=courses["CSE502"].id,
                    exam_type="CAT-1",
                    exam_date=today + timedelta(days=1),
                    start_time="09:30",
                    venue="LH-201",
                    semester=5,
                ),
                ExamSchedule(
                    course_id=courses["CSE503"].id,
                    exam_type="CAT-1",
                    exam_date=today + timedelta(days=2),
                    start_time="09:30",
                    venue="LH-204",
                    semester=5,
                ),
                ExamSchedule(
                    course_id=courses["CSE505"].id,
                    exam_type="End Semester",
                    exam_date=date(2026, 12, 10),
                    start_time="10:00",
                    venue="Exam Hall 2",
                    semester=5,
                ),
            ]
        )

        db.add_all(
            [
                Announcement(
                    title="Odd semester classes in progress",
                    body="CSE 5th semester instructional period continues through 28 Nov 2026. Check your timetable in UIS or Campus-GPT.",
                    audience="all",
                    department_code="CSE",
                ),
                Announcement(
                    title="CAT-1 examinations",
                    body="CAT-1 for UG programmes: 15–19 Sep 2026. Hall tickets are available in the student portal.",
                    audience="student",
                    department_code=None,
                ),
                Announcement(
                    title="Faculty meeting — Friday",
                    body="Department faculty meeting every Friday 4:00–5:00 PM, HoD Conference Room.",
                    audience="faculty",
                    department_code="CSE",
                ),
            ]
        )

        await db.commit()

    print("Seed complete.")
    print("Password for all demo accounts: campus123")
    print("UIS login (username):")
    print("  student.demo   Ananya Krishnan   KARE2024CSE045")
    for row in STUDENTS[1:]:
        print(f"  {row[0]:<14} {row[2]:<18} {row[3]}")
    print("  faculty.demo   Dr. Priya Raman")
    print("  hod.demo       Dr. Ramesh Venkat")
    print("  warden.demo    Hostel Warden (approve leaves)")
    print("  admin.demo     University Administrator")
    print("Campus-GPT login uses the same emails, e.g. student.demo@klu.ac.in")


if __name__ == "__main__":
    asyncio.run(seed())
