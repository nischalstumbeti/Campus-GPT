"""Student complaints — raised by students; handled by faculty, warden, or admin."""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Complaint, CourseOffering, Enrollment, StudentProfile, User
from app.security.auth import require_roles
from app.services.acknowledge import issue_acknowledgement
from app.services.audit import write_audit

router = APIRouter(prefix="/api/v1/complaints", tags=["complaints"])

CATEGORY_AUDIENCE = {
    "hostel": "hostel",
    "mess": "hostel",
    "room": "hostel",
    "facility": "hostel",
    "academic": "faculty",
    "marks": "faculty",
    "attendance": "faculty",
    "faculty": "faculty",
    "general": "any",
    "other": "any",
}

STAFF_ROLES = (
    "faculty",
    "hod",
    "hostel_admin",
    "admin",
    "university_admin",
    "super_admin",
)


def _audience_for(category: str) -> str:
    return CATEGORY_AUDIENCE.get((category or "general").lower().strip(), "any")


def _serialize(c: Complaint) -> dict:
    sp = c.student
    user = sp.user if sp else None
    return {
        "id": c.id,
        "student_id": sp.student_id if sp else None,
        "student_name": user.full_name if user else "",
        "section": sp.section if sp else "",
        "category": c.category,
        "audience": c.audience,
        "subject": c.subject,
        "description": c.description,
        "status": c.status,
        "resolver_username": c.resolver_username,
        "resolver_role": c.resolver_role,
        "resolution_note": c.resolution_note or "",
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
    }


class ComplaintCreate(BaseModel):
    category: str = Field(default="general", max_length=32)
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)


class ComplaintUpdate(BaseModel):
    status: str = Field(pattern="^(open|in_progress|resolved|closed)$")
    resolution_note: str = Field(default="", max_length=2000)


async def _faculty_student_ids(user: User, db: AsyncSession) -> Optional[set[int]]:
    """None = no filter (hod/admin). set = only these profile PKs."""
    if user.role in ("hod", "admin", "university_admin", "super_admin"):
        return None
    if user.role != "faculty" or not user.faculty:
        return set()
    offering_ids = (
        await db.execute(select(CourseOffering.id).where(CourseOffering.faculty_id == user.faculty.id))
    ).scalars().all()
    if not offering_ids:
        return set()
    return set(
        (
            await db.execute(
                select(Enrollment.student_id).where(Enrollment.offering_id.in_(list(offering_ids))).distinct()
            )
        ).scalars().all()
    )


def _audience_filter_for_role(role: str) -> list[str]:
    if role == "hostel_admin":
        return ["hostel", "any"]
    if role in ("faculty", "hod"):
        return ["faculty", "any"]
    return ["hostel", "faculty", "any"]


@router.post("")
async def create_complaint(
    body: ComplaintCreate,
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    category = (body.category or "general").lower().strip()
    if category not in CATEGORY_AUDIENCE:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Use one of: {', '.join(sorted(CATEGORY_AUDIENCE))}",
        )
    complaint = Complaint(
        student_id=user.student.id,
        category=category,
        audience=_audience_for(category),
        subject=body.subject.strip(),
        description=(body.description or "").strip(),
        status="open",
    )
    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)
    # reload student for serialize
    complaint = (
        await db.execute(
            select(Complaint)
            .where(Complaint.id == complaint.id)
            .options(selectinload(Complaint.student).selectinload(StudentProfile.user))
        )
    ).scalar_one()
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="complaint",
        title="Complaint received",
        summary=f"Complaint {complaint.id}: {complaint.subject}\nCategory: {category}\nStatus: open",
        email=user.email,
    )
    await write_audit(
        db,
        actor="UIS Student",
        user_ref=user.username,
        role=user.role,
        resource="complaint",
        action="CREATE",
        purpose=f"complaint:{complaint.id}:{category}",
        result="ALLOWED",
    )
    return {"ok": True, "complaint": _serialize(complaint), "acknowledgement": ack}


@router.get("/mine")
async def my_complaints(
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not user.student:
        raise HTTPException(status_code=403, detail="Student profile required")
    rows = (
        await db.execute(
            select(Complaint)
            .where(Complaint.student_id == user.student.id)
            .options(selectinload(Complaint.student).selectinload(StudentProfile.user))
            .order_by(Complaint.created_at.desc())
        )
    ).scalars().all()
    return {"complaints": [_serialize(c) for c in rows]}


@router.get("")
async def list_complaints(
    user: Annotated[User, Depends(require_roles(*STAFF_ROLES))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[str] = Query(default=None),
    audience: Optional[str] = Query(default=None),
):
    q = (
        select(Complaint)
        .options(selectinload(Complaint.student).selectinload(StudentProfile.user))
        .order_by(Complaint.created_at.desc())
    )
    if status:
        q = q.where(Complaint.status == status)
    allowed_audiences = _audience_filter_for_role(user.role)
    if audience:
        if audience not in allowed_audiences and user.role not in ("admin", "university_admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Audience not allowed for your role")
        q = q.where(Complaint.audience == audience)
    else:
        q = q.where(Complaint.audience.in_(allowed_audiences))

    rows = (await db.execute(q)).scalars().all()

    if user.role == "faculty":
        allowed_students = await _faculty_student_ids(user, db)
        assert allowed_students is not None
        # Faculty: own-class academic/faculty complaints + campus-wide "any" still visible
        rows = [
            r
            for r in rows
            if r.audience == "any" or r.student_id in allowed_students
        ]

    return {"complaints": [_serialize(c) for c in rows], "role": user.role}


@router.post("/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: int,
    body: ComplaintUpdate,
    user: Annotated[User, Depends(require_roles(*STAFF_ROLES))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    complaint = (
        await db.execute(
            select(Complaint)
            .where(Complaint.id == complaint_id)
            .options(selectinload(Complaint.student).selectinload(StudentProfile.user))
        )
    ).scalar_one_or_none()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    allowed = _audience_filter_for_role(user.role)
    if complaint.audience not in allowed and user.role not in ("admin", "university_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="This complaint is routed to another office")

    if user.role == "faculty" and complaint.audience != "any":
        allowed_students = await _faculty_student_ids(user, db)
        if allowed_students is not None and complaint.student_id not in allowed_students:
            raise HTTPException(status_code=403, detail="Student not in your classes")

    complaint.status = body.status
    if body.resolution_note is not None:
        complaint.resolution_note = body.resolution_note.strip()
    complaint.resolver_username = user.username
    complaint.resolver_role = user.role
    complaint.updated_at = datetime.utcnow()
    if body.status in ("resolved", "closed"):
        complaint.resolved_at = datetime.utcnow()
    elif body.status in ("open", "in_progress"):
        complaint.resolved_at = None

    await db.commit()
    await db.refresh(complaint)
    await write_audit(
        db,
        actor=f"UIS {user.role}",
        user_ref=user.username,
        role=user.role,
        resource="complaint",
        action="STATUS",
        purpose=f"complaint:{complaint_id}->{body.status}",
        result="ALLOWED",
    )
    return {"ok": True, "complaint": _serialize(complaint)}
