"""Consent, access history, and security audit (no raw secrets)."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from datetime import datetime

from app.utils.database import Base


class UserConsent(Base):
    __tablename__ = "user_consents"
    __table_args__ = (UniqueConstraint("user_id", "permission_key", name="uq_user_permission"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    permission_key = Column(String(80), nullable=False)
    status = Column(String(16), default="allow")  # allow | deny
    purpose = Column(String(255), default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AccessLog(Base):
    """Shown in Privacy Center — data accessed for assistance."""
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    data_type = Column(String(80), nullable=False)
    purpose = Column(String(255), default="")
    component = Column(String(80), default="copilot")
    permission_key = Column(String(80), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(80), nullable=False)
    detail = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, default="")
    category = Column(String(40), default="general")
    audience = Column(String(40), default="all")  # all | student | faculty | warden
    department = Column(String(80), default="")
    effective_date = Column(String(20), default="")
    source = Column(String(255), default="Official notice")
    important = Column(Integer, default=0)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False, index=True)
    kind = Column(String(40), default="cert")  # cert | award | activity
    title = Column(String(255), nullable=False)
    detail = Column(String(255), default="")
    year = Column(String(8), default="")


class HostelProfile(Base):
    __tablename__ = "hostel_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), unique=True, nullable=False)
    hostel = Column(String(80), default="KARE Men's / Women's Hostel")
    block = Column(String(20), default="B")
    room = Column(String(20), default="")
    mess = Column(String(40), default="South Indian veg/non-veg")
