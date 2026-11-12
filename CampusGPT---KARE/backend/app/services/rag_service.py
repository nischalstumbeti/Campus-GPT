"""RAG pipeline service - Retrieval Augmented Generation. Uses Gemini only."""
import asyncio
from app.config import get_settings
from app.services.demo_responses import get_demo_response
from app.utils.prompt_validator import is_valid_prompt

settings = get_settings()

# Lazy init - only when API key is present
_genai = None


def _is_internet_issue(exc: BaseException) -> bool:
    msg = f"{type(exc).__name__} {exc}".lower()
    tokens = (
        "failed to resolve",
        "nameresolution",
        "getaddrinfo",
        "network is unreachable",
        "connection aborted",
        "connection reset",
        "connection refused",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "unreachable",
        "offline",
        "nodename nor servname",
        "max retries exceeded",
        "connecterror",
        "connect timeout",
        "sslerror",
        "temporary failure in name resolution",
    )
    return any(t in msg for t in tokens)


def _live_settings():
    return get_settings()


def reset_gemini() -> None:
    """Drop the cached client after an admin saves a new Gemini key."""
    global _genai, _resolved_chat_model
    _genai = None
    _resolved_chat_model = None


def _get_genai():
    global _genai
    key = (_live_settings().GEMINI_API_KEY or "").strip()
    if _genai is None and key:
        import google.generativeai as genai
        genai.configure(api_key=key)
        _genai = genai
    return _genai


# Preferred chat models (first configured, then known-good fallbacks)
_CHAT_MODEL_FALLBACKS = (
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-pro-latest",
)

# Cache the first model that works for this process
_resolved_chat_model: str | None = None


def _chat_model_candidates() -> list[str]:
    primary = (_live_settings().GEMINI_CHAT_MODEL or "").strip()
    out: list[str] = []
    if primary:
        out.append(primary)
    for m in _CHAT_MODEL_FALLBACKS:
        if m not in out:
            out.append(m)
    return out


async def _gemini_generate(genai, prompt: str) -> str:
    """Call Gemini with model fallbacks when a model id is retired/unavailable."""
    global _resolved_chat_model
    import logging

    log = logging.getLogger(__name__)
    last_err: Exception | None = None
    models = list(_chat_model_candidates())
    if _resolved_chat_model and _resolved_chat_model in models:
        models = [_resolved_chat_model] + [m for m in models if m != _resolved_chat_model]

    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 900},
            )
            text = response.text if response and hasattr(response, "text") and response.text else ""
            if text.strip():
                _resolved_chat_model = model_name
                return text
            last_err = RuntimeError(f"Empty response from {model_name}")
        except Exception as exc:
            last_err = exc
            msg = str(exc).lower()
            # Retry next model when this model id is retired/unavailable
            if any(t in msg for t in ("not found", "no longer available", "not supported", "404")):
                log.warning(
                    "Gemini model %s failed (%s); trying fallback",
                    model_name,
                    type(exc).__name__,
                )
                continue
            raise
    if last_err:
        raise last_err
    return ""


from app.services.embeddings import get_embedding
from app.services.vector_store import get_vector_store

def _get_agent_context(agent_type: str) -> str:
    """Return agent persona description."""
    from app.services.agent_scope import agent_persona

    return agent_persona(agent_type)


SYSTEM_PROMPT = """You are Campus-GPT for Kalasalingam Academy of Research and Education (KARE).

Answer using only the provided university records and knowledge excerpts.

Style rules (important):
1. Write in plain normal text only. Do not sound like a chatbot or say you are an AI.
2. Do not use markdown bold/italic/headings (no **, *, #, code fences, or emoji).
3. For large structured data (timetable, attendance, marks, faculty schedule), keep the pipe table from context exactly — do not flatten it into a clumsy paragraph.
4. Use only facts from the context. Never invent marks, attendance, roll numbers, fees, or dates.
5. If the record is missing, say so plainly and suggest the right office (Academic Office, Hostel Warden, or Accounts).
6. When leave has already been submitted by the system, confirm the details plainly without inventing a new request.
7. Refuse cheating, impersonation, hacking, harassment, fake attendance, leaked papers, and any request to bypass campus rules.
8. Never change a measured figure. If a number is not in the evidence, say it was not measured.
9. Do not reveal another person's private marks, attendance, password, or contact details. Campus-wide counts are allowed.
10. If the evidence is not enough, name the gap and the office that can confirm it. A short correct answer is better than a full guess."""


async def retrieve_context(query: str, top_k: int = None) -> tuple[list[str], list[dict], float]:
    """Retrieve relevant chunks from vector store (works with local embeddings too)."""
    top_k = top_k or settings.RAG_TOP_K
    store = get_vector_store()
    if store.count() == 0:
        return [], [], 0.0
    query_embedding = await get_embedding(query)
    if not query_embedding:
        return [], [], 0.0
    results = store.search(query_embedding, top_k=top_k)

    if not results:
        return [], [], 0.0

    chunks = []
    sources = []
    avg_score = 0.0
    for meta, score in results:
        chunks.append(meta.get("text", meta.get("content", "")))
        sources.append({
            "source": meta.get("source", "Unknown"),
            "page": meta.get("page"),
            "relevance": round(score, 2),
        })
        avg_score += score

    avg_score = avg_score / len(results) if results else 0
    return chunks, sources, avg_score


async def generate_response(
    query: str,
    context_chunks: list[str],
    chat_history: list[dict] = None,
    agent_type: str = "general",
    long_term_memory: str = "",
    db=None,
    extra_context: str = "",
) -> tuple[str, float, list[dict]]:
    """Generate response using Gemini with context."""
    genai = _get_genai()
    if not genai:
        # Prefer knowledge-base chunks over hardcoded demo FAQ when Gemini is offline
        if context_chunks:
            clean = (context_chunks[0] or "").strip()
            if clean:
                return (
                    clean[:1200],
                    0.65,
                    [{"source": "Campus knowledge (database)", "excerpt": clean[:180]}],
                )
        return get_demo_response(query, agent_type=agent_type)

    context = "\n\n---\n\n".join(context_chunks) if context_chunks else ""
    history_lines = []
    for m in (chat_history or [])[-12:]:
        role = (m.get("role") or "user").capitalize()
        content = (m.get("content") or "").strip()
        if content:
            history_lines.append(f"{role}: {content[:600]}")
    history_block = "\n".join(history_lines)

    agent_context = _get_agent_context(agent_type)
    campus_brief = ""
    if (agent_type or "").lower() in ("reception", "general"):
        try:
            from app.services.campus_facts import reception_context_block_async

            campus_brief = await reception_context_block_async(db)
        except Exception:
            campus_brief = ""

    if not context and not history_block and not long_term_memory and not campus_brief and not (extra_context or "").strip():
        return (
            "I don't have enough verified information to answer that accurately. "
            "For academics (timetable, attendance, marks, faculty) ask from the Campus tools or contact the Academic Office. "
            "For admissions contact admission@kluniversity.ac.in; hostel hostel@kluniversity.ac.in; "
            "finance fees@kluniversity.ac.in; placement placement@kluniversity.ac.in.",
            0.0,
            [],
        )

    user_content = f"""You are responding as: {agent_context}

{long_term_memory or ""}

Official campus fact sheet (use freely for college-wide questions):
{campus_brief or "(none)"}

Recent discussion (this chat):
{history_block or "(new discussion)"}

Context from knowledge base and academic database:
{context or "(none)"}

Measured campus evidence (copy these figures exactly; do not round or replace them):
{extra_context or "(none)"}

User question: {query}

Answer PRECISELY in plain normal text (no markdown). Prefer academic-database facts for timetable, attendance, marks, faculty, and planning.
For Reception/Front Desk, give complete campus information (contacts, directions, admissions overview, fees overview, hostel overview, placements, facilities, office hours) using the fact sheet above.
Use long-term memory and recent discussion for follow-ups and personalization.
If a personal academic record is missing, say so — do not invent numbers."""

    try:
        full_prompt = f"""{SYSTEM_PROMPT}

---
{user_content}"""
        answer = await _gemini_generate(genai, full_prompt)
        if not (answer or "").strip():
            raise RuntimeError("Empty Gemini answer")
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("Gemini generate failed: %s", e)
        evidence = (extra_context or context or "").strip()
        if evidence:
            return (
                evidence[:1600],
                0.45,
                [{"source": "Live campus records", "excerpt": evidence[:180]}],
            )
        if _is_internet_issue(e) and not context_chunks:
            return (
                "Internet issue. Check your connection and try again.",
                0.0,
                [],
            )
        # Prefer curated FAQ / demo answers over a raw error banner
        demo_answer, demo_conf, demo_sources = get_demo_response(query, agent_type=agent_type)
        if context_chunks and demo_conf < 0.7:
            clean = (context_chunks[0] or "").strip()
            if clean:
                return (
                    clean[:1200],
                    0.7,
                    [{"source": "Campus knowledge", "excerpt": clean[:180]}],
                )
        return demo_answer, max(demo_conf, 0.7), demo_sources

    confidence = 0.85 if context else 0.3
    if "don't have enough" in answer.lower() or "verified information" in answer.lower():
        confidence = 0.4

    sources = []
    for i, chunk in enumerate(context_chunks):
        sources.append({"id": i + 1, "excerpt": chunk[:200] + "..." if len(chunk) > 200 else chunk})

    return answer, confidence, sources


async def rag_pipeline(
    query: str,
    chat_history: list[dict] = None,
    agent_type: str = "general",
    db=None,
    user: dict | None = None,
    extra_context: str = "",
) -> dict:
    """Full RAG pipeline: retrieve -> generate -> return. Uses demo mode if no API key."""
    from app.services.academic_service import detect_academic_intent

    valid, err_msg = is_valid_prompt(query)
    if not valid:
        return {
            "answer": err_msg or "I can only help with institute academics, admissions, and campus services.",
            "confidence": 0.0,
            "sources": [],
            "escalated": False,
            "retrieval_score": 0.0,
            "diagram": None,
        }

    academic_context = None
    long_term_memory = ""
    data_used: list[dict] = []
    intent_name = "knowledge"
    denied: list[str] = []

    from app.ai.intent import classify_intent, greeting_reply, is_greeting, response_kind as _rk
    from app.services.agent_scope import (
        hostel_off_topic_reply,
        is_clearly_off_hostel,
        is_hostel_scoped_query,
        should_enforce_hostel_only,
    )

    agent = (agent_type or "general").lower()

    # Reception: complete college briefing from DB fact sheet
    if agent == "reception":
        try:
            from app.services.campus_facts import reception_full_reply_async, wants_full_campus_brief

            if wants_full_campus_brief(query):
                full = await reception_full_reply_async(db)
                if full:
                    return {
                        "answer": full,
                        "confidence": 1.0,
                        "sources": [
                            {
                                "source": "campus_fact_sheets (database)",
                                "excerpt": "Campus identity, contacts, programs, fees, hostel, placements",
                                "relevance": 1.0,
                            }
                        ],
                        "escalated": False,
                        "retrieval_score": 1.0,
                        "diagram": None,
                        "data_used": [{"data": "Reception fact sheet", "source": "database", "permission": "public"}],
                        "intent": "knowledge",
                        "kind": "fact",
                        "denied": [],
                    }
        except Exception:
            pass

    # Short greetings: never pull faculty/timetable dumps
    if is_greeting(query) or classify_intent(query) == "greeting":
        return {
            "answer": greeting_reply(user),
            "confidence": 1.0,
            "sources": [],
            "escalated": False,
            "retrieval_score": 1.0,
            "diagram": None,
            "data_used": [],
            "intent": "greeting",
            "kind": "greeting",
            "denied": [],
        }

    # Hostel / Warden desks: only hostel-related discussion
    if should_enforce_hostel_only(agent) and (
        is_clearly_off_hostel(query) or not is_hostel_scoped_query(query)
    ):
        # Allow vague short follow-ups only when they still look hostel-ish; otherwise redirect
        if is_clearly_off_hostel(query) or len((query or "").split()) >= 3:
            return {
                "answer": hostel_off_topic_reply(),
                "confidence": 1.0,
                "sources": [],
                "escalated": False,
                "retrieval_score": 1.0,
                "diagram": None,
                "data_used": [],
                "intent": "scope_redirect",
                "kind": "fact",
                "denied": [],
            }

    # Agentic action: propose leave apply (confirm in UI before UIS write)
    # Leave is a hostel workflow — allow on hostel/warden/reception/general
    if db is not None and agent in ("hostel", "warden", "reception", "general", "academic"):
        try:
            from app.services.agent_actions import try_apply_leave

            if agent in ("hostel", "warden") or is_hostel_scoped_query(query):
                action = await try_apply_leave(db, user, query)
                if action and action.get("handled"):
                    return {
                        "answer": action.get("answer") or "Leave request processed.",
                        "confidence": 1.0 if action.get("ok") else 0.7,
                        "sources": [{"source": "KARE UIS", "excerpt": "Hostel leave application", "relevance": 1.0}],
                        "escalated": False,
                        "retrieval_score": 1.0,
                        "diagram": None,
                        "data_used": action.get("data_used") or [],
                        "intent": "workflow",
                        "kind": "fact",
                        "denied": [],
                        "pending_action": action.get("pending_action"),
                        "needs_confirmation": bool(action.get("needs_confirmation")),
                    }
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("try_apply_leave failed: %s", exc)

    if db is not None:
        try:
            from app.gateway.data_gateway import assemble, DENIED_MESSAGE

            # Hostel desk: only assemble hostel/leave/complaint personal records
            if should_enforce_hostel_only(agent) and not is_hostel_scoped_query(query):
                return {
                    "answer": hostel_off_topic_reply(),
                    "confidence": 1.0,
                    "sources": [],
                    "escalated": False,
                    "retrieval_score": 1.0,
                    "diagram": None,
                    "data_used": [],
                    "intent": "scope_redirect",
                    "kind": "fact",
                    "denied": [],
                }

            # FAQ desks — avoid hijacking college questions with personal SIS overview dumps
            skip_personal = False
            qlow = (query or "").lower()
            personal_sis = any(
                t in qlow
                for t in (
                    "my fee",
                    "my fees",
                    "my marks",
                    "my attendance",
                    "my timetable",
                    "my hostel",
                    "my room",
                    "my leave",
                )
            )
            if agent == "admission":
                admission_faq = any(
                    t in qlow
                    for t in (
                        "application fee",
                        "admission fee",
                        "eligibility",
                        "how to apply",
                        "programs",
                        "scholarship",
                        "documents required",
                        "admission process",
                        "cutoff",
                    )
                )
                skip_personal = admission_faq and not personal_sis
            elif agent == "reception":
                campus_info = any(
                    t in qlow
                    for t in (
                        "about kare",
                        "about college",
                        "about the university",
                        "about university",
                        "complete information",
                        "campus",
                        "college",
                        "university",
                        "facilities",
                        "contact",
                        "where is",
                        "direction",
                        "office hours",
                        "visiting",
                        "programs",
                        "admission",
                        "scholarship",
                        "placement",
                        "library",
                        "examination branch",
                        "department",
                    )
                )
                # Reception answers college-wide questions from fact sheet + RAG
                skip_personal = campus_info and not personal_sis

            if skip_personal:
                bundle = None
            else:
                bundle = await assemble(db, user, query)

            if bundle is None:
                academic_context = None
                data_used = []
                intent_name = "knowledge"
                denied = []
            else:
                academic_context = bundle.text or None
                data_used = bundle.data_used
                intent_name = bundle.intent
                denied = bundle.denied
            if bundle and bundle.intent == "greeting":
                return {
                    "answer": bundle.text or greeting_reply(user),
                    "confidence": 1.0,
                    "sources": [],
                    "escalated": False,
                    "retrieval_score": 1.0,
                    "diagram": None,
                    "data_used": [],
                    "intent": "greeting",
                    "kind": "greeting",
                    "denied": [],
                }
            # Hard stop when assist master switch or specific consents block personal answers
            consent_blocked = bool(bundle) and (
                "campus_gpt.assist" in (denied or [])
                or (
                    denied
                    and not data_used
                    and intent_name not in ("knowledge", "greeting", "faculty_directory")
                    and academic_context
                )
                or (bundle.text == DENIED_MESSAGE and not data_used)
            )
            if consent_blocked and academic_context and bundle:
                return {
                    "answer": academic_context,
                    "confidence": 1.0,
                    "sources": [],
                    "escalated": False,
                    "retrieval_score": 0.0,
                    "diagram": None,
                    "data_used": [],
                    "intent": bundle.intent,
                    "kind": "fact",
                    "denied": bundle.denied,
                }
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("assemble failed: %s", exc)
            academic_context = None
            # Do not silently continue into personal demo answers when gateway crashed mid-consent
            if user and user.get("role") == "student":
                return {
                    "answer": "I could not load authorized campus records right now. Please try again shortly.",
                    "confidence": 0.2,
                    "sources": [],
                    "escalated": True,
                    "retrieval_score": 0.0,
                    "diagram": None,
                    "data_used": [],
                    "intent": "knowledge",
                    "kind": "fact",
                    "denied": [],
                }
        if user and user.get("sub"):
            try:
                from app.services.memory_service import load_memory_text
                long_term_memory = await load_memory_text(db, int(user["sub"]))
            except Exception:
                long_term_memory = ""

    # Only keep academic intent when the user actually asked for academic data
    academic_intent = detect_academic_intent(query)

    kind = _rk(intent_name)
    extras = {
        "data_used": data_used,
        "intent": intent_name,
        "kind": kind,
        "denied": denied,
    }

    try:
        from app.services.live_campus import live_records_text

        live_text = await live_records_text()
    except Exception:
        live_text = ""
    if live_text:
        extra_context = (extra_context + "\n\nLive university records:\n" + live_text).strip()
        data_used = list(data_used) + [
            {
                "data": "Live campus counts",
                "purpose": "Current attendance, fees, and notices",
                "source": "UIS",
                "permission": "aggregate",
                "access": "Authorized",
                "why": "The answer uses the latest university counts, with no student names.",
            }
        ]
        extras["data_used"] = data_used

    # Without Gemini, a ready personal record is the answer. With a key, Gemini writes from those records.
    if academic_context and intent_name not in ("knowledge", "greeting") and data_used:
        extra_context = (extra_context + "\n\nAuthorized records for this person:\n" + academic_context).strip()
        if not (_live_settings().GEMINI_API_KEY or "").strip():
            return {
                "answer": academic_context,
                "confidence": 0.95,
                "sources": [{"source": "Academic database", "excerpt": "Authorized campus records", "relevance": 1.0}],
                "escalated": False,
                "retrieval_score": 1.0,
                "diagram": None,
                **extras,
            }

    if not (_live_settings().GEMINI_API_KEY or "").strip():
        if academic_context and intent_name not in ("knowledge", "greeting"):
            return {
                "answer": academic_context,
                "confidence": 0.9,
                "sources": [{"source": "Academic database", "excerpt": "Live SIS records", "relevance": 1.0}],
                "escalated": False,
                "retrieval_score": 1.0,
                "diagram": None,
                **extras,
            }
        if live_text:
            return {
                "answer": live_text,
                "confidence": 0.9,
                "sources": [{"source": "UIS", "excerpt": live_text[:180], "relevance": 1.0}],
                "escalated": False,
                "retrieval_score": 1.0,
                "diagram": None,
                **extras,
            }
        answer, confidence, response_sources = get_demo_response(query, agent_type=agent_type)
        return {
            "answer": answer,
            "confidence": confidence,
            "sources": response_sources,
            "escalated": confidence < settings.CONFIDENCE_THRESHOLD,
            "retrieval_score": 0.0,
            "diagram": None,
            **extras,
        }

    chunks, sources, retrieval_score = await retrieve_context(query)
    if academic_context:
        chunks = [academic_context] + list(chunks)
        sources = [{"source": "Academic database", "excerpt": academic_context[:180], "relevance": 1.0}] + list(sources)
        retrieval_score = max(retrieval_score, 0.95)

    answer, confidence, response_sources = await generate_response(
        query,
        chunks,
        chat_history,
        agent_type=agent_type,
        long_term_memory=long_term_memory,
        db=db,
        extra_context=extra_context,
    )

    if academic_context:
        confidence = max(confidence, 0.88)

    for i, src in enumerate(response_sources):
        if i < len(sources):
            src.update(sources[i])

    escalated = False
    if settings.ESCALATION_ENABLED and confidence < settings.CONFIDENCE_THRESHOLD:
        escalated = True

    # Diagram generation intentionally skipped (plain-text chat only)

    if intent_name == "knowledge" and not sources and not academic_context:
        if not answer or "don't have enough" in (answer or "").lower():
            answer = (
                "I could not find an official university source for this. "
                "Please check with the Academic Office or the department office."
            )
            confidence = 0.2

    # Keep replies as normal plain text (no markdown / chatbot styling)
    import re

    answer = re.sub(r"[*_`#>]{1,}", "", answer or "")
    answer = re.sub(r"\n{3,}", "\n\n", answer).strip()

    return {
        "answer": answer,
        "confidence": confidence,
        "sources": response_sources,
        "escalated": escalated,
        "retrieval_score": retrieval_score,
        "diagram": None,  # keep chat answers as plain text only
        **extras,
    }
