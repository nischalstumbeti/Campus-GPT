# UIS database notes

## Local development

Default: SQLite file `backend/uis.db` via:

```text
DATABASE_URL=sqlite+aiosqlite:///./uis.db
```

## Production / Supabase

Set:

```text
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/uis
SUPABASE_URL=
SUPABASE_KEY=
```

SQLAlchemy models in `backend/app/models/` are the schema source of truth for Phase 1–4.
Alembic migrations can be added when locking production schema.

## Ownership

UIS owns all institutional tables. Campus-GPT must not mount this database.
