"""Remove a user or course together with the records that belong to it."""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Achievement,
    AppNotification,
    AttendanceRecord,
    AttendanceSession,
    Complaint,
    Course,
    CourseOffering,
    DirectMessage,
    Enrollment,
    ExamApplication,
    ExamSchedule,
    FacultyAdvisor,
    FacultyAvailability,
    FacultyProfile,
    FeePayment,
    FeeReminder,
    Grade,
    HostelAllocation,
    HostelAttendance,
    HostelLeave,
    IntegrationConsent,
    Mark,
    MessageAttachment,
    MessageThread,
    RegistrationRequest,
    StudentFee,
    StudentProfile,
    TimetableSlot,
    User,
)


async def _ids(db: AsyncSession, stmt) -> list[int]:
    return [row[0] for row in (await db.execute(stmt)).all()]


async def _drop(db: AsyncSession, model, column, ids: list[int]) -> None:
    if ids:
        await db.execute(delete(model).where(column.in_(ids)))


async def delete_enrollments(db: AsyncSession, enrollment_ids: list[int]) -> None:
    await _drop(db, AttendanceSession, AttendanceSession.enrollment_id, enrollment_ids)
    await _drop(db, AttendanceRecord, AttendanceRecord.enrollment_id, enrollment_ids)
    await _drop(db, Mark, Mark.enrollment_id, enrollment_ids)
    await _drop(db, Grade, Grade.enrollment_id, enrollment_ids)
    await _drop(db, Enrollment, Enrollment.id, enrollment_ids)


async def delete_offerings(db: AsyncSession, offering_ids: list[int]) -> None:
    if not offering_ids:
        return
    enrollment_ids = await _ids(db, select(Enrollment.id).where(Enrollment.offering_id.in_(offering_ids)))
    await delete_enrollments(db, enrollment_ids)
    await _drop(db, TimetableSlot, TimetableSlot.offering_id, offering_ids)
    await _drop(db, CourseOffering, CourseOffering.id, offering_ids)


async def delete_student_profile(db: AsyncSession, student_id: int) -> None:
    enrollment_ids = await _ids(db, select(Enrollment.id).where(Enrollment.student_id == student_id))
    await delete_enrollments(db, enrollment_ids)
    for model, column in (
        (ExamApplication, ExamApplication.student_id),
        (RegistrationRequest, RegistrationRequest.student_id),
        (HostelAllocation, HostelAllocation.student_id),
        (HostelLeave, HostelLeave.student_id),
        (HostelAttendance, HostelAttendance.student_id),
        (Achievement, Achievement.student_id),
        (Complaint, Complaint.student_id),
        (FacultyAdvisor, FacultyAdvisor.student_id),
    ):
        await db.execute(delete(model).where(column == student_id))
    await db.execute(delete(StudentProfile).where(StudentProfile.id == student_id))


async def delete_faculty_profile(db: AsyncSession, faculty_id: int) -> None:
    await db.execute(
        update(CourseOffering).where(CourseOffering.faculty_id == faculty_id).values(faculty_id=None)
    )
    await db.execute(delete(FacultyAdvisor).where(FacultyAdvisor.faculty_id == faculty_id))
    await db.execute(delete(FacultyAvailability).where(FacultyAvailability.faculty_id == faculty_id))
    await db.execute(delete(FacultyProfile).where(FacultyProfile.id == faculty_id))


async def _delete_messages_for_user(db: AsyncSession, user_id: int) -> None:
    own_threads = await _ids(db, select(MessageThread.id).where(MessageThread.created_by == user_id))
    sent = await _ids(db, select(DirectMessage.id).where(DirectMessage.sender_id == user_id))
    thread_messages = await _ids(db, select(DirectMessage.id).where(DirectMessage.thread_id.in_(own_threads))) if own_threads else []
    message_ids = list({*sent, *thread_messages})
    await _drop(db, MessageAttachment, MessageAttachment.message_id, message_ids)
    await _drop(db, DirectMessage, DirectMessage.id, message_ids)
    await _drop(db, MessageThread, MessageThread.id, own_threads)
    await db.execute(update(MessageThread).where(MessageThread.assignee_id == user_id).values(assignee_id=None))
    await db.execute(delete(AppNotification).where(AppNotification.user_id == user_id))


async def delete_user_record(db: AsyncSession, target: User) -> None:
    student = (
        await db.execute(select(StudentProfile).where(StudentProfile.user_id == target.id))
    ).scalar_one_or_none()
    faculty = (
        await db.execute(select(FacultyProfile).where(FacultyProfile.user_id == target.id))
    ).scalar_one_or_none()
    if student:
        await delete_student_profile(db, student.id)
    if faculty:
        await delete_faculty_profile(db, faculty.id)
    fee_ids = await _ids(db, select(StudentFee.id).where(StudentFee.user_id == target.id))
    await _drop(db, FeePayment, FeePayment.fee_id, fee_ids)
    await _drop(db, FeeReminder, FeeReminder.fee_id, fee_ids)
    await db.execute(delete(FeeReminder).where(FeeReminder.user_id == target.id))
    await _drop(db, StudentFee, StudentFee.id, fee_ids)
    await db.execute(delete(IntegrationConsent).where(IntegrationConsent.user_id == target.id))
    await _delete_messages_for_user(db, target.id)
    await db.execute(delete(User).where(User.id == target.id))


async def delete_course_record(db: AsyncSession, course: Course) -> None:
    offering_ids = await _ids(db, select(CourseOffering.id).where(CourseOffering.course_id == course.id))
    await delete_offerings(db, offering_ids)
    await db.execute(delete(ExamApplication).where(ExamApplication.course_id == course.id))
    await db.execute(delete(ExamSchedule).where(ExamSchedule.course_id == course.id))
    await db.execute(delete(Course).where(Course.id == course.id))
