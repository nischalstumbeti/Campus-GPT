"""UIS fees — system of record shared with Campus-GPT."""
from __future__ import annotations

import random
from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import FeePayment, FeePlan, FeeReminder, HostelAllocation, StudentFee, StudentProfile, User
from app.security.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/v1/fees", tags=["fees"])

# Fee administration is finance/admin scoped — not ordinary teaching faculty
FEE_ADMIN = ("hod", "admin", "university_admin", "super_admin", "hostel_admin")


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


def _receipt_no() -> str:
    return f"KARE-RCP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"


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
        "payments": [
            {
                "id": p.id,
                "amount": p.amount,
                "method": p.method,
                "note": p.note,
                "receipt_no": p.receipt_no or "",
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in (f.payments or [])
        ],
    }


async def _student_category(db: AsyncSession, user_id: int) -> str:
    profile = (
        await db.execute(select(StudentProfile).where(StudentProfile.user_id == user_id))
    ).scalar_one_or_none()
    if not profile:
        return "day_scholar"
    alloc = (
        await db.execute(select(HostelAllocation).where(HostelAllocation.student_id == profile.id))
    ).scalar_one_or_none()
    return "hostel" if alloc else "day_scholar"


class PlanIn(BaseModel):
    title: str
    category: str = "all"
    amount: float = Field(ge=0)
    deadline: str
    notes: str = ""
    assign_to_students: bool = True


class PayIn(BaseModel):
    amount: float = Field(gt=0)
    method: str = "mock_upi"
    note: str = ""


class ReminderIn(BaseModel):
    category: str = "all"
    message: str = "Your fee deadline is approaching. Kindly pay soon."
    student_user_id: Optional[int] = None


class FeeEditIn(BaseModel):
    total_amount: Optional[float] = None
    deadline: Optional[str] = None
    title: Optional[str] = None


@router.get("/mine")
async def my_fees(
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (
        await db.execute(
            select(StudentFee)
            .where(StudentFee.user_id == user.id)
            .options(selectinload(StudentFee.payments))
            .order_by(StudentFee.id.desc())
        )
    ).scalars().all()
    # Compute status for response only — do not dirty the session on GET
    serialized = []
    for f in rows:
        status = _fee_status(f.total_amount, f.paid_amount, f.deadline or "")
        item = _serialize_fee(f)
        item["status"] = status
        serialized.append(item)
    reminders = (
        await db.execute(
            select(FeeReminder).where(FeeReminder.user_id == user.id).order_by(FeeReminder.created_at.desc()).limit(20)
        )
    ).scalars().all()
    return {
        "fees": serialized,
        "reminders": [
            {
                "id": r.id,
                "message": r.message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "read": r.read,
            }
            for r in reminders
        ],
        "category": await _student_category(db, user.id),
        "source": "UIS",
    }


@router.post("/mine/{fee_id}/pay")
async def pay_fee(
    fee_id: int,
    body: PayIn,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    fee = (
        await db.execute(
            select(StudentFee)
            .where(StudentFee.id == fee_id, StudentFee.user_id == user.id)
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
    # Optimistic concurrency — works on SQLite where FOR UPDATE is a no-op
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
    receipt_no = _receipt_no()
    pay = FeePayment(
        fee_id=fee.id,
        amount=round(body.amount, 2),
        method=body.method,
        note=body.note.strip() or "UIS student payment",
        receipt_no=receipt_no,
    )
    db.add(pay)
    await db.flush()
    await db.refresh(fee)
    new_remaining = max(0.0, round((fee.total_amount or 0) - (fee.paid_amount or 0), 2))
    return {
        "ok": True,
        "fee": _serialize_fee(fee),
        "receipt": {
            "receipt_no": receipt_no,
            "student_name": user.full_name,
            "student_email": user.email,
            "fee_title": fee.title,
            "amount_paid": round(body.amount, 2),
            "total_amount": fee.total_amount,
            "paid_amount": fee.paid_amount,
            "remaining": new_remaining,
            "method": pay.method,
            "paid_at": pay.created_at.isoformat() if pay.created_at else datetime.utcnow().isoformat(),
            "status": fee.status,
        },
        "message": f"Payment successful. Receipt {receipt_no}",
        "source": "UIS",
    }


@router.get("/plans")
async def list_plans(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Optional[str] = Query(default=None),
):
    q = select(FeePlan).where(FeePlan.active == True).order_by(FeePlan.deadline)  # noqa: E712
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


@router.post("/plans")
async def create_plan(
    body: PlanIn,
    user: Annotated[User, Depends(require_roles(*FEE_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if body.category not in ("all", "hostel", "day_scholar", "bus"):
        raise HTTPException(status_code=400, detail="Invalid category")
    plan = FeePlan(
        title=body.title.strip(),
        category=body.category,
        amount=body.amount,
        deadline=body.deadline,
        notes=body.notes,
        created_by=user.id,
    )
    db.add(plan)
    await db.flush()
    assigned = 0
    if body.assign_to_students:
        students = (await db.execute(select(User).where(User.role == "student"))).scalars().all()
        for s in students:
            cat = await _student_category(db, s.id)
            if body.category == "all":
                target = cat
            elif body.category == "bus":
                target = "bus"
            elif body.category == cat:
                target = cat
            else:
                continue
            db.add(
                StudentFee(
                    user_id=s.id,
                    plan_id=plan.id,
                    title=plan.title,
                    category=target,
                    total_amount=plan.amount,
                    paid_amount=0,
                    deadline=plan.deadline,
                    status="due",
                )
            )
            assigned += 1
    return {"ok": True, "plan_id": plan.id, "assigned": assigned, "source": "UIS"}


@router.get("/students")
async def list_student_fees(
    user: Annotated[User, Depends(require_roles(*FEE_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
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
                "username": u.username if u else "",
                "user_id": f.user_id,
            }
        )
    return {"students": out, "count": len(out), "source": "UIS"}


@router.put("/students/{fee_id}")
async def staff_edit_fee(
    fee_id: int,
    body: FeeEditIn,
    user: Annotated[User, Depends(require_roles(*FEE_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    fee = (
        await db.execute(select(StudentFee).where(StudentFee.id == fee_id).options(selectinload(StudentFee.payments)))
    ).scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    if body.total_amount is not None:
        fee.total_amount = body.total_amount
    if body.deadline is not None:
        fee.deadline = body.deadline
    if body.title is not None:
        fee.title = body.title
    fee.status = _fee_status(fee.total_amount, fee.paid_amount, fee.deadline or "")
    await db.flush()
    return {"ok": True, "fee": _serialize_fee(fee)}


@router.post("/reminders")
async def trigger_reminders(
    body: ReminderIn,
    user: Annotated[User, Depends(require_roles(*FEE_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
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
                triggered_by=user.username,
            )
        )
        sent += 1
    await db.flush()
    return {"ok": True, "reminders_sent": sent, "source": "UIS"}
