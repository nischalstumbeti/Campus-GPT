"""Open-close switches for revaluation, arrear, and backlog. Closed until an admin enables them."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import Enrollment, ExamApplicationWindow, Grade, StudentProfile

KINDS = ("revaluation", "arrear", "backlog", "registration", "withdrawal")
FAIL = {"F", "RA", "U", "AB", "I"}


def _failed(letter: str, point: float) -> bool:
    return letter.strip().upper() in FAIL


async def ensure_exam_windows() -> dict:
    async with SessionLocal() as db:
        existing = {
            row.kind: row
            for row in (await db.execute(select(ExamApplicationWindow))).scalars().all()
        }
        created = 0
        for kind in KINDS:
            if kind in existing:
                continue
            db.add(ExamApplicationWindow(kind=kind, enabled=False, note="", fee=0))
            created += 1

        marked = 0
        students = (await db.execute(select(StudentProfile))).scalars().all()
        for student in students:
            if student.backlogs <= 0:
                continue
            rows = (
                await db.execute(
                    select(Grade)
                    .join(Enrollment)
                    .where(Enrollment.student_id == student.id)
                    .options(selectinload(Grade.enrollment).selectinload(Enrollment.offering))
                )
            ).scalars().all()
            already = sum(1 for grade in rows if _failed(grade.letter, grade.grade_point))
            need = student.backlogs - already
            if need <= 0:
                continue
            passing = [grade for grade in rows if not _failed(grade.letter, grade.grade_point) and grade.enrollment and grade.enrollment.offering]
            passing.sort(key=lambda grade: (0 if grade.enrollment.offering.semester == student.semester else 1, grade.enrollment.offering.semester))
            for grade in passing[:need]:
                grade.letter = "F"
                grade.grade_point = 0
                marked += 1

        for student in students:
            if student.backlogs <= 0:
                continue
            rows = (
                await db.execute(
                    select(Grade)
                    .join(Enrollment)
                    .where(Enrollment.student_id == student.id)
                    .options(selectinload(Grade.enrollment).selectinload(Enrollment.offering))
                )
            ).scalars().all()
            usable = [grade for grade in rows if grade.enrollment and grade.enrollment.offering]
            fails = [grade for grade in usable if _failed(grade.letter, grade.grade_point)]
            older = [grade for grade in fails if grade.enrollment.offering.semester < student.semester]
            if older:
                continue
            earlier = [
                grade
                for grade in usable
                if not _failed(grade.letter, grade.grade_point)
                and grade.enrollment.offering.semester < student.semester
            ]
            current = [grade for grade in fails if grade.enrollment.offering.semester == student.semester]
            if not earlier:
                continue
            earlier.sort(key=lambda grade: grade.enrollment.offering.semester)
            earlier[0].letter = "F"
            earlier[0].grade_point = 0
            if current and len(fails) >= student.backlogs:
                current[0].letter = "B"
                current[0].grade_point = 6
            marked += 1
        await db.commit()
    return {"ok": True, "windows": created, "failed_grades": marked}
