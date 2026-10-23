"""Intent agent: LLM structured output when available, deterministic rules otherwise."""

import logging
import re

from pydantic import ValidationError

from app.schemas.intent import CANONICAL_ORDER, Intent, IntentResult
from app.services.llm import LLMClient

logger = logging.getLogger(__name__)

ORDER_ID_RE = re.compile(r"\bORD-\d{4,6}\b", re.IGNORECASE)

_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.RETURN_REQUEST: (
        "return",
        "refund",
        "damaged",
        "broken",
        "defective",
        "cracked",
        "send it back",
        "money back",
        "wrong item",
    ),
    Intent.ORDER_STATUS: (
        "order",
        "track",
        "where is",
        "late",
        "delay",
        "delivery",
        "delivered",
        "shipped",
        "status",
        "arrive",
        "package",
    ),
    Intent.PRODUCT_SEARCH: (
        "do you have",
        "looking for",
        "in stock",
        "price of",
        "how much is",
        "available",
        "recommend",
        "do you sell",
        "want to buy",
    ),
    Intent.POLICY_QUESTION: (
        "policy",
        "warranty",
        "shipping cost",
        "shipping fee",
        "payment",
        "cancel",
        "how long does",
        "invoice",
        "free shipping",
    ),
}
_ACTION_PHRASES = (
    "start the return",
    "start a return",
    "start return",
    "submit",
    "initiate",
    "go ahead",
    "please return",
    "refund me",
    "i want to return",
    "i want a refund",
    "i'd like to return",
    "i would like to return",
    "money back",
    "process the return",
)
_REASONS = (
    ("damaged", ("damaged", "broken", "defective", "cracked", "faulty")),
    ("wrong_item", ("wrong item", "wrong size", "not what i ordered")),
    ("changed_mind", ("changed my mind", "don't like", "dont like", "no longer need")),
)


def classify_with_rules(message: str) -> IntentResult:
    text = message.lower()
    found = {i for i, words in _KEYWORDS.items() if any(w in text for w in words)}
    # A return question is also an "order" question only if an order is actually discussed.
    if Intent.RETURN_REQUEST in found and Intent.POLICY_QUESTION in found and "policy" not in text:
        found.discard(Intent.POLICY_QUESTION)
    if Intent.RETURN_REQUEST in found and Intent.PRODUCT_SEARCH in found:
        found.discard(Intent.PRODUCT_SEARCH)

    reason = None
    if Intent.RETURN_REQUEST in found:
        reason = next((r for r, words in _REASONS if any(w in text for w in words)), "other")

    match = ORDER_ID_RE.search(message)
    return IntentResult(
        intents=[i for i in CANONICAL_ORDER if i in found],
        order_id=match.group(0).upper() if match else None,
        wants_return_action=Intent.RETURN_REQUEST in found
        and any(p in text for p in _ACTION_PHRASES),
        return_reason=reason,
        source="rules",
    )


_SYSTEM = """You classify e-commerce customer messages. Reply with ONLY a JSON object:
{"intents": [subset of "order_status","return_request","product_search","policy_question"],
 "order_id": "ORD-1234 or null",
 "wants_return_action": true only if the customer explicitly asks to START a return/refund,
 "return_reason": "damaged"|"wrong_item"|"changed_mind"|"other"|null}
A customer may have several intents. Do not answer the customer."""


def classify(message: str, llm: LLMClient) -> IntentResult:
    if not llm.available:
        return classify_with_rules(message)
    try:
        result = IntentResult.model_validate_json(llm.complete(_SYSTEM, message, json_mode=True))
        result.intents = [i for i in CANONICAL_ORDER if i in result.intents]
        # never trust an order id the model invented: it must literally appear in the message
        found = ORDER_ID_RE.search(message)
        result.order_id = found.group(0).upper() if found else None
        result.source = "llm"
        return result
    except (ValidationError, ValueError, RuntimeError, OSError) as exc:
        logger.warning("LLM intent failed (%s); using rules", exc)
        return classify_with_rules(message)
