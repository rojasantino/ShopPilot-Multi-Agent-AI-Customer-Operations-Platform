"""Shared LangGraph state. Reducers make parallel/sequential nodes append instead of overwrite."""

import operator
from typing import Annotated, Any, TypedDict


def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {**(left or {}), **(right or {})}


class AgentState(TypedDict, total=False):
    # input
    message: str
    customer_id: str
    # routing
    intent: dict[str, Any]
    queue: list[str]
    next_agent: str | None
    order_id: str | None
    # outputs
    results: Annotated[dict[str, Any], merge_dicts]
    evidence: Annotated[list[dict[str, str]], operator.add]
    trace: Annotated[list[str], operator.add]
    approval: dict[str, Any] | None
    ticket_id: int | None
    # response + review loop
    reply: str
    strict: bool
    retries: int
    review: dict[str, Any]
