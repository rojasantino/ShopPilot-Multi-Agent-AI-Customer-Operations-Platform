"""Specialist agents (graph nodes). Each node: read state -> call tools -> return a state patch."""

from decimal import Decimal

from langchain_core.runnables import RunnableConfig

from app.agents.deps import AgentDeps, deps_from
from app.agents.intent import classify
from app.agents.state import AgentState
from app.db.models import Order
from app.repositories.approvals import ApprovalRepository
from app.repositories.orders import OrderRepository
from app.repositories.products import ProductRepository, extract_keywords
from app.schemas.intent import Intent, IntentResult
from app.services.return_policy import evaluate_return


def _money(value: Decimal, currency: str = "AED") -> str:
    return f"{value:,.2f} {currency}"


def resolve_order(deps: AgentDeps, state: AgentState) -> Order | None:
    """Explicit order id wins; otherwise the customer's latest (delivered one for returns)."""
    repo = OrderRepository(deps.session)
    customer_id = state["customer_id"]
    if state.get("order_id"):
        return repo.get_for_customer(state["order_id"], customer_id)
    intent = IntentResult(**state["intent"])
    return repo.latest_for_customer(
        customer_id, delivered_only=Intent.RETURN_REQUEST in intent.intents
    )


# ----------------------------------------------------------------- classify + supervisor
def classify_node(state: AgentState, config: RunnableConfig) -> dict:
    deps = deps_from(config)
    result = classify(state["message"], deps.llm)
    deps.audit("intent.classified", result.model_dump(mode="json"))
    return {
        "intent": result.model_dump(mode="json"),
        "queue": [i.value for i in result.intents],
        "order_id": result.order_id,
        "retries": 0,
        "strict": False,
        "trace": [f"classify -> {[i.value for i in result.intents] or 'none'} ({result.source})"],
    }


def supervisor_node(state: AgentState) -> dict:
    """Pops the next agent from the queue. Pure Python: routing is deterministic and testable."""
    queue = list(state.get("queue", []))
    nxt = queue.pop(0) if queue else None
    return {"next_agent": nxt, "queue": queue, "trace": [f"supervisor -> {nxt or 'compose'}"]}


# ----------------------------------------------------------------- order agent
def order_node(state: AgentState, config: RunnableConfig) -> dict:
    deps = deps_from(config)
    order = resolve_order(deps, state)
    if order is None:
        deps.audit("agent.order", {"found": False})
        return {
            "results": {"order": {"found": False, "asked_for": state.get("order_id")}},
            "trace": ["order_agent: order not found for this customer"],
        }

    late_days = None
    if (
        order.expected_delivery
        and order.delivered_at
        and order.delivered_at > order.expected_delivery
    ):
        late_days = (order.delivered_at - order.expected_delivery).days
    data = {
        "found": True,
        "id": order.id,
        "status": order.status,
        "currency": order.currency,
        "total": str(order.total),
        "placed_at": order.placed_at.date().isoformat(),
        "expected_delivery": order.expected_delivery.date().isoformat()
        if order.expected_delivery
        else None,
        "delivered_at": order.delivered_at.date().isoformat() if order.delivered_at else None,
        "late_days": late_days,
        "items": [f"{i.quantity} x {i.product.name}" for i in order.items],
    }
    deps.audit("agent.order", {"order_id": order.id, "status": order.status})
    return {
        "order_id": order.id,
        "results": {"order": data},
        "evidence": [
            {
                "kind": "order",
                "ref": order.id,
                "detail": f"status={order.status}, total={_money(order.total, order.currency)}",
            }
        ],
        "trace": [f"order_agent: loaded {order.id} ({order.status})"],
    }


# ----------------------------------------------------------------- product agent
def product_node(state: AgentState, config: RunnableConfig) -> dict:
    deps = deps_from(config)
    keywords = extract_keywords(state["message"])
    key = "products:" + ",".join(sorted(keywords))
    cached = deps.cache.get_json(key)  # Redis: product search is safe to cache briefly
    source = "cache"
    if cached is None:
        rows = ProductRepository(deps.session).search(keywords)
        cached = [
            {"id": p.id, "name": p.name, "price": str(p.price), "stock": p.stock} for p in rows
        ]
        deps.cache.set_json(key, cached, deps.settings.cache_ttl_seconds)
        source = "db"
    deps.audit("agent.product", {"keywords": keywords, "hits": len(cached), "source": source})
    return {
        "results": {"products": {"items": cached, "keywords": keywords}},
        "evidence": [
            {
                "kind": "product",
                "ref": p["id"],
                "detail": f"{p['name']} - {p['price']} AED, stock={p['stock']}",
            }
            for p in cached
        ],
        "trace": [f"product_agent: {len(cached)} match(es) via {source}"],
    }


# ----------------------------------------------------------------- returns agent
def returns_node(state: AgentState, config: RunnableConfig) -> dict:
    deps = deps_from(config)
    intent = IntentResult(**state["intent"])
    order = resolve_order(deps, state)
    if order is None:
        return {
            "results": {"returns": {"order_found": False}},
            "trace": ["returns_agent: no returnable order found"],
        }

    # Optional: narrow to a product the customer mentioned ("the earbuds were damaged").
    msg = state["message"].lower()
    mentioned = [
        i
        for i in order.items
        if any(w in msg for w in i.product.name.lower().split() if len(w) > 4)
    ]
    decision = evaluate_return(
        order,
        now=deps.now(),
        window_days=deps.settings.return_window_days,
        only_items=mentioned or None,
    )

    policy_hits = deps.rag.search("return policy damaged items refund window", k=1)
    evidence = [
        {
            "kind": "eligibility",
            "ref": order.id,
            "detail": f"eligible={decision.eligible}, days_left={decision.days_left}",
        }
    ]
    evidence += [
        {"kind": "policy", "ref": f"{h.source}#{h.chunk_index}", "detail": h.content[:160]}
        for h in policy_hits
    ]

    result = {
        "order_found": True,
        "order_id": order.id,
        "eligible": decision.eligible,
        "reasons": decision.reasons,
        "days_left": decision.days_left,
        "amount": str(decision.refundable_amount),
        "currency": order.currency,
        "items": [
            {"name": d.name, "eligible": d.eligible, "reason": d.reason} for d in decision.items
        ],
        "scope": "mentioned_item" if mentioned else "whole_order",
        "action_requested": intent.wants_return_action,
        "approval_created": False,
    }
    patch: dict = {"order_id": order.id, "results": {"returns": result}, "evidence": evidence}

    # SIDE EFFECT GATE: only create an approval when eligible AND the customer asked to start it.
    if decision.eligible and intent.wants_return_action:
        row, created = ApprovalRepository(deps.session).create_refund_request(
            order_id=order.id,
            customer_id=state["customer_id"],
            reason=intent.return_reason or "other",
            amount=decision.refundable_amount,
            details={
                "scope": result["scope"],
                "items": result["items"],
                "note": "Customer did not specify an item" if not mentioned else "",
            },
        )
        result["approval_created"] = True
        patch["approval"] = {
            "id": row.id,
            "status": row.status,
            "amount": str(row.amount),
            "kind": row.kind,
        }
        deps.audit("approval.created" if created else "approval.reused", {"approval_id": row.id})
    deps.audit("agent.returns", {"order_id": order.id, "eligible": decision.eligible})
    patch["trace"] = [
        f"returns_agent: eligible={decision.eligible}, approval={patch.get('approval', {}).get('id')}"
    ]
    return patch


# ----------------------------------------------------------------- knowledge (RAG) agent
def knowledge_node(state: AgentState, config: RunnableConfig) -> dict:
    deps = deps_from(config)
    hits = deps.rag.search(state["message"], k=3)
    deps.audit(
        "agent.knowledge",
        {"hits": [{"ref": f"{h.source}#{h.chunk_index}", "score": h.score} for h in hits]},
    )
    return {
        "results": {"knowledge": {"hits": [h.model_dump() for h in hits]}},
        "evidence": [
            {
                "kind": "policy",
                "ref": f"{h.source}#{h.chunk_index}",
                "detail": f"score={h.score}: {h.content[:160]}",
            }
            for h in hits
        ],
        "trace": [f"knowledge_agent: {len(hits)} chunk(s) retrieved from pgvector"],
    }


AGENT_NODES = {
    Intent.ORDER_STATUS.value: order_node,
    Intent.PRODUCT_SEARCH.value: product_node,
    Intent.RETURN_REQUEST.value: returns_node,
    Intent.POLICY_QUESTION.value: knowledge_node,
}
