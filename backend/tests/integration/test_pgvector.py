"""Real pgvector tests. Run with:  TEST_DATABASE_URL=postgresql+psycopg://... pytest tests/integration"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.bootstrap import ingest_policies, init_schema
from app.repositories.knowledge import KnowledgeRepository
from app.services.embeddings import HashEmbedder
from app.services.rag import RagService

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture()
def rag_session():
    engine = create_engine(URL)
    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS knowledge_chunks CASCADE"))
    init_schema(engine)
    with sessionmaker(bind=engine)() as s:
        ingest_policies(s, HashEmbedder(), force=True)
        yield s


@pytest.mark.parametrize(
    ("query", "expected_source"),
    [
        ("how many days do I have to return an item", "returns_policy.md"),
        ("is shipping free", "shipping_policy.md"),
        ("what payment methods do you accept", "payment_and_cancellation.md"),
        ("is my headphones covered by warranty", "warranty.md"),
    ],
)
def test_top_hit_is_the_right_document(rag_session, query, expected_source):
    rag = RagService(KnowledgeRepository(rag_session), HashEmbedder(), min_score=0.0)
    hits = rag.search(query, k=1)
    assert hits and hits[0].source == expected_source


def test_embedding_dimension_and_index(rag_session):
    chunk = KnowledgeRepository(rag_session).list_chunks(1)[0]
    assert chunk.embedding_dim == 384
    idx = rag_session.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname='ix_knowledge_embedding_hnsw'")
    ).scalar()
    assert "hnsw" in idx
