"""Per-request dependencies injected into every node via LangGraph's `config["configurable"]`."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.audit import AuditRepository
from app.services.cache import Cache
from app.services.llm import LLMClient
from app.services.rag import KnowledgeSearcher


@dataclass
class AgentDeps:
    session: Session
    llm: LLMClient
    rag: KnowledgeSearcher
    cache: Cache
    settings: Settings
    request_id: str
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def audit(self, event: str, payload: dict | None = None) -> None:
        AuditRepository(self.session).log(self.request_id, event, payload)


def deps_from(config: RunnableConfig) -> AgentDeps:
    return config["configurable"]["deps"]
