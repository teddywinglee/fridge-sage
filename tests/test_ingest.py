from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


def _llm_response(items: list[dict]) -> MagicMock:
    """Build a mock that looks like an openai Responses API result."""
    import json
    mock = MagicMock()
    mock.output_text = json.dumps(items)
    return mock


def _mock_client(items: list[dict]):
    client = MagicMock()
    client.responses.create.return_value = _llm_response(items)
    return client


# ---------------------------------------------------------------------------
# Single item
# ---------------------------------------------------------------------------

def test_ingest_single_item(client):
    llm_items = [{"name": "milk", "category": "dairy", "quantity": 1, "unit": "gallon", "notes": None}]
    with patch("app.services.ingest_service._get_client", return_value=_mock_client(llm_items)):
        resp = client.post("/api/v1/ingest", json={"text": "I bought a gallon of milk"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["raw_text"] == "I bought a gallon of milk"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["name"] == "milk"
    assert item["category"] == "dairy"
    assert item["quantity"] == 1
    assert item["unit"] == "gallon"

    # Expiration should use the shelf-life lookup for "milk" (7 days)
    expected_expires = (date.today() + timedelta(days=7)).isoformat()
    assert item["expires_at"] == expected_expires


# ---------------------------------------------------------------------------
# Multi-item
# ---------------------------------------------------------------------------

def test_ingest_multiple_items(client):
    llm_items = [
        {"name": "eggs", "category": "dairy", "quantity": 12, "unit": None, "notes": None},
        {"name": "chicken breast", "category": "meat", "quantity": 2, "unit": "lb", "notes": None},
    ]
    with patch("app.services.ingest_service._get_client", return_value=_mock_client(llm_items)):
        resp = client.post("/api/v1/ingest", json={"text": "a dozen eggs and 2 lb of chicken breast"})

    assert resp.status_code == 201
    body = resp.json()
    assert len(body["items"]) == 2

    names = {i["name"] for i in body["items"]}
    assert names == {"eggs", "chicken breast"}

    # Verify items were persisted — they should show up in /items
    items_resp = client.get("/api/v1/items")
    assert items_resp.status_code == 200
    persisted_names = {i["name"] for i in items_resp.json()}
    assert "eggs" in persisted_names
    assert "chicken breast" in persisted_names


# ---------------------------------------------------------------------------
# Shelf-life lookup
# ---------------------------------------------------------------------------

def test_shelf_life_lookup_hit():
    from app.services.ingest_service import _estimate_expiration
    result = _estimate_expiration("whole milk")
    assert result == date.today() + timedelta(days=7)


def test_shelf_life_lookup_case_insensitive():
    from app.services.ingest_service import _estimate_expiration
    result = _estimate_expiration("Fresh Salmon Fillet")
    assert result == date.today() + timedelta(days=2)


def test_shelf_life_default_fallback():
    from app.services.ingest_service import _estimate_expiration, settings
    result = _estimate_expiration("mystery ingredient xyz")
    assert result == date.today() + timedelta(days=settings.ingest_default_shelf_life_days)


# ---------------------------------------------------------------------------
# Events are logged
# ---------------------------------------------------------------------------

def test_ingest_logs_item_added_event(client):
    llm_items = [{"name": "leftover pasta", "category": "leftover", "quantity": 1, "unit": None, "notes": None}]
    with patch("app.services.ingest_service._get_client", return_value=_mock_client(llm_items)):
        ingest_resp = client.post("/api/v1/ingest", json={"text": "leftover pasta from last night"})

    item_id = ingest_resp.json()["items"][0]["id"]
    events_resp = client.get(f"/api/v1/events?item_id={item_id}")
    assert events_resp.status_code == 200
    event_types = [e["event_type"] for e in events_resp.json()]
    assert "ITEM_ADDED" in event_types


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

def test_ingest_malformed_json_returns_422(client):
    client_mock = MagicMock()
    client_mock.responses.create.return_value.output_text = "not valid json at all"
    with patch("app.services.ingest_service._get_client", return_value=client_mock):
        resp = client.post("/api/v1/ingest", json={"text": "some groceries"})
    assert resp.status_code == 422


def test_ingest_llm_returns_object_not_array_returns_422(client):
    import json
    client_mock = MagicMock()
    client_mock.responses.create.return_value.output_text = json.dumps({"name": "milk"})
    with patch("app.services.ingest_service._get_client", return_value=client_mock):
        resp = client.post("/api/v1/ingest", json={"text": "some groceries"})
    assert resp.status_code == 422


def test_ingest_llm_connection_error_returns_503(client):
    import openai
    with patch("app.services.ingest_service._get_client") as mock_get:
        mock_get.return_value.responses.create.side_effect = openai.APIConnectionError(request=MagicMock())
        resp = client.post("/api/v1/ingest", json={"text": "some groceries"})
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_ingest_text_too_short_returns_422(client):
    resp = client.post("/api/v1/ingest", json={"text": "ab"})
    assert resp.status_code == 422


def test_ingest_markdown_fenced_json(client):
    """LLM sometimes wraps JSON in ```json ... ``` — should be stripped."""
    import json
    raw = [{"name": "butter", "category": "dairy", "quantity": 1, "unit": "stick", "notes": None}]
    fenced = f"```json\n{json.dumps(raw)}\n```"
    client_mock = MagicMock()
    client_mock.responses.create.return_value.output_text = fenced
    with patch("app.services.ingest_service._get_client", return_value=client_mock):
        resp = client.post("/api/v1/ingest", json={"text": "a stick of butter"})
    assert resp.status_code == 201
    assert resp.json()["items"][0]["name"] == "butter"
