"""Hostel warden APIs — leave queue, inmate attendance, and approvals."""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Complaint,
    HostelAllocation,
    HostelAttendance,
    HostelBlock,
    HostelLeave,
    Room,
    StudentProfile,
    User,
)
from app.security.auth import require_roles
from app.services.audit import write_audit

router = APIRouter(prefix="/api/v1/hostel", tags=["hostel"])


def _serialize_leave(leave: HostelLeave) -> dict:
    sp = leave.student
    user = sp.user if sp else None
    return {
        "id": leave.id,
        "student_id": sp.student_id if sp else None,
        "student_name": user.full_name if user else "",
        "section": sp.section if sp else "",
        "semester": sp.semester if sp else None,
        "from": leave.from_date.isoformat(),
        "to": leave.to_date.isoformat(),
        "reason": leave.reason,
        "destination": leave.destination or "",
        "status": leave.status,
        "source": leave.source or "uis",
        "decision_note": getattr(leave, "decision_note", "") or "",
        "faculty_status": getattr(leave, "faculty_status", "pending") or "pending",
        "hostel_status": getattr(leave, "hostel_status", "pending") or "pending",
    }


def _recompute_leave_status(leave: HostelLeave) -> None:
    fac = getattr(leave, "faculty_status", "pending") or "pending"
    hos = getattr(leave, "hostel_status", "pending") or "pending"
    if fac == "rejected" or hos == "rejected":
        leave.status = "rejected"
    elif fac == "approved" and hos == "approved":
        leave.status = "approved"
    else:
        leave.status = "pending"


@router.get("/dashboard")
async def dashboard(
    user: Annotated[User, Depends(require_roles("hostel_admin", "admin", "university_admin", "super_admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    leaves = (await db.execute(select(HostelLeave))).scalars().all()
    pending = sum(1 for l in leaves if l.status == "pending")
    approved = sum(1 for l in leaves if l.status == "approved")
    rejected = sum(1 for l in leaves if l.status == "rejected")
    allocations = (await db.execute(select(func.count()).select_from(HostelAllocation))).scalar() or 0
    open_complaints = (
        await db.execute(
            select(func.count())
            .select_from(Complaint)
            .where(
                Complaint.audience.in_(["hostel", "any"]),
                Complaint.status.in_(["open", "in_progress"]),
            )
        )
    ).scalar() or 0
    return {
        "welcome": f"Welcome, {user.full_name}",
        "role": user.role,
        "title": "Hostel Warden Office",
        "pending_leaves": pending,
        "approved_leaves": approved,
        "rejected_leaves": rejected,
        "total_leaves": len(leaves),
        "active_allocations": allocations,
        "open_hostel_complaints": open_complaints,
    }


@router.get("/leaves")
async def list_leaves(
    user: Annotated[User, Depends(require_roles("hostel_admin", "admin", "university_admin", "super_admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[str] = Query(default=None),
):
    q = (
        select(HostelLeave)
        .options(selectinload(HostelLeave.student).selectinload(StudentProfile.user))
        .order_by(HostelLeave.from_date.desc())
    )
    if status:
        q = q.where(HostelLeave.status == status)
    rows = (await db.execute(q)).scalars().all()
    return {"leaves": [_serialize_leave(r) for r in rows]}


class LeaveStatusUpdate(BaseModel):
    status: str = Field(pattern="^(approved|rejected|pending)$")
    note: str = ""


@router.post("/leaves/{leave_id}/status")
async def update_leave_status(
    leave_id: int,
    body: LeaveStatusUpdate,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(require_roles("hostel_admin", "admin", "university_admin", "super_admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.services.email_service import send_leave_status_email

    leave = (
        await db.execute(
            select(HostelLeave)
            .where(HostelLeave.id == leave_id)
            .options(selectinload(HostelLeave.student).selectinload(StudentProfile.user))
        )
    ).scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    leave.hostel_status = body.status
    # University admins may finalize both legs in one action
    if user.role in ("admin", "university_admin", "super_admin"):
        leave.faculty_status = body.status
    if body.note:
        leave.decision_note = (body.note or "")[:500]
    _recompute_leave_status(leave)
    await db.flush()
    await write_audit(
        db,
        actor="UIS Hostel Warden",
        user_ref=user.username,
        role=user.role,
        resource="hostel.leave",
        action="STATUS",
        purpose=f"leave:{leave_id} hostel->{body.status} overall={leave.status}"
        + (f" note:{body.note[:80]}" if body.note else ""),
        result="ALLOWED",
    )
    student_user = leave.student.user if leave.student else None
    email_queued = False
    if student_user and student_user.email and leave.status in ("approved", "rejected"):
        background_tasks.add_task(
            send_leave_status_email,
            student_user.email,
            student_user.full_name or "",
            status=leave.status,
            from_date=leave.from_date.isoformat(),
            to_date=leave.to_date.isoformat(),
            reason=leave.reason,
            destination=leave.destination or "",
            decided_by=user.full_name or user.username,
            decided_role=user.role,
        )
        email_queued = True
    return {"ok": True, "leave": _serialize_leave(leave), "email_sent": email_queued}


@router.get("/allocations")
async def list_allocations(
    user: Annotated[User, Depends(require_roles("hostel_admin", "admin", "university_admin", "super_admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (
        await db.execute(
            select(HostelAllocation).options(
                selectinload(HostelAllocation.student).selectinload(StudentProfile.user),
                selectinload(HostelAllocation.room).selectinload(Room.block).selectinload(HostelBlock.hostel),
            )
        )
    ).scalars().all()
    return {
        "allocations": [
            {
                "student_id": a.student.student_id,
                "name": a.student.user.full_name if a.student.user else "",
                "hostel": a.room.block.hostel.name,
                "block": a.room.block.name,
                "room": a.room.room_number,
                "bed": a.bed_no,
                "status": a.status,
            }
            for a in rows
        ]
    }


def _allocation_options():
    return (
        selectinload(HostelAllocation.student).selectinload(StudentProfile.user),
        selectinload(HostelAllocation.room).selectinload(Room.block).selectinload(HostelBlock.hostel),
    )


class AttendanceRow(BaseModel):
    student_id: str
    status: str = Field(pattern="^(P|A)$")


class AttendanceIn(BaseModel):
    entry_date: date
    rows: list[AttendanceRow]


@router.get("/attendance")
async def inmate_attendance(
    user: Annotated[User, Depends(require_roles("hostel_admin", "admin", "university_admin", "super_admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    entry_date: date = Query(...),
):
    allocations = (
        await db.execute(select(HostelAllocation).options(*_allocation_options()).order_by(HostelAllocation.id))
    ).scalars().all()
    profile_ids = [row.student_id for row in allocations]
    marked = {}
    if profile_ids:
        for record in (
            await db.execute(
                select(HostelAttendance).where(
                    HostelAttendance.entry_date == entry_date,
                    HostelAttendance.student_id.in_(profile_ids),
                )
            )
        ).scalars().all():
            marked[record.student_id] = record.status
    students = []
    for index, row in enumerate(allocations, start=1):
        student = row.student
        students.append(
            {
                "sno": index,
                "student_id": student.student_id if student else "",
                "name": student.user.full_name if student and student.user else "",
                "section": student.section if student else "",
                "hostel": row.room.block.hostel.name if row.room and row.room.block and row.room.block.hostel else "",
                "block": row.room.block.name if row.room and row.room.block else "",
                "room": row.room.room_number if row.room else "",
                "bed": row.bed_no,
                "status": marked.get(row.student_id, ""),
            }
        )
    return {"entry_date": entry_date.isoformat(), "students": students}


@router.post("/attendance")
async def save_inmate_attendance(
    body: AttendanceIn,
    user: Annotated[User, Depends(require_roles("hostel_admin", "admin", "university_admin", "super_admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    allocations = (await db.execute(select(HostelAllocation))).scalars().all()
    by_code = {}
    for row in allocations:
        student = (
            await db.execute(select(StudentProfile).where(StudentProfile.id == row.student_id))
        ).scalar_one_or_none()
        if student:
            by_code[student.student_id] = student.id
    saved = 0
    for item in body.rows:
        profile_id = by_code.get(item.student_id.strip())
        if not profile_id:
            raise HTTPException(status_code=400, detail=f"{item.student_id} is not a hostel inmate.")
        record = (
            await db.execute(
                select(HostelAttendance).where(
                    HostelAttendance.student_id == profile_id,
                    HostelAttendance.entry_date == body.entry_date,
                )
            )
        ).scalar_one_or_none()
        if record:
            record.status = item.status
        else:
            db.add(HostelAttendance(student_id=profile_id, entry_date=body.entry_date, status=item.status))
        saved += 1
    actor_name = user.username
    actor_role = user.role
    await write_audit(
        db,
        actor="UIS Hostel Warden",
        user_ref=actor_name,
        role=actor_role,
        resource="hostel.attendance",
        action="REGISTER",
        purpose=f"{body.entry_date.isoformat()} saved={saved}",
        result="ALLOWED",
    )
    return {"ok": True, "saved": saved}


@router.get("/students/{student_id}")
async def inmate_profile(
    student_id: str,
    user: Annotated[User, Depends(require_roles("hostel_admin", "admin", "university_admin", "super_admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    student = (
        await db.execute(
            select(StudentProfile)
            .where(StudentProfile.student_id == student_id)
            .options(selectinload(StudentProfile.user), selectinload(StudentProfile.program))
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    allocation = (
        await db.execute(
            select(HostelAllocation)
            .where(HostelAllocation.student_id == student.id)
            .options(selectinload(HostelAllocation.room).selectinload(Room.block).selectinload(HostelBlock.hostel))
        )
    ).scalar_one_or_none()
    if not allocation or not allocation.room or not allocation.room.block or not allocation.room.block.hostel:
        raise HTTPException(status_code=404, detail="This student is not a hostel inmate.")
    program = student.program
    programme = program.name if program else ""
    return {
        "student_id": student.student_id,
        "name": student.user.full_name if student.user else "",
        "programme": programme,
        "batch": student.batch,
        "section": student.section,
        "year": student.year,
        "semester": student.semester,
        "photo_url": student.photo_url or "",
        "hostel": allocation.room.block.hostel.name,
        "block": allocation.room.block.name,
        "room": allocation.room.room_number,
        "bed": allocation.bed_no,
    }
