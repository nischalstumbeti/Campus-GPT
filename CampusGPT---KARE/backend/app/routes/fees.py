"""Student fee payment (mock) + admin/faculty deadline management."""
from __future__ import annotations

import random
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fees import FeePayment, FeePlan, FeeReminder, StudentFee
from app.models.user import User
from app.models.privacy import HostelProfile
from app.utils.auth import get_current_user, require_student
from app.utils.database import get_db
from app.services import email_service as mail
from app.services import uis_client
from app.services.audit_log import write_audit
from app.services.uis_link import linked_uis_username

router = APIRouter()


def _uid(user: dict) -> int:
    return int(user["sub"])


def _fee_status(total: float, paid: float, deadline: str) -> str:
    if paid >= total - 0.01:
        return "paid"
    if deadline:
        try:
            if date.fromisoformat(deadline) < date.today() and paid < total:
                return "overdue"
        except ValueError:
            pass
    if paid > 0:
        return "partial"
    return "due"


def _make_receipt_no() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"KARE-RCP-{stamp}-{random.randint(1000, 9999)}"


def _serialize_payment(p: FeePayment) -> dict:
    return {
        "id": p.id,
        "amount": p.amount,
        "method": p.method,
        "note": p.note,
        "receipt_no": getattr(p, "receipt_no", None) or "",
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _serialize_fee(f: StudentFee) -> dict:
    remaining = max(0.0, round((f.total_amount or 0) - (f.paid_amount or 0), 2))
    return {
        "id": f.id,
        "title": f.title,
        "category": f.category,
        "total_amount": f.total_amount,
        "paid_amount": f.paid_amount,
        "remaining": remaining,
        "deadline": f.deadline,
        "status": f.status,
        "payments": [_serialize_payment(p) for p in (f.payments or [])],
    }


async def _student_category(db: AsyncSession, user_id: int) -> str:
    """Infer hostel / day_scholar; bus fees are assigned via plan targeting."""
    from app.models.academic import StudentProfile

    profile = (
        await db.execute(select(StudentProfile).where(StudentProfile.user_id == user_id))
    ).scalar_one_or_none()
    if not profile:
        return "day_scholar"
    hostel = (
        await db.execute(select(HostelProfile).where(HostelProfile.student_id == profile.id))
    ).scalar_one_or_none()
    if hostel:
        return "hostel"
    return "day_scholar"


class PlanIn(BaseModel):
    title: str
    category: str = "all"  # all | hostel | day_scholar | bus
    amount: float = Field(ge=0)
    deadline: str
    notes: str = ""
    assign_to_students: bool = True


class FeeEditIn(BaseModel):
    total_amount: Optional[float] = None
    deadline: Optional[str] = None
    editable_splits: Optional[int] = Field(default=None, ge=1, le=12)
    title: Optional[str] = None


class PayIn(BaseModel):
    amount: float = Field(gt=0)
    method: str = "mock_upi"
    note: str = ""


class ReminderIn(BaseModel):
    category: str = "all"
    message: str = "Your fee deadline is approaching. Kindly pay soon."
    student_user_id: Optional[int] = None


@router.get("/fees/mine")
async def my_fees(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    from app.services import consent as consents

    uid = _uid(user)
    if not await consents.is_allowed(db, uid, "financial.fees"):
        raise HTTPException(status_code=403, detail="Fee consent is off. Enable it in Privacy settings.")
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.get_student_fees(uis_user)
            data["source"] = "UIS"
            return data
        except uis_client.UisClientError:
            pass
    rows = (
        await db.execute(
            select(StudentFee)
            .where(StudentFee.user_id == uid)
            .options(selectinload(StudentFee.payments))
            .order_by(StudentFee.id.desc())
        )
    ).scalars().all()
    fees_out = []
    for f in rows:
        item = _serialize_fee(f)
        item["status"] = _fee_status(f.total_amount, f.paid_amount, f.deadline or "")
        fees_out.append(item)
    reminders = (
        await db.execute(
            select(FeeReminder).where(FeeReminder.user_id == uid).order_by(FeeReminder.created_at.desc()).limit(20)
        )
    ).scalars().all()
    return {
        "fees": fees_out,
        "reminders": [
            {
                "id": r.id,
                "message": r.message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "read": r.read,
            }
            for r in reminders
        ],
        "category": await _student_category(db, uid),
        "source": "local",
    }


@router.post("/fees/mine/{fee_id}/pay")
async def pay_fee(
    fee_id: int,
    body: PayIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    """Student pays any amount up to remaining; generates a fake receipt and updates balances."""
    from app.services import consent as consents

    uid = _uid(user)
    if not await consents.is_allowed(db, uid, "financial.fees"):
        raise HTTPException(
            status_code=403,
            detail="Fee consent is off. Enable Fees in Privacy / UIS Consent before paying.",
        )
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.pay_student_fee(
                uis_user, fee_id, amount=body.amount, method=body.method, note=body.note
            )
            data["source"] = "UIS"
            return data
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    fee = (
        await db.execute(
            select(StudentFee)
            .where(StudentFee.id == fee_id, StudentFee.user_id == uid)
            .options(selectinload(StudentFee.payments))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    remaining = max(0.0, (fee.total_amount or 0) - (fee.paid_amount or 0))
    if body.amount > remaining + 0.01:
        raise HTTPException(status_code=400, detail=f"Amount exceeds remaining {remaining}")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Enter a valid amount")

    from sqlalchemy import update

    paid_before = float(fee.paid_amount or 0)
    new_paid = round(paid_before + body.amount, 2)
    new_status = _fee_status(fee.total_amount, new_paid, fee.deadline or "")
    result = await db.execute(
        update(StudentFee)
        .where(StudentFee.id == fee.id, StudentFee.paid_amount == paid_before)
        .values(paid_amount=new_paid, status=new_status)
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=409, detail="Concurrent payment detected — please retry")

    receipt_no = _make_receipt_no()
    pay = FeePayment(
        fee_id=fee.id,
        amount=round(body.amount, 2),
        method=body.method or "mock_upi",
        note=body.note.strip() or "Student portal payment",
        receipt_no=receipt_no,
    )
    db.add(pay)
    await db.flush()
    await db.refresh(fee)
    new_remaining = max(0.0, round((fee.total_amount or 0) - (fee.paid_amount or 0), 2))
    student = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    receipt = {
        "receipt_no": receipt_no,
        "student_name": student.full_name if student else "",
        "student_email": student.email if student else "",
        "fee_title": fee.title,
        "amount_paid": round(body.amount, 2),
        "total_amount": fee.total_amount,
        "paid_amount": fee.paid_amount,
        "remaining": new_remaining,
        "method": pay.method,
        "paid_at": pay.created_at.isoformat() if pay.created_at else datetime.utcnow().isoformat(),
        "status": fee.status,
    }
    return {
        "ok": True,
        "fee": _serialize_fee(fee),
        "receipt": receipt,
        "message": f"Payment successful. Receipt {receipt_no}",
    }


@router.get("/fees/plans")
async def list_plans(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    category: Optional[str] = Query(default=None),
):
    q = select(FeePlan).where(FeePlan.active == True).order_by(FeePlan.deadline)
    if category and category != "all":
        q = q.where(FeePlan.category.in_([category, "all"]))
    rows = (await db.execute(q)).scalars().all()
    return {
        "plans": [
            {
                "id": p.id,
                "title": p.title,
                "category": p.category,
                "amount": p.amount,
                "deadline": p.deadline,
                "notes": p.notes,
            }
            for p in rows
        ]
    }


@router.post("/fees/plans")
async def create_plan(
    body: PlanIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Fee admin only")
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.create_fee_plan(uis_user, body.model_dump())
            data["source"] = "UIS"
            await write_audit(db, user=user, action="CREATE_FEE_PLAN", resource="fees", detail=body.title)
            return data
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    if body.category not in ("all", "hostel", "day_scholar", "bus"):
        raise HTTPException(status_code=400, detail="Invalid category")
    plan = FeePlan(
        title=body.title.strip(),
        category=body.category,
        amount=body.amount,
        deadline=body.deadline,
        notes=body.notes,
        created_by=_uid(user),
    )
    db.add(plan)
    await db.flush()

    assigned = 0
    if body.assign_to_students:
        from app.models.user import Role

        students = (await db.execute(select(User).where(User.role == Role.STUDENT))).scalars().all()
        for s in students:
            cat = await _student_category(db, s.id)
            if body.category == "all":
                target_cat = cat
            elif body.category == "bus":
                target_cat = "bus"
            elif body.category == cat:
                target_cat = cat
            else:
                continue
            db.add(
                StudentFee(
                    user_id=s.id,
                    plan_id=plan.id,
                    title=plan.title,
                    category=target_cat,
                    total_amount=plan.amount,
                    paid_amount=0,
                    deadline=plan.deadline,
                    status="due",
                    editable_splits=3 if target_cat != "bus" else 2,
                )
            )
            assigned += 1
    return {"ok": True, "plan_id": plan.id, "assigned": assigned}


@router.get("/fees/students")
async def list_student_fees(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    role = user.get("role")
    # Align with UIS FEE_ADMIN-style roles (no plain faculty)
    if role not in ("admin", "super_admin", "hod", "hostel_admin"):
        raise HTTPException(status_code=403, detail="Fee admin role required")
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.list_fee_students(uis_user, category=category, status=status)
            data["source"] = "UIS"
            return data
        except uis_client.UisClientError:
            pass
    q = select(StudentFee).options(selectinload(StudentFee.payments)).order_by(StudentFee.deadline)
    if category and category != "all":
        q = q.where(StudentFee.category == category)
    rows = (await db.execute(q)).scalars().all()
    out = []
    for f in rows:
        computed = _fee_status(f.total_amount, f.paid_amount, f.deadline or "")
        if status and computed != status:
            continue
        u = (await db.execute(select(User).where(User.id == f.user_id))).scalar_one_or_none()
        item = _serialize_fee(f)
        item["status"] = computed
        out.append(
            {
                **item,
                "student_name": u.full_name if u else "",
                "student_email": u.email if u else "",
                "user_id": f.user_id,
            }
        )
    return {"students": out, "count": len(out)}


@router.put("/fees/students/{fee_id}")
async def staff_edit_fee(
    fee_id: int,
    body: FeeEditIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Fee admin only")
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.staff_edit_fee(
                uis_user,
                fee_id,
                {
                    "total_amount": body.total_amount,
                    "deadline": body.deadline,
                    "title": body.title,
                },
            )
            data["source"] = "UIS"
            return data
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    fee = (
        await db.execute(select(StudentFee).where(StudentFee.id == fee_id).options(selectinload(StudentFee.payments)))
    ).scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    if body.total_amount is not None:
        fee.total_amount = body.total_amount
    if body.deadline is not None:
        fee.deadline = body.deadline
    if body.editable_splits is not None:
        fee.editable_splits = body.editable_splits
    if body.title is not None:
        fee.title = body.title
    fee.status = _fee_status(fee.total_amount, fee.paid_amount, fee.deadline or "")
    await db.flush()
    return {"ok": True, "fee": _serialize_fee(fee), "source": "local"}


@router.post("/fees/reminders")
async def trigger_fee_reminders(
    body: ReminderIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Admin trigger deadline reminders → student notification + email."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Fee admin only")
    uis_user = await linked_uis_username(db, user)
    if uis_user:
        try:
            data = await uis_client.trigger_fee_reminders(uis_user, body.model_dump())
            data["source"] = "UIS"
            return data
        except uis_client.UisClientError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail or str(exc)) from exc
    q = select(StudentFee).where(StudentFee.status.in_(["due", "partial", "overdue"]))
    if body.student_user_id:
        q = q.where(StudentFee.user_id == body.student_user_id)
    elif body.category and body.category != "all":
        q = q.where(StudentFee.category == body.category)
    fees = (await db.execute(q)).scalars().all()
    sent = 0
    for f in fees:
        msg = (
            f"{body.message} Fee: {f.title}. Amount due: "
            f"{max(0, round(f.total_amount - f.paid_amount, 2))}. Deadline: {f.deadline or 'not set'}."
        )
        db.add(
            FeeReminder(
                fee_id=f.id,
                user_id=f.user_id,
                message=msg,
                triggered_by=str(user.get("email") or user.get("sub")),
            )
        )
        u = (await db.execute(select(User).where(User.id == f.user_id))).scalar_one_or_none()
        if u and u.email:
            try:
                await mail.send_email(
                    u.email,
                    "Fee deadline reminder · Campus-GPT",
                    f"<p>{msg}</p><p>Triggered by {user.get('role')}.</p>",
                    text_body=msg,
                )
            except Exception:
                pass
        sent += 1
    await db.flush()
    return {"ok": True, "reminders_sent": sent}
