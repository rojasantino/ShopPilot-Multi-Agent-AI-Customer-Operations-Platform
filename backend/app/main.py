"""FastAPI entrypoint."""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import text

from app.api.deps import get_embedder
from app.api.routes import admin, chat, health
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_ctx
from app.db.bootstrap import ingest_policies, init_schema, seed_demo_data
from app.db.session import get_engine, get_session_factory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings = get_settings()
    if settings.auto_bootstrap:
        engine = get_engine()
        if engine.dialect.name == "postgresql":
            with engine.connect() as conn:
                conn.execute(text("SELECT pg_advisory_lock(999999)"))
                try:
                    init_schema(engine)
                    with get_session_factory()() as session:
                        seeded = seed_demo_data(session)
                        chunks = ingest_policies(session, get_embedder())
                    logger.info("bootstrap done (seeded=%s, new_chunks=%s)", seeded, chunks)
                finally:
                    conn.execute(text("SELECT pg_advisory_unlock(999999)"))
                    conn.commit()
        else:
            init_schema(engine)
            with get_session_factory()() as session:
                seeded = seed_demo_data(session)
                chunks = ingest_policies(session, get_embedder())
            logger.info("bootstrap done (seeded=%s, new_chunks=%s)", seeded, chunks)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ShopPilot API",
        version="1.0.0",
        lifespan=lifespan,
        description="Multi-agent customer operations (LangGraph + FastAPI + pgvector).",
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request_id_ctx.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(admin.router)
    return app


app = create_app()
