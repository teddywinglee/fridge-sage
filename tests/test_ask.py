from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import openai
import pytest


def _future_date(days=10):
    return (date.today() + timedelta(days=days)).isoformat()


def _past_date(days=5):
    return (date.today() - timedelta(days=days)).isoformat()


def _mock_llm_response(text: str):
    """Returns a mock that mimics openai Responses API output."""
    mock_client = MagicMock()
    mock_client.responses.create.return_value = SimpleNamespace(output_text=text)
    return mock_client


def test_ask_basic_question(client):
    client.post("/api/v1/items", json={"name": "Cheddar", "category": "dairy", "expires_at": _future_date(10)})
    with patch("app.services.ask_service._get_client", return_value=_mock_llm_response("You have Cheddar cheese.")):
        resp = client.post("/api/v1/ask", json={"question": "What dairy do I have?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data
    assert data["answer"] == "You have Cheddar cheese."
    assert len(data["sources"]) > 0


def test_ask_expiring_soon(client):
    client.post("/api/v1/items", json={"name": "Yogurt", "category": "dairy", "expires_at": _future_date(2)})
    client.post("/api/v1/items", json={"name": "Apples", "category": "fruit", "expires_at": _future_date(30)})

    captured = {}

    def fake_create(**kwargs):
        captured["instructions"] = kwargs.get("instructions", "")
        return SimpleNamespace(output_text="Yogurt expires in 2 days.")

    mock_client = MagicMock()
    mock_client.responses.create.side_effect = fake_create

    with patch("app.services.ask_service._get_client", return_value=mock_client):
        resp = client.post("/api/v1/ask", json={"question": "What is expiring soon?"})

    assert resp.status_code == 200
    assert "Yogurt" in captured["instructions"]


def test_ask_empty_fridge(client):
    with patch("app.services.ask_service._get_client", return_value=_mock_llm_response("The fridge is empty.")):
        resp = client.post("/api/v1/ask", json={"question": "What do I have?"})
    assert resp.status_code == 200
    # context should mention empty fridge
    assert resp.json()["answer"] == "The fridge is empty."


def test_ask_question_too_short(client):
    resp = client.post("/api/v1/ask", json={"question": "hi"})
    assert resp.status_code == 422


def test_ask_question_too_long(client):
    resp = client.post("/api/v1/ask", json={"question": "a" * 501})
    assert resp.status_code == 422


def test_ask_server_down(client):
    client.post("/api/v1/items", json={"name": "Milk", "expires_at": _future_date()})

    mock_client = MagicMock()
    mock_client.responses.create.side_effect = openai.APIConnectionError(request=MagicMock())

    with patch("app.services.ask_service._get_client", return_value=mock_client):
        resp = client.post("/api/v1/ask", json={"question": "What do I have?"})

    assert resp.status_code == 503
