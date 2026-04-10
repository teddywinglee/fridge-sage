from fastapi import APIRouter, HTTPException, Query

from app.models import ExtendRequest, ItemCreate, ItemResponse, ItemUpdate
from app.services import item_service

router = APIRouter(prefix="/api/v1/items", tags=["items"])


@router.post("", status_code=201)
def create_item(data: ItemCreate) -> ItemResponse:
    return item_service.create_item(data)


@router.get("")
def list_items(
    category: str | None = None,
    expired: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ItemResponse]:
    return item_service.list_items(
        category=category, expired=expired, limit=limit, offset=offset
    )


@router.get("/expired")
def get_expired_items() -> list[ItemResponse]:
    return item_service.get_expired_items()


@router.get("/expiring-soon")
def get_expiring_soon(days: int = Query(default=3, ge=1)) -> list[ItemResponse]:
    return item_service.get_expiring_soon(days=days)


@router.get("/{item_id}")
def get_item(item_id: str) -> ItemResponse:
    item = item_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}")
def update_item(item_id: str, data: ItemUpdate) -> ItemResponse:
    item = item_service.update_item(item_id, data)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: str) -> None:
    if not item_service.delete_item(item_id):
        raise HTTPException(status_code=404, detail="Item not found")


@router.post("/{item_id}/extend")
def extend_expiration(item_id: str, data: ExtendRequest) -> ItemResponse:
    item = item_service.extend_expiration(item_id, data.days)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
