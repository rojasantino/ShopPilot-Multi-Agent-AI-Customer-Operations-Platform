"""All pgvector access is isolated here (swap this class to change vector store)."""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeChunk
from app.schemas.admin import ChunkOut, SearchHit


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def count(self) -> int:
        return self._s.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0

    def replace_source(self, source: str, contents: list[str], vectors: list[list[float]]) -> int:
        self._s.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source == source))
        for i, (text, vec) in enumerate(zip(contents, vectors, strict=True)):
            self._s.add(KnowledgeChunk(source=source, chunk_index=i, content=text, embedding=vec))
        self._s.flush()
        return len(contents)

    def search(self, query_vector: list[float], k: int) -> list[SearchHit]:
        # `<=>` is pgvector's cosine DISTANCE operator; similarity = 1 - distance.
        distance = KnowledgeChunk.embedding.cosine_distance(query_vector).label("distance")
        rows = self._s.execute(select(KnowledgeChunk, distance).order_by(distance).limit(k)).all()
        return [
            SearchHit(
                id=c.id,
                source=c.source,
                chunk_index=c.chunk_index,
                content=c.content,
                score=round(1.0 - float(d), 4),
            )
            for c, d in rows
        ]

    def list_chunks(self, limit: int = 50) -> list[ChunkOut]:
        rows = self._s.scalars(
            select(KnowledgeChunk)
            .order_by(KnowledgeChunk.source, KnowledgeChunk.chunk_index)
            .limit(limit)
        )
        return [
            ChunkOut(
                id=r.id,
                source=r.source,
                chunk_index=r.chunk_index,
                content=r.content,
                embedding_dim=len(r.embedding),
                embedding_preview=[round(float(x), 4) for x in r.embedding[:8]],
            )
            for r in rows
        ]
