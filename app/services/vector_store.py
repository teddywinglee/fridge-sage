from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import settings

_embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")


def _get_client() -> chromadb.ClientAPI:
    path = Path(settings.chroma_persist_dir)
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def _get_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        embedding_function=_embedding_fn,
    )


def build_document(name: str, category: str | None, notes: str | None) -> str:
    parts = [name]
    if category:
        parts.append(f"category: {category}")
    if notes:
        parts.append(notes)
    return ". ".join(parts)


def upsert(item_id: str, name: str, category: str | None, expires_at: str, notes: str | None) -> None:
    collection = _get_collection()
    document = build_document(name, category, notes)
    metadata = {"category": category or "", "expires_at": expires_at}
    collection.upsert(ids=[item_id], documents=[document], metadatas=[metadata])


def delete(item_id: str) -> None:
    collection = _get_collection()
    collection.delete(ids=[item_id])


def search(query: str, n_results: int = 5) -> list[tuple[str, float]]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    n_results = min(n_results, collection.count())
    results = collection.query(query_texts=[query], n_results=n_results)
    ids = results["ids"][0]
    distances = results["distances"][0]
    return list(zip(ids, distances))
