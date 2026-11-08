"""Admin CMS — branding / theme settings for UIS."""
from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import BrandingSettings, User
from app.security.auth import require_roles

router = APIRouter(prefix="/api/v1", tags=["branding"])

AdminRoles = require_roles("university_admin", "admin", "super_admin", "hod")

DEFAULT_BRANDING = {
    "primary": "#0B2A4A",
    "primary_dark": "#071E36",
    "secondary": "#1E4A7A",
    "accent": "#C9A227",
    "bg_light": "#F4F7FB",
    "bg_card": "#FFFFFF",
    "text_color": "#0F172A",
    "font_family": "Verdana, Tahoma, sans-serif",
    "font_size_base": "16px",
    "heading_scale": "1.25",
    "background_image_url": "",
    "background_overlay": "0.9",
    "login_background_url": "",
    "logo_url": "",
    "header_title": "",
    "header_subtitle": "",
    "footer_text": "",
    "sign_in_label": "Sign in",
    "app_name": "",
}

FONT_PRESETS = [
    "Verdana, Tahoma, sans-serif",
    "Tahoma, Geneva, Verdana, sans-serif",
    "Georgia, 'Times New Roman', serif",
    "'Segoe UI', Tahoma, Geneva, sans-serif",
    "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
]


def _ser(row: BrandingSettings | None) -> dict:
    if row is None:
        return {**DEFAULT_BRANDING, "id": None, "updated_at": None, "updated_by": None}
    return {
        "id": row.id,
        "primary": row.primary or DEFAULT_BRANDING["primary"],
        "primary_dark": row.primary_dark or DEFAULT_BRANDING["primary_dark"],
        "secondary": row.secondary or DEFAULT_BRANDING["secondary"],
        "accent": row.accent or DEFAULT_BRANDING["accent"],
        "bg_light": row.bg_light or DEFAULT_BRANDING["bg_light"],
        "bg_card": row.bg_card or DEFAULT_BRANDING["bg_card"],
        "text_color": row.text_color or DEFAULT_BRANDING["text_color"],
        "font_family": row.font_family or DEFAULT_BRANDING["font_family"],
        "font_size_base": row.font_size_base or DEFAULT_BRANDING["font_size_base"],
        "heading_scale": row.heading_scale or DEFAULT_BRANDING["heading_scale"],
        "background_image_url": row.background_image_url or "",
        "background_overlay": row.background_overlay or DEFAULT_BRANDING["background_overlay"],
        "login_background_url": row.login_background_url or "",
        "logo_url": row.logo_url or "",
        "header_title": row.header_title or "",
        "header_subtitle": row.header_subtitle or "",
        "footer_text": row.footer_text or "",
        "sign_in_label": row.sign_in_label or DEFAULT_BRANDING["sign_in_label"],
        "app_name": row.app_name or "",
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def _get_or_create(db: AsyncSession) -> BrandingSettings:
    row = (await db.execute(select(BrandingSettings).order_by(BrandingSettings.id).limit(1))).scalar_one_or_none()
    if row:
        return row
    row = BrandingSettings(**DEFAULT_BRANDING)
    db.add(row)
    await db.flush()
    return row


class BrandingIn(BaseModel):
    primary: Optional[str] = Field(default=None, max_length=32)
    primary_dark: Optional[str] = Field(default=None, max_length=32)
    secondary: Optional[str] = Field(default=None, max_length=32)
    accent: Optional[str] = Field(default=None, max_length=32)
    bg_light: Optional[str] = Field(default=None, max_length=32)
    bg_card: Optional[str] = Field(default=None, max_length=32)
    text_color: Optional[str] = Field(default=None, max_length=32)
    font_family: Optional[str] = Field(default=None, max_length=255)
    font_size_base: Optional[str] = Field(default=None, max_length=16)
    heading_scale: Optional[str] = Field(default=None, max_length=16)
    background_image_url: Optional[str] = None
    background_overlay: Optional[str] = Field(default=None, max_length=16)
    login_background_url: Optional[str] = None
    logo_url: Optional[str] = None
    header_title: Optional[str] = Field(default=None, max_length=160)
    header_subtitle: Optional[str] = Field(default=None, max_length=255)
    footer_text: Optional[str] = None
    sign_in_label: Optional[str] = Field(default=None, max_length=80)
    app_name: Optional[str] = Field(default=None, max_length=120)


@router.get("/branding")
async def get_branding_public(db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(select(BrandingSettings).order_by(BrandingSettings.id).limit(1))).scalar_one_or_none()
    return {"branding": _ser(row), "fonts": FONT_PRESETS}


@router.get("/admin/branding")
async def get_branding_admin(
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _get_or_create(db)
    return {"branding": _ser(row), "fonts": FONT_PRESETS}


@router.put("/admin/branding")
async def update_branding(
    body: BrandingIn,
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _get_or_create(db)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    row.updated_by = user.email or user.username
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "branding": _ser(row), "fonts": FONT_PRESETS}


@router.post("/admin/branding/reset")
async def reset_branding(
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = await _get_or_create(db)
    for key, value in DEFAULT_BRANDING.items():
        setattr(row, key, value)
    row.updated_by = user.email or user.username
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "branding": _ser(row), "fonts": FONT_PRESETS}


@router.post("/admin/branding/upload-background")
async def upload_background(
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    kind: str = Query(default="app"),
):
    content = await file.read()
    if len(content) > 4_500_000:
        return {"ok": False, "detail": "Image too large (max ~4.5MB)."}
    mime = file.content_type or "image/png"
    if not mime.startswith("image/"):
        return {"ok": False, "detail": "Only image uploads are allowed."}
    b64 = base64.b64encode(content).decode("ascii")
    public_url = f"data:{mime};base64,{b64}"
    row = await _get_or_create(db)
    fields = {"login": "login_background_url", "logo": "logo_url"}
    field = fields.get(kind, "background_image_url")
    setattr(row, field, public_url)
    row.updated_by = user.email or user.username
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "url": public_url, "branding": _ser(row)}


@router.post("/admin/branding/clear-image")
async def clear_image(
    user: Annotated[User, Depends(AdminRoles)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: str = Query(default="logo"),
):
    fields = {"login": "login_background_url", "logo": "logo_url", "app": "background_image_url"}
    field = fields.get(kind)
    if not field:
        return {"ok": False, "detail": "Unknown image kind"}
    row = await _get_or_create(db)
    setattr(row, field, "")
    row.updated_by = user.email or user.username
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "branding": _ser(row)}
