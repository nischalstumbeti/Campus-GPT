import os
import ssl

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

url = settings.database_url
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
if url.startswith("sqlite"):
    connect_args: dict = {"check_same_thread": False}
elif "supabase" in url or "pooler.supabase.com" in url or url.startswith("postgresql"):
    # Supabase pooler (PgBouncer/Supavisor) rejects prepared statements unless cache is off
    ssl_ctx = ssl.create_default_context()
    # Windows/local cert chains often fail against Supabase pooler
    insecure = os.getenv("UIS_DB_SSL_INSECURE", "1" if "supabase" in url else "").strip().lower()
    if insecure in ("1", "true", "yes") or "supabase" in url:
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
    connect_args = {"ssl": ssl_ctx, "statement_cache_size": 0}
else:
    connect_args = {}

engine = create_async_engine(url, echo=False, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Campus-GPT and UIS share one Supabase project — keep UIS tables in schema "uis"
# so they never collide with Campus-GPT's public.users / student_profiles / etc.
_UIS_SCHEMA = os.getenv("UIS_DB_SCHEMA", "uis").strip() or "uis"
_is_postgres = url.startswith("postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(schema=_UIS_SCHEMA if _is_postgres else None)


async def ensure_schema(conn) -> None:
    """Create the UIS Postgres schema when sharing a DB with Campus-GPT."""
    if not _is_postgres:
        return
    await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{_UIS_SCHEMA}"'))


async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
