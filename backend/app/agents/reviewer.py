"""Response reviewer: deterministic guardrails between the draft reply and the customer."""

import re

from langchain_core.runnables import RunnableConfig

from app.agents.deps import deps_from
from app.agents.state import AgentState
from app.repositories.approvals import ApprovalRepository

ORDER_ID_RE = re.compile(r"\bORD-\d{4,6}\b")
FORBIDDEN_CLAIMS = re.compile(
    r"(?<!\bno )(?<!\bnot )(?<!\byet )refund (has been|was|is being|will be) (issued|processed|completed|sent)"
    r"|i(?:'ve| have) (refunded|issued|processed) (a|your|the) refund"
    r"|money (has been|was) (sent|returned|refunded)"
    r"|(guarantee|guaranteed) (a )?refund",
    re.IGNORECASE,
)
MAX_REPLY_CHARS = 1200


def review_reply(state: AgentState) -> list[str]:
    reply = state.get("reply", "")
    issues: list[str] = []
    if not reply.strip():
        issues.append("empty reply")
    if len(reply) > MAX_REPLY_CHARS:
        issues.append("reply too long")
    if FORBIDDEN_CLAIMS.search(reply):
        issues.append("reply claims a refund was issued/guaranteed (only humans approve refunds)")

    known = {e["ref"] for e in state.get("evidence", []) if e["kind"] in ("order", "eligibility")}
    unknown = set(ORDER_ID_RE.findall(reply)) - known
    if unknown:
        issues.append(f"reply mentions order id(s) not supported by evidence: {sorted(unknown)}")

    if state.get("approval") and not re.search(r"pending|approval", reply, re.IGNORECASE):
        issues.append("approval exists but reply does not say it is pending")
    return issues


def review_node(state: AgentState, config: RunnableConfig) -> dict:
    deps = deps_from(config)
    issues = review_reply(state)
    review = {"passed": not issues, "issues": issues, "retries": state.get("retries", 0)}
    deps.audit("review.result", review)
    return {
        "review": review,
        "trace": [f"review: {'PASS' if not issues else 'FAIL ' + str(issues)}"],
    }


def retry_node(state: AgentState) -> dict:
    return {
        "strict": True,
        "retries": state.get("retries", 0) + 1,
        "trace": ["retry: switching to strict template reply"],
    }


def escalate_node(state: AgentState, config: RunnableConfig) -> dict:
    deps = deps_from(config)
    issues = state.get("review", {}).get("issues", [])
    ticket = ApprovalRepository(deps.session).create_ticket(
        customer_id=state["customer_id"],
        order_id=state.get("order_id"),
        issue=f"Auto-escalated: reply failed review {issues}. Customer said: {state['message'][:300]}",
    )
    deps.audit("ticket.created", {"ticket_id": ticket.id, "issues": issues})
    reply = (
        f"I want to make sure you get accurate help, so I've passed this to our support team "
        f"(ticket #{ticket.id}). They will follow up with you."
    )
    return {"reply": reply, "ticket_id": ticket.id, "trace": [f"escalate: ticket #{ticket.id}"]}
