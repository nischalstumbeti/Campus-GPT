from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), index=True)  # student, faculty, hod, admin, ...
    department_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    photo_url: Mapped[str] = mapped_column(Text, default="")
    designation: Mapped[str] = mapped_column(String(80), default="")
    cabin_block: Mapped[str] = mapped_column(String(80), default="")
    school: Mapped[str] = mapped_column(String(120), default="")
    office: Mapped[str] = mapped_column(String(120), default="")
    abc_id: Mapped[str] = mapped_column(String(32), default="")
    residence: Mapped[str] = mapped_column(String(24), default="")
    transport: Mapped[str] = mapped_column(String(24), default="")
    residence_detail: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped[Optional["StudentProfile"]] = relationship(back_populates="user", uselist=False)
    faculty: Mapped[Optional["FacultyProfile"]] = relationship(back_populates="user", uselist=False)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(255))


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    degree_type: Mapped[str] = mapped_column(String(32), default="B.Tech")
    duration_years: Mapped[int] = mapped_column(Integer, default=4)
    total_credits: Mapped[int] = mapped_column(Integer, default=160)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    credits: Mapped[int] = mapped_column(Integer, default=3)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    result_group: Mapped[str] = mapped_column(String(16), default="cgpa")


class CourseOffering(Base):
    __tablename__ = "course_offerings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    faculty_id: Mapped[Optional[int]] = mapped_column(ForeignKey("faculty_profiles.id"), nullable=True)
    semester: Mapped[int] = mapped_column(Integer)
    academic_year: Mapped[str] = mapped_column(String(16))
    section: Mapped[str] = mapped_column(String(8), default="A")

    course: Mapped["Course"] = relationship()
    faculty: Mapped[Optional["FacultyProfile"]] = relationship()


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    student_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"))
    batch: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    semester: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(8), default="A")
    cgpa: Mapped[float] = mapped_column(Float, default=0.0)
    credits_completed: Mapped[int] = mapped_column(Integer, default=0)
    credits_required: Mapped[int] = mapped_column(Integer, default=160)
    backlogs: Mapped[int] = mapped_column(Integer, default=0)
    overall_attendance: Mapped[float] = mapped_column(Float, default=0.0)
    photo_url: Mapped[str] = mapped_column(Text, default="")

    user: Mapped["User"] = relationship(back_populates="student")
    program: Mapped["Program"] = relationship()


class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    faculty_id: Mapped[str] = mapped_column(String(32), unique=True)
    designation: Mapped[str] = mapped_column(String(64), default="Assistant Professor")
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))

    user: Mapped["User"] = relationship(back_populates="faculty")
    department: Mapped["Department"] = relationship()
    availability: Mapped[list["FacultyAvailability"]] = relationship(back_populates="faculty")


class FacultyAdvisor(Base):
    """Faculty advisor or mentor for a section, or for one student."""

    __tablename__ = "faculty_advisors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty_profiles.id"))
    scope: Mapped[str] = mapped_column(String(16), default="section")
    section: Mapped[str] = mapped_column(String(8), default="")
    batch: Mapped[str] = mapped_column(String(16), default="")
    student_id: Mapped[Optional[int]] = mapped_column(ForeignKey("student_profiles.id"), nullable=True)

    faculty: Mapped["FacultyProfile"] = relationship()
    student: Mapped[Optional["StudentProfile"]] = relationship()


class FacultyAvailability(Base):
    __tablename__ = "faculty_availability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty_profiles.id"))
    day_of_week: Mapped[str] = mapped_column(String(16))  # Monday
    start_time: Mapped[str] = mapped_column(String(8))
    end_time: Mapped[str] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(32), default="office_hours")
    location: Mapped[str] = mapped_column(String(80), default="")
    notes: Mapped[str] = mapped_column(String(255), default="")

    faculty: Mapped["FacultyProfile"] = relationship(back_populates="availability")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "offering_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"))
    status: Mapped[str] = mapped_column(String(16), default="active")

    student: Mapped["StudentProfile"] = relationship()
    offering: Mapped["CourseOffering"] = relationship()


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id"))
    attended: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)

    enrollment: Mapped["Enrollment"] = relationship()


class AttendanceSession(Base):
    """One class period: date, slot, and P / A / OD / ML / RH / EH."""

    __tablename__ = "attendance_sessions"
    __table_args__ = (UniqueConstraint("enrollment_id", "entry_date", "slot_name", name="uq_attendance_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id"))
    entry_date: Mapped[date] = mapped_column(Date)
    slot_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(8), default="P")

    enrollment: Mapped["Enrollment"] = relationship()

    @property
    def percentage(self) -> float:
        if self.total <= 0:
            return 0.0
        return round(100.0 * self.attended / self.total, 1)


class Mark(Base):
    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id"))
    assessment: Mapped[str] = mapped_column(String(64))  # CAT-1, CAT-2, Assignment, EndSem
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float, default=100.0)

    enrollment: Mapped["Enrollment"] = relationship()


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id"), unique=True)
    letter: Mapped[str] = mapped_column(String(4))
    grade_point: Mapped[float] = mapped_column(Float)

    enrollment: Mapped["Enrollment"] = relationship()


class ExamApplicationWindow(Base):
    """Admin switch for revaluation, arrear, and backlog applications."""

    __tablename__ = "exam_application_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(500), default="")
    fee: Mapped[float] = mapped_column(Float, default=0.0)


class ExamApplication(Base):
    __tablename__ = "exam_applications"
    __table_args__ = (UniqueConstraint("student_id", "kind", "course_id", name="uq_exam_application"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="submitted")
    advisor_status: Mapped[str] = mapped_column(String(16), default="pending")
    hod_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["StudentProfile"] = relationship()
    course: Mapped["Course"] = relationship()


class RegistrationRequest(Base):
    """Course registration or withdrawal, approved by the faculty advisor and then the HoD."""

    __tablename__ = "registration_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    offering_ids: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(24), default="submitted")
    advisor_status: Mapped[str] = mapped_column(String(16), default="pending")
    hod_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["StudentProfile"] = relationship()


class HallTicketSettings(Base):
    """Admin-designed hall ticket. Students can open it only while enabled."""

    __tablename__ = "hall_ticket_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    institution: Mapped[str] = mapped_column(String(160), default="Campus Information System")
    title: Mapped[str] = mapped_column(String(160), default="Hall Ticket")
    session_name: Mapped[str] = mapped_column(String(160), default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    footer: Mapped[str] = mapped_column(String(255), default="")
    min_attendance: Mapped[float] = mapped_column(Float, default=75.0)
    require_overall: Mapped[bool] = mapped_column(Boolean, default=True)
    require_subject: Mapped[bool] = mapped_column(Boolean, default=True)


class TimetableSlot(Base):
    __tablename__ = "timetable_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"))
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Mon
    start_time: Mapped[str] = mapped_column(String(8))
    end_time: Mapped[str] = mapped_column(String(8))
    room: Mapped[str] = mapped_column(String(32))

    offering: Mapped["CourseOffering"] = relationship()


class ExamSchedule(Base):
    __tablename__ = "exam_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    exam_type: Mapped[str] = mapped_column(String(32))
    exam_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[str] = mapped_column(String(8))
    venue: Mapped[str] = mapped_column(String(64))
    semester: Mapped[int] = mapped_column(Integer)
    paper_text: Mapped[str] = mapped_column(Text, default="")

    course: Mapped["Course"] = relationship()


class Hostel(Base):
    __tablename__ = "hostels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    gender: Mapped[str] = mapped_column(String(16), default="mixed")


class HostelBlock(Base):
    __tablename__ = "hostel_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    name: Mapped[str] = mapped_column(String(64))

    hostel: Mapped["Hostel"] = relationship()


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_id: Mapped[int] = mapped_column(ForeignKey("hostel_blocks.id"))
    room_number: Mapped[str] = mapped_column(String(16))
    capacity: Mapped[int] = mapped_column(Integer, default=2)

    block: Mapped["HostelBlock"] = relationship()


class HostelAllocation(Base):
    __tablename__ = "hostel_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), unique=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    bed_no: Mapped[str] = mapped_column(String(8), default="A")
    status: Mapped[str] = mapped_column(String(16), default="active")

    student: Mapped["StudentProfile"] = relationship()
    room: Mapped["Room"] = relationship()


class HostelLeave(Base):
    __tablename__ = "hostel_leaves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(255))
    destination: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    source: Mapped[str] = mapped_column(String(32), default="uis")  # uis | campus-gpt
    decision_note: Mapped[str] = mapped_column(String(500), default="")
    faculty_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|rejected
    hostel_status: Mapped[str] = mapped_column(String(16), default="pending")

    student: Mapped["StudentProfile"] = relationship()


class HostelAttendance(Base):
    """Night roll call for hostel inmates. One status per student per date."""

    __tablename__ = "hostel_attendance"
    __table_args__ = (UniqueConstraint("student_id", "entry_date", name="uq_hostel_attendance"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    entry_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(8), default="P")

    student: Mapped["StudentProfile"] = relationship()


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64))
    awarded_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")

    student: Mapped["StudentProfile"] = relationship()


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(32), default="all")
    department_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IntegrationConsent(Base):
    __tablename__ = "integration_consents"
    __table_args__ = (UniqueConstraint("user_id", "permission_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    permission_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="deny")  # allow | deny | revoke (opt-in)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    user_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    resource: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(128), default="")
    result: Mapped[str] = mapped_column(String(32))


class Complaint(Base):
    """Student-raised issues routed to faculty, hostel warden, or anyone who can resolve."""

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    category: Mapped[str] = mapped_column(String(32), default="general")
    # hostel | faculty | any — who should primarily handle it
    audience: Mapped[str] = mapped_column(String(16), default="any", index=True)
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)  # open | in_progress | resolved | closed
    resolver_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolver_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    student: Mapped["StudentProfile"] = relationship()


# --- Fees (shared SoR with Campus-GPT) ---


class FeePlan(Base):
    __tablename__ = "fee_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32), default="all", index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    deadline: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudentFee(Base):
    __tablename__ = "student_fees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fee_plans.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="Semester fee")
    category: Mapped[str] = mapped_column(String(32), default="all")
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    deadline: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(24), default="due")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments: Mapped[list["FeePayment"]] = relationship(back_populates="fee", cascade="all, delete-orphan")


class FeePayment(Base):
    __tablename__ = "fee_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fee_id: Mapped[int] = mapped_column(ForeignKey("student_fees.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[str] = mapped_column(String(32), default="mock_upi")
    note: Mapped[str] = mapped_column(String(255), default="")
    receipt_no: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    fee: Mapped["StudentFee"] = relationship(back_populates="payments")


class FeeReminder(Base):
    __tablename__ = "fee_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("student_fees.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    triggered_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


# --- Messages / notifications (shared SoR with Campus-GPT) ---


class MessageThread(Base):
    __tablename__ = "message_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), default="Issue")
    category: Mapped[str] = mapped_column(String(64), default="general")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    redirected_to: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[list["DirectMessage"]] = relationship(back_populates="thread", cascade="all, delete-orphan")


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("message_threads.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    read: Mapped[bool] = mapped_column(Boolean, default=False)

    thread: Mapped["MessageThread"] = relationship(back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("direct_messages.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255), default="file")
    stored_name: Mapped[str] = mapped_column(String(80), default="")
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)

    message: Mapped["DirectMessage"] = relationship(back_populates="attachments")


class AppNotification(Base):
    __tablename__ = "app_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="message")
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(120), default="/messages")
    thread_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MarqueeItem(Base):
    """Admin-managed scrolling marquee (CMS) — admin login only."""

    __tablename__ = "marquee_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    icon: Mapped[str] = mapped_column(String(32), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    link_url: Mapped[str] = mapped_column(String(500), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BrandingSettings(Base):
    """Admin CMS — branding / theme (colors, fonts, backgrounds)."""

    __tablename__ = "branding_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    primary: Mapped[str] = mapped_column(String(32), default="#0B2A4A")
    primary_dark: Mapped[str] = mapped_column(String(32), default="#071E36")
    secondary: Mapped[str] = mapped_column(String(32), default="#1E4A7A")
    accent: Mapped[str] = mapped_column(String(32), default="#C9A227")
    bg_light: Mapped[str] = mapped_column(String(32), default="#F4F7FB")
    bg_card: Mapped[str] = mapped_column(String(32), default="#FFFFFF")
    text_color: Mapped[str] = mapped_column(String(32), default="#0F172A")
    font_family: Mapped[str] = mapped_column(String(255), default="Verdana, Tahoma, sans-serif")
    font_size_base: Mapped[str] = mapped_column(String(16), default="16px")
    heading_scale: Mapped[str] = mapped_column(String(16), default="1.25")
    background_image_url: Mapped[str] = mapped_column(Text, default="")
    background_overlay: Mapped[str] = mapped_column(String(16), default="0.9")
    login_background_url: Mapped[str] = mapped_column(Text, default="")
    logo_url: Mapped[str] = mapped_column(Text, default="")
    header_title: Mapped[str] = mapped_column(String(160), default="")
    header_subtitle: Mapped[str] = mapped_column(String(255), default="")
    footer_text: Mapped[str] = mapped_column(Text, default="")
    sign_in_label: Mapped[str] = mapped_column(String(80), default="")
    app_name: Mapped[str] = mapped_column(String(120), default="")
    updated_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
