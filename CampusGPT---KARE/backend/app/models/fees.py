"""Mock fee plans, student dues, installments, and reminders."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from app.utils.database import Base


class FeePlan(Base):
    """Deadline + amount template for a student category."""

    __tablename__ = "fee_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    category = Column(String(32), default="all", index=True)  # all | hostel | day_scholar | bus
    amount = Column(Float, default=0.0)
    deadline = Column(String(32), default="")  # YYYY-MM-DD
    notes = Column(Text, default="")
    active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentFee(Base):
    """Per-student fee account (can override plan amount/deadline)."""

    __tablename__ = "student_fees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("fee_plans.id"), nullable=True)
    title = Column(String(200), default="Semester fee")
    category = Column(String(32), default="all")
    total_amount = Column(Float, default=0.0)
    paid_amount = Column(Float, default=0.0)
    deadline = Column(String(32), default="")
    status = Column(String(24), default="due")  # due | partial | paid | overdue
    editable_splits = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments = relationship("FeePayment", back_populates="fee", cascade="all, delete-orphan")


class FeePayment(Base):
    __tablename__ = "fee_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fee_id = Column(Integer, ForeignKey("student_fees.id"), index=True)
    amount = Column(Float, default=0.0)
    method = Column(String(32), default="mock_upi")
    note = Column(String(255), default="")
    receipt_no = Column(String(64), default="", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    fee = relationship("StudentFee", back_populates="payments")


class FeeReminder(Base):
    __tablename__ = "fee_reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fee_id = Column(Integer, ForeignKey("student_fees.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    message = Column(Text, default="")
    triggered_by = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)
