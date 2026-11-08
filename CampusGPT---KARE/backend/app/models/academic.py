"""Academic records: timetable, faculty, attendance, marks, calendar."""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from datetime import datetime

from app.utils.database import Base


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    roll_no = Column(String(40), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    program = Column(String(120), default="B.Tech")
    department = Column(String(80), default="CSE")
    semester = Column(Integer, default=5)
    section = Column(String(8), default="A")
    batch = Column(String(20), default="2024-28")


class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    employee_id = Column(String(40), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    department = Column(String(80), default="CSE")
    designation = Column(String(120), default="Assistant Professor")
    cabin = Column(String(40), default="")
    email = Column(String(255), default="")
    phone = Column(String(40), default="")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    department = Column(String(80), default="CSE")
    credits = Column(Integer, default=3)
    semester = Column(Integer, default=5)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id"), nullable=True)


class TimetableSlot(Base):
    __tablename__ = "timetable_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id"), nullable=True)
    day_of_week = Column(String(16), nullable=False)  # Monday
    start_time = Column(String(8), nullable=False)  # 09:00
    end_time = Column(String(8), nullable=False)
    room = Column(String(40), default="")
    section = Column(String(8), default="A")
    semester = Column(Integer, default=5)
    department = Column(String(80), default="CSE")


class FacultyAvailability(Base):
    __tablename__ = "faculty_availability"

    id = Column(Integer, primary_key=True, autoincrement=True)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id"), nullable=False)
    day_of_week = Column(String(16), nullable=False)
    start_time = Column(String(8), nullable=False)
    end_time = Column(String(8), nullable=False)
    kind = Column(String(32), default="office_hours")  # office_hours | meeting | leave
    location = Column(String(80), default="")
    notes = Column(String(255), default="")


class AttendanceSummary(Base):
    __tablename__ = "attendance_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    conducted = Column(Integer, default=0)
    present = Column(Integer, default=0)
    od = Column(Integer, default=0)


class MarksRecord(Base):
    __tablename__ = "marks_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    assessment = Column(String(40), nullable=False)  # CAT-1, CAT-2, Assignment, Lab
    marks = Column(Float, nullable=False)
    max_marks = Column(Float, default=50)
    recorded_on = Column(String(20), default="")


class AcademicEvent(Base):
    __tablename__ = "academic_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    event_type = Column(String(40), default="general")  # exam | holiday | meeting | deadline
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), default="")
    recurrence = Column(String(20), default="none")  # none | weekly
    description = Column(Text, default="")


class RecurringDraft(Base):
    __tablename__ = "recurring_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    draft_type = Column(String(40), nullable=False)
    body = Column(Text, nullable=False)
    recurrence = Column(String(20), default="weekly")
    created_by = Column(String(120), default="Campus-GPT")
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentTask(Base):
    __tablename__ = "student_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    notes = Column(Text, default="")
    due_date = Column(String(20), default="")
    status = Column(String(20), default="open")  # open | done
    category = Column(String(40), default="academic")
    created_at = Column(DateTime, default=datetime.utcnow)


class HostelLeave(Base):
    __tablename__ = "hostel_leaves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False, index=True)
    from_date = Column(String(20), nullable=False)
    to_date = Column(String(20), nullable=False)
    reason = Column(String(255), nullable=False)
    destination = Column(String(120), default="")
    status = Column(String(20), default="pending")  # pending | approved | rejected
    created_at = Column(DateTime, default=datetime.utcnow)
