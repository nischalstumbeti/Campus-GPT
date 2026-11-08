"""Simple in-memory sliding-window rate limiter for auth endpoints."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, *, limit: int = 30, window_seconds: float = 60.0) -> None:
    now = time.monotonic()
    bucket = _hits[key]
    _hits[key] = [t for t in bucket if now - t < window_seconds]
    if len(_hits[key]) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Try again shortly.")
    _hits[key].append(now)


def client_key(request: Request | None, suffix: str) -> str:
    if request is None:
        return suffix
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = (forwarded.split(",")[0].strip() if forwarded else "") or (
        request.client.host if request.client else "unknown"
    )
    return f"{ip}:{suffix}"
