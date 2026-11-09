"""Ping the live Render APIs on a timer so the free instances stay awake."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

from app.database import SessionLocal
from app.models import RuntimeSetting

SETTING_KEY = "keep_render_awake"
INTERVAL_SECONDS = 300
PROBE_TIMEOUT_S = 75.0

# Inbound requests are what reset Render's idle timer. Calling each public URL
# does that for both services, including this API.
TARGETS: list[dict[str, str]] = [
    {"name": "CIMS API", "url": "https://cims-api-g0rm.onrender.com"},
    {"name": "Campus GPT API", "url": "https://campus-gpt-api.onrender.com/"},
]

_last_run_at: str | None = None
_last_results: list[dict[str, Any]] = []
_task: asyncio.Task | None = None


def status_payload(enabled: bool) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "interval_minutes": INTERVAL_SECONDS // 60,
        "targets": TARGETS,
        "last_run_at": _last_run_at,
        "last_results": _last_results,
    }


async def is_enabled() -> bool:
    try:
        async with SessionLocal() as db:
            row = await db.get(RuntimeSetting, SETTING_KEY)
            return bool(row and row.value == "1")
    except Exception:
        return False


async def set_enabled(enabled: bool) -> None:
    async with SessionLocal() as db:
        row = await db.get(RuntimeSetting, SETTING_KEY)
        if row is None:
            row = RuntimeSetting(key=SETTING_KEY, value="1" if enabled else "0")
            db.add(row)
        else:
            row.value = "1" if enabled else "0"
            row.updated_at = datetime.utcnow()
        await db.commit()


async def ping_once() -> list[dict[str, Any]]:
    global _last_run_at, _last_results
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S, follow_redirects=True) as client:
        for target in TARGETS:
            try:
                res = await client.get(target["url"])
                ok = res.status_code < 500
                detail = f"HTTP {res.status_code}"
            except httpx.HTTPError as exc:
                ok = False
                detail = str(exc.__class__.__name__)
            results.append({"name": target["name"], "url": target["url"], "ok": ok, "detail": detail})
    _last_run_at = datetime.now(timezone.utc).isoformat()
    _last_results = results
    print("Render keep-awake: " + ", ".join(f"{r['name']} {r['detail']}" for r in results))
    return results


async def keep_awake_loop() -> None:
    while True:
        try:
            if await is_enabled():
                await ping_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Render keep-awake skipped: {exc}")
        await asyncio.sleep(INTERVAL_SECONDS)


def start() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(keep_awake_loop())


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
