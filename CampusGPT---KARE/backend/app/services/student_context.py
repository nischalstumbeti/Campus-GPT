"""Resolve the current Campus-GPT user to UIS personal data (university database via API)."""
from __future__ import annotations

from typing import Any, Optional, Union
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.services import academic_service as acad
from app.services import uis_academic as uis_acad
from app.services import uis_client
from app.services.uis_academic import LinkedStudent

logger = logging.getLogger(__name__)


async def get_uis_username(db: AsyncSession, user: dict) -> Optional[str]:
    if not str(user.get("sub", "")).isdigit():
        return None
    row = (await db.execute(select(User).where(User.id == int(user["sub"])))).scalar_one_or_none()
    if not row:
        return None
    if row.uis_username:
        return row.uis_username
    if uis_client.uis_enabled() and row.email:
        ident = await uis_client.resolve_identity_by_email(row.email)
        if ident and ident.get("username") and ident.get("has_student_profile"):
            row.uis_username = ident["username"]
            await db.flush()
            return row.uis_username
    return None


async def resolve_personal_student(
    db: AsyncSession, user: dict
) -> tuple[Optional[Union[LinkedStudent, Any]], str]:
    """Returns (student, source) where source is 'UIS' | 'local' | ''.

    Personal records come from the UIS database only unless ALLOW_LOCAL_SIS_FALLBACK is enabled.
    """
    if user.get("role") == "faculty":
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")

    uis_user = await get_uis_username(db, user)
    if uis_user and uis_client.uis_enabled():
        try:
            linked = await uis_acad.load_linked_student(uis_user)
            if linked:
                return linked, "UIS"
        except uis_client.UisConsentDenied:
            raise HTTPException(
                status_code=403,
                detail="I can't provide that information because you don't have permission to access it.",
            )
        except uis_client.UisClientError as exc:
            logger.warning("UIS unavailable (%s); local SIS fallback is disabled", exc)

    if get_settings().ALLOW_LOCAL_SIS_FALLBACK:
        student, _ = await acad.resolve_student(db, user)
        if student:
            return student, "local"
    return None, ""


def serialize_any(student, source: str) -> dict:
    if isinstance(student, LinkedStudent):
        data = uis_acad.serialize_linked(student)
        data["source"] = source
        return data
    data = acad.serialize_student(student)
    data["source"] = source
    return data
