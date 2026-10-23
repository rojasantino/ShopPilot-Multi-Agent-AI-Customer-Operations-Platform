"""ShopPilot - customer chat page (Streamlit entrypoint)."""

import streamlit as st

from api_client import ApiError, ShopPilotClient

st.set_page_config(page_title="ShopPilot", page_icon="🛍️", layout="wide")

CUSTOMERS = {"CUST-001": "Aisha Khan", "CUST-002": "Omar Ali", "CUST-003": "Priya Nair"}
EXAMPLES = [
    "My order is late, and one item is damaged. Can you check the order and tell me if I can return it?",
    "Yes, please start the return for the earbuds, they are damaged",
    "Do you have running shoes in stock?",
    "What is your warranty on headphones?",
]


@st.cache_resource
def client() -> ShopPilotClient:
    return ShopPilotClient()


def render_details(turn: dict) -> None:
    """Show the agent workflow so the system is transparent, not a black box."""
    cols = st.columns(3)
    cols[0].metric("Review", "PASSED" if turn["review"]["passed"] else "FAILED")
    cols[1].metric("Agents run", len(turn["agents_run"]))
    cols[2].metric("Request", turn["request_id"])
    if turn.get("approval"):
        a = turn["approval"]
        st.warning(f"Refund request #{a['id']} is **{a['status']}** ({a['amount']} AED) - awaiting human approval.")
    with st.expander("Agent trace"):
        st.code("\n".join(turn["trace"]), language="text")
    if turn["evidence"]:
        with st.expander(f"Evidence ({len(turn['evidence'])})"):
            for e in turn["evidence"]:
                st.markdown(f"**{e['kind']}** `{e['ref']}` - {e['detail']}")


st.title("🛍️ ShopPilot")
st.caption("Multi-agent customer operations: supervisor, order, product, returns and policy (RAG) agents.")

with st.sidebar:
    customer_id = st.selectbox("Signed in as", list(CUSTOMERS), format_func=lambda c: f"{c} - {CUSTOMERS[c]}")
    st.subheader("Try an example")
    for example in EXAMPLES:
        if st.button(example[:48] + "...", width="stretch"):
            st.session_state["pending"] = example
    try:
        with st.expander("My orders"):
            for o in client().orders(customer_id):
                st.markdown(f"**{o['id']}** - {o['status']} - {float(o['total']):,.0f} {o['currency']}")
                st.caption(", ".join(i["name"] for i in o["items"]))
    except ApiError as exc:
        st.error(str(exc))

history = st.session_state.setdefault("history", {}).setdefault(customer_id, [])
for turn in history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if turn.get("details"):
            render_details(turn["details"])

prompt = st.chat_input("Ask about an order, a return, a product or a policy...")
prompt = prompt or st.session_state.pop("pending", None)
if prompt:
    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"), st.spinner("Agents are working..."):
        try:
            result = client().chat(customer_id, prompt)
            st.markdown(result["reply"])
            render_details(result)
            history.append({"role": "assistant", "content": result["reply"], "details": result})
        except ApiError as exc:
            st.error(str(exc))
