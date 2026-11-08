"""Connect to Supabase and create UIS schema + minimal seeds."""
import asyncio
from sqlalchemy import select, text
from app.database import engine, url, Base, SessionLocal, ensure_schema, _UIS_SCHEMA
from app import models  # noqa: F401
from app.models import BrandingSettings


async def main():
    print("UIS target:", url.split("@")[-1])
    print("UIS schema:", _UIS_SCHEMA)
    async with engine.begin() as conn:
        v = (await conn.execute(text("select version()"))).scalar()
        print("CONNECTED:", str(v)[:90])
        await ensure_schema(conn)
        await conn.run_sync(Base.metadata.create_all)
        print("Schema create_all done")

    async with SessionLocal() as db:
        existing = (
            await db.execute(select(BrandingSettings).order_by(BrandingSettings.id).limit(1))
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                BrandingSettings(
                    primary="#0B2A4A",
                    primary_dark="#071E36",
                    secondary="#1E4A7A",
                    accent="#C9A227",
                    bg_light="#F4F7FB",
                    bg_card="#FFFFFF",
                    text_color="#0F172A",
                    font_family="Verdana, Tahoma, sans-serif",
                    font_size_base="16px",
                    heading_scale="1.25",
                    app_name="KARE UIS",
                )
            )
            await db.commit()
            print("Branding defaults inserted")
        else:
            print("Branding already present")

        try:
            from app.seed.ensure_marquee import ensure_marquee

            print("marquee:", await ensure_marquee())
        except Exception as exc:
            print("marquee seed skipped:", exc)
        try:
            from app.seed.ensure_fees import ensure_fees

            print("fees:", await ensure_fees())
        except Exception as exc:
            print("fees seed skipped:", exc)

    async with engine.begin() as conn:
        n = (
            await conn.execute(
                text(
                    "select count(*) from information_schema.tables "
                    "where table_schema=:s"
                ),
                {"s": _UIS_SCHEMA},
            )
        ).scalar()
        print(f"{_UIS_SCHEMA} tables:", n)
        for table in ("users", "student_profiles", "branding_settings", "marquee_items", "departments"):
            try:
                c = (
                    await conn.execute(
                        text(f'select count(*) from "{_UIS_SCHEMA}"."{table}"')
                    )
                ).scalar()
                print(f"  {table}: {c}")
            except Exception as exc:
                print(f"  {table}: ERR {type(exc).__name__}")


if __name__ == "__main__":
    asyncio.run(main())
