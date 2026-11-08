"""Admin API for reusable Supabase, MongoDB, S3, and SMTP connectors."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security.auth import require_roles
from app.services.connectors import hub
from app.services import connectors as connector_mod

router = APIRouter(prefix="/api/v1/admin", tags=["integrations"])
AdminRoles = require_roles(
    "university_admin", "admin", "super_admin", "developer", "director", "coe", "operator"
)


class SaveBody(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    make_active: bool = False


class TestBody(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    to: str | None = None


def _known(provider: str) -> str:
    from campus_connectors import provider_ids

    if provider not in provider_ids():
        raise HTTPException(status_code=404, detail="Unknown connector")
    return provider


@router.get("/integrations")
async def get_integrations(user: Annotated[object, Depends(AdminRoles)]):
    return hub.public()


@router.put("/integrations/{provider}")
async def save_integration(
    provider: str,
    body: SaveBody,
    user: Annotated[object, Depends(AdminRoles)],
):
    _known(provider)
    try:
        return hub.save(provider, body.values, make_active=body.make_active)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)[:500]) from exc


@router.post("/integrations/{provider}/test")
async def test_integration(
    provider: str,
    body: TestBody,
    user: Annotated[object, Depends(AdminRoles)],
):
    _known(provider)
    return hub.test(provider, body.values, send_to=body.to)


@router.post("/integrations/open-check")
async def open_check(user: Annotated[object, Depends(AdminRoles)]):
    try:
        client = connector_mod.open_store()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)[:500]) from exc
    name = type(client).__name__
    closer = getattr(client, "close", None)
    if callable(closer):
        closer()
    return {"ok": True, "detail": f"Active store opened ({name}).", "active": hub.active()}
