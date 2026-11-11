"""Sidebar, hall-ticket exceptions, the institute gateway, payroll, and the fee register."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    FeePayment,
    GatewaySetting,
    HallTicketWaiver,
    NavLink,
    PayrollEntry,
    StudentFee,
    StudentProfile,
    User,
)
from app.security.auth import get_current_user, require_roles
from app.services.acknowledge import issue_acknowledgement
from app.services.confirm import PhraseIn, require_phrase

router = APIRouter(tags=["institute"])
EditRoles = require_roles("university_admin", "admin", "super_admin", "developer", "operator", "coe")
RecommendRoles = require_roles(
    "university_admin", "admin", "super_admin", "developer", "operator", "coe", "faculty", "hod", "school_dean", "director"
)
PROVIDERS = {"own", "razorpay", "cashfree", "billdesk", "none"}


async def _gateway(db: AsyncSession) -> GatewaySetting:
    row = (await db.execute(select(GatewaySetting).order_by(GatewaySetting.id))).scalars().first()
    if row:
        return row
    row = GatewaySetting(provider="own", merchant_name="KARE Institute Gateway")
    db.add(row)
    await db.flush()
    return row


def _gateway_public(row: GatewaySetting) -> dict:
    return {
        "provider": row.provider or "own",
        "merchant_name": row.merchant_name or "Institute gateway",
        "key_id": row.key_id or "",
        "secret_saved": bool(row.key_secret),
        "live_charges": bool(row.live_charges),
    }


@router.get("/api/v1/navigation")
async def my_navigation(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (
        await db.execute(
            select(NavLink).where(NavLink.role == user.role).order_by(NavLink.sort_order, NavLink.id)
        )
    ).scalars().all()
    visible = [row for row in rows if row.visible]
    return {
        "custom": bool(rows),
        "items": [
            {"id": row.id, "label": row.label, "href": row.href, "icon": row.icon or "file", "group": row.group_label or ""}
            for row in visible
        ],
    }


@router.get("/api/v1/admin/navigation")
async def list_navigation(
    _: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    role: str = "student",
):
    rows = (
        await db.execute(select(NavLink).where(NavLink.role == role).order_by(NavLink.sort_order, NavLink.id))
    ).scalars().all()
    return {
        "items": [
            {
                "id": row.id,
                "role": row.role,
                "label": row.label,
                "href": row.href,
                "icon": row.icon,
                "group": row.group_label,
                "sort_order": row.sort_order,
                "visible": row.visible,
            }
            for row in rows
        ]
    }


def _safe_href(raw: str) -> str:
    href = raw.strip()
    if not href.startswith("/") or href.startswith("//") or "\\" in href or ":" in href or ".." in href:
        raise HTTPException(status_code=400, detail="Use an address inside this site, starting with /")
    return href[:200]


class NavIn(BaseModel):
    role: str = "student"
    label: str = Field(min_length=1, max_length=80)
    href: str = Field(min_length=1, max_length=200)
    icon: str = "file"
    group: str = ""
    sort_order: int = 0
    visible: bool = True


class NavPatch(BaseModel):
    label: Optional[str] = None
    href: Optional[str] = None
    visible: Optional[bool] = None
    sort_order: Optional[int] = None
    group: Optional[str] = None


@router.post("/api/v1/admin/navigation")
async def create_nav(body: NavIn, _: Annotated[User, Depends(EditRoles)], db: Annotated[AsyncSession, Depends(get_db)]):
    row = NavLink(
        role=body.role.strip()[:32],
        label=body.label.strip(),
        href=_safe_href(body.href),
        icon=(body.icon or "file")[:32],
        group_label=(body.group or "")[:80],
        sort_order=body.sort_order,
        visible=body.visible,
    )
    db.add(row)
    await db.commit()
    return {"ok": True, "id": row.id}


@router.patch("/api/v1/admin/navigation/{item_id}")
async def update_nav(
    item_id: int,
    body: NavPatch,
    _: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(NavLink).where(NavLink.id == item_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Menu item not found")
    if body.label is not None:
        row.label = body.label.strip()[:80]
    if body.href is not None:
        row.href = _safe_href(body.href)
    if body.visible is not None:
        row.visible = body.visible
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    if body.group is not None:
        row.group_label = body.group[:80]
    await db.commit()
    return {"ok": True}


@router.delete("/api/v1/admin/navigation/{item_id}")
async def delete_nav(
    item_id: int,
    body: PhraseIn,
    _: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(NavLink).where(NavLink.id == item_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Menu item not found")
    require_phrase(body.confirm, row.label)
    await db.delete(row)
    await db.commit()
    return {"ok": True}


class WaiverIn(BaseModel):
    student_id: str
    reason: str = Field(min_length=3, max_length=500)
    source: str = "faculty"
    active: bool = True


@router.get("/api/v1/hall-ticket/waivers")
async def list_waivers(_: Annotated[User, Depends(RecommendRoles)], db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(HallTicketWaiver).order_by(HallTicketWaiver.id.desc()))).scalars().all()
    student_ids = [row.student_id for row in rows]
    students = {}
    if student_ids:
        found = (
            await db.execute(
                select(StudentProfile).where(StudentProfile.id.in_(student_ids)).options(selectinload(StudentProfile.user))
            )
        ).scalars().all()
        students = {row.id: row for row in found}
    return {
        "items": [
            {
                "id": row.id,
                "student_id": students[row.student_id].student_id if row.student_id in students else "",
                "name": students[row.student_id].user.full_name if row.student_id in students and students[row.student_id].user else "",
                "reason": row.reason,
                "recommended_by": row.recommended_by,
                "source": row.source,
                "active": row.active,
            }
            for row in rows
        ]
    }


@router.post("/api/v1/hall-ticket/waivers")
async def save_waiver(
    body: WaiverIn,
    user: Annotated[User, Depends(RecommendRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    source = body.source if body.source in {"faculty", "management"} else "faculty"
    student = (
        await db.execute(select(StudentProfile).where(StudentProfile.student_id == body.student_id.strip()))
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    row = (
        await db.execute(select(HallTicketWaiver).where(HallTicketWaiver.student_id == student.id))
    ).scalar_one_or_none()
    if row is None:
        row = HallTicketWaiver(student_id=student.id)
        db.add(row)
    row.reason = body.reason.strip()
    row.source = source
    row.recommended_by = user.full_name
    row.active = body.active
    await db.commit()
    return {"ok": True, "student_id": student.student_id, "active": row.active}


@router.get("/api/v1/finance/gateway")
async def public_gateway(_: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _gateway_public(await _gateway(db))


class GatewayIn(BaseModel):
    provider: str = "own"
    merchant_name: str = "KARE Institute Gateway"
    key_id: str = ""
    key_secret: str = ""
    live_charges: bool = False


@router.put("/api/v1/admin/finance/gateway")
async def save_gateway(
    body: GatewayIn,
    _: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _gateway(db)
    provider = body.provider.strip().lower()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Choose own, razorpay, cashfree, billdesk, or none")
    row.provider = provider
    row.merchant_name = body.merchant_name.strip()[:120] or "Institute gateway"
    row.key_id = body.key_id.strip()[:120]
    if body.key_secret.strip():
        row.key_secret = body.key_secret.strip()[:255]
    row.live_charges = body.live_charges
    await db.commit()
    return _gateway_public(row)


@router.get("/api/v1/admin/finance/transactions")
async def transactions(_: Annotated[User, Depends(EditRoles)], db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (
        await db.execute(
            select(FeePayment).options(selectinload(FeePayment.fee)).order_by(FeePayment.id.desc()).limit(200)
        )
    ).scalars().all()
    user_ids = [row.fee.user_id for row in rows if row.fee]
    people = {}
    if user_ids:
        found = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        people = {row.id: row for row in found}
    return {
        "items": [
            {
                "id": row.id,
                "receipt_no": row.receipt_no,
                "amount": row.amount,
                "method": row.method,
                "note": row.note,
                "title": row.fee.title if row.fee else "",
                "payer": people[row.fee.user_id].full_name if row.fee and row.fee.user_id in people else "",
                "email": people[row.fee.user_id].email if row.fee and row.fee.user_id in people else "",
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in rows
        ]
    }


class PayrollIn(BaseModel):
    username: str
    period: str = Field(min_length=4, max_length=16)
    gross: float = Field(ge=0)
    deduction: float = Field(ge=0, default=0)
    note: str = ""


@router.post("/api/v1/admin/finance/payroll")
async def create_payroll(
    body: PayrollIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    staff = (await db.execute(select(User).where(User.username == body.username.strip()))).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff account not found")
    net = round(body.gross - body.deduction, 2)
    if net < 0:
        raise HTTPException(status_code=400, detail="Deduction cannot exceed gross pay")
    row = PayrollEntry(
        user_id=staff.id,
        period=body.period.strip(),
        gross=body.gross,
        deduction=body.deduction,
        note=body.note.strip()[:255],
        status="paid",
    )
    db.add(row)
    await db.flush()
    ack = await issue_acknowledgement(
        db,
        user=staff,
        kind="payroll",
        title=f"Payslip {body.period.strip()}",
        summary=f"Gross {body.gross:.2f}. Deduction {body.deduction:.2f}. Net {net:.2f}. {body.note}".strip(),
        email=staff.email,
        status="paid",
        ref_key=f"payroll:{staff.id}:{body.period.strip()}",
    )
    return {"ok": True, "net": net, "acknowledgement": ack, "recorded_by": user.username}


@router.get("/api/v1/finance/payroll")
async def my_payroll(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (
        await db.execute(
            select(PayrollEntry).where(PayrollEntry.user_id == user.id).order_by(PayrollEntry.id.desc())
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": row.id,
                "period": row.period,
                "gross": row.gross,
                "deduction": row.deduction,
                "net": round((row.gross or 0) - (row.deduction or 0), 2),
                "note": row.note,
                "status": row.status,
            }
            for row in rows
        ]
    }
