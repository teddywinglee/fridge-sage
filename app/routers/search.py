from fastapi import APIRouter, Query

from app.models import SearchResult
from app.services import item_service, vector_store

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
def semantic_search(
    q: str = Query(min_length=1),
    n_results: int = Query(default=5, ge=1, le=50),
) -> list[SearchResult]:
    hits = vector_store.search(q, n_results=n_results)
    results = []
    for item_id, distance in hits:
        item = item_service.get_item(item_id)
        if item is not None:
            results.append(SearchResult(item=item, score=distance))
    return sorted(results, key=lambda r: r.score)
