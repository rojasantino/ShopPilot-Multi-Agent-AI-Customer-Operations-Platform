"""Human-in-the-loop approvals queue (staff view)."""

import pandas as pd
import streamlit as st

from api_client import ApiError, ShopPilotClient

st.set_page_config(page_title="Approvals", page_icon="✅", layout="wide")
st.title("✅ Refund approvals")
st.caption("Agents can only create PENDING requests. A human decides here.")

client = ShopPilotClient()
reviewer = st.sidebar.text_input("Reviewer name", value="manager.sara")
status = st.sidebar.selectbox("Show", ["pending", "approved", "rejected"])

try:
    rows = client.approvals(status)
except ApiError as exc:
    st.error(str(exc))
    st.stop()

if not rows:
    st.info(f"No {status} requests.")
for row in rows:
    with st.container(border=True):
        left, right = st.columns([3, 2])
        left.markdown(f"### #{row['id']} - {row['order_id']}  \n"
                      f"Customer `{row['customer_id']}` - reason **{row['reason']}** - "
                      f"**{float(row['amount']):,.2f} AED**")
        left.caption(row["details"].get("note") or "")
        left.dataframe(pd.DataFrame(row["details"].get("items", [])), hide_index=True)
        if row["status"] == "pending":
            note = right.text_input("Note", key=f"note{row['id']}")
            ok, no = right.columns(2)
            for col, decision in ((ok, "approved"), (no, "rejected")):
                if col.button(decision.title(), key=f"{decision}{row['id']}", width="stretch"):
                    try:
                        client.decide(row["id"], decision, reviewer, note or None)
                        st.rerun()
                    except ApiError as exc:
                        st.error(str(exc))
        else:
            right.success(f"{row['status'].title()} by {row['decided_by']}")
