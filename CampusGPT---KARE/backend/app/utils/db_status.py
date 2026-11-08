"""Database connection status for admin / health endpoints."""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text

from app.utils.database import AsyncSessionLocal, database_url, engine


def _mask_url(url: str) -> str:
    try:
        p = urlparse(url)
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        path = p.path or ""
        user = f"{p.username}@" if p.username else ""
        return f"{p.scheme}://{user}{host}{port}{path}"
    except Exception:
        return "(unavailable)"


def _dialect(url: str) -> str:
    if url.startswith("sqlite"):
        return "sqlite"
    if "postgresql" in url or "postgres" in url:
        return "postgresql"
    return url.split(":", 1)[0] if ":" in url else "unknown"


async def get_database_status() -> dict[str, Any]:
    """Ping the DB and return a safe status payload for admins."""
    dialect = _dialect(database_url)
    started = time.perf_counter()
    connected = False
    error: str | None = None
    server_version = ""
    table_count: int | None = None

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            connected = True
            if dialect == "postgresql":
                ver = (await db.execute(text("SELECT version()"))).scalar()
                server_version = str(ver or "")[:120]
                table_count = (
                    await db.execute(
                        text(
                            "SELECT COUNT(*) FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        )
                    )
                ).scalar()
            elif dialect == "sqlite":
                ver = (await db.execute(text("SELECT sqlite_version()"))).scalar()
                server_version = f"SQLite {ver}" if ver else "SQLite"
                table_count = (
                    await db.execute(
                        text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                    )
                ).scalar()
    except Exception as exc:
        connected = False
        error = str(exc)[:240]

    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    return {
        "connected": connected,
        "status": "connected" if connected else "disconnected",
        "dialect": dialect,
        "engine": engine.dialect.name if engine is not None else dialect,
        "url": _mask_url(database_url),
        "latency_ms": latency_ms,
        "server_version": server_version,
        "table_count": int(table_count) if table_count is not None else None,
        "error": error,
        "source_of_truth": "UIS API (university DB) for personal records; Campus-GPT DB for users/chat/knowledge",
    }
