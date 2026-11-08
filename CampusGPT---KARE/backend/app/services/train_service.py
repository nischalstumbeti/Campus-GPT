"""Admin-triggered knowledge training: rebuild FAISS from seed + UIS campus data."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import numpy as np

from app.config import get_settings
from app.services.embeddings import get_embedding
from app.services.vector_store import get_vector_store, reset_vector_store
from app.utils.seed_knowledge import SAMPLE_KNOWLEDGE
from app.services import uis_client

logger = logging.getLogger(__name__)


def _local_embedding(text: str, dim: int) -> list[float]:
    """Deterministic fallback embedding when Gemini is unavailable."""
    vec = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    if not tokens:
        tokens = ["empty"]
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec)) or 1.0
    vec /= norm
    return vec.tolist()


async def _embed_texts(texts: list[str], source: str) -> tuple[list[list[float]], list[dict], str]:
    settings = get_settings()
    dim = settings.EMBEDDING_DIM
    embeddings: list[list[float]] = []
    metadatas: list[dict] = []
    mode = "gemini"
    gemini_ok = 0
    for i, text in enumerate(texts):
        text = (text or "").strip()
        if not text:
            continue
        emb: list[float] = []
        try:
            emb = await get_embedding(text)
        except Exception as exc:
            logger.warning("Embedding failed for chunk %s (%s): %s", i, source, exc)
        if not emb or len(emb) != dim:
            emb = _local_embedding(text, dim)
            mode = "local_fallback"
        else:
            gemini_ok += 1
        embeddings.append(emb)
        metadatas.append({"text": text, "content": text, "source": source, "chunk_id": i})
    if gemini_ok and mode == "local_fallback":
        mode = "mixed"
    elif gemini_ok == len(embeddings) and embeddings:
        mode = "gemini"
    return embeddings, metadatas, mode


async def collect_uis_training_texts() -> list[str]:
    """Pull live UIS public/campus facts so Campus-GPT stays mapped to UMS."""
    texts: list[str] = []
    try:
        notices = await uis_client.get_announcements()
        for n in notices or []:
            title = (n.get("title") or "").strip()
            body = (n.get("body") or "").strip()
            if title or body:
                texts.append(f"UIS Announcement: {title}. {body}".strip())
    except Exception as exc:
        logger.warning("UIS announcements for train skipped: %s", exc)

    try:
        faculty = await uis_client.get_faculty()
        # Collapse directory into compact chunks (by faculty name)
        by_name: dict[str, list[str]] = {}
        for row in faculty or []:
            name = (row.get("faculty") or "Faculty").strip()
            kind = row.get("kind") or "availability"
            day = row.get("day") or ""
            start = row.get("start") or row.get("start_time") or ""
            end = row.get("end") or row.get("end_time") or ""
            loc = row.get("location") or ""
            note = row.get("notes") or ""
            line = f"{kind}: {day} {start}-{end} @ {loc}".strip()
            if note:
                line += f" ({note})"
            by_name.setdefault(name, []).append(line)
        for name, lines in by_name.items():
            texts.append(f"UIS Faculty directory — {name}: " + "; ".join(lines[:8]))
    except Exception as exc:
        logger.warning("UIS faculty for train skipped: %s", exc)

    texts.append(
        "Campus-GPT is linked to KARE UIS (University Information System). "
        "Student academics (attendance, marks, timetable, leave, hostel) come from UIS when the account is linked. "
        "Hostel leave is approved by the hostel warden or faculty; status updates are emailed to the student."
    )
    return texts


async def collect_consented_student_texts() -> tuple[list[str], int, int]:
    """Include only students who allowed campus_gpt.train. Skip denied consents."""
    from sqlalchemy import select
    from app.utils.database import AsyncSessionLocal
    from app.models.user import User, Role
    from app.models.academic import StudentProfile
    from app.services import consent as consents

    texts: list[str] = []
    included = 0
    skipped = 0
    async with AsyncSessionLocal() as db:
        students = (await db.execute(select(User).where(User.role == Role.STUDENT))).scalars().all()
        for u in students:
            allowed = await consents.is_allowed(db, u.id, "campus_gpt.train")
            if not allowed:
                skipped += 1
                continue
            profile = (
                await db.execute(select(StudentProfile).where(StudentProfile.user_id == u.id))
            ).scalar_one_or_none()
            if not profile:
                continue
            # Anonymized / aggregate-safe training snippet (no email)
            texts.append(
                f"Student cohort profile: program {profile.program}, department {profile.department}, "
                f"semester {profile.semester}, section {profile.section}, batch {profile.batch}."
            )
            included += 1
    return texts, included, skipped


async def train_model() -> dict[str, Any]:
    """
    Rebuild the RAG index so the AI assistant answers students/faculty
    from institutional seed data + live UIS campus information.
    Students who denied Campus-GPT train consent are excluded.
    """
    store = reset_vector_store()
    texts = list(SAMPLE_KNOWLEDGE)
    uis_texts = await collect_uis_training_texts()
    texts.extend(uis_texts)
    student_texts, included, skipped = await collect_consented_student_texts()
    texts.extend(student_texts)

    embeddings, metadatas, embed_mode = await _embed_texts(texts, source="admin_train")
    if embeddings:
        store.add(np.array(embeddings, dtype=np.float32), metadatas)

    return {
        "ok": True,
        "message": (
            "Model knowledge base trained. Campus-GPT will use this data for student and faculty answers. "
            f"Included {included} consented student profile(s); skipped {skipped} who denied train consent."
            + (" (local embeddings used because Gemini embed API was unavailable)" if embed_mode != "gemini" else "")
        ),
        "chunks_indexed": store.count(),
        "seed_chunks": len(SAMPLE_KNOWLEDGE),
        "uis_chunks": len(uis_texts),
        "student_chunks": len(student_texts),
        "students_included": included,
        "students_skipped_no_consent": skipped,
        "embedding_mode": embed_mode,
        "sources": ["KARE_seed", "UIS_announcements", "UIS_faculty", "consented_students", "integration_map"],
    }
