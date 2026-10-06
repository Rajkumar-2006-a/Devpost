# Design Decisions

## Why Gemini 1.5 Flash (not GPT-4o)?

Gemini 1.5 Flash has:
- A **1 million token context window** — useful for long transcript processing
- **Native multimodal input** — images can be passed directly in the API call, enabling VLM captioning without a separate model
- **Free tier** sufficient for a hackathon demo (~1.5M input tokens/day)
- A single SDK handles both LLM and VLM tasks → simpler provider abstraction

Trade-off: GPT-4o has higher benchmark performance but higher cost and a smaller context window.

## Why ChromaDB (not Qdrant or Weaviate)?

- **Zero infrastructure**: runs in-process, persisted to disk; no Docker dependency just for the vector store
- Supports metadata filters (`where={"student_id": ...}`) for per-student scoping
- Python-native, well-maintained, easy to swap if scale demands Qdrant

Trade-off: ChromaDB's HNSW index doesn't match Qdrant's performance at >1M vectors.

## Why SQLite first (not PostgreSQL)?

- Zero configuration for local development
- Same SQLAlchemy ORM code runs on PostgreSQL (swap just the `DATABASE_URL`)
- For a hackathon demo with a handful of students, SQLite is more than sufficient

Production path: set `DATABASE_URL=postgresql://...` in `.env`.

## Why BKT (not IRT)?

| | BKT | IRT |
|---|---|---|
| Data needed | Works with ~5-10 observations | Needs 30+ observations per item |
| Interpretability | Direct probability interpretation | Parameter estimation opaque |
| Cold start | Works with priors | Requires item parameter calibration |
| Established use | Well-studied in AIED | More common in large-scale testing |

BKT was chosen for its interpretability and cold-start friendliness.

## Why Hybrid BM25+Dense Retrieval?

Dense embedding retrieval captures semantic similarity but misses exact keyword matches (e.g., formula names, algorithm names). BM25 captures keywords but misses paraphrases. Reciprocal Rank Fusion of both consistently outperforms either alone for heterogeneous educational content.

## Why Sliding Window Chunking (not semantic chunking)?

Semantic chunking requires an LLM call per chunk boundary (expensive, slow). Sliding window with sentence-boundary awareness is:
- Fast (pure Python, no LLM calls)
- Predictable in chunk size (critical for embedding quality)
- Good enough for RAG when overlap is set to 50 tokens

## Why Cross-Encoder Reranking?

Bi-encoder embeddings (used for retrieval) compress documents into fixed vectors and lose fine-grained interaction signals. A cross-encoder processes (query, passage) pairs jointly and scores relevance much more accurately. We use it only on the top-10 retrieved passages (reranking, not retrieval) to keep latency manageable.

## Why Inline Citations `[N]` (not hyperlinks in text)?

Inline citation numbers are familiar from academic papers and don't interrupt reading flow. They allow the user to selectively click only the citations they want to investigate, rather than being flooded with links. The side panel design keeps the citation detail accessible without breaking the conversation.

## Why SSE (not WebSocket) for Progress Streaming?

Server-Sent Events are simpler than WebSocket for unidirectional streaming (server → client):
- Built into FastAPI via `sse-starlette`
- No client reconnection logic needed (browser handles it)
- Works through proxies without WebSocket upgrade negotiation

## Async Architecture

FastAPI's async support means the ingestion pipeline (which runs background tasks) never blocks the web server. Long-running tasks (Whisper transcription, LLM calls) run in a thread pool executor, keeping the event loop free for concurrent requests.
