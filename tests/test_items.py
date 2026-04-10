from datetime import date, timedelta


def _future_date(days=10):
    return (date.today() + timedelta(days=days)).isoformat()


def _past_date(days=5):
    return (date.today() - timedelta(days=days)).isoformat()


def test_create_item(client):
    resp = client.post("/api/v1/items", json={
        "name": "Milk",
        "category": "dairy",
        "expires_at": _future_date(),
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Milk"
    assert data["category"] == "dairy"
    assert data["is_expired"] is False
    assert data["days_until_expiry"] == 10


def test_get_item(client):
    resp = client.post("/api/v1/items", json={
        "name": "Eggs",
        "expires_at": _future_date(),
    })
    item_id = resp.json()["id"]

    resp = client.get(f"/api/v1/items/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Eggs"


def test_get_item_not_found(client):
    resp = client.get("/api/v1/items/nonexistent")
    assert resp.status_code == 404


def test_list_items(client):
    client.post("/api/v1/items", json={"name": "Milk", "category": "dairy", "expires_at": _future_date()})
    client.post("/api/v1/items", json={"name": "Steak", "category": "meat", "expires_at": _future_date()})

    resp = client.get("/api/v1/items")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_items_filter_category(client):
    client.post("/api/v1/items", json={"name": "Milk", "category": "dairy", "expires_at": _future_date()})
    client.post("/api/v1/items", json={"name": "Steak", "category": "meat", "expires_at": _future_date()})

    resp = client.get("/api/v1/items", params={"category": "dairy"})
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Milk"


def test_list_expired_items(client):
    client.post("/api/v1/items", json={"name": "Old milk", "category": "dairy", "expires_at": _past_date()})
    client.post("/api/v1/items", json={"name": "Fresh milk", "category": "dairy", "expires_at": _future_date()})

    resp = client.get("/api/v1/items/expired")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Old milk"


def test_update_item(client):
    resp = client.post("/api/v1/items", json={"name": "Milk", "expires_at": _future_date()})
    item_id = resp.json()["id"]

    resp = client.patch(f"/api/v1/items/{item_id}", json={"name": "Oat Milk"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Oat Milk"


def test_delete_item(client):
    resp = client.post("/api/v1/items", json={"name": "Milk", "expires_at": _future_date()})
    item_id = resp.json()["id"]

    resp = client.delete(f"/api/v1/items/{item_id}")
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/items/{item_id}")
    assert resp.status_code == 404


def test_extend_expiration(client):
    resp = client.post("/api/v1/items", json={"name": "Milk", "expires_at": _future_date(5)})
    item_id = resp.json()["id"]

    resp = client.post(f"/api/v1/items/{item_id}/extend", json={"days": 7})
    assert resp.status_code == 200
    assert resp.json()["days_until_expiry"] == 12


def test_expiring_soon(client):
    client.post("/api/v1/items", json={"name": "About to expire", "expires_at": _future_date(2)})
    client.post("/api/v1/items", json={"name": "Not soon", "expires_at": _future_date(30)})

    resp = client.get("/api/v1/items/expiring-soon", params={"days": 3})
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "About to expire"


def test_events_created_on_crud(client):
    resp = client.post("/api/v1/items", json={"name": "Milk", "expires_at": _future_date()})
    item_id = resp.json()["id"]

    client.patch(f"/api/v1/items/{item_id}", json={"name": "Oat Milk"})
    client.delete(f"/api/v1/items/{item_id}")

    resp = client.get("/api/v1/events")
    events = resp.json()
    event_types = [e["event_type"] for e in events]
    assert "ITEM_ADDED" in event_types
    assert "ITEM_UPDATED" in event_types
    assert "ITEM_REMOVED" in event_types
