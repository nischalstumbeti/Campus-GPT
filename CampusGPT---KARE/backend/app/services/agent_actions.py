"""Agentic actions the Campus-GPT assistant can perform (leave apply, etc.)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import uis_client
from app.services.uis_link import linked_uis_username


_DATE_PATTERNS = [
    re.compile(
        r"(?:from|between)\s+(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?:to|until|-|and)\s+(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        re.I,
    ),
    re.compile(
        r"(\d{4}-\d{2}-\d{2})\s*(?:to|-|until)\s*(\d{4}-\d{2}-\d{2})",
        re.I,
    ),
]

_REASON_PATTERNS = [
    re.compile(r"(?:with\s+the\s+reason|reason)\s*[:\-]?\s*(.+)$", re.I | re.S),
    re.compile(r"(?:because|due to)\s+(.+)$", re.I | re.S),
    re.compile(r"(?:for the reason)\s*[:\-]?\s*(.+)$", re.I | re.S),
]


def _normalize_date(raw: str) -> Optional[str]:
    raw = (raw or "").strip().replace("/", "-")
    # Prefer day-first (India) over US month-first for ambiguous values
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _relative_dates(text: str) -> tuple[Optional[str], Optional[str]]:
    low = text.lower()
    today = date.today()
    if "day after tomorrow" in low:
        d = today + timedelta(days=2)
        return d.isoformat(), d.isoformat()
    if "tomorrow" in low:
        d = today + timedelta(days=1)
        return d.isoformat(), d.isoformat()
    if "today" in low and "leave" in low:
        return today.isoformat(), today.isoformat()
    if "this weekend" in low or "weekend" in low:
        # next Saturday–Sunday
        days_ahead = (5 - today.weekday()) % 7
        sat = today + timedelta(days=days_ahead or 7)
        return sat.isoformat(), (sat + timedelta(days=1)).isoformat()
    return None, None


def parse_leave_request(message: str, *, allow_defaults: bool = False) -> Optional[dict[str, str]]:
    text = (message or "").strip()
    low = text.lower()
    # Status / history questions must NOT become apply-leave proposals
    if any(
        k in low
        for k in (
            "leave status",
            "my leave",
            "hostel leave status",
            "show leave",
            "list leave",
            "pending leave",
            "leave history",
        )
    ) and not any(k in low for k in ("apply", "submit", "request leave", "apply for")):
        return None
    apply_intent = any(
        k in low
        for k in (
            "apply leave",
            "apply for leave",
            "apply for a leave",
            "apply for hostel leave",
            "submit leave",
            "request leave",
            "request a leave",
        )
    ) or (("leave" in low) and ("apply" in low or "submit" in low or "request" in low))
    if not apply_intent:
        return None

    from_date = to_date = None
    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if m:
            from_date = _normalize_date(m.group(1))
            to_date = _normalize_date(m.group(2))
            break
    if not from_date or not to_date:
        from_date, to_date = _relative_dates(text)
    if not from_date or not to_date:
        # Never invent dates — ask the student (confirmation chips may pre-fill later)
        return {
            "from_date": "",
            "to_date": "",
            "reason": "Leave requested via Campus-GPT assistant",
            "destination": "",
            "needs_dates": "true",
        }

    if not from_date or not to_date:
        return None

    # Prefer DD-MM-YYYY for ambiguous numeric dates (India campus)
    # (already attempted before %m-%d-%Y in _normalize_date)

    reason = "Leave requested via Campus-GPT assistant"
    for pat in _REASON_PATTERNS:
        m = pat.search(text)
        if m:
            reason = re.sub(r"\s+", " ", m.group(1)).strip(" .")[:255]
            break

    destination = ""
    dest_m = re.search(r"(?:destination|to go to|going to)\s*[:\-]?\s*([A-Za-z][\w\s,]{1,60})", text, re.I)
    if dest_m:
        destination = dest_m.group(1).strip()[:120]

    return {
        "from_date": from_date,
        "to_date": to_date,
        "reason": reason or "Leave requested via Campus-GPT assistant",
        "destination": destination,
    }


async def submit_leave_to_uis(
    db: AsyncSession,
    user: dict,
    *,
    from_date: str,
    to_date: str,
    reason: str,
    destination: str = "",
) -> dict[str, Any]:
    """Shared submit used by chat confirm + REST leave page."""
    if (user.get("role") or "") != "student":
        return {"ok": False, "answer": "Leave application is available for student accounts."}

    uis_user = await linked_uis_username(db, user)
    if not uis_user or not uis_client.uis_enabled():
        return {
            "ok": False,
            "answer": "Your Campus-GPT login is not linked to UIS yet. Open Settings, or sign in with your UIS username, then try again.",
        }

    try:
        created = await uis_client.create_leave(
            uis_user,
            from_date=from_date,
            to_date=to_date,
            reason=reason,
            destination=destination or "",
        )
    except uis_client.UisConsentDenied:
        return {
            "ok": False,
            "answer": "Hostel leave consent is denied in UIS. Enable hostel leave on the Consent page, then try again.",
        }
    except uis_client.UisClientError as exc:
        return {
            "ok": False,
            "answer": f"Could not submit leave to UIS ({exc.detail or exc}).",
            "error": str(exc.detail or exc),
            "retryable": True,
            "payload": {
                "action": "apply_leave",
                "from_date": from_date,
                "to_date": to_date,
                "reason": reason,
                "destination": destination,
            },
        }

    leave = created.get("leave") or {}
    status = leave.get("status") or "pending"
    dest_line = f"\nDestination: {destination}" if destination else ""
    answer = (
        f"Leave request submitted in KARE UIS.\n"
        f"From: {from_date}\n"
        f"To: {to_date}\n"
        f"Reason: {reason}{dest_line}\n"
        f"Status: {status}\n"
        f"Faculty and the hostel warden can approve or reject it."
    )
    return {
        "ok": True,
        "answer": answer,
        "leave": leave,
        "source": "UIS",
        "data_used": [
            {
                "data": "Hostel leave",
                "purpose": "Apply leave via assistant",
                "source": "UIS",
                "permission": "hostel.leave",
                "access": "Authorized",
            }
        ],
    }


async def try_apply_leave(
    db: AsyncSession,
    user: Optional[dict],
    message: str,
) -> Optional[dict[str, Any]]:
    """Propose leave apply for confirmation (does not submit until confirmed)."""
    parsed = parse_leave_request(message, allow_defaults=True)
    if not parsed:
        return None
    if not user or not str(user.get("sub", "")).isdigit():
        return {
            "handled": True,
            "ok": False,
            "answer": "Please sign in as a student before I can apply leave for you.",
        }
    if (user.get("role") or "") != "student":
        return {
            "handled": True,
            "ok": False,
            "answer": "Leave application is available for student accounts. Faculty and warden can approve leave in UIS.",
        }
    from app.services import consent as consents

    uid = int(user["sub"])
    if not await consents.is_allowed(db, uid, "hostel.leave"):
        return {
            "handled": True,
            "ok": False,
            "answer": "Hostel leave consent is off. Enable hostel leave in Privacy / Consent, then ask again.",
        }

    if parsed.get("needs_dates") == "true" or not parsed.get("from_date") or not parsed.get("to_date"):
        return {
            "handled": True,
            "ok": False,
            "answer": (
                "I can apply for hostel leave. Please include the dates, for example:\n"
                '"Apply for leave from 2026-11-01 to 2026-11-03 with reason medical checkup"'
            ),
        }

    dest_line = f"\nDestination: {parsed['destination']}" if parsed["destination"] else ""
    return {
        "handled": True,
        "ok": True,
        "needs_confirmation": True,
        "answer": (
            "I can submit this hostel leave to KARE UIS. Please confirm:\n"
            f"From: {parsed['from_date']}\n"
            f"To: {parsed['to_date']}\n"
            f"Reason: {parsed['reason']}{dest_line}\n\n"
            "Tap Confirm to send it to the warden and faculty."
        ),
        "pending_action": {
            "type": "apply_leave",
            "payload": {
                "from_date": parsed["from_date"],
                "to_date": parsed["to_date"],
                "reason": parsed["reason"],
                "destination": parsed.get("destination") or "",
            },
        },
        "data_used": [],
    }
