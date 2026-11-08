from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.security.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    hash_password_async,
    verify_password_async,
)
from app.utils.rate_limit import check_rate_limit, client_key

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    username: str


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    check_rate_limit(client_key(request, "uis-login"), limit=20, window_seconds=60)
    ident = (body.username or "").strip()
    result = await db.execute(
        select(User).where(or_(User.username == ident, User.email == ident))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not await verify_password_async(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role, "uid": user.id})
    return TokenResponse(
        access_token=token,
        role=user.role,
        full_name=user.full_name,
        username=user.username,
    )


@router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]):
    student = None
    if user.student:
        student = {
            "student_id": user.student.student_id,
            "year": user.student.year,
            "semester": user.student.semester,
            "section": user.student.section,
            "cgpa": user.student.cgpa,
            "overall_attendance": user.student.overall_attendance,
            "credits_completed": user.student.credits_completed,
            "credits_required": user.student.credits_required,
            "backlogs": user.student.backlogs,
        }
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "department_code": user.department_code,
        "student": student,
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Self-service password change — updates the shared UIS account (admin SoR)."""
    if not await verify_password_async(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    user.hashed_password = await hash_password_async(body.new_password)
    await db.flush()
    return {
        "ok": True,
        "message": "Password updated. Use the new password for UIS and Campus-GPT sign-in.",
        "source": "UIS",
    }
