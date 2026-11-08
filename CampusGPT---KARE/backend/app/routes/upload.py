"""Document upload and ingestion."""
import json

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ingestion import ingest_document
from app.services.supabase_storage import is_supabase_configured, upload_file
from app.utils.database import get_db
from app.utils.auth import require_admin
from app.models.document import Document

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md", ".csv"}


async def _archive_to_supabase(filename: str, content: bytes) -> dict:
    """Upload raw file to Supabase Storage when configured.

    Returns a storage dict for the API response. Never raises — failures are
    reported in the dict so document ingestion still succeeds locally.
    """
    if not is_supabase_configured():
        return {"status": "skipped", "reason": "Supabase not configured"}
    try:
        result = await upload_file(content, filename)
        if result is None:
            return {"status": "skipped", "reason": "Supabase not configured"}
        return {"status": "uploaded", **result}
    except Exception as exc:  # noqa: BLE001 - never break ingestion
        return {"status": "error", "detail": str(exc)}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Upload and ingest document into knowledge base (archived to Supabase)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    doc = Document(
        filename=file.filename,
        file_type=ext,
        file_size=len(content),
        status="processing",
        uploaded_by=user.get("sub"),
    )
    db.add(doc)
    await db.flush()

    storage = await _archive_to_supabase(file.filename, content)

    try:
        result = await ingest_document(file.filename, content, doc_id=doc.id)
        doc.status = result["status"]
        doc.chunk_count = result.get("chunks", 0)
        if storage.get("status") == "uploaded":
            doc.metadata_json = json.dumps(storage)
        await db.flush()
        return {**result, "storage": storage}
    except Exception as e:
        doc.status = "failed"
        await db.flush()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/public")
async def upload_document_public(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Legacy path — same as /upload, admin-only."""
    return await upload_document(file=file, db=db, user=user)
