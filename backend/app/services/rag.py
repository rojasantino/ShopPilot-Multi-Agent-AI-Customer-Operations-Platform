"""Retrieval-augmented generation helper: embed query -> pgvector cosine search -> hits."""

from typing import Protocol

from app.repositories.knowledge import KnowledgeRepository
from app.schemas.admin import SearchHit
from app.services.embeddings import Embedder


class KnowledgeSearcher(Protocol):
    def search(self, query: str, k: int = 3) -> list[SearchHit]: ...


class RagService:
    def __init__(self, repo: KnowledgeRepository, embedder: Embedder, min_score: float) -> None:
        self._repo = repo
        self._embedder = embedder
        self._min_score = min_score

    def search(self, query: str, k: int = 3) -> list[SearchHit]:
        [vector] = self._embedder.embed([query])
        hits = self._repo.search(vector, k)
        return [h for h in hits if h.score >= self._min_score]
