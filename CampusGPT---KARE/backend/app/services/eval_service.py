"""Evaluation harness: latency + keyword/token accuracy + retrieval hit@k (no invented metrics)."""
from __future__ import annotations

import json
import re
import statistics
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import EvalCaseResult, EvalRun, QueryLog
from app.services.rag_service import rag_pipeline

GOLD_PATH = Path(__file__).resolve().parent.parent / "eval" / "gold_set.json"


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+]+", (text or "").lower()) if len(t) > 1}


def token_f1(pred: str, ref: str) -> float:
    p, r = _tokenize(pred), _tokenize(ref)
    if not p and not r:
        return 1.0
    if not p or not r:
        return 0.0
    overlap = len(p & r)
    precision = overlap / len(p)
    recall = overlap / len(r)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def keyword_hit_rate(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    low = (answer or "").lower()
    hits = sum(1 for k in keywords if (k or "").lower() in low)
    return hits / len(keywords)


def retrieval_keyword_hit(sources: list[dict], keywords: list[str]) -> bool:
    if not keywords:
        return False
    blob = " ".join(
        str(s.get("excerpt") or s.get("source") or s.get("text") or "") for s in (sources or [])
    ).lower()
    # Also treat empty sources as miss
    if not blob.strip():
        return False
    return any((k or "").lower() in blob for k in keywords)


def load_gold_suite() -> dict[str, Any]:
    if not GOLD_PATH.exists():
        return {"suite_name": "empty", "cases": [], "top_k": 5}
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


def summarize_latencies(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"avg": None, "min": None, "max": None, "median": None}
    ordered = sorted(values)
    return {
        "avg": round(statistics.mean(ordered), 2),
        "min": round(ordered[0], 2),
        "max": round(ordered[-1], 2),
        "median": round(statistics.median(ordered), 2),
    }


async def run_gold_evaluation(db: AsyncSession, user: dict | None = None) -> dict[str, Any]:
    suite = load_gold_suite()
    cases = suite.get("cases") or []
    latencies: list[float] = []
    kw_scores: list[float] = []
    f1_scores: list[float] = []
    retrieval_hits = 0
    escalations = 0
    per_case: list[dict] = []

    for case in cases:
        query = (case.get("query") or "").strip()
        agent = (case.get("agent_type") or "general").strip()
        keywords = list(case.get("expected_keywords") or [])
        reference = case.get("reference_answer") or ""

        t0 = time.perf_counter()
        result = await rag_pipeline(query, chat_history=[], agent_type=agent, db=db, user=user)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(latency_ms)

        answer = result.get("answer") or ""
        sources = result.get("sources") or []
        conf = float(result.get("confidence") or 0.0)
        escalated = bool(result.get("escalated"))
        if escalated:
            escalations += 1

        kh = keyword_hit_rate(answer, keywords)
        f1 = token_f1(answer, reference)
        # For refusal cases, keyword hit on the refusal text is the accuracy signal
        rhit = retrieval_keyword_hit(sources, keywords) if not case.get("expect_refusal") else kh >= 0.5
        if rhit:
            retrieval_hits += 1
        kw_scores.append(kh)
        f1_scores.append(f1)

        per_case.append(
            {
                "case_id": case.get("id"),
                "query": query,
                "agent_type": agent,
                "latency_ms": round(latency_ms, 2),
                "confidence": round(conf, 3),
                "escalated": escalated,
                "keyword_hit_rate": round(kh, 3),
                "token_f1": round(f1, 3),
                "retrieval_hit": bool(rhit),
                "answer_preview": answer[:400],
            }
        )

    lat = summarize_latencies(latencies)
    n = max(len(cases), 1)
    summary = {
        "suite_name": suite.get("suite_name") or "campus_gold_v1",
        "case_count": len(cases),
        "latency_ms": lat,
        "keyword_accuracy": round(statistics.mean(kw_scores), 4) if kw_scores else None,
        "token_f1": round(statistics.mean(f1_scores), 4) if f1_scores else None,
        "retrieval_hit_at_k": round(retrieval_hits / n, 4) if cases else None,
        "escalate_rate": round(escalations / n, 4) if cases else None,
        "metric_definitions": {
            "keyword_accuracy": "Mean fraction of expected_keywords found in the model answer (reference-guided).",
            "token_f1": "Mean token-overlap F1 between answer and reference_answer.",
            "retrieval_hit_at_k": "Fraction of cases where at least one expected keyword appears in retrieved source excerpts (or refusal text for expect_refusal cases).",
            "latency_ms": "End-to-end rag_pipeline wall time per gold case.",
        },
        "disclaimer": (
            "These are measured prototype metrics on the bundled gold FAQ suite. "
            "keyword_accuracy / token_f1 are automatic proxies, not human-rated correctness. "
            "They must not be reported as Precision@K / Recall@K unless a chunk-annotated IR study is run."
        ),
        "cases": per_case,
    }

    run = EvalRun(
        suite_name=summary["suite_name"],
        case_count=summary["case_count"],
        latency_avg_ms=lat["avg"],
        latency_min_ms=lat["min"],
        latency_max_ms=lat["max"],
        latency_median_ms=lat["median"],
        keyword_accuracy=summary["keyword_accuracy"],
        token_f1=summary["token_f1"],
        retrieval_hit_at_k=summary["retrieval_hit_at_k"],
        escalate_rate=summary["escalate_rate"],
        notes=summary["disclaimer"],
        raw_json=json.dumps(summary)[:200000],
    )
    db.add(run)
    await db.flush()
    for c in per_case:
        db.add(
            EvalCaseResult(
                run_id=run.id,
                case_id=c["case_id"],
                query=c["query"],
                agent_type=c["agent_type"],
                latency_ms=c["latency_ms"],
                confidence=c["confidence"],
                escalated=c["escalated"],
                keyword_hit_rate=c["keyword_hit_rate"],
                token_f1=c["token_f1"],
                retrieval_hit=c["retrieval_hit"],
                answer_preview=c["answer_preview"],
            )
        )
    summary["run_id"] = run.id
    return summary


async def live_latency_stats(db: AsyncSession, limit: int = 500) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(QueryLog.latency_ms)
            .where(QueryLog.latency_ms.is_not(None))
            .order_by(QueryLog.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    values = [float(v) for v in rows if v is not None]
    stats = summarize_latencies(values)
    return {
        "sample_size": len(values),
        "latency_ms": stats,
        "note": "From production query_logs with recorded latency_ms (empty until traffic after deploy).",
    }


async def latest_eval_run(db: AsyncSession) -> dict[str, Any] | None:
    run = (
        await db.execute(select(EvalRun).order_by(EvalRun.id.desc()).limit(1))
    ).scalar_one_or_none()
    if not run:
        return None
    cases = (
        await db.execute(
            select(EvalCaseResult).where(EvalCaseResult.run_id == run.id).order_by(EvalCaseResult.id)
        )
    ).scalars().all()
    return {
        "run_id": run.id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "suite_name": run.suite_name,
        "case_count": run.case_count,
        "latency_ms": {
            "avg": run.latency_avg_ms,
            "min": run.latency_min_ms,
            "max": run.latency_max_ms,
            "median": run.latency_median_ms,
        },
        "keyword_accuracy": run.keyword_accuracy,
        "token_f1": run.token_f1,
        "retrieval_hit_at_k": run.retrieval_hit_at_k,
        "escalate_rate": run.escalate_rate,
        "notes": run.notes,
        "cases": [
            {
                "case_id": c.case_id,
                "query": c.query,
                "agent_type": c.agent_type,
                "latency_ms": c.latency_ms,
                "confidence": c.confidence,
                "escalated": c.escalated,
                "keyword_hit_rate": c.keyword_hit_rate,
                "token_f1": c.token_f1,
                "retrieval_hit": c.retrieval_hit,
                "answer_preview": c.answer_preview,
            }
            for c in cases
        ],
    }
