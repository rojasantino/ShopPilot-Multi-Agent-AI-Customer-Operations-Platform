# Resources & where each piece came from

Every link below is an official project page or a page I opened while building this repo.

| What | Used for | Link |
|---|---|---|
| LangGraph (GitHub) | Supervisor graph, conditional edges, state | https://github.com/langchain-ai/langgraph |
| LangGraph docs | Tutorials: multi-agent, persistence, human-in-the-loop | https://langchain-ai.github.io/langgraph/ |
| pgvector (GitHub) | Postgres vector extension (`vector` type, `<=>`, HNSW) | https://github.com/pgvector/pgvector |
| pgvector-python | SQLAlchemy `Vector` column + `cosine_distance` | https://github.com/pgvector/pgvector-python |
| pgvector Docker image | `pgvector/pgvector:pg16` used in docker-compose | https://hub.docker.com/r/pgvector/pgvector |
| FastAPI | API framework, dependency injection | https://github.com/fastapi/fastapi |
| Pydantic / pydantic-settings | Request/response models, config | https://docs.pydantic.dev |
| Streamlit | UI (chat, approvals, vector explorer) | https://docs.streamlit.io |
| BAAI/bge-small-en-v1.5 | Optional real embedding model (384 dims) | https://huggingface.co/BAAI/bge-small-en-v1.5 |
| Ollama | Optional local LLM (OpenAI-compatible `/v1`) | https://ollama.com |
| E-commerce agent-routing dataset | **Hugging Face dataset** for routing tests (12,550 synthetic queries, 7 agents) | https://huggingface.co/datasets/scionoftech/functiongemma-e-commerce-dataset |
| Langfuse / LangSmith | LLM tracing (production) | https://github.com/langfuse/langfuse |
| RAGAS / DeepEval | RAG + LLM evaluation (next step) | https://github.com/explodinggradients/ragas , https://github.com/confident-ai/deepeval |

## About data
* **Orders, products, customers** are fictional and seeded in `backend/app/db/bootstrap.py`.
* **Policies** are fictional markdown files in `backend/data/policies/`.
* **Hugging Face dataset**: not required to run the MVP. Use it to build a larger routing test set:

```python
from datasets import load_dataset  # pip install datasets
ds = load_dataset("scionoftech/functiongemma-e-commerce-dataset")
print(ds)  # inspect splits/columns first, then map its 7 agent labels to ShopPilot's 4 intents
```
Its labels (e.g. "order management") differ from ShopPilot's four intents, so you must write a mapping before
using it for evaluation. Check the dataset's license on its page before reuse.
