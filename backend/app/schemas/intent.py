"""Intent classification result shared by the router and the agents."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Intent(StrEnum):
    ORDER_STATUS = "order_status"
    RETURN_REQUEST = "return_request"
    PRODUCT_SEARCH = "product_search"
    POLICY_QUESTION = "policy_question"


# Agents run in this order, so e.g. the order is looked up before returns are evaluated.
CANONICAL_ORDER = [
    Intent.ORDER_STATUS,
    Intent.RETURN_REQUEST,
    Intent.PRODUCT_SEARCH,
    Intent.POLICY_QUESTION,
]

ReturnReason = Literal["damaged", "wrong_item", "changed_mind", "other"]


class IntentResult(BaseModel):
    intents: list[Intent] = Field(default_factory=list)
    order_id: str | None = None
    wants_return_action: bool = False  # True only if the customer explicitly asks to START a return
    return_reason: ReturnReason | None = None
    source: Literal["rules", "llm"] = "rules"
