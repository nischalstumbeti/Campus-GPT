from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def write_audit(
    db: AsyncSession,
    *,
    actor: str,
    resource: str,
    action: str,
    result: str,
    user_ref: str | None = None,
    role: str | None = None,
    purpose: str = "",
) -> None:
    db.add(
        AuditLog(
            timestamp=datetime.utcnow(),
            actor=actor,
            user_ref=user_ref,
            role=role,
            resource=resource,
            action=action,
            purpose=purpose,
            result=result,
        )
    )
    await db.commit()
