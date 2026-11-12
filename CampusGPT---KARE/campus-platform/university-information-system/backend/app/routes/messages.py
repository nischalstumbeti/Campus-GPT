"""UIS messaging + notifications — shared SoR with Campus-GPT."""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AppNotification, DirectMessage, MessageAttachment, MessageRecipient, MessageThread, PeopleGroup, PeopleGroupMember, User
from app.security.auth import get_current_user, require_roles

_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "message_files"
_ALLOWED_EXT = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".png", ".jpg", ".jpeg", ".csv", ".xlsx"}
_MAX_BYTES = 8 * 1024 * 1024
_MAX_FILES = 5

router = APIRouter(prefix="/api/v1", tags=["messages"])

STAFF = (
    "faculty",
    "hod",
    "school_dean",
    "director",
    "operator",
    "coe",
    "developer",
    "admin",
    "university_admin",
    "super_admin",
    "hostel_admin",
)


class ThreadCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    category: str = "general"
    to_role: str = "admin"  # admin | faculty | hostel
    group_id: Optional[int] = None
    user_ids: list[int] = Field(default_factory=list)


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class RedirectIn(BaseModel):
    redirected_to: str
    note: str = ""


async def _load_users(db: AsyncSession, ids: set[int]) -> dict[int, User]:
    if not ids:
        return {}
    rows = (await db.execute(select(User).where(User.id.in_(list(ids))))).scalars().all()
    return {u.id: u for u in rows}


def _thread_load():
    return (
        selectinload(MessageThread.messages).selectinload(DirectMessage.attachments),
        selectinload(MessageThread.recipients),
    )


def _can_view(user: User, thread: MessageThread) -> bool:
    if user.role in ("admin", "university_admin", "super_admin"):
        return True
    if user.role == "hostel_admin" and (thread.category == "hostel" or thread.assignee_id == user.id):
        return True
    return thread.created_by == user.id or thread.assignee_id == user.id or any(
        row.user_id == user.id for row in (thread.recipients or [])
    )


async def _save_attachments(db: AsyncSession, message: DirectMessage, files: list[UploadFile] | None) -> None:
    uploads = [f for f in (files or []) if f and f.filename]
    if len(uploads) > _MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Attach at most {_MAX_FILES} files")
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for upload in uploads:
        original = Path(upload.filename or "file").name
        ext = Path(original).suffix.lower()
        if ext not in _ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"{original} is not an allowed file type")
        data = await upload.read()
        if len(data) > _MAX_BYTES:
            raise HTTPException(status_code=400, detail=f"{original} is larger than 8 MB")
        stored = f"{uuid.uuid4().hex}{ext}"
        (_UPLOAD_DIR / stored).write_bytes(data)
        db.add(
            MessageAttachment(
                message_id=message.id,
                filename=original[:255],
                stored_name=stored,
                content_type=upload.content_type or "application/octet-stream",
                size=len(data),
            )
        )


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
        "created_by_role": creator.role if creator else "",
        "assignee_id": t.assignee_id,
        "assignee_name": assignee.full_name if assignee else "",
        "audience_label": getattr(t, "audience_label", "") or "",
        "recipient_count": len(t.recipients or []),
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_name": (users.get(m.sender_id).full_name if users.get(m.sender_id) else ""),
                "body": m.body,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "read": m.read,
                "attachments": [
                    {
                        "id": a.id,
                        "filename": a.filename,
                        "size": a.size,
                        "content_type": a.content_type,
                    }
                    for a in (m.attachments or [])
                ],
            }
            for m in msgs
        ],
        "source": "UIS",
    }


async def _notify(
    db: AsyncSession,
    *,
    user_id: int,
    kind: str,
    title: str,
    body: str,
    thread_id: int | None = None,
    link: str = "/messages",
) -> None:
    if not user_id:
        return
    db.add(
        AppNotification(
            user_id=user_id,
            kind=kind,
            title=title[:200],
            body=(body or "")[:500],
            link=link,
            thread_id=thread_id,
            read=False,
        )
    )


@router.get("/messages/threads")
async def list_threads(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[str] = Query(default=None),
):
    q = select(MessageThread).options(*_thread_load()).order_by(MessageThread.updated_at.desc())
    mine = or_(
        MessageThread.created_by == user.id,
        MessageThread.assignee_id == user.id,
        MessageThread.id.in_(select(MessageRecipient.thread_id).where(MessageRecipient.user_id == user.id)),
    )
    if user.role in ("admin", "university_admin", "super_admin"):
        pass
    elif user.role in ("faculty", "hod", "school_dean", "director", "operator", "coe"):
        q = q.where(mine)
    elif user.role == "hostel_admin":
        q = q.where(or_(mine, MessageThread.category == "hostel"))
    else:
        q = q.where(mine)
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
    return {"threads": [_serialize_thread(t, users) for t in threads], "source": "UIS"}


async def _recipient(db: AsyncSession, to_role: str, category: str) -> tuple[Optional[int], str]:
    assignee_id = None
    if to_role == "faculty":
        for uname in ("faculty.demo", "arun.kumar"):
            fac = (await db.execute(select(User).where(User.username == uname))).scalar_one_or_none()
            if fac:
                assignee_id = fac.id
                break
        if not assignee_id:
            fac = (
                await db.execute(select(User).where(User.role.in_(["faculty", "hod"])).order_by(User.id).limit(1))
            ).scalar_one_or_none()
            assignee_id = fac.id if fac else None
    elif to_role == "hostel":
        w = (await db.execute(select(User).where(User.username == "warden.demo"))).scalar_one_or_none()
        if not w:
            w = (
                await db.execute(select(User).where(User.role == "hostel_admin").order_by(User.id).limit(1))
            ).scalar_one_or_none()
        assignee_id = w.id if w else None
        if not assignee_id:
            raise HTTPException(status_code=400, detail="No hostel warden account is available to receive messages")
    else:
        adm = (
            await db.execute(
                select(User).where(User.role.in_(["admin", "university_admin", "super_admin"])).order_by(User.id).limit(1)
            )
        ).scalar_one_or_none()
        assignee_id = adm.id if adm else None
    resolved = "hostel" if to_role == "hostel" else (category.strip() or "general")
    return assignee_id, resolved


def _group_family(groups: list[PeopleGroup], root_id: int) -> set[int]:
    ids = {root_id}
    growing = True
    while growing:
        growing = False
        for group in groups:
            if group.parent_id in ids and group.id not in ids:
                ids.add(group.id)
                growing = True
    return ids


async def _audience(db: AsyncSession, group_id: int | None, user_ids: list[int], sender_id: int) -> tuple[list[int], str]:
    chosen: set[int] = set()
    label_parts: list[str] = []
    if group_id:
        groups = list((await db.execute(select(PeopleGroup))).scalars().all())
        group = next((item for item in groups if item.id == group_id), None)
        if not group:
            raise HTTPException(status_code=404, detail="That group was not found")
        family = _group_family(groups, group.id)
        members = (
            await db.execute(select(PeopleGroupMember.user_id).where(PeopleGroupMember.group_id.in_(family)))
        ).scalars().all()
        chosen.update(int(item) for item in members)
        label_parts.append(group.name)
    if user_ids:
        rows = (
            await db.execute(select(User.id).where(User.id.in_(list({int(item) for item in user_ids})), User.is_active.is_(True)))
        ).scalars().all()
        chosen.update(int(item) for item in rows)
        label_parts.append(f"{len(rows)} selected")
    chosen.discard(sender_id)
    if not chosen:
        raise HTTPException(status_code=400, detail="Choose a group or at least one person")
    if len(chosen) > 300:
        raise HTTPException(status_code=400, detail="Choose 300 people or fewer")
    return sorted(chosen), ", ".join(label_parts)[:200]


async def _open_thread(
    db: AsyncSession,
    user: User,
    *,
    subject: str,
    body: str,
    to_role: str,
    category: str,
    group_id: int | None,
    user_ids: list[int],
    files: list[UploadFile] | None = None,
) -> dict:
    audience_ids: list[int] = []
    audience_label = ""
    if group_id or user_ids:
        if user.role not in STAFF:
            raise HTTPException(status_code=403, detail="Only faculty, staff, admin, and HoD can message a group or selected people")
        audience_ids, audience_label = await _audience(db, group_id, user_ids, user.id)
        category = "group"
        assignee_id = None
    else:
        assignee_id, category = await _recipient(db, to_role, category)
    thread = MessageThread(
        subject=subject.strip(),
        category=category,
        created_by=user.id,
        assignee_id=assignee_id,
        status="open",
        audience_label=audience_label,
    )
    db.add(thread)
    await db.flush()
    message = DirectMessage(thread_id=thread.id, sender_id=user.id, body=body.strip())
    db.add(message)
    await db.flush()
    if files:
        await _save_attachments(db, message, files)
    for person_id in audience_ids:
        db.add(MessageRecipient(thread_id=thread.id, user_id=person_id))
    thread.updated_at = datetime.utcnow()
    targets = set(audience_ids)
    if assignee_id:
        targets.add(assignee_id)
    targets.discard(user.id)
    for person_id in targets:
        await _notify(
            db,
            user_id=person_id,
            kind="message",
            title=f"New message from {user.full_name}",
            body=f"{user.full_name} messaged you: {thread.subject}",
            thread_id=thread.id,
        )
    await db.flush()
    return await _thread_out(db, thread.id)


async def _thread_out(db: AsyncSession, thread_id: int) -> dict:
    thread = (
        await db.execute(select(MessageThread).where(MessageThread.id == thread_id).options(*_thread_load()))
    ).scalar_one()
    ids = {thread.created_by}
    if thread.assignee_id:
        ids.add(thread.assignee_id)
    for message in thread.messages or []:
        ids.add(message.sender_id)
    return _serialize_thread(thread, await _load_users(db, ids))


@router.get("/messages/audience")
async def message_audience(
    user: Annotated[User, Depends(require_roles(*STAFF))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user.role not in STAFF:
        raise HTTPException(status_code=403, detail="Only faculty, staff, admin, and HoD can choose recipients")
    groups = list((await db.execute(select(PeopleGroup).order_by(PeopleGroup.id))).scalars().all())

    def path(group: PeopleGroup) -> str:
        names = [group.name]
        parent_id = group.parent_id
        seen = {group.id}
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            parent = next((item for item in groups if item.id == parent_id), None)
            if not parent:
                break
            names.append(parent.name)
            parent_id = parent.parent_id
        return " / ".join(reversed(names))

    people = (
        await db.execute(select(User).where(User.is_active.is_(True)).order_by(User.full_name).limit(300))
    ).scalars().all()
    return {
        "groups": [{"id": group.id, "name": path(group)} for group in groups],
        "users": [
            {"id": person.id, "name": person.full_name or person.username, "username": person.username, "role": person.role}
            for person in people
            if person.id != user.id
        ],
    }


@router.post("/messages/threads")
async def create_thread(
    body: ThreadCreate,
    user: Annotated[User, Depends(require_roles("student", *STAFF))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await _open_thread(
        db,
        user,
        subject=body.subject,
        body=body.body,
        to_role=body.to_role,
        category=body.category,
        group_id=body.group_id,
        user_ids=body.user_ids,
    )


FacultySend = require_roles(*STAFF)


@router.post("/messages/threads/with-files")
async def create_thread_with_files(
    user: Annotated[User, Depends(FacultySend)],
    db: Annotated[AsyncSession, Depends(get_db)],
    subject: str = Form(min_length=3, max_length=200),
    body: str = Form(default=""),
    to_role: str = Form(default="admin"),
    group_id: Optional[int] = Form(default=None),
    user_ids: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
):
    text = (body or "").strip()
    if not text and not any(f.filename for f in files):
        raise HTTPException(status_code=400, detail="Write a message or attach a file")
    if not text:
        text = "Please see the attached file."
    picked = [int(part) for part in user_ids.replace(" ", "").split(",") if part.isdigit()]
    return await _open_thread(
        db,
        user,
        subject=subject,
        body=text,
        to_role=to_role,
        category="general",
        group_id=group_id,
        user_ids=picked,
        files=files,
    )


@router.post("/messages/threads/{thread_id}/reply-with-files")
async def reply_with_files(
    thread_id: int,
    user: Annotated[User, Depends(FacultySend)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
):
    thread = (
        await db.execute(select(MessageThread).where(MessageThread.id == thread_id).options(*_thread_load()))
    ).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if not _can_view(user, thread) and not (
        user.role in ("faculty", "hod") and thread.assignee_id is None and thread.status in ("open", "pending", None, "")
    ):
        raise HTTPException(status_code=403, detail="Not your thread")
    if user.role in ("faculty", "hod") and thread.assignee_id is None:
        thread.assignee_id = user.id
    text = (body or "").strip()
    if not text and not any(f.filename for f in files):
        raise HTTPException(status_code=400, detail="Write a reply or attach a file")
    if not text:
        text = "Please see the attached file."
    message = DirectMessage(thread_id=thread.id, sender_id=user.id, body=text)
    db.add(message)
    await db.flush()
    await _save_attachments(db, message, files)
    thread.updated_at = datetime.utcnow()
    targets = {thread.created_by}
    if thread.assignee_id:
        targets.add(thread.assignee_id)
    targets.update(row.user_id for row in (thread.recipients or []))
    for target in targets:
        if target == user.id:
            continue
        await _notify(
            db,
            user_id=target,
            kind="reply",
            title=f"Reply from {user.full_name}",
            body=f"{user.full_name}: {text[:120]}",
            thread_id=thread.id,
        )
    await db.flush()
    return await _thread_out(db, thread.id)


@router.get("/messages/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(
            select(MessageAttachment)
            .where(MessageAttachment.id == attachment_id)
            .options(
                selectinload(MessageAttachment.message)
                .selectinload(DirectMessage.thread)
                .selectinload(MessageThread.recipients)
            )
        )
    ).scalar_one_or_none()
    if not row or not row.message or not row.message.thread:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not _can_view(user, row.message.thread):
        raise HTTPException(status_code=403, detail="Not your thread")
    path = _UPLOAD_DIR / row.stored_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File is missing")
    return FileResponse(path, filename=row.filename, media_type=row.content_type or "application/octet-stream")


@router.post("/messages/threads/{thread_id}/reply")
async def reply_thread(
    thread_id: int,
    body: ReplyIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    thread = (
        await db.execute(
            select(MessageThread).where(MessageThread.id == thread_id).options(*_thread_load())
        )
    ).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    is_admin = user.role in ("admin", "university_admin", "super_admin")
    is_hostel = user.role == "hostel_admin" and (
        thread.category == "hostel" or thread.assignee_id == user.id
    )
    # Faculty/HoD may claim unassigned open threads (parity with Campus-GPT)
    if (
        user.role in ("faculty", "hod")
        and thread.assignee_id is None
        and thread.status in ("open", "pending", None, "")
    ):
        thread.assignee_id = user.id
    allowed = (
        is_admin
        or is_hostel
        or thread.created_by == user.id
        or thread.assignee_id == user.id
        or any(row.user_id == user.id for row in (thread.recipients or []))
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Not your thread")
    is_staff = user.role in STAFF
    db.add(DirectMessage(thread_id=thread.id, sender_id=user.id, body=body.body.strip()))
    thread.updated_at = datetime.utcnow()
    await db.flush()
    targets = {thread.created_by, user.id}
    if thread.assignee_id:
        targets.add(thread.assignee_id)
    targets.update(row.user_id for row in (thread.recipients or []))
    for target in targets:
        if target == user.id:
            continue
        kind = "reply" if is_staff else "message"
        await _notify(
            db,
            user_id=target,
            kind=kind,
            title=f"{'Reply' if kind == 'reply' else 'Message'} from {user.full_name}",
            body=f"{user.full_name}: {body.body.strip()[:120]}",
            thread_id=thread.id,
            link="/messages",
        )
    await db.flush()
    await db.refresh(thread, attribute_names=["messages"])
    users = await _load_users(db, targets)
    return _serialize_thread(thread, users)


@router.post("/messages/threads/{thread_id}/redirect")
async def redirect_thread(
    thread_id: int,
    body: RedirectIn,
    user: Annotated[User, Depends(require_roles(*STAFF))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    thread = (
        await db.execute(
            select(MessageThread).where(MessageThread.id == thread_id).options(*_thread_load())
        )
    ).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    target = (body.redirected_to or "").strip() or "student_login"
    # Faculty / HoD: student login only (admin/warden may use other targets)
    if user.role in ("faculty", "hod") and target != "student_login":
        raise HTTPException(status_code=400, detail="Faculty can only redirect to student_login")
    # Reassign inbox so warden/faculty/admin actually see the thread
    new_assignee = None
    if target == "warden":
        new_assignee = (
            await db.execute(select(User).where(User.username == "warden.demo"))
        ).scalar_one_or_none() or (
            await db.execute(select(User).where(User.role == "hostel_admin").order_by(User.id).limit(1))
        ).scalar_one_or_none()
        thread.category = "hostel"
    elif target == "faculty":
        new_assignee = (
            await db.execute(select(User).where(User.username == "faculty.demo"))
        ).scalar_one_or_none() or (
            await db.execute(select(User).where(User.role.in_(["faculty", "hod"])).order_by(User.id).limit(1))
        ).scalar_one_or_none()
    elif target in ("admin", "admin_login"):
        new_assignee = (
            await db.execute(
                select(User).where(User.role.in_(["admin", "university_admin", "super_admin"])).order_by(User.id).limit(1)
            )
        ).scalar_one_or_none()
    elif target == "student_login":
        new_assignee = (
            await db.execute(select(User).where(User.id == thread.created_by))
        ).scalar_one_or_none()
    if new_assignee:
        thread.assignee_id = new_assignee.id
    thread.redirected_to = target
    thread.status = "redirected"
    note = body.note.strip() or f"Redirected to {target}"
    db.add(DirectMessage(thread_id=thread.id, sender_id=user.id, body=f"[Redirect] {note}"))
    thread.updated_at = datetime.utcnow()
    await _notify(
        db,
        user_id=thread.created_by,
        kind="reply",
        title=f"Issue redirected by {user.full_name}",
        body=note,
        thread_id=thread.id,
        link="/messages",
    )
    if new_assignee and new_assignee.id != thread.created_by:
        await _notify(
            db,
            user_id=new_assignee.id,
            kind="message",
            title=f"Thread redirected to you",
            body=note,
            thread_id=thread.id,
            link="/messages",
        )
    await db.flush()
    await db.refresh(thread, attribute_names=["messages"])
    ids = {thread.created_by, user.id}
    if thread.assignee_id:
        ids.add(thread.assignee_id)
    users = await _load_users(db, ids)
    return _serialize_thread(thread, users)


@router.get("/notifications")
async def list_notifications(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (
        await db.execute(
            select(AppNotification)
            .where(AppNotification.user_id == user.id)
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
        "source": "UIS",
    }


@router.post("/notifications/read-all")
async def mark_all_read(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await db.execute(
        update(AppNotification)
        .where(AppNotification.user_id == user.id, AppNotification.read == False)  # noqa: E712
        .values(read=True)
    )
    await db.flush()
    return {"ok": True}


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(
            select(AppNotification).where(AppNotification.id == notification_id, AppNotification.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row:
        row.read = True
        await db.flush()
    return {"ok": True}
