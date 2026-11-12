"""Admin CMS — application branding / theme settings (single active row)."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.utils.database import Base


class BrandingSettings(Base):
    __tablename__ = "branding_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Color palette
    primary = Column(String(32), default="#7C5AED")
    primary_dark = Column(String(32), default="#6B4DD4")
    secondary = Column(String(32), default="#5B3AD4")
    accent = Column(String(32), default="#F59E0B")
    bg_light = Column(String(32), default="#FFFFFF")
    bg_card = Column(String(32), default="#FFFFFF")
    text_color = Column(String(32), default="#1a1a2e")
    # Typography
    font_family = Column(String(255), default="Tahoma, Geneva, Verdana, sans-serif")
    font_size_base = Column(String(16), default="16px")
    heading_scale = Column(String(16), default="1.25")
    # Backgrounds (URL or data URL)
    background_image_url = Column(Text, default="")
    background_overlay = Column(String(16), default="0.88")
    login_background_url = Column(Text, default="")
    logo_url = Column(Text, default="")
    app_name = Column(String(120), default="Campus-GPT")
    updated_by = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


DEFAULT_BRANDING = {
    "primary": "#7C5AED",
    "primary_dark": "#6B4DD4",
    "secondary": "#5B3AD4",
    "accent": "#F59E0B",
    "bg_light": "#FFFFFF",
    "bg_card": "#FFFFFF",
    "text_color": "#1a1a2e",
    "font_family": "Tahoma, Geneva, Verdana, sans-serif",
    "font_size_base": "16px",
    "heading_scale": "1.25",
    "background_image_url": "",
    "background_overlay": "0.88",
    "login_background_url": "",
    "logo_url": "",
    "app_name": "Campus-GPT",
}
