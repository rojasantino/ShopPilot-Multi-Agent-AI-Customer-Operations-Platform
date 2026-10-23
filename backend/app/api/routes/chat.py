import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.deps import AgentDeps
from app.api.deps import get_cache, get_graph, get_llm, get_rag, rate_limit
from app.core.config import Settings, get_settings
from app.core.logging import request_id_ctx
from app.core.security import require_api_key
from app.db.models import Customer
from app.db.session import get_session
from app.schemas.chat import ApprovalInfo, ChatRequest, ChatResponse, Evidence, ReviewInfo
from app.services.cache import Cache
from app.services.llm import LLMClient
from app.services.rag import KnowledgeSearcher

AGENT_TRACE = re.compile(r"^(\w+_agent):")
logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/v1", tags=["chat"], dependencies=[Depends(require_api_key), Depends(rate_limit)]
)


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    session: Session = Depends(get_session),
    graph=Depends(get_graph),
    llm: LLMClient = Depends(get_llm),
    rag: KnowledgeSearcher = Depends(get_rag),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    if session.get(Customer, body.customer_id) is None:
        raise HTTPException(404, "Unknown customer")

    request_id = uuid.uuid4().hex[:12]
    request_id_ctx.set(request_id)
    deps = AgentDeps(
        session=session, llm=llm, rag=rag, cache=cache, settings=settings, request_id=request_id
    )
    deps.audit("chat.received", {"customer_id": body.customer_id, "chars": len(body.message)})

    try:
        state = graph.invoke(
            {"message": body.message, "customer_id": body.customer_id},
            config={"configurable": {"deps": deps}},
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("graph failed")
        raise HTTPException(500, "Could not process the request") from None

    return ChatResponse(
        request_id=request_id,
        reply=state["reply"],
        intents=state["intent"]["intents"],
        agents_run=[m.group(1) for t in state["trace"] if (m := AGENT_TRACE.match(t))],
        evidence=[Evidence(**e) for e in state.get("evidence", [])],
        approval=ApprovalInfo(**state["approval"]) if state.get("approval") else None,
        ticket_id=state.get("ticket_id"),
        review=ReviewInfo(**state["review"]),
        trace=state["trace"],
    )
