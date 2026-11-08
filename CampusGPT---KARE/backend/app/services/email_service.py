"""SMTP email delivery for Campus-GPT (Gmail app password supported)."""
from __future__ import annotations

import asyncio
import logging
import mimetypes
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# filename, raw bytes, optional content-type
Attachment = tuple[str, bytes, str | None]


def _wrap_html(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:Verdana,Tahoma,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px;">
    <tr><td align="center">
      <table width="560" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
        <tr><td style="background:#1E40AF;color:#fff;padding:18px 24px;">
          <div style="font-size:18px;font-weight:bold;">Campus-GPT</div>
          <div style="font-size:12px;opacity:0.9;">Kalasalingam Academy of Research and Education</div>
        </td></tr>
        <tr><td style="padding:24px;">
          <h1 style="margin:0 0 12px;font-size:18px;color:#111827;">{title}</h1>
          {body_html}
        </td></tr>
        <tr><td style="padding:14px 24px;background:#f9fafb;color:#6b7280;font-size:11px;">
          This is an automated message from Campus-GPT. Do not reply to this email.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _attach_files(msg: MIMEMultipart, attachments: list[Attachment] | None) -> None:
    for filename, data, content_type in attachments or []:
        if not filename or data is None:
            continue
        ctype = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, _, subtype = ctype.partition("/")
        if not subtype:
            maintype, subtype = "application", "octet-stream"
        part = MIMEBase(maintype, subtype)
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)


def send_email_sync(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    attachments: list[Attachment] | None = None,
) -> bool:
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    settings = get_settings()
    password = (settings.SMTP_PASSWORD or "").replace(" ", "").strip()
    user = (settings.SMTP_USER or "").strip()
    if not settings.EMAIL_ENABLED or not user or not password:
        logger.warning("Email skipped (not configured): %s -> %s", subject, to_email)
        return False
    if not to_email or "@" not in to_email:
        return False

    if attachments:
        msg = MIMEMultipart("mixed")
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(text_body or subject, "plain", "utf-8"))
        alt.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt)
        _attach_files(msg, attachments)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(text_body or subject, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or user
    msg["To"] = to_email
    msg["Reply-To"] = user

    try:
        used = _smtp_send_resilient(settings.SMTP_HOST, int(settings.SMTP_PORT or 587), user, password, [to_email], msg)
        logger.info("Email sent via %s: %s -> %s", used, subject, to_email)
        return True
    except Exception as exc:
        logger.exception("Email failed (%s -> %s): %s", subject, to_email, exc)
        return False


def _smtp_send_resilient(
    host: str,
    port: int,
    user: str,
    password: str,
    recipients: list[str],
    msg: MIMEMultipart,
) -> str:
    """Try SSL/STARTTLS ports; return the transport label that worked."""
    attempts: list[tuple[str, int, str]] = []
    # Prefer 465 SSL for Google Workspace, then configured port, then 587 STARTTLS
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
            logger.warning("SMTP attempt failed (%s:%s/%s): %s", h, p, mode, exc)
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
    """Send via SSL (465) or STARTTLS (587). Hostname must be used for TLS cert checks."""
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


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    attachments: list[Attachment] | None = None,
) -> bool:
    return await asyncio.to_thread(
        send_email_sync, to_email, subject, html_body, text_body, attachments
    )


def email_config_status() -> dict:
    settings = get_settings()
    configured = bool(settings.EMAIL_ENABLED and settings.SMTP_USER and settings.SMTP_PASSWORD)
    return {
        "enabled": bool(settings.EMAIL_ENABLED),
        "configured": configured,
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "from_email": settings.SMTP_USER or "",
        "from_header": settings.SMTP_FROM or settings.SMTP_USER or "",
    }


def _smtp_error_detail(exc: Exception) -> str:
    detail = str(exc)[:500]
    low = detail.lower()
    if "badcredentials" in low or "username and password not accepted" in low or "authentication unsuccessful" in low:
        return (
            "SMTP login rejected. Create a new Google App Password "
            "(Google Account → Security → 2-Step Verification → App passwords), "
            "update SMTP_PASSWORD in backend/.env, then restart the API."
        )
    if "connection unexpectedly closed" in low:
        return (
            "SMTP connection closed during login (usually invalid app password). "
            "Regenerate the Google App Password and update SMTP_PASSWORD."
        )
    if "certificate" in low or "ssl" in low:
        return f"SMTP TLS/SSL error: {detail}"
    return detail


def _send_composed_sync(
    to_email: str,
    subject: str,
    description: str,
    attachments: list[Attachment] | None = None,
) -> tuple[bool, str]:
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    settings = get_settings()
    password = (settings.SMTP_PASSWORD or "").replace(" ", "").strip()
    user = (settings.SMTP_USER or "").strip()
    if not settings.EMAIL_ENABLED or not user or not password:
        return False, "Email is not configured (EMAIL_ENABLED / SMTP_USER / SMTP_PASSWORD)."
    if not to_email or "@" not in to_email:
        return False, "Provide a valid recipient email address."

    desc = (description or "").strip() or "Message from Campus-GPT admin."
    subj = (subject or "").strip() or "Campus-GPT notice"
    # Escape minimal HTML from admin description (keep line breaks)
    safe = (
        desc.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    attach_note = ""
    if attachments:
        names = ", ".join(a[0] for a in attachments if a[0])
        attach_note = f'<p style="color:#6b7280;font-size:13px;">Attachments: {names}</p>'

    html = _wrap_html(
        subj,
        f"""
        <p style="color:#374151;font-size:14px;line-height:1.6;">{safe}</p>
        {attach_note}
        <p style="color:#374151;font-size:13px;line-height:1.6;margin-top:16px;">
          Sent from Campus-GPT admin · mailbox <strong>{user}</strong>
        </p>
        """,
    )

    if attachments:
        msg = MIMEMultipart("mixed")
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(desc, "plain", "utf-8"))
        alt.attach(MIMEText(html, "html", "utf-8"))
        msg.attach(alt)
        _attach_files(msg, attachments)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(desc, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

    msg["Subject"] = subj
    msg["From"] = settings.SMTP_FROM or user
    msg["To"] = to_email
    msg["Reply-To"] = user

    try:
        used = _smtp_send_resilient(
            settings.SMTP_HOST, int(settings.SMTP_PORT or 587), user, password, [to_email], msg
        )
        return True, f"Email sent ({used})."
    except Exception as exc:
        logger.exception("Composed email failed: %s", exc)
        return False, _smtp_error_detail(exc)


async def send_test_email(to_email: str | None = None) -> dict:
    """Send a one-off test message; returns ok + detail for admin UI."""
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    settings = get_settings()
    target = (to_email or settings.SMTP_USER or "").strip()
    status = email_config_status()
    ok, detail = await asyncio.to_thread(
        _send_composed_sync,
        target,
        "Campus-GPT mail test",
        "This is a test alert from Campus-GPT admin.",
        None,
    )
    return {**status, "ok": ok, "to": target, "detail": detail}


async def send_admin_notice(
    to_email: str,
    subject: str,
    description: str,
    attachments: list[Attachment] | None = None,
) -> dict:
    """Admin-composed notice with optional document attachments."""
    status = email_config_status()
    ok, detail = await asyncio.to_thread(
        _send_composed_sync, to_email, subject, description, attachments
    )
    return {
        **status,
        "ok": ok,
        "to": to_email,
        "subject": subject,
        "detail": detail,
        "attachments": [a[0] for a in (attachments or [])],
    }

async def send_welcome_email(to_email: str, full_name: str, role: str = "student") -> bool:
    settings = get_settings()
    name = full_name or to_email.split("@")[0]
    login_url = f"{settings.FRONTEND_URL}/login"
    html = _wrap_html(
        f"Welcome, {name}",
        f"""
        <p style="color:#374151;font-size:14px;line-height:1.6;">
          Your Campus-GPT account is ready. You are registered as <strong>{role}</strong>.
        </p>
        <p style="color:#374151;font-size:14px;line-height:1.6;">
          Sign in to chat with campus assistants, check academics, manage leave, and more.
        </p>
        <p style="margin:20px 0;">
          <a href="{login_url}" style="background:#1E40AF;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px;display:inline-block;">
            Open Campus-GPT
          </a>
        </p>
        """,
    )
    return await send_email(to_email, "Welcome to Campus-GPT · KARE", html)


async def send_password_reset_email(to_email: str, full_name: str, reset_token: str) -> bool:
    settings = get_settings()
    name = full_name or to_email.split("@")[0]
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    html = _wrap_html(
        "Reset your password",
        f"""
        <p style="color:#374151;font-size:14px;line-height:1.6;">Hi {name},</p>
        <p style="color:#374151;font-size:14px;line-height:1.6;">
          We received a request to reset your Campus-GPT password. This link expires in 1 hour.
        </p>
        <p style="margin:20px 0;">
          <a href="{reset_url}" style="background:#1E40AF;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px;display:inline-block;">
            Reset password
          </a>
        </p>
        <p style="color:#6b7280;font-size:12px;">If you did not request this, you can ignore this email.</p>
        """,
    )
    return await send_email(to_email, "Campus-GPT password reset", html)


async def send_password_changed_email(to_email: str, full_name: str) -> bool:
    name = full_name or to_email.split("@")[0]
    html = _wrap_html(
        "Password updated",
        f"""
        <p style="color:#374151;font-size:14px;line-height:1.6;">Hi {name},</p>
        <p style="color:#374151;font-size:14px;line-height:1.6;">
          Your Campus-GPT password was changed successfully. If this wasn't you, contact campus support immediately.
        </p>
        """,
    )
    return await send_email(to_email, "Your Campus-GPT password was changed", html)


async def send_login_activity_email(to_email: str, full_name: str) -> bool:
    name = full_name or to_email.split("@")[0]
    html = _wrap_html(
        "New sign-in",
        f"""
        <p style="color:#374151;font-size:14px;line-height:1.6;">Hi {name},</p>
        <p style="color:#374151;font-size:14px;line-height:1.6;">
          There was a successful sign-in to your Campus-GPT account. If this wasn't you, reset your password right away.
        </p>
        """,
    )
    return await send_email(to_email, "Campus-GPT sign-in activity", html)


async def send_leave_applied_email(
    to_email: str,
    full_name: str,
    from_date: str,
    to_date: str,
    reason: str,
    destination: str = "",
) -> bool:
    name = full_name or to_email.split("@")[0]
    dest = f"<br/>Destination: {destination}" if destination else ""
    html = _wrap_html(
        "Hostel leave submitted",
        f"""
        <p style="color:#374151;font-size:14px;line-height:1.6;">Hi {name},</p>
        <p style="color:#374151;font-size:14px;line-height:1.6;">
          Your hostel leave request was submitted and is <strong>pending</strong>.
        </p>
        <ul style="color:#374151;font-size:14px;line-height:1.7;">
          <li>From: {from_date}</li>
          <li>To: {to_date}</li>
          <li>Reason: {reason}</li>
          {f"<li>Destination: {destination}</li>" if destination else ""}
        </ul>
        """,
    )
    ok = await send_email(to_email, "Hostel leave request submitted · Campus-GPT", html)
    # Also notify the system mailbox
    settings = get_settings()
    if settings.SMTP_USER and to_email.lower() != settings.SMTP_USER.lower():
        await send_email(
            settings.SMTP_USER,
            f"[Campus-GPT] Leave request from {name}",
            _wrap_html(
                "Leave application received",
                f"<p>{name} ({to_email}) applied for leave {from_date} → {to_date}. Reason: {reason}.{dest}</p>",
            ),
        )
    return ok


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
    who = decided_by or "campus staff"
    if decided_role:
        who = f"{who} ({decided_role})"
    dest_li = f"<li>Destination: {destination}</li>" if destination else ""
    html = _wrap_html(
        f"Hostel leave {status_label.lower()}",
        f"""
        <p style="color:#374151;font-size:14px;line-height:1.6;">Hi {name},</p>
        <p style="color:#374151;font-size:14px;line-height:1.6;">
          Your hostel leave request has been <strong>{status_label}</strong> by {who}.
        </p>
        <ul style="color:#374151;font-size:14px;line-height:1.7;">
          <li>From: {from_date}</li>
          <li>To: {to_date}</li>
          <li>Reason: {reason}</li>
          {dest_li}
          <li>Status: <strong>{status_label}</strong></li>
        </ul>
        """,
    )
    return await send_email(to_email, f"Hostel leave {status_label.lower()} · Campus-GPT", html)


async def send_task_created_email(to_email: str, full_name: str, title: str, due_date: str = "") -> bool:
    name = full_name or to_email.split("@")[0]
    due = f"<li>Due: {due_date}</li>" if due_date else ""
    html = _wrap_html(
        "Task created",
        f"""
        <p style="color:#374151;font-size:14px;line-height:1.6;">Hi {name},</p>
        <p style="color:#374151;font-size:14px;line-height:1.6;">A new task was added to your Campus-GPT planner:</p>
        <ul style="color:#374151;font-size:14px;line-height:1.7;">
          <li>Title: {title}</li>
          {due}
        </ul>
        """,
    )
    return await send_email(to_email, f"Task added: {title}", html)
