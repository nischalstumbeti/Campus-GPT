"""Read a stored acknowledgement slip."""
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Acknowledgement, User
from app.security.auth import get_current_user

router = APIRouter(prefix="/api/v1/acknowledgements", tags=["acknowledgements"])

_ADMIN = {"university_admin", "admin", "super_admin", "developer", "operator", "coe", "director"}
_REGISTRATION = {"registration", "withdrawal", "revaluation", "arrear", "backlog", "makeup"}


def _layout_kind(kind: str) -> str:
    if kind == "form":
        return "form"
    if kind in _REGISTRATION:
        return "registration"
    return "general"


def _public(row: Acknowledgement) -> dict:
    return {
        "number": row.number,
        "kind": row.kind,
        "title": row.title,
        "summary": row.summary,
        "email": row.recipient_email,
        "email_sent": row.email_sent,
        "status": row.status or "",
        "layout_kind": _layout_kind(row.kind or ""),
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _seal(row: Acknowledgement) -> None:
    if not row.verify_code:
        row.verify_code = secrets.token_urlsafe(18)


@router.get("/verify/{code}")
async def verify_acknowledgement(code: str, db: Annotated[AsyncSession, Depends(get_db)]):
    token = code.strip()
    if len(token) < 12 or any(ch.isspace() for ch in token):
        raise HTTPException(status_code=404, detail="This code does not match an issued acknowledgement")
    row = (
        await db.execute(select(Acknowledgement).where(Acknowledgement.verify_code == token))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="This code does not match an issued acknowledgement")
    return {
        "valid": True,
        "number": row.number,
        "title": row.title,
        "status": row.status or "recorded",
        "issued_at": row.created_at.isoformat() if row.created_at else "",
    }


@router.get("")
async def my_acknowledgements(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    query = select(Acknowledgement).order_by(Acknowledgement.id.desc()).limit(50)
    if user.role not in _ADMIN:
        query = query.where(
            or_(Acknowledgement.actor_user_id == user.id, Acknowledgement.recipient_email == user.email)
        )
    rows = (await db.execute(query)).scalars().all()
    return {"items": [_public(row) for row in rows]}


@router.get("/{number}")
async def one_acknowledgement(
    number: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(select(Acknowledgement).where(Acknowledgement.number == number))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Acknowledgement not found")
    if user.role not in _ADMIN and row.actor_user_id != user.id and row.recipient_email != user.email:
        raise HTTPException(status_code=404, detail="Acknowledgement not found")
    _seal(row)
    payload = _public(row)
    payload["verify_path"] = f"/ack/verify/{row.verify_code}"
    return payload
