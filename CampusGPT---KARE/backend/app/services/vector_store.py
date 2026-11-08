"""FAISS vector store for RAG, with NumPy fallback when FAISS is unavailable."""
import json
from pathlib import Path

import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None


class FAISSVectorStore:
    """In-memory + persistent vector index with metadata."""

    def __init__(self, index_path: str = "./data/faiss_index", embedding_dim: int = 1536):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.index_path / "metadata.jsonl"
        self.vectors_path = self.index_path / "vectors.npy"
        self.embedding_dim = embedding_dim
        self.index = None
        self.vectors: np.ndarray | None = None
        self.metadata: list[dict] = []
        self._load()

    def _load(self):
        """Load existing index and metadata."""
        index_file = self.index_path / "index.faiss"
        if FAISS_AVAILABLE and index_file.exists():
            self.index = faiss.read_index(str(index_file))
            if self.metadata_path.exists():
                with open(self.metadata_path, encoding="utf-8") as f:
                    self.metadata = [json.loads(line) for line in f if line.strip()]
            return

        if self.vectors_path.exists() and self.metadata_path.exists():
            self.vectors = np.load(self.vectors_path)
            with open(self.metadata_path, encoding="utf-8") as f:
                self.metadata = [json.loads(line) for line in f if line.strip()]
            if FAISS_AVAILABLE and self.vectors is not None and len(self.vectors):
                self.index = faiss.IndexFlatL2(self.embedding_dim)
                self.index.add(np.array(self.vectors, dtype=np.float32))
            return

        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatL2(self.embedding_dim)
        else:
            self.index = None
        self.vectors = np.zeros((0, self.embedding_dim), dtype=np.float32)
        self.metadata = []

    def add(self, embeddings: np.ndarray, metadatas: list[dict]):
        """Add embeddings with metadata."""
        embeddings = np.array(embeddings, dtype=np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        if FAISS_AVAILABLE:
            if self.index is None:
                self.index = faiss.IndexFlatL2(self.embedding_dim)
            self.index.add(embeddings)
        if self.vectors is None or len(self.vectors) == 0:
            self.vectors = embeddings
        else:
            self.vectors = np.vstack([self.vectors, embeddings])
        self.metadata.extend(metadatas)
        self._save()

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[dict, float]]:
        """Search for similar chunks. Returns (metadata, distance) tuples."""
        if not self.metadata:
            return []
        query = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        if FAISS_AVAILABLE and self.index is not None and self.index.ntotal > 0:
            distances, indices = self.index.search(query, min(top_k, len(self.metadata)))
            results = []
            for i, idx in enumerate(indices[0]):
                if 0 <= idx < len(self.metadata):
                    score = 1 / (1 + float(distances[0][i]))
                    results.append((self.metadata[idx], score))
            return results

        if self.vectors is None or len(self.vectors) == 0:
            return []
        # Cosine-like via L2 on normalized vectors
        diffs = self.vectors - query
        dists = np.sum(diffs * diffs, axis=1)
        top = np.argsort(dists)[: min(top_k, len(self.metadata))]
        return [(self.metadata[int(i)], 1 / (1 + float(dists[int(i)]))) for i in top]

    def _save(self):
        """Persist index and metadata."""
        if FAISS_AVAILABLE and self.index is not None:
            faiss.write_index(self.index, str(self.index_path / "index.faiss"))
        if self.vectors is not None:
            np.save(self.vectors_path, self.vectors)
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            for m in self.metadata:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

    def count(self) -> int:
        """Return number of vectors in index."""
        if FAISS_AVAILABLE and self.index is not None:
            return int(self.index.ntotal)
        return 0 if self.vectors is None else int(len(self.vectors))

    def clear(self) -> None:
        """Wipe the index and metadata so the knowledge base can be retrained."""
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatL2(self.embedding_dim)
        else:
            self.index = None
        self.vectors = np.zeros((0, self.embedding_dim), dtype=np.float32)
        self.metadata = []
        for path in (self.index_path / "index.faiss", self.metadata_path, self.vectors_path):
            if path.exists():
                path.unlink()
        self._save()


_vector_store: FAISSVectorStore | None = None


def get_vector_store() -> FAISSVectorStore:
    """Get or create vector store instance."""
    global _vector_store
    if _vector_store is None:
        from app.config import get_settings
        settings = get_settings()
        _vector_store = FAISSVectorStore(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=settings.EMBEDDING_DIM,
        )
    return _vector_store


def reset_vector_store() -> FAISSVectorStore:
    """Clear singleton and reload a fresh empty store (used after train)."""
    global _vector_store
    store = get_vector_store()
    store.clear()
    return store
