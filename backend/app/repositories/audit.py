from sqlalchemy.orm import Session

from app.db.models import AuditLog


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def log(self, request_id: str, event: str, payload: dict | None = None) -> None:
        self._s.add(AuditLog(request_id=request_id, event=event, payload=payload or {}))
        self._s.flush()
