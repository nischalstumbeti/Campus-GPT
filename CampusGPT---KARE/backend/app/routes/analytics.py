"""Analytics API - usage insights. Identifies common concerns for administrators."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db
from app.utils.auth import require_admin
from app.models.analytics import QueryLog
from app.models.escalation import EscalationLog
from app.models.user import User, Role

router = APIRouter()

# Keyword categories for identifying common concerns
CONCERN_CATEGORIES = {
    "eligibility": ["eligibility", "qualify", "criteria", "cutoff", "marks required", "minimum"],
    "fees": ["fee", "fees", "tuition", "cost", "charges", "payment"],
    "scholarships": ["scholarship", "financial", "fee waiver", "merit", "sc st", "aid"],
    "courses": ["courses", "programs", "branches", "btech", "mtech", "mba", "bca", "compare", "which branch"],
    "hostel": ["hostel", "accommodation", "stay", "room", "boarding", "mess", "warden"],
    "placement": ["placement", "job", "salary", "package", "recruitment", "companies"],
    "admission_process": ["application", "apply", "admission", "process", "how to"],
    "documents": ["documents", "required", "certificates"],
    "facilities": ["facilities", "campus", "library", "lab", "infrastructure"],
    "accreditation": ["naac", "nirf", "ranking", "accredited"],
    "deadlines": ["last date", "deadline", "closing", "when to apply"],
    "academics": ["timetable", "attendance", "marks", "exam", "grade"],
}


async def _top_queries(db: AsyncSession, limit: int = 20) -> list[dict]:
    top_result = await db.execute(
        select(QueryLog.query, func.count(QueryLog.id).label("count"))
        .group_by(QueryLog.query)
        .order_by(desc("count"))
        .limit(limit)
    )
    return [{"query": r[0], "count": r[1]} for r in top_result]


def _common_concerns(top_queries: list[dict]) -> dict:
    common_concerns: dict[str, int] = {}
    for item in top_queries:
        q_lower = (item.get("query") or "").lower()
        cnt = item.get("count", 1)
        for cat, keywords in CONCERN_CATEGORIES.items():
            if any(k in q_lower for k in keywords):
                common_concerns[cat] = common_concerns.get(cat, 0) + cnt
                break
    return dict(sorted(common_concerns.items(), key=lambda x: -x[1]))


async def _leaderboard(db: AsyncSession, limit: int = 10) -> list[dict]:
    """Student points leaderboard (no secrets)."""
    if not hasattr(User, "points"):
        return []
    rows = (
        await db.execute(
            select(User)
            .where(User.role == Role.STUDENT)
            .order_by(desc(User.points))
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "name": u.full_name or u.email or "Student",
            "email": (u.email or "")[:3] + "***" if u.email else "",
            "points": int(getattr(u, "points", 0) or 0),
        }
        for u in rows
        if int(getattr(u, "points", 0) or 0) > 0
    ]


@router.get("/analytics")
async def get_analytics(
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Get analytics: top queries, failed queries, trends."""
    _ = user
    top_queries = await _top_queries(db, 20)

    failed_result = await db.execute(
        select(QueryLog)
        .where(QueryLog.failed == 1)
        .order_by(desc(QueryLog.created_at))
        .limit(limit)
    )
    failed_queries = [
        {"query": q.query, "confidence": q.confidence_score, "created_at": str(q.created_at)}
        for q in failed_result.scalars().all()
    ]

    esc_result = await db.execute(
        select(EscalationLog)
        .order_by(desc(EscalationLog.created_at))
        .limit(limit)
    )
    escalations = [
        {
            "query": e.query,
            "confidence": e.confidence_score,
            "status": e.status,
            "created_at": str(e.created_at),
        }
        for e in esc_result.scalars().all()
    ]

    total_result = await db.execute(select(func.count(QueryLog.id)))
    total_queries = total_result.scalar() or 0
    failed_count_result = await db.execute(select(func.count(QueryLog.id)).where(QueryLog.failed == 1))
    failed_count = failed_count_result.scalar() or 0
    common_concerns = _common_concerns(top_queries)

    return {
        "top_queries": top_queries,
        "failed_queries": failed_queries,
        "escalations": escalations,
        "common_concerns": common_concerns,
        "summary": {
            "total_queries": total_queries,
            "failed_count": failed_count,
            "failure_rate": round(failed_count / total_queries * 100, 2) if total_queries else 0,
        },
    }


@router.get("/analytics/public")
async def get_analytics_public(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Admin aggregate stats used by Admin Overview + Analytics pages."""
    _ = user
    total_result = await db.execute(select(func.count(QueryLog.id)))
    total_queries = total_result.scalar() or 0
    failed_count_result = await db.execute(select(func.count(QueryLog.id)).where(QueryLog.failed == 1))
    failed_count = failed_count_result.scalar() or 0
    top_queries = await _top_queries(db, 20)
    try:
        leaderboard = await _leaderboard(db)
    except Exception:
        leaderboard = []
    return {
        "total_queries": total_queries,
        "failed_count": failed_count,
        "top_queries": top_queries,
        "common_concerns": _common_concerns(top_queries),
        "leaderboard": leaderboard,
    }
