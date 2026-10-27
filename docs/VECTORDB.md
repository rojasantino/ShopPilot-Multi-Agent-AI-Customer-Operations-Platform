# The vector database, explained

ShopPilot does **not** need a separate vector database. PostgreSQL + the **pgvector** extension stores the
vectors next to the normal business tables, so one backup, one connection pool, one place to secure.

## What it looks like (real output from this project)

```
                      Table "public.knowledge_chunks"
   Column    |          Type          | Nullable
-------------+------------------------+----------
 id          | integer                | not null
 source      | character varying(120) | not null      <- file the text came from
 chunk_index | integer                | not null      <- position inside that file
 content     | text                   | not null      <- the actual text
 embedding   | vector(384)            | not null      <- 384 numbers = the "meaning" of content
Indexes:
    "knowledge_chunks_pkey" PRIMARY KEY, btree (id)
    "ix_knowledge_embedding_hnsw" hnsw (embedding vector_cosine_ops)
```

```
 id |           source            | chunk_index |                content                  | embedding
----+-----------------------------+-------------+-----------------------------------------+---------------------------
  1 | payment_and_cancellation.md |           0 | Payment methods: We accept Visa, Master | [0,0,0,...,-0.218,...]
  4 | returns_policy.md           |           0 | Returns Policy: ShopPilot Store accepts | [0,0.14,0,...]
```

## How a question becomes a result

```
"how many days to return?"  --embed-->  [0.01, -0.20, ... 384 numbers]
                                                 |
        SELECT content, 1 - (embedding <=> :q) AS similarity
        FROM knowledge_chunks ORDER BY embedding <=> :q LIMIT 3;     (HNSW index makes this fast)
                                                 |
                      top-3 closest chunks  ->  knowledge agent  ->  cited answer
```
`<=>` is pgvector's **cosine distance**; similarity = 1 - distance.

## Look at it yourself
```bash
make up && make psql
\d knowledge_chunks
SELECT id, source, left(content, 60) FROM knowledge_chunks LIMIT 5;
SELECT vector_dims(embedding) FROM knowledge_chunks LIMIT 1;   -- 384
```
Or open the Streamlit page **Vector Explorer** (http://localhost:8501) to see rows and run a search.

## Two embedders
| `EMBEDDING_PROVIDER` | Quality | Install size | Use |
|---|---|---|---|
| `hash` (default) | Lexical (shared words) | none | tests, quick demo |
| `sentence-transformers` | Semantic (meaning) | ~2 GB (PyTorch) | real use; model `BAAI/bge-small-en-v1.5` |

Switching: `pip install -r backend/requirements-ml.txt`, set `EMBEDDING_PROVIDER=sentence-transformers`,
then re-ingest (`ingest_policies(session, embedder, force=True)`), because old vectors came from another model.
The `hash` embedder's vectors are mostly zeros (sparse); a real model gives 384 dense numbers.

## Scaling notes
* Up to ~1M chunks: pgvector + HNSW is enough. Beyond that, consider partitioning or a dedicated vector DB.
* Vector dimension is fixed in the column type (`vector(384)`); changing models with a different size needs a migration.

---
