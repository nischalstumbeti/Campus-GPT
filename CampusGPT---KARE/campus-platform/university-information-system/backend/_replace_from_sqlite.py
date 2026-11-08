"""Full replace: uis.db -> Supabase schema uis."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import Base, engine, ensure_schema, _UIS_SCHEMA
from app import models  # noqa: F401


SQLITE_PATH = Path(__file__).resolve().parent / "uis.db"
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
    schema = _UIS_SCHEMA
    async with engine.begin() as conn:
        await ensure_schema(conn)
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await ensure_schema(conn)
        await conn.run_sync(Base.metadata.create_all)
    print(f'Postgres schema "{schema}" recreated for UIS models')


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
    print("Target schema:", _UIS_SCHEMA)
    await wipe_and_create()

    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    available = sqlite_tables(sqlite_conn)
    tables = list(Base.metadata.sorted_tables)
    schema = _UIS_SCHEMA

    total = 0
    missing = []
    async with engine.begin() as conn:
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
                          pg_get_serial_sequence('"{schema}"."{table.name}"', 'id'),
                          COALESCE((SELECT MAX(id) FROM "{schema}"."{table.name}"), 1),
                          true
                        )
                        """
                    )
                )
        await conn.execute(text("SET session_replication_role = DEFAULT"))

    sqlite_conn.close()
    if missing:
        print("Tables in models but not in SQLite:", ", ".join(missing))
    print(f"DONE UIS rows copied: {total}")

    async with engine.begin() as conn:
        for t in ("users", "student_profiles", "complaints", "student_fees", "enrollments"):
            n = (
                await conn.execute(text(f'select count(*) from "{schema}"."{t}"'))
            ).scalar()
            print(f"  check {t}: {n}")


if __name__ == "__main__":
    asyncio.run(main())
