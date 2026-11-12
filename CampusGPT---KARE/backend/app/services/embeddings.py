"""Embedding service using Gemini, with local hash fallback for offline/demo."""
import asyncio
import hashlib
import re

import numpy as np

from app.config import get_settings

EMBED_MODEL = "models/text-embedding-004"


def _local_embedding(text: str, dim: int) -> list[float]:
    vec = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower()) or ["empty"]
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec)) or 1.0
    vec /= norm
    return vec.tolist()


async def get_embedding(text: str) -> list[float]:
    """Get embedding vector for text. Falls back to local embedding if Gemini fails."""
    settings = get_settings()
    dim = settings.EMBEDDING_DIM
    # Gemini embedding models reject oversized inputs; keep a safe char budget
    payload = (text or "")[:8000]
    if settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            result = await asyncio.wait_for(
                asyncio.to_thread(genai.embed_content, model=EMBED_MODEL, content=payload),
                timeout=4,
            )
            emb = result.get("embedding", []) if result else []
            if emb and len(emb) == dim:
                return emb
        except Exception:
            pass
    return _local_embedding(payload, dim)


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple texts; always returns one vector per text (local fallback)."""
    results: list[list[float]] = []
    for text in texts:
        results.append(await get_embedding(text))
    return results
