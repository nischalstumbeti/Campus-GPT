"""Admin panel APIs."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db
from app.utils.auth import require_admin
from app.utils.db_status import get_database_status
from app.models.document import Document
from app.models.user import User
from app.services.vector_store import get_vector_store
from app.services.train_service import train_model
from app.services import email_service as mail
from app.services import uis_client

router = APIRouter()

_ALLOWED_MAIL_EXT = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
    ".csv",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
}
_MAX_ATTACH_BYTES = 8 * 1024 * 1024  # 8 MB per file
_MAX_ATTACH_COUNT = 5


class TestEmailBody(BaseModel):
    to: str | None = Field(default=None, description="Recipient; defaults to SMTP_USER")
    subject: str | None = Field(default=None, description="Optional subject override")
    description: str | None = Field(default=None, description="Optional body text")


@router.get("/database-status")
async def database_status(user: dict = Depends(require_admin)):
    """Live database connection status for the admin dashboard."""
    status = await get_database_status()
    uis_ok = False
    try:
        uis_ok = await uis_client.ping() if hasattr(uis_client, "ping") else uis_client.uis_enabled()
    except Exception:
        uis_ok = False
    status["uis_api"] = "connected" if uis_ok else "disconnected"
    status["personal_data_source"] = "UIS database (API)" if uis_ok else "UIS unavailable"
    return status


@router.get("/email-status")
async def email_status(user: dict = Depends(require_admin)):
    """SMTP configuration status (no secrets)."""
    return mail.email_config_status()


@router.get("/users")
async def list_users(
    q: str = "",
    role: str | None = None,
    limit: int = 40,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Search Campus-GPT users for mail recipient picker."""
    lim = max(1, min(int(limit or 40), 100))
    stmt = select(User).order_by(User.email.asc()).limit(lim)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(like),
                User.full_name.ilike(like),
                User.uis_username.ilike(like),
            )
        )
    if role:
        try:
            from app.models.user import Role

            stmt = stmt.where(User.role == Role(role))
        except Exception:
            stmt = stmt.where(User.role == role)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name or "",
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "uis_username": u.uis_username or "",
            }
            for u in rows
        ]
    }


@router.post("/test-email")
async def test_email(body: TestEmailBody = TestEmailBody(), user: dict = Depends(require_admin)):
    """Send a test / notice email (JSON). Prefer /send-mail for attachments."""
    if body.subject or body.description:
        result = await mail.send_admin_notice(
            (body.to or "").strip() or (mail.email_config_status().get("from_email") or ""),
            body.subject or "Campus-GPT mail test",
            body.description or "This is a test alert from Campus-GPT admin.",
            None,
        )
    else:
        result = await mail.send_test_email(body.to)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("detail") or "Send failed")
    return result


@router.post("/send-mail")
async def send_mail(
    to: str | None = Form(None),
    user_id: int | None = Form(None),
    subject: str = Form("Campus-GPT notice"),
    description: str = Form(""),
    files: list[UploadFile] | None = File(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Send a composed email to a particular user, with optional PDF/document attachments."""
    recipient = (to or "").strip()
    if user_id and not recipient:
        row = (await db.execute(select(User).where(User.id == int(user_id)))).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        recipient = (row.email or "").strip()
    if not recipient or "@" not in recipient:
        raise HTTPException(status_code=400, detail="Select a user or enter a valid email address")

    upload_list = list(files or [])
    if len(upload_list) > _MAX_ATTACH_COUNT:
        raise HTTPException(status_code=400, detail=f"Maximum {_MAX_ATTACH_COUNT} attachments allowed")

    attachments: list[tuple[str, bytes, str | None]] = []
    for f in upload_list:
        name = (f.filename or "attachment").strip()
        ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
        if ext not in _ALLOWED_MAIL_EXT:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed for {name}. Allowed: {', '.join(sorted(_ALLOWED_MAIL_EXT))}",
            )
        data = await f.read()
        if len(data) > _MAX_ATTACH_BYTES:
            raise HTTPException(status_code=400, detail=f"{name} exceeds 8 MB limit")
        if data:
            attachments.append((name, data, f.content_type))

    result = await mail.send_admin_notice(
        recipient,
        (subject or "Campus-GPT notice").strip(),
        (description or "").strip() or "Message from Campus-GPT admin.",
        attachments or None,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("detail") or "Send failed")
    return result


@router.get("/documents")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """List uploaded documents."""
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [{"id": d.id, "filename": d.filename, "status": d.status, "chunks": d.chunk_count} for d in docs]


@router.get("/vector-stats")
async def vector_stats(user: dict = Depends(require_admin)):
    """Get vector store statistics."""
    store = get_vector_store()
    return {"total_chunks": store.count()}


@router.post("/train")
async def train_knowledge_model(user: dict = Depends(require_admin)):
    """Rebuild RAG knowledge from institutional seed + live UIS campus data."""
    return await train_model()


@router.post("/train/public")
async def train_knowledge_model_public(user: dict = Depends(require_admin)):
    """Legacy path — same as /train, admin-only."""
    return await train_model()


@router.get("/vector-stats/public")
async def vector_stats_public(user: dict = Depends(require_admin)):
    store = get_vector_store()
    return {"total_chunks": store.count()}


@router.post("/eval/run")
async def run_evaluation(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Run gold-set evaluation (latency + keyword/token proxies). May take 1–3 minutes."""
    from app.services.eval_service import run_gold_evaluation

    result = await run_gold_evaluation(db, user=user)
    await db.commit()
    return result


@router.get("/eval/latest")
async def eval_latest(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    from app.services.eval_service import latest_eval_run

    data = await latest_eval_run(db)
    if not data:
        return {"ok": False, "detail": "No evaluation runs yet. POST /api/admin/eval/run first."}
    return {"ok": True, **data}


@router.get("/eval/latency")
async def eval_live_latency(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    from app.services.eval_service import live_latency_stats

    return await live_latency_stats(db)


class InsightIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


def _pct(present: int, od: int, conducted: int) -> float:
    if conducted <= 0:
        return 0.0
    return round(100.0 * (present + od) / conducted, 1)


async def _campus_measures(db: AsyncSession) -> dict:
    from app.models.academic import AttendanceSummary
    from app.models.analytics import QueryLog
    from app.services.vector_store import get_vector_store

    rows = (await db.execute(select(AttendanceSummary))).scalars().all()
    counted = below = watch = ok = 0
    for row in rows:
        conducted = int(row.conducted or 0)
        if conducted <= 0:
            continue
        counted += 1
        pct = _pct(int(row.present or 0), int(row.od or 0), conducted)
        if pct < 70:
            below += 1
        elif pct < 75:
            watch += 1
        else:
            ok += 1
    queries = int((await db.execute(select(func.count()).select_from(QueryLog))).scalar() or 0)
    failed = int((await db.execute(select(func.count()).select_from(QueryLog).where(QueryLog.failed == 1))).scalar() or 0)
    try:
        chunks = int(get_vector_store().count() or 0)
    except Exception:
        chunks = 0
    return {
        "attendance_rows": counted,
        "attendance_below_70": below,
        "attendance_watch": watch,
        "attendance_ok": ok,
        "questions_logged": queries,
        "questions_low_confidence": failed,
        "knowledge_excerpts": chunks,
    }


def _measure_text(measures: dict) -> str:
    return (
        f"Attendance course rows counted: {measures['attendance_rows']}. "
        f"Below 70 percent: {measures['attendance_below_70']}. "
        f"From 70 up to 75 percent: {measures['attendance_watch']}. "
        f"At or above 75 percent: {measures['attendance_ok']}. "
        f"Questions logged: {measures['questions_logged']}. "
        f"Low-confidence questions: {measures['questions_low_confidence']}. "
        f"Knowledge excerpts stored: {measures['knowledge_excerpts']}."
    )


@router.post("/insight")
async def admin_insight(
    body: InsightIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Admin reading: ethics check, measured campus figures, then Gemini over those records."""
    from app.config import get_settings
    from app.services.rag_service import rag_pipeline, retrieve_context
    from app.utils.prompt_validator import is_valid_prompt

    valid, err = is_valid_prompt(body.question)
    measures = await _campus_measures(db)
    evidence = _measure_text(measures)
    thinking = [
        "Checked the question against campus ethics rules.",
        "Counted attendance rows, logged questions, and knowledge excerpts. No student names are included.",
    ]
    if not valid:
        return {
            "answer": err or "This desk only answers campus questions from measured records.",
            "thinking": thinking + ["The question was refused."],
            "sources": [],
            "measures": measures,
            "confidence": 0,
            "gemini": bool((get_settings().GEMINI_API_KEY or "").strip()),
        }
    chunks, sources, _score = await retrieve_context(body.question)
    thinking.append(f"Retrieved {len(chunks)} knowledge excerpt(s) for this question.")
    if not (get_settings().GEMINI_API_KEY or "").strip():
        thinking.append("No Gemini key is saved, so the reply is the measured figures only.")
        return {
            "answer": evidence + " Paste the Gemini API key on Connections and test it. Then ask again for a written reading of these figures.",
            "thinking": thinking,
            "sources": sources,
            "measures": measures,
            "confidence": 1 if measures["attendance_rows"] or measures["questions_logged"] else 0.4,
            "gemini": False,
        }
    result = await rag_pipeline(
        body.question,
        agent_type="admin",
        db=db,
        user=user,
        extra_context=evidence,
    )
    thinking.append("Wrote the answer from the measured figures and the retrieved excerpts only.")
    return {
        "answer": result.get("answer") or evidence,
        "thinking": thinking,
        "sources": result.get("sources") or sources,
        "measures": measures,
        "confidence": result.get("confidence") or 0,
        "gemini": True,
    }
