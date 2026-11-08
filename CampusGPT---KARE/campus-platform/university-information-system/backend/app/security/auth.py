import asyncio
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import StudentProfile, User

bearer = HTTPBearer(auto_error=False)
settings = get_settings()

ROLE_HIERARCHY = {
    "student": 1,
    "faculty": 2,
    "staff": 2,
    "hod": 3,
    "department_admin": 3,
    "exam_admin": 3,
    "hostel_admin": 3,
    "admin": 4,
    "university_admin": 4,
    "super_admin": 5,
}


def hash_password(password: str) -> str:
    pw = (password or "")[:72].encode("utf-8")
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Direct bcrypt — avoids passlib backend stalls on some Windows setups."""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw((plain or "")[:72].encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


async def verify_password_async(plain: str, hashed: str) -> bool:
    """Offload bcrypt to a worker thread so the event loop stays responsive."""
    return await asyncio.to_thread(verify_password, plain, hashed)


async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)

def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(
        select(User)
        .where(User.username == username)
        .options(
            selectinload(User.student).selectinload(StudentProfile.program),
            selectinload(User.faculty),
        )
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or not found")
    return user


def require_roles(*roles: str):
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles and user.role != "super_admin":
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return checker
