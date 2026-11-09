"""Admin switch that keeps the CIMS and Campus GPT Render services awake."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models import User
from app.routes.admin import AdminRoles, EditRoles
from app.services import keep_awake

router = APIRouter(prefix="/api/v1/admin/keep-awake", tags=["keep-awake"])


class KeepAwakeUpdate(BaseModel):
    enabled: bool


@router.get("")
async def get_keep_awake(_: Annotated[User, Depends(AdminRoles)]):
    return keep_awake.status_payload(await keep_awake.is_enabled())


@router.put("")
async def update_keep_awake(body: KeepAwakeUpdate, _: Annotated[User, Depends(EditRoles)]):
    await keep_awake.set_enabled(body.enabled)
    if body.enabled:
        asyncio.create_task(keep_awake.ping_once())
    return keep_awake.status_payload(body.enabled)
