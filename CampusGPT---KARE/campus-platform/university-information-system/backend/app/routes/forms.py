"""Services that staff publish as forms, shared by identity, with a printed acknowledgement."""
import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import FormGrant, FormResponse, ServiceForm, SlipTemplate, User
from app.security.auth import get_current_user, require_roles
from app.services.acknowledge import issue_acknowledgement
from app.services.confirm import PhraseIn, require_phrase

router = APIRouter(prefix="/api/v1", tags=["forms"])
Staff = require_roles(
    "university_admin", "admin", "super_admin", "developer", "operator", "coe", "faculty", "hod", "school_dean", "director"
)
Admins = {"university_admin", "admin", "super_admin", "developer", "operator"}
AUDIENCES = {"all_students", "listed", "any_signed_in"}
FIELD_TYPES = {"text", "long", "number", "date", "choice"}


def _is_admin(user: User) -> bool:
    return user.role in Admins


def _owns(user: User, form: ServiceForm) -> bool:
    return _is_admin(user) or form.created_by == user.id


def _clean_fields(raw: list) -> list[dict]:
    cleaned = []
    for item in raw[:30]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        kind = str(item.get("type") or "text")
        if kind not in FIELD_TYPES:
            kind = "text"
        options = [part.strip() for part in str(item.get("options") or "").replace("\n", ",").split(",") if part.strip()][:20]
        cleaned.append(
            {
                "key": f"f{len(cleaned) + 1}",
                "label": label[:80],
                "type": kind,
                "required": bool(item.get("required", True)),
                "options": options,
            }
        )
    if not cleaned:
        raise HTTPException(status_code=400, detail="Add at least one question")
    return cleaned


def _public_form(form: ServiceForm, *, used: int = 0, identities: Optional[list[str]] = None) -> dict:
    return {
        "id": form.id,
        "title": form.title,
        "instructions": form.instructions,
        "audience": form.audience,
        "response_limit": form.response_limit,
        "is_open": form.is_open,
        "fields": json.loads(form.fields_json or "[]"),
        "used": used,
        "identities": identities or [],
        "created_at": form.created_at.isoformat() if form.created_at else "",
    }


def _identities(user: User) -> set[str]:
    names = {user.username.casefold(), user.email.casefold()}
    if user.student and user.student.student_id:
        names.add(user.student.student_id.casefold())
    return names


def _allowed(user: User, form: ServiceForm, grants: set[str]) -> bool:
    if form.audience == "any_signed_in":
        return True
    if form.audience == "all_students":
        return user.role == "student"
    return bool(_identities(user) & grants)


async def _layout(db: AsyncSession) -> SlipTemplate:
    row = (await db.execute(select(SlipTemplate).order_by(SlipTemplate.id))).scalars().first()
    if row:
        return row
    row = SlipTemplate()
    db.add(row)
    await db.flush()
    return row


def _layout_public(row: SlipTemplate) -> dict:
    return {
        "institution": row.institution,
        "document_title": row.document_title,
        "subtitle": row.subtitle,
        "footer": row.footer,
        "signatory": row.signatory,
        "signatory_title": row.signatory_title,
    }


class FieldIn(BaseModel):
    label: str
    type: str = "text"
    required: bool = True
    options: str = ""


class FormIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    instructions: str = ""
    audience: str = "listed"
    response_limit: int = 1
    is_open: bool = True
    fields: list[FieldIn]


class FormPatch(BaseModel):
    title: Optional[str] = None
    instructions: Optional[str] = None
    audience: Optional[str] = None
    response_limit: Optional[int] = None
    is_open: Optional[bool] = None
    fields: Optional[list[FieldIn]] = None


class ShareIn(BaseModel):
    identities: str = ""


class LayoutIn(BaseModel):
    institution: str = ""
    document_title: str = ""
    subtitle: str = ""
    footer: str = ""
    signatory: str = ""
    signatory_title: str = ""


class SubmitIn(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


@router.get("/slips/layout")
async def read_layout(_: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _layout_public(await _layout(db))


@router.put("/admin/slips/layout")
async def save_layout(
    body: LayoutIn,
    _: Annotated[User, Depends(require_roles("university_admin", "admin", "super_admin", "developer", "operator"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _layout(db)
    row.institution = body.institution.strip()[:160] or row.institution
    row.document_title = body.document_title.strip()[:80] or row.document_title
    row.subtitle = body.subtitle.strip()[:160]
    row.footer = body.footer.strip()[:400]
    row.signatory = body.signatory.strip()[:80]
    row.signatory_title = body.signatory_title.strip()[:80]
    await db.commit()
    return _layout_public(row)


@router.get("/forms")
async def list_forms(user: Annotated[User, Depends(Staff)], db: Annotated[AsyncSession, Depends(get_db)]):
    query = select(ServiceForm).order_by(ServiceForm.id.desc())
    if not _is_admin(user):
        query = query.where(ServiceForm.created_by == user.id)
    forms = (await db.execute(query)).scalars().all()
    return {"items": [_public_form(form) for form in forms]}


@router.post("/forms")
async def create_form(body: FormIn, user: Annotated[User, Depends(Staff)], db: Annotated[AsyncSession, Depends(get_db)]):
    audience = body.audience if body.audience in AUDIENCES else "listed"
    limit = max(0, min(int(body.response_limit), 20))
    form = ServiceForm(
        title=body.title.strip(),
        instructions=body.instructions.strip()[:2000],
        audience=audience,
        response_limit=limit,
        is_open=body.is_open,
        fields_json=json.dumps(_clean_fields([item.model_dump() for item in body.fields])),
        created_by=user.id,
    )
    db.add(form)
    await db.commit()
    return _public_form(form)


@router.patch("/forms/desk/{form_id}")
async def update_form(
    form_id: int,
    body: FormPatch,
    user: Annotated[User, Depends(Staff)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id))).scalar_one_or_none()
    if not form or not _owns(user, form):
        raise HTTPException(status_code=404, detail="Service not found")
    if body.title is not None:
        form.title = body.title.strip()[:120]
    if body.instructions is not None:
        form.instructions = body.instructions.strip()[:2000]
    if body.audience is not None and body.audience in AUDIENCES:
        form.audience = body.audience
    if body.response_limit is not None:
        form.response_limit = max(0, min(int(body.response_limit), 20))
    if body.is_open is not None:
        form.is_open = body.is_open
    if body.fields is not None:
        form.fields_json = json.dumps(_clean_fields([item.model_dump() for item in body.fields]))
    await db.commit()
    return _public_form(form)


@router.delete("/forms/desk/{form_id}")
async def delete_form(
    form_id: int,
    body: PhraseIn,
    user: Annotated[User, Depends(Staff)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id))).scalar_one_or_none()
    if not form or not _owns(user, form):
        raise HTTPException(status_code=404, detail="Service not found")
    require_phrase(body.confirm, form.title)
    grants = (await db.execute(select(FormGrant).where(FormGrant.form_id == form.id))).scalars().all()
    answers = (await db.execute(select(FormResponse).where(FormResponse.form_id == form.id))).scalars().all()
    for row in [*grants, *answers]:
        await db.delete(row)
    await db.delete(form)
    await db.commit()
    return {"ok": True}


@router.post("/forms/desk/{form_id}/share")
async def share_form(
    form_id: int,
    body: ShareIn,
    user: Annotated[User, Depends(Staff)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id))).scalar_one_or_none()
    if not form or not _owns(user, form):
        raise HTTPException(status_code=404, detail="Service not found")
    tokens = []
    for part in body.identities.replace(",", "\n").splitlines():
        token = part.strip()
        if token:
            tokens.append(token[:64])
    tokens = tokens[:500]
    existing = (await db.execute(select(FormGrant).where(FormGrant.form_id == form.id))).scalars().all()
    for row in existing:
        await db.delete(row)
    await db.flush()
    seen = set()
    for token in tokens:
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        db.add(FormGrant(form_id=form.id, identity=token))
    form.audience = "listed"
    await db.commit()
    return {"ok": True, "count": len(seen)}


@router.get("/forms/desk/{form_id}/responses")
async def form_responses(
    form_id: int,
    user: Annotated[User, Depends(Staff)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id))).scalar_one_or_none()
    if not form or not _owns(user, form):
        raise HTTPException(status_code=404, detail="Service not found")
    rows = (
        await db.execute(
            select(FormResponse).where(FormResponse.form_id == form.id).order_by(FormResponse.id.desc()).limit(300)
        )
    ).scalars().all()
    user_ids = [row.user_id for row in rows]
    people = {}
    if user_ids:
        found = (
            await db.execute(select(User).where(User.id.in_(user_ids)).options(selectinload(User.student)))
        ).scalars().all()
        people = {row.id: row for row in found}
    grants = (await db.execute(select(FormGrant.identity).where(FormGrant.form_id == form.id))).scalars().all()
    return {
        "form": _public_form(form, identities=list(grants)),
        "items": [
            {
                "id": row.id,
                "name": people[row.user_id].full_name if row.user_id in people else "",
                "identity": (
                    people[row.user_id].student.student_id
                    if row.user_id in people and people[row.user_id].student
                    else (people[row.user_id].username if row.user_id in people else "")
                ),
                "answers": json.loads(row.answers_json or "{}"),
                "ack_number": row.ack_number,
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in rows
        ],
    }


@router.get("/forms/open")
async def open_forms(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    forms = (await db.execute(select(ServiceForm).where(ServiceForm.is_open.is_(True)).order_by(ServiceForm.id.desc()))).scalars().all()
    form_ids = [form.id for form in forms]
    grants: dict[int, set[str]] = {form.id: set() for form in forms}
    if form_ids:
        rows = (await db.execute(select(FormGrant).where(FormGrant.form_id.in_(form_ids)))).scalars().all()
        for row in rows:
            grants.setdefault(row.form_id, set()).add(row.identity.casefold())
    counts = {}
    if form_ids:
        counted = (
            await db.execute(
                select(FormResponse.form_id, func.count())
                .where(FormResponse.user_id == user.id, FormResponse.form_id.in_(form_ids))
                .group_by(FormResponse.form_id)
            )
        ).all()
        counts = {form_id: count for form_id, count in counted}
    visible = []
    for form in forms:
        if not _allowed(user, form, grants.get(form.id, set())):
            continue
        used = int(counts.get(form.id, 0))
        visible.append(
            {
                "id": form.id,
                "title": form.title,
                "instructions": form.instructions,
                "response_limit": form.response_limit,
                "used": used,
                "remaining": None if form.response_limit == 0 else max(0, form.response_limit - used),
            }
        )
    return {"items": visible}


@router.get("/forms/open/{form_id}")
async def open_form(form_id: int, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id, ServiceForm.is_open.is_(True)))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="This service is not open")
    grants = {
        row.casefold()
        for row in (await db.execute(select(FormGrant.identity).where(FormGrant.form_id == form.id))).scalars().all()
    }
    if not _allowed(user, form, grants):
        raise HTTPException(status_code=403, detail="This service is not shared with your register number or username")
    used = int(
        await db.scalar(select(func.count()).select_from(FormResponse).where(FormResponse.form_id == form.id, FormResponse.user_id == user.id))
        or 0
    )
    return _public_form(form, used=used)


@router.post("/forms/open/{form_id}/submit")
async def submit_form(
    form_id: int,
    body: SubmitIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id, ServiceForm.is_open.is_(True)))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="This service is not open")
    grants = {
        row.casefold()
        for row in (await db.execute(select(FormGrant.identity).where(FormGrant.form_id == form.id))).scalars().all()
    }
    if not _allowed(user, form, grants):
        raise HTTPException(status_code=403, detail="This service is not shared with your register number or username")
    used = int(
        await db.scalar(select(func.count()).select_from(FormResponse).where(FormResponse.form_id == form.id, FormResponse.user_id == user.id))
        or 0
    )
    if form.response_limit and used >= form.response_limit:
        raise HTTPException(status_code=400, detail="You have already used the responses allowed for this service")
    fields = json.loads(form.fields_json or "[]")
    stored = {}
    lines = []
    for field in fields:
        value = str(body.answers.get(field["key"]) or "").strip()
        if field["required"] and not value:
            raise HTTPException(status_code=400, detail=f"Enter {field['label']}")
        if field["type"] == "choice" and value and value not in field["options"]:
            raise HTTPException(status_code=400, detail=f"{field['label']} is not one of the allowed choices")
        stored[field["key"]] = value[:1000]
        if value:
            lines.append(f"{field['label']}: {value}")
    identity = user.student.student_id if user.student else user.username
    response = FormResponse(form_id=form.id, user_id=user.id, answers_json=json.dumps(stored))
    db.add(response)
    await db.flush()
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="service",
        title=form.title,
        summary="\n".join(
            [
                f"Service: {form.title}",
                f"Identity: {identity}",
                f"Status: submitted",
                *lines,
            ]
        ),
        email=user.email,
        status="submitted",
        ref_key=f"form:{response.id}",
    )
    response.ack_number = ack["number"]
    await db.commit()
    return {"ok": True, "acknowledgement": ack}
