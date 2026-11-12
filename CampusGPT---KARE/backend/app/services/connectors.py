"""Campus-GPT adapter for the shared connector hub."""
from __future__ import annotations

import sys
from pathlib import Path

from app.config import get_settings

_BACKEND = Path(__file__).resolve().parents[2]
_SHARED = _BACKEND.parent / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from campus_connectors import IntegrationHub  # noqa: E402

_SMTP = {
    "enabled": "EMAIL_ENABLED",
    "host": "SMTP_HOST",
    "port": "SMTP_PORT",
    "user": "SMTP_USER",
    "password": "SMTP_PASSWORD",
    "from_header": "SMTP_FROM",
}
_SUPABASE = {"url": "SUPABASE_URL", "key": "SUPABASE_KEY"}


def _apply(provider: str, cfg: dict) -> None:
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    settings = get_settings()
    if provider == "smtp":
        settings.EMAIL_ENABLED = bool(cfg.get("enabled"))
        settings.SMTP_HOST = str(cfg.get("host") or settings.SMTP_HOST)
        settings.SMTP_PORT = int(cfg.get("port") or settings.SMTP_PORT or 587)
        settings.SMTP_USER = str(cfg.get("user") or "")
        settings.SMTP_PASSWORD = str(cfg.get("password") or "")
        settings.SMTP_FROM = str(cfg.get("from_header") or "")
    elif provider == "supabase":
        settings.SUPABASE_URL = str(cfg.get("url") or "")
        settings.SUPABASE_KEY = str(cfg.get("key") or "")
        if cfg.get("database_url"):
            settings.SUPABASE_DB_URL = str(cfg["database_url"])
    elif provider == "mongodb":
        settings.MONGODB_URI = str(cfg.get("uri") or "")
        settings.MONGODB_DB = str(cfg.get("database") or "campus")
    elif provider == "s3":
        settings.S3_ENDPOINT = str(cfg.get("endpoint") or "")
        settings.S3_REGION = str(cfg.get("region") or "us-east-1")
        settings.S3_BUCKET = str(cfg.get("bucket") or "")
        settings.S3_ACCESS_KEY = str(cfg.get("access_key") or "")
        settings.S3_SECRET_KEY = str(cfg.get("secret_key") or "")
    elif provider == "gemini":
        settings.GEMINI_API_KEY = str(cfg.get("api_key") or "").strip()
        if str(cfg.get("model") or "").strip():
            settings.GEMINI_CHAT_MODEL = str(cfg.get("model")).strip()
        try:
            from app.services.rag_service import reset_gemini

            reset_gemini()
        except Exception:
            pass


hub = IntegrationHub(
    store_path=_BACKEND / "data" / "integrations.json",
    env_path=_BACKEND / ".env",
    on_apply=_apply,
)


def open_store(provider: str | None = None):
    """Return a live Supabase, MongoDB, or S3 client for the store the admin selected."""
    return hub.open_client(provider)
