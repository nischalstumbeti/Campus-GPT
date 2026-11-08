"""Database models."""
from app.models.user import User, Role
from app.models.chat import ChatSession, ChatMessage, UserMemory
from app.models.privacy import UserConsent, AccessLog, AuditLog, Announcement, Achievement, HostelProfile
from app.models.document import Document
from app.models.escalation import EscalationLog
from app.models.analytics import QueryLog, EvalRun, EvalCaseResult
from app.models.academic import (
    StudentProfile,
    FacultyProfile,
    Course,
    TimetableSlot,
    FacultyAvailability,
    AttendanceSummary,
    MarksRecord,
    AcademicEvent,
    RecurringDraft,
    StudentTask,
    HostelLeave,
)

__all__ = [
    "User",
    "Role",
    "ChatSession",
    "ChatMessage",
    "UserMemory",
    "UserConsent",
    "AccessLog",
    "AuditLog",
    "Announcement",
    "Achievement",
    "HostelProfile",
    "Document",
    "EscalationLog",
    "QueryLog",
    "EvalRun",
    "EvalCaseResult",
    "StudentProfile",
    "FacultyProfile",
    "Course",
    "TimetableSlot",
    "FacultyAvailability",
    "AttendanceSummary",
    "MarksRecord",
    "AcademicEvent",
    "RecurringDraft",
    "StudentTask",
    "HostelLeave",
]
