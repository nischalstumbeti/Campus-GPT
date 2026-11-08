"""Student APIs - points, profile."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.utils.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/student/points")
async def get_my_points(
    db=Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get current student's points. Requires login."""
    result = await db.execute(select(User).where(User.id == int(user["sub"])))
    u = result.scalar_one_or_none()
    points = getattr(u, "points", 0) or 0 if u else 0
    return {"points": points}
