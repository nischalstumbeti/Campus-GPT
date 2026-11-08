"""Privacy & Consent Center APIs."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db
from app.utils.auth import get_current_user, require_admin
from app.security.permissions import catalog_payload, ALL_KEYS
from app.services import consent as consents
from app.models.privacy import AccessLog, AuditLog

router = APIRouter()


class ConsentPatch(BaseModel):
    key: str
    status: str  # allow | deny


@router.get("/privacy/consents")
async def get_consents(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    uid = int(user["sub"])
    rows = await consents.list_consents(db, uid)
    by_key = {r.permission_key: r for r in rows}
    groups = catalog_payload()
    for g in groups:
        for p in g["permissions"]:
            row = by_key.get(p["key"])
            p["status"] = row.status if row else "allow"
            p["purpose"] = row.purpose if row else g["purpose"]
            p["updated_at"] = row.updated_at.isoformat() if row and row.updated_at else None
    return {
        "notice": "Campus-GPT uses this information only to provide personalized university assistance.",
        "groups": groups,
    }


@router.post("/privacy/consents")
async def patch_consent(
    body: ConsentPatch,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if body.key not in ALL_KEYS:
        raise HTTPException(status_code=400, detail="Unknown permission")
    if body.status not in ("allow", "deny"):
        raise HTTPException(status_code=400, detail="status must be allow or deny")
    uid = int(user["sub"])
    row = await consents.set_consent(db, uid, body.key, body.status)
    # Keep UIS integration consents in sync so revoke blocks Campus-GPT API access too
    try:
        from app.services.student_context import get_uis_username

        uis_user = await get_uis_username(db, user)
        if uis_user:
            await consents.push_consent_to_uis(uis_user, body.key, body.status)
    except Exception:
        pass
    return {
        "ok": True,
        "key": row.permission_key,
        "status": row.status,
        "notice": (
            "Revoked permissions stop Campus-GPT from using that data until you allow them again."
            if body.status == "deny"
            else "Permission allowed for Campus-GPT assistance."
        ),
    }


@router.get("/privacy/access-log")
async def access_log(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    uid = int(user["sub"])
    rows = (
        await db.execute(
            select(AccessLog).where(AccessLog.user_id == uid).order_by(AccessLog.created_at.desc()).limit(50)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "when": r.created_at.isoformat() if r.created_at else None,
                "data": r.data_type,
                "purpose": r.purpose,
                "component": r.component,
                "permission": r.permission_key,
            }
            for r in rows
        ]
    }


@router.get("/audit")
async def admin_audit(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "detail": r.detail,
                "when": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
