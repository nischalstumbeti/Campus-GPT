"""Forms for collecting responses, with a publisher-designed slip and shared results."""
import csv
import io
import json
import re
import secrets
import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Acknowledgement,
    AppNotification,
    FormCollaborator,
    FormGrant,
    FormResponse,
    PeopleGroup,
    PeopleGroupMember,
    ServiceForm,
    SlipTemplate,
    StudentProfile,
    User,
)
from app.security.auth import get_current_user, require_roles
from app.services.acknowledge import issue_acknowledgement
from app.services.confirm import PhraseIn, require_phrase
from app.services.email_service import send_email
from app.utils.rate_limit import check_rate_limit, client_key

_FILES = Path(__file__).resolve().parents[2] / "data" / "form_files"
_FILE_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".txt", ".xlsx"}

router = APIRouter(prefix="/api/v1", tags=["forms"])
Staff = require_roles(
    "university_admin", "admin", "super_admin", "developer", "operator", "coe", "faculty", "hod", "school_dean", "director"
)
Admins = {"university_admin", "admin", "super_admin", "developer", "operator"}
AUDIENCES = {"all_students", "listed", "any_signed_in", "open"}
FIELD_TYPES = {"text", "long", "number", "date", "choice", "link", "file"}
EMAIL_MODES = {"none", "acknowledgement", "message"}
PROFILE_FIELDS = {
    "name": "Name",
    "email": "Email",
    "register_or_employee": "Register number or employee id",
    "program": "Programme",
    "department": "Department",
    "batch": "Batch",
    "section": "Section",
    "semester": "Semester",
    "designation": "Designation",
    "school": "School",
    "abc_id": "ABC ID",
}
DEFAULT_COLLECT = ["name", "email", "register_or_employee"]
LAYOUTS = {
    "general": ("ACKNOWLEDGEMENT", "Registrar", "Office of the Registrar", True),
    "form": ("APPLICATION CONFIRMATION", "", "", False),
    "registration": ("COURSE REGISTRATION", "Dean, Academic Affairs", "Office of the Dean (Academic)", True),
    "withdrawal": ("COURSE WITHDRAWAL", "Dean, Academic Affairs", "Office of the Dean (Academic)", True),
    "revaluation": ("REVALUATION APPLICATION", "Controller of Examinations", "Office of the Controller of Examinations", True),
    "arrear": ("ARREAR APPLICATION", "Controller of Examinations", "Office of the Controller of Examinations", True),
    "backlog": ("BACKLOG APPLICATION", "Controller of Examinations", "Office of the Controller of Examinations", True),
    "makeup": ("MAKE-UP APPLICATION", "Controller of Examinations", "Office of the Controller of Examinations", True),
    "payment": ("FEE RECEIPT", "Finance Officer", "Office of the Finance Officer", True),
    "complaint": ("COMPLAINT RECEIPT", "Dean, Student Affairs", "Office of the Dean (Student Affairs)", True),
}
_TAG = re.compile(r"</?\s*([a-zA-Z0-9]+)[^>]*>")
_KEEP = {"b", "strong", "i", "em", "u", "br", "p", "div"}


def _clean_body(raw: str) -> str:
    text = re.sub(r"(?is)<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", raw or "")

    def keep(match: re.Match) -> str:
        tag = match.group(1).lower()
        if tag not in _KEEP:
            return ""
        if tag == "br":
            return "<br>"
        if match.group(0).startswith("</"):
            return f"</{tag}>"
        return f"<{tag}>"

    return _TAG.sub(keep, text)[:8000]


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
        show_if = str(item.get("show_if") or "").strip()[:80]
        try:
            digits = int(item.get("digits") or 0)
        except (TypeError, ValueError):
            digits = 0
        digits = min(15, max(0, digits))
        cleaned.append(
            {
                "key": f"f{len(cleaned) + 1}",
                "label": label[:80],
                "type": kind,
                "required": bool(item.get("required", True)),
                "options": options,
                "show_if": show_if,
                "digits": digits if kind == "number" else 0,
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
        "confirmation": form.confirmation or "",
        "redirect_url": form.redirect_url or "",
        "email_mode": form.email_mode or "acknowledgement",
        "email_subject": form.email_subject or "",
        "email_body": form.email_body or "",
        "slip": json.loads(form.slip_json or "{}"),
        "public_code": form.public_code or "",
        "collect": _collect(form),
        "allow_edit": bool(form.allow_edit),
        "issue_ack": bool(form.issue_ack),
        "share_path": f"/f/{form.public_code}" if form.audience == "open" and form.public_code else f"/student/forms?open={form.id}",
        "created_at": form.created_at.isoformat() if form.created_at else "",
    }


def _identities(user: User) -> set[str]:
    names = {user.username.casefold(), user.email.casefold()}
    if user.student and user.student.student_id:
        names.add(user.student.student_id.casefold())
    return names


def _allowed(user: User, form: ServiceForm, grants: set[str]) -> bool:
    if form.audience in {"any_signed_in", "open"}:
        return True
    if form.audience == "all_students":
        return user.role == "student"
    return bool(_identities(user) & grants)


def _shown(field: dict, answers: dict) -> bool:
    rule = str(field.get("show_if") or "")
    if "=" not in rule:
        return True
    key, expected = rule.split("=", 1)
    return str(answers.get(key.strip()) or "") == expected.strip()


def _collect(form: ServiceForm) -> list[str]:
    raw = json.loads(form.collect_json or "[]")
    if not isinstance(raw, list):
        return []
    return [key for key in raw if key in PROFILE_FIELDS]


def _profile_values(user: User) -> dict[str, str]:
    student = user.student
    faculty = user.faculty
    program = ""
    if student and student.program:
        program = student.program.name or ""
    register = ""
    if student and student.student_id:
        register = student.student_id
    elif faculty and faculty.faculty_id:
        register = faculty.faculty_id
    return {
        "name": user.full_name or "",
        "email": user.email or "",
        "register_or_employee": register,
        "program": program,
        "department": user.department_code or "",
        "batch": student.batch if student else "",
        "section": student.section if student else "",
        "semester": str(student.semester) if student else "",
        "designation": user.designation or (faculty.designation if faculty else ""),
        "school": user.school or "",
        "abc_id": user.abc_id or "",
    }


def _attach_profile(form: ServiceForm, user: User | None, stored: dict, lines: list[str]) -> list[dict]:
    if user is None or form.audience == "open":
        return []
    values = _profile_values(user)
    attached = []
    for key in _collect(form):
        value = values.get(key) or "Not on the account"
        stored[f"profile:{key}"] = value
        lines.append(f"{PROFILE_FIELDS[key]}: {value}")
        attached.append({"key": key, "label": PROFILE_FIELDS[key], "value": value})
    return attached


def _slip(form: ServiceForm) -> dict:
    data = json.loads(form.slip_json or "{}")
    if not isinstance(data, dict):
        data = {}
    data["body"] = _clean_body(str(data.get("body") or ""))
    data["show_particulars"] = bool(data.get("show_particulars", True))
    data["show_signatory"] = bool(data.get("show_signatory", False))
    return data


def _stored_slip(slip: SlipIn) -> str:
    data = slip.model_dump()
    data["body"] = _clean_body(data.get("body") or "")
    return json.dumps(data)


async def _layout(db: AsyncSession, kind: str) -> SlipTemplate:
    kind = kind if kind in LAYOUTS else "general"
    row = (await db.execute(select(SlipTemplate).where(SlipTemplate.kind == kind))).scalars().first()
    if row:
        return row
    title, signatory, office, signed = LAYOUTS[kind]
    row = SlipTemplate(
        kind=kind,
        document_title=title,
        signatory=signatory,
        signatory_title=office,
        show_signatory=signed,
        body="Number {{number}}\nStatus {{status}}\nDate {{date}}\n\n{{title}}",
    )
    db.add(row)
    await db.flush()
    return row


def _layout_public(row: SlipTemplate) -> dict:
    return {
        "kind": row.kind or "general",
        "institution": row.institution,
        "document_title": row.document_title,
        "subtitle": row.subtitle,
        "footer": row.footer,
        "signatory": row.signatory,
        "signatory_title": row.signatory_title,
        "body": row.body or "",
        "show_particulars": bool(row.show_particulars),
        "show_signatory": bool(row.show_signatory),
    }


class FieldIn(BaseModel):
    label: str
    type: str = "text"
    required: bool = True
    options: str = ""
    show_if: str = ""
    digits: int = 0


class SlipIn(BaseModel):
    institution: str = ""
    document_title: str = "APPLICATION CONFIRMATION"
    subtitle: str = ""
    footer: str = ""
    signatory: str = ""
    signatory_title: str = ""
    body: str = ""
    show_particulars: bool = True
    show_signatory: bool = False


class FormIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    instructions: str = ""
    audience: str = "listed"
    response_limit: int = 1
    is_open: bool = False
    confirmation: str = ""
    redirect_url: str = ""
    email_mode: str = "acknowledgement"
    email_subject: str = ""
    email_body: str = ""
    slip: SlipIn = SlipIn()
    collect: list[str] = DEFAULT_COLLECT
    allow_edit: bool = False
    issue_ack: bool = True
    fields: list[FieldIn]


class FormPatch(BaseModel):
    title: Optional[str] = None
    instructions: Optional[str] = None
    audience: Optional[str] = None
    response_limit: Optional[int] = None
    is_open: Optional[bool] = None
    confirmation: Optional[str] = None
    redirect_url: Optional[str] = None
    email_mode: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    slip: Optional[SlipIn] = None
    collect: Optional[list[str]] = None
    allow_edit: Optional[bool] = None
    issue_ack: Optional[bool] = None
    fields: Optional[list[FieldIn]] = None


class ShareIn(BaseModel):
    identities: str = ""
    group_id: Optional[int] = None
    can_edit: bool = False


class LayoutIn(BaseModel):
    kind: str = "general"
    institution: str = ""
    document_title: str = ""
    subtitle: str = ""
    footer: str = ""
    signatory: str = ""
    signatory_title: str = ""
    body: str = ""
    show_particulars: bool = True
    show_signatory: bool = True


class SubmitIn(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


@router.get("/slips/layout")
async def read_layout(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: str = "general",
):
    return _layout_public(await _layout(db, kind))


@router.put("/admin/slips/layout")
async def save_layout(
    body: LayoutIn,
    _: Annotated[User, Depends(require_roles("university_admin", "admin", "super_admin", "developer", "operator"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _layout(db, body.kind)
    row.institution = body.institution.strip()[:160] or row.institution
    row.document_title = body.document_title.strip()[:80] or row.document_title
    row.subtitle = body.subtitle.strip()[:160]
    row.footer = body.footer.strip()[:400]
    row.signatory = body.signatory.strip()[:80]
    row.signatory_title = body.signatory_title.strip()[:80]
    row.body = _clean_body(body.body)
    row.show_particulars = body.show_particulars
    row.show_signatory = body.show_signatory
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
    mode = body.email_mode if body.email_mode in EMAIL_MODES else "acknowledgement"
    form = ServiceForm(
        title=body.title.strip(),
        instructions=body.instructions.strip()[:2000],
        audience=audience,
        response_limit=limit,
        is_open=body.is_open,
        confirmation=body.confirmation.strip()[:2000],
        redirect_url=body.redirect_url.strip()[:500],
        email_mode=mode,
        email_subject=body.email_subject.strip()[:160],
        email_body=body.email_body.strip()[:4000],
        slip_json=_stored_slip(body.slip),
        public_code=secrets.token_urlsafe(8),
        collect_json=json.dumps([key for key in body.collect if key in PROFILE_FIELDS]),
        allow_edit=body.allow_edit,
        issue_ack=body.issue_ack,
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
    if body.confirmation is not None:
        form.confirmation = body.confirmation.strip()[:2000]
    if body.redirect_url is not None:
        form.redirect_url = body.redirect_url.strip()[:500]
    if body.email_mode is not None and body.email_mode in EMAIL_MODES:
        form.email_mode = body.email_mode
    if body.email_subject is not None:
        form.email_subject = body.email_subject.strip()[:160]
    if body.email_body is not None:
        form.email_body = body.email_body.strip()[:4000]
    if body.allow_edit is not None:
        form.allow_edit = body.allow_edit
    if body.issue_ack is not None:
        form.issue_ack = body.issue_ack
    if body.collect is not None:
        form.collect_json = json.dumps([key for key in body.collect if key in PROFILE_FIELDS])
    if body.slip is not None and _owns(user, form):
        form.slip_json = _stored_slip(body.slip)
    if not form.public_code:
        form.public_code = secrets.token_urlsafe(8)
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
    collaborators = (await db.execute(select(FormCollaborator).where(FormCollaborator.form_id == form.id))).scalars().all()
    for row in [*grants, *answers, *collaborators]:
        await db.delete(row)
    await db.delete(form)
    await db.commit()
    return {"ok": True}


async def _users_in_group(db: AsyncSession, group_id: int) -> list[User]:
    groups = (await db.execute(select(PeopleGroup))).scalars().all()
    if not any(group.id == group_id for group in groups):
        raise HTTPException(status_code=404, detail="Group not found")
    wanted = set()

    def walk(current: int) -> None:
        wanted.add(current)
        for group in groups:
            if group.parent_id == current:
                walk(group.id)

    walk(group_id)
    member_ids = (
        await db.execute(select(PeopleGroupMember.user_id).where(PeopleGroupMember.group_id.in_(wanted)))
    ).scalars().all()
    if not member_ids:
        return []
    return list(
        (
            await db.execute(select(User).where(User.id.in_(member_ids)).options(selectinload(User.student)))
        ).scalars().all()
    )


@router.get("/forms/directory")
async def form_directory(_: Annotated[User, Depends(Staff)], db: Annotated[AsyncSession, Depends(get_db)]):
    groups = (await db.execute(select(PeopleGroup).order_by(PeopleGroup.id))).scalars().all()

    def path(group: PeopleGroup) -> str:
        parent = next((item for item in groups if item.id == group.parent_id), None)
        return f"{path(parent)} / {group.name}" if parent else group.name

    return {"items": [{"id": group.id, "path": path(group)} for group in groups]}


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
    if body.group_id:
        for person in await _users_in_group(db, body.group_id):
            tokens.append(person.student.student_id if person.student else person.username)
    if not tokens:
        raise HTTPException(status_code=400, detail="Choose a group that has people, or enter a register number")
    seen = {row.identity.casefold() for row in existing}
    fresh = set()
    for token in tokens:
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        fresh.add(key)
        db.add(FormGrant(form_id=form.id, identity=token))
    if fresh:
        matched = (
            await db.execute(
                select(User)
                .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
                .where(or_(func.lower(User.username).in_(list(fresh)), func.lower(StudentProfile.student_id).in_(list(fresh))))
            )
        ).scalars().all()
        for person in matched:
            db.add(
                AppNotification(
                    user_id=person.id,
                    kind="form",
                    title=form.title,
                    body="A form has been shared with you. Open Forms to fill it.",
                    link="/student/forms",
                )
            )
    await db.commit()
    return {"ok": True, "count": len(fresh)}


async def _can_view(db: AsyncSession, user: User, form: ServiceForm) -> bool:
    if _owns(user, form):
        return True
    row = (
        await db.execute(
            select(FormCollaborator).where(FormCollaborator.form_id == form.id, FormCollaborator.user_id == user.id)
        )
    ).scalar_one_or_none()
    return row is not None


@router.get("/forms/desk/{form_id}/responses")
async def form_responses(
    form_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id))).scalar_one_or_none()
    if not form or not await _can_view(db, user, form):
        raise HTTPException(status_code=404, detail="Form not found")
    rows = (
        await db.execute(
            select(FormResponse).where(FormResponse.form_id == form.id).order_by(FormResponse.id.desc()).limit(300)
        )
    ).scalars().all()
    user_ids = [row.user_id for row in rows if row.user_id]
    people = {}
    if user_ids:
        found = (
            await db.execute(select(User).where(User.id.in_(user_ids)).options(selectinload(User.student)))
        ).scalars().all()
        people = {row.id: row for row in found}
    grants = (await db.execute(select(FormGrant.identity).where(FormGrant.form_id == form.id))).scalars().all()
    collaborator = (
        await db.execute(
            select(FormCollaborator).where(FormCollaborator.form_id == form.id, FormCollaborator.user_id == user.id)
        )
    ).scalar_one_or_none()
    return {
        "can_edit": _owns(user, form) or bool(collaborator and collaborator.can_edit),
        "form": _public_form(form, identities=list(grants)),
        "items": [
            {
                "id": row.id,
                "name": row.guest_name or (people[row.user_id].full_name if row.user_id in people else "Open response"),
                "identity": row.guest_email or (
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
        "charts": _charts(form, rows),
    }


def _charts(form: ServiceForm, rows: list) -> list[dict]:
    fields = json.loads(form.fields_json or "[]")
    parsed = [json.loads(row.answers_json or "{}") for row in rows]
    charts = []
    for field in fields:
        if field.get("type") != "choice":
            continue
        counts = {option: 0 for option in field.get("options") or []}
        for answers in parsed:
            value = str(answers.get(field["key"]) or "")
            if value in counts:
                counts[value] += 1
        charts.append({"key": field["key"], "label": field["label"], "counts": counts})
    return charts


@router.get("/forms/open")
async def open_forms(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    forms = (
        await db.execute(
            select(ServiceForm).where(ServiceForm.is_open.is_(True), ServiceForm.audience != "open").order_by(ServiceForm.id.desc())
        )
    ).scalars().all()
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
                "remaining": None if form.allow_edit else (None if form.response_limit == 0 else max(0, form.response_limit - used)),
                "allow_edit": bool(form.allow_edit),
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
    payload = _public_form(form, used=used)
    values = _profile_values(user)
    payload["profile"] = [
        {"key": key, "label": PROFILE_FIELDS[key], "value": values.get(key) or "Not on the account"}
        for key in _collect(form)
    ]
    payload["profile_notice"] = "These details come from your signed-in account and will be stored with this response."
    prior = (
        await db.execute(
            select(FormResponse)
            .where(FormResponse.form_id == form.id, FormResponse.user_id == user.id)
            .order_by(FormResponse.id.desc())
        )
    ).scalars().first()
    if prior:
        saved = json.loads(prior.answers_json or "{}")
        payload["mine"] = {
            "answers": {key: value for key, value in saved.items() if not str(key).startswith("profile:")},
            "ack_number": prior.ack_number,
        }
    return payload


def _read_answers(form: ServiceForm, answers: dict) -> tuple[dict, list[str]]:
    fields = json.loads(form.fields_json or "[]")
    stored = {}
    lines = []
    for field in fields:
        if not _shown(field, answers):
            continue
        value = str(answers.get(field["key"]) or "").strip()
        if field["required"] and not value:
            raise HTTPException(status_code=400, detail=f"Enter {field['label']}")
        if field["type"] == "number" and value:
            if not value.isdigit():
                raise HTTPException(status_code=400, detail=f"{field['label']}: only numbers are allowed")
            need = int(field.get("digits") or 0)
            if need and len(value) != need:
                raise HTTPException(status_code=400, detail=f"{field['label']}: enter exactly {need} digits")
        if field["type"] == "choice" and value and value not in field["options"]:
            raise HTTPException(status_code=400, detail=f"{field['label']} is not one of the allowed choices")
        if field["type"] == "link" and value and not value.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail=f"{field['label']} needs a full link")
        if field["type"] == "file" and value and not (_FILES / Path(value).name).exists():
            raise HTTPException(status_code=400, detail=f"Upload {field['label']} again")
        stored[field["key"]] = value[:1000]
        if value:
            lines.append(f"{field['label']}: {value}")
    return stored, lines


async def _finish(db, form, response, user, email, identity, lines):
    mode = form.email_mode or "acknowledgement"
    if not form.issue_ack:
        if mode == "message" and email:
            note = form.email_body or "Your response has been recorded."
            await send_email(email, form.email_subject or form.title, f"<p>{note}</p>", text_body=note)
        return {"number": "", "title": form.title, "email": email or "", "email_sent": False, "status": "recorded", "link": ""}
    ack = await issue_acknowledgement(
        db,
        user=user,
        kind="form",
        title=form.title,
        summary="\n".join([f"Form: {form.title}", f"Identity: {identity}", "Status: submitted", *lines]),
        email=email if mode == "acknowledgement" else None,
        status="submitted",
        ref_key=f"form:{response.id}",
        notify_kind="form",
    )
    if mode == "message" and email:
        note = form.email_body or "Your response has been recorded."
        await send_email(email, form.email_subject or form.title, f"<p>{note}</p><p>Acknowledgement {ack['number']}</p>", text_body=f"{note}\n{ack['number']}")
    return ack


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
    prior = (
        await db.execute(
            select(FormResponse)
            .where(FormResponse.form_id == form.id, FormResponse.user_id == user.id)
            .order_by(FormResponse.id.desc())
        )
    ).scalars().first()
    if prior and not form.allow_edit and form.response_limit and used >= form.response_limit:
        raise HTTPException(status_code=400, detail="You have already used the responses allowed for this service")
    if not prior and form.response_limit and used >= form.response_limit:
        raise HTTPException(status_code=400, detail="You have already used the responses allowed for this service")
    stored, lines = _read_answers(form, body.answers)
    _attach_profile(form, user, stored, lines)
    identity = user.student.student_id if user.student else user.username
    if prior and form.allow_edit:
        response = prior
        response.answers_json = json.dumps(stored)
    else:
        response = FormResponse(form_id=form.id, user_id=user.id, answers_json=json.dumps(stored))
        db.add(response)
    await db.flush()
    ack = await _finish(db, form, response, user, user.email, identity, lines)
    response.ack_number = ack["number"]
    await db.commit()
    return {"ok": True, "acknowledgement": ack, "confirmation": form.confirmation, "redirect_url": form.redirect_url}


@router.get("/forms/sheet/{number}")
async def response_sheet(number: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    ack = (await db.execute(select(Acknowledgement).where(Acknowledgement.number == number))).scalar_one_or_none()
    response = (await db.execute(select(FormResponse).where(FormResponse.ack_number == number))).scalar_one_or_none()
    if not ack or not response:
        raise HTTPException(status_code=404, detail="Filled response not found")
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == response.form_id))).scalar_one_or_none()
    allowed = user.role in Admins or ack.actor_user_id == user.id or (form and await _can_view(db, user, form))
    if not allowed:
        raise HTTPException(status_code=404, detail="Filled response not found")
    answers = json.loads(response.answers_json or "{}")
    fields = json.loads(form.fields_json or "[]") if form else []
    person = None
    if response.user_id:
        person = (await db.execute(select(User).where(User.id == response.user_id).options(selectinload(User.student)))).scalar_one_or_none()
    return {
        "number": number,
        "title": form.title if form else ack.title,
        "instructions": form.instructions if form else "",
        "identity": response.guest_email or (person.student.student_id if person and person.student else (person.username if person else "")),
        "name": response.guest_name or (person.full_name if person else ""),
        "status": ack.status,
        "slip": _slip(form) if form else {},
        "photo_url": (person.photo_url if person and person.photo_url else "") or (person.student.photo_url if person and person.student and person.student.photo_url else ""),
        "profile": [
            {"label": PROFILE_FIELDS[key.split(":", 1)[1]], "value": value}
            for key, value in answers.items()
            if key.startswith("profile:") and key.split(":", 1)[1] in PROFILE_FIELDS
        ],
        "answers": [
            {"label": field["label"], "value": "File attached" if field.get("type") == "file" and answers.get(field["key"]) else answers.get(field["key"], "")}
            for field in fields
        ],
        "fields": [
            {"label": PROFILE_FIELDS[key.split(":", 1)[1]], "value": value}
            for key, value in answers.items()
            if key.startswith("profile:") and key.split(":", 1)[1] in PROFILE_FIELDS
        ] + [
            {"label": field["label"], "value": "File attached" if field.get("type") == "file" and answers.get(field["key"]) else answers.get(field["key"], "")}
            for field in fields
        ],
    }


class PublicSubmit(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)
    name: str = ""
    email: str = ""


async def _save_upload(upload: UploadFile) -> str:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in _FILE_EXT:
        raise HTTPException(status_code=400, detail="Use a pdf, image, Word, text, or Excel file")
    data = await upload.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File is larger than 5 MB")
    _FILES.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    (_FILES / stored).write_bytes(data)
    return stored


@router.post("/forms/open/{form_id}/file")
async def upload_answer_file(
    form_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    upload: UploadFile = File(...),
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id, ServiceForm.is_open.is_(True)))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="This form is not open")
    grants = {
        item.casefold()
        for item in (await db.execute(select(FormGrant.identity).where(FormGrant.form_id == form.id))).scalars().all()
    }
    if not _allowed(user, form, grants):
        raise HTTPException(status_code=404, detail="This form is not open")
    return {"stored": await _save_upload(upload)}


@router.get("/forms/public/{code}")
async def public_form(code: str, db: Annotated[AsyncSession, Depends(get_db)]):
    form = (
        await db.execute(select(ServiceForm).where(ServiceForm.public_code == code, ServiceForm.audience == "open", ServiceForm.is_open.is_(True)))
    ).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="This form is not open")
    payload = _public_form(form)
    payload.pop("identities", None)
    payload.pop("email_body", None)
    return payload


@router.post("/forms/public/{code}/file")
async def public_file(code: str, request: Request, db: Annotated[AsyncSession, Depends(get_db)], upload: UploadFile = File(...)):
    check_rate_limit(client_key(request, "form-file"), limit=20, window_seconds=60)
    form = (
        await db.execute(select(ServiceForm).where(ServiceForm.public_code == code, ServiceForm.audience == "open", ServiceForm.is_open.is_(True)))
    ).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="This form is not open")
    return {"stored": await _save_upload(upload)}


@router.post("/forms/public/{code}/submit")
async def public_submit(code: str, body: PublicSubmit, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    check_rate_limit(client_key(request, "form-submit"), limit=10, window_seconds=60)
    form = (
        await db.execute(select(ServiceForm).where(ServiceForm.public_code == code, ServiceForm.audience == "open", ServiceForm.is_open.is_(True)))
    ).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="This form is not open")
    email = body.email.strip()
    if form.response_limit and email:
        used = int(
            await db.scalar(
                select(func.count()).select_from(FormResponse).where(FormResponse.form_id == form.id, FormResponse.guest_email == email)
            )
            or 0
        )
        if used >= form.response_limit:
            raise HTTPException(status_code=400, detail="This email has already used the responses allowed for this form")
    stored, lines = _read_answers(form, body.answers)
    response = FormResponse(
        form_id=form.id,
        user_id=None,
        guest_name=body.name.strip()[:120],
        guest_email=email[:255],
        answers_json=json.dumps(stored),
    )
    db.add(response)
    await db.flush()
    ack = await _finish(db, form, response, None, email, email or body.name or "Open response", lines)
    response.ack_number = ack["number"]
    await db.commit()
    return {"ok": True, "acknowledgement": ack, "confirmation": form.confirmation, "redirect_url": form.redirect_url}


@router.post("/forms/desk/{form_id}/collaborators")
async def add_collaborators(
    form_id: int,
    body: ShareIn,
    user: Annotated[User, Depends(Staff)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id))).scalar_one_or_none()
    if not form or not _owns(user, form):
        raise HTTPException(status_code=404, detail="Form not found")
    keys = [part.strip().casefold() for part in body.identities.replace(",", "\n").splitlines() if part.strip()]
    people = []
    if body.group_id:
        people.extend(await _users_in_group(db, body.group_id))
    if keys:
        people.extend(
            (
                await db.execute(
                    select(User)
                    .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
                    .where(or_(func.lower(User.username).in_(keys), func.lower(StudentProfile.student_id).in_(keys)))
                )
            ).scalars().all()
        )
    if not people:
        raise HTTPException(status_code=400, detail="Choose a group or enter a username or register number")
    existing = {
        row.user_id: row
        for row in (await db.execute(select(FormCollaborator).where(FormCollaborator.form_id == form.id))).scalars().all()
    }
    added = 0
    for person in people:
        if person.id == form.created_by:
            continue
        if person.id in existing:
            current = existing[person.id]
            if current is not None:
                current.can_edit = body.can_edit or current.can_edit
            continue
        db.add(FormCollaborator(form_id=form.id, user_id=person.id, can_edit=body.can_edit))
        existing[person.id] = None
        db.add(AppNotification(user_id=person.id, kind="form", title=form.title, body="You can view the responses.", link=f"/forms/results/{form.id}"))
        added += 1
    await db.commit()
    return {"ok": True, "added": added}


class EditIn(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


@router.patch("/forms/desk/{form_id}/responses/{response_id}")
async def edit_response(
    form_id: int,
    response_id: int,
    body: EditIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id))).scalar_one_or_none()
    if not form or not await _can_view(db, user, form):
        raise HTTPException(status_code=404, detail="Form not found")
    collaborator = (
        await db.execute(select(FormCollaborator).where(FormCollaborator.form_id == form.id, FormCollaborator.user_id == user.id))
    ).scalar_one_or_none()
    if not _owns(user, form) and not (collaborator and collaborator.can_edit):
        raise HTTPException(status_code=403, detail="You can view these responses. Editing was not turned on for you.")
    response = (
        await db.execute(select(FormResponse).where(FormResponse.id == response_id, FormResponse.form_id == form.id))
    ).scalar_one_or_none()
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")
    stored, lines = _read_answers(form, body.answers)
    owner = None
    if response.user_id:
        owner = (await db.execute(select(User).where(User.id == response.user_id).options(selectinload(User.student)))).scalar_one_or_none()
    if owner:
        _attach_profile(form, owner, stored, lines)
    response.answers_json = json.dumps(stored)
    if form.issue_ack:
        ack = await _finish(db, form, response, owner, owner.email if owner else response.guest_email, response.guest_email or (owner.username if owner else ""), lines)
        response.ack_number = ack["number"] or response.ack_number
    await db.commit()
    return {"ok": True}


@router.get("/forms/results")
async def result_forms(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    forms = (await db.execute(select(ServiceForm).order_by(ServiceForm.id.desc()))).scalars().all()
    visible = []
    for form in forms:
        if await _can_view(db, user, form):
            visible.append({"id": form.id, "title": form.title, "is_open": form.is_open, "public_code": form.public_code if _owns(user, form) else ""})
    return {"items": visible}


def _table(form: ServiceForm, rows: list[FormResponse], people: dict) -> tuple[list[str], list[list[str]]]:
    fields = json.loads(form.fields_json or "[]")
    collected = _collect(form)
    header = ["Acknowledgement", "Name", "Identity", *[PROFILE_FIELDS[key] for key in collected], *[field["label"] for field in fields]]
    body = []
    for row in rows:
        person = people.get(row.user_id)
        answers = json.loads(row.answers_json or "{}")
        body.append(
            [
                row.ack_number,
                row.guest_name or (person.full_name if person else ""),
                row.guest_email or (person.student.student_id if person and person.student else (person.username if person else "")),
                *[str(answers.get(f"profile:{key}") or "") for key in collected],
                *[str(answers.get(field["key"]) or "") for field in fields],
            ]
        )
    return header, body


def _pdf(header: list[str], body: list[list[str]]) -> bytes:
    lines = [" | ".join(header)]
    lines.extend(" | ".join(cell.replace("\n", " ")[:40] for cell in row) for row in body[:80])
    commands = ["BT", "/F1 9 Tf"]
    y = 800
    for line in lines:
        if y < 40:
            break
        safe = line.replace("\\", "").replace("(", "[").replace(")", "]")[:140]
        commands.append(f"1 0 0 1 36 {y} Tm ({safe}) Tj")
        y -= 14
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n",
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode() + stream + b"\nendstream endobj\n",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for item in objects:
        offsets.append(sum(len(part) for part in parts))
        parts.append(item)
    xref = sum(len(part) for part in parts)
    parts.append(f"xref\n0 {len(offsets)}\n".encode())
    parts.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        parts.append(f"{offset:010d} 00000 n \n".encode())
    parts.append(f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return b"".join(parts)


@router.get("/forms/desk/{form_id}/export")
async def export_responses(
    form_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = "csv",
):
    form = (await db.execute(select(ServiceForm).where(ServiceForm.id == form_id))).scalar_one_or_none()
    if not form or not await _can_view(db, user, form):
        raise HTTPException(status_code=404, detail="Form not found")
    rows = (await db.execute(select(FormResponse).where(FormResponse.form_id == form.id).order_by(FormResponse.id))).scalars().all()
    ids = [row.user_id for row in rows if row.user_id]
    people = {}
    if ids:
        found = (await db.execute(select(User).where(User.id.in_(ids)).options(selectinload(User.student)))).scalars().all()
        people = {row.id: row for row in found}
    header, body = _table(form, rows, people)
    stem = "".join(ch if ch.isalnum() else "-" for ch in form.title)[:40] or "form"
    if format == "xlsx":
        book = Workbook()
        sheet = book.active
        sheet.title = "Responses"
        sheet.append(header)
        for row in body:
            sheet.append(row)
        buffer = io.BytesIO()
        book.save(buffer)
        return Response(
            buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{stem}.xlsx"'},
        )
    if format == "pdf":
        return Response(_pdf(header, body), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'})
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(body)
    return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'})
