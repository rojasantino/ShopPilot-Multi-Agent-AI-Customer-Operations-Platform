from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_cache
from app.db.session import get_session
from app.services.cache import Cache

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe: the process is up."""
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Session = Depends(get_session), cache: Cache = Depends(get_cache)) -> dict:
    """Readiness probe: dependencies are reachable."""
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, "database unavailable") from exc
    return {"status": "ready", "cache": cache.backend, "redis_ok": cache.ping()}
