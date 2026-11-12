"""Campus-GPT integration APIs — auth, consent, minimization, audit."""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import (
    Achievement,
    Announcement,
    AttendanceRecord,
    AttendanceSession,
    Complaint,
    CourseOffering,
    Enrollment,
    ExamSchedule,
    FacultyAvailability,
    FacultyProfile,
    Grade,
    HostelAllocation,
    HostelBlock,
    HostelLeave,
    IntegrationConsent,
    StudentFee,
    Mark,
    Room,
    StudentProfile,
    TimetableSlot,
    User,
)
from app.security.auth import hash_password, verify_password, verify_password_async
from app.services.audit import write_audit
from app.services.payloads import serialize_timetable_slot

router = APIRouter(prefix="/api/v1/integration/campus-gpt", tags=["campus-gpt-integration"])
settings = get_settings()

RESOURCE_CONSENT = {
    "profile": "academic.credits",
    "attendance": "academic.attendance",
    "marks": "academic.marks",
    "grades": "academic.grades",
    "courses": "academic.courses",
    "timetable": "academic.timetable",
    "exams": "academic.exams",
    "hostel": "hostel.room",
    "achievements": "achievements.certs",
}

DEFAULT_CONSENT_KEYS = list(dict.fromkeys(RESOURCE_CONSENT.values())) + [
    "hostel.leave",
    "academic.cgpa",
    "academic.history",
    "fees.records",
    "messaging.inbox",
    "complaints.own",
]


STAFF_ROLES = ("faculty", "hod", "admin", "university_admin", "super_admin", "hostel_admin", "department_admin", "exam_admin")


async def ensure_student_consents(db: AsyncSession, user_id: int, status: str = "deny") -> None:
    """Seed missing consent rows as deny (opt-in)."""
    for key in DEFAULT_CONSENT_KEYS:
        exists = (
            await db.execute(
                select(IntegrationConsent).where(
                    IntegrationConsent.user_id == user_id,
                    IntegrationConsent.permission_key == key,
                )
            )
        ).scalar_one_or_none()
        if not exists:
            db.add(IntegrationConsent(user_id=user_id, permission_key=key, status=status))



def _require_integration_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not x_api_key or x_api_key != settings.integration_api_key:
        raise HTTPException(status_code=401, detail="Invalid integration API key")
    return True


def _integration_key_ok(x_api_key: Optional[str]) -> bool:
    return bool(x_api_key and x_api_key == settings.integration_api_key)


async def _load_user(db: AsyncSession, username: str, *, require_student: bool) -> User:
    result = await db.execute(
        select(User)
        .where(User.username == username)
        .options(
            selectinload(User.student).selectinload(StudentProfile.program),
            selectinload(User.faculty),
        )
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found for identity")
    if require_student and not user.student:
        raise HTTPException(status_code=404, detail="Student not found for identity")
    return user


async def _resolve_subject_user(
    db: AsyncSession,
    *,
    authorization: Optional[str],
    x_uis_username: Optional[str],
    require_student: bool = True,
    allow_username_header: bool = True,
) -> User:
    """Identity from UIS user JWT (preferred). Username header only in non-production."""
    username = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            username = payload.get("sub")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid user token")
    elif x_uis_username and allow_username_header:
        # Impersonation header: development only — never in staging/production
        if settings.environment.lower() not in ("development", "dev", "local", "test"):
            raise HTTPException(
                status_code=401,
                detail="Bearer user JWT required (X-UIS-Username disabled outside development)",
            )
        username = x_uis_username
    if not username:
        raise HTTPException(status_code=401, detail="User identity required (Bearer user JWT)")

    return await _load_user(db, username, require_student=require_student)


async def _require_staff_user(
    db: AsyncSession,
    *,
    authorization: Optional[str],
    x_uis_username: Optional[str],
) -> User:
    """Staff/admin actions — Bearer user JWT required (no username-header impersonation)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Staff actions require Bearer user JWT")
    user = await _resolve_subject_user(
        db,
        authorization=authorization,
        x_uis_username=None,
        require_student=False,
        allow_username_header=False,
    )
    if user.role not in STAFF_ROLES and user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Staff role required")
    return user


async def _check_consent(db: AsyncSession, user_id: int, key: str) -> bool:
    result = await db.execute(
        select(IntegrationConsent).where(
            IntegrationConsent.user_id == user_id,
            IntegrationConsent.permission_key == key,
        )
    )
    row = result.scalar_one_or_none()
    return bool(row and row.status == "allow")


async def _gate(
    db: AsyncSession,
    user: User,
    resource: str,
    purpose: str,
):
    key = RESOURCE_CONSENT[resource]
    allowed = await _check_consent(db, user.id, key)
    await write_audit(
        db,
        actor="Campus-GPT Integration",
        user_ref=user.student.student_id,
        role=user.role,
        resource=resource,
        action="READ",
        purpose=purpose,
        result="ALLOWED" if allowed else "CONSENT_DENIED",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="CONSENT_DENIED")
    return user.student


@router.get("/student/profile")
async def student_profile(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Academic assistance"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    s = await _gate(db, user, "profile", purpose)
    return {
        "student_id": s.student_id,
        "name": user.full_name,
        "year": s.year,
        "semester": s.semester,
        "section": s.section,
        "batch": s.batch,
        "program": s.program.name if s.program else "B.Tech",
        "department": user.department_code or "",
        "cgpa": s.cgpa,
        "credits_completed": s.credits_completed,
        "credits_required": s.credits_required,
        "overall_attendance": s.overall_attendance,
        "backlogs": s.backlogs,
    }


@router.get("/student/attendance")
async def student_attendance(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Academic assistance"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    s = await _gate(db, user, "attendance", purpose)
    result = await db.execute(
        select(AttendanceRecord)
        .join(Enrollment)
        .where(Enrollment.student_id == s.id)
        .options(
            selectinload(AttendanceRecord.enrollment)
            .selectinload(Enrollment.offering)
            .selectinload(CourseOffering.course)
        )
    )
    records = result.scalars().all()
    # Minimized payload — no full profile
    return {
        "student_id": s.student_id,
        "attendance": [
            {
                "course": r.enrollment.offering.course.title,
                "code": r.enrollment.offering.course.code,
                "attended": r.attended,
                "total": r.total,
                "percentage": r.percentage,
            }
            for r in records
        ],
    }


@router.get("/student/marks")
async def student_marks(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Academic assistance"),
    target_student_id: Optional[str] = Query(default=None, description="Ignored for authorization — ABAC uses token identity only"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    # Reject attempts to read another student's data via query param
    if target_student_id and target_student_id != user.student.student_id:
        await write_audit(
            db,
            actor="Campus-GPT Integration",
            user_ref=user.student.student_id,
            role=user.role,
            resource="marks",
            action="READ",
            purpose=purpose,
            result="DENIED_ABAC",
        )
        raise HTTPException(status_code=403, detail="Cannot access another student's records")
    s = await _gate(db, user, "marks", purpose)
    result = await db.execute(
        select(Mark)
        .join(Enrollment)
        .where(Enrollment.student_id == s.id)
        .options(
            selectinload(Mark.enrollment).selectinload(Enrollment.offering).selectinload(CourseOffering.course)
        )
    )
    rows = result.scalars().all()
    return {
        "student_id": s.student_id,
        "marks": [
            {
                "course": m.enrollment.offering.course.title,
                "code": m.enrollment.offering.course.code,
                "assessment": m.assessment,
                "score": m.score,
                "max_score": m.max_score,
            }
            for m in rows
        ],
    }


@router.get("/student/grades")
async def student_grades(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Academic assistance"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    s = await _gate(db, user, "grades", purpose)
    result = await db.execute(
        select(Grade)
        .join(Enrollment)
        .where(Enrollment.student_id == s.id)
        .options(
            selectinload(Grade.enrollment).selectinload(Enrollment.offering).selectinload(CourseOffering.course)
        )
    )
    rows = result.scalars().all()
    return {
        "student_id": s.student_id,
        "grades": [
            {
                "course": g.enrollment.offering.course.title,
                "letter": g.letter,
                "grade_point": g.grade_point,
            }
            for g in rows
        ],
    }


@router.get("/student/courses")
async def student_courses(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Academic assistance"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    s = await _gate(db, user, "courses", purpose)
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.student_id == s.id)
        .options(selectinload(Enrollment.offering).selectinload(CourseOffering.course))
    )
    rows = result.scalars().all()
    return {
        "student_id": s.student_id,
        "courses": [{"code": e.offering.course.code, "title": e.offering.course.title, "credits": e.offering.course.credits} for e in rows],
    }


@router.get("/student/timetable")
async def student_timetable(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Academic assistance"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    s = await _gate(db, user, "timetable", purpose)
    offering_ids = [
        r[0]
        for r in (await db.execute(select(Enrollment.offering_id).where(Enrollment.student_id == s.id))).all()
    ]
    if not offering_ids:
        return {"student_id": s.student_id, "slots": []}
    slots = (
        await db.execute(
            select(TimetableSlot)
            .where(TimetableSlot.offering_id.in_(offering_ids))
            .options(
                selectinload(TimetableSlot.offering).selectinload(CourseOffering.course),
                selectinload(TimetableSlot.offering)
                .selectinload(CourseOffering.faculty)
                .selectinload(FacultyProfile.user),
            )
        )
    ).scalars().all()
    return {
        "student_id": s.student_id,
        "slots": [serialize_timetable_slot(sl) for sl in slots],
    }


@router.get("/student/exams")
async def student_exams(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Academic assistance"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    s = await _gate(db, user, "exams", purpose)
    enrolls = (
        await db.execute(
            select(Enrollment).where(Enrollment.student_id == s.id).options(selectinload(Enrollment.offering))
        )
    ).scalars().all()
    course_ids = [e.offering.course_id for e in enrolls]
    if not course_ids:
        return {"student_id": s.student_id, "exams": []}
    exams = (
        await db.execute(
            select(ExamSchedule).where(ExamSchedule.course_id.in_(course_ids)).options(selectinload(ExamSchedule.course))
        )
    ).scalars().all()
    return {
        "student_id": s.student_id,
        "exams": [
            {
                "course": e.course.title,
                "type": e.exam_type,
                "date": e.exam_date.isoformat(),
                "venue": e.venue,
            }
            for e in exams
        ],
    }


@router.get("/student/residence")
async def student_residence(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
):
    """Hostel vs day-scholar/bus — identity only (no hostel.room consent required)."""
    from app.models import StudentFee

    user = await _resolve_subject_user(
        db, authorization=authorization, x_uis_username=x_uis_username, require_student=True
    )
    s = user.student
    if not s:
        raise HTTPException(status_code=404, detail="Student profile required")
    alloc = (
        await db.execute(select(HostelAllocation.id).where(HostelAllocation.student_id == s.id).limit(1))
    ).scalar_one_or_none()
    if alloc:
        return {
            "student_id": s.student_id,
            "residence": "hostel",
            "is_hosteller": True,
            "source": "UIS",
        }
    # Bus students: have a bus-category fee without hostel allocation
    bus_fee = (
        await db.execute(
            select(StudentFee.id).where(StudentFee.user_id == user.id, StudentFee.category == "bus").limit(1)
        )
    ).scalar_one_or_none()
    residence = "bus" if bus_fee else "day_scholar"
    return {
        "student_id": s.student_id,
        "residence": residence,
        "is_hosteller": False,
        "source": "UIS",
    }


@router.get("/student/hostel")
async def student_hostel(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Hostel assistance"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    s = await _gate(db, user, "hostel", purpose)
    leave_allowed = await _check_consent(db, user.id, "hostel.leave")
    alloc = (
        await db.execute(
            select(HostelAllocation)
            .where(HostelAllocation.student_id == s.id)
            .options(selectinload(HostelAllocation.room).selectinload(Room.block).selectinload(HostelBlock.hostel))
        )
    ).scalar_one_or_none()
    leaves = []
    if leave_allowed:
        leaves = (
            await db.execute(
                select(HostelLeave).where(HostelLeave.student_id == s.id).order_by(HostelLeave.from_date.desc())
            )
        ).scalars().all()
    return {
        "student_id": s.student_id,
        "room": {
            "hostel": alloc.room.block.hostel.name,
            "room": alloc.room.room_number,
            "bed": alloc.bed_no,
        }
        if alloc
        else None,
        "leaves": [
            {
                "id": l.id,
                "from": l.from_date.isoformat(),
                "to": l.to_date.isoformat(),
                "reason": l.reason,
                "destination": l.destination or "",
                "status": l.status,
                "source": l.source or "uis",
            }
            for l in leaves
        ],
    }


class IntegrationLeaveIn(BaseModel):
    from_date: date
    to_date: date
    reason: str = Field(min_length=2, max_length=255)
    destination: str = ""


@router.post("/student/leave")
async def create_student_leave(
    body: IntegrationLeaveIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Hostel leave application"),
):
    """Campus-GPT applies leave into UIS — visible to student, faculty, and warden."""
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    from app.models import IntegrationConsent

    leave_ok = await _check_consent(db, user.id, "hostel.leave")
    if not leave_ok:
        await ensure_student_consents(db, user.id, "deny")
        await write_audit(
            db,
            actor="Campus-GPT Integration",
            user_ref=user.username,
            role=user.role,
            resource="hostel.leave",
            action="APPLY",
            purpose=purpose,
            result="CONSENT_DENIED",
        )
        raise HTTPException(status_code=403, detail="CONSENT_DENIED: hostel.leave")

    s = user.student
    if not s:
        raise HTTPException(status_code=404, detail="Student profile missing")

    if body.to_date < body.from_date:
        raise HTTPException(status_code=400, detail="to_date must be on or after from_date")

    leave = HostelLeave(
        student_id=s.id,
        from_date=body.from_date,
        to_date=body.to_date,
        reason=body.reason.strip(),
        destination=(body.destination or "").strip(),
        status="pending",
        source="campus-gpt",
    )
    db.add(leave)
    await db.commit()
    await db.refresh(leave)
    await write_audit(
        db,
        actor="Campus-GPT",
        user_ref=user.username,
        role="integration",
        resource="hostel.leave",
        action="APPLY",
        purpose=purpose,
        result="ALLOWED",
    )
    return {
        "ok": True,
        "leave": {
            "id": leave.id,
            "from": leave.from_date.isoformat(),
            "to": leave.to_date.isoformat(),
            "reason": leave.reason,
            "destination": leave.destination or "",
            "status": leave.status,
            "source": leave.source,
        },
    }


@router.get("/student/achievements")
async def student_achievements(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Career assistance"),
):
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    s = await _gate(db, user, "achievements", purpose)
    rows = (await db.execute(select(Achievement).where(Achievement.student_id == s.id))).scalars().all()
    return {
        "student_id": s.student_id,
        "achievements": [
            {
                "title": a.title,
                "category": a.category,
                "description": a.description or "",
                "awarded_on": a.awarded_on.isoformat() if a.awarded_on else None,
            }
            for a in rows
        ],
    }


@router.get("/student/complaints")
async def student_complaints(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
    x_uis_username: Optional[str] = Header(default=None, alias="X-UIS-Username"),
    purpose: str = Query(default="Complaint assistance"),
):
    """Campus-GPT reads the student's own UIS complaints (status + resolution)."""
    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    if not user.student:
        raise HTTPException(status_code=404, detail="Student profile required")
    allowed = await _check_consent(db, user.id, "complaints.own")
    await write_audit(
        db,
        actor="Campus-GPT",
        user_ref=user.username,
        role="integration",
        resource="complaint",
        action="READ",
        purpose=purpose,
        result="ALLOWED" if allowed else "CONSENT_DENIED",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="CONSENT_DENIED: complaints.own")
    s = user.student
    rows = (
        await db.execute(
            select(Complaint).where(Complaint.student_id == s.id).order_by(Complaint.created_at.desc())
        )
    ).scalars().all()
    return {
        "student_id": s.student_id,
        "complaints": [
            {
                "id": c.id,
                "category": c.category,
                "audience": c.audience,
                "subject": c.subject,
                "description": c.description,
                "status": c.status,
                "resolution_note": c.resolution_note or "",
                "resolver_role": c.resolver_role,
            }
            for c in rows
        ],
    }


def _identity(user: User) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "student_id": user.student.student_id if user.student else None,
        "has_student_profile": bool(user.student),
        "has_faculty_profile": bool(user.faculty),
    }


@router.get("/resolve-identity")
async def resolve_identity(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    email: Optional[str] = Query(default=None, min_length=3),
    username: Optional[str] = Query(default=None, min_length=2),
):
    """Server-to-server: map Campus-GPT login email or UIS username → identity."""
    ident = (email or username or "").strip()
    if not ident:
        raise HTTPException(status_code=400, detail="email or username required")
    result = await db.execute(
        select(User)
        .where(or_(User.email == ident, User.username == ident))
        .options(selectinload(User.student), selectinload(User.faculty))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="No UIS user for identity")
    return _identity(user)


class CredentialCheck(BaseModel):
    username: str
    password: str


@router.post("/verify-credentials")
async def verify_credentials(
    body: CredentialCheck,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Campus-GPT sign-in: validate UIS username/email + password and return identity."""
    from app.utils.rate_limit import check_rate_limit

    check_rate_limit(f"verify-credentials:{(body.username or '').strip().lower()}", limit=20, window_seconds=60)
    ident = (body.username or "").strip()
    result = await db.execute(
        select(User)
        .where(or_(User.username == ident, User.email == ident))
        .options(selectinload(User.student), selectinload(User.faculty))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not await verify_password_async(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _identity(user)


@router.post("/verify-session")
async def verify_session(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
):
    """Campus-GPT SSO: accept a UIS user JWT and return identity."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="UIS user token required")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid UIS token")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid UIS token")
    result = await db.execute(
        select(User)
        .where(User.username == username)
        .options(selectinload(User.student), selectinload(User.faculty))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or not found")
    return _identity(user)


class MintTokenIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)


@router.post("/mint-user-token")
async def mint_user_token(
    body: MintTokenIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Trusted Campus-GPT mints a short-lived UIS user JWT for delegated calls."""
    from app.security.auth import create_access_token

    user = await _load_user(db, body.username.strip(), require_student=False)
    token = create_access_token(
        {"sub": user.username, "role": user.role, "purpose": "access"},
        expires_minutes=30,
    )
    await write_audit(
        db,
        actor="Campus-GPT Integration",
        user_ref=user.username,
        role="service",
        resource="token",
        action="MINT_USER",
        purpose="campus_gpt_delegate",
        result="ALLOWED",
    )
    await db.flush()
    return {"access_token": token, "token_type": "bearer", "username": user.username, "role": user.role}


@router.get("/faculty")
async def faculty_directory(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Optional[str] = Query(default=None),
):
    """Public academic directory: office hours + teaching slots."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    avail = (
        await db.execute(
            select(FacultyAvailability).options(
                selectinload(FacultyAvailability.faculty).selectinload(FacultyProfile.user),
                selectinload(FacultyAvailability.faculty).selectinload(FacultyProfile.department),
            )
        )
    ).scalars().all()
    records = []
    needle = (q or "").lower()
    for row in avail:
        fac = row.faculty
        name = fac.user.full_name if fac and fac.user else ""
        dept = fac.department.code if fac and fac.department else ""
        if needle and needle not in name.lower() and needle not in dept.lower():
            continue
        records.append(
            {
                "faculty": name,
                "designation": fac.designation if fac else "",
                "department": dept,
                "cabin": row.location,
                # Public directory: cabin/hours only — no personal email
                "day": row.day_of_week,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "kind": row.kind,
                "location": row.location,
                "notes": row.notes,
            }
        )
    offerings = (
        await db.execute(
            select(CourseOffering).options(
                selectinload(CourseOffering.course),
                selectinload(CourseOffering.faculty).selectinload(FacultyProfile.user),
                selectinload(CourseOffering.faculty).selectinload(FacultyProfile.department),
            )
        )
    ).scalars().all()
    offering_ids = [o.id for o in offerings]
    slots = []
    if offering_ids:
        slots = (
            await db.execute(select(TimetableSlot).where(TimetableSlot.offering_id.in_(offering_ids)))
        ).scalars().all()
    off_map = {o.id: o for o in offerings}
    for sl in slots:
        off = off_map.get(sl.offering_id)
        if not off or not off.faculty:
            continue
        name = off.faculty.user.full_name if off.faculty.user else ""
        dept = off.faculty.department.code if off.faculty.department else ""
        if needle and needle not in name.lower() and needle not in (off.course.code or "").lower():
            continue
        records.append(
            {
                "faculty": name,
                "designation": off.faculty.designation,
                "department": dept,
                "cabin": sl.room,
                "day": days[sl.day_of_week] if 0 <= sl.day_of_week < 7 else str(sl.day_of_week),
                "start_time": sl.start_time,
                "end_time": sl.end_time,
                "kind": "class",
                "location": sl.room,
                "notes": f"{off.course.code} · {off.course.title} · Sec {off.section}",
            }
        )
    return {"records": records}


@router.get("/announcements")
async def integration_announcements(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    role: Optional[str] = Query(default=None, description="Filter by viewer role: student|faculty|all"),
    department_code: Optional[str] = Query(default=None),
):
    from app.models import Announcement

    rows = (
        await db.execute(select(Announcement).order_by(Announcement.published_at.desc()).limit(80))
    ).scalars().all()
    role_l = (role or "").lower().strip()
    dept = (department_code or "").upper().strip()
    items = []
    for n in rows:
        aud = (n.audience or "all").lower()
        if role_l and aud not in ("all", role_l, ""):
            continue
        if dept and n.department_code and (n.department_code or "").upper() != dept:
            continue
        items.append(
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "audience": n.audience,
                "department_code": n.department_code,
                "published_at": n.published_at.isoformat() if n.published_at else None,
                "source": "UIS Announcements",
            }
        )
        if len(items) >= 40:
            break
    return {"items": items}


class ConsentUpdate(BaseModel):
    permission_key: str
    status: str  # allow | deny | revoke


@router.get("/consents")
async def list_consents(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    """Own consents for the signed-in portal user, or Campus-GPT sync with the integration key."""
    if not _integration_key_ok(x_api_key) and not (authorization and authorization.lower().startswith("bearer ")):
        raise HTTPException(status_code=401, detail="Sign in required")
    user = await _resolve_subject_user(
        db,
        authorization=authorization,
        x_uis_username=x_uis_username if _integration_key_ok(x_api_key) else None,
        require_student=False,
        allow_username_header=_integration_key_ok(x_api_key),
    )
    if user.role == "student":
        await ensure_student_consents(db, user.id, status="deny")
    rows = (
        await db.execute(select(IntegrationConsent).where(IntegrationConsent.user_id == user.id))
    ).scalars().all()
    return {
        "items": [{"permission_key": r.permission_key, "status": r.status} for r in rows],
        "source": "UIS",
    }


@router.put("/consents")
async def update_consent(
    body: ConsentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    if body.status not in ("allow", "deny", "revoke"):
        raise HTTPException(status_code=400, detail="Invalid status")
    if not _integration_key_ok(x_api_key) and not (authorization and authorization.lower().startswith("bearer ")):
        raise HTTPException(status_code=401, detail="Sign in required")
    user = await _resolve_subject_user(
        db,
        authorization=authorization,
        x_uis_username=x_uis_username if _integration_key_ok(x_api_key) else None,
        require_student=False,
        allow_username_header=_integration_key_ok(x_api_key),
    )
    result = await db.execute(
        select(IntegrationConsent).where(
            IntegrationConsent.user_id == user.id,
            IntegrationConsent.permission_key == body.permission_key,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.status = body.status
    else:
        db.add(IntegrationConsent(user_id=user.id, permission_key=body.permission_key, status=body.status))
    await write_audit(
        db,
        actor="Campus-GPT Integration",
        user_ref=user.username,
        role=user.role,
        resource="consent",
        action="UPDATE",
        purpose=body.permission_key,
        result=body.status.upper(),
    )
    await db.flush()
    return {"ok": True, "permission_key": body.permission_key, "status": body.status, "source": "UIS"}


# --- Shared fees / messages for Campus-GPT (UIS is system of record) ---


class FeePayIn(BaseModel):
    amount: float = Field(gt=0)
    method: str = "mock_upi"
    note: str = ""


class ThreadCreateIn(BaseModel):
    subject: str
    body: str
    category: str = "general"
    to_role: str = "admin"


class ReplyIn(BaseModel):
    body: str


@router.get("/student/fees")
async def integration_student_fees(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
    purpose: str = Query(default="Fee assistance"),
):
    from app.routes import fees as fees_routes

    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Student only")
    if not await _check_consent(db, user.id, "fees.records"):
        await write_audit(
            db,
            actor="Campus-GPT Integration",
            user_ref=user.username,
            role=user.role,
            resource="fees",
            action="READ",
            purpose=purpose,
            result="CONSENT_DENIED",
        )
        raise HTTPException(status_code=403, detail="CONSENT_DENIED")
    return await fees_routes.my_fees(user=user, db=db)


@router.post("/student/fees/{fee_id}/pay")
async def integration_pay_fee(
    fee_id: int,
    body: FeePayIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
    purpose: str = Query(default="Fee payment"),
):
    from app.routes import fees as fees_routes

    user = await _resolve_subject_user(db, authorization=authorization, x_uis_username=x_uis_username)
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Student only")
    if not await _check_consent(db, user.id, "fees.records"):
        raise HTTPException(status_code=403, detail="CONSENT_DENIED")
    return await fees_routes.pay_fee(fee_id=fee_id, body=fees_routes.PayIn(**body.model_dump()), user=user, db=db)


@router.get("/messages/threads")
async def integration_list_threads(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import messages as msg_routes

    user = await _resolve_subject_user(
        db, authorization=authorization, x_uis_username=x_uis_username, require_student=False
    )
    if user.role == "student" and not await _check_consent(db, user.id, "messaging.inbox"):
        raise HTTPException(status_code=403, detail="CONSENT_DENIED")
    return await msg_routes.list_threads(user=user, db=db)


@router.post("/messages/threads")
async def integration_create_thread(
    body: ThreadCreateIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import messages as msg_routes

    user = await _resolve_subject_user(
        db, authorization=authorization, x_uis_username=x_uis_username, require_student=False
    )
    if user.role == "student" and not await _check_consent(db, user.id, "messaging.inbox"):
        raise HTTPException(status_code=403, detail="CONSENT_DENIED")
    return await msg_routes.create_thread(
        body=msg_routes.ThreadCreate(**body.model_dump()), user=user, db=db
    )


@router.post("/messages/threads/{thread_id}/reply")
async def integration_reply(
    thread_id: int,
    body: ReplyIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import messages as msg_routes

    user = await _resolve_subject_user(
        db, authorization=authorization, x_uis_username=x_uis_username, require_student=False
    )
    if user.role == "student" and not await _check_consent(db, user.id, "messaging.inbox"):
        raise HTTPException(status_code=403, detail="CONSENT_DENIED")
    return await msg_routes.reply_thread(
        thread_id=thread_id, body=msg_routes.ReplyIn(**body.model_dump()), user=user, db=db
    )


class FeePlanIn(BaseModel):
    title: str
    category: str = "all"
    amount: float = Field(ge=0)
    deadline: str
    notes: str = ""
    assign_to_students: bool = True


class FeeReminderIn(BaseModel):
    category: str = "all"
    message: str = "Your fee deadline is approaching. Kindly pay soon."
    student_user_id: Optional[int] = None


class RedirectIn(BaseModel):
    redirected_to: str
    note: str = ""


@router.get("/fees/students")
async def integration_fee_students(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    from app.routes import fees as fees_routes

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    return await fees_routes.list_student_fees(user=user, db=db, category=category, status=status)


@router.post("/fees/plans")
async def integration_create_fee_plan(
    body: FeePlanIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import fees as fees_routes

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    return await fees_routes.create_plan(body=fees_routes.PlanIn(**body.model_dump()), user=user, db=db)


@router.post("/fees/reminders")
async def integration_fee_reminders(
    body: FeeReminderIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import fees as fees_routes

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    return await fees_routes.trigger_reminders(
        body=fees_routes.ReminderIn(**body.model_dump()), user=user, db=db
    )


class FeeEditIn(BaseModel):
    total_amount: Optional[float] = None
    deadline: Optional[str] = None
    title: Optional[str] = None


@router.put("/fees/students/{fee_id}")
async def integration_staff_edit_fee(
    fee_id: int,
    body: FeeEditIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import fees as fees_routes

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    return await fees_routes.staff_edit_fee(
        fee_id=fee_id, body=fees_routes.FeeEditIn(**body.model_dump()), user=user, db=db
    )


@router.post("/messages/threads/{thread_id}/redirect")
async def integration_redirect(
    thread_id: int,
    body: RedirectIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import messages as msg_routes

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    return await msg_routes.redirect_thread(
        thread_id=thread_id, body=msg_routes.RedirectIn(**body.model_dump()), user=user, db=db
    )


@router.get("/notifications")
async def integration_notifications(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import messages as msg_routes

    # Notifications are for every role (student, faculty, warden, admin)
    user = await _resolve_subject_user(
        db, authorization=authorization, x_uis_username=x_uis_username, require_student=False
    )
    return await msg_routes.list_notifications(user=user, db=db)


@router.post("/notifications/read-all")
async def integration_notifications_read_all(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import messages as msg_routes

    user = await _resolve_subject_user(
        db, authorization=authorization, x_uis_username=x_uis_username, require_student=False
    )
    return await msg_routes.mark_all_read(user=user, db=db)


@router.post("/notifications/{notification_id}/read")
async def integration_notification_read(
    notification_id: int,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import messages as msg_routes

    user = await _resolve_subject_user(
        db, authorization=authorization, x_uis_username=x_uis_username, require_student=False
    )
    return await msg_routes.mark_read(notification_id=notification_id, user=user, db=db)


class MarqueeIn(BaseModel):
    icon: str = ""
    description: str
    link_url: str = ""
    active: bool = True
    sort_order: int = 0


class MarqueePatch(BaseModel):
    icon: Optional[str] = None
    description: Optional[str] = None
    link_url: Optional[str] = None
    active: Optional[bool] = None
    sort_order: Optional[int] = None


def _require_admin_subject(user) -> None:
    if user.role not in ("university_admin", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")


@router.get("/marquee")
async def integration_list_marquee(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import marquee as mq

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    _require_admin_subject(user)
    return await mq.list_marquees(user=user, db=db)


@router.get("/marquee/active")
async def integration_active_marquee(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    """Active marquee is public campus content."""
    from app.routes import marquee as mq

    _ = (authorization, x_uis_username)
    return await mq.active_marquees(db=db)


@router.post("/marquee")
async def integration_create_marquee(
    body: MarqueeIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import marquee as mq

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    _require_admin_subject(user)
    return await mq.create_marquee(body=mq.MarqueeIn(**body.model_dump()), user=user, db=db)


@router.put("/marquee/{item_id}")
async def integration_update_marquee(
    item_id: int,
    body: MarqueePatch,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import marquee as mq

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    _require_admin_subject(user)
    return await mq.update_marquee(
        item_id=item_id, body=mq.MarqueePatch(**body.model_dump()), user=user, db=db
    )


@router.delete("/marquee/{item_id}")
async def integration_delete_marquee(
    item_id: int,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    from app.routes import marquee as mq

    user = await _require_staff_user(db, authorization=authorization, x_uis_username=x_uis_username)
    _require_admin_subject(user)
    return await mq.delete_marquee(item_id=item_id, user=user, db=db)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=72)


@router.post("/change-password")
async def integration_change_password(
    body: ChangePasswordIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_uis_username: Annotated[Optional[str], Header(alias="X-UIS-Username")] = None,
):
    """Campus-GPT → UIS password sync (UIS remains credential SoR)."""
    from app.security.auth import hash_password

    user = await _resolve_subject_user(
        db, authorization=authorization, x_uis_username=x_uis_username, require_student=False
    )
    if not await verify_password_async(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    user.hashed_password = hash_password(body.new_password)
    await db.flush()
    return {
        "ok": True,
        "message": "Password updated in UIS",
        "username": user.username,
        "email": user.email,
        "source": "UIS",
    }


class ServiceSetPasswordIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    new_password: str = Field(min_length=6, max_length=72)


@router.post("/service-set-password")
async def service_set_password(
    body: ServiceSetPasswordIn,
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Campus-GPT password-reset sync — integration key only (no current password)."""
    user = (
        await db.execute(select(User).where(User.username == body.username.strip()))
    ).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(body.new_password)
    await write_audit(
        db,
        actor="Campus-GPT Integration",
        user_ref=user.username,
        role="service",
        resource="password",
        action="SERVICE_SET",
        purpose="password_reset_sync",
        result="ALLOWED",
    )
    await db.flush()
    return {"ok": True, "username": user.username, "source": "UIS"}


def _band(attended: int, total: int) -> str | None:
    if total <= 0:
        return None
    pct = 100.0 * attended / total
    if pct < 70:
        return "below_70"
    if pct < 75:
        return "watch_70_75"
    return "at_or_above_75"


@router.get("/campus-snapshot")
async def campus_snapshot(
    _: Annotated[bool, Depends(_require_integration_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Aggregate campus figures for Campus-GPT. No student names."""
    from datetime import datetime

    course_rows = (
        await db.execute(select(AttendanceRecord.attended, AttendanceRecord.total))
    ).all()
    bands = {"below_70": 0, "watch_70_75": 0, "at_or_above_75": 0, "counted": 0}
    for attended, total in course_rows:
        band = _band(int(attended or 0), int(total or 0))
        if not band:
            continue
        bands["counted"] += 1
        bands[band] += 1

    profiles = (await db.execute(select(StudentProfile.overall_attendance))).scalars().all()
    profile_bands = {"below_75": 0, "at_or_above_75": 0, "counted": 0}
    for raw in profiles:
        value = float(raw or 0)
        if value <= 0:
            continue
        profile_bands["counted"] += 1
        if value < 75:
            profile_bands["below_75"] += 1
        else:
            profile_bands["at_or_above_75"] += 1

    today_rows = (
        await db.execute(
            select(AttendanceSession.status, func.count())
            .where(AttendanceSession.entry_date == date.today())
            .group_by(AttendanceSession.status)
        )
    ).all()
    today = {str(status or "").upper(): int(count or 0) for status, count in today_rows}

    fee_rows = (
        await db.execute(select(StudentFee.status, func.count()).group_by(StudentFee.status))
    ).all()
    fees = {str(status or "unknown"): int(count or 0) for status, count in fee_rows}
    due_amount = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(StudentFee.total_amount - StudentFee.paid_amount), 0)).where(
                    StudentFee.status != "paid"
                )
            )
        ).scalar()
        or 0
    )

    notices = (
        await db.execute(select(Announcement.title).order_by(Announcement.published_at.desc()).limit(6))
    ).scalars().all()

    return {
        "source": "UIS",
        "counted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "course_attendance": bands,
        "student_overall_attendance": profile_bands,
        "attendance_today": today,
        "fees": {"by_status": fees, "unpaid_balance": round(due_amount, 2)},
        "notices": [title for title in notices if title],
    }
