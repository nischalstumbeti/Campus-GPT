"""Add earlier semesters plus non-CGPA and mandatory courses without rebuilding the database."""
from __future__ import annotations

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Course, CourseOffering, Department, Enrollment, Grade, StudentProfile

EXTRAS = [
    ("CSE101", "Programming for Problem Solving", 4, "cgpa", 1, "2023-24"),
    ("CSE201", "Data Structures", 4, "cgpa", 2, "2024-25"),
    ("HS201", "Universal Human Values", 0, "mandatory", 2, "2024-25"),
    ("CSE301", "Operating Systems", 3, "cgpa", 3, "2024-25"),
    ("CSE401", "Design and Analysis of Algorithms", 4, "cgpa", 4, "2025-26"),
    ("NC401", "NPTEL / Online Course", 2, "non_cgpa", 4, "2025-26"),
]


def _letter(cgpa: float, shift: float) -> tuple[str, float]:
    point = float(max(6, min(10, int(round(cgpa + shift)))))
    letters = {10.0: "O", 9.0: "A+", 8.0: "A", 7.0: "B+", 6.0: "B"}
    return letters[point], point


async def ensure_academics() -> dict:
    created = 0
    async with SessionLocal() as db:
        dept = (await db.execute(select(Department).where(Department.code == "CSE"))).scalar_one_or_none()
        students = (await db.execute(select(StudentProfile))).scalars().all()
        if not dept or not students:
            return {"ok": True, "created": 0, "reason": "no students"}

        for index, (code, title, credits, group, semester, year) in enumerate(EXTRAS):
            course = (await db.execute(select(Course).where(Course.code == code))).scalar_one_or_none()
            if not course:
                course = Course(
                    code=code,
                    title=title,
                    credits=credits,
                    department_id=dept.id,
                    result_group=group,
                )
                db.add(course)
                await db.flush()
                created += 1
            elif not course.result_group:
                course.result_group = group

            offering = (
                await db.execute(
                    select(CourseOffering).where(
                        CourseOffering.course_id == course.id,
                        CourseOffering.semester == semester,
                        CourseOffering.section == "A",
                    )
                )
            ).scalar_one_or_none()
            if not offering:
                offering = CourseOffering(
                    course_id=course.id,
                    semester=semester,
                    academic_year=year,
                    section="A",
                )
                db.add(offering)
                await db.flush()

            for student in students:
                enrolled = (
                    await db.execute(
                        select(Enrollment).where(
                            Enrollment.student_id == student.id,
                            Enrollment.offering_id == offering.id,
                        )
                    )
                ).scalar_one_or_none()
                if enrolled:
                    continue
                enrolled = Enrollment(student_id=student.id, offering_id=offering.id, status="completed")
                db.add(enrolled)
                await db.flush()
                if group == "mandatory":
                    letter, point = "P", 0.0
                elif group == "non_cgpa":
                    letter, point = "A", 8.0
                else:
                    letter, point = _letter(student.cgpa or 7.0, -0.4 * (index % 3))
                db.add(Grade(enrollment_id=enrolled.id, letter=letter, grade_point=point))
                created += 1

        await db.commit()
    return {"ok": True, "created": created}
