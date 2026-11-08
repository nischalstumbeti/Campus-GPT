"""Analytics model for query logging and offline evaluation runs."""
from sqlalchemy import Column, String, DateTime, Integer, Text, Float, Boolean
from datetime import datetime

from app.utils.database import Base


class QueryLog(Base):
    """Log of user queries for analytics."""
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)  # null = guest
    session_id = Column(String(100))
    query = Column(Text)
    response_length = Column(Integer)
    confidence_score = Column(Float)
    sources_used = Column(Text)  # JSON
    failed = Column(Integer, default=0)  # 1 if failed/low confidence
    points_earned = Column(Integer, default=0)  # points awarded for this query
    latency_ms = Column(Float, nullable=True)  # end-to-end RAG/chat latency
    retrieval_score = Column(Float, nullable=True)
    agent_type = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalRun(Base):
    """One execution of the Campus-GPT evaluation harness."""
    __tablename__ = "eval_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    suite_name = Column(String(120), default="campus_gold_v1")
    case_count = Column(Integer, default=0)
    latency_avg_ms = Column(Float, nullable=True)
    latency_min_ms = Column(Float, nullable=True)
    latency_max_ms = Column(Float, nullable=True)
    latency_median_ms = Column(Float, nullable=True)
    keyword_accuracy = Column(Float, nullable=True)  # mean keyword hit rate
    token_f1 = Column(Float, nullable=True)  # mean token F1 vs reference
    retrieval_hit_at_k = Column(Float, nullable=True)  # fraction with keyword in sources
    escalate_rate = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)  # full per-case results


class EvalCaseResult(Base):
    """Per-question result inside an eval run."""
    __tablename__ = "eval_case_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(Integer, index=True, nullable=False)
    case_id = Column(String(64))
    query = Column(Text)
    agent_type = Column(String(40), default="general")
    latency_ms = Column(Float)
    confidence = Column(Float)
    escalated = Column(Boolean, default=False)
    keyword_hit_rate = Column(Float)
    token_f1 = Column(Float)
    retrieval_hit = Column(Boolean, default=False)
    answer_preview = Column(Text)
