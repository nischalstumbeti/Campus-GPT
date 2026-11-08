"""Today home, action confirm, prefs, observability, demo login helpers."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fees import StudentFee
from app.models.messaging import MessageThread
from app.models.notifications import AppNotification
from app.models.platform import AuditEvent, NotificationPref, SyncOutbox
from app.models.user import User, Role
from app.services import uis_client
from app.services.agent_actions import submit_leave_to_uis
from app.services.audit_log import write_audit
from app.services.sync_queue import process_outbox
from app.services.uis_link import linked_uis_username
from app.utils.auth import get_current_user, require_admin, require_student, create_access_token
from app.utils.database import get_db
from app.utils.seed_academic import DEMO_PASSWORD

router = APIRouter()


class ConfirmActionIn(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)


class PrefsIn(BaseModel):
    email_messages: Optional[bool] = None
    email_fees: Optional[bool] = None
    email_leave: Optional[bool] = None
    inapp_messages: Optional[bool] = None
    inapp_fees: Optional[bool] = None
    inapp_leave: Optional[bool] = None


class DemoLoginIn(BaseModel):
    role: str = "student"  # student | faculty | admin


@router.get("/me/today")
async def student_today(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    """Student Today home: next class, fee due, unread messages, leave status."""
    uid = int(user["sub"])
    uis_user = await linked_uis_username(db, user)
    source = "UIS" if uis_user and uis_client.uis_enabled() else "local"

    next_class = None
    leave_status = None
    if uis_user and uis_client.uis_enabled():
        try:
            tt = await uis_client.get_timetable(uis_user)
            slots = tt.get("slots") or tt.get("timetable") or tt.get("items") or []
            if slots:
                next_class = slots[0]
        except uis_client.UisClientError:
            pass
        try:
            hostel = await uis_client.get_hostel(uis_user)
            leaves = hostel.get("leaves") or []
            if leaves:
                leave_status = leaves[0]
        except uis_client.UisClientError:
            pass

    fee_due = None
    fees = (
        await db.execute(select(StudentFee).where(StudentFee.user_id == uid).order_by(StudentFee.deadline))
    ).scalars().all()
    for f in fees:
        rem = max(0.0, (f.total_amount or 0) - (f.paid_amount or 0))
        if rem > 0.01:
            fee_due = {
                "title": f.title,
                "remaining": rem,
                "deadline": f.deadline,
                "status": f.status,
            }
            break
    if uis_user and uis_client.uis_enabled() and not fee_due:
        try:
            remote = await uis_client.get_student_fees(uis_user)
            for f in remote.get("fees") or []:
                if (f.get("remaining") or 0) > 0.01:
                    fee_due = {
                        "title": f.get("title"),
                        "remaining": f.get("remaining"),
                        "deadline": f.get("deadline"),
                        "status": f.get("status"),
                    }
                    break
            source = "UIS"
        except uis_client.UisClientError:
            pass

    unread = (
        await db.execute(
            select(func.count()).select_from(AppNotification).where(
                AppNotification.user_id == uid, AppNotification.read == False  # noqa: E712
            )
        )
    ).scalar() or 0
    if uis_user and uis_client.uis_enabled():
        try:
            notes = await uis_client.list_notifications(uis_user)
            unread = notes.get("unread") or unread
        except uis_client.UisClientError:
            pass

    return {
        "date": date.today().isoformat(),
        "uis_linked": bool(uis_user),
        "uis_username": uis_user,
        "source": source,
        "next_class": next_class,
        "fee_due": fee_due,
        "unread_notifications": unread,
        "unread_messages": unread,  # legacy alias for older UI
        "leave_status": leave_status,
    }


@router.get("/me/link-status")
async def link_status(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uis_user = await linked_uis_username(db, user)
    return {
        "uis_enabled": uis_client.uis_enabled(),
        "uis_linked": bool(uis_user),
        "uis_username": uis_user,
        "email": user.get("email"),
        "role": user.get("role"),
        "source": "UIS" if uis_user and uis_client.uis_enabled() else "local",
    }


@router.post("/actions/confirm")
async def confirm_action(
    body: ConfirmActionIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if body.type == "apply_leave":
        p = body.payload or {}
        result = await submit_leave_to_uis(
            db,
            user,
            from_date=str(p.get("from_date") or ""),
            to_date=str(p.get("to_date") or ""),
            reason=str(p.get("reason") or "Leave via Campus-GPT"),
            destination=str(p.get("destination") or ""),
        )
        await write_audit(
            db,
            user=user,
            action="CONFIRM_APPLY_LEAVE",
            resource="hostel.leave",
            detail=f"{p.get('from_date')}→{p.get('to_date')} ok={result.get('ok')}",
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("answer") or "Action failed")
        return result
    raise HTTPException(status_code=400, detail="Unknown action type")


@router.get("/me/notification-prefs")
async def get_prefs(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = int(user["sub"])
    row = (await db.execute(select(NotificationPref).where(NotificationPref.user_id == uid))).scalar_one_or_none()
    if not row:
        row = NotificationPref(user_id=uid)
        db.add(row)
        await db.flush()
    return {
        "email_messages": row.email_messages,
        "email_fees": row.email_fees,
        "email_leave": row.email_leave,
        "inapp_messages": row.inapp_messages,
        "inapp_fees": row.inapp_fees,
        "inapp_leave": getattr(row, "inapp_leave", True),
    }


@router.put("/me/notification-prefs")
async def put_prefs(
    body: PrefsIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = int(user["sub"])
    row = (await db.execute(select(NotificationPref).where(NotificationPref.user_id == uid))).scalar_one_or_none()
    if not row:
        row = NotificationPref(user_id=uid)
        db.add(row)
    data = body.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(row, k, v)
    await db.flush()
    await write_audit(db, user=user, action="UPDATE_PREFS", resource="notifications", detail=str(data))
    return await get_prefs(db=db, user=user)


@router.get("/admin/audit")
async def admin_audit(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
    limit: int = 80,
):
    rows = (
        await db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit))
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "actor_email": r.actor_email,
                "actor_role": r.actor_role,
                "action": r.action,
                "resource": r.resource,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/admin/observability")
async def observability(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    pending = (
        await db.execute(select(func.count()).select_from(SyncOutbox).where(SyncOutbox.status == "pending"))
    ).scalar() or 0
    failed = (
        await db.execute(select(func.count()).select_from(SyncOutbox).where(SyncOutbox.status == "failed"))
    ).scalar() or 0
    users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    threads = (await db.execute(select(func.count()).select_from(MessageThread))).scalar() or 0
    uis_ok = False
    if uis_client.uis_enabled():
        try:
            notices = await uis_client.get_announcements()
            uis_ok = True
            notice_count = len(notices)
        except Exception:
            notice_count = 0
    else:
        notice_count = 0
    return {
        "uis_enabled": uis_client.uis_enabled(),
        "uis_reachable": uis_ok,
        "uis_announcements": notice_count,
        "sync_pending": pending,
        "sync_failed": failed,
        "users": users,
        "message_threads": threads,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.post("/admin/sync/retry")
async def retry_sync(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    result = await process_outbox(db)
    await write_audit(db, user=user, action="SYNC_RETRY", resource="outbox", detail=str(result))
    return result


@router.get("/admin/fees/overdue.csv")
async def overdue_csv(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    uis_user = await linked_uis_username(db, user)
    rows = []
    if uis_user and uis_client.uis_enabled():
        try:
            data = await uis_client.list_fee_students(uis_user)
            for s in data.get("students") or []:
                if s.get("status") in ("due", "partial", "overdue") or (s.get("remaining") or 0) > 0:
                    rows.append(s)
        except uis_client.UisClientError:
            pass
    if not rows:
        fees = (await db.execute(select(StudentFee))).scalars().all()
        for f in fees:
            rem = max(0.0, (f.total_amount or 0) - (f.paid_amount or 0))
            if rem > 0.01:
                u = (await db.execute(select(User).where(User.id == f.user_id))).scalar_one_or_none()
                rows.append(
                    {
                        "student_name": u.full_name if u else "",
                        "student_email": u.email if u else "",
                        "title": f.title,
                        "remaining": rem,
                        "deadline": f.deadline,
                        "status": f.status,
                    }
                )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["student_name", "student_email", "title", "remaining", "deadline", "status"])
    for r in rows:
        w.writerow(
            [
                r.get("student_name") or "",
                r.get("student_email") or "",
                r.get("title") or "",
                r.get("remaining") or "",
                r.get("deadline") or "",
                r.get("status") or "",
            ]
        )
    await write_audit(db, user=user, action="EXPORT_OVERDUE", resource="fees", detail=f"rows={len(rows)}")
    data = buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=overdue_fees.csv"},
    )


@router.post("/demo/login")
async def demo_login(
    body: DemoLoginIn,
    db: AsyncSession = Depends(get_db),
):
    """One-click role demos for presentations."""
    from app.config import get_settings

    settings = get_settings()
    if settings.ENVIRONMENT.lower() == "production" or not settings.ALLOW_PUBLIC_DEMO:
        raise HTTPException(status_code=403, detail="Demo login disabled")
    role = (body.role or "student").lower()
    email_map = {
        "student": "student@example.com",
        "faculty": "faculty@example.com",
        "admin": "admin@example.com",
    }
    # Prefer linked institutional emails when present
    alt = {
        "student": "student.demo@klu.ac.in",
        "faculty": "faculty.demo@klu.ac.in",
        "admin": "admin.demo@klu.ac.in",
    }
    if role not in email_map:
        raise HTTPException(status_code=400, detail="role must be student|faculty|admin")
    user = None
    for email in (alt[role], email_map[role]):
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user:
            break
    if not user:
        raise HTTPException(status_code=404, detail=f"Demo {role} account missing — restart API to seed")
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": role_val,
            "email": user.email,
            "full_name": user.full_name or "",
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role_val,
        "full_name": user.full_name,
        "email": user.email,
        "message": f"Signed in as demo {role}",
    }


@router.post("/admin/demo/reset-hint")
async def demo_reset_hint(user: dict = Depends(require_admin)):
    return {
        "ok": True,
        "password": DEMO_PASSWORD,
        "accounts": [
            "student@example.com / student.demo@klu.ac.in",
            "faculty@example.com / faculty.demo@klu.ac.in",
            "admin@example.com / admin.demo@klu.ac.in",
        ],
        "note": "Restart Campus-GPT + UIS backends to reseed demo data if needed.",
    }
