
# ShopPilot — Multi-Agent AI Customer Operations Platform

Python · FastAPI · Pydantic · LangGraph · PostgreSQL + pgvector · Redis · Streamlit · Docker

A supervisor agent routes customer messages to specialist agents (**order, returns, product, policy/RAG**), a reviewer
checks every reply, and refunds are **never issued by the AI**: agents only create a *pending* request that a human approves.

> Works with **no API key** (rule-based intent + template replies). Add OpenAI or Ollama to improve wording.

## Quick start (Docker)
```bash
cp .env.example .env
make up                       # = docker compose up --build -d
```
| Service | URL |
|---|---|
| Streamlit UI | http://localhost:8501 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health / readiness | `/health`, `/ready` |

First start creates the tables, the HNSW vector index, seeds demo data and ingests the policy documents.

### Try this
1. Sign in as `CUST-001` and send: *"My order is late, and one item is damaged. Can you check the order and tell me if I can return it?"*
   → order looked up, eligibility checked, **no side effect** (it was a question).
2. Send: *"Yes, please start the return for the earbuds, they are damaged"* → a **pending** refund request is created.
3. Open **Approvals** → approve/reject as staff.
4. Open **Vector Explorer** → see the vector table and run a semantic search.

## Run without Docker
```bash
make setup && source .venv/bin/activate
docker compose up -d db redis                       # only the data stores
cd backend && uvicorn app.main:app --reload         # API  :8000
cd frontend && API_URL=http://localhost:8000 streamlit run app.py   # UI :8501
```

## Project structure
```
shoppilot/
├── docker-compose.yml        db (pgvector) · redis · api · ui
├── Makefile                  make up | test | test-int | lint | eval | psql
├── .env.example
├── .github/workflows/ci.yml  lint + tests (real pgvector) + docker build
├── backend/                  FastAPI service
│   ├── Dockerfile · requirements*.txt · pyproject.toml
│   ├── app/
│   │   ├── main.py           app factory, request-id middleware, bootstrap
│   │   ├── core/             config (pydantic-settings), logging, API-key auth
│   │   ├── api/              deps.py (DI) · routes/{chat,admin,health}.py
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── agents/           state · intent · nodes (agents) · composer · reviewer · graph (LangGraph)
│   │   ├── services/         llm · embeddings · chunker · rag · cache (Redis) · return_policy (business rules)
│   │   ├── repositories/     orders · products · approvals · audit · knowledge (pgvector)
│   │   └── db/               models · session · bootstrap (schema, seed, ingest)
│   ├── data/policies/        fictional policy documents (RAG source)
│   ├── evals/                routing_cases.jsonl · run_routing_eval.py
│   └── tests/                unit + integration/test_pgvector.py
├── frontend/                 Streamlit: app.py (chat) · pages/{Approvals,Vector_Explorer}
└── docs/                     ARCHITECTURE · VECTORDB · PRODUCTION · MICROSERVICES · RESOURCES
```

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/chat` | Run the multi-agent workflow |
| GET | `/v1/customers/{id}/orders` | Orders for the UI |
| GET | `/v1/approvals?status=pending` | Approval queue |
| POST | `/v1/approvals/{id}/decision` | Human approve / reject |
| GET | `/v1/admin/knowledge` | Rows of the vector table |
| POST | `/v1/admin/knowledge/search` | Semantic search with similarity scores |

All `/v1` routes need header `X-API-Key`. Example:
```bash
curl -s localhost:8000/v1/chat -H 'X-API-Key: change-me-dev-key' -H 'Content-Type: application/json' \
  -d '{"customer_id":"CUST-001","message":"Do you have running shoes in stock?"}'
```

## Configuration (`.env`)
| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `rules` | `rules` \| `openai` \| `ollama` |
| `EMBEDDING_PROVIDER` | `hash` | `sentence-transformers` for real semantic search (see docs/VECTORDB.md) |
| `DATABASE_URL`, `REDIS_URL` | local | compose overrides the hosts |
| `API_KEY` | dev value | **change it** |
| `RETURN_WINDOW_DAYS` | 30 | business rule |
| `AUTO_BOOTSTRAP` | true | set false in production (use migrations) |

Real embeddings in Docker: `API_REQUIREMENTS=requirements-ml.txt EMBEDDING_PROVIDER=sentence-transformers make up`.
Local LLM: `ollama pull llama3.1` then `LLM_PROVIDER=ollama LLM_MODEL=llama3.1`.

## Testing & evaluation
```bash
make test        # 27 fast unit tests (SQLite + fake RAG, no Docker)
make test-int    # 5 tests against real pgvector (retrieval accuracy, index, dimension)
make eval        # routing precision/recall/F1 on evals/routing_cases.jsonl
```
Measured while building: 32/32 tests passing (27 unit + 5 pgvector). Routing eval on the 26 hand-written cases:
**96.2 % exact match, macro-F1 0.98**; the one miss is a message that names an order ID without the word "order"
(a known limitation of the rules). This is a small self-written set, so treat it as a regression guard, not a benchmark.

## Status & honesty notes
* Tested directly in a sandbox with real PostgreSQL 16 + pgvector 0.6, FastAPI, LangGraph and Streamlit.
* **Not exercised there:** the Docker images / `docker compose` (no Docker in the sandbox), Redis server (the code falls back to
  in-memory if Redis is unreachable), and live OpenAI/Ollama calls (the rule-based path is what was tested).
* MVP security: shared API key and client-supplied `customer_id`. See **docs/PRODUCTION.md** before exposing this anywhere.

## More
* Architecture & workflows → `docs/ARCHITECTURE.md`
* Vector DB explained (with Tamil section) → `docs/VECTORDB.md`
* Production steps → `docs/PRODUCTION.md` · Microservices → `docs/MICROSERVICES.md` · Links → `docs/RESOURCES.md`
