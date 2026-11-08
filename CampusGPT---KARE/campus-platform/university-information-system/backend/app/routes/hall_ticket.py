from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import CourseOffering, Enrollment, ExamSchedule, HallTicketSettings, Program, User
from app.security.auth import require_roles
from app.services.attendance_board import courses_for_student
from app.services.audit import write_audit
from app.services.hall_ticket_pdf import build_hall_ticket_pdf, ticket_lines

router = APIRouter(prefix="/api/v1", tags=["hall-ticket"])
EditRoles = require_roles("university_admin", "admin", "super_admin", "developer", "coe")


async def _settings(db: AsyncSession) -> HallTicketSettings:
    row = (await db.execute(select(HallTicketSettings).order_by(HallTicketSettings.id))).scalars().first()
    if row:
        return row
    row = HallTicketSettings(
        enabled=False,
        institution="Campus Information System",
        title="Hall Ticket",
        session_name="End Semester Examination",
        instructions="Bring this hall ticket and your identity card. Report 30 minutes before the examination.",
        footer="This hall ticket is valid only for the examinations listed above.",
        min_attendance=75.0,
        require_overall=True,
        require_subject=True,
    )
    db.add(row)
    await db.flush()
    return row


async def _ticket(db: AsyncSession, user: User) -> dict:
    student = user.student
    if not student:
        raise HTTPException(status_code=403, detail="Student profile required")
    settings = await _settings(db)
    enrollments = (
        await db.execute(
            select(Enrollment)
            .where(Enrollment.student_id == student.id)
            .options(selectinload(Enrollment.offering).selectinload(CourseOffering.course))
        )
    ).scalars().all()
    course_ids = [row.offering.course_id for row in enrollments if row.offering]
    exams = []
    if course_ids:
        rows = (
            await db.execute(
                select(ExamSchedule)
                .where(ExamSchedule.course_id.in_(course_ids))
                .options(selectinload(ExamSchedule.course))
                .order_by(ExamSchedule.exam_date, ExamSchedule.start_time)
            )
        ).scalars().all()
        exams = [
            {
                "code": row.course.code,
                "course": row.course.title,
                "type": row.exam_type,
                "date": row.exam_date.strftime("%d/%m/%Y"),
                "start": row.start_time,
                "venue": row.venue,
            }
            for row in rows
            if row.course
        ]
    courses = await courses_for_student(db, student.id)
    by_code = {row["code"]: row for row in courses}
    attended = sum(row["attended"] for row in courses)
    conducted = sum(row["conducted"] for row in courses)
    overall = round(100.0 * attended / conducted, 1) if conducted else 0.0
    minimum = 75.0 if settings.min_attendance is None else float(settings.min_attendance)
    require_overall = bool(settings.require_overall)
    require_subject = bool(settings.require_subject)
    overall_ok = (not require_overall) or overall >= minimum
    eligible = []
    withheld = []
    for exam in exams:
        course = by_code.get(exam["code"])
        percentage = float(course["percentage"]) if course else 0.0
        subject_ok = (not require_subject) or percentage >= minimum
        if overall_ok and subject_ok:
            eligible.append({**exam, "attendance": percentage})
        else:
            withheld.append(
                {
                    "code": exam["code"],
                    "course": exam["course"],
                    "attendance": percentage,
                    "reason": (
                        f"Overall attendance is {overall}%. The hall ticket needs {minimum:g}% or more."
                        if not overall_ok
                        else f"{exam['code']} attendance is {percentage}%. This subject needs {minimum:g}% or more."
                    ),
                }
            )
    program_row = await db.get(Program, student.program_id) if student.program_id else None
    program = program_row.name if program_row else ""
    return {
        "enabled": bool(settings.enabled),
        "institution": settings.institution,
        "title": settings.title,
        "session_name": settings.session_name,
        "instructions": settings.instructions or "",
        "footer": settings.footer or "",
        "name": user.full_name,
        "student_id": student.student_id,
        "program": program,
        "batch": student.batch,
        "semester": student.semester,
        "section": student.section,
        "photo_url": student.photo_url or "",
        "min_attendance": minimum,
        "require_overall": require_overall,
        "require_subject": require_subject,
        "overall_attendance": overall,
        "overall_ok": overall_ok,
        "exams": eligible,
        "withheld": withheld,
    }


class HallTicketIn(BaseModel):
    enabled: bool
    institution: str = Field(default="Campus Information System", max_length=160)
    title: str = Field(default="Hall Ticket", min_length=1, max_length=160)
    session_name: str = Field(default="", max_length=160)
    instructions: str = Field(default="", max_length=2000)
    footer: str = Field(default="", max_length=255)
    min_attendance: float = Field(default=75, ge=0, le=100)
    require_overall: bool = True
    require_subject: bool = True


@router.get("/student/hall-ticket")
async def student_hall_ticket(
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ticket = await _ticket(db, user)
    if not ticket["enabled"]:
        return {"enabled": False}
    return ticket


@router.get("/student/hall-ticket/pdf")
async def student_hall_ticket_pdf(
    user: Annotated[User, Depends(require_roles("student"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ticket = await _ticket(db, user)
    if not ticket["enabled"]:
        raise HTTPException(status_code=403, detail="The hall ticket has not been enabled.")
    if not ticket["exams"]:
        detail = ticket["withheld"][0]["reason"] if ticket["withheld"] else "No subject meets the attendance rule for the hall ticket."
        raise HTTPException(status_code=403, detail=detail)
    pdf = build_hall_ticket_pdf(ticket_lines(ticket))
    filename = f"hall-ticket-{ticket['student_id']}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/admin/hall-ticket")
async def admin_hall_ticket(
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _settings(db)
    return {
        "enabled": bool(row.enabled),
        "institution": row.institution,
        "title": row.title,
        "session_name": row.session_name,
        "instructions": row.instructions or "",
        "footer": row.footer or "",
        "min_attendance": 75.0 if row.min_attendance is None else float(row.min_attendance),
        "require_overall": bool(row.require_overall),
        "require_subject": bool(row.require_subject),
    }


@router.put("/admin/hall-ticket")
async def save_hall_ticket(
    body: HallTicketIn,
    user: Annotated[User, Depends(EditRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _settings(db)
    row.enabled = body.enabled
    row.institution = body.institution.strip() or "Campus Information System"
    row.title = body.title.strip() or "Hall Ticket"
    row.session_name = body.session_name.strip()
    row.instructions = body.instructions.strip()
    row.footer = body.footer.strip()
    row.min_attendance = body.min_attendance
    row.require_overall = body.require_overall
    row.require_subject = body.require_subject
    await write_audit(
        db,
        actor="UIS Admin",
        user_ref=user.username,
        role=user.role,
        resource="hall_ticket",
        action="ENABLE" if body.enabled else "DISABLE",
        purpose=row.title,
        result="ALLOWED",
    )
    return {"ok": True, "enabled": row.enabled}
