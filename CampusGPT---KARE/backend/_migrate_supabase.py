"""Connect to Supabase and create/seed Campus-GPT schema."""
import asyncio
from sqlalchemy import text
from app.utils.database import engine, database_url, init_db


async def main():
    print("CGPT target:", database_url.split("@")[-1])
    async with engine.begin() as conn:
        v = (await conn.execute(text("select version()"))).scalar()
        print("CONNECTED:", str(v)[:90])
    print("Running init_db (create tables + seed)...")
    await init_db()
    async with engine.begin() as conn:
        n = (
            await conn.execute(
                text(
                    "select count(*) from information_schema.tables "
                    "where table_schema='public'"
                )
            )
        ).scalar()
        print("public tables:", n)
        for table in ("users", "branding_settings", "marquee_items", "documents"):
            try:
                c = (await conn.execute(text(f"select count(*) from {table}"))).scalar()
                print(f"  {table}: {c}")
            except Exception as exc:
                print(f"  {table}: ERR {exc}")


if __name__ == "__main__":
    asyncio.run(main())
