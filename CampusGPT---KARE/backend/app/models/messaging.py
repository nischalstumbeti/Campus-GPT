"""Direct messages between students / faculty / admin (issue threads)."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from app.utils.database import Base


class MessageThread(Base):
    __tablename__ = "message_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(255), default="Issue")
    category = Column(String(64), default="general")  # academic | hostel | fees | other
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # admin/faculty
    status = Column(String(32), default="open", index=True)  # open | redirected | closed
    redirected_to = Column(String(64), default="")  # student_login | faculty | warden | admin
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("DirectMessage", back_populates="thread", cascade="all, delete-orphan")


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey("message_threads.id"), index=True, nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    body = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)

    thread = relationship("MessageThread", back_populates="messages")
