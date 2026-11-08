from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import AuditEvent


async def write_audit(
    db: AsyncSession,
    *,
    user: dict | None,
    action: str,
    resource: str,
    detail: str = "",
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=int(user["sub"]) if user and str(user.get("sub", "")).isdigit() else None,
            actor_email=str(user.get("email") or "") if user else "",
            actor_role=str(user.get("role") or "") if user else "",
            action=action,
            resource=resource,
            detail=(detail or "")[:1000],
        )
    )
    await db.flush()
