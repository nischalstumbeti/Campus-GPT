"""In-app notification APIs — prefer UIS SoR when account is linked."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import AppNotification
from app.services import uis_client
from app.services.uis_link import linked_uis_username
from app.utils.auth import get_current_user
from app.utils.database import get_db

router = APIRouter()


def _uid(user: dict) -> int:
    return int(user["sub"])


@router.get("/notifications")
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.list_notifications(uis_user)
            data["source"] = "UIS"
            return data
        except uis_client.UisClientError:
            pass
    uid = _uid(user)
    rows = (
        await db.execute(
            select(AppNotification)
            .where(AppNotification.user_id == uid)
            .order_by(AppNotification.created_at.desc())
            .limit(40)
        )
    ).scalars().all()
    unread = sum(1 for r in rows if not r.read)
    return {
        "unread": unread,
        "items": [
            {
                "id": r.id,
                "kind": r.kind,
                "title": r.title,
                "body": r.body,
                "link": r.link or "/messages",
                "thread_id": r.thread_id,
                "read": r.read,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "source": "local",
    }


@router.get("/notifications/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    data = await list_notifications(db=db, user=user)
    return {"unread": data.get("unread") or 0}


@router.post("/notifications/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            return await uis_client.mark_notifications_read_all(uis_user)
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    uid = _uid(user)
    await db.execute(
        update(AppNotification).where(AppNotification.user_id == uid, AppNotification.read == False).values(read=True)  # noqa: E712
    )
    await db.flush()
    return {"ok": True}


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            return await uis_client.mark_notification_read(uis_user, notification_id)
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    uid = _uid(user)
    row = (
        await db.execute(
            select(AppNotification).where(AppNotification.id == notification_id, AppNotification.user_id == uid)
        )
    ).scalar_one_or_none()
    if row:
        row.read = True
        await db.flush()
    return {"ok": True}
