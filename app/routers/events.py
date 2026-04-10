from fastapi import APIRouter, Query

from app.models import EventResponse
from app.services import event_service

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
def list_events(
    item_id: str | None = None,
    event_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[EventResponse]:
    return event_service.list_events(
        item_id=item_id, event_type=event_type, limit=limit
    )
