"""Local SIS adapter — swap for UniversityERPProvider later."""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import academic_service as acad
from app.models.academic import StudentProfile
from sqlalchemy import select


class SqliteAcademicProvider:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _student(self, student_key: str) -> Optional[StudentProfile]:
        return (
            await self.db.execute(select(StudentProfile).where(StudentProfile.roll_no == student_key))
        ).scalar_one_or_none()

    async def get_attendance(self, student_key: str):
        s = await self._student(student_key)
        return await acad.get_attendance(self.db, s) if s else []

    async def get_marks(self, student_key: str):
        s = await self._student(student_key)
        return await acad.get_marks(self.db, s) if s else []

    async def get_timetable(self, student_key: str, day: Optional[str] = None):
        s = await self._student(student_key)
        return await acad.get_timetable(self.db, s, day) if s else []
