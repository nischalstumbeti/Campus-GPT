"""SMTP email delivery for UIS (shares Campus-GPT Gmail mailbox)."""
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


def _wrap_html(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Verdana,Tahoma,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px;">
    <tr><td align="center">
      <table width="560" style="max-width:560px;background:#ffffff;border-radius:12px;border:1px solid #e2e8f0;overflow:hidden;">
        <tr><td style="background:#0B2A4A;color:#fff;padding:18px 24px;">
          <div style="font-size:18px;font-weight:bold;">KARE UIS</div>
          <div style="font-size:12px;opacity:0.9;">University Information System</div>
        </td></tr>
        <tr><td style="padding:24px;">
          <h1 style="margin:0 0 12px;font-size:18px;color:#0B2A4A;">{title}</h1>
          {body_html}
        </td></tr>
        <tr><td style="padding:14px 24px;background:#f8fafc;color:#64748b;font-size:11px;">
          Automated message from KARE University Information System.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_email_sync(to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    settings = get_settings()
    password = (settings.smtp_password or "").replace(" ", "").strip()
    user = (settings.smtp_user or "").strip()
    if not settings.email_enabled or not user or not password:
        logger.warning("UIS email skipped (not configured): %s", subject)
        return False
    if not to_email or "@" not in to_email:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or user
    msg["To"] = to_email
    msg["Reply-To"] = user
    msg.attach(MIMEText(text_body or subject, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        used = _smtp_send_resilient(settings.smtp_host, int(settings.smtp_port or 587), user, password, [to_email], msg)
        logger.info("UIS email sent via %s: %s -> %s", used, subject, to_email)
        return True
    except Exception as exc:
        logger.exception("UIS email failed: %s", exc)
        return False


def _smtp_send_resilient(
    host: str,
    port: int,
    user: str,
    password: str,
    recipients: list[str],
    msg: MIMEMultipart,
) -> str:
    attempts: list[tuple[str, int, str]] = []
    for h, p, mode in (
        (host or "smtp.gmail.com", 465, "ssl"),
        (host or "smtp.gmail.com", port or 587, "starttls" if int(port or 587) != 465 else "ssl"),
        ("smtp.gmail.com", 587, "starttls"),
        ("smtp.gmail.com", 465, "ssl"),
    ):
        key = (h, int(p), mode)
        if key not in attempts:
            attempts.append(key)
    errors: list[str] = []
    for h, p, mode in attempts:
        try:
            _smtp_send(h, p, user, password, recipients, msg, mode=mode)
            return f"{h}:{p}/{mode}"
        except Exception as exc:
            errors.append(f"{h}:{p}/{mode} -> {exc}")
            logger.warning("UIS SMTP attempt failed (%s:%s/%s): %s", h, p, mode, exc)
    raise RuntimeError("; ".join(errors[-3:]) or "SMTP failed")


def _smtp_send(
    host: str,
    port: int,
    user: str,
    password: str,
    recipients: list[str],
    msg: MIMEMultipart,
    mode: str = "starttls",
) -> None:
    import ssl

    ctx = ssl.create_default_context()
    if mode == "ssl" or int(port) == 465:
        with smtplib.SMTP_SSL(host, int(port), context=ctx, timeout=45) as server:
            server.ehlo()
            server.login(user, password)
            server.send_message(msg, from_addr=user, to_addrs=recipients)
        return
    with smtplib.SMTP(host, int(port), timeout=45) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
        server.login(user, password)
        server.send_message(msg, from_addr=user, to_addrs=recipients)


async def send_email(to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    return await asyncio.to_thread(send_email_sync, to_email, subject, html_body, text_body)


def email_config_status() -> dict:
    settings = get_settings()
    configured = bool(settings.email_enabled and settings.smtp_user and settings.smtp_password)
    return {
        "enabled": bool(settings.email_enabled),
        "configured": configured,
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "from_email": settings.smtp_user or "",
        "from_header": settings.smtp_from or settings.smtp_user or "",
    }


def _send_test_email_sync(to_email: str) -> tuple[bool, str]:
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    settings = get_settings()
    password = (settings.smtp_password or "").replace(" ", "").strip()
    user = (settings.smtp_user or "").strip()
    if not settings.email_enabled or not user or not password:
        return False, "Email is not configured (EMAIL_ENABLED / SMTP_USER / SMTP_PASSWORD)."
    if not to_email or "@" not in to_email:
        return False, "Provide a valid recipient email address."

    html = _wrap_html(
        "Mail test successful",
        f"""
        <p style="color:#334155;font-size:14px;line-height:1.6;">
          This is a test alert from the UIS admin dashboard.
        </p>
        <p style="color:#334155;font-size:14px;line-height:1.6;">
          Outbound mailbox: <strong>{user}</strong>
        </p>
        """,
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "UIS mail test"
    msg["From"] = settings.smtp_from or user
    msg["To"] = to_email
    msg["Reply-To"] = user
    msg.attach(MIMEText("UIS mail test", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        used = _smtp_send_resilient(settings.smtp_host, int(settings.smtp_port or 587), user, password, [to_email], msg)
        return True, f"Test email sent ({used})."
    except Exception as exc:
        logger.exception("UIS test email failed: %s", exc)
        detail = str(exc)[:500]
        low = detail.lower()
        if "badcredentials" in low or "username and password not accepted" in low or "authentication unsuccessful" in low:
            detail = (
                "SMTP login rejected for this mailbox. "
                "Create a new Google App Password and update SMTP_PASSWORD in the UIS backend .env, then restart the API."
            )
        elif "connection unexpectedly closed" in low:
            detail = (
                "SMTP connection closed during login (usually invalid app password). "
                "Regenerate the Google App Password and update SMTP_PASSWORD."
            )
        return False, detail


async def send_test_email(to_email: Optional[str] = None) -> dict:
    """Send a one-off test message; returns ok + detail for admin UI."""
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    settings = get_settings()
    target = (to_email or settings.smtp_user or "").strip()
    status = email_config_status()
    ok, detail = await asyncio.to_thread(_send_test_email_sync, target)
    return {**status, "ok": ok, "to": target, "detail": detail}


async def send_leave_status_email(
    to_email: str,
    full_name: str,
    *,
    status: str,
    from_date: str,
    to_date: str,
    reason: str,
    destination: str = "",
    decided_by: str = "",
    decided_role: str = "",
) -> bool:
    name = full_name or (to_email.split("@")[0] if to_email else "Student")
    status_label = (status or "").replace("_", " ").title()
    who = decided_by or "UIS staff"
    if decided_role:
        who = f"{who} ({decided_role})"
    dest_li = f"<li>Destination: {destination}</li>" if destination else ""
    html = _wrap_html(
        f"Hostel leave {status_label.lower()}",
        f"""
        <p style="color:#334155;font-size:14px;line-height:1.6;">Hi {name},</p>
        <p style="color:#334155;font-size:14px;line-height:1.6;">
          Your hostel leave request has been <strong>{status_label}</strong> by {who}.
        </p>
        <ul style="color:#334155;font-size:14px;line-height:1.7;">
          <li>From: {from_date}</li>
          <li>To: {to_date}</li>
          <li>Reason: {reason}</li>
          {dest_li}
          <li>Status: <strong>{status_label}</strong></li>
        </ul>
        <p style="color:#334155;font-size:14px;line-height:1.6;">
          You can also see this update in KARE UIS Hostel and Campus-GPT Leave.
        </p>
        """,
    )
    return await send_email(
        to_email,
        f"Hostel leave {status_label.lower()} · KARE UIS",
        html,
        text_body=f"Leave {from_date} to {to_date} is {status}. Reason: {reason}.",
    )


async def send_uis_welcome_email(
    to_email: str,
    full_name: str,
    username: str,
    password: str,
    role: str,
) -> bool:
    """Welcome email — never embeds the password in mail (admin shares it out-of-band)."""
    settings = get_settings()
    name = full_name or username
    _ = password  # intentionally not emailed
    login_url = f"{settings.uis_frontend_url}/login"
    html = _wrap_html(
        f"Welcome to KARE UIS, {name}",
        f"""
        <p style="color:#334155;font-size:14px;line-height:1.6;">
          An account has been created for you in the University Information System.
        </p>
        <ul style="color:#334155;font-size:14px;line-height:1.7;">
          <li>Username: <strong>{username}</strong></li>
          <li>Role: <strong>{role}</strong></li>
        </ul>
        <p style="color:#334155;font-size:14px;line-height:1.6;">
          Your temporary password was shared by the administrator separately (not in this email).
          Sign in and change it immediately under Settings.
        </p>
        <p style="margin:20px 0;">
          <a href="{login_url}" style="background:#0B2A4A;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px;display:inline-block;">
            Open UIS
          </a>
        </p>
        """,
    )
    return await send_email(to_email, "Welcome to KARE University Information System", html)
