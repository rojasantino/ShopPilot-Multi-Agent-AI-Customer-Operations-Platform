"""FastAPI dependency providers (singletons are cached; tests override them)."""

import time
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents.graph import build_graph
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.repositories.knowledge import KnowledgeRepository
from app.services.cache import Cache
from app.services.embeddings import Embedder, build_embedder
from app.services.llm import LLMClient, build_llm
from app.services.rag import RagService


@lru_cache
def get_graph():
    return build_graph()


@lru_cache
def get_cache() -> Cache:
    return Cache(get_settings().redis_url)


@lru_cache
def get_llm() -> LLMClient:
    return build_llm(get_settings())


@lru_cache
def get_embedder() -> Embedder:
    return build_embedder(get_settings())


def get_rag(
    session: Session = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> RagService:
    return RagService(KnowledgeRepository(session), embedder, settings.rag_min_score)


def rate_limit(
    request: Request,
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> None:
    """Fixed-window limiter per client IP, stored in Redis."""
    ip = request.client.host if request.client else "unknown"
    count = cache.hit(f"rl:{ip}:{int(time.time() // 60)}", 60)
    if count > settings.rate_limit_per_minute:
        raise HTTPException(429, "Too many requests", headers={"Retry-After": "60"})
