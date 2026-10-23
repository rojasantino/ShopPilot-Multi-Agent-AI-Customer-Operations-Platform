"""Unit-test fixtures: SQLite in-memory for relational data, a fake RAG for vector search."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.deps import AgentDeps
from app.agents.graph import build_graph
from app.core.config import Settings
from app.db.bootstrap import seed_demo_data
from app.db.models import Base, KnowledgeChunk
from app.schemas.admin import SearchHit
from app.services.cache import Cache
from app.services.llm import NullLLM

NON_VECTOR_TABLES = [
    t for t in Base.metadata.sorted_tables if t.name != KnowledgeChunk.__tablename__
]


class FakeRag:
    """Stands in for pgvector (SQLite has no vector type). Real retrieval is in tests/integration."""

    def search(self, query: str, k: int = 3) -> list[SearchHit]:
        return [
            SearchHit(
                id=1,
                source="returns_policy.md",
                chunk_index=0,
                content="Returns are accepted within 30 days.",
                score=0.9,
            )
        ][:k]


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine, tables=NON_VECTOR_TABLES)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        seed_demo_data(s, now=datetime.now(UTC))
        yield s


@pytest.fixture()
def settings() -> Settings:
    return Settings(llm_provider="rules", redis_url="", api_key="test-key")


@pytest.fixture()
def deps(session, settings) -> AgentDeps:
    return AgentDeps(
        session=session,
        llm=NullLLM(),
        rag=FakeRag(),
        cache=Cache(None),
        settings=settings,
        request_id="test-req",
    )


@pytest.fixture(scope="session")
def graph():
    return build_graph()


@pytest.fixture()
def run(graph, deps):
    def _run(customer_id: str, message: str) -> dict:
        return graph.invoke(
            {"message": message, "customer_id": customer_id},
            config={"configurable": {"deps": deps}},
        )

    return _run
