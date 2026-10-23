"""Public API contracts (Pydantic v2)."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    customer_id: str = Field(pattern=r"^CUST-\d{3,6}$", examples=["CUST-001"])
    message: str = Field(min_length=1, max_length=1000)


class Evidence(BaseModel):
    kind: Literal["order", "eligibility", "product", "policy"]
    ref: str
    detail: str


class ApprovalInfo(BaseModel):
    id: int
    status: str
    amount: Decimal
    kind: str


class ReviewInfo(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    retries: int = 0


class ChatResponse(BaseModel):
    request_id: str
    reply: str
    intents: list[str]
    agents_run: list[str]
    evidence: list[Evidence]
    approval: ApprovalInfo | None = None
    ticket_id: int | None = None
    review: ReviewInfo
    trace: list[str]
