"""Admin CMS — branding / theme settings."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branding import DEFAULT_BRANDING, BrandingSettings
from app.utils.auth import get_current_user_optional, require_admin
from app.utils.database import get_db

router = APIRouter()

FONT_PRESETS = [
    "Tahoma, Geneva, Verdana, sans-serif",
    "Verdana, Geneva, Tahoma, sans-serif",
    "Georgia, 'Times New Roman', serif",
    "'Segoe UI', Tahoma, Geneva, sans-serif",
    "'Trebuchet MS', Helvetica, sans-serif",
    "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
    "'Courier New', Courier, monospace",
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
        "app_name": row.app_name or DEFAULT_BRANDING["app_name"],
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
    app_name: Optional[str] = Field(default=None, max_length=120)


@router.get("/branding")
async def get_branding_public(db: AsyncSession = Depends(get_db)):
    """Public active branding for ThemeProvider."""
    row = (await db.execute(select(BrandingSettings).order_by(BrandingSettings.id).limit(1))).scalar_one_or_none()
    return {"branding": _ser(row), "fonts": FONT_PRESETS}


@router.get("/admin/branding")
async def get_branding_admin(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    row = await _get_or_create(db)
    return {"branding": _ser(row), "fonts": FONT_PRESETS}


@router.put("/admin/branding")
async def update_branding(
    body: BrandingIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    row = await _get_or_create(db)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    row.updated_by = str(user.get("email") or user.get("sub") or "admin")
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "branding": _ser(row), "fonts": FONT_PRESETS}


@router.post("/admin/branding/reset")
async def reset_branding(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    row = await _get_or_create(db)
    for key, value in DEFAULT_BRANDING.items():
        setattr(row, key, value)
    row.updated_by = str(user.get("email") or user.get("sub") or "admin")
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "branding": _ser(row), "fonts": FONT_PRESETS}


@router.post("/admin/branding/upload-background")
async def upload_background(
    file: UploadFile = File(...),
    kind: str = Query(default="app"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Upload a background image (stored via Supabase when available, else data URL in DB)."""
    import base64

    content = await file.read()
    if len(content) > 4_500_000:
        return {"ok": False, "detail": "Image too large (max ~4.5MB)."}
    mime = file.content_type or "image/png"
    if not mime.startswith("image/"):
        return {"ok": False, "detail": "Only image uploads are allowed."}

    public_url = None
    try:
        from app.services.supabase_storage import is_supabase_configured, upload_file

        if is_supabase_configured():
            stored = await upload_file(content, file.filename or "bg.png", folder="branding")
            if stored:
                public_url = stored.get("public_url")
    except Exception:
        public_url = None

    if not public_url:
        b64 = base64.b64encode(content).decode("ascii")
        public_url = f"data:{mime};base64,{b64}"

    row = await _get_or_create(db)
    field = "login_background_url" if kind == "login" else "background_image_url"
    setattr(row, field, public_url)
    row.updated_by = str(user.get("email") or user.get("sub") or "admin")
    row.updated_at = datetime.utcnow()
    await db.flush()
    return {"ok": True, "url": public_url, "branding": _ser(row)}
