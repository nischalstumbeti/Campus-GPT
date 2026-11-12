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
LABELS = {
    "advisor": "Advisor",
    "hod": "HoD",
    "school_dean": "School dean",
    "director": "Director",
    "coe": "COE",
    "admin": "Admin",
}
OFFICE_ROLES = {
    "advisor": {"faculty", "hod", "school_dean"},
    "hod": {"hod"},
    "school_dean": {"school_dean"},
    "director": {"director"},
    "coe": {"coe"},
    "admin": {"university_admin", "admin", "super_admin", "developer", "operator", "director"},
}
OFFICE = OFFICE_ROLES["admin"]
STAFF = {"faculty", "hod", "school_dean", "director", "coe"}
ROUTE_ROLES = ("university_admin", "admin", "super_admin", "developer", "operator", "director")


def _parse_steps(raw: str) -> list[tuple[str, int | None]]:
    found: list[tuple[str, int | None]] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        piece = part.strip().lower()
        role, _, ident = piece.partition(":")
        if role not in STEPS or role in seen:
            continue
        seen.add(role)
        found.append((role, int(ident) if ident.isdigit() else None))
    return found


def _label(role: str, user_id: int | None, names: dict[int, str]) -> str:
    title = LABELS[role]
    if user_id and names.get(user_id):
        return f"{title} · {names[user_id]}"
    return title


async def _names(db: AsyncSession, raws: list[str]) -> dict[int, str]:
    ids = [user_id for raw in raws for _, user_id in _parse_steps(raw) if user_id]
    if not ids:
        return {}
    people = (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    return {person.id: person.full_name for person in people}


async def _checked_steps(db: AsyncSession, raw: str) -> str:
    parsed = _parse_steps(raw)
    if not parsed:
        raise HTTPException(status_code=400, detail="Add at least one office")
    ids = [user_id for _, user_id in parsed if user_id]
    people = {
        person.id: person
        for person in (await db.execute(select(User).where(User.id.in_(ids or [0])))).scalars().all()
    }
    stored = []
    for role, user_id in parsed:
        if not user_id:
            raise HTTPException(status_code=400, detail=f"Select the {LABELS[role].lower()} from the list")
        person = people.get(user_id)
        if not person or not person.is_active or person.role == "student":
            raise HTTPException(status_code=400, detail=f"Select a staff member for {LABELS[role].lower()}")
        stored.append(f"{role}:{user_id}")
    return ",".join(stored)


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


async def _can_sign(db: AsyncSession, actor: User, applicant: User | None, role: str, user_id: int | None) -> bool:
    if user_id:
        return actor.id == user_id
    if role == "advisor":
        if not actor.faculty or not applicant or not applicant.student:
            return False
        return await advisor_for(db, applicant.student) == actor.faculty.id
    if role == "hod":
        return actor.role == "hod" and _same_department(actor, applicant)
    if role == "admin":
        return actor.role in OFFICE
    if role in {"school_dean", "director", "coe"}:
        return actor.role == role
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


def _route_public(row: RequestRoute, names: dict[int, str]) -> dict:
    parsed = _parse_steps(row.steps)
    return {
        "id": row.id,
        "name": row.name,
        "steps": [_label(role, user_id, names) for role, user_id in parsed],
        "offices": [{"role": role, "user_id": user_id, "label": _label(role, user_id, names)} for role, user_id in parsed],
        "active": bool(row.active),
    }


def _letter_public(row: LetterRequest, route: RequestRoute | None, person: User | None, names: dict[int, str]) -> dict:
    parsed = _parse_steps(route.steps) if route else []
    current = parsed[row.step_index] if row.status == "pending" and row.step_index < len(parsed) else None
    return {
        "id": row.id,
        "subject": row.subject,
        "body": row.body,
        "status": row.status,
        "note": row.note,
        "step": _label(*current, names) if current else "",
        "steps": [_label(role, user_id, names) for role, user_id in parsed],
        "route": route.name if route else "",
        "name": person.full_name if person else "",
        "role": person.role if person else "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


@router.get("/admin/request-offices")
async def request_offices(_: Annotated[User, Depends(require_roles(*ROUTE_ROLES))], db: Annotated[AsyncSession, Depends(get_db)]):
    people = (await db.execute(select(User).where(User.is_active.is_(True)).order_by(User.full_name))).scalars().all()
    items = []
    for role, allowed in OFFICE_ROLES.items():
        items.append(
            {
                "role": role,
                "label": LABELS[role],
                "people": [
                    {"id": person.id, "name": person.full_name or person.username, "department": person.department_code or ""}
                    for person in people
                    if person.role in allowed
                ],
            }
        )
    return {"items": items}


@router.get("/admin/request-routes")
async def list_routes(_: Annotated[User, Depends(require_roles(*ROUTE_ROLES))], db: Annotated[AsyncSession, Depends(get_db)]):
    await _ensure_route(db)
    rows = (await db.execute(select(RequestRoute).order_by(RequestRoute.id))).scalars().all()
    names = await _names(db, [row.steps for row in rows])
    return {"items": [_route_public(row, names) for row in rows]}


@router.post("/admin/request-routes")
async def save_route(body: RouteIn, _: Annotated[User, Depends(require_roles(*ROUTE_ROLES))], db: Annotated[AsyncSession, Depends(get_db)]):
    stored = await _checked_steps(db, body.steps)
    row = RequestRoute(name=body.name.strip(), steps=stored, active=body.active)
    db.add(row)
    await db.flush()
    names = await _names(db, [row.steps])
    return _route_public(row, names)


@router.get("/requests/routes")
async def open_routes(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only a student can raise this letter")
    await _ensure_route(db)
    rows = (await db.execute(select(RequestRoute).where(RequestRoute.active.is_(True)).order_by(RequestRoute.id))).scalars().all()
    names = await _names(db, [row.steps for row in rows])
    return {"items": [_route_public(row, names) for row in rows]}


@router.get("/requests/mine")
async def my_letters(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(LetterRequest).where(LetterRequest.user_id == user.id).order_by(LetterRequest.id.desc()))).scalars().all()
    routes = {row.id: row for row in (await db.execute(select(RequestRoute))).scalars().all()}
    names = await _names(db, [route.steps for route in routes.values()])
    return {"items": [_letter_public(row, routes.get(row.route_id), user, names) for row in rows]}


@router.post("/requests")
async def raise_letter(body: LetterIn, user: Annotated[User, Depends(require_roles("student"))], db: Annotated[AsyncSession, Depends(get_db)]):
    route = (await db.execute(select(RequestRoute).where(RequestRoute.id == body.route_id, RequestRoute.active.is_(True)))).scalar_one_or_none()
    if not route or not _parse_steps(route.steps):
        raise HTTPException(status_code=404, detail="That route is not open")
    row = LetterRequest(user_id=user.id, route_id=route.id, subject=body.subject.strip(), body=body.body.strip())
    db.add(row)
    await db.flush()
    names = await _names(db, [route.steps])
    return _letter_public(row, route, user, names)


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
        steps = _parse_steps(route.steps) if route else []
        if row.step_index >= len(steps):
            continue
        role, user_id = steps[row.step_index]
        if await _can_sign(db, user, people.get(row.user_id), role, user_id):
            visible.append(row)
    names = await _names(db, [routes[item.route_id].steps for item in visible if item.route_id in routes])
    return {"items": [_letter_public(item, routes.get(item.route_id), people.get(item.user_id), names) for item in visible]}


@router.post("/requests/{letter_id}/decide")
async def decide_letter(letter_id: int, body: DecideIn, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(select(LetterRequest).where(LetterRequest.id == letter_id))).scalar_one_or_none()
    route = (await db.execute(select(RequestRoute).where(RequestRoute.id == row.route_id))).scalar_one_or_none() if row else None
    if not row or not route or row.status != "pending":
        raise HTTPException(status_code=404, detail="That letter is not waiting")
    steps = _parse_steps(route.steps)
    applicant = (
        await db.execute(select(User).where(User.id == row.user_id).options(selectinload(User.student), selectinload(User.faculty)))
    ).scalar_one_or_none()
    current = steps[row.step_index] if row.step_index < len(steps) else None
    if not current or not await _can_sign(db, user, applicant, current[0], current[1]):
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
                summary=f"Route: {route.name}\n{row.body}\nApproved through {', '.join(_label(role, user_id, {}) for role, user_id in steps)}",
                email=applicant.email if applicant else None,
                status="approved",
                ref_key=f"letter:{row.id}",
            )
            await db.refresh(row)
            await db.refresh(route)
    else:
        raise HTTPException(status_code=400, detail="Choose approve or reject")
    await db.flush()
    names = await _names(db, [route.steps])
    return _letter_public(row, route, applicant, names)


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
    await db.flush()
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
    await db.flush()
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
