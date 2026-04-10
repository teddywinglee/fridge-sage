import uuid
from datetime import date, datetime, timedelta, timezone

from app.database import get_db
from app.models import ItemCreate, ItemResponse, ItemUpdate
from app.services import vector_store
from app.services.event_service import log_event


def _row_to_response(row) -> ItemResponse:
    expires = date.fromisoformat(row["expires_at"])
    today = date.today()
    return ItemResponse(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        quantity=row["quantity"],
        unit=row["unit"],
        stored_at=datetime.fromisoformat(row["stored_at"]),
        expires_at=expires,
        notes=row["notes"],
        is_expired=expires < today,
        days_until_expiry=(expires - today).days,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_to_vector_store(item: ItemResponse) -> None:
    vector_store.upsert(
        item_id=item.id,
        name=item.name,
        category=item.category,
        expires_at=item.expires_at.isoformat(),
        notes=item.notes,
    )


def create_item(data: ItemCreate) -> ItemResponse:
    item_id = str(uuid.uuid4())
    now = _now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO items (id, name, category, quantity, unit, stored_at, expires_at, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item_id,
                data.name,
                data.category,
                data.quantity,
                data.unit,
                now,
                data.expires_at.isoformat(),
                data.notes,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    result = _row_to_response(row)
    _sync_to_vector_store(result)
    log_event(item_id, "ITEM_ADDED", result.model_dump(mode="json"))
    return result


def get_item(item_id: str) -> ItemResponse | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return None
    return _row_to_response(row)


def list_items(
    category: str | None = None,
    expired: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ItemResponse]:
    query = "SELECT * FROM items WHERE 1=1"
    params: list = []

    if category is not None:
        query += " AND category = ?"
        params.append(category)
    if expired is True:
        query += " AND expires_at < date('now')"
    elif expired is False:
        query += " AND expires_at >= date('now')"

    query += " ORDER BY expires_at ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_response(row) for row in rows]


def update_item(item_id: str, data: ItemUpdate) -> ItemResponse | None:
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return get_item(item_id)

    if "expires_at" in updates and updates["expires_at"] is not None:
        updates["expires_at"] = updates["expires_at"].isoformat()

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [item_id]

    with get_db() as conn:
        cursor = conn.execute(
            f"UPDATE items SET {set_clause} WHERE id = ?", values
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    result = _row_to_response(row)
    _sync_to_vector_store(result)
    log_event(item_id, "ITEM_UPDATED", result.model_dump(mode="json"))
    return result


def delete_item(item_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return False
        snapshot = _row_to_response(row).model_dump(mode="json")
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    vector_store.delete(item_id)
    log_event(item_id, "ITEM_REMOVED", snapshot)
    return True


def extend_expiration(item_id: str, days: int) -> ItemResponse | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return None
        current = date.fromisoformat(row["expires_at"])
        new_date = current + timedelta(days=days)
        now = _now()
        conn.execute(
            "UPDATE items SET expires_at = ?, updated_at = ? WHERE id = ?",
            (new_date.isoformat(), now, item_id),
        )
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    result = _row_to_response(row)
    _sync_to_vector_store(result)
    log_event(
        item_id,
        "EXPIRATION_EXTENDED",
        {"old_expires_at": current.isoformat(), "new_expires_at": new_date.isoformat(), "days": days},
    )
    return result


def get_expired_items() -> list[ItemResponse]:
    return list_items(expired=True, limit=1000)


def get_expiring_soon(days: int = 3) -> list[ItemResponse]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE expires_at >= date('now') AND expires_at <= date('now', ? || ' days') ORDER BY expires_at ASC",
            (str(days),),
        ).fetchall()
    return [_row_to_response(row) for row in rows]
