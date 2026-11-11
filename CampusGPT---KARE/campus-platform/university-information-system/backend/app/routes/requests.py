"""Student letters that follow an admin route, and staff leave in the personnel desk."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import LetterRequest, RequestRoute, StaffLeave, User
from app.security.auth import get_current_user, require_roles
from app.services.acknowledge import issue_acknowledgement
from app.services.advisors import advisor_for

router = APIRouter(prefix="/api/v1", tags=["requests"])
STEPS = {"advisor", "hod", "school_dean", "director", "coe", "admin"}
OFFICE = {"university_admin", "admin", "super_admin", "developer", "operator", "director"}
STAFF = {"faculty", "hod", "school_dean", "director", "coe"}


def _steps(raw: str) -> list[str]:
    found = []
    for part in (raw or "").split(","):
        name = part.strip().lower()
        if name in STEPS and name not in found:
            found.append(name)
    return found


async def _ensure_route(db: AsyncSession) -> None:
    existing = (await db.execute(select(RequestRoute).limit(1))).scalar_one_or_none()
    if existing:
        return
    db.add(RequestRoute(name="Bonafide / requisition", steps="advisor,hod,school_dean", active=True))
    await db.flush()


def _same_department(actor: User, applicant: User | None) -> bool:
    if not applicant or not actor.department_code or not applicant.department_code:
        return True
    return actor.department_code.strip().lower() == applicant.department_code.strip().lower()


async def _can_sign(db: AsyncSession, actor: User, applicant: User | None, step: str) -> bool:
    if step == "advisor":
        if not actor.faculty or not applicant or not applicant.student:
            return False
        return await advisor_for(db, applicant.student) == actor.faculty.id
    if step == "hod":
        return actor.role == "hod" and _same_department(actor, applicant)
    if step == "admin":
        return actor.role in OFFICE
    if step in {"school_dean", "director", "coe"}:
        return actor.role == step
    return False


class RouteIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    steps: str = Field(min_length=3, max_length=200)
    active: bool = True


class LetterIn(BaseModel):
    route_id: int
    subject: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=3, max_length=4000)


class DecideIn(BaseModel):
    decision: str
    note: str = ""


class LeaveIn(BaseModel):
    start_date: str = Field(min_length=8, max_length=16)
    end_date: str = Field(min_length=8, max_length=16)
    reason: str = Field(min_length=3, max_length=255)


def _route_public(row: RequestRoute) -> dict:
    return {"id": row.id, "name": row.name, "steps": _steps(row.steps), "active": bool(row.active)}


def _letter_public(row: LetterRequest, route: RequestRoute | None, person: User | None) -> dict:
    steps = _steps(route.steps) if route else []
    current = steps[row.step_index] if row.status == "pending" and row.step_index < len(steps) else ""
    return {
        "id": row.id,
        "subject": row.subject,
        "body": row.body,
        "status": row.status,
        "note": row.note,
        "step": current,
        "steps": steps,
        "route": route.name if route else "",
        "name": person.full_name if person else "",
        "role": person.role if person else "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


@router.get("/admin/request-routes")
async def list_routes(_: Annotated[User, Depends(require_roles("university_admin", "admin", "super_admin", "developer", "operator", "director"))], db: Annotated[AsyncSession, Depends(get_db)]):
    await _ensure_route(db)
    rows = (await db.execute(select(RequestRoute).order_by(RequestRoute.id))).scalars().all()
    return {"items": [_route_public(row) for row in rows]}


@router.post("/admin/request-routes")
async def save_route(body: RouteIn, _: Annotated[User, Depends(require_roles("university_admin", "admin", "super_admin", "developer", "operator", "director"))], db: Annotated[AsyncSession, Depends(get_db)]):
    steps = _steps(body.steps)
    if not steps:
        raise HTTPException(status_code=400, detail="Use advisor, hod, school_dean, director, coe, or admin")
    row = RequestRoute(name=body.name.strip(), steps=",".join(steps), active=body.active)
    db.add(row)
    await db.commit()
    return _route_public(row)


@router.get("/requests/routes")
async def open_routes(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only a student can raise this letter")
    await _ensure_route(db)
    rows = (await db.execute(select(RequestRoute).where(RequestRoute.active.is_(True)).order_by(RequestRoute.id))).scalars().all()
    return {"items": [_route_public(row) for row in rows]}


@router.get("/requests/mine")
async def my_letters(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(LetterRequest).where(LetterRequest.user_id == user.id).order_by(LetterRequest.id.desc()))).scalars().all()
    routes = {row.id: row for row in (await db.execute(select(RequestRoute))).scalars().all()}
    return {"items": [_letter_public(row, routes.get(row.route_id), user) for row in rows]}


@router.post("/requests")
async def raise_letter(body: LetterIn, user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    route = (await db.execute(select(RequestRoute).where(RequestRoute.id == body.route_id, RequestRoute.active.is_(True)))).scalar_one_or_none()
    if not route or not _steps(route.steps):
        raise HTTPException(status_code=404, detail="That route is not open")
    row = LetterRequest(user_id=user.id, route_id=route.id, subject=body.subject.strip(), body=body.body.strip())
    db.add(row)
    await db.commit()
    return _letter_public(row, route, user)


@router.get("/requests/inbox")
async def letter_inbox(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (
        await db.execute(select(LetterRequest).where(LetterRequest.status == "pending").order_by(LetterRequest.id.desc()))
    ).scalars().all()
    routes = {row.id: row for row in (await db.execute(select(RequestRoute))).scalars().all()}
    people = {
        person.id: person
        for person in (
            await db.execute(select(User).where(User.id.in_([row.user_id for row in rows] or [0])).options(selectinload(User.student), selectinload(User.faculty)))
        ).scalars().all()
    }
    visible = []
    for row in rows:
        route = routes.get(row.route_id)
        steps = _steps(route.steps) if route else []
        if row.step_index >= len(steps):
            continue
        if await _can_sign(db, user, people.get(row.user_id), steps[row.step_index]):
            visible.append(_letter_public(row, route, people.get(row.user_id)))
    return {"items": visible}


@router.post("/requests/{letter_id}/decide")
async def decide_letter(letter_id: int, body: DecideIn, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(select(LetterRequest).where(LetterRequest.id == letter_id))).scalar_one_or_none()
    route = (await db.execute(select(RequestRoute).where(RequestRoute.id == row.route_id))).scalar_one_or_none() if row else None
    if not row or not route or row.status != "pending":
        raise HTTPException(status_code=404, detail="That letter is not waiting")
    steps = _steps(route.steps)
    applicant = (
        await db.execute(select(User).where(User.id == row.user_id).options(selectinload(User.student), selectinload(User.faculty)))
    ).scalar_one_or_none()
    if row.step_index >= len(steps) or not await _can_sign(db, user, applicant, steps[row.step_index]):
        raise HTTPException(status_code=403, detail="This letter is not at your desk")
    decision = body.decision.strip().lower()
    row.note = body.note.strip()[:255]
    if decision == "reject":
        row.status = "rejected"
    elif decision == "approve":
        row.step_index += 1
        if row.step_index >= len(steps):
            row.status = "approved"
            await issue_acknowledgement(
                db,
                user=applicant,
                kind="general",
                title=row.subject,
                summary=f"Route: {route.name}\n{row.body}\nApproved through {', '.join(steps)}",
                email=applicant.email if applicant else None,
                status="approved",
                ref_key=f"letter:{row.id}",
            )
    else:
        raise HTTPException(status_code=400, detail="Choose approve or reject")
    await db.commit()
    return _letter_public(row, route, applicant)


@router.get("/personnel/leave")
async def my_leave(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if user.role not in STAFF and user.role not in OFFICE:
        raise HTTPException(status_code=403, detail="Personnel leave is for staff")
    rows = (await db.execute(select(StaffLeave).where(StaffLeave.user_id == user.id).order_by(StaffLeave.id.desc()))).scalars().all()
    return {"items": [_leave_public(row, user) for row in rows]}


@router.post("/personnel/leave")
async def apply_leave(body: LeaveIn, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if user.role not in STAFF and user.role not in OFFICE:
        raise HTTPException(status_code=403, detail="Personnel leave is for staff")
    row = StaffLeave(user_id=user.id, start_date=body.start_date.strip(), end_date=body.end_date.strip(), reason=body.reason.strip())
    db.add(row)
    await db.commit()
    return _leave_public(row, user)


@router.get("/personnel/leave/inbox")
async def leave_inbox(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if user.role not in {"hod", "school_dean", "director"} and user.role not in OFFICE:
        return {"items": []}
    rows = (await db.execute(select(StaffLeave).where(StaffLeave.status == "pending").order_by(StaffLeave.id.desc()))).scalars().all()
    people = {person.id: person for person in (await db.execute(select(User).where(User.id.in_([row.user_id for row in rows] or [0])))).scalars().all()}
    visible = []
    for row in rows:
        person = people.get(row.user_id)
        if not person or person.id == user.id:
            continue
        if user.role == "hod" and not _same_department(user, person):
            continue
        if user.role == "hod" and person.role != "faculty":
            continue
        if user.role == "school_dean" and person.role not in {"faculty", "hod"}:
            continue
        visible.append(_leave_public(row, person))
    return {"items": visible}


@router.post("/personnel/leave/{leave_id}/decide")
async def decide_leave(leave_id: int, body: DecideIn, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(select(StaffLeave).where(StaffLeave.id == leave_id))).scalar_one_or_none()
    if not row or row.status != "pending":
        raise HTTPException(status_code=404, detail="That leave is not waiting")
    person = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
    if user.role == "hod":
        allowed = bool(person and person.role == "faculty" and _same_department(user, person))
    elif user.role == "school_dean":
        allowed = bool(person and person.role in {"faculty", "hod"})
    else:
        allowed = user.role in OFFICE
    if not allowed or (person and person.id == user.id):
        raise HTTPException(status_code=403, detail="This leave is not at your desk")
    decision = body.decision.strip().lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Choose approve or reject")
    row.status = "approved" if decision == "approve" else "rejected"
    row.decided_by = user.full_name
    await db.commit()
    return _leave_public(row, person)


def _leave_public(row: StaffLeave, person: User | None) -> dict:
    return {
        "id": row.id,
        "name": person.full_name if person else "",
        "role": person.role if person else "",
        "start_date": row.start_date,
        "end_date": row.end_date,
        "reason": row.reason,
        "status": row.status,
        "decided_by": row.decided_by,
    }
