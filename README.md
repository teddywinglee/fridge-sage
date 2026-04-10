# Fridge Sage

A REST API service for managing refrigerator inventory with expiration tracking, semantic search, and local AI Q&A — built to demonstrate **ChromaDB**, **sentence-transformer embeddings**, and **RAG with a local LLM**, all without external API calls.

## Features

- Add, update, and remove items from your refrigerator
- Track expiration dates and get alerts for expired or soon-to-expire items
- Extend expiration dates on items you know are still good
- **Semantic search** powered by ChromaDB + `all-MiniLM-L6-v2` embeddings (e.g. search "dairy products" to find milk, cheese, yogurt)
- Automatic event log on every CRUD operation

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12 |
| Package manager | uv |
| API framework | FastAPI |
| Vector store | ChromaDB (local persistent) |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Database | SQLite (`sqlite3`, synchronous) |

## Configuration

All settings can be overridden via environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `data/refrigerator.db` | Path to the SQLite database file |
| `CHROMA_PERSIST_DIR` | `data/chroma` | Directory for ChromaDB persistent storage |
| `CHROMA_COLLECTION_NAME` | `items` | ChromaDB collection name |
| `ASK_BASE_URL` | `http://localhost:1234/v1` | Base URL of an OpenAI-compatible LLM server |
| `ASK_MODEL` | `gemma-4-26b-a4b-it-GGUF` | Model name to pass to the LLM server |
| `ASK_MAX_TOKENS` | `1024` | Max tokens for LLM responses |

The `ASK_*` variables are only relevant if you use the `/ask` endpoint (see below).

## Getting Started

**Prerequisites:** [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
# Clone and install dependencies
git clone <repo-url>
cd fridge-sage
uv sync

# Run the server
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

Data is persisted locally under `data/`:
- `data/refrigerator.db` — SQLite database
- `data/chroma/` — ChromaDB vector store

## API Overview

### Items

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/items` | Add an item |
| `GET` | `/api/v1/items` | List items (filter by `category`, `expired`) |
| `GET` | `/api/v1/items/{id}` | Get a single item |
| `PATCH` | `/api/v1/items/{id}` | Update an item |
| `DELETE` | `/api/v1/items/{id}` | Remove an item |
| `GET` | `/api/v1/items/expired` | List all expired items |
| `GET` | `/api/v1/items/expiring-soon` | Items expiring within N days (default: 3) |
| `POST` | `/api/v1/items/{id}/extend` | Extend expiration by N days |

### Search

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/search?q=<query>` | Semantic search across all items |

### Ask (RAG)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/ask` | Ask a natural language question about your fridge contents |

Requires a running OpenAI-compatible LLM server (see [Local LLM Setup](#local-llm-setup) below).

### Events

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/events` | List events (filter by `item_id`, `event_type`) |

## Example Usage

```bash
# Add an item
curl -X POST http://localhost:8000/api/v1/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Whole Milk", "category": "dairy", "quantity": 1, "unit": "L", "expires_at": "2026-04-10"}'

# Check what's expiring soon
curl http://localhost:8000/api/v1/items/expiring-soon?days=5

# Semantic search — finds milk, cheese, yogurt, etc.
curl "http://localhost:8000/api/v1/search?q=dairy+products"

# Extend expiration by 2 days
curl -X POST http://localhost:8000/api/v1/items/<id>/extend \
  -H "Content-Type: application/json" \
  -d '{"days": 2}'

# Ask a natural language question (requires local LLM server)
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What should I use up before it expires?"}'
```

## Local LLM Setup

The `/ask` endpoint is optional — the rest of the API works without it. To enable it, you need an OpenAI-compatible LLM server running locally.

**[LM Studio](https://lmstudio.ai/)** is the easiest option:
1. Download and install LM Studio
2. Load a model (e.g. any Gemma or Llama GGUF)
3. Start the local server (default: `http://localhost:1234/v1`)
4. Set `ASK_MODEL` to match the model identifier shown in LM Studio

**[Ollama](https://ollama.com/)** works too — set `ASK_BASE_URL=http://localhost:11434/v1` and `ASK_MODEL` to your pulled model name.

> **WSL2 users:** If the LLM server is running on Windows and your project is inside WSL2, `localhost` won't resolve to the Windows host by default. Enable mirrored networking by adding the following to `C:\Users\<you>\.wslconfig`, then run `wsl --shutdown` and reopen:
> ```ini
> [wsl2]
> networkingMode=mirrored
> ```

### How `/ask` works

The endpoint combines semantic search and structured retrieval to build a context window from your actual inventory, then passes it to the local LLM. The LLM is instructed to answer only from that context — it won't hallucinate items you don't have.

## How ChromaDB Is Used

Each item is embedded and stored in a local ChromaDB persistent collection when created or updated, and removed when deleted. The document fed to the embedder combines the item's name, category, and notes — enabling natural language queries that go beyond exact keyword matching.

```
"leftover pasta" → finds "spaghetti bolognese", "penne arrabiata"
"dairy products" → finds "milk", "cheese", "yogurt"
```

The embedding model (`all-MiniLM-L6-v2`) runs fully locally — no external API calls required.

## Lessons Learned: Semantic Search Is Context-Dependent

One of the more interesting observations from this project: semantic search is not an off-the-shelf solution that works equally well for every domain.

When searching for `"drink"`, a general-purpose embedding model may rank `"cheese"` closer to the query than `"milk"` — not because it's wrong, but because `all-MiniLM-L6-v2` was trained on broad text corpora where "milk" appears in food contexts as often as drink contexts, and "cheese" may sit in a similar embedding neighborhood.

This is further compounded by **collection size**. With only a handful of items in the vector store, all embeddings are crowded into a small, similar region of the vector space — the distances between them are numerically close, so ranking becomes noisy and less meaningful. Relevance improves as the collection grows and vectors spread out.

This highlights a real-world tradeoff:

- **General-purpose models** (like `all-MiniLM-L6-v2`) are easy to deploy locally and work well for name/description similarity, but their relevance degrades on abstract or domain-specific queries.
- **Domain-tuned models** or **enriched document schemas** (e.g. adding an explicit `type: beverage` field to the embedded text) can significantly improve relevance — at the cost of more upfront design and labelling effort.

The takeaway: RAG and vector search are powerful tools, but they reward teams who invest in understanding their data and query patterns. Dropping in an embedding model is a starting point, not a finish line.

## Running Tests

```bash
# Unit + integration tests (no external dependencies)
uv run pytest tests/ -v

# Retrieval eval — measures hit rate of the hybrid retrieval pipeline
uv run pytest tests/test_retrieval_eval.py -v -s

# Generation eval — requires local LLM server running (e.g. LM Studio)
uv run pytest -m llm -s
```
