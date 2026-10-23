import pytest

from app.agents.intent import classify_with_rules
from app.schemas.intent import Intent


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Where is my order ORD-1001?", {Intent.ORDER_STATUS}),
        ("Do you have running shoes in stock?", {Intent.PRODUCT_SEARCH}),
        ("What is your warranty on headphones?", {Intent.POLICY_QUESTION}),
        (
            "My order is late and one item is damaged, can I return it?",
            {Intent.ORDER_STATUS, Intent.RETURN_REQUEST},
        ),
        ("hello there", set()),
    ],
)
def test_intents(message, expected):
    assert set(classify_with_rules(message).intents) == expected


def test_order_id_extracted_and_normalised():
    assert classify_with_rules("status of ord-1003 please").order_id == "ORD-1003"


def test_question_is_not_an_action():
    assert not classify_with_rules("Can I return the earbuds?").wants_return_action
    assert classify_with_rules("Please start the return for the earbuds").wants_return_action


def test_damage_reason_detected():
    assert (
        classify_with_rules("the item arrived broken, I want a refund").return_reason == "damaged"
    )
