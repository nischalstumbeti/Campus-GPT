"""Seed demo students, faculty, timetable, attendance, marks, and calendar."""
import bcrypt
from sqlalchemy import select

from app.models.user import User, Role
from app.models.academic import (
    StudentProfile,
    FacultyProfile,
    Course,
    TimetableSlot,
    FacultyAvailability,
    AttendanceSummary,
    MarksRecord,
    AcademicEvent,
    StudentTask,
    HostelLeave,
)
from app.utils.database import AsyncSessionLocal


DEMO_STUDENT_EMAIL = "student.demo@klu.ac.in"
DEMO_FACULTY_EMAIL = "faculty.demo@klu.ac.in"
DEMO_PASSWORD = "campus123"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


async def seed_academic_data() -> None:
    """Idempotent seed of academic records for campus operations."""
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Course).limit(1))
        if existing.scalar_one_or_none():
            return

        student_user = User(
            email=DEMO_STUDENT_EMAIL,
            hashed_password=_hash_password(DEMO_PASSWORD),
            full_name="Ananya Krishnan",
            role=Role.STUDENT,
        )
        faculty_user = User(
            email=DEMO_FACULTY_EMAIL,
            hashed_password=_hash_password(DEMO_PASSWORD),
            full_name="Dr. Priya Raman",
            role=Role.FACULTY,
        )
        db.add_all([student_user, faculty_user])
        await db.flush()

        faculty_rows = [
            FacultyProfile(
                user_id=faculty_user.id,
                employee_id="KARE-FAC-1021",
                full_name="Dr. Priya Raman",
                department="CSE",
                designation="Associate Professor",
                cabin="CSE-214",
                email="priya.raman@klu.ac.in",
                phone="+91-4562-235210",
            ),
            FacultyProfile(
                employee_id="KARE-FAC-1044",
                full_name="Prof. Arun Kumar",
                department="CSE",
                designation="Assistant Professor",
                cabin="CSE-118",
                email="arun.kumar@klu.ac.in",
                phone="+91-4562-235211",
            ),
            FacultyProfile(
                employee_id="KARE-FAC-1078",
                full_name="Dr. Meena Iyer",
                department="CSE",
                designation="Professor",
                cabin="CSE-301",
                email="meena.iyer@klu.ac.in",
                phone="+91-4562-235212",
            ),
            FacultyProfile(
                employee_id="KARE-FAC-1102",
                full_name="Prof. Suresh Babu",
                department="CSE",
                designation="Assistant Professor",
                cabin="CSE-122",
                email="suresh.babu@klu.ac.in",
                phone="+91-4562-235213",
            ),
            FacultyProfile(
                employee_id="KARE-FAC-1130",
                full_name="Dr. Kavitha N",
                department="CSE",
                designation="Associate Professor",
                cabin="CSE-220",
                email="kavitha.n@klu.ac.in",
                phone="+91-4562-235214",
            ),
        ]
        db.add_all(faculty_rows)
        await db.flush()
        f = {row.full_name: row for row in faculty_rows}

        courses = [
            Course(code="CSE501", name="Database Management Systems", credits=4, semester=5, faculty_id=f["Dr. Priya Raman"].id),
            Course(code="CSE502", name="Computer Networks", credits=4, semester=5, faculty_id=f["Prof. Arun Kumar"].id),
            Course(code="CSE503", name="Theory of Computation", credits=3, semester=5, faculty_id=f["Dr. Meena Iyer"].id),
            Course(code="CSE504", name="Software Engineering", credits=3, semester=5, faculty_id=f["Prof. Suresh Babu"].id),
            Course(code="CSE505", name="Artificial Intelligence", credits=3, semester=5, faculty_id=f["Dr. Kavitha N"].id),
            Course(code="CSE506", name="DBMS Laboratory", credits=2, semester=5, faculty_id=f["Dr. Priya Raman"].id),
            Course(code="CSE507", name="Networks Laboratory", credits=2, semester=5, faculty_id=f["Prof. Arun Kumar"].id),
        ]
        db.add_all(courses)
        await db.flush()
        c = {row.code: row for row in courses}

        student = StudentProfile(
            user_id=student_user.id,
            roll_no="KARE2024CSE045",
            full_name="Ananya Krishnan",
            program="B.Tech Computer Science and Engineering",
            department="CSE",
            semester=5,
            section="A",
            batch="2024-28",
        )
        db.add(student)
        await db.flush()

        # Weekly class timetable for CSE 5th sem Section A
        slots = [
            ("Monday", "09:00", "09:50", "CSE501", "Dr. Priya Raman", "LH-201"),
            ("Monday", "10:00", "10:50", "CSE502", "Prof. Arun Kumar", "LH-201"),
            ("Monday", "11:10", "12:00", "CSE503", "Dr. Meena Iyer", "LH-204"),
            ("Monday", "14:00", "14:50", "CSE505", "Dr. Kavitha N", "LH-210"),
            ("Tuesday", "09:00", "09:50", "CSE504", "Prof. Suresh Babu", "LH-201"),
            ("Tuesday", "10:00", "10:50", "CSE501", "Dr. Priya Raman", "LH-201"),
            ("Tuesday", "11:10", "13:00", "CSE506", "Dr. Priya Raman", "Lab-CSE-2"),
            ("Tuesday", "14:00", "14:50", "CSE502", "Prof. Arun Kumar", "LH-201"),
            ("Wednesday", "09:00", "09:50", "CSE503", "Dr. Meena Iyer", "LH-204"),
            ("Wednesday", "10:00", "10:50", "CSE505", "Dr. Kavitha N", "LH-210"),
            ("Wednesday", "11:10", "12:00", "CSE504", "Prof. Suresh Babu", "LH-201"),
            ("Wednesday", "14:00", "15:50", "CSE507", "Prof. Arun Kumar", "Lab-CSE-3"),
            ("Thursday", "09:00", "09:50", "CSE502", "Prof. Arun Kumar", "LH-201"),
            ("Thursday", "10:00", "10:50", "CSE501", "Dr. Priya Raman", "LH-201"),
            ("Thursday", "11:10", "12:00", "CSE505", "Dr. Kavitha N", "LH-210"),
            ("Thursday", "14:00", "14:50", "CSE503", "Dr. Meena Iyer", "LH-204"),
            ("Friday", "09:00", "09:50", "CSE504", "Prof. Suresh Babu", "LH-201"),
            ("Friday", "10:00", "10:50", "CSE502", "Prof. Arun Kumar", "LH-201"),
            ("Friday", "11:10", "12:00", "CSE501", "Dr. Priya Raman", "LH-201"),
            ("Friday", "14:00", "14:50", "CSE505", "Dr. Kavitha N", "Seminar Hall"),
        ]
        db.add_all(
            [
                TimetableSlot(
                    course_id=c[code].id,
                    faculty_id=f[fac].id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    room=room,
                    section="A",
                    semester=5,
                    department="CSE",
                )
                for day, start, end, code, fac, room in slots
            ]
        )

        availability = [
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
                    faculty_id=f[name].id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    kind=kind,
                    location=loc,
                    notes=notes,
                )
                for name, day, start, end, kind, loc, notes in availability
            ]
        )

        attendance = [
            ("CSE501", 32, 29, 1),
            ("CSE502", 32, 24, 0),
            ("CSE503", 28, 26, 0),
            ("CSE504", 28, 25, 1),
            ("CSE505", 26, 22, 0),
            ("CSE506", 12, 12, 0),
            ("CSE507", 12, 10, 0),
        ]
        db.add_all(
            [
                AttendanceSummary(
                    student_id=student.id,
                    course_id=c[code].id,
                    conducted=cond,
                    present=pres,
                    od=od,
                )
                for code, cond, pres, od in attendance
            ]
        )

        marks = [
            ("CSE501", "CAT-1", 42, 50, "2026-09-16"),
            ("CSE501", "CAT-2", 38, 50, "2026-11-11"),
            ("CSE501", "Assignment", 18, 20, "2026-10-05"),
            ("CSE502", "CAT-1", 35, 50, "2026-09-16"),
            ("CSE502", "CAT-2", 31, 50, "2026-11-11"),
            ("CSE502", "Assignment", 16, 20, "2026-10-08"),
            ("CSE503", "CAT-1", 44, 50, "2026-09-17"),
            ("CSE503", "CAT-2", 40, 50, "2026-11-12"),
            ("CSE504", "CAT-1", 39, 50, "2026-09-17"),
            ("CSE504", "CAT-2", 41, 50, "2026-11-12"),
            ("CSE505", "CAT-1", 36, 50, "2026-09-18"),
            ("CSE505", "CAT-2", 33, 50, "2026-11-13"),
            ("CSE506", "Lab Internal", 42, 50, "2026-10-20"),
            ("CSE507", "Lab Internal", 38, 50, "2026-10-21"),
        ]
        db.add_all(
            [
                MarksRecord(
                    student_id=student.id,
                    course_id=c[code].id,
                    assessment=assess,
                    marks=score,
                    max_marks=mx,
                    recorded_on=when,
                )
                for code, assess, score, mx, when in marks
            ]
        )

        events = [
            AcademicEvent(
                title="Odd Semester classes in progress",
                event_type="term",
                start_date="2026-07-14",
                end_date="2026-11-28",
                description="CSE 5th semester instructional period",
            ),
            AcademicEvent(
                title="CAT-1 examinations",
                event_type="exam",
                start_date="2026-09-15",
                end_date="2026-09-19",
                description="Continuous Assessment Test 1 for all UG programmes",
            ),
            AcademicEvent(
                title="Gandhi Jayanthi holiday",
                event_type="holiday",
                start_date="2026-10-02",
                end_date="2026-10-02",
                description="Institute closed",
            ),
            AcademicEvent(
                title="CAT-2 examinations",
                event_type="exam",
                start_date="2026-11-10",
                end_date="2026-11-14",
                description="Continuous Assessment Test 2",
            ),
            AcademicEvent(
                title="Last working day",
                event_type="deadline",
                start_date="2026-11-28",
                end_date="2026-11-28",
                description="Attendance freeze and last instructional day",
            ),
            AcademicEvent(
                title="End-semester examinations",
                event_type="exam",
                start_date="2026-12-08",
                end_date="2026-12-20",
                description="University end-semester theory exams",
            ),
            AcademicEvent(
                title="Department faculty meeting",
                event_type="meeting",
                start_date="2026-08-28",
                end_date="",
                recurrence="weekly",
                description="Every Friday 4:00–5:00 PM, HoD Conference Room",
            ),
            AcademicEvent(
                title="Weekly class reminder circular",
                event_type="notice",
                start_date="2026-08-31",
                end_date="",
                recurrence="weekly",
                description="Auto-drafted reminder of next week's timetable and office hours",
            ),
        ]
        db.add_all(events)
        await db.commit()


async def seed_student_workspace() -> None:
    """Tasks and hostel leave for the demo student (safe to run if academic seed already ran)."""
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(StudentTask).limit(1))
        if existing.scalar_one_or_none():
            return
        student = (await db.execute(select(StudentProfile).where(StudentProfile.roll_no == "KARE2024CSE045"))).scalar_one_or_none()
        if not student or not student.user_id:
            return
        db.add_all(
            [
                StudentTask(
                    user_id=student.user_id,
                    title="Revise Computer Networks CAT-2 topics",
                    notes="Focus on subnetting and TCP congestion — internals are at 66%.",
                    due_date="2026-09-10",
                    category="study",
                ),
                StudentTask(
                    user_id=student.user_id,
                    title="Submit SE mini-project proposal",
                    notes="Meet Prof. Suresh Babu during Wednesday office hours.",
                    due_date="2026-09-05",
                    category="assignment",
                ),
                StudentTask(
                    user_id=student.user_id,
                    title="Do not miss CSE502 this week",
                    notes="Attendance is 75%. Missing one more period drops below the exam cutoff.",
                    due_date="2026-08-29",
                    category="attendance",
                ),
            ]
        )
        db.add(
            HostelLeave(
                student_id=student.id,
                from_date="2026-10-01",
                to_date="2026-10-03",
                reason="Festival at hometown (Gandhi Jayanthi weekend)",
                destination="Madurai",
                status="approved",
            )
        )
        await db.commit()


LINKED_STUDENTS = [
    ("student.demo@klu.ac.in", "student.demo", "Ananya Krishnan", "KARE2024CSE045"),
    ("rohan.mehta@klu.ac.in", "rohan.mehta", "Rohan Mehta", "KARE2024CSE012"),
    ("priya.sharma@klu.ac.in", "priya.sharma", "Priya Sharma", "KARE2024CSE028"),
    ("karthik.raj@klu.ac.in", "karthik.raj", "Karthik Raj", "KARE2024CSE033"),
    ("divya.nair@klu.ac.in", "divya.nair", "Divya Nair", "KARE2024CSE041"),
    ("arjun.patel@klu.ac.in", "arjun.patel", "Arjun Patel", "KARE2024CSE019"),
    ("sneha.reddy@klu.ac.in", "sneha.reddy", "Sneha Reddy", "KARE2024CSE052"),
    ("vishal.kumar@klu.ac.in", "vishal.kumar", "Vishal Kumar", "KARE2024CSE007"),
    ("meera.iyer@klu.ac.in", "meera.iyer", "Meera Iyer", "KARE2024CSE061"),
    ("aditya.singh@klu.ac.in", "aditya.singh", "Aditya Singh", "KARE2024CSE074"),
]

LINKED_FACULTY = [
    ("faculty.demo@klu.ac.in", "faculty.demo", "Dr. Priya Raman", "KARE-FAC-1021", "Associate Professor"),
    ("arun.kumar@klu.ac.in", "arun.kumar", "Prof. Arun Kumar", "KARE-FAC-1044", "Assistant Professor"),
    ("meena.iyer@klu.ac.in", "meena.iyer", "Dr. Meena Iyer", "KARE-FAC-1078", "Professor"),
    ("suresh.babu@klu.ac.in", "suresh.babu", "Prof. Suresh Babu", "KARE-FAC-1102", "Assistant Professor"),
    ("kavitha.n@klu.ac.in", "kavitha.n", "Dr. Kavitha N", "KARE-FAC-1130", "Associate Professor"),
    ("hod.demo@klu.ac.in", "hod.demo", "Dr. Ramesh Venkat", "KARE-FAC-1000", "Professor & Head"),
]

LINKED_STAFF = [
    ("admin.demo@klu.ac.in", "admin.demo", "University Administrator", Role.ADMIN),
    ("admin@example.com", "admin.demo", "Campus Admin (DEMO)", Role.ADMIN),
]


async def seed_linked_directory() -> None:
    """Create Campus-GPT logins that match UIS emails so timetable/attendance auto-link."""
    hashed = _hash_password(DEMO_PASSWORD)
    async with AsyncSessionLocal() as db:
        for email, uis_username, name, roll in LINKED_STUDENTS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not user:
                user = User(
                    email=email,
                    hashed_password=hashed,
                    full_name=name,
                    role=Role.STUDENT,
                    uis_username=uis_username,
                )
                db.add(user)
                await db.flush()
            else:
                if not user.uis_username:
                    user.uis_username = uis_username
                if not user.full_name:
                    user.full_name = name
            profile = (
                await db.execute(select(StudentProfile).where(StudentProfile.roll_no == roll))
            ).scalar_one_or_none()
            if not profile:
                db.add(
                    StudentProfile(
                        user_id=user.id,
                        roll_no=roll,
                        full_name=name,
                        program="B.Tech Computer Science and Engineering",
                        department="CSE",
                        semester=5,
                        section="A",
                        batch="2024-28",
                    )
                )
            elif not profile.user_id:
                profile.user_id = user.id

        for email, uis_username, name, emp_id, designation in LINKED_FACULTY:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not user:
                user = User(
                    email=email,
                    hashed_password=hashed,
                    full_name=name,
                    role=Role.FACULTY,
                    uis_username=uis_username,
                )
                db.add(user)
                await db.flush()
            else:
                if not user.uis_username:
                    user.uis_username = uis_username
            fac = (
                await db.execute(select(FacultyProfile).where(FacultyProfile.employee_id == emp_id))
            ).scalar_one_or_none()
            if not fac:
                fac = (
                    await db.execute(select(FacultyProfile).where(FacultyProfile.full_name == name))
                ).scalar_one_or_none()
            if not fac:
                db.add(
                    FacultyProfile(
                        user_id=user.id,
                        employee_id=emp_id,
                        full_name=name,
                        department="CSE",
                        designation=designation,
                        email=email,
                    )
                )
            elif not fac.user_id:
                fac.user_id = user.id

        for email, uis_username, name, role in LINKED_STAFF:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not user:
                db.add(
                    User(
                        email=email,
                        hashed_password=hashed,
                        full_name=name,
                        role=role,
                        uis_username=uis_username,
                    )
                )
            elif not user.uis_username:
                user.uis_username = uis_username
        await db.commit()


async def seed_demo_chat_memory() -> None:
    """Long-term memory + one sample discussion for the demo student."""
    from app.models.chat import UserMemory, ChatSession, ChatMessage

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == DEMO_STUDENT_EMAIL))).scalar_one_or_none()
        if not user:
            return
        existing = await db.execute(select(UserMemory).where(UserMemory.user_id == user.id).limit(1))
        if existing.scalar_one_or_none():
            return
        db.add_all(
            [
                UserMemory(
                    user_id=user.id,
                    fact="CSE 5th semester student, Section A, roll KARE2024CSE045",
                ),
                UserMemory(
                    user_id=user.id,
                    fact="I prefer planning study around CAT tests and need to watch CSE502 attendance",
                ),
                UserMemory(
                    user_id=user.id,
                    fact="I stay in hostel and apply leave from this app",
                ),
            ]
        )
        sess = ChatSession(
            user_id=user.id,
            session_id="demo-session-attendance",
            title="Attendance and CAT planning",
        )
        db.add(sess)
        await db.flush()
        db.add_all(
            [
                ChatMessage(
                    session_id=sess.id,
                    role="user",
                    content="Remember that I prefer planning study around CAT tests. Any attendance shortage?",
                ),
                ChatMessage(
                    session_id=sess.id,
                    role="assistant",
                    content="I'll remember that you plan around CAT tests. CSE502 (Computer Networks) is at 75% — do not miss this week. Overall attendance is about 88.9%.",
                    sources='[{"source":"Academic database"}]',
                    confidence_score="0.9",
                ),
            ]
        )
        await db.commit()
