# CLAUDE.md

## Project Overview

A FastAPI REST service for managing refrigerator inventory with SQLite persistence, an append-only event log, ChromaDB-backed semantic search (local embeddings), and a RAG-powered `/ask` endpoint backed by a local LLM via any OpenAI-compatible server (e.g. LM Studio).

## Tech Stack

- **Language:** Python 3.12 (pinned in `.python-version`)
- **Package manager:** `uv` — use `uv run` to execute anything; do not use `python` or `pip` directly
- **API framework:** FastAPI
- **Database:** SQLite via synchronous `sqlite3` (not async despite the `aiosqlite` dependency)
- **Vector store:** ChromaDB (local persistent) at `data/chroma/`
- **Embeddings:** `all-MiniLM-L6-v2` via `sentence-transformers` — runs fully locally

## Development Commands

```bash
# Install dependencies
uv sync

# Run the server (reload on change)
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_items.py -v
```

Server runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Project Layout

```
app/
  main.py              # FastAPI app, lifespan (calls init_db on startup)
  config.py            # Settings via pydantic-settings; data paths configurable
  database.py          # SQLite schema, init_db(), get_db() context manager
  models.py            # Pydantic request/response models
  routers/
    items.py           # CRUD + /expired, /expiring-soon, /{id}/extend
    events.py          # Read-only event log
    search.py          # Semantic search endpoint
    ask.py             # RAG Q&A endpoint; delegates to ask_service
    ingest.py          # Text-to-items endpoint; delegates to ingest_service
    system.py          # GET /health
  services/
    item_service.py    # Business logic; calls vector_store + event_service after each mutation
    event_service.py   # log_event() + list_events()
    vector_store.py    # ChromaDB wrapper: upsert/delete/search
    ask_service.py     # RAG pipeline: hybrid retrieval (_retrieve_context) + local LLM call
    ingest_service.py  # Text → item extraction via LLM + shelf-life lookup + bulk item creation
tests/
  conftest.py               # `client` fixture using tmp_path + Settings override + mock patches
  test_items.py             # Item CRUD + event log integration tests
  test_search.py            # Semantic search tests
  test_ingest.py            # Ingest endpoint tests (mocks LLM call)
  test_retrieval_eval.py    # Hit-rate eval; calls ask_service._retrieve_context() directly
  test_generation_eval.py   # LLM-as-judge eval; requires local LLM server (pytest -m llm)
```

**Note:** There is a `refrigerator_event_stream/` subdirectory that mirrors this layout — it is a stale nested copy and should be ignored. All active code lives at the repo root under `app/` and `tests/`.

## Architecture Patterns

- **Service layer is synchronous.** `get_db()` is a `contextlib.contextmanager`, not async. Do not introduce `async def` into service functions.
- **Mutations always do three things:** update SQLite → upsert/delete ChromaDB → log an event. This order is intentional and should be preserved.
- **Event types:** `ITEM_ADDED`, `ITEM_UPDATED`, `ITEM_REMOVED`, `EXPIRATION_EXTENDED`. Events are immutable; never delete them.
- **IDs:** items use `uuid4` strings; events use SQLite autoincrement integers.
- **ChromaDB document format:** `"{name}. category: {category}. {notes}"` — see `vector_store.build_document()`. Changing this affects search relevance.
- **Settings override pattern:** Tests patch `app.config.settings`, `app.database.settings`, `app.services.vector_store.settings`, `app.services.ask_service.settings`, and `app.services.ingest_service.settings` in `conftest.py` — if you add a new module that imports `settings` at module level, add it to the patch list.

## Data Persistence

Runtime data is in `data/` (gitignored):
- `data/refrigerator.db` — SQLite database
- `data/chroma/` — ChromaDB vector store

The `data/` directory is created automatically on startup via `settings.database_path` property and `vector_store._get_client()`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/items` | Create item (`name`, `expires_at` required) |
| GET | `/api/v1/items` | List items (query: `category`, `expired`, `limit`, `offset`) |
| GET | `/api/v1/items/expired` | All expired items |
| GET | `/api/v1/items/expiring-soon` | Items expiring within `days` (default 3) |
| GET | `/api/v1/items/{id}` | Get single item |
| PATCH | `/api/v1/items/{id}` | Partial update |
| DELETE | `/api/v1/items/{id}` | Delete item |
| POST | `/api/v1/items/{id}/extend` | Extend expiration by `days` |
| GET | `/api/v1/events` | List events (query: `item_id`, `event_type`, `limit`) |
| GET | `/api/v1/search` | Semantic search (query: `q`, `n_results`) |
| POST | `/api/v1/ask` | RAG Q&A (body: `question`); requires local LLM server |
| POST | `/api/v1/ingest` | Parse free-text description into items and insert them; requires local LLM server |

## Testing Notes

- Tests use `TestClient` (synchronous) and isolated `tmp_path` directories — no shared state between tests.
- No mocking of ChromaDB or SQLite — tests hit real instances in temp dirs.
- `conftest.py` must be imported after patches are applied; note the in-fixture `from app.main import app` import to pick up patched settings.
- The `database.init_db()` call happens in the FastAPI `lifespan`, which `TestClient.__enter__` triggers.
- `test_retrieval_eval.py` calls `ask_service._retrieve_context()` directly (no LLM needed); runs in the normal test suite.
- `test_generation_eval.py` is marked `@pytest.mark.llm` and requires a local LLM server. Run with `uv run pytest -m llm -s`. The `conftest.py` patches `app.services.ask_service.settings` — keep this in sync if ask_service gains new top-level settings imports.
- `test_ingest.py` mocks the LLM call (`ingest_service._parse_with_llm`) so it runs without a local server. `ingest_service.settings` is patched in `conftest.py`; add it if you add new top-level settings imports to that module.
