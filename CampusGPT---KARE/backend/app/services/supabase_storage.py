"""Supabase Storage helper — optional document archival for the knowledge base.

Uses the Supabase Storage REST API directly via httpx (no SDK required).

Configuration (backend/.env):
    SUPABASE_URL=https://<project-ref>.supabase.co
    SUPABASE_KEY=<storage-scoped project API key, sb_secret_...>
    SUPABASE_BUCKET=campus-documents          (optional, default applied)

The supplied key is expected to be a Storage-scoped API key; PostgREST/auth
access is NOT used. Every function is safe to call when Supabase is not
configured — callers get None / a skip so the rest of the app keeps working
on the local SQLite setup.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx

from app.config import get_settings

DEFAULT_BUCKET = "campus-documents"


def is_supabase_configured() -> bool:
    settings = get_settings()
    return bool(settings.SUPABASE_URL and settings.SUPABASE_KEY)


def _headers(key: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _base_url() -> str:
    return get_settings().SUPABASE_URL.rstrip("/")


async def ensure_bucket(bucket: str | None = None, public: bool = True) -> str | None:
    """Idempotently create the storage bucket. Returns the bucket name or None.

    Never raises — a failure simply leaves the app without Supabase storage.
    """
    if not is_supabase_configured():
        return None
    settings = get_settings()
    bucket = (bucket or settings.SUPABASE_BUCKET or DEFAULT_BUCKET).strip()
    if not bucket:
        return None
    url = f"{_base_url()}/storage/v1/bucket"
    headers = _headers(settings.SUPABASE_KEY)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            existing = await client.get(url, headers=headers)
            if existing.status_code == 200:
                data = existing.json()
                if isinstance(data, list) and any(b.get("name") == bucket for b in data):
                    return bucket
            resp = await client.post(
                url,
                headers={**headers, "Content-Type": "application/json"},
                json={"id": bucket, "name": bucket, "public": public},
            )
            if resp.status_code in (200, 201, 202) or "already exists" in resp.text.lower():
                return bucket
    except Exception:
        return None
    return None


async def upload_file(
    content: bytes,
    filename: str,
    folder: str = "uploads",
    bucket: str | None = None,
) -> dict | None:
    """Upload a file to Supabase Storage.

    Returns {"storage_path": ..., "public_url": ...} or None when Supabase is
    not configured. Raises RuntimeError on a hard storage failure so callers
    can decide how to surface it.
    """
    if not is_supabase_configured():
        return None
    settings = get_settings()
    bucket = (bucket or settings.SUPABASE_BUCKET or DEFAULT_BUCKET).strip()
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename) or "file"
    path = f"{folder}/{datetime.now(timezone.utc).strftime('%Y%m%d')}/{uuid.uuid4().hex[:12]}_{safe_name}"
    url = f"{_base_url()}/storage/v1/object/{bucket}/{path}"
    headers = _headers(settings.SUPABASE_KEY)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers={**headers, "Content-Type": "application/octet-stream"},
            content=content,
        )
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(
                f"Supabase Storage upload failed: {resp.status_code} {resp.text[:300]}"
            )
    return {
        "storage_path": f"{bucket}/{path}",
        "public_url": f"{_base_url()}/storage/v1/object/public/{bucket}/{path}",
    }