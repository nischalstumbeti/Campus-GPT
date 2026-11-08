"""One photo format for every account.

Pages render `photo_url` as an image source, so the stored value is a data URL.
JPG, PNG, and WebP are accepted even when the browser omits a content type.
"""
from __future__ import annotations

import base64

ALLOWED = {"image/jpeg": "image/jpeg", "image/jpg": "image/jpeg", "image/png": "image/png", "image/webp": "image/webp"}
MAX_BYTES = 1_500_000


def image_mime(content: bytes, declared: str | None) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    cleaned = (declared or "").split(";")[0].strip().lower()
    if cleaned in ALLOWED:
        return ALLOWED[cleaned]
    raise ValueError("Upload a JPG, PNG, or WebP photo.")


def photo_data_url(content: bytes, declared: str | None) -> str:
    if len(content) > MAX_BYTES:
        raise ValueError("Photo is too large (max 1.5 MB).")
    if not content:
        raise ValueError("The photo file is empty.")
    mime = image_mime(content, declared)
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def apply_photo(user, student, photo: str) -> None:
    """Keep the account photo and the student record photo the same."""
    if user is not None:
        user.photo_url = photo
    if student is not None:
        student.photo_url = photo
