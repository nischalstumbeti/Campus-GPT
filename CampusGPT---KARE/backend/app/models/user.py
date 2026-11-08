"""User model and roles."""
from enum import Enum
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, Integer
from sqlalchemy.orm import relationship
from datetime import datetime

from app.utils.database import Base


class Role(str, Enum):
    """User roles for access control."""
    STUDENT = "student"
    FACULTY = "faculty"
    HOSTEL_ADMIN = "hostel_admin"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(SQLEnum(Role), default=Role.STUDENT)
    points = Column(Integer, default=0)  # earned for careful usage, good queries
    uis_username = Column(String(128), nullable=True, index=True)  # linked UIS identity
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user")
