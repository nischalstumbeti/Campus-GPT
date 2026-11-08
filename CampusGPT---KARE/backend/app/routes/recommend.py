"""Recommendation API."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.recommendation import get_recommendations

router = APIRouter()


class RecommendRequest(BaseModel):
    course: str | None = None
    subject: str | None = None
    budget: str | None = None
    marks: float | None = None
    board: str | None = None
    state: str | None = None
    program_level: str | None = None


@router.post("/recommend")
async def recommend(req: RecommendRequest):
    """Get personalized course/college recommendations."""
    return await get_recommendations(
        course=req.course,
        subject=req.subject,
        budget=req.budget,
        marks=req.marks,
        board=req.board,
        state=req.state,
        program_level=req.program_level,
    )
