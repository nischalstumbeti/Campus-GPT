from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.models import (  # noqa: F401 — register metadata
    Achievement,
    Announcement,
    AppNotification,
    AttendanceRecord,
    AttendanceSession,
    Complaint,
    Course,
    CourseOffering,
    Department,
    DirectMessage,
    Enrollment,
    ExamApplication,
    ExamApplicationWindow,
    ExamSchedule,
    FacultyAdvisor,
    FacultyAvailability,
    FacultyProfile,
    FeePayment,
    FeePlan,
    FeeReminder,
    Grade,
    HallTicketSettings,
    Hostel,
    HostelAllocation,
    HostelBlock,
    HostelAttendance,
    HostelLeave,
    IntegrationConsent,
    Mark,
    MarqueeItem,
    MessageThread,
    Program,
    Room,
    RuntimeSetting,
    StudentFee,
    StudentProfile,
    TimetableSlot,
    User,
)
from app.routes import (
    acknowledgements,
    admin,
    auth,
    branding,
    complaints,
    exam_applications,
    faculty,
    fees,
    directory,
    hall_ticket,
    forms,
    people,
    hostel,
    integration,
    keep_awake,
    institute,
    integrations,
    marquee,
    messages,
    records,
    student,
)

settings = get_settings()


_DEFAULT_SECRETS = {
    "dev-only-insecure-uis-key",
    "uis-campus-gpt-dev-integration-key",
    "your-secret-key-change-in-production",
}


async def _ensure_hostel_leave_columns(conn):
    """Add leave workflow columns on existing SQLite DBs without a full reseed."""
    from sqlalchemy import text

    dialect = conn.engine.dialect.name if hasattr(conn, "engine") else getattr(conn, "dialect", None)
    # AsyncConnection exposes .dialect
    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(hostel_leaves)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    alters = {
        "destination": "ALTER TABLE hostel_leaves ADD COLUMN destination VARCHAR(255) DEFAULT ''",
        "source": "ALTER TABLE hostel_leaves ADD COLUMN source VARCHAR(32) DEFAULT 'uis'",
        "decision_note": "ALTER TABLE hostel_leaves ADD COLUMN decision_note VARCHAR(500) DEFAULT ''",
        "faculty_status": "ALTER TABLE hostel_leaves ADD COLUMN faculty_status VARCHAR(16) DEFAULT 'pending'",
        "hostel_status": "ALTER TABLE hostel_leaves ADD COLUMN hostel_status VARCHAR(16) DEFAULT 'pending'",
    }
    for col, stmt in alters.items():
        if col not in existing:
            await conn.execute(text(stmt))


async def _ensure_branding_columns(conn):
    """Add CMS text/logo columns on an existing SQLite branding table."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(branding_settings)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    if not existing:
        return
    alters = {
        "logo_url": "ALTER TABLE branding_settings ADD COLUMN logo_url TEXT DEFAULT ''",
        "header_title": "ALTER TABLE branding_settings ADD COLUMN header_title VARCHAR(160) DEFAULT ''",
        "header_subtitle": "ALTER TABLE branding_settings ADD COLUMN header_subtitle VARCHAR(255) DEFAULT ''",
        "footer_text": "ALTER TABLE branding_settings ADD COLUMN footer_text TEXT DEFAULT ''",
        "sign_in_label": "ALTER TABLE branding_settings ADD COLUMN sign_in_label VARCHAR(80) DEFAULT ''",
    }
    for col, stmt in alters.items():
        if col not in existing:
            await conn.execute(text(stmt))


async def _ensure_marquee_columns(conn):
    """Add the notification link column on an existing SQLite marquee table."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(marquee_items)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    if not existing or "link_url" in existing:
        return
    await conn.execute(text("ALTER TABLE marquee_items ADD COLUMN link_url VARCHAR(500) DEFAULT ''"))


async def _ensure_student_photo_column(conn):
    """Add the student portrait column on an existing SQLite profile table."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(student_profiles)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    if not existing or "photo_url" in existing:
        return
    await conn.execute(text("ALTER TABLE student_profiles ADD COLUMN photo_url TEXT DEFAULT ''"))


async def _ensure_course_group_column(conn):
    """Mark courses as CGPA, non-CGPA, or mandatory on an existing table."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(courses)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    if not existing or "result_group" in existing:
        return
    await conn.execute(text("ALTER TABLE courses ADD COLUMN result_group VARCHAR(16) DEFAULT 'cgpa'"))


async def _ensure_exam_paper_column(conn):
    """Store the question paper text on an existing exam schedule."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(exam_schedules)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    if not existing or "paper_text" in existing:
        return
    await conn.execute(text("ALTER TABLE exam_schedules ADD COLUMN paper_text TEXT DEFAULT ''"))


async def _ensure_application_approval_columns(conn):
    """Advisor and HoD stages on an existing exam application."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(exam_applications)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    if not existing:
        return
    if "advisor_status" not in existing:
        await conn.execute(text("ALTER TABLE exam_applications ADD COLUMN advisor_status VARCHAR(16) DEFAULT 'pending'"))
    if "hod_status" not in existing:
        await conn.execute(text("ALTER TABLE exam_applications ADD COLUMN hod_status VARCHAR(16) DEFAULT 'pending'"))


async def _ensure_hall_ticket_columns(conn):
    """Attendance rule on the hall ticket design row."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(hall_ticket_settings)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    if not existing:
        return
    alters = {
        "min_attendance": "ALTER TABLE hall_ticket_settings ADD COLUMN min_attendance FLOAT DEFAULT 75",
        "require_overall": "ALTER TABLE hall_ticket_settings ADD COLUMN require_overall BOOLEAN DEFAULT 1",
        "require_subject": "ALTER TABLE hall_ticket_settings ADD COLUMN require_subject BOOLEAN DEFAULT 1",
    }
    for column, sql in alters.items():
        if column not in existing:
            await conn.execute(text(sql))


async def _ensure_directory_columns(conn):
    """Cabin and photo fields for the staff directory on an existing users table."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(users)")).fetchall()
        return {r[1] for r in rows}

    existing = await conn.run_sync(lambda c: _cols(c))
    if not existing:
        return
    alters = {
        "photo_url": "ALTER TABLE users ADD COLUMN photo_url TEXT DEFAULT ''",
        "designation": "ALTER TABLE users ADD COLUMN designation VARCHAR(80) DEFAULT ''",
        "cabin_block": "ALTER TABLE users ADD COLUMN cabin_block VARCHAR(80) DEFAULT ''",
        "school": "ALTER TABLE users ADD COLUMN school VARCHAR(120) DEFAULT ''",
        "office": "ALTER TABLE users ADD COLUMN office VARCHAR(120) DEFAULT ''",
        "abc_id": "ALTER TABLE users ADD COLUMN abc_id VARCHAR(32) DEFAULT ''",
        "residence": "ALTER TABLE users ADD COLUMN residence VARCHAR(24) DEFAULT ''",
        "transport": "ALTER TABLE users ADD COLUMN transport VARCHAR(24) DEFAULT ''",
        "residence_detail": "ALTER TABLE users ADD COLUMN residence_detail VARCHAR(255) DEFAULT ''",
    }
    for column, statement in alters.items():
        if column not in existing:
            await conn.execute(text(statement))


async def _ensure_ack_columns(conn):
    """Status and reference on slips created before those fields existed."""
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(acknowledgements)")).fetchall()
        return {row[1] for row in rows}

    existing = await conn.run_sync(lambda sync_conn: _cols(sync_conn))
    if not existing:
        return
    if "status" not in existing:
        await conn.execute(text("ALTER TABLE acknowledgements ADD COLUMN status VARCHAR(32) DEFAULT ''"))
    if "ref_key" not in existing:
        await conn.execute(text("ALTER TABLE acknowledgements ADD COLUMN ref_key VARCHAR(64) DEFAULT ''"))


async def _ensure_slip_kind(conn):
    from sqlalchemy import text

    name = getattr(getattr(conn, "dialect", None), "name", "") or ""
    if name != "sqlite":
        return

    def _cols(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(slip_templates)")).fetchall()
        return {row[1] for row in rows}

    existing = await conn.run_sync(lambda sync_conn: _cols(sync_conn))
    if existing and "kind" not in existing:
        await conn.execute(text("ALTER TABLE slip_templates ADD COLUMN kind VARCHAR(24) DEFAULT 'general'"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment.lower() == "production":
        if settings.jwt_secret in _DEFAULT_SECRETS or not settings.jwt_secret:
            raise RuntimeError("Set a strong jwt_secret before running UIS in production")
        if settings.integration_api_key in _DEFAULT_SECRETS:
            raise RuntimeError("Set integration_api_key before running UIS in production")
    elif settings.jwt_secret in _DEFAULT_SECRETS:
        print("WARNING: using default jwt_secret — set jwt_secret for any shared/deployed environment")

    # Keep startup light so /health and /login respond quickly
    try:
        from app.database import ensure_schema

        async with engine.begin() as conn:
            await ensure_schema(conn)
            await conn.run_sync(Base.metadata.create_all)
            try:
                await _ensure_hostel_leave_columns(conn)
                await _ensure_branding_columns(conn)
                await _ensure_marquee_columns(conn)
                await _ensure_student_photo_column(conn)
                await _ensure_course_group_column(conn)
                await _ensure_exam_paper_column(conn)
                await _ensure_directory_columns(conn)
                await _ensure_application_approval_columns(conn)
                await _ensure_hall_ticket_columns(conn)
                await _ensure_ack_columns(conn)
                await _ensure_slip_kind(conn)
            except Exception:
                pass
    except Exception as exc:
        print(f"UIS schema init warning: {exc}")
    # Free Render disks start empty. Load the campus123 demo accounts once
    # per empty database so live login works after every cold start.
    try:
        from sqlalchemy import func, select

        from app.database import SessionLocal
        from app.seed.run_seed import seed

        async with SessionLocal() as db:
            user_count = await db.scalar(select(func.count()).select_from(User))
        if not user_count:
            print("UIS demo seed: no users, loading campus123 accounts")
            await seed()
    except Exception as exc:
        print(f"UIS demo seed skipped: {exc}")
    try:
        from app.seed.ensure_fees import ensure_fees

        result = await ensure_fees()
        print(f"UIS fees seed: {result}")
    except Exception as exc:
        print(f"UIS fees seed skipped: {exc}")
    try:
        from app.seed.ensure_academics import ensure_academics

        academic = await ensure_academics()
        print(f"UIS academics seed: {academic}")
    except Exception as exc:
        print(f"UIS academics seed skipped: {exc}")
    try:
        from app.seed.ensure_attendance import ensure_attendance_sessions

        sessions = await ensure_attendance_sessions()
        print(f"UIS attendance sessions: {sessions}")
    except Exception as exc:
        print(f"UIS attendance sessions skipped: {exc}")
    try:
        from app.seed.ensure_exam_papers import ensure_exam_papers

        papers = await ensure_exam_papers()
        print(f"UIS exam papers: {papers}")
    except Exception as exc:
        print(f"UIS exam papers skipped: {exc}")
    try:
        from app.seed.ensure_exam_windows import ensure_exam_windows

        windows = await ensure_exam_windows()
        print(f"UIS exam windows: {windows}")
    except Exception as exc:
        print(f"UIS exam windows skipped: {exc}")
    try:
        from app.seed.ensure_hall_ticket import ensure_hall_ticket

        hall = await ensure_hall_ticket()
        print(f"UIS hall ticket: {hall}")
    except Exception as exc:
        print(f"UIS hall ticket skipped: {exc}")
    try:
        from app.seed.ensure_directory import ensure_directory

        directory_seed = await ensure_directory()
        from app.seed.ensure_advisors import ensure_advisors

        print(f"UIS advisors: {await ensure_advisors()}")
        print(f"UIS directory: {directory_seed}")
    except Exception as exc:
        print(f"UIS directory skipped: {exc}")
    try:
        from app.seed.ensure_marquee import ensure_marquee

        mq = await ensure_marquee()
        print(f"UIS marquee seed: {mq}")
    except Exception as exc:
        print(f"UIS marquee seed skipped: {exc}")
    try:
        from sqlalchemy import select
        from app.database import SessionLocal
        from app.routes.integration import ensure_student_consents

        async with SessionLocal() as db:
            demos = (
                await db.execute(
                    select(User).where(
                        User.username.in_(
                            [
                                "student.demo",
                                "faculty.demo",
                                "admin.demo",
                                "warden.demo",
                                "hod.demo",
                            ]
                        )
                    )
                )
            ).scalars().all()
            for u in demos:
                await ensure_student_consents(db, u.id, "allow")
            await db.commit()
    except Exception as exc:
        print(f"UIS consent backfill skipped: {exc}")
    from app.services.keep_awake import start as start_keep_awake
    from app.services.keep_awake import stop as stop_keep_awake

    start_keep_awake()
    try:
        yield
    finally:
        await stop_keep_awake()


_prod = settings.environment.lower() == "production"
_docs = None if _prod else "/docs"
_redoc = None if _prod else "/redoc"

app = FastAPI(
    title="University Information System API",
    description=(
        "Institutional system of record for Kalasalingam University (synthetic demo). "
        "Campus-GPT must integrate only via `/api/v1/integration/campus-gpt/`."
    ),
    version="1.0.0",
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=None if _prod else "/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(directory.router)
app.include_router(student.router)
app.include_router(faculty.router)
app.include_router(hostel.router)
app.include_router(complaints.router)
app.include_router(fees.router)
app.include_router(messages.router)
app.include_router(marquee.router)
app.include_router(branding.router)
app.include_router(admin.router)
app.include_router(acknowledgements.router)
app.include_router(institute.router)
app.include_router(records.router)
app.include_router(integrations.router)
app.include_router(exam_applications.router)
app.include_router(hall_ticket.router)
app.include_router(forms.router)
app.include_router(people.router)
app.include_router(integration.router)
app.include_router(keep_awake.router)


@app.get("/health")
async def health():
    from app.utils.db_status import get_database_status

    db_info = await get_database_status()
    db_ok = bool(db_info.get("connected"))
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "university-information-system",
        "database": db_ok,
        "database_status": db_info,
    }
