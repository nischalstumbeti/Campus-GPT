"""Staff directory. Students receive email only; other roles also receive cabin details."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import FacultyProfile, User
from app.security.auth import get_current_user
from app.seed.ensure_directory import OFFICIAL_ROLES

router = APIRouter(prefix="/api/v1/directory", tags=["directory"])

ROLE_LABELS = {
    "faculty": "Faculty",
    "hod": "Head of Department",
    "hostel_admin": "Hostel Warden",
    "warden": "Hostel Warden",
    "hostel_warden": "Hostel Warden",
    "admin": "Administrator",
    "university_admin": "Administrator",
    "super_admin": "Administrator",
    "department_admin": "Administrator",
    "exam_admin": "Administrator",
}


@router.get("")
async def directory(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (
        await db.execute(
            select(User)
            .where(User.role.in_(OFFICIAL_ROLES), User.is_active.is_(True))
            .options(selectinload(User.faculty).selectinload(FacultyProfile.department))
            .order_by(User.full_name)
        )
    ).scalars().all()
    student_view = user.role == "student"
    people = []
    for row in rows:
        faculty = row.faculty
        item = {
            "name": row.full_name,
            "email": row.email,
            "role": ROLE_LABELS.get(row.role, row.role.replace("_", " ").title()),
            "photo_url": row.photo_url or "",
        }
        if not student_view:
            department = ""
            if faculty and faculty.department:
                department = faculty.department.name
            item.update(
                {
                    "photo_url": row.photo_url or "",
                    "designation": (faculty.designation if faculty and faculty.designation else row.designation) or "",
                    "department": department or row.office or "",
                    "school": row.school or "",
                    "block": row.cabin_block or "",
                }
            )
        people.append(item)
    return {"limited": student_view, "people": people}
