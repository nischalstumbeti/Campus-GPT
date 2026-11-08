"""Live health probes for the campus services shown on the admin Service monitor page."""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx

from app.utils.db_status import get_database_status

HISTORY_SIZE = 30
PROBE_TIMEOUT_S = 3.0

# kind: "http" (GET, 2xx = up), "tcp" (port accepts connections), "self" (this API + its database).
# optional services show "not running" instead of "down" when unreachable.
SERVICES: list[dict[str, Any]] = [
    {"key": "uis-web", "group": "University Information System", "name": "UIS web portal", "kind": "http",
     "url": os.getenv("MONITOR_UIS_WEB_URL", "http://localhost:3000/"), "port": 3000},
    {"key": "uis-api", "group": "University Information System", "name": "UIS API and database", "kind": "self",
     "url": "http://localhost:8000/health", "port": 8000},
    {"key": "gpt-web", "group": "Campus-GPT", "name": "Campus-GPT web app", "kind": "http",
     "url": os.getenv("MONITOR_GPT_WEB_URL", "http://localhost:3001/"), "port": 3001},
    {"key": "gpt-api", "group": "Campus-GPT", "name": "Campus-GPT API", "kind": "http",
     "url": os.getenv("MONITOR_GPT_API_URL", "http://localhost:8002/health"), "port": 8002},
    {"key": "tt-web", "group": "Timetable Allotment System", "name": "SmartTimetable web app", "kind": "http",
     "url": os.getenv("MONITOR_TT_WEB_URL", "http://localhost:5173/"), "port": 5173},
    {"key": "tt-api", "group": "Timetable Allotment System", "name": "SmartTimetable API", "kind": "http",
     "url": os.getenv("MONITOR_TT_API_URL", "http://localhost:5000/api/health"), "port": 5000},
    {"key": "tt-db", "group": "Timetable Allotment System", "name": "SmartTimetable PostgreSQL", "kind": "tcp",
     "host": "localhost", "port": int(os.getenv("MONITOR_TT_DB_PORT", "5433"))},
    {"key": "tt-scheduler", "group": "Timetable Allotment System", "name": "Timetable scheduler (OR-Tools)",
     "kind": "http", "url": os.getenv("MONITOR_TT_SCHEDULER_URL", "http://localhost:8100/health"), "port": 8100,
     "optional": True, "note": "Built in SmartTimetable Phase 4"},
    {"key": "pg-main", "group": "Infrastructure", "name": "PostgreSQL 18 service", "kind": "tcp",
     "host": "localhost", "port": int(os.getenv("MONITOR_PG_PORT", "5432"))},
]

_history: dict[str, deque] = {s["key"]: deque(maxlen=HISTORY_SIZE) for s in SERVICES}
_last_up: dict[str, str] = {}


def _health_detail(body: Any) -> tuple[bool, str]:
    """Interpret common health JSON shapes; returns (healthy, detail)."""
    if not isinstance(body, dict):
        return True, "Responding"
    status = str(body.get("status", "")).lower()
    db = body.get("database")
    db_state = db.get("connected") if isinstance(db, dict) else db
    if db_state in (False, "unreachable", "disconnected"):
        return False, "Responding, database unreachable"
    if status in ("degraded", "unhealthy", "error", "down"):
        return False, f"Reports status '{status}'"
    parts = []
    if status:
        parts.append(f"status {status}")
    if db_state in (True, "connected"):
        parts.append("database connected")
    return True, ", ".join(parts).capitalize() or "Responding"


async def _probe_http(client: httpx.AsyncClient, svc: dict) -> dict:
    started = time.perf_counter()
    try:
        res = await client.get(svc["url"])
    except httpx.HTTPError as exc:
        return {"state": "down", "latency_ms": None, "detail": _connection_error(exc, svc)}
    latency = round((time.perf_counter() - started) * 1000)
    if res.status_code >= 500:
        return {"state": "down", "latency_ms": latency, "detail": f"HTTP {res.status_code}"}
    if res.status_code >= 400:
        return {"state": "degraded", "latency_ms": latency, "detail": f"HTTP {res.status_code}"}
    healthy, detail = True, f"HTTP {res.status_code}"
    if "json" in res.headers.get("content-type", ""):
        try:
            healthy, detail = _health_detail(res.json())
        except ValueError:
            pass
    return {"state": "up" if healthy else "degraded", "latency_ms": latency, "detail": detail}


def _connection_error(exc: Exception, svc: dict) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return f"No response within {PROBE_TIMEOUT_S:.0f}s"
    return f"Nothing is listening on port {svc.get('port')}"


async def _probe_tcp(svc: dict) -> dict:
    started = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(svc["host"], svc["port"]), PROBE_TIMEOUT_S)
    except (OSError, asyncio.TimeoutError):
        return {"state": "down", "latency_ms": None, "detail": f"Port {svc['port']} is not accepting connections"}
    latency = round((time.perf_counter() - started) * 1000)
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return {"state": "up", "latency_ms": latency, "detail": f"Accepting connections on port {svc['port']}"}


async def _probe_self() -> dict:
    started = time.perf_counter()
    db = await get_database_status()
    latency = round((time.perf_counter() - started) * 1000)
    if db.get("connected"):
        engine = db.get("server_version") or db.get("dialect") or "database"
        return {"state": "up", "latency_ms": latency, "detail": f"API running, {engine} connected"}
    return {"state": "degraded", "latency_ms": latency, "detail": "API running, database unreachable"}


async def check_services() -> dict:
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S, follow_redirects=True) as client:

        async def run(svc: dict) -> dict:
            if svc["kind"] == "self":
                return await _probe_self()
            if svc["kind"] == "tcp":
                return await _probe_tcp(svc)
            return await _probe_http(client, svc)

        results = await asyncio.gather(*(run(s) for s in SERVICES))

    now = datetime.now(timezone.utc).isoformat()
    services = []
    for svc, result in zip(SERVICES, results):
        state = result["state"]
        if state == "down" and svc.get("optional"):
            state = "not_running"
        if state == "up":
            _last_up[svc["key"]] = now
        hist = _history[svc["key"]]
        hist.append({"at": now, "state": state, "latency_ms": result["latency_ms"]})
        ups = sum(1 for h in hist if h["state"] == "up")
        services.append({
            "key": svc["key"],
            "group": svc["group"],
            "name": svc["name"],
            "target": svc.get("url") or f"{svc['host']}:{svc['port']}",
            "kind": svc["kind"],
            "optional": bool(svc.get("optional")),
            "note": svc.get("note"),
            "state": state,
            "latency_ms": result["latency_ms"],
            "detail": result["detail"],
            "last_up": _last_up.get(svc["key"]),
            "uptime_pct": round(ups / len(hist) * 100, 1),
            "history": list(hist),
        })

    counted = [s for s in services if not s["optional"]]
    summary = {
        "total": len(counted),
        "up": sum(1 for s in counted if s["state"] == "up"),
        "degraded": sum(1 for s in counted if s["state"] == "degraded"),
        "down": sum(1 for s in counted if s["state"] == "down"),
    }
    summary["overall"] = "down" if summary["down"] else "degraded" if summary["degraded"] else "up"
    return {"checked_at": now, "summary": summary, "services": services}
