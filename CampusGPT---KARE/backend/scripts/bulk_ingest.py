"""
Bulk ingest documents from a folder into the knowledge base.
Place PDFs, DOCX, TXT, MD, CSV files in data/documents/ and run:
  python -m scripts.bulk_ingest
"""
import asyncio
import sys
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Project root: backend/scripts/ -> backend/ -> project root
DOCUMENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents"
ALLOWED = {".pdf", ".docx", ".pptx", ".txt", ".md", ".csv"}


async def main():
    from app.config import get_settings
    from app.services.ingestion import ingest_document

    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set. Set it in .env to enable ingestion.")
        return 1

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    files = [f for f in DOCUMENTS_DIR.iterdir() if f.is_file() and f.suffix.lower() in ALLOWED]

    if not files:
        print(f"No documents found in {DOCUMENTS_DIR}")
        print(f"Add PDF, DOCX, TXT, MD, or CSV files (e.g. policies, circulars, rules) and re-run.")
        return 0

    print(f"Ingesting {len(files)} file(s) from {DOCUMENTS_DIR}...")
    ok = 0
    for f in files:
        try:
            content = f.read_bytes()
            result = await ingest_document(f.name, content)
            if result.get("status") == "completed":
                ok += 1
                print(f"  OK: {f.name} ({result.get('chunks', 0)} chunks)")
            else:
                print(f"  FAIL: {f.name} - {result.get('reason', 'unknown')}")
        except Exception as e:
            print(f"  FAIL: {f.name} - {e}")
    print(f"Done. {ok}/{len(files)} ingested successfully.")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
