import json
from datetime import datetime, timezone

from app.database import get_db
from app.models import EventResponse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_response(row) -> EventResponse:
    return EventResponse(
        id=row["id"],
        item_id=row["item_id"],
        event_type=row["event_type"],
        payload=json.loads(row["payload"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def log_event(item_id: str | None, event_type: str, payload: dict) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO events (item_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
            (item_id, event_type, json.dumps(payload), _now()),
        )


def list_events(
    item_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[EventResponse]:
    query = "SELECT * FROM events WHERE 1=1"
    params: list = []

    if item_id is not None:
        query += " AND item_id = ?"
        params.append(item_id)
    if event_type is not None:
        query += " AND event_type = ?"
        params.append(event_type)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_response(row) for row in rows]
