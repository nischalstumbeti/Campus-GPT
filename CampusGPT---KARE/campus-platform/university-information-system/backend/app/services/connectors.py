"""UIS adapter for the shared connector hub."""
from __future__ import annotations

import sys
from pathlib import Path

from app.config import get_settings

_BACKEND = Path(__file__).resolve().parents[2]
_SHARED = _BACKEND.parents[2] / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from campus_connectors import IntegrationHub  # noqa: E402


def _apply(provider: str, cfg: dict) -> None:
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    settings = get_settings()
    if provider == "smtp":
        settings.email_enabled = bool(cfg.get("enabled"))
        settings.smtp_host = str(cfg.get("host") or settings.smtp_host)
        settings.smtp_port = int(cfg.get("port") or settings.smtp_port or 587)
        settings.smtp_user = str(cfg.get("user") or "")
        settings.smtp_password = str(cfg.get("password") or "")
        settings.smtp_from = str(cfg.get("from_header") or "")
    elif provider == "supabase":
        settings.supabase_url = str(cfg.get("url") or "")
        settings.supabase_key = str(cfg.get("key") or "")
        if cfg.get("database_url"):
            settings.supabase_db_url = str(cfg["database_url"])
    elif provider == "mongodb":
        settings.mongodb_uri = str(cfg.get("uri") or "")
        settings.mongodb_db = str(cfg.get("database") or "campus")
    elif provider == "s3":
        settings.s3_endpoint = str(cfg.get("endpoint") or "")
        settings.s3_region = str(cfg.get("region") or "us-east-1")
        settings.s3_bucket = str(cfg.get("bucket") or "")
        settings.s3_access_key = str(cfg.get("access_key") or "")
        settings.s3_secret_key = str(cfg.get("secret_key") or "")


hub = IntegrationHub(
    store_path=_BACKEND / "data" / "integrations.json",
    env_path=_BACKEND / ".env",
    on_apply=_apply,
)


def open_store(provider: str | None = None):
    """Return a live Supabase, MongoDB, or S3 client for the selected store."""
    return hub.open_client(provider)
