"""Who is the faculty advisor for a student: a student mapping overrides the section mapping."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FacultyAdvisor, FacultyProfile, StudentProfile


def _advisor_id(maps: list[FacultyAdvisor], student: StudentProfile) -> int | None:
    for row in maps:
        if row.scope == "student" and row.student_id == student.id:
            return row.faculty_id
    for row in maps:
        if row.scope != "section":
            continue
        if (row.section or "").strip() != (student.section or "").strip():
            continue
        batch = (row.batch or "").strip()
        if batch and not (student.batch or "").startswith(batch):
            continue
        return row.faculty_id
    return None


async def advisor_for(db: AsyncSession, student: StudentProfile) -> int | None:
    maps = (await db.execute(select(FacultyAdvisor))).scalars().all()
    return _advisor_id(list(maps), student)


async def mentee_ids(db: AsyncSession, faculty_profile_id: int) -> set[int]:
    maps = list((await db.execute(select(FacultyAdvisor))).scalars().all())
    students = (await db.execute(select(StudentProfile))).scalars().all()
    return {student.id for student in students if _advisor_id(maps, student) == faculty_profile_id}


async def list_advisors(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(FacultyAdvisor)
            .options(
                selectinload(FacultyAdvisor.faculty).selectinload(FacultyProfile.user),
                selectinload(FacultyAdvisor.student).selectinload(StudentProfile.user),
            )
            .order_by(FacultyAdvisor.id)
        )
    ).scalars().all()
    items = []
    for row in rows:
        faculty_name = row.faculty.user.full_name if row.faculty and row.faculty.user else ""
        student = row.student
        items.append(
            {
                "id": row.id,
                "scope": row.scope,
                "section": row.section or "",
                "batch": row.batch or "",
                "student_id": student.student_id if student else "",
                "student_name": student.user.full_name if student and student.user else "",
                "faculty_profile_id": row.faculty_id,
                "faculty_name": faculty_name,
            }
        )
    return items
