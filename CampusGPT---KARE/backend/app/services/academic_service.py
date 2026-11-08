"""Academic operations: timetable, attendance, marks, faculty, planning, drafts."""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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
)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

INTENT_KEYWORDS = {
    "timetable": ["timetable", "time table", "class schedule", "today's class", "todays class", "tomorrow class", "which class", "period", "lab slot"],
    "attendance": ["attendance", "absent", "present", "shortage", "75%"],
    "marks": ["marks", "grades", "result", "cat-1", "cat 1", "cat-2", "internal mark", "score"],
    "faculty": ["faculty available", "office hours", "is professor", "staff available", "cabin", "when can i meet", "availability of"],
    "planning": ["plan my", "study plan", "academic schedule", "when should i", "prepare for cat", "free slot", "planner"],
    "forecast": ["forecast", "predict", "will i", "shortage if", "can i miss", "projected"],
    "leave": ["hostel leave", "leave application", "apply leave", "going home"],
    "draft": ["draft", "circular", "notice", "recurring reminder", "announcement", "meeting invite"],
}


def detect_academic_intent(query: str) -> Optional[str]:
    q = (query or "").lower()
    for intent, keys in INTENT_KEYWORDS.items():
        if any(k in q for k in keys):
            return intent
    return None


def _pct(present: int, conducted: int) -> float:
    if not conducted:
        return 0.0
    return round(100.0 * present / conducted, 1)


async def _courses_map(db: AsyncSession) -> dict[int, Course]:
    rows = (await db.execute(select(Course))).scalars().all()
    return {c.id: c for c in rows}


async def _faculty_map(db: AsyncSession) -> dict[int, FacultyProfile]:
    rows = (await db.execute(select(FacultyProfile))).scalars().all()
    return {f.id: f for f in rows}


async def resolve_student(db: AsyncSession, user: Optional[dict]) -> tuple[Optional[StudentProfile], bool]:
    """Return the logged-in student's SIS profile. Guests get nothing."""
    if not user or not str(user.get("sub", "")).isdigit():
        return None, False
    uid = int(user["sub"])
    row = (await db.execute(select(StudentProfile).where(StudentProfile.user_id == uid))).scalar_one_or_none()
    return (row, False) if row else (None, False)


async def resolve_faculty(db: AsyncSession, user: Optional[dict]) -> Optional[FacultyProfile]:
    """Own faculty profile only. Never fall back to a demo colleague."""
    if not user or not str(user.get("sub", "")).isdigit():
        return None
    if user.get("role") not in ("faculty", "admin", "super_admin"):
        return None
    uid = int(user["sub"])
    return (await db.execute(select(FacultyProfile).where(FacultyProfile.user_id == uid))).scalar_one_or_none()


def serialize_student(s: StudentProfile) -> dict:
    return {
        "roll_no": s.roll_no,
        "full_name": s.full_name,
        "program": s.program,
        "department": s.department,
        "semester": s.semester,
        "section": s.section,
        "batch": s.batch,
    }


async def get_timetable(db: AsyncSession, student: StudentProfile, day: Optional[str] = None) -> list[dict]:
    courses = await _courses_map(db)
    faculty = await _faculty_map(db)
    q = select(TimetableSlot).where(
        TimetableSlot.department == student.department,
        TimetableSlot.semester == student.semester,
        TimetableSlot.section == student.section,
    )
    if day:
        q = q.where(TimetableSlot.day_of_week == day.capitalize())
    rows = (await db.execute(q)).scalars().all()
    out = []
    for slot in rows:
        course = courses.get(slot.course_id)
        fac = faculty.get(slot.faculty_id) if slot.faculty_id else None
        out.append({
            "day": slot.day_of_week,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "course_code": course.code if course else "",
            "course_name": course.name if course else "",
            "faculty": fac.full_name if fac else "",
            "room": slot.room,
            "section": slot.section,
        })
    out.sort(key=lambda x: (DAYS.index(x["day"]) if x["day"] in DAYS else 99, x["start_time"]))
    return out


async def get_attendance(db: AsyncSession, student: StudentProfile) -> list[dict]:
    courses = await _courses_map(db)
    rows = (await db.execute(select(AttendanceSummary).where(AttendanceSummary.student_id == student.id))).scalars().all()
    result = []
    for row in rows:
        course = courses.get(row.course_id)
        pct = _pct(row.present + row.od, row.conducted)
        result.append({
            "course_code": course.code if course else "",
            "course_name": course.name if course else "",
            "conducted": row.conducted,
            "present": row.present,
            "od": row.od,
            "percentage": pct,
            "status": "Shortage" if pct < 75 else ("Watch" if pct < 80 else "Good"),
        })
    result.sort(key=lambda x: x["percentage"])
    return result


async def get_marks(db: AsyncSession, student: StudentProfile) -> list[dict]:
    courses = await _courses_map(db)
    rows = (await db.execute(select(MarksRecord).where(MarksRecord.student_id == student.id))).scalars().all()
    out = []
    for row in rows:
        course = courses.get(row.course_id)
        out.append({
            "course_code": course.code if course else "",
            "course_name": course.name if course else "",
            "assessment": row.assessment,
            "marks": row.marks,
            "max_marks": row.max_marks,
            "percentage": round(100.0 * row.marks / row.max_marks, 1) if row.max_marks else 0,
            "recorded_on": row.recorded_on,
        })
    out.sort(key=lambda x: (x["course_code"], x["assessment"]))
    return out


async def get_faculty_availability(db: AsyncSession, name_query: Optional[str] = None) -> list[dict]:
    faculty = (await db.execute(select(FacultyProfile))).scalars().all()
    avail = (await db.execute(select(FacultyAvailability))).scalars().all()
    by_id = {f.id: f for f in faculty}
    out = []
    q = (name_query or "").lower()
    for row in avail:
        fac = by_id.get(row.faculty_id)
        if not fac:
            continue
        if q and q not in fac.full_name.lower() and q not in fac.department.lower():
            continue
        out.append({
            "faculty": fac.full_name,
            "designation": fac.designation,
            "department": fac.department,
            "cabin": fac.cabin,
            "day": row.day_of_week,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "kind": row.kind,
            "location": row.location,
            "notes": row.notes,
        })
    out.sort(key=lambda x: (x["faculty"], DAYS.index(x["day"]) if x["day"] in DAYS else 99, x["start_time"]))
    return out


async def get_calendar(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(AcademicEvent))).scalars().all()
    return [
        {
            "title": e.title,
            "event_type": e.event_type,
            "start_date": e.start_date,
            "end_date": e.end_date,
            "recurrence": e.recurrence,
            "description": e.description,
        }
        for e in rows
    ]


async def build_week_plan(db: AsyncSession, student: StudentProfile) -> dict:
    timetable = await get_timetable(db, student)
    attendance = await get_attendance(db, student)
    marks = await get_marks(db, student)
    calendar = await get_calendar(db)
    faculty = await get_faculty_availability(db)

    weak_courses = [a for a in attendance if a["percentage"] < 80]
    low_marks = []
    by_course: dict[str, list[dict]] = {}
    for m in marks:
        by_course.setdefault(m["course_code"], []).append(m)
    for code, items in by_course.items():
        cats = [i for i in items if i["assessment"].startswith("CAT")]
        if cats:
            avg = sum(i["percentage"] for i in cats) / len(cats)
            if avg < 75:
                low_marks.append({"course_code": code, "average": round(avg, 1), "name": cats[0]["course_name"]})

    busy = {(s["day"], s["start_time"]) for s in timetable}
    free_blocks = []
    for day in DAYS[:5]:
        for start, end in [("15:00", "16:00"), ("16:00", "17:00")]:
            if (day, start) not in busy:
                free_blocks.append({"day": day, "start_time": start, "end_time": end, "use": "self-study / faculty meeting"})

    office = [f for f in faculty if f["kind"] == "office_hours"]
    exams = [e for e in calendar if e["event_type"] == "exam"]

    suggestions = []
    if weak_courses:
        worst = weak_courses[0]
        suggestions.append(
            f"Priority: attend remaining {worst['course_code']} classes — attendance is {worst['percentage']}% (need ≥75%)."
        )
    if low_marks:
        lm = low_marks[0]
        suggestions.append(
            f"Revise {lm['name']} ({lm['course_code']}) during free 3–5 PM slots; CAT average is {lm['average']}%."
        )
    if office:
        fac = office[0]
        suggestions.append(
            f"Meet {fac['faculty']} on {fac['day']} {fac['start_time']}-{fac['end_time']} at {fac['location']}."
        )
    if exams:
        suggestions.append(f"Next assessment window: {exams[0]['title']} ({exams[0]['start_date']} to {exams[0]['end_date'] or exams[0]['start_date']}).")

    return {
        "student": serialize_student(student),
        "suggestions": suggestions,
        "free_blocks": free_blocks[:8],
        "focus_attendance": weak_courses[:3],
        "focus_marks": low_marks[:3],
        "upcoming_exams": exams[:4],
        "office_hours": office[:6],
        "today_hint": datetime.utcnow().strftime("%A"),
    }


DRAFT_TYPES = {
    "weekly_timetable": "Weekly class reminder",
    "faculty_meeting": "Recurring faculty meeting invite",
    "attendance_warning": "Attendance shortage notice",
    "exam_reminder": "Assessment / exam reminder",
    "office_hours": "Faculty office-hours circular",
}


async def generate_draft(
    db: AsyncSession,
    draft_type: str,
    student: StudentProfile,
    extra: str = "",
    save: bool = False,
    created_by: str = "Campus-GPT",
) -> dict:
    timetable = await get_timetable(db, student)
    attendance = await get_attendance(db, student)
    calendar = await get_calendar(db)
    faculty = await get_faculty_availability(db)
    title = DRAFT_TYPES.get(draft_type, "Campus circular")
    extra_line = f"\nNote: {extra.strip()}\n" if extra and extra.strip() else "\n"

    if draft_type == "weekly_timetable":
        lines = [f"- {s['day']} {s['start_time']}-{s['end_time']}: {s['course_code']} {s['course_name']} ({s['room']}, {s['faculty']})" for s in timetable]
        body = (
            f"CIRCULAR — Weekly timetable reminder\n"
            f"Department of {student.department} | Semester {student.semester} | Section {student.section}\n\n"
            f"Classes for the coming week:\n" + "\n".join(lines) + extra_line
            + "Students must occupy seats five minutes before the period. Labs require ID card and observation book.\n"
            f"— Academic Coordinator, {student.department}"
        )
        recurrence = "weekly"
    elif draft_type == "faculty_meeting":
        meetings = [f for f in faculty if f["kind"] == "meeting"]
        when = meetings[0] if meetings else {"day": "Friday", "start_time": "16:00", "end_time": "17:00", "location": "HoD Conference Room"}
        body = (
            f"MEETING NOTICE — Department faculty (recurring)\n\n"
            f"The {student.department} faculty meeting will be held every {when['day']} "
            f"{when['start_time']}-{when['end_time']} at {when.get('location', 'HoD Conference Room')}.\n"
            f"Agenda: academic schedule, CAT planning, attendance follow-up, lab utilization.\n"
            f"{extra_line}"
            f"Please confirm attendance to the HoD office.\n— Head of Department, {student.department}"
        )
        recurrence = "weekly"
    elif draft_type == "attendance_warning":
        short = [a for a in attendance if a["percentage"] < 75]
        listing = "\n".join([f"- {a['course_code']} {a['course_name']}: {a['percentage']}% ({a['present']}/{a['conducted']})" for a in short]) or "- None below 75% this week"
        body = (
            f"NOTICE — Attendance shortage follow-up\n"
            f"Student: {student.full_name} ({student.roll_no})\n\n"
            f"Courses below the 75% requirement:\n{listing}\n"
            f"{extra_line}"
            f"Please meet the course faculty during office hours and ensure remaining periods are attended. "
            f"OD must be submitted within 3 working days.\n— Class Advisor"
        )
        recurrence = "weekly"
    elif draft_type == "exam_reminder":
        exams = [e for e in calendar if e["event_type"] == "exam"]
        listing = "\n".join([f"- {e['title']}: {e['start_date']} to {e['end_date'] or e['start_date']}" for e in exams])
        body = (
            f"CIRCULAR — Assessment schedule reminder\n"
            f"Department of {student.department}, Semester {student.semester}\n\n"
            f"{listing}\n"
            f"{extra_line}"
            f"Seating and timetable will be published on the notice board 48 hours prior. "
            f"Mobile phones are not permitted in the hall.\n— Exam Cell / Academic Office"
        )
        recurrence = "per_assessment"
    else:
        office = [f for f in faculty if f["kind"] == "office_hours"]
        listing = "\n".join(
            [f"- {f['faculty']} ({f['cabin']}): {f['day']} {f['start_time']}-{f['end_time']} — {f['notes']}" for f in office]
        )
        body = (
            f"CIRCULAR — Faculty office hours (odd semester)\n"
            f"Department of {student.department}\n\n"
            f"{listing}\n"
            f"{extra_line}"
            f"Students may meet faculty only during published hours unless an appointment is booked.\n"
            f"— Department Office"
        )
        recurrence = "weekly"

    payload = {"title": title, "draft_type": draft_type, "body": body, "recurrence": recurrence}
    if save:
        rec = RecurringDraft(
            title=title,
            draft_type=draft_type,
            body=body,
            recurrence=recurrence,
            created_by=created_by,
        )
        db.add(rec)
        await db.flush()
        payload["id"] = rec.id
    return payload


def _format_timetable(rows: list[dict]) -> str:
    if not rows:
        return "No timetable rows found."
    lines = [f"- {r['day']} {r['start_time']}-{r['end_time']}: {r['course_code']} {r['course_name']} | {r['faculty']} | {r['room']}" for r in rows]
    return "Weekly timetable:\n" + "\n".join(lines)


def _format_attendance(rows: list[dict]) -> str:
    lines = [f"- {r['course_code']} {r['course_name']}: {r['percentage']}% ({r['present']}+OD{r['od']}/{r['conducted']}) [{r['status']}]" for r in rows]
    return "Attendance (need ≥75%):\n" + "\n".join(lines)


def _format_marks(rows: list[dict]) -> str:
    lines = [f"- {r['course_code']} {r['assessment']}: {r['marks']}/{r['max_marks']} ({r['percentage']}%)" for r in rows]
    return "Internal marks:\n" + "\n".join(lines)


async def get_academic_context(db: AsyncSession, query: str, user: Optional[dict]) -> Optional[str]:
    """Build verified DB context for campus-operation questions."""
    intent = detect_academic_intent(query)
    student, demo = await resolve_student(db, user)
    if not student:
        return None

    header = (
        f"Live academic database for {student.full_name} ({student.roll_no}), "
        f"{student.program}, Sem {student.semester} Section {student.section}."
        + (" Showing linked demo student record because this login has no SIS row yet." if demo else "")
    )

    parts = [header]
    q = (query or "").lower()
    name_hint = None
    for fac in (await db.execute(select(FacultyProfile))).scalars().all():
        last = fac.full_name.split()[-1].lower()
        if last in q or fac.full_name.lower() in q:
            name_hint = fac.full_name
            break

    if intent == "timetable" or not intent:
        day = next((d for d in DAYS if d.lower() in q), None)
        parts.append(_format_timetable(await get_timetable(db, student, day)))
    if intent in (None, "attendance"):
        parts.append(_format_attendance(await get_attendance(db, student)))
    if intent in (None, "marks"):
        parts.append(_format_marks(await get_marks(db, student)))
    if intent in (None, "faculty"):
        fac_rows = await get_faculty_availability(db, name_hint)
        parts.append(
            "Faculty availability:\n"
            + "\n".join(
                [f"- {r['faculty']} | {r['kind']} | {r['day']} {r['start_time']}-{r['end_time']} | {r['location']} | {r['notes']}" for r in fac_rows]
            )
        )
    if intent in (None, "planning"):
        plan = await build_week_plan(db, student)
        parts.append("Planning suggestions:\n- " + "\n- ".join(plan["suggestions"]))
        parts.append(
            "Free blocks:\n"
            + "\n".join([f"- {b['day']} {b['start_time']}-{b['end_time']}: {b['use']}" for b in plan["free_blocks"]])
        )
    if intent == "draft":
        draft = await generate_draft(db, "weekly_timetable", student)
        parts.append("Draft circular preview:\n" + draft["body"])
    if intent == "forecast":
        fc = await forecast_academics(db, student)
        parts.append(fc["summary"])
        parts.append("Course forecast:\n" + "\n".join(
            [f"- {c['course_code']}: now {c['current_attendance']}%, can miss {c['can_miss']}, if attend all {c['if_attend_all']}%, internals ~{c['predicted_internal']}% [{c['risk']}]" for c in fc["courses"]]
        ))

    # If no specific academic intent, only inject when query looks campus-ops related
    if intent is None:
        ops_words = ["class", "faculty", "semester", "course", "lab", "exam", "cat", "internal"]
        if not any(w in q for w in ops_words):
            return None
        # Keep it short: timetable + attendance snapshot
        return "\n\n".join(parts[:3])

    return "\n\n".join(parts)


async def forecast_academics(db: AsyncSession, student: StudentProfile) -> dict:
    """Project attendance and internal marks from current SIS records."""
    attendance = await get_attendance(db, student)
    marks = await get_marks(db, student)
    by_course: dict[str, list[dict]] = {}
    for m in marks:
        by_course.setdefault(m["course_code"], []).append(m)

    rows = []
    warnings = []
    for a in attendance:
        lab = "lab" in a["course_name"].lower()
        planned = 14 if lab else 40
        remaining = max(planned - a["conducted"], 0)
        present = a["present"] + a["od"]
        total_end = a["conducted"] + remaining
        if_attend_all = _pct(present + remaining, total_end) if total_end else a["percentage"]
        can_miss = 0
        for miss in range(remaining + 1):
            attended_more = remaining - miss
            if _pct(present + attended_more, total_end) >= 75:
                can_miss = miss
            else:
                break
        if a["percentage"] < 75:
            risk = "Critical"
            warnings.append(f"{a['course_code']} is already below 75%. Apply OD or meet the faculty.")
        elif can_miss <= 1:
            risk = "High"
            warnings.append(f"{a['course_code']}: you can miss at most {can_miss} more period(s).")
        elif can_miss <= 3:
            risk = "Watch"
        else:
            risk = "Safe"

        course_marks = by_course.get(a["course_code"], [])
        cats = [x for x in course_marks if x["assessment"].upper().startswith("CAT")]
        assigns = [x for x in course_marks if "assign" in x["assessment"].lower() or "lab" in x["assessment"].lower()]
        cat_avg = round(sum(x["percentage"] for x in cats) / len(cats), 1) if cats else None
        asg_avg = round(sum(x["percentage"] for x in assigns) / len(assigns), 1) if assigns else None
        if cat_avg is not None and asg_avg is not None:
            predicted_internal = round(0.7 * cat_avg + 0.3 * asg_avg, 1)
        elif cat_avg is not None:
            predicted_internal = cat_avg
        else:
            predicted_internal = None

        rows.append({
            "course_code": a["course_code"],
            "course_name": a["course_name"],
            "current_attendance": a["percentage"],
            "remaining_classes": remaining,
            "if_attend_all": if_attend_all,
            "can_miss": can_miss,
            "risk": risk,
            "cat_average": cat_avg,
            "predicted_internal": predicted_internal,
        })

    overall = round(sum(a["percentage"] for a in attendance) / len(attendance), 1) if attendance else 0
    summary = (
        f"Overall attendance {overall}%. "
        + ("Raise Networks/watch courses immediately. " if any(r["risk"] in ("Critical", "High") for r in rows) else "On track if you stay regular. ")
        + "Predicted internals use CAT (70%) and assignment/lab (30%)."
    )
    return {
        "student": serialize_student(student),
        "overall_attendance": overall,
        "summary": summary,
        "warnings": warnings,
        "courses": rows,
    }
