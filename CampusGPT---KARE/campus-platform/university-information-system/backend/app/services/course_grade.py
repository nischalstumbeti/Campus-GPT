"""Assign one course and a letter grade to a student."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, CourseOffering, Enrollment, Grade, StudentProfile

GRADE_POINTS = {
    "O": 10.0,
    "A+": 9.0,
    "A": 8.0,
    "B+": 7.0,
    "B": 6.0,
    "C": 5.0,
    "P": 4.0,
    "F": 0.0,
    "RA": 0.0,
    "AB": 0.0,
}


def grade_point(letter: str) -> float:
    key = (letter or "").strip().upper()
    if key not in GRADE_POINTS:
        raise ValueError("Grade must be one of " + ", ".join(GRADE_POINTS))
    return GRADE_POINTS[key]


async def assign_course_grade(
    db: AsyncSession,
    *,
    student_id: str,
    course_code: str,
    letter: str,
    section: str | None = None,
) -> dict:
    point = grade_point(letter)
    normalized = (letter or "").strip().upper()
    register = (student_id or "").strip()
    code = (course_code or "").strip()
    student = (
        await db.execute(select(StudentProfile).where(func.lower(StudentProfile.student_id) == register.lower()))
    ).scalar_one_or_none()
    if not student:
        raise LookupError(f"Student not found: {register}")
    course = (
        await db.execute(select(Course).where(func.lower(Course.code) == code.lower()))
    ).scalar_one_or_none()
    if not course:
        raise LookupError(f"Course not found: {code}")
    chosen_section = ((section or student.section or "A").strip() or "A")[:8]
    offering = (
        await db.execute(
            select(CourseOffering).where(
                CourseOffering.course_id == course.id,
                CourseOffering.section == chosen_section,
                CourseOffering.semester == student.semester,
            )
        )
    ).scalars().first()
    if not offering:
        offering = CourseOffering(
            course_id=course.id,
            faculty_id=None,
            semester=student.semester or 1,
            academic_year=(student.batch or "2025-26")[:16],
            section=chosen_section,
        )
        db.add(offering)
        await db.flush()
    enrollment = (
        await db.execute(
            select(Enrollment).where(Enrollment.student_id == student.id, Enrollment.offering_id == offering.id)
        )
    ).scalar_one_or_none()
    if not enrollment:
        enrollment = Enrollment(student_id=student.id, offering_id=offering.id, status="active")
        db.add(enrollment)
        await db.flush()
    grade = (
        await db.execute(select(Grade).where(Grade.enrollment_id == enrollment.id))
    ).scalar_one_or_none()
    if grade:
        grade.letter = normalized
        grade.grade_point = point
        action = "updated"
    else:
        db.add(Grade(enrollment_id=enrollment.id, letter=normalized, grade_point=point))
        action = "created"
    return {
        "student_id": student.student_id,
        "course_code": course.code,
        "section": offering.section,
        "grade": normalized,
        "grade_point": point,
        "action": action,
    }
