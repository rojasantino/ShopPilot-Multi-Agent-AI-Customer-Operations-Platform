"""End-to-end workflow tests (no network, no LLM)."""

from sqlalchemy import select

from app.agents.reviewer import review_reply
from app.db.models import ApprovalRequest


def test_demo_scenario_informs_but_does_not_create_approval(run, session):
    state = run(
        "CUST-001",
        "My order is late, and one item is damaged. "
        "Can you check the order and tell me if I can return it?",
    )
    assert state["results"]["order"]["id"] == "ORD-1001"
    assert state["results"]["returns"]["eligible"] is True
    assert state["review"]["passed"]
    assert session.scalars(select(ApprovalRequest)).all() == []  # a question has no side effects


def test_explicit_request_creates_pending_approval_only(run, session):
    state = run("CUST-001", "Please start the return for the earbuds, they are damaged")
    row = session.scalars(select(ApprovalRequest)).one()
    assert row.status == "pending" and float(row.amount) == 249.0
    assert state["approval"]["id"] == row.id
    assert "pending" in state["reply"].lower()


def test_duplicate_request_is_idempotent(run, session):
    msg = "Please start the return for ORD-1001"
    run("CUST-001", msg)
    run("CUST-001", msg)
    assert len(session.scalars(select(ApprovalRequest)).all()) == 1


def test_cannot_touch_another_customers_order(run, session):
    state = run("CUST-002", "Please start the return for ORD-1001")
    assert state["results"]["returns"]["order_found"] is False
    assert session.scalars(select(ApprovalRequest)).all() == []


def test_product_search_uses_cache_second_time(run):
    run("CUST-001", "Do you have a yoga mat?")
    second = run("CUST-001", "Do you have a yoga mat?")
    assert "via cache" in " ".join(second["trace"])


def test_unknown_message_gets_help_text(run):
    assert "order status" in run("CUST-001", "hi")["reply"]


def test_reviewer_blocks_refund_claims_and_unknown_orders():
    bad = {"reply": "Your refund has been issued for ORD-9999.", "evidence": []}
    issues = review_reply(bad)
    assert len(issues) == 2


def test_reviewer_allows_negated_refund_wording():
    ok = {"reply": "It is pending approval and no refund has been issued yet.", "evidence": []}
    assert review_reply(ok) == []
