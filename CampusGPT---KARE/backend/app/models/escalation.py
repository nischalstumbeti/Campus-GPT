"""Escalation model for flagged queries."""
from sqlalchemy import Column, String, DateTime, Integer, Text, Float
from datetime import datetime

from app.utils.database import Base


class EscalationLog(Base):
    """Log of escalated (low-confidence) queries."""
    __tablename__ = "escalation_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100))
    query = Column(Text)
    confidence_score = Column(Float)
    response_preview = Column(Text)
    status = Column(String(50), default="pending")  # pending, resolved
    resolved_by = Column(Integer)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
