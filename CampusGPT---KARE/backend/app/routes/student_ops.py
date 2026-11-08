"""Student workspace: tasks and hostel leave. Login required."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db
from app.utils.auth import get_current_user, require_student
from app.models.academic import StudentTask, HostelLeave
from app.models.user import User
from app.services import academic_service as acad
from app.services import email_service as mail
from app.services import uis_client
from app.services.uis_link import linked_uis_username
from app.services.agent_actions import submit_leave_to_uis
from app.services.sync_queue import enqueue_sync

router = APIRouter()


class TaskIn(BaseModel):
    title: str
    notes: str = ""
    due_date: str = ""
    category: str = "academic"


class TaskStatusIn(BaseModel):
    status: str


class LeaveIn(BaseModel):
    from_date: str
    to_date: str
    reason: str
    destination: str = ""


async def _student(db, user):
    student, _ = await acad.resolve_student(db, user)
    if not student:
        raise HTTPException(status_code=404, detail="No academic profile linked to this login.")
    return student


async def _user_row(db, user_dict) -> User | None:
    if not str(user_dict.get("sub", "")).isdigit():
        return None
    return (await db.execute(select(User).where(User.id == int(user_dict["sub"])))).scalar_one_or_none()


def _normalize_uis_leaves(payload: dict) -> list[dict]:
    leaves = []
    for i, r in enumerate(payload.get("leaves") or []):
        leaves.append(
            {
                "id": r.get("id") or -(i + 1),
                "from_date": r.get("from") or r.get("from_date") or "",
                "to_date": r.get("to") or r.get("to_date") or "",
                "reason": r.get("reason") or "",
                "destination": r.get("destination") or "",
                "status": r.get("status") or "pending",
                "source": r.get("source") or "uis",
            }
        )
    return leaves


@router.get("/me/tasks")
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    uid = int(user["sub"])
    rows = (await db.execute(select(StudentTask).where(StudentTask.user_id == uid).order_by(StudentTask.due_date))).scalars().all()
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "notes": t.notes,
                "due_date": t.due_date,
                "status": t.status,
                "category": t.category,
            }
            for t in rows
        ]
    }


@router.post("/me/tasks")
async def create_task(
    data: TaskIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    if not data.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    task = StudentTask(
        user_id=int(user["sub"]),
        title=data.title.strip(),
        notes=data.notes.strip(),
        due_date=data.due_date,
        category=data.category,
        status="open",
    )
    db.add(task)
    await db.flush()
    u = await _user_row(db, user)
    if u:
        background_tasks.add_task(
            mail.send_task_created_email, u.email, u.full_name or "", task.title, task.due_date or ""
        )
    return {"ok": True, "id": task.id}


@router.post("/me/tasks/{task_id}/status")
async def update_task_status(
    task_id: int,
    data: TaskStatusIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    if data.status not in ("open", "done"):
        raise HTTPException(status_code=400, detail="Status must be open or done")
    uid = int(user["sub"])
    task = (await db.execute(select(StudentTask).where(StudentTask.id == task_id, StudentTask.user_id == uid))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = data.status
    return {"ok": True}


@router.delete("/me/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    uid = int(user["sub"])
    result = await db.execute(sql_delete(StudentTask).where(StudentTask.id == task_id, StudentTask.user_id == uid))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}


@router.get("/me/leaves")
async def list_leaves(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    uis_user = await linked_uis_username(db, user)
    if uis_user and uis_client.uis_enabled():
        try:
            payload = await uis_client.get_hostel(uis_user)
            return {
                "leaves": _normalize_uis_leaves(payload),
                "allocation": payload.get("allocation") or payload.get("room") or None,
                "source": "UIS",
            }
        except uis_client.UisClientError:
            pass

    student = await _student(db, user)
    rows = (
        await db.execute(
            select(HostelLeave).where(HostelLeave.student_id == student.id).order_by(HostelLeave.from_date.desc())
        )
    ).scalars().all()
    return {
        "leaves": [
            {
                "id": r.id,
                "from_date": r.from_date,
                "to_date": r.to_date,
                "reason": r.reason,
                "destination": r.destination,
                "status": r.status,
                "source": "local",
            }
            for r in rows
        ],
        "allocation": None,
        "source": "local",
    }


@router.post("/me/leaves")
async def apply_leave(
    data: LeaveIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_student),
):
    if not data.from_date or not data.to_date or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Dates and reason are required")
    from app.services import consent as consents

    if not str(user.get("sub", "")).isdigit() or not await consents.is_allowed(
        db, int(user["sub"]), "hostel.leave"
    ):
        raise HTTPException(status_code=403, detail="Hostel leave consent is off")

    u = await _user_row(db, user)
    result = await submit_leave_to_uis(
        db,
        user,
        from_date=data.from_date,
        to_date=data.to_date,
        reason=data.reason.strip(),
        destination=data.destination.strip(),
    )
    if result.get("ok"):
        leave_payload = result.get("leave") or {}
        if u and u.email:
            background_tasks.add_task(
                mail.send_leave_applied_email,
                u.email,
                u.full_name or "",
                data.from_date,
                data.to_date,
                data.reason.strip(),
                data.destination.strip() or "",
            )
        return {
            "ok": True,
            "id": leave_payload.get("id"),
            "status": leave_payload.get("status") or "pending",
            "source": "UIS",
            "message": "Leave sent to KARE UIS — visible to student, faculty, and hostel warden.",
        }

    # Queue retry when UIS is temporarily down
    if result.get("retryable") and u:
        await enqueue_sync(
            db,
            user_id=u.id,
            kind="apply_leave",
            payload={
                "from_date": data.from_date,
                "to_date": data.to_date,
                "reason": data.reason.strip(),
                "destination": data.destination.strip(),
            },
        )

    detail = result.get("answer") or "Could not submit leave"
    # Still allow local save only if no UIS link at all
    uis_user = await linked_uis_username(db, user)
    if uis_user and uis_client.uis_enabled() and not result.get("retryable"):
        raise HTTPException(status_code=400, detail=detail)

    try:
        student = await _student(db, user)
    except HTTPException:
        raise HTTPException(status_code=400, detail=detail) from None

    leave = HostelLeave(
        student_id=student.id,
        from_date=data.from_date,
        to_date=data.to_date,
        reason=data.reason.strip(),
        destination=data.destination.strip(),
        status="pending",
    )
    db.add(leave)
    await db.flush()
    if u and u.email:
        background_tasks.add_task(
            mail.send_leave_applied_email,
            u.email,
            u.full_name or "",
            leave.from_date,
            leave.to_date,
            leave.reason,
            leave.destination or "",
        )
    return {
        "ok": True,
        "id": leave.id,
        "status": leave.status,
        "source": "local",
        "queued": bool(result.get("retryable")),
        "message": (
            "UIS was unreachable — leave queued for retry and saved locally."
            if result.get("retryable")
            else detail
        ),
    }


@router.get("/me/calendar")
async def my_calendar(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    events = await acad.get_calendar(db)
    items = [
        {
            "kind": "academic",
            "title": e["title"],
            "date": e["start_date"],
            "end_date": e["end_date"],
            "event_type": e["event_type"],
            "description": e["description"],
            "recurrence": e.get("recurrence") or "",
        }
        for e in events
    ]
    if user.get("role") == "student" and str(user.get("sub", "")).isdigit():
        uid = int(user["sub"])
        tasks = (
            await db.execute(select(StudentTask).where(StudentTask.user_id == uid, StudentTask.status == "open"))
        ).scalars().all()
        for t in tasks:
            items.append(
                {
                    "kind": "task",
                    "title": t.title,
                    "date": t.due_date,
                    "end_date": "",
                    "event_type": t.category,
                    "description": t.notes,
                }
            )
        u = await _user_row(db, user)
        leave_items: list[dict] = []
        if u and u.uis_username and uis_client.uis_enabled():
            try:
                leave_items = _normalize_uis_leaves(await uis_client.get_hostel(u.uis_username))
            except uis_client.UisClientError:
                leave_items = []
        if not leave_items:
            student, _ = await acad.resolve_student(db, user)
            if student:
                leaves = (
                    await db.execute(select(HostelLeave).where(HostelLeave.student_id == student.id))
                ).scalars().all()
                leave_items = [
                    {
                        "from_date": lv.from_date,
                        "to_date": lv.to_date,
                        "status": lv.status,
                        "reason": lv.reason,
                    }
                    for lv in leaves
                ]
        for lv in leave_items:
            items.append(
                {
                    "kind": "leave",
                    "title": f"Hostel leave ({lv.get('status')})",
                    "date": lv.get("from_date") or "",
                    "end_date": lv.get("to_date") or "",
                    "event_type": lv.get("status") or "",
                    "description": lv.get("reason") or "",
                }
            )
    items.sort(key=lambda x: x.get("date") or "9999")
    return {"items": items}
