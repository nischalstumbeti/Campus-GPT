"""Admin-managed scrolling marquee (CMS)."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.utils.database import Base


class MarqueeItem(Base):
    __tablename__ = "marquee_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    icon = Column(String(32), default="📢")
    description = Column(Text, default="")
    active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    updated_by = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
