"""Idempotent outbox for failed UIS writes (leave, etc.)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import SyncOutbox
from app.models.user import User
from app.services import uis_client
from app.services.agent_actions import submit_leave_to_uis


async def enqueue_sync(db: AsyncSession, *, user_id: int, kind: str, payload: dict) -> SyncOutbox:
    # Deduplicate identical pending leave jobs
    if kind == "apply_leave":
        pending = (
            await db.execute(
                select(SyncOutbox).where(
                    SyncOutbox.user_id == user_id,
                    SyncOutbox.kind == kind,
                    SyncOutbox.status == "pending",
                )
            )
        ).scalars().all()
        for row in pending:
            try:
                existing = json.loads(row.payload_json or "{}")
            except json.JSONDecodeError:
                continue
            if (
                existing.get("from_date") == payload.get("from_date")
                and existing.get("to_date") == payload.get("to_date")
                and (existing.get("reason") or "") == (payload.get("reason") or "")
            ):
                return row

    row = SyncOutbox(
        user_id=user_id,
        kind=kind,
        payload_json=json.dumps(payload),
        status="pending",
        attempts=0,
    )
    db.add(row)
    await db.flush()
    return row


async def process_outbox(db: AsyncSession, limit: int = 20) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(SyncOutbox)
            .where(SyncOutbox.status == "pending")
            .order_by(SyncOutbox.id)
            .limit(limit)
        )
    ).scalars().all()
    done = failed = 0
    for row in rows:
        row.attempts = (row.attempts or 0) + 1
        row.updated_at = datetime.utcnow()
        try:
            payload = json.loads(row.payload_json or "{}")
            if row.kind == "apply_leave":
                user_row = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
                if not user_row:
                    raise RuntimeError("user missing")
                # Skip if UIS already has a matching pending leave (avoid duplicates)
                if user_row.uis_username and uis_client.uis_enabled():
                    try:
                        hostel = await uis_client.get_hostel(user_row.uis_username)
                        for leave in hostel.get("leaves") or []:
                            if (
                                leave.get("from") == payload.get("from_date")
                                and leave.get("to") == payload.get("to_date")
                                and (leave.get("status") or "").lower() in ("pending", "approved")
                            ):
                                row.status = "done"
                                row.last_error = "skipped: matching leave already on UIS"
                                done += 1
                                raise StopIteration
                    except StopIteration:
                        continue
                    except uis_client.UisClientError:
                        pass
                fake_user = {
                    "sub": str(user_row.id),
                    "role": user_row.role.value if hasattr(user_row.role, "value") else str(user_row.role),
                }
                result = await submit_leave_to_uis(
                    db,
                    fake_user,
                    from_date=payload["from_date"],
                    to_date=payload["to_date"],
                    reason=payload.get("reason") or "Queued leave",
                    destination=payload.get("destination") or "",
                )
                if not result.get("ok"):
                    raise RuntimeError(result.get("answer") or "leave failed")
            else:
                raise RuntimeError(f"unknown kind {row.kind}")
            row.status = "done"
            row.last_error = ""
            done += 1
        except StopIteration:
            pass
        except Exception as exc:
            row.last_error = str(exc)[:500]
            if row.attempts >= 8:
                row.status = "failed"
            failed += 1
    await db.flush()
    return {"processed": len(rows), "done": done, "failed": failed, "uis_enabled": uis_client.uis_enabled()}
