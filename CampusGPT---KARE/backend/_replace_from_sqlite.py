"""Full replace: campus_gpt.db -> Supabase public (Campus-GPT tables only)."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.utils.database import Base, engine

from app.models import academic as _a  # noqa: F401
from app.models import analytics as _an  # noqa: F401
from app.models import branding as _b  # noqa: F401
from app.models import chat as _c  # noqa: F401
from app.models import document as _d  # noqa: F401
from app.models import escalation as _e  # noqa: F401
from app.models import fees as _f  # noqa: F401
from app.models import marquee as _m  # noqa: F401
from app.models import messaging as _msg  # noqa: F401
from app.models import notifications as _n  # noqa: F401
from app.models import platform as _p  # noqa: F401
from app.models import privacy as _pr  # noqa: F401
from app.models.user import User  # noqa: F401


SQLITE_PATH = Path(__file__).resolve().parent / "campus_gpt.db"
BATCH = 200


def sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def convert_value(col_name: str, value, col_type: str):
    if value is None:
        return None
    t = (col_type or "").lower()
    if "bool" in t:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "t")
    if "datetime" in t or t.startswith("timestamp"):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T"))
            except ValueError:
                return value
    if t == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return value
    return value


async def wipe_and_create():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                DO $$ DECLARE r RECORD;
                BEGIN
                  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                  END LOOP;
                  FOR r IN (
                    SELECT t.typname
                    FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = 'public' AND t.typtype = 'e'
                  ) LOOP
                    EXECUTE 'DROP TYPE IF EXISTS public.' || quote_ident(r.typname) || ' CASCADE';
                  END LOOP;
                END $$;
                """
            )
        )
        await conn.run_sync(Base.metadata.create_all)
    print("Postgres public schema recreated for Campus-GPT models")


def load_payload(sqlite_conn: sqlite3.Connection, table):
    table_name = table.name
    src_cols = set(sqlite_columns(sqlite_conn, table_name))
    dst_cols = [c for c in table.columns if c.name in src_cols]
    if not dst_cols:
        return [], []
    col_names = [c.name for c in dst_cols]
    select_sql = "SELECT " + ", ".join(f'"{n}"' for n in col_names) + f' FROM "{table_name}"'
    rows = sqlite_conn.execute(select_sql).fetchall()
    payload = []
    for row in rows:
        item = {}
        for i, col in enumerate(dst_cols):
            item[col.name] = convert_value(col.name, row[i], str(col.type))
        payload.append(item)
    return col_names, payload


async def main():
    if not SQLITE_PATH.exists():
        raise SystemExit(f"Missing {SQLITE_PATH}")

    print("Source:", SQLITE_PATH)
    await wipe_and_create()

    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    available = sqlite_tables(sqlite_conn)
    tables = list(Base.metadata.sorted_tables)

    total = 0
    missing = []
    async with engine.begin() as conn:
        # Same session: disable FK checks for bulk restore
        await conn.execute(text("SET session_replication_role = replica"))
        for table in tables:
            if table.name not in available:
                missing.append(table.name)
                continue
            col_names, payload = load_payload(sqlite_conn, table)
            if not col_names:
                print(f"  skip {table.name}: no overlapping columns")
                continue
            if not payload:
                print(f"  {table.name}: 0")
                continue
            for i in range(0, len(payload), BATCH):
                chunk = payload[i : i + BATCH]
                await conn.execute(pg_insert(table).values(chunk))
            total += len(payload)
            print(f"  {table.name}: {len(payload)}")

            pk = list(table.primary_key.columns)
            if len(pk) == 1 and pk[0].name == "id" and "id" in col_names:
                await conn.execute(
                    text(
                        f"""
                        SELECT setval(
                          pg_get_serial_sequence('public."{table.name}"', 'id'),
                          COALESCE((SELECT MAX(id) FROM "{table.name}"), 1),
                          true
                        )
                        """
                    )
                )
        await conn.execute(text("SET session_replication_role = DEFAULT"))

    sqlite_conn.close()
    if missing:
        print("Tables in models but not in SQLite:", ", ".join(missing))
    print(f"DONE Campus-GPT rows copied: {total}")

    async with engine.begin() as conn:
        for t in ("users", "chat_sessions", "query_logs", "student_profiles", "achievements"):
            n = (await conn.execute(text(f'select count(*) from "{t}"'))).scalar()
            print(f"  check {t}: {n}")


if __name__ == "__main__":
    asyncio.run(main())
