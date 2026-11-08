"""Admin-only marquee CMS — prefers UIS SoR when admin account is linked."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marquee import MarqueeItem
from app.services import uis_client
from app.services.audit_log import write_audit
from app.services.uis_link import linked_uis_username
from app.utils.auth import get_current_user_optional, require_admin
from app.utils.database import get_db

router = APIRouter()

ICON_PRESETS = ["📢", "⚠️", "🎓", "🏫", "📅", "💰", "🚌", "🏆", "🔔", "ℹ️"]


def _ser(m: MarqueeItem) -> dict:
    return {
        "id": m.id,
        "icon": m.icon or "📢",
        "description": m.description or "",
        "active": bool(m.active),
        "sort_order": m.sort_order or 0,
        "updated_by": m.updated_by,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


class MarqueeIn(BaseModel):
    icon: str = Field(default="📢", max_length=32)
    description: str = Field(min_length=1, max_length=500)
    active: bool = True
    sort_order: int = 0


class MarqueePatch(BaseModel):
    icon: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = Field(default=None, max_length=500)
    active: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("/admin/marquee/icons")
async def list_icons(user: dict = Depends(require_admin)):
    return {"icons": ICON_PRESETS}


@router.get("/admin/marquee")
async def list_marquees(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.list_marquees(uis_user)
            data["source"] = "UIS"
            data.setdefault("icons", ICON_PRESETS)
            return data
        except uis_client.UisClientError:
            pass
    rows = (
        await db.execute(select(MarqueeItem).order_by(MarqueeItem.sort_order, MarqueeItem.id.desc()))
    ).scalars().all()
    return {"items": [_ser(r) for r in rows], "icons": ICON_PRESETS, "source": "local"}


@router.get("/admin/marquee/active")
async def active_marquees_admin(
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """Active ticker — any signed-in role (student, faculty, hostel, admin)."""
    return await active_marquees_public(db=db, user=user)


@router.get("/marquee/active")
async def active_marquees_public(
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """Any signed-in user can read the active campus ticker."""
    uis_user = await linked_uis_username(db, user) if user else None
    if uis_user:
        try:
            data = await uis_client.active_marquees(uis_user)
            data["source"] = "UIS"
            return data
        except uis_client.UisClientError:
            pass
    rows = (
        await db.execute(
            select(MarqueeItem)
            .where(MarqueeItem.active == True)  # noqa: E712
            .order_by(MarqueeItem.sort_order, MarqueeItem.id.desc())
        )
    ).scalars().all()
    return {"items": [_ser(r) for r in rows], "source": "local"}


@router.post("/admin/marquee")
async def create_marquee(
    body: MarqueeIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            return await uis_client.create_marquee(uis_user, body.model_dump())
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    row = MarqueeItem(
        icon=(body.icon or "📢").strip()[:32],
        description=body.description.strip(),
        active=body.active,
        sort_order=body.sort_order,
        updated_by=str(user.get("email") or user.get("sub")),
    )
    db.add(row)
    await db.flush()
    await write_audit(db, user=user, action="CREATE", resource="marquee", detail=row.description[:120])
    return {"ok": True, "item": _ser(row)}


@router.put("/admin/marquee/{item_id}")
async def update_marquee(
    item_id: int,
    body: MarqueePatch,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            return await uis_client.update_marquee(uis_user, item_id, body.model_dump(exclude_none=True))
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    row = (await db.execute(select(MarqueeItem).where(MarqueeItem.id == item_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Marquee item not found")
    if body.icon is not None:
        row.icon = body.icon.strip()[:32] or "📢"
    if body.description is not None:
        row.description = body.description.strip()
    if body.active is not None:
        row.active = body.active
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    row.updated_by = str(user.get("email") or user.get("sub"))
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "item": _ser(row)}


@router.delete("/admin/marquee/{item_id}")
async def delete_marquee(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            return await uis_client.delete_marquee(uis_user, item_id)
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    row = (await db.execute(select(MarqueeItem).where(MarqueeItem.id == item_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Marquee item not found")
    await db.delete(row)
    await db.flush()
    return {"ok": True}
