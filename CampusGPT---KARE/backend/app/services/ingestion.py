"""Document ingestion - chunk and embed. Supports PDF, DOCX, TXT, MD, CSV."""
import io
from pathlib import Path

from PyPDF2 import PdfReader
import numpy as np

from app.config import get_settings
from app.services.embeddings import get_embeddings_batch
from app.services.vector_store import get_vector_store

settings = get_settings()


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """Split text into overlapping chunks by token approximation (4 chars ~ 1 token)."""
    chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
    overlap = overlap or settings.RAG_CHUNK_OVERLAP
    char_chunk = max(200, chunk_size * 4)
    char_overlap = max(0, min(overlap * 4, char_chunk // 2))

    if not text or not text.strip():
        return []

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + char_chunk, n)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        if end >= n:
            break
        start = end - char_overlap
        if start <= 0 and end == n:
            break
        # Prevent zero-progress loops on tiny remainders
        if start >= end:
            start = end
    return chunks


def extract_text_from_pdf(file_content: bytes) -> tuple[str, list[tuple[str, int]]]:
    """Extract text from PDF bytes. Returns (full_text, [(chunk_text, page_num), ...])."""
    text_parts = []
    page_chunks: list[tuple[str, int]] = []
    try:
        reader = PdfReader(io.BytesIO(file_content))
        for i, page in enumerate(reader.pages, start=1):
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t and t.strip():
                text_parts.append(t)
                for chunk in chunk_text(t):
                    if chunk.strip():
                        page_chunks.append((chunk.strip(), i))
    except Exception:
        text_parts = []
        page_chunks = []

    # Fallback extractor for PDFs PyPDF2 struggles with
    if not text_parts:
        try:
            from pypdf import PdfReader as PdfReader2

            reader2 = PdfReader2(io.BytesIO(file_content))
            for i, page in enumerate(reader2.pages, start=1):
                t = page.extract_text() or ""
                if t.strip():
                    text_parts.append(t)
                    for chunk in chunk_text(t):
                        if chunk.strip():
                            page_chunks.append((chunk.strip(), i))
        except Exception:
            pass

    full_text = "\n\n".join(text_parts)
    return full_text, page_chunks


def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from Word DOCX bytes."""
    from docx import Document as DocxDocument
    doc = DocxDocument(io.BytesIO(file_content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_text_from_txt(file_content: bytes) -> str:
    """Extract text from plain text file."""
    return file_content.decode("utf-8", errors="replace")


def extract_text_from_pptx(file_content: bytes) -> str:
    """Extract text from PowerPoint PPTX bytes (from reference)."""
    from pptx import Presentation
    prs = Presentation(io.BytesIO(file_content))
    slides_text = []
    for i, slide in enumerate(prs.slides, start=1):
        lines = [f"Slide {i}:"]
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                lines.append(shape.text)
        slides_text.append("\n".join(lines))
    return "\n\n".join(slides_text)


def extract_text_from_csv(file_content: bytes) -> str:
    """Extract text from CSV - convert to readable format."""
    text = file_content.decode("utf-8", errors="replace")
    lines = text.split("\n")[:200]  # Limit rows
    return "\n".join(lines)


def extract_text(filename: str, file_content: bytes) -> str:
    """Extract raw text based on file type."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        full_text, _ = extract_text_from_pdf(file_content)
        return full_text
    if ext == ".docx":
        return extract_text_from_docx(file_content)
    if ext == ".pptx":
        return extract_text_from_pptx(file_content)
    if ext in (".txt", ".md"):
        return extract_text_from_txt(file_content)
    if ext == ".csv":
        return extract_text_from_csv(file_content)
    return extract_text_from_txt(file_content)


def extract_chunks_with_metadata(filename: str, file_content: bytes) -> list[dict]:
    """Extract chunked text with metadata (page numbers for PDF). Returns list of {text, page?}."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        _, page_chunks = extract_text_from_pdf(file_content)
        return [{"text": t, "page": p} for t, p in page_chunks]
    # DOCX, TXT, MD, CSV: extract text and chunk
    if ext == ".docx":
        text = extract_text_from_docx(file_content)
    elif ext == ".pptx":
        text = extract_text_from_pptx(file_content)
    elif ext in (".txt", ".md"):
        text = extract_text_from_txt(file_content)
    elif ext == ".csv":
        text = extract_text_from_csv(file_content)
    else:
        text = extract_text_from_txt(file_content)
    chunks = chunk_text(text) if text and text.strip() else []
    return [{"text": c, "page": None} for c in chunks]


async def ingest_document(filename: str, file_content: bytes, doc_id: int = None) -> dict:
    """Ingest document: extract, chunk, embed, store. Supports PDF, DOCX, TXT, MD, CSV."""
    chunks_with_meta = extract_chunks_with_metadata(filename, file_content)
    if not chunks_with_meta:
        return {
            "status": "failed",
            "reason": "No text extracted from this file. If it is a scanned PDF, export a text PDF or upload DOCX/TXT.",
            "chunks": 0,
            "filename": filename,
        }

    chunks = [c["text"] for c in chunks_with_meta]

    # Get embeddings in batches of 50 (local fallback ensures non-empty vectors)
    batch_size = 50
    all_embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        embs = await get_embeddings_batch(batch)
        if len(embs) != len(batch):
            return {
                "status": "failed",
                "reason": "Embedding step failed for some chunks",
                "chunks": 0,
                "filename": filename,
            }
        all_embeddings.extend(embs)

    # Drop empty embedding rows if any
    pairs = [(e, c) for e, c in zip(all_embeddings, chunks_with_meta) if e]
    if not pairs:
        return {"status": "failed", "reason": "Could not embed document text", "chunks": 0, "filename": filename}

    embeddings = [p[0] for p in pairs]
    chunks_with_meta = [p[1] for p in pairs]

    metadatas = [
        {
            "text": chunk["text"],
            "content": chunk["text"],
            "source": filename,
            "doc_id": doc_id,
            "chunk_id": i,
            **({"page": chunk["page"]} if chunk.get("page") is not None else {}),
        }
        for i, chunk in enumerate(chunks_with_meta)
    ]

    store = get_vector_store()
    store.add(np.array(embeddings, dtype=np.float32), metadatas)

    return {
        "status": "completed",
        "chunks": len(embeddings),
        "filename": filename,
        "doc_id": doc_id,
    }
