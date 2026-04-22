import json
import re
from datetime import date, timedelta

import openai

from app.config import settings
from app.models import IngestRequest, IngestResponse, ItemCreate, ItemResponse
from app.services import item_service

# Typical refrigerator shelf life in days for common food keywords.
# Matched via case-insensitive substring against the item name.
SHELF_LIFE_DAYS: dict[str, int] = {
    "milk": 7,
    "cream": 7,
    "yogurt": 14,
    "butter": 30,
    "cheese": 21,
    "egg": 21,
    "chicken": 2,
    "turkey": 2,
    "beef": 3,
    "pork": 3,
    "fish": 2,
    "shrimp": 2,
    "salmon": 2,
    "tuna": 2,
    "bacon": 7,
    "sausage": 4,
    "ham": 5,
    "tofu": 5,
    "lettuce": 7,
    "spinach": 5,
    "kale": 7,
    "broccoli": 5,
    "carrot": 14,
    "celery": 14,
    "cucumber": 7,
    "tomato": 5,
    "pepper": 7,
    "mushroom": 5,
    "strawberr": 3,
    "blueberr": 7,
    "raspberr": 3,
    "grape": 7,
    "apple": 30,
    "orange": 14,
    "lemon": 14,
    "lime": 14,
    "avocado": 3,
    "melon": 5,
    "juice": 7,
    "leftover": 4,
    "soup": 4,
    "sauce": 7,
    "salsa": 14,
    "hummus": 7,
    "dressing": 30,
    "mayo": 60,
    "ketchup": 60,
    "mustard": 60,
    "jam": 30,
    "jelly": 30,
}

_SYSTEM_PROMPT = """\
You are a refrigerator inventory parser. The user will describe what food items they bought or have.
Extract each distinct item and return ONLY a JSON array with no other text or commentary.

Each element must be a JSON object with these fields:
- "name": string, the food item name (singular or plural as appropriate, e.g. "eggs", "milk", "chicken breast")
- "category": one of "produce", "dairy", "meat", "seafood", "beverage", "condiment", "leftover", "other"
- "quantity": integer (default 1)
- "unit": string or null (e.g. "gallon", "lb", "bunch", "dozen") — use null if not specified
- "notes": string or null — any relevant detail (e.g. "organic", "low-fat", "opened")

Rules:
- Return a JSON array even for a single item: [{"name": ...}]
- Do not include expires_at or any date fields
- If quantity is described as "a dozen eggs", return name "eggs", quantity 12, unit null
- Combine duplicates into one entry with summed quantity
"""


def _get_client() -> openai.OpenAI:
    return openai.OpenAI(base_url=settings.ask_base_url, api_key="local")


def _estimate_expiration(name: str) -> date:
    name_lower = name.lower()
    for keyword, days in SHELF_LIFE_DAYS.items():
        if keyword in name_lower:
            return date.today() + timedelta(days=days)
    return date.today() + timedelta(days=settings.ingest_default_shelf_life_days)


def _parse_with_llm(text: str) -> list[dict]:
    client = _get_client()
    response = client.responses.create(
        model=settings.ask_model,
        instructions=_SYSTEM_PROMPT,
        input=text,
        max_output_tokens=512,
    )
    raw = response.output_text.strip()

    # Strip markdown code fences if the LLM wraps the JSON
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array from LLM, got: {type(parsed)}")
    return parsed


def ingest(request: IngestRequest) -> IngestResponse:
    parsed_items = _parse_with_llm(request.text)

    created: list[ItemResponse] = []
    for raw in parsed_items:
        expires_at = _estimate_expiration(raw.get("name", ""))
        item_data = ItemCreate(
            name=raw["name"],
            category=raw.get("category"),
            quantity=int(raw.get("quantity") or 1),
            unit=raw.get("unit"),
            expires_at=expires_at,
            notes=raw.get("notes"),
        )
        created.append(item_service.create_item(item_data))

    return IngestResponse(items=created, raw_text=request.text)
