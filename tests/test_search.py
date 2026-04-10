from datetime import date, timedelta


def _future_date(days=10):
    return (date.today() + timedelta(days=days)).isoformat()


def test_semantic_search(client):
    client.post("/api/v1/items", json={"name": "Greek yogurt", "category": "dairy", "expires_at": _future_date()})
    client.post("/api/v1/items", json={"name": "Whole milk", "category": "dairy", "expires_at": _future_date()})
    client.post("/api/v1/items", json={"name": "Raw chicken breast", "category": "meat", "expires_at": _future_date()})

    resp = client.get("/api/v1/search", params={"q": "something for breakfast", "n_results": 2})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) <= 2
    for r in results:
        assert "item" in r
        assert "score" in r


def test_search_empty(client):
    resp = client.get("/api/v1/search", params={"q": "milk"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_after_delete(client):
    resp = client.post("/api/v1/items", json={"name": "Milk", "category": "dairy", "expires_at": _future_date()})
    item_id = resp.json()["id"]

    resp = client.get("/api/v1/search", params={"q": "milk"})
    assert len(resp.json()) == 1

    client.delete(f"/api/v1/items/{item_id}")

    resp = client.get("/api/v1/search", params={"q": "milk"})
    assert len(resp.json()) == 0
