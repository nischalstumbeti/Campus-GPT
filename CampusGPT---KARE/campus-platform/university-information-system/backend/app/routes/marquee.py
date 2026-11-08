"""Admin-only marquee CMS (UIS SoR)."""
from __future__ import annotations

import html
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MarqueeItem, User
from app.security.auth import require_roles

router = APIRouter(prefix="/api/v1/admin/marquee", tags=["marquee"])

AdminOnly = require_roles("university_admin", "admin", "super_admin")

ICON_PRESETS = ["📢", "⚠️", "🎓", "🏫", "📅", "💰", "🚌", "🏆", "🔔", "ℹ️"]


def _clean_link(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("www."):
        raw = "https://" + raw
    lowered = raw.lower()
    if lowered.startswith(("http://", "https://", "mailto:")) or raw.startswith("/"):
        return raw[:500]
    raise HTTPException(status_code=400, detail="Link must start with http://, https://, mailto:, or /")


class _NoticeHtml(HTMLParser):
    """Allow text plus <a href> so a link covers only the selected words."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._open = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br":
            self.out.append(" ")
            return
        if tag.lower() != "a":
            return
        href = ""
        for key, value in attrs:
            if key.lower() == "href" and value:
                href = value
                break
        try:
            href = _clean_link(href)
        except HTTPException:
            return
        extra = "" if href.startswith("/") else ' target="_blank" rel="noreferrer"'
        self.out.append(f'<a href="{html.escape(href, quote=True)}"{extra}>')
        self._open = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._open:
            self.out.append("</a>")
            self._open = False

    def handle_data(self, data: str) -> None:
        self.out.append(html.escape(data))


def sanitize_notice(value: str) -> str:
    parser = _NoticeHtml()
    parser.feed(value or "")
    parser.close()
    cleaned = " ".join("".join(parser.out).split())
    visible = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", cleaned)).split())
    if not visible:
        raise HTTPException(status_code=400, detail="Write the notification message")
    if len(visible) > 500 or len(cleaned) > 2000:
        raise HTTPException(status_code=400, detail="Notification is too long")
    return cleaned


def _ser(m: MarqueeItem) -> dict:
    return {
        "id": m.id,
        "icon": m.icon or "",
        "description": m.description or "",
        "link_url": "",
        "active": bool(m.active),
        "sort_order": m.sort_order or 0,
        "updated_by": m.updated_by,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


class MarqueeIn(BaseModel):
    icon: str = Field(default="", max_length=32)
    description: str = Field(min_length=1, max_length=2000)
    link_url: str = Field(default="", max_length=500)
    active: bool = True
    sort_order: int = 0


class MarqueePatch(BaseModel):
    icon: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = Field(default=None, max_length=2000)
    link_url: Optional[str] = Field(default=None, max_length=500)
    active: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("/icons")
async def list_icons(user: Annotated[User, Depends(AdminOnly)]):
    return {"icons": ICON_PRESETS}


@router.get("")
async def list_marquees(
    user: Annotated[User, Depends(AdminOnly)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (
        await db.execute(select(MarqueeItem).order_by(MarqueeItem.sort_order, MarqueeItem.id.desc()))
    ).scalars().all()
    return {"items": [_ser(r) for r in rows], "icons": ICON_PRESETS, "source": "UIS"}


@router.get("/active")
async def active_marquees(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Active ticker items — public campus notices (no PII)."""
    rows = (
        await db.execute(
            select(MarqueeItem)
            .where(MarqueeItem.active == True)  # noqa: E712
            .order_by(MarqueeItem.sort_order, MarqueeItem.id.desc())
        )
    ).scalars().all()
    return {"items": [_ser(r) for r in rows], "source": "UIS"}


@router.post("")
async def create_marquee(
    body: MarqueeIn,
    user: Annotated[User, Depends(AdminOnly)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = MarqueeItem(
        icon=(body.icon or "").strip()[:32],
        description=sanitize_notice(body.description),
        link_url="",
        active=body.active,
        sort_order=body.sort_order,
        updated_by=user.username,
    )
    db.add(row)
    await db.flush()
    return {"ok": True, "item": _ser(row)}


@router.put("/{item_id}")
async def update_marquee(
    item_id: int,
    body: MarqueePatch,
    user: Annotated[User, Depends(AdminOnly)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(MarqueeItem).where(MarqueeItem.id == item_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Marquee item not found")
    if body.icon is not None:
        row.icon = body.icon.strip()[:32]
    if body.description is not None:
        row.description = sanitize_notice(body.description)
        row.link_url = ""
    if body.active is not None:
        row.active = body.active
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    row.updated_by = user.username
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "item": _ser(row)}


@router.delete("/{item_id}")
async def delete_marquee(
    item_id: int,
    user: Annotated[User, Depends(AdminOnly)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(MarqueeItem).where(MarqueeItem.id == item_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Marquee item not found")
    await db.delete(row)
    await db.flush()
    return {"ok": True}
