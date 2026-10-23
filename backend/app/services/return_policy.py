"""Deterministic return-eligibility rules. Business rules live in code, NOT in the LLM prompt."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.db.models import Order, OrderItem


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@dataclass(frozen=True)
class ItemDecision:
    product_id: str
    name: str
    eligible: bool
    reason: str
    refund_amount: Decimal


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    items: list[ItemDecision] = field(default_factory=list)
    refundable_amount: Decimal = Decimal("0")
    days_left: int | None = None


def evaluate_return(
    order: Order, *, now: datetime, window_days: int, only_items: list[OrderItem] | None = None
) -> EligibilityDecision:
    if order.status != "delivered" or order.delivered_at is None:
        return EligibilityDecision(
            False, [f"Order is '{order.status}', not delivered yet, so it cannot be returned."]
        )

    elapsed = (_aware(now) - _aware(order.delivered_at)).days
    days_left = window_days - elapsed
    if days_left < 0:
        return EligibilityDecision(
            False,
            [f"The {window_days}-day return window closed {-days_left} day(s) ago."],
            days_left=days_left,
        )

    decisions: list[ItemDecision] = []
    for item in only_items or order.items:
        amount = item.unit_price * item.quantity
        if item.product.is_final_sale:
            decisions.append(
                ItemDecision(
                    item.product_id, item.product.name, False, "final-sale item", Decimal("0")
                )
            )
        else:
            decisions.append(
                ItemDecision(
                    item.product_id, item.product.name, True, "within return window", amount
                )
            )

    refundable = sum((d.refund_amount for d in decisions), Decimal("0"))
    eligible = any(d.eligible for d in decisions)
    reasons = [] if eligible else ["All selected items are final-sale and cannot be returned."]
    return EligibilityDecision(eligible, reasons, decisions, refundable, days_left)
