"""Approvals queue, customer orders and the vector-table explorer."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_embedder, rate_limit
from app.core.config import Settings, get_settings
from app.core.security import require_api_key
from app.db.session import get_session
from app.repositories.approvals import ApprovalRepository
from app.repositories.audit import AuditRepository
from app.repositories.knowledge import KnowledgeRepository
from app.repositories.orders import OrderRepository
from app.schemas.admin import (
    ApprovalOut,
    ChunkOut,
    DecisionIn,
    OrderItemOut,
    OrderOut,
    SearchHit,
    SearchIn,
)
from app.services.embeddings import Embedder

router = APIRouter(
    prefix="/v1", tags=["admin"], dependencies=[Depends(require_api_key), Depends(rate_limit)]
)


@router.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(
    status: str | None = Query(None, pattern="^(pending|approved|rejected)$"),
    session: Session = Depends(get_session),
):
    return ApprovalRepository(session).list(status)


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalOut)
def decide(approval_id: int, body: DecisionIn, session: Session = Depends(get_session)):
    repo = ApprovalRepository(session)
    row = repo.get(approval_id)
    if row is None:
        raise HTTPException(404, "Approval not found")
    if row.status != "pending":
        raise HTTPException(409, f"Already {row.status}")
    repo.decide(row, decision=body.decision, decided_by=body.decided_by, note=body.note)
    AuditRepository(session).log(
        "human", f"approval.{body.decision}", {"approval_id": row.id, "by": body.decided_by}
    )
    session.commit()
    return row


@router.get("/customers/{customer_id}/orders", response_model=list[OrderOut])
def customer_orders(customer_id: str, session: Session = Depends(get_session)):
    return [
        OrderOut(
            id=o.id,
            status=o.status,
            placed_at=o.placed_at,
            expected_delivery=o.expected_delivery,
            delivered_at=o.delivered_at,
            currency=o.currency,
            total=o.total,
            items=[
                OrderItemOut(
                    product_id=i.product_id,
                    name=i.product.name,
                    quantity=i.quantity,
                    unit_price=i.unit_price,
                )
                for i in o.items
            ],
        )
        for o in OrderRepository(session).list_for_customer(customer_id)
    ]


@router.get("/admin/knowledge", response_model=list[ChunkOut])
def knowledge_rows(limit: int = Query(50, ge=1, le=200), session: Session = Depends(get_session)):
    """Shows what the vector table really contains (text + first numbers of each embedding)."""
    return KnowledgeRepository(session).list_chunks(limit)


@router.post("/admin/knowledge/search", response_model=list[SearchHit])
def knowledge_search(
    body: SearchIn,
    session: Session = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
):
    [vector] = embedder.embed([body.query])
    return KnowledgeRepository(session).search(vector, body.k)
