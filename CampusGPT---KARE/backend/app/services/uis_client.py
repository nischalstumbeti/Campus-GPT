"""HTTP client for University Information System integration APIs.

Campus-GPT never opens the UIS database — only these endpoints.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# username -> (token, expires_at monotonic)
_token_cache: dict[str, tuple[str, float]] = {}


class UisClientError(Exception):
    def __init__(self, message: str, status_code: int = 0, detail: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class UisConsentDenied(UisClientError):
    pass


async def ping() -> bool:
    """Lightweight UIS reachability check."""
    if not uis_enabled():
        return False
    try:
        import httpx
        from app.config import get_settings

        settings = get_settings()
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.UIS_API_BASE_URL.rstrip('/')}/health")
            return r.status_code < 500
    except Exception:
        return False


def uis_enabled() -> bool:
    s = get_settings()
    return bool(s.UIS_ENABLED and s.UIS_API_BASE_URL and s.UIS_INTEGRATION_API_KEY)


async def _mint_user_token(uis_username: str) -> str:
    """Mint/cached short-lived UIS user JWT so production can reject username-only headers."""
    now = time.monotonic()
    cached = _token_cache.get(uis_username)
    if cached and cached[1] > now + 30:
        return cached[0]
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}/api/v1/integration/campus-gpt/mint-user-token"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            url,
            headers={"X-API-Key": s.UIS_INTEGRATION_API_KEY, "Accept": "application/json"},
            json={"username": uis_username},
        )
    if r.status_code >= 400:
        raise UisClientError(f"UIS mint token failed {r.status_code}", status_code=r.status_code, detail=r.text[:300])
    token = (r.json() or {}).get("access_token") or ""
    if not token:
        raise UisClientError("UIS mint token returned empty token")
    _token_cache[uis_username] = (token, now + 25 * 60)
    return token


async def _headers(uis_username: str) -> dict[str, str]:
    s = get_settings()
    headers = {
        "X-API-Key": s.UIS_INTEGRATION_API_KEY,
        "Accept": "application/json",
    }
    # Prefer Bearer user JWT; keep username header only as a non-production fallback
    try:
        token = await _mint_user_token(uis_username)
        headers["Authorization"] = f"Bearer {token}"
    except Exception as exc:
        if s.ENVIRONMENT.lower() == "production":
            raise
        logger.warning("UIS mint token failed, falling back to X-UIS-Username: %s", exc)
        headers["X-UIS-Username"] = uis_username
    return headers


async def _get(path: str, uis_username: str, purpose: str = "Campus-GPT assistance") -> dict[str, Any]:
    if not uis_enabled():
        raise UisClientError("UIS integration is disabled")
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, headers=await _headers(uis_username), params={"purpose": purpose})
    except httpx.HTTPError as exc:
        logger.exception("UIS request failed: %s", path)
        raise UisClientError(f"UIS unreachable: {exc}") from exc

    if r.status_code == 403 and "CONSENT" in (r.text or "").upper():
        raise UisConsentDenied("CONSENT_DENIED", status_code=403, detail=r.text)
    if r.status_code >= 400:
        detail = ""
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise UisClientError(f"UIS error {r.status_code}", status_code=r.status_code, detail=str(detail))
    return r.json()


async def resolve_identity_by_email(email: str) -> Optional[dict[str, Any]]:
    """Map Campus-GPT email → UIS username (API-key only)."""
    if not uis_enabled() or not email:
        return None
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}/api/v1/integration/campus-gpt/resolve-identity"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                url,
                headers={"X-API-Key": s.UIS_INTEGRATION_API_KEY, "Accept": "application/json"},
                params={"email": email},
            )
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            logger.warning("UIS resolve-identity failed: %s %s", r.status_code, r.text[:200])
            return None
        return r.json()
    except httpx.HTTPError as exc:
        logger.warning("UIS resolve-identity unreachable: %s", exc)
        return None


async def get_profile(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/profile", uis_username, "Academic assistance")


async def get_attendance(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/attendance", uis_username, "Attendance assistance")


async def get_marks(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/marks", uis_username, "Marks assistance")


async def get_grades(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/grades", uis_username, "Grades assistance")


async def get_courses(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/courses", uis_username, "Course assistance")


async def get_timetable(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/timetable", uis_username, "Timetable assistance")


async def get_exams(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/exams", uis_username, "Exam assistance")


async def get_hostel(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/hostel", uis_username, "Hostel assistance")


async def get_residence(uis_username: str) -> dict:
    """Hostel vs day-scholar/bus — no hostel.room consent required."""
    return await _request(
        "GET",
        "/api/v1/integration/campus-gpt/student/residence",
        uis_username,
        purpose="Residence check",
    )


async def get_complaints(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/complaints", uis_username, "Complaint assistance")


async def create_leave(
    uis_username: str,
    *,
    from_date: str,
    to_date: str,
    reason: str,
    destination: str = "",
) -> dict[str, Any]:
    """Push a hostel leave application into UIS (source of truth for student/faculty/warden)."""
    if not uis_enabled():
        raise UisClientError("UIS integration is disabled")
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}/api/v1/integration/campus-gpt/student/leave"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                url,
                headers=await _headers(uis_username),
                params={"purpose": "Hostel leave application"},
                json={
                    "from_date": from_date,
                    "to_date": to_date,
                    "reason": reason,
                    "destination": destination or "",
                },
            )
    except httpx.HTTPError as exc:
        logger.exception("UIS create leave failed")
        raise UisClientError(f"UIS unreachable: {exc}") from exc

    if r.status_code == 403 and "CONSENT" in (r.text or "").upper():
        raise UisConsentDenied("CONSENT_DENIED", status_code=403, detail=r.text)
    if r.status_code >= 400:
        detail = ""
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise UisClientError(f"UIS error {r.status_code}", status_code=r.status_code, detail=str(detail))
    return r.json()


async def get_achievements(uis_username: str) -> dict:
    return await _get("/api/v1/integration/campus-gpt/student/achievements", uis_username, "Career assistance")


async def get_announcements(*, role: str | None = None, department_code: str | None = None) -> list[dict]:
    if not uis_enabled():
        return []
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}/api/v1/integration/campus-gpt/announcements"
    params: dict[str, str] = {}
    if role:
        params["role"] = role
    if department_code:
        params["department_code"] = department_code
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                url,
                headers={"X-API-Key": s.UIS_INTEGRATION_API_KEY, "Accept": "application/json"},
                params=params or None,
            )
        if r.status_code >= 400:
            return []
        return r.json().get("items") or []
    except httpx.HTTPError:
        return []


async def verify_credentials(identifier: str, password: str) -> Optional[dict[str, Any]]:
    """Validate UIS username/email + password. Returns identity or None if UIS is down / unknown user."""
    if not uis_enabled() or not identifier:
        return None
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}/api/v1/integration/campus-gpt/verify-credentials"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                url,
                headers={"X-API-Key": s.UIS_INTEGRATION_API_KEY, "Accept": "application/json"},
                json={"username": identifier, "password": password},
            )
        if r.status_code == 401:
            raise UisClientError("Invalid UIS credentials", status_code=401)
        if r.status_code >= 400:
            logger.warning("UIS verify-credentials failed: %s %s", r.status_code, r.text[:200])
            return None
        return r.json()
    except httpx.HTTPError as exc:
        logger.warning("UIS verify-credentials unreachable: %s", exc)
        return None


async def verify_session(uis_token: str) -> Optional[dict[str, Any]]:
    if not uis_enabled() or not uis_token:
        return None
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}/api/v1/integration/campus-gpt/verify-session"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                url,
                headers={
                    "X-API-Key": s.UIS_INTEGRATION_API_KEY,
                    "Authorization": f"Bearer {uis_token}",
                    "Accept": "application/json",
                },
            )
        if r.status_code >= 400:
            return None
        return r.json()
    except httpx.HTTPError as exc:
        logger.warning("UIS verify-session unreachable: %s", exc)
        return None


async def get_faculty(q: str | None = None) -> list[dict]:
    if not uis_enabled():
        return []
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}/api/v1/integration/campus-gpt/faculty"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                url,
                headers={"X-API-Key": s.UIS_INTEGRATION_API_KEY, "Accept": "application/json"},
                params={"q": q} if q else None,
            )
        if r.status_code >= 400:
            return []
        return r.json().get("records") or []
    except httpx.HTTPError:
        return []


async def _request(
    method: str,
    path: str,
    uis_username: str,
    *,
    purpose: str = "Campus-GPT assistance",
    json_body: dict | None = None,
    params: dict | None = None,
) -> dict[str, Any]:
    if not uis_enabled():
        raise UisClientError("UIS integration is disabled")
    s = get_settings()
    url = f"{s.UIS_API_BASE_URL.rstrip('/')}{path}"
    q = {"purpose": purpose, **(params or {})}
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.request(
                method,
                url,
                headers=await _headers(uis_username),
                params=q,
                json=json_body,
            )
    except httpx.HTTPError as exc:
        logger.exception("UIS %s failed: %s", method, path)
        raise UisClientError(f"UIS unreachable: {exc}") from exc

    if r.status_code == 403 and "CONSENT" in (r.text or "").upper():
        raise UisConsentDenied("CONSENT_DENIED", status_code=403, detail=r.text)
    if r.status_code >= 400:
        detail = ""
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise UisClientError(f"UIS error {r.status_code}", status_code=r.status_code, detail=str(detail))
    if not r.content:
        return {"ok": True}
    try:
        return r.json()
    except Exception:
        return {"ok": True}


# --- Fees / messages (UIS is system of record when linked) ---


async def get_student_fees(uis_username: str) -> dict:
    return await _request("GET", "/api/v1/integration/campus-gpt/student/fees", uis_username, purpose="Fee assistance")


async def pay_student_fee(uis_username: str, fee_id: int, *, amount: float, method: str = "mock_upi", note: str = "") -> dict:
    return await _request(
        "POST",
        f"/api/v1/integration/campus-gpt/student/fees/{fee_id}/pay",
        uis_username,
        purpose="Fee payment",
        json_body={"amount": amount, "method": method, "note": note},
    )


async def list_fee_students(uis_username: str, *, category: str | None = None, status: str | None = None) -> dict:
    params: dict[str, str] = {}
    if category:
        params["category"] = category
    if status:
        params["status"] = status
    return await _request(
        "GET",
        "/api/v1/integration/campus-gpt/fees/students",
        uis_username,
        purpose="Fee administration",
        params=params or None,
    )


async def staff_edit_fee(uis_username: str, fee_id: int, body: dict) -> dict:
    return await _request(
        "PUT",
        f"/api/v1/integration/campus-gpt/fees/students/{fee_id}",
        uis_username,
        purpose="Fee administration",
        json_body=body,
    )


async def create_fee_plan(uis_username: str, body: dict) -> dict:
    return await _request(
        "POST",
        "/api/v1/integration/campus-gpt/fees/plans",
        uis_username,
        purpose="Fee administration",
        json_body=body,
    )


async def trigger_fee_reminders(uis_username: str, body: dict) -> dict:
    return await _request(
        "POST",
        "/api/v1/integration/campus-gpt/fees/reminders",
        uis_username,
        purpose="Fee reminders",
        json_body=body,
    )


async def get_consents(uis_username: str) -> dict:
    """Fetch UIS integration consent rows for this student (allow / deny / revoke)."""
    return await _request("GET", "/api/v1/integration/campus-gpt/consents", uis_username, purpose="Consent sync")


async def update_consent(uis_username: str, permission_key: str, status: str) -> dict:
    return await _request(
        "PUT",
        "/api/v1/integration/campus-gpt/consents",
        uis_username,
        purpose="Consent update",
        json_body={"permission_key": permission_key, "status": status},
    )


async def list_message_threads(uis_username: str) -> dict:
    return await _request("GET", "/api/v1/integration/campus-gpt/messages/threads", uis_username, purpose="Messaging")


async def create_message_thread(uis_username: str, body: dict) -> dict:
    return await _request(
        "POST",
        "/api/v1/integration/campus-gpt/messages/threads",
        uis_username,
        purpose="Messaging",
        json_body=body,
    )


async def reply_message_thread(uis_username: str, thread_id: int, body: str) -> dict:
    return await _request(
        "POST",
        f"/api/v1/integration/campus-gpt/messages/threads/{thread_id}/reply",
        uis_username,
        purpose="Messaging",
        json_body={"body": body},
    )


async def redirect_message_thread(uis_username: str, thread_id: int, *, redirected_to: str, note: str = "") -> dict:
    return await _request(
        "POST",
        f"/api/v1/integration/campus-gpt/messages/threads/{thread_id}/redirect",
        uis_username,
        purpose="Messaging",
        json_body={"redirected_to": redirected_to, "note": note},
    )


async def list_notifications(uis_username: str) -> dict:
    return await _request("GET", "/api/v1/integration/campus-gpt/notifications", uis_username, purpose="Notifications")


async def mark_notifications_read_all(uis_username: str) -> dict:
    return await _request(
        "POST",
        "/api/v1/integration/campus-gpt/notifications/read-all",
        uis_username,
        purpose="Notifications",
    )


async def mark_notification_read(uis_username: str, notification_id: int) -> dict:
    return await _request(
        "POST",
        f"/api/v1/integration/campus-gpt/notifications/{notification_id}/read",
        uis_username,
        purpose="Notifications",
    )


async def list_marquees(uis_username: str) -> dict:
    return await _request("GET", "/api/v1/integration/campus-gpt/marquee", uis_username, purpose="Marquee CMS")


async def active_marquees(uis_username: str) -> dict:
    return await _request("GET", "/api/v1/integration/campus-gpt/marquee/active", uis_username, purpose="Marquee CMS")


async def create_marquee(uis_username: str, body: dict) -> dict:
    return await _request(
        "POST",
        "/api/v1/integration/campus-gpt/marquee",
        uis_username,
        purpose="Marquee CMS",
        json_body=body,
    )


async def update_marquee(uis_username: str, item_id: int, body: dict) -> dict:
    return await _request(
        "PUT",
        f"/api/v1/integration/campus-gpt/marquee/{item_id}",
        uis_username,
        purpose="Marquee CMS",
        json_body=body,
    )


async def delete_marquee(uis_username: str, item_id: int) -> dict:
    return await _request(
        "DELETE",
        f"/api/v1/integration/campus-gpt/marquee/{item_id}",
        uis_username,
        purpose="Marquee CMS",
    )


async def service_set_password(uis_username: str, new_password: str) -> dict:
    """Password-reset sync (integration API key + username, no current password)."""
    return await _request(
        "POST",
        "/api/v1/integration/campus-gpt/service-set-password",
        uis_username,
        purpose="Password reset sync",
        json_body={"username": uis_username, "new_password": new_password},
    )


async def change_password(uis_username: str, *, current_password: str, new_password: str) -> dict:
    return await _request(
        "POST",
        "/api/v1/integration/campus-gpt/change-password",
        uis_username,
        purpose="Password change",
        json_body={"current_password": current_password, "new_password": new_password},
    )


async def service_set_password(uis_username: str, new_password: str) -> dict:
    """Password-reset sync after Campus-GPT validates a reset token (UIS SoR)."""
    return await _request(
        "POST",
        "/api/v1/integration/campus-gpt/service-set-password",
        uis_username,
        purpose="Password reset sync",
        json_body={"username": uis_username, "new_password": new_password},
    )
