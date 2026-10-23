# From MVP to production

This repo is a **working MVP**, not production-hardened. Work through this list in order.

## Known MVP limitations (read first)
* **Auth is a single shared API key** and `customer_id` comes from the request body. Anyone with the key can act as any
  customer. Production: OIDC/JWT login, derive `customer_id` from the token, add staff roles for `/approvals`.
* Tables are created with `create_all`; there are **no migrations** yet.
* No LangGraph checkpointer; each request runs start to finish. Conversation memory is not persisted.
* Default embedder is lexical (`hash`). Evaluate retrieval with a semantic model before launch.
* Routing eval is a small, self-written set (26 cases) - useful as a regression guard, not a benchmark.

## Step-by-step
1. **Secrets & config** - move `.env` to a secret manager (AWS Secrets Manager / GCP Secret Manager / Vault). Rotate `API_KEY`.
2. **Managed Postgres with pgvector** - RDS/Aurora, Cloud SQL, Azure Flexible Server, Neon or Supabase all support it.
   Enable backups + point-in-time recovery, TLS, a least-privilege app user, a connection pooler (PgBouncer).
3. **Migrations** - add Alembic (`alembic init`), generate the baseline from `app/db/models.py`, run it in CI/CD, set `AUTO_BOOTSTRAP=false`.
4. **Real auth** - OAuth2/OIDC (Auth0, Keycloak, Cognito). RBAC: `customer`, `support_agent`, `admin`. Remove customer_id from request bodies.
5. **Managed Redis** - ElastiCache/Memorystore with auth + TLS. Keep the fail-open rate limiter.
6. **Real LLM + embeddings** - `LLM_PROVIDER=openai` (or a hosted open model); `requirements-ml.txt` and
   `EMBEDDING_PROVIDER=sentence-transformers`; re-ingest. Add timeouts, budgets and a fallback (already: template reply).
7. **Safety** - redact PII before it reaches a third-party LLM; treat retrieved documents as untrusted (prompt injection);
   keep the reviewer and approval gate; add content moderation if customers type free text.
8. **Observability** - structured logs (request id already included), OpenTelemetry traces, Prometheus metrics
   (latency p50/p95, agent errors, approval queue size), LLM tracing with Langfuse/LangSmith, alerts on `/ready`.
9. **State & memory** - add `langgraph-checkpoint-postgres` if you need resumable / multi-turn workflows.
10. **CI/CD** - `.github/workflows/ci.yml` already lints, tests (incl. real pgvector) and builds images. Add: push images to a
    registry, image scanning (Trivy), dependency audit, deploy on tag.
11. **Deploy** - containers on ECS Fargate / Cloud Run / Azure Container Apps (simple) or Kubernetes (scale). Run 2+ API replicas
    behind a load balancer; probes: liveness `/health`, readiness `/ready`. Streamlit is an internal/staff tool; put it behind SSO.
12. **Load & quality gates** - Locust/k6 test the `/v1/chat` path; add RAGAS/DeepEval suites; block deploys when routing/retrieval metrics regress.
13. **Compliance** - data residency, retention for `audit_log`, consent, and a privacy review (e.g. UAE PDPL) before real customer data.

## Reference deployment (small)
```
Route53/DNS -> ALB (TLS) -> ECS: api x2 (+ ui x1)  -> RDS Postgres+pgvector (Multi-AZ)
                                                   -> ElastiCache Redis
                                                   -> Secrets Manager, CloudWatch/OTel, ECR
```
