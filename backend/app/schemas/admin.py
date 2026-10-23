"""Contracts for approvals, orders and the vector-table explorer."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    order_id: str
    customer_id: str
    reason: str
    amount: Decimal
    status: str
    details: dict
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_note: str | None = None


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str = Field(min_length=2, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class OrderItemOut(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    id: str
    status: str
    placed_at: datetime
    expected_delivery: datetime | None
    delivered_at: datetime | None
    currency: str
    total: Decimal
    items: list[OrderItemOut]


class ChunkOut(BaseModel):
    id: int
    source: str
    chunk_index: int
    content: str
    embedding_dim: int
    embedding_preview: list[float]  # first 8 numbers of the vector


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    k: int = Field(default=3, ge=1, le=10)


class SearchHit(BaseModel):
    id: int
    source: str
    chunk_index: int
    content: str
    score: float  # cosine similarity, 1.0 = identical direction
