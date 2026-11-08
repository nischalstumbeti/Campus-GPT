"""Resolve Campus-GPT user → UIS username for shared SoR calls."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import uis_client


async def linked_uis_username(db: AsyncSession, user: dict | None) -> Optional[str]:
    if not user or not uis_client.uis_enabled():
        return None
    try:
        uid = int(user["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    row = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not row:
        return None
    if row.uis_username:
        return row.uis_username
    if row.email:
        ident = await uis_client.resolve_identity_by_email(row.email)
        if ident and ident.get("username"):
            row.uis_username = ident["username"]
            await db.flush()
            return row.uis_username
    return None
