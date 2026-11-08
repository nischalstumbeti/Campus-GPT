"""Consent checks and access / audit logging.

Local UserConsent is the Campus-GPT mirror. When a student is linked to UIS,
UIS IntegrationConsent is also required (allow only). Revoke/deny on either
side blocks that specific permission for Campus-GPT assistance.
"""
from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.privacy import UserConsent, AccessLog, AuditLog
from app.security.permissions import ALL_KEYS, CATEGORIES

# Campus-GPT key -> UIS integration key(s) that must also be allow
LOCAL_TO_UIS: dict[str, list[str]] = {
    "academic.attendance": ["academic.attendance"],
    "academic.marks": ["academic.marks"],
    "academic.grades": ["academic.grades"],
    "academic.cgpa": ["academic.cgpa"],
    "academic.credits": ["academic.credits"],
    "academic.history": ["academic.history"],
    "academic.timetable": ["academic.timetable"],
    "academic.courses": ["academic.courses"],
    "academic.exams": ["academic.exams"],
    "hostel.room": ["hostel.room"],
    "hostel.leave": ["hostel.leave"],
    "hostel.records": ["hostel.room", "complaints.own"],
    "achievements.certs": ["achievements.certs"],
    "achievements.awards": ["achievements.certs"],
    "achievements.activities": ["achievements.certs"],
    "financial.fees": ["fees.records"],
    "financial.scholarship": ["fees.records"],
    "messaging.inbox": ["messaging.inbox"],
    "complaints.own": ["complaints.own"],
}

# Short TTL cache: uis_username -> (expires_monotonic, {key: status})
_uis_consent_cache: dict[str, tuple[float, dict[str, str]]] = {}


def _purpose_for(key: str) -> str:
    for g in CATEGORIES.values():
        if key in g["keys"]:
            return g["purpose"]
    return "Personalized university assistance"


async def ensure_default_consents(db: AsyncSession, user_id: int, default: str = "deny") -> None:
    existing = await db.execute(select(UserConsent.permission_key).where(UserConsent.user_id == user_id))
    have = set(existing.scalars().all())
    for key in ALL_KEYS:
        if key in have:
            continue
        db.add(
            UserConsent(
                user_id=user_id,
                permission_key=key,
                status=default,
                purpose=_purpose_for(key),
            )
        )
    await db.flush()


async def grant_all_consents(db: AsyncSession, user_id: int) -> None:
    """Used by demo seed so presentation accounts work with opt-in defaults elsewhere."""
    await ensure_default_consents(db, user_id, default="allow")
    rows = await db.execute(select(UserConsent).where(UserConsent.user_id == user_id))
    for row in rows.scalars().all():
        row.status = "allow"
    await db.flush()


async def _local_allowed(db: AsyncSession, user_id: int, key: str) -> bool:
    await ensure_default_consents(db, user_id)
    row = (
        await db.execute(
            select(UserConsent).where(UserConsent.user_id == user_id, UserConsent.permission_key == key)
        )
    ).scalar_one_or_none()
    return bool(row and row.status == "allow")


async def fetch_uis_consent_map(uis_username: str, *, force: bool = False) -> dict[str, str]:
    """Return UIS permission_key -> status for a student."""
    now = time.monotonic()
    cached = _uis_consent_cache.get(uis_username)
    if not force and cached and cached[0] > now:
        return cached[1]
    try:
        from app.services import uis_client

        if not uis_client.uis_enabled():
            return {}
        data = await uis_client.get_consents(uis_username)
        mapping = {
            str(it.get("permission_key")): str(it.get("status") or "deny")
            for it in (data.get("items") or [])
            if it.get("permission_key")
        }
        _uis_consent_cache[uis_username] = (now + 45.0, mapping)
        return mapping
    except Exception:
        if cached:
            return cached[1]
        return {}


def invalidate_uis_consent_cache(uis_username: str | None = None) -> None:
    if uis_username:
        _uis_consent_cache.pop(uis_username, None)
    else:
        _uis_consent_cache.clear()


async def sync_from_uis(db: AsyncSession, user_id: int, uis_username: str) -> dict[str, str]:
    """Pull UIS consents into local mirror (revoke/deny → deny)."""
    mapping = await fetch_uis_consent_map(uis_username, force=True)
    if not mapping:
        return mapping
    await ensure_default_consents(db, user_id)
    for local_key, uis_keys in LOCAL_TO_UIS.items():
        if local_key not in ALL_KEYS:
            continue
        # Local allow only if every mapped UIS key is allow
        uis_ok = all(mapping.get(uk) == "allow" for uk in uis_keys)
        if not uis_ok and any(uk in mapping for uk in uis_keys):
            row = (
                await db.execute(
                    select(UserConsent).where(
                        UserConsent.user_id == user_id, UserConsent.permission_key == local_key
                    )
                )
            ).scalar_one_or_none()
            if row and row.status == "allow":
                row.status = "deny"
                row.updated_at = datetime.utcnow()
    await db.flush()
    return mapping


async def is_allowed(
    db: AsyncSession,
    user_id: int | None,
    key: str,
    *,
    uis_username: str | None = None,
) -> bool:
    if user_id is None:
        return False
    if not await _local_allowed(db, user_id, key):
        return False
    # Campus-GPT-only master switches — local only
    if key.startswith("campus_gpt."):
        return True
    if not uis_username:
        return True
    uis_keys = LOCAL_TO_UIS.get(key)
    if not uis_keys:
        return True
    mapping = await fetch_uis_consent_map(uis_username)
    if not mapping:
        # UIS unreachable — keep local decision (API calls will still CONSENT_DENIED later)
        return True
    for uk in uis_keys:
        status = mapping.get(uk)
        if status is None:
            # Key never seeded → treat as deny (opt-in)
            return False
        if status != "allow":
            return False
    return True


async def set_consent(db: AsyncSession, user_id: int, key: str, status: str) -> UserConsent:
    if key not in ALL_KEYS:
        raise ValueError("Unknown permission")
    if status not in ("allow", "deny"):
        raise ValueError("Invalid status")
    await ensure_default_consents(db, user_id)
    row = (
        await db.execute(
            select(UserConsent).where(UserConsent.user_id == user_id, UserConsent.permission_key == key)
        )
    ).scalar_one_or_none()
    if not row:
        row = UserConsent(user_id=user_id, permission_key=key, purpose=_purpose_for(key))
        db.add(row)
    row.status = status
    row.updated_at = datetime.utcnow()
    db.add(AuditLog(user_id=user_id, action="consent_" + status, detail=key))
    await db.flush()
    return row


async def push_consent_to_uis(uis_username: str, key: str, status: str) -> None:
    """Mirror Campus-GPT Privacy toggle onto UIS integration consents."""
    uis_keys = LOCAL_TO_UIS.get(key, [])
    if not uis_keys:
        return
    uis_status = "allow" if status == "allow" else "revoke"
    try:
        from app.services import uis_client

        if not uis_client.uis_enabled():
            return
        for uk in uis_keys:
            await uis_client.update_consent(uis_username, uk, uis_status)
        invalidate_uis_consent_cache(uis_username)
    except Exception:
        pass


async def list_consents(db: AsyncSession, user_id: int) -> list[UserConsent]:
    await ensure_default_consents(db, user_id)
    rows = await db.execute(select(UserConsent).where(UserConsent.user_id == user_id))
    return list(rows.scalars().all())


async def log_access(
    db: AsyncSession,
    user_id: int | None,
    data_type: str,
    purpose: str,
    permission_key: str = "",
    component: str = "copilot",
) -> None:
    if user_id is None:
        return
    db.add(
        AccessLog(
            user_id=user_id,
            data_type=data_type,
            purpose=purpose,
            permission_key=permission_key,
            component=component,
        )
    )


async def log_audit(db: AsyncSession, user_id: int | None, action: str, detail: str = "") -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail[:250]))
