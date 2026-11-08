"""Database connection and session management."""
import os
import ssl

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import get_settings

settings = get_settings()

# Use SQLite for local development if PostgreSQL URL is the stock default
database_url = settings.DATABASE_URL
# Accept plain postgresql:// from .env and normalize for asyncpg
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
_default_pg = "postgresql+asyncpg://postgres:postgres@localhost:5432/campus_gpt"
if database_url == _default_pg and settings.ENVIRONMENT.lower() != "production":
    database_url = "sqlite+aiosqlite:///./campus_gpt.db"
elif database_url == _default_pg and settings.ENVIRONMENT.lower() == "production":
    raise RuntimeError("Set DATABASE_URL to a real PostgreSQL URL in production")

_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
elif "supabase" in database_url or "pooler.supabase.com" in database_url or database_url.startswith("postgresql"):
    ssl_ctx = ssl.create_default_context()
    # Windows/local chains often fail against Supabase pooler; allow opt-out via .env
    insecure = os.getenv("DB_SSL_INSECURE", "1" if "supabase" in database_url else "").strip().lower()
    if insecure in ("1", "true", "yes") or "supabase" in database_url:
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
    _engine_kwargs["connect_args"] = {"ssl": ssl_ctx, "statement_cache_size": 0}
engine = create_async_engine(database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db():
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    from app.models import academic as _academic  # noqa: F401
    from app.models import chat as _chat  # noqa: F401
    from app.models import privacy as _privacy  # noqa: F401
    from app.models import fees as _fees  # noqa: F401
    from app.models import messaging as _messaging  # noqa: F401
    from app.models import notifications as _notifications  # noqa: F401
    from app.models import marquee as _marquee  # noqa: F401
    from app.models import platform as _platform  # noqa: F401
    from app.models import branding as _branding  # noqa: F401
    from app.models import analytics as _analytics  # noqa: F401
    from app.models import escalation as _escalation  # noqa: F401
    from app.models import document as _document  # noqa: F401
    from app.models.user import User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new columns for existing DBs (SQLite + Postgres)
        from sqlalchemy import text

        alter_stmts = [
            "ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS latency_ms DOUBLE PRECISION",
            "ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS retrieval_score DOUBLE PRECISION",
            "ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS agent_type VARCHAR(40)",
        ]
        if "sqlite" in str(database_url):
            # SQLite does not support IF NOT EXISTS on ADD COLUMN in older versions — try/except below
            alter_stmts = [
                "ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN uis_username VARCHAR(128)",
                "ALTER TABLE query_logs ADD COLUMN user_id INTEGER",
                "ALTER TABLE query_logs ADD COLUMN points_earned INTEGER DEFAULT 0",
                "ALTER TABLE query_logs ADD COLUMN latency_ms REAL",
                "ALTER TABLE query_logs ADD COLUMN retrieval_score REAL",
                "ALTER TABLE query_logs ADD COLUMN agent_type VARCHAR(40)",
                "ALTER TABLE chat_sessions ADD COLUMN agent_type VARCHAR(40) DEFAULT 'general'",
                "ALTER TABLE announcements ADD COLUMN created_by INTEGER",
                "ALTER TABLE announcements ADD COLUMN created_at DATETIME",
                "ALTER TABLE fee_payments ADD COLUMN receipt_no VARCHAR(64) DEFAULT ''",
                "ALTER TABLE notification_prefs ADD COLUMN inapp_leave BOOLEAN DEFAULT 1",
            ]
        for stmt in alter_stmts:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # column may already exist

    # Always ensure campus fact sheets live in the DB (runtime source of truth)
    try:
        from app.services.campus_facts import ensure_fact_sheets

        async with AsyncSessionLocal() as db:
            await ensure_fact_sheets(db)
            await db.commit()
    except Exception as exc:
        print(f"Campus fact sheet seed skipped: {exc}")

    try:
        from sqlalchemy import select
        from app.models.branding import BrandingSettings, DEFAULT_BRANDING

        async with AsyncSessionLocal() as db:
            row = (
                await db.execute(select(BrandingSettings).order_by(BrandingSettings.id).limit(1))
            ).scalar_one_or_none()
            if row is None:
                db.add(BrandingSettings(**DEFAULT_BRANDING))
                await db.commit()
                print("Branding CMS defaults seeded.")
    except Exception as exc:
        print(f"Branding seed skipped: {exc}")

    if not settings.SEED_LOCAL_ACADEMIC:
        print("Local academic seed disabled — personal records come from UIS database only.")
        return

    from app.utils.seed_academic import (
        seed_academic_data,
        seed_demo_chat_memory,
        seed_linked_directory,
        seed_student_workspace,
    )
    from app.utils.seed_copilot import seed_copilot_layer
    try:
        await seed_academic_data()
        await seed_linked_directory()
        await seed_student_workspace()
        await seed_demo_chat_memory()
        await seed_copilot_layer()
        # Bulk fake students are not created automatically. Add real accounts from CIMS or the admin screen.
        # Demo accounts need consents allowed (defaults are opt-in/deny for everyone else)
        from sqlalchemy import select
        from app.models.user import User
        from app.services.consent import grant_all_consents

        demo_emails = (
            "student@example.com",
            "student.demo@klu.ac.in",
            "faculty@example.com",
            "faculty.demo@klu.ac.in",
            "admin@example.com",
            "admin.demo@klu.ac.in",
        )
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(User).where(User.email.in_(demo_emails)))).scalars().all()
            for u in rows:
                await grant_all_consents(db, u.id)
            await db.commit()
    except Exception as exc:
        print(f"Academic seed skipped: {exc}")
