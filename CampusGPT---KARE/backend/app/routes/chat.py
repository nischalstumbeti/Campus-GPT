"""Chat API - RAG pipeline, discussion history, and long-term memory."""
import json
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.rag_service import rag_pipeline
from app.services.demo_responses import DEPARTMENT_CONTACTS
from app.services.memory_service import extract_memory_facts, save_memory_facts, load_memory_facts
from app.config import get_settings
from app.utils.database import get_db
from app.utils.auth import get_current_user_optional, get_current_user
from app.models.analytics import QueryLog
from app.models.escalation import EscalationLog
from app.models.chat import ChatSession, ChatMessage, UserMemory

router = APIRouter()
settings = get_settings()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    history: list[dict] | None = None
    agent_type: str | None = "general"


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[dict]
    confidence: float
    escalated: bool
    diagram: dict | None = None
    points_earned: int = 0
    data_used: list[dict] = []
    intent: str = "knowledge"
    kind: str = "knowledge"
    denied: list[str] = []
    pending_action: dict | None = None
    needs_confirmation: bool = False
    latency_ms: float | None = None


def _user_id(user: dict | None) -> int | None:
    if not user or not user.get("sub"):
        return None
    try:
        return int(user["sub"])
    except (TypeError, ValueError):
        return None


async def _get_or_create_session(
    db: AsyncSession,
    session_id: str,
    uid: int | None,
    title: str,
    agent_type: str = "general",
) -> ChatSession | None:
    if uid is None:
        return None
    result = await db.execute(select(ChatSession).where(ChatSession.session_id == session_id))
    sess = result.scalar_one_or_none()
    if sess:
        if sess.user_id and sess.user_id != uid:
            raise HTTPException(status_code=403, detail="Not your discussion")
        if getattr(sess, "agent_type", None) and sess.agent_type != agent_type:
            raise HTTPException(status_code=400, detail="Session belongs to a different assistant")
        sess.agent_type = agent_type
        sess.updated_at = datetime.utcnow()
        return sess
    sess = ChatSession(
        user_id=uid,
        session_id=session_id,
        agent_type=agent_type or "general",
        title=(title or "New discussion")[:80],
    )
    db.add(sess)
    await db.flush()
    return sess


async def _persist_turn(
    db: AsyncSession,
    sess: ChatSession,
    user_msg: str,
    answer: str,
    sources: list,
    confidence: float,
    escalated: bool,
):
    db.add(ChatMessage(session_id=sess.id, role="user", content=user_msg))
    db.add(
        ChatMessage(
            session_id=sess.id,
            role="assistant",
            content=answer,
            sources=json.dumps(sources or [])[:8000],
            confidence_score=str(round(confidence, 3)),
            escalated=escalated,
        )
    )
    sess.updated_at = datetime.utcnow()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    session_id = req.session_id or str(uuid.uuid4())
    history = list(req.history or [])
    uid = _user_id(user)

    if uid and not history:
        existing = await db.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.session_id == session_id, ChatSession.user_id == uid)
        )
        sess = existing.scalar_one_or_none()
        if sess and sess.messages:
            history = [
                {"role": m.role, "content": m.content}
                for m in sorted(sess.messages, key=lambda x: x.created_at or datetime.utcnow())
            ]

    t0 = time.perf_counter()
    result = await rag_pipeline(
        req.message,
        chat_history=history,
        agent_type=req.agent_type or "general",
        db=db,
        user=user,
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0

    points_earned = 0
    if user and user.get("sub") and user.get("role") == "student":
        try:
            conf = result["confidence"]
            concise = len(req.message.strip()) <= 80
            if not result["escalated"]:
                points_earned = 8 if conf >= 0.8 else (5 if conf >= 0.5 else 2)
                if concise:
                    points_earned += 3
            from sqlalchemy import update
            from app.models.user import User
            await db.execute(update(User).where(User.id == uid).values(points=User.points + points_earned))
        except Exception:
            points_earned = 0

    log = QueryLog(
        user_id=uid,
        session_id=session_id,
        query=req.message,
        response_length=len(result["answer"]),
        confidence_score=result["confidence"],
        sources_used=str(result.get("sources", []))[:8000],
        failed=1 if result["escalated"] else 0,
        points_earned=points_earned,
        latency_ms=round(latency_ms, 2),
        retrieval_score=float(result.get("retrieval_score") or 0) or None,
        agent_type=req.agent_type or "general",
    )
    db.add(log)

    if result["escalated"]:
        escalation = EscalationLog(
            session_id=session_id,
            query=req.message,
            confidence_score=result["confidence"],
            response_preview=result["answer"][:200],
            status="pending",
        )
        db.add(escalation)

    answer = result["answer"]
    if result["escalated"]:
        answer = (
            answer
            + "\n\n---\nRedirect to appropriate department:\n"
            + DEPARTMENT_CONTACTS.strip()
        )
    # Final plain-text pass (no markdown chatbot styling)
    import re

    answer = re.sub(r"[*_`#>]{1,}", "", answer or "")
    answer = re.sub(r"\n{3,}", "\n\n", answer).strip()

    try:
        sess = await _get_or_create_session(
            db, session_id, uid, req.message.strip(), agent_type=req.agent_type or "general"
        )
        if sess:
            await _persist_turn(
                db,
                sess,
                req.message,
                answer,
                result.get("sources") or [],
                result["confidence"],
                result["escalated"],
            )
            await save_memory_facts(db, uid, extract_memory_facts(req.message), session_id)
    except HTTPException:
        raise
    except Exception:
        pass

    await db.flush()

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        sources=result.get("sources", []),
        confidence=result["confidence"],
        escalated=result["escalated"],
        diagram=result.get("diagram"),
        points_earned=points_earned,
        data_used=result.get("data_used") or [],
        intent=result.get("intent") or "knowledge",
        kind=result.get("kind") or "knowledge",
        denied=result.get("denied") or [],
        pending_action=result.get("pending_action"),
        needs_confirmation=bool(result.get("needs_confirmation")),
        latency_ms=round(latency_ms, 2),
    )


@router.get("/chat/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    agent_type: str | None = None,
):
    uid = _user_id(user)
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    q = select(ChatSession).where(ChatSession.user_id == uid)
    if agent_type:
        q = q.where(ChatSession.agent_type == agent_type)
    result = await db.execute(q.order_by(ChatSession.updated_at.desc()).limit(50))
    sessions = []
    for s in result.scalars().all():
        sessions.append(
            {
                "session_id": s.session_id,
                "title": s.title or "Discussion",
                "agent_type": getattr(s, "agent_type", None) or "general",
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
        )
    memories = await load_memory_facts(db, uid)
    return {
        "sessions": sessions,
        "memories": [
            {
                "id": m.id,
                "fact": m.fact,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memories
        ],
    }


@router.get("/chat/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = _user_id(user)
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.session_id == session_id, ChatSession.user_id == uid)
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Discussion not found")
    messages = []
    for m in sorted(sess.messages, key=lambda x: x.created_at or datetime.utcnow()):
        sources = []
        if m.sources:
            try:
                sources = json.loads(m.sources)
            except Exception:
                sources = []
        messages.append(
            {
                "role": m.role,
                "content": m.content,
                "sources": sources if m.role == "assistant" else None,
                "escalated": bool(m.escalated),
            }
        )
    return {
        "session_id": sess.session_id,
        "title": sess.title,
        "agent_type": getattr(sess, "agent_type", None) or "general",
        "messages": messages,
    }


@router.delete("/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = _user_id(user)
    result = await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id, ChatSession.user_id == uid)
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Discussion not found")
    await db.execute(sql_delete(ChatMessage).where(ChatMessage.session_id == sess.id))
    await db.execute(sql_delete(ChatSession).where(ChatSession.id == sess.id))
    await db.flush()
    return {"ok": True, "deleted": session_id}


@router.delete("/chat/sessions")
async def delete_all_sessions(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete all chat history for the signed-in user."""
    uid = _user_id(user)
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sessions = (
        await db.execute(select(ChatSession).where(ChatSession.user_id == uid))
    ).scalars().all()
    ids = [s.id for s in sessions]
    if ids:
        await db.execute(sql_delete(ChatMessage).where(ChatMessage.session_id.in_(ids)))
        await db.execute(sql_delete(ChatSession).where(ChatSession.id.in_(ids)))
        await db.flush()
    return {"ok": True, "deleted": len(ids)}


@router.delete("/chat/memory/{memory_id}")
async def delete_memory(
    memory_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = _user_id(user)
    result = await db.execute(select(UserMemory).where(UserMemory.id == memory_id, UserMemory.user_id == uid))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    await db.delete(row)
    await db.flush()
    return {"ok": True}
