from datetime import UTC, datetime

from app.repositories.orders import OrderRepository
from app.services.return_policy import evaluate_return


def test_delivered_within_window_is_eligible(session):
    order = OrderRepository(session).get_for_customer("ORD-1001", "CUST-001")
    d = evaluate_return(order, now=datetime.now(UTC), window_days=30)
    assert d.eligible and d.refundable_amount == order.total and d.days_left == 25


def test_outside_window_is_rejected(session):
    order = OrderRepository(session).get_for_customer("ORD-1003", "CUST-002")
    d = evaluate_return(order, now=datetime.now(UTC), window_days=30)
    assert not d.eligible and "closed" in d.reasons[0]


def test_not_delivered_is_rejected(session):
    order = OrderRepository(session).get_for_customer("ORD-1002", "CUST-001")
    assert not evaluate_return(order, now=datetime.now(UTC), window_days=30).eligible


def test_final_sale_item_excluded_from_refund(session):
    order = OrderRepository(session).get_for_customer("ORD-1004", "CUST-002")
    d = evaluate_return(order, now=datetime.now(UTC), window_days=30)
    assert d.eligible and float(d.refundable_amount) == 118.0
    assert [i.eligible for i in d.items].count(False) == 1


def test_customer_cannot_read_someone_elses_order(session):
    assert OrderRepository(session).get_for_customer("ORD-1001", "CUST-002") is None
