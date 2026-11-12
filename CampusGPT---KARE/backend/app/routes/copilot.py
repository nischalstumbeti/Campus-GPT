"""Copilot modules: graduation, announcements, letters, career, achievements, week plan."""
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db
from app.utils.auth import get_current_user
from app.services import academic_service as acad
from app.services import consent as consents
from app.services import student_context as ctx
from app.services import uis_client
from app.models.privacy import Announcement, Achievement, HostelProfile
from app.models.academic import Course, HostelLeave

router = APIRouter()


class LetterRequest(BaseModel):
    kind: str = "hod_permission"
    topic: str = "attend an academic event"
    audience: str = "Head of Department"


def _uid(user: dict) -> int:
    return int(user["sub"])


async def _student(db, user):
    student, _ = await acad.resolve_student(db, user)
    if not student:
        raise HTTPException(status_code=404, detail="No academic profile linked")
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")
    return student


@router.get("/copilot/graduation")
async def graduation(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    if not await consents.is_allowed(db, _uid(user), "academic.credits"):
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")
    student = await _student(db, user)
    courses = (await db.execute(select(Course).where(Course.department == student.department, Course.semester <= student.semester))).scalars().all()
    earned = sum(c.credits or 0 for c in courses)
    required = 160
    remaining = max(required - earned, 0)
    await consents.log_access(db, _uid(user), "Credits", "Graduation progress", "academic.credits")
    return {
        "kind": "fact",
        "disclaimer": "Official Information from authorized academic records. Not an official degree audit until the Controller of Examinations confirms it.",
        "credits_completed": earned,
        "credits_required": required,
        "credits_remaining": remaining,
        "percent": round(100 * earned / required),
        "core": "In progress",
        "electives": "4 / 6 (demo)",
        "internship": "Pending",
        "project": "Complete" if student.semester >= 7 else "Not started",
        "remaining": [
            f"{remaining} credits still required (assumption: {required} credit B.Tech).",
            "Internship status is pending — confirm with your department office.",
            "Confirm core/elective split with your department office.",
        ],
    }


def _audience_visible(audience: str, role: str | None) -> bool:
    """Hierarchy: admin sees all; faculty sees faculty+all+warden; students see student+all."""
    aud = (audience or "all").lower()
    role = (role or "").lower()
    if role in ("admin", "super_admin"):
        return True
    if aud == "all":
        return True
    if role == "faculty":
        return aud in ("faculty", "warden", "all")
    if role == "student":
        return aud in ("student", "all")
    return aud == "all"


@router.get("/copilot/announcements")
async def announcements(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    rows = (await db.execute(select(Announcement).order_by(Announcement.important.desc(), Announcement.id.desc()))).scalars().all()
    role = user.get("role")
    dept = None
    student, _ = await acad.resolve_student(db, user)
    if student:
        dept = student.department
    items = []
    for n in rows:
        if not _audience_visible(n.audience, role):
            continue
        important_for_you = bool(n.important) or (dept and n.department == dept)
        items.append(
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "category": n.category,
                "audience": n.audience,
                "effective_date": n.effective_date,
                "source": n.source or "Campus-GPT",
                "important_for_you": important_for_you,
            }
        )
    # Merge official UIS announcements (same feed chat uses)
    try:
        uis_items = await uis_client.get_announcements(role=role)
        for i, n in enumerate(uis_items):
            aud = (n.get("audience") or "all").lower()
            if not _audience_visible(aud, role):
                continue
            items.append(
                {
                    "id": 100000 + int(n.get("id") or i),
                    "title": n.get("title") or "Notice",
                    "body": n.get("body") or "",
                    "category": "uis",
                    "audience": aud,
                    "effective_date": (n.get("published_at") or "")[:10],
                    "source": n.get("source") or "UIS Announcements",
                    "important_for_you": False,
                }
            )
    except Exception:
        pass
    return {"items": items, "source": "UIS+local"}


class AnnouncementIn(BaseModel):
    title: str
    body: str = ""
    category: str = "general"
    audience: str = "all"  # all | student | faculty | warden
    department: str = ""
    effective_date: str = ""
    important: bool = False


@router.post("/copilot/announcements")
async def create_announcement(
    body: AnnouncementIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    if body.audience not in ("all", "student", "faculty", "warden"):
        raise HTTPException(status_code=400, detail="Invalid audience")
    row = Announcement(
        title=body.title.strip(),
        body=body.body.strip(),
        category=body.category.strip() or "general",
        audience=body.audience,
        department=body.department.strip(),
        effective_date=body.effective_date.strip(),
        source=f"Admin · {user.get('email') or 'Campus-GPT'}",
        important=1 if body.important else 0,
        created_by=int(user["sub"]),
    )
    db.add(row)
    await db.flush()
    return {
        "ok": True,
        "announcement": {
            "id": row.id,
            "title": row.title,
            "audience": row.audience,
            "body": row.body,
        },
        "cascade": "Visible to hierarchy below admin (students / faculty / warden based on audience).",
    }


@router.post("/copilot/letters")
async def letters(body: LetterRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    if not await consents.is_allowed(db, _uid(user), "academic.history"):
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")
    student = await _student(db, user)
    await consents.log_access(db, _uid(user), "Academic history", "Letter draft", "academic.history")
    name = student.full_name
    roll = student.roll_no
    dept = student.department
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Say what the letter is about")
    audience = " ".join((body.audience or "").split())
    if not audience:
        raise HTTPException(status_code=400, detail="Choose who the letter is addressed to")
    while audience.lower().startswith("the the "):
        audience = audience[4:].strip()
    dear = audience[4:].strip() if audience.lower().startswith("the ") else audience
    from app.config import get_settings
    from app.services.rag_service import _gemini_generate, _get_genai

    if not (get_settings().GEMINI_API_KEY or "").strip():
        raise HTTPException(status_code=503, detail="The AI key is not set. Add it on Thinking, then generate the letter again.")
    genai = _get_genai()
    if not genai:
        raise HTTPException(status_code=503, detail="The AI key is not set. Add it on Thinking, then generate the letter again.")
    prompt = (
        "Write a real student letter for Kalasalingam Academy of Research and Education. "
        "Use only the identity facts below. Do not invent marks, attendance, dates, or a different student.\n"
        f"Student: {name}\nRegister: {roll}\nDepartment: {dept}\n"
        f"Semester: {student.semester}\nSection: {student.section}\n"
        f"Addressed to: {audience}\nSalutation name: {dear}\nWhat they need: {topic}\n\n"
        "Return JSON only, with keys formal, email, and short. "
        "formal is the full letter. email is a short email with a subject line. short is two sentences."
    )
    try:
        raw = await _gemini_generate(genai, prompt, max_output_tokens=700)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"The AI could not write the letter. {exc}"[:400])
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    try:
        parsed = json.loads(match.group(0) if match else (raw or ""))
    except json.JSONDecodeError:
        parsed = {}
    formal = str(parsed.get("formal") or raw or "").strip()
    email = str(parsed.get("email") or "").strip()
    short = str(parsed.get("short") or "").strip()
    if not formal:
        raise HTTPException(status_code=502, detail="The AI returned an empty letter. Try again.")
    return {
        "kind": "recommendation",
        "disclaimer": "AI-generated drafts. Not submitted. Review before you send. This is not an official university decision.",
        "formal": formal,
        "email": email,
        "short": short,
        "submit": False,
    }


@router.get("/copilot/achievements")
async def achievements(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    if not await consents.is_allowed(db, _uid(user), "achievements.certs"):
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")
    await consents.log_access(db, _uid(user), "Achievements", "Profile view", "achievements.certs")
    uis_user = await ctx.get_uis_username(db, user)
    if uis_user and uis_client.uis_enabled():
        try:
            remote = await uis_client.get_achievements(uis_user)
            items = []
            for a in remote.get("achievements") or []:
                items.append(
                    {
                        "kind": a.get("category") or "achievement",
                        "title": a.get("title") or "",
                        "detail": a.get("description") or a.get("detail") or "",
                        "year": str(a.get("awarded_on") or a.get("year") or "")[:4],
                    }
                )
            if items:
                return {"items": items, "source": "UIS"}
        except uis_client.UisClientError:
            pass
    student = await _student(db, user)
    rows = (await db.execute(select(Achievement).where(Achievement.student_id == student.id))).scalars().all()
    return {
        "items": [{"kind": r.kind, "title": r.title, "detail": r.detail, "year": r.year} for r in rows],
        "source": "local",
    }


@router.get("/copilot/career")
async def career(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    student = await _student(db, user)
    ok = await consents.is_allowed(db, _uid(user), "achievements.activities")
    ach = []
    if ok:
        ach = (await db.execute(select(Achievement).where(Achievement.student_id == student.id))).scalars().all()
        await consents.log_access(db, _uid(user), "Achievements", "Career assistance", "achievements.activities")
    strengths = [r.title for r in ach] or ["Coursework in CSE core subjects (from authorized timetable)."]
    return {
        "kind": "recommendation",
        "disclaimer": "Recommendations, not official placement outcomes or job guarantees.",
        "strengths": strengths,
        "gaps": ["Document a cloud internship project", "Add one public GitHub systems project"],
        "next_steps": [
            "Draft a resume from your authorized achievements.",
            "Complete one certification listed by your department (verify on the official portal).",
            "Ask faculty during office hours about internships — not a placement guarantee.",
        ],
        "resume_blurb": f"{student.full_name} is a {student.program} student in {student.department} (Sem {student.semester}).",
    }


@router.get("/copilot/week-plan")
async def week_plan(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    student = await _student(db, user)
    if not await consents.is_allowed(db, _uid(user), "academic.history"):
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")
    plan = await acad.build_week_plan(db, student)
    await consents.log_access(db, _uid(user), "Timetable", "Weekly plan", "academic.history")
    return {"kind": "recommendation", "disclaimer": "Prioritized suggestions from authorized timetable and calendar.", "plan": plan}


@router.get("/copilot/hostel")
async def hostel(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    out: dict = {"source": "local"}
    uis_user = await ctx.get_uis_username(db, user)
    if uis_user and uis_client.uis_enabled():
        try:
            payload = await uis_client.get_hostel(uis_user)
            out["source"] = "UIS"
            if await consents.is_allowed(db, _uid(user), "hostel.room"):
                out["room"] = payload.get("allocation") or payload.get("room")
                await consents.log_access(db, _uid(user), "Room information", "Hostel view", "hostel.room")
            if await consents.is_allowed(db, _uid(user), "hostel.leave"):
                leaves = payload.get("leaves") or []
                out["leaves"] = [
                    {
                        "from": lv.get("from") or lv.get("from_date"),
                        "to": lv.get("to") or lv.get("to_date"),
                        "status": lv.get("status"),
                        "reason": lv.get("reason"),
                    }
                    for lv in leaves
                ]
                await consents.log_access(db, _uid(user), "Hostel leave", "Leave status", "hostel.leave")
            if out.get("room") or out.get("leaves"):
                return out
        except uis_client.UisClientError:
            pass
    student = await _student(db, user)
    if await consents.is_allowed(db, _uid(user), "hostel.room"):
        hp = (await db.execute(select(HostelProfile).where(HostelProfile.student_id == student.id))).scalar_one_or_none()
        if hp:
            out["room"] = {"hostel": hp.hostel, "block": hp.block, "room": hp.room, "mess": hp.mess}
            await consents.log_access(db, _uid(user), "Room information", "Hostel view", "hostel.room")
    if await consents.is_allowed(db, _uid(user), "hostel.leave"):
        leaves = (await db.execute(select(HostelLeave).where(HostelLeave.student_id == student.id))).scalars().all()
        out["leaves"] = [{"from": lv.from_date, "to": lv.to_date, "status": lv.status, "reason": lv.reason} for lv in leaves]
        await consents.log_access(db, _uid(user), "Hostel leave", "Leave status", "hostel.leave")
    if not out:
        raise HTTPException(status_code=403, detail="I can't provide that information because you don't have permission to access it.")
    return out
