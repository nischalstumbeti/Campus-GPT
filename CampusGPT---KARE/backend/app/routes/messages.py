"""Real-time-ish direct messaging between students, faculty, and admin."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.messaging import DirectMessage, MessageThread
from app.models.notifications import AppNotification
from app.models.platform import NotificationPref
from app.models.user import User, Role
from app.utils.auth import get_current_user
from app.utils.database import get_db
from app.utils.auth import decode_token
from app.services import uis_client
from app.services.uis_link import linked_uis_username

router = APIRouter()

# In-memory fanout for websocket subscribers: user_id -> set of websockets
_subscribers: dict[int, set[WebSocket]] = {}


async def _notify(user_id: int, payload: dict) -> None:
    sockets = list(_subscribers.get(user_id, set()))
    dead = []
    for ws in sockets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _subscribers.get(user_id, set()).discard(ws)


async def _prefs_allow_inapp(db: AsyncSession, user_id: int, kind: str) -> bool:
    row = (
        await db.execute(select(NotificationPref).where(NotificationPref.user_id == user_id))
    ).scalar_one_or_none()
    if not row:
        return True
    k = (kind or "").lower()
    if "fee" in k:
        return bool(row.inapp_fees)
    if "leave" in k or "hostel" in k:
        return bool(getattr(row, "inapp_leave", True))
    if "message" in k or "thread" in k or "reply" in k:
        return bool(row.inapp_messages)
    return True


async def _create_notification(
    db: AsyncSession,
    *,
    user_id: int,
    kind: str,
    title: str,
    body: str,
    thread_id: int | None = None,
) -> None:
    if not user_id:
        return
    if not await _prefs_allow_inapp(db, user_id, kind):
        return
    note = AppNotification(
        user_id=user_id,
        kind=kind,
        title=title[:200],
        body=(body or "")[:500],
        link="/messages",
        thread_id=thread_id,
        read=False,
    )
    db.add(note)
    await db.flush()
    await _notify(
        user_id,
        {
            "type": "notification",
            "notification": {
                "id": note.id,
                "kind": note.kind,
                "title": note.title,
                "body": note.body,
                "link": note.link,
                "thread_id": note.thread_id,
                "read": False,
                "created_at": note.created_at.isoformat() if note.created_at else None,
            },
        },
    )


def _uid(user: dict) -> int:
    return int(user["sub"])


class ThreadCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    category: str = "general"
    to_role: str = "admin"  # admin | faculty


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class RedirectIn(BaseModel):
    redirected_to: str  # student_login | faculty | warden | admin
    note: str = ""


def _serialize_thread(t: MessageThread, users: dict[int, User]) -> dict:
    creator = users.get(t.created_by)
    assignee = users.get(t.assignee_id) if t.assignee_id else None
    msgs = sorted(t.messages or [], key=lambda m: m.created_at or datetime.utcnow())
    return {
        "id": t.id,
        "subject": t.subject,
        "category": t.category,
        "status": t.status,
        "redirected_to": t.redirected_to or "",
        "created_by": t.created_by,
        "created_by_name": creator.full_name if creator else "",
        "created_by_role": creator.role.value if creator and creator.role else "",
        "assignee_id": t.assignee_id,
        "assignee_name": assignee.full_name if assignee else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_name": (users.get(m.sender_id).full_name if users.get(m.sender_id) else ""),
                "body": m.body,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "read": m.read,
            }
            for m in msgs
        ],
    }


async def _load_users(db: AsyncSession, ids: set[int]) -> dict[int, User]:
    if not ids:
        return {}
    rows = (await db.execute(select(User).where(User.id.in_(list(ids))))).scalars().all()
    return {u.id: u for u in rows}


@router.get("/messages/threads")
async def list_threads(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(default=None),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.list_message_threads(uis_user)
            data["source"] = "UIS"
            return data
        except uis_client.UisClientError:
            pass
    uid = _uid(user)
    role = user.get("role")
    q = select(MessageThread).options(selectinload(MessageThread.messages)).order_by(MessageThread.updated_at.desc())
    if role in ("admin", "super_admin"):
        pass  # see all
    elif role == "faculty":
        q = q.where(
            or_(
                MessageThread.assignee_id == uid,
                MessageThread.created_by == uid,
            )
        )
    else:
        q = q.where(MessageThread.created_by == uid)
    if status:
        q = q.where(MessageThread.status == status)
    threads = (await db.execute(q.limit(80))).scalars().all()
    ids: set[int] = set()
    for t in threads:
        ids.add(t.created_by)
        if t.assignee_id:
            ids.add(t.assignee_id)
        for m in t.messages or []:
            ids.add(m.sender_id)
    users = await _load_users(db, ids)
    return {"threads": [_serialize_thread(t, users) for t in threads]}


@router.post("/messages/threads")
async def create_thread(
    body: ThreadCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = _uid(user)
    role = user.get("role")
    if role not in ("student", "faculty"):
        raise HTTPException(status_code=403, detail="Students and faculty can open issues")
    uis_user = await linked_uis_username(db, user)
    if role == "student":
        from app.services import consent as consents

        if uis_user:
            try:
                await consents.sync_from_uis(db, uid, uis_user)
            except Exception:
                pass
        if not await consents.is_allowed(db, uid, "messaging.inbox", uis_username=uis_user):
            raise HTTPException(
                status_code=403,
                detail="Messaging consent is revoked. Allow messaging.inbox in Privacy / UIS Consent to message staff or the hostel warden.",
            )
    if uis_user:
        # Ensure hostel category is set before UIS create
        payload = body.model_dump()
        if payload.get("to_role") == "hostel":
            payload["category"] = "hostel"
        try:
            return await uis_client.create_message_thread(uis_user, payload)
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc

    assignee_id = None
    if body.to_role == "faculty":
        fac = None
        for email in ("faculty@example.com", "faculty.demo@klu.ac.in", "arun.kumar@klu.ac.in"):
            fac = (
                await db.execute(select(User).where(User.role == Role.FACULTY, User.email == email))
            ).scalar_one_or_none()
            if fac:
                break
        if not fac:
            fac = (
                await db.execute(select(User).where(User.role == Role.FACULTY).order_by(User.id).limit(1))
            ).scalar_one_or_none()
        assignee_id = fac.id if fac else None
    elif body.to_role == "hostel":
        # Prefer UIS-linked warden when present locally
        warden = (
            await db.execute(
                select(User).where(User.uis_username == "warden.demo").limit(1)
            )
        ).scalar_one_or_none()
        if not warden:
            warden = (
                await db.execute(
                    select(User).where(User.role.in_([Role.ADMIN, Role.SUPER_ADMIN])).order_by(User.id).limit(1)
                )
            ).scalar_one_or_none()
        assignee_id = warden.id if warden else None
        if not assignee_id:
            raise HTTPException(
                status_code=400,
                detail="No hostel warden is available. Link UIS or ask admin to create a warden account.",
            )
    else:
        adm = (
            await db.execute(
                select(User).where(User.role.in_([Role.ADMIN, Role.SUPER_ADMIN])).order_by(User.id).limit(1)
            )
        ).scalar_one_or_none()
        assignee_id = adm.id if adm else None

    category = "hostel" if body.to_role == "hostel" else (body.category.strip() or "general")
    thread = MessageThread(
        subject=body.subject.strip(),
        category=category,
        created_by=uid,
        assignee_id=assignee_id,
        status="open",
    )
    db.add(thread)
    await db.flush()
    msg = DirectMessage(thread_id=thread.id, sender_id=uid, body=body.body.strip())
    db.add(msg)
    thread.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(thread, attribute_names=["messages"])
    id_set = {uid}
    if assignee_id:
        id_set.add(assignee_id)
    users = await _load_users(db, id_set)
    sender_name = users.get(uid).full_name if users.get(uid) else "Someone"
    if assignee_id and assignee_id != uid:
        await _create_notification(
            db,
            user_id=assignee_id,
            kind="message",
            title=f"New message from {sender_name}",
            body=f"{sender_name} messaged you: {thread.subject}",
            thread_id=thread.id,
        )
    payload = {"type": "thread_created", "thread": _serialize_thread(thread, users)}
    if assignee_id:
        await _notify(assignee_id, payload)
    await _notify(uid, payload)
    return payload["thread"]


@router.post("/messages/threads/{thread_id}/reply")
async def reply_thread(
    thread_id: int,
    body: ReplyIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            return await uis_client.reply_message_thread(uis_user, thread_id, body.body)
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    uid = _uid(user)
    role = user.get("role")
    thread = (
        await db.execute(
            select(MessageThread).where(MessageThread.id == thread_id).options(selectinload(MessageThread.messages))
        )
    ).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    is_faculty = role == "faculty"
    # Faculty may claim unassigned open threads; assigned peers' threads stay private
    allowed = (
        role in ("admin", "super_admin")
        or thread.created_by == uid
        or thread.assignee_id == uid
        or (is_faculty and thread.assignee_id is None)
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Not your thread")
    if is_faculty and thread.assignee_id is None:
        thread.assignee_id = uid
    msg = DirectMessage(thread_id=thread.id, sender_id=uid, body=body.body.strip())
    db.add(msg)
    thread.updated_at = datetime.utcnow()
    if role in ("admin", "super_admin", "faculty") and thread.status == "open":
        thread.status = "open"
    await db.flush()
    await db.refresh(thread, attribute_names=["messages"])
    ids = {thread.created_by, uid}
    if thread.assignee_id:
        ids.add(thread.assignee_id)
    users = await _load_users(db, ids)
    sender_name = users.get(uid).full_name if users.get(uid) else "Someone"
    # Notify everyone else on the thread (student sees faculty reply, faculty sees student reply)
    for target in ids:
        if target == uid:
            continue
        kind = "reply" if role in ("admin", "super_admin", "faculty") else "message"
        await _create_notification(
            db,
            user_id=target,
            kind=kind,
            title=f"Reply from {sender_name}" if kind == "reply" else f"Message from {sender_name}",
            body=f"{sender_name}: {(body.body.strip())[:120]}",
            thread_id=thread.id,
        )
    payload = {"type": "message", "thread": _serialize_thread(thread, users)}
    for target in ids:
        await _notify(target, payload)
    return payload["thread"]


@router.post("/messages/threads/{thread_id}/redirect")
async def redirect_thread(
    thread_id: int,
    body: RedirectIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    role = user.get("role")
    if role not in ("admin", "super_admin", "faculty"):
        raise HTTPException(status_code=403, detail="Staff only")
    # Faculty may only redirect students back to student login
    target = (body.redirected_to or "").strip()
    if role == "faculty" and target != "student_login":
        raise HTTPException(
            status_code=400,
            detail="Faculty can only redirect to student_login",
        )
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            return await uis_client.redirect_message_thread(
                uis_user, thread_id, redirected_to=target or "student_login", note=body.note
            )
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    thread = (
        await db.execute(
            select(MessageThread).where(MessageThread.id == thread_id).options(selectinload(MessageThread.messages))
        )
    ).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    redirect_to = target or "student_login"
    thread.redirected_to = redirect_to
    thread.status = "redirected"
    note = body.note.strip() or f"Redirected to {redirect_to}"
    db.add(DirectMessage(thread_id=thread.id, sender_id=_uid(user), body=f"[Redirect] {note}"))
    thread.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(thread, attribute_names=["messages"])
    ids = {thread.created_by, _uid(user)}
    if thread.assignee_id:
        ids.add(thread.assignee_id)
    users = await _load_users(db, ids)
    payload = {"type": "redirect", "thread": _serialize_thread(thread, users)}
    for uid_target in ids:
        await _notify(uid_target, payload)
    return payload["thread"]


@router.websocket("/messages/ws")
async def messages_ws(websocket: WebSocket):
    import base64

    # Prefer Sec-WebSocket-Protocol auth so we can reject before accept()
    token = ""
    chosen_proto = None
    raw_proto = websocket.headers.get("sec-websocket-protocol") or ""
    for part in raw_proto.split(","):
        p = part.strip()
        if p.startswith("cgpt."):
            try:
                pad = "=" * (-len(p[5:]) % 4)
                token = base64.urlsafe_b64decode(p[5:] + pad).decode("utf-8")
                chosen_proto = p
            except Exception:
                token = ""
            break

    if token:
        data = decode_token(token)
        purpose = (data or {}).get("purpose")
        if purpose and purpose != "access":
            await websocket.close(code=4401)
            return
        if not data or not str(data.get("sub", "")).isdigit():
            await websocket.close(code=4401)
            return
        await websocket.accept(subprotocol=chosen_proto)
        uid = int(data["sub"])
    else:
        # Fallback: accept then require auth JSON within 2s (no query-string tokens)
        await websocket.accept()
        try:
            first = await asyncio.wait_for(websocket.receive_json(), timeout=2)
            if isinstance(first, dict) and first.get("type") == "auth":
                token = str(first.get("token") or "")
        except Exception:
            await websocket.close(code=4401)
            return
        data = decode_token(token)
        purpose = (data or {}).get("purpose")
        if purpose and purpose != "access":
            await websocket.close(code=4401)
            return
        if not data or not str(data.get("sub", "")).isdigit():
            await websocket.close(code=4401)
            return
        uid = int(data["sub"])

    _subscribers.setdefault(uid, set()).add(websocket)
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        _subscribers.get(uid, set()).discard(websocket)
