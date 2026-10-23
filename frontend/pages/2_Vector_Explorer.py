"""See what the vector database actually looks like, and run a semantic search yourself."""

import pandas as pd
import streamlit as st

from api_client import ApiError, ShopPilotClient

st.set_page_config(page_title="Vector DB Explorer", page_icon="🧭", layout="wide")
st.title("🧭 Vector database explorer")
st.markdown(
    "Each policy document is split into **chunks**. Every chunk is stored as a row: "
    "the text plus its **embedding** - a list of 384 numbers that represent its meaning. "
    "Searching = turning your question into numbers and finding the rows with the closest numbers."
)
client = ShopPilotClient()

try:
    rows = client.knowledge(200)
except ApiError as exc:
    st.error(str(exc))
    st.stop()

st.subheader(f"Table `knowledge_chunks` - {len(rows)} rows")
st.dataframe(
    pd.DataFrame(
        {
            "id": r["id"],
            "source": r["source"],
            "chunk": r["chunk_index"],
            "content": r["content"][:90] + "...",
            "embedding (first 8 of 384)": str(r["embedding_preview"]),
        }
        for r in rows
    ),
    hide_index=True,
    width="stretch",
)

st.subheader("Try a semantic search")
query = st.text_input("Question", "how many days do I have to return something?")
k = st.slider("Top K", 1, 6, 3)
if query:
    try:
        for hit in client.knowledge_search(query, k):
            with st.container(border=True):
                st.markdown(f"**{hit['source']}** (chunk {hit['chunk_index']}) - similarity **{hit['score']:.3f}**")
                st.progress(max(0.0, min(1.0, hit["score"])))
                st.write(hit["content"])
    except ApiError as exc:
        st.error(str(exc))
