"""Authentication utilities - JWT, password hashing."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User, Role
from app.utils.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        import bcrypt
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    pw = (password or "")[:72]
    try:
        return pwd_context.hash(pw)
    except Exception:
        import bcrypt
        return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # Session tokens must not carry password_reset (or other) purpose claims
    if "purpose" not in to_encode:
        to_encode["purpose"] = "access"
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def _session_claims(payload: dict) -> dict:
    """Reject non-session tokens (e.g. password_reset) for API auth."""
    purpose = payload.get("purpose")
    if purpose and purpose != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return {
        "sub": payload.get("sub"),
        "role": payload.get("role", "student"),
        "full_name": payload.get("full_name") or "",
        "email": payload.get("email") or "",
    }


async def _revalidate_user(db: AsyncSession, claims: dict) -> dict:
    """Ensure JWT still maps to an active DB user; refresh role/name/email from SoR."""
    try:
        uid = int(claims.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    row = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=401, detail="Session revoked")
    role = row.role.value if hasattr(row.role, "value") else str(row.role)
    return {
        "sub": str(row.id),
        "role": role,
        "full_name": row.full_name or "",
        "email": row.email or "",
    }


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[dict]:
    """Optional auth - returns user info or None."""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    try:
        claims = _session_claims(payload)
        return await _revalidate_user(db, claims)
    except HTTPException:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Required auth - raises if invalid or user deleted/revoked."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    claims = _session_claims(payload)
    return await _revalidate_user(db, claims)


async def require_student(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != Role.STUDENT.value:
        raise HTTPException(status_code=403, detail="Student access required")
    return user


async def require_faculty(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in (Role.FACULTY.value, Role.ADMIN.value, Role.SUPER_ADMIN.value):
        raise HTTPException(status_code=403, detail="Faculty access required")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require admin or super_admin role."""
    if user.get("role") not in (Role.ADMIN.value, Role.SUPER_ADMIN.value):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require super_admin role."""
    if user.get("role") != Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user
