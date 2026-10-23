# Can this be microservices? Yes. Should it be, now? Not yet.

**Recommendation:** ship the **modular monolith** you have (API + UI + Postgres + Redis = 4 containers).
Split only when a concrete pain appears: different scaling needs, separate teams, or different release cadence.
Microservices add network failures, distributed tracing and deployment overhead that an MVP does not need.

## Why this code is "microservice-ready"
Each future service already has a clean seam:

| Future service | Today's seam | What moves |
|---|---|---|
| `knowledge-service` (RAG ingest + search) | `services/rag.py`, `repositories/knowledge.py`, `KnowledgeSearcher` protocol | pgvector + embedding model (CPU/GPU-heavy, scales alone) |
| `order-service` (orders, returns rules) | `repositories/orders.py`, `services/return_policy.py` | order DB + business rules |
| `approval-service` | `repositories/approvals.py`, `/v1/approvals` | human-review workflow, own auth/RBAC |
| `agent-service` (LangGraph) | `agents/*` | orchestration only; calls the others over HTTP/gRPC |

To split, implement the same Protocol with an HTTP client:
```python
class HttpKnowledgeSearcher:                       # satisfies KnowledgeSearcher
    def search(self, query: str, k: int = 3) -> list[SearchHit]:
        r = httpx.post(f"{KNOWLEDGE_URL}/search", json={"query": query, "k": k}, timeout=5)
        r.raise_for_status()
        return [SearchHit(**h) for h in r.json()]
```
The graph does not change because nodes depend on `deps.rag`, not on pgvector.

## Target topology
```
Streamlit UI -> API gateway (auth, rate limit)
                  |-> agent-service (LangGraph) --HTTP--> knowledge-service --> pgvector DB
                  |                              --HTTP--> order-service --> orders DB
                  |-> approval-service --> approvals DB
                  `-> Redis (shared cache) · message queue for async events
```
Rules when splitting: one database per service; timeouts + retries + circuit breakers on every call;
propagate `X-Request-ID` everywhere; version every API (`/v1`); contract-test each boundary.
