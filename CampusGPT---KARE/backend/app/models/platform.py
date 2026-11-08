"""Cross-cutting platform models: audit, sync queue, notification prefs, health events."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.utils.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_email = Column(String(255), default="")
    actor_role = Column(String(40), default="")
    action = Column(String(64), default="")
    resource = Column(String(64), default="")
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SyncOutbox(Base):
    __tablename__ = "sync_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    kind = Column(String(64), default="", index=True)  # apply_leave | fee_pay | change_password
    payload_json = Column(Text, default="{}")
    status = Column(String(20), default="pending", index=True)  # pending | done | failed
    attempts = Column(Integer, default=0)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationPref(Base):
    __tablename__ = "notification_prefs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    email_messages = Column(Boolean, default=True)
    email_fees = Column(Boolean, default=True)
    email_leave = Column(Boolean, default=True)
    inapp_messages = Column(Boolean, default=True)
    inapp_fees = Column(Boolean, default=True)
    inapp_leave = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CampusFactSheet(Base):
    """Authoritative campus knowledge stored in the database (not hardcoded at runtime)."""

    __tablename__ = "campus_fact_sheets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), default="")
    body = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
