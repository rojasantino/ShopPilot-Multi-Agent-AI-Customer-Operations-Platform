"""Compose the customer-facing reply. Template = always-safe baseline; LLM = optional polish."""

import json
import logging

from langchain_core.runnables import RunnableConfig

from app.agents.deps import deps_from
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "I can help with order status, returns and refunds, product availability, and store policies "
    "(shipping, payment, warranty). Which of these do you need?"
)


def _order_text(o: dict) -> str:
    if not o.get("found"):
        return (
            "I couldn't find that order on your account. Please check the order ID and try again."
        )
    text = (
        f"Order {o['id']} is {o['status']} (total {float(o['total']):,.2f} {o['currency']}; "
        f"items: {', '.join(o['items'])})."
    )
    if o["status"] == "delivered":
        text += f" It was delivered on {o['delivered_at']}."
        if o.get("late_days"):
            text += (
                f" That is {o['late_days']} day(s) later than the promised date "
                f"({o['expected_delivery']}) - sorry for the delay."
            )
    elif o.get("expected_delivery"):
        text += f" Expected delivery: {o['expected_delivery']}."
    return text


def _returns_text(r: dict, intent: dict) -> str:
    if not r.get("order_found"):
        return "I couldn't find a delivered order on your account to return."
    prefix = "Sorry the item arrived damaged. " if intent.get("return_reason") == "damaged" else ""
    if not r["eligible"]:
        return (
            prefix + "Unfortunately this order isn't eligible for return: " + " ".join(r["reasons"])
        )
    scope = "the item you mentioned from order" if r["scope"] == "mentioned_item" else "order"
    text = (
        f"{prefix}Good news - {scope} {r['order_id']} can be returned "
        f"({r['days_left']} day(s) left in the return window; refundable up to "
        f"{float(r['amount']):,.2f} {r['currency']})."
    )
    skipped = [i["name"] for i in r["items"] if not i["eligible"]]
    if skipped:
        text += f" Not returnable (final sale): {', '.join(skipped)}."
    if r["approval_created"]:
        text += (
            " I've submitted a refund request for review by our support team. It is pending "
            "approval and no refund has been issued yet."
        )
    else:
        text += " If you'd like to go ahead, reply 'start the return' and I'll submit it for team approval."
    return text


def _products_text(p: dict) -> str:
    if not p["items"]:
        return "I couldn't find matching products. Could you describe what you're looking for?"
    lines = [
        f"- {i['name']}: {float(i['price']):,.0f} AED "
        f"({'in stock' if i['stock'] > 0 else 'out of stock'})"
        for i in p["items"]
    ]
    return "Here is what I found:\n" + "\n".join(lines)


def _knowledge_text(k: dict) -> str:
    if not k["hits"]:
        return "I couldn't find that in our policies. A support specialist can help with this."
    best = k["hits"][0]
    return f"{best['content']} (source: {best['source']})"


def render_template(state: AgentState) -> str:
    results, intent = state.get("results", {}), state.get("intent", {})
    parts = []
    if "order" in results:
        parts.append(_order_text(results["order"]))
    if "returns" in results:
        parts.append(_returns_text(results["returns"], intent))
    if "products" in results:
        parts.append(_products_text(results["products"]))
    if "knowledge" in results:
        parts.append(_knowledge_text(results["knowledge"]))
    return "\n\n".join(parts) or HELP_TEXT


_SYSTEM = (
    "You are a customer-support assistant. Write a short, friendly reply using ONLY the facts in "
    "the JSON. Never invent order IDs, dates or amounts. Never say a refund was issued or "
    "processed: refunds are only 'pending approval' by our team. If a refund request exists, say "
    "it is pending approval."
)


def compose_node(state: AgentState, config: RunnableConfig) -> dict:
    deps = deps_from(config)
    reply = None
    if deps.llm.available and not state.get("strict"):
        try:
            facts = {
                "customer_message": state["message"],
                "results": state.get("results", {}),
                "approval": state.get("approval"),
            }
            reply = deps.llm.complete(_SYSTEM, json.dumps(facts, default=str)).strip() or None
        except Exception as exc:  # noqa: BLE001 - any provider failure must degrade gracefully
            logger.warning("LLM compose failed (%s); using template", exc)
    mode = "llm" if reply else ("template-strict" if state.get("strict") else "template")
    return {"reply": reply or render_template(state), "trace": [f"compose ({mode})"]}
