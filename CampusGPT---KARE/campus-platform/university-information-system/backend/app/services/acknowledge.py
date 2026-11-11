"""Save an acknowledgement, alert the user, and email the slip."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Acknowledgement, AppNotification, User
from app.services.email_service import send_email


def _html(title: str, number: str, summary: str) -> str:
    lines = "".join(f"<li>{line}</li>" for line in summary.splitlines() if line.strip())
    delivery = "Keep this number. It is the receipt stored with the record."
    return (
        f"<p>Acknowledgement <strong>{number}</strong></p>"
        f"<ul>{lines}</ul>"
        f"<p>{delivery}</p>"
        f"<p>Open Acknowledgements in CIMS and search for this number.</p>"
    )


async def issue_acknowledgement(
    db: AsyncSession,
    *,
    user: User | None,
    kind: str,
    title: str,
    summary: str,
    email: str | None = None,
    status: str = "",
    ref_key: str = "",
    notify_kind: str = "acknowledgement",
) -> dict:
    recipient = (email or (user.email if user else "") or "").strip()
    row = None
    if ref_key:
        row = (
            await db.execute(select(Acknowledgement).where(Acknowledgement.ref_key == ref_key))
        ).scalars().first()
    if row is None:
        row = Acknowledgement(
        kind=kind[:40],
        title=title[:200],
        summary=summary,
        actor_user_id=user.id if user else None,
        recipient_email=recipient,
        email_sent=False,
        status=status[:32],
        ref_key=ref_key[:64],
        )
        db.add(row)
        await db.flush()
        row.number = f"UIS-{row.created_at:%Y%m%d}-{row.id:05d}"
    row.kind = kind[:40]
    row.title = title[:200]
    row.summary = summary
    row.status = status[:32]
    row.recipient_email = recipient
    if user is not None:
        row.actor_user_id = user.id
    if user is not None:
        db.add(
            AppNotification(
                user_id=user.id,
                kind=notify_kind[:40],
                title=title[:200],
                body=f"{row.number}. {summary[:400]}",
                link=f"/ack/{row.number}",
            )
        )
    sent = False
    if recipient:
        sent = await send_email(
            recipient,
            f"{title} · {row.number}",
            _html(title, row.number, summary),
            text_body=f"{title}\n{row.number}\n{summary}",
        )
    row.email_sent = bool(sent)
    await db.commit()
    return {
        "number": row.number,
        "title": row.title,
        "email": recipient,
        "email_sent": row.email_sent,
        "status": row.status,
        "link": f"/ack/{row.number}",
    }
