"""Campus-GPT FastAPI Application Entry Point."""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import chat, upload, voice, analytics, recommend, auth, admin, student, academic, student_ops, privacy, copilot, fees, messages, notifications, marquee, platform, branding, integrations
from app.utils.database import init_db

_DEFAULT_SECRETS = {
    "your-secret-key-change-in-production",
    "dev-only-insecure-campus-gpt-key",
    "uis-campus-gpt-dev-integration-key",
}


async def _outbox_worker(stop: asyncio.Event) -> None:
    from app.utils.database import AsyncSessionLocal
    from app.services.sync_queue import process_outbox

    while not stop.is_set():
        try:
            async with AsyncSessionLocal() as db:
                result = await process_outbox(db)
                await db.commit()
                if result.get("processed"):
                    print(f"Sync outbox: {result}")
        except Exception as exc:
            print(f"Sync outbox tick failed: {exc}")
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + optional Supabase bucket. Shutdown: cleanup."""
    settings = get_settings()
    if settings.ENVIRONMENT.lower() == "production":
        if settings.SECRET_KEY in _DEFAULT_SECRETS or not settings.SECRET_KEY:
            raise RuntimeError("Set a strong SECRET_KEY before running in production")
        if settings.UIS_INTEGRATION_API_KEY in _DEFAULT_SECRETS:
            raise RuntimeError("Set UIS_INTEGRATION_API_KEY before running in production")
    elif settings.SECRET_KEY in _DEFAULT_SECRETS:
        print("WARNING: using default SECRET_KEY — set SECRET_KEY for any shared/deployed environment")

    await init_db()
    from app.services.supabase_storage import ensure_bucket
    try:
        bucket = await ensure_bucket()
        if bucket:
            print(f"Supabase Storage ready — bucket: {bucket}")
        else:
            print("Supabase storage skipped/not configured — using local storage only.")
    except Exception as exc:
        print(f"Supabase storage init skipped: {exc}")
    stop = asyncio.Event()
    worker = asyncio.create_task(_outbox_worker(stop))
    yield
    stop.set()
    await worker


_settings = get_settings()
_docs = None if _settings.ENVIRONMENT.lower() == "production" else "/docs"
_redoc = None if _settings.ENVIRONMENT.lower() == "production" else "/redoc"

app = FastAPI(
    lifespan=lifespan,
    title="Campus-GPT API",
    description="Multi-purpose campus assistant: academics, timetable, attendance, marks, faculty, planning, admissions",
    version="1.0.0",
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=None if _settings.ENVIRONMENT.lower() == "production" else "/openapi.json",
)
_cors_origins = {
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://campus-gpt-ecru.vercel.app",
    "https://campusgpt-ai.vercel.app",
}
if _settings.FRONTEND_URL:
    _cors_origins.add(_settings.FRONTEND_URL.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(voice.router, prefix="/api", tags=["Voice"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])
app.include_router(recommend.router, prefix="/api", tags=["Recommendation"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(integrations.router, prefix="/api/admin", tags=["Integrations"])
app.include_router(student.router, prefix="/api", tags=["Student"])
app.include_router(student_ops.router, prefix="/api", tags=["Student workspace"])
app.include_router(academic.router, prefix="/api", tags=["Academic"])
app.include_router(privacy.router, prefix="/api", tags=["Privacy"])
app.include_router(copilot.router, prefix="/api", tags=["Copilot"])
app.include_router(fees.router, prefix="/api", tags=["Fees"])
app.include_router(messages.router, prefix="/api", tags=["Messages"])
app.include_router(notifications.router, prefix="/api", tags=["Notifications"])
app.include_router(marquee.router, prefix="/api", tags=["Marquee"])
app.include_router(branding.router, prefix="/api", tags=["Branding CMS"])
app.include_router(platform.router, prefix="/api", tags=["Platform"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Campus-GPT API is running"}


@app.get("/health")
async def health():
    """Detailed health check."""
    from app.utils.db_status import get_database_status

    db_info = await get_database_status()
    db_ok = bool(db_info.get("connected"))
    uis_ok = False
    try:
        from app.services import uis_client

        uis_ok = await uis_client.ping() if hasattr(uis_client, "ping") else uis_client.uis_enabled()
    except Exception:
        uis_ok = False
    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "service": "campus-gpt",
        "database": db_ok,
        "database_status": db_info,
        "uis": uis_ok,
    }
