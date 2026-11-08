"""ERP-replaceable academic data provider."""
from __future__ import annotations

from typing import Any, Optional, Protocol


class AcademicDataProvider(Protocol):
    async def get_attendance(self, student_key: str) -> list[dict[str, Any]]: ...
    async def get_marks(self, student_key: str) -> list[dict[str, Any]]: ...
    async def get_timetable(self, student_key: str, day: Optional[str] = None) -> list[dict[str, Any]]: ...
