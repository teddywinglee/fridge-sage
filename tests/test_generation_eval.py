"""
Generation quality eval using a local LLM as judge.

Requires a running OpenAI-compatible server (e.g. LM Studio).
Run with: uv run pytest -m llm -s

The -s flag prints per-question scores to stdout.
JUDGE_MODEL should ideally differ from ASK_MODEL to avoid self-validation bias.
"""
import json
from datetime import date, timedelta

import openai
import pytest

pytestmark = pytest.mark.llm

# Judge config — override these if your judge model differs from the ask model.
JUDGE_BASE_URL = "http://localhost:1234/v1"
JUDGE_MODEL = "gemma-4-26b-a4b-it-GGUF"

JUDGE_PROMPT = """\
You are evaluating the output of a RAG system that answers questions about refrigerator contents.

Question asked: "{question}"

Inventory context the system was given:
{context}

System's answer: "{answer}"

Rate the answer on two dimensions:
- faithfulness: does the answer only reference items present in the context above?
  1 = invented items not in context, 2 = mostly grounded with minor issues, 3 = fully grounded
- relevance: does the answer address the question asked?
  1 = off-topic or useless, 2 = partially answers, 3 = directly and helpfully answers

Respond ONLY with a JSON object, no explanation, no markdown fences:
{{"faithfulness": <1|2|3>, "relevance": <1|2|3>}}\
"""

FAITHFULNESS_THRESHOLD = 2.0
RELEVANCE_THRESHOLD = 2.0


def _future(days):
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days):
    return (date.today() - timedelta(days=days)).isoformat()


SEED_ITEMS = [
    {"name": "Whole Milk",     "category": "dairy",     "expires_at": _future(7)},
    {"name": "Cheddar Cheese", "category": "dairy",     "expires_at": _future(14)},
    {"name": "Orange Juice",   "category": "drinks",    "expires_at": _future(5)},
    {"name": "Chicken Breast", "category": "meat",      "expires_at": _future(2)},
    {"name": "Leftover Pasta", "category": "leftovers", "expires_at": _future(1)},
    {"name": "Expired Yogurt", "category": "dairy",     "expires_at": _past(3)},
]

EVAL_CASES = [
    {"question": "What dairy products do I have?"},
    {"question": "What should I use up first before it goes bad?"},
    {"question": "Is there anything expired I should throw out?"},
    {"question": "What can I make a quick meal with?"},
]


def _build_context(client, source_ids: list[str]) -> str:
    lines = []
    for item_id in source_ids:
        r = client.get(f"/api/v1/items/{item_id}")
        if r.status_code == 200:
            item = r.json()
            status = "EXPIRED" if item["is_expired"] else f"expires {item['expires_at']}"
            lines.append(
                f"- {item['name']} ({item.get('category') or 'uncategorized'}): {status}"
            )
    return "\n".join(lines) if lines else "(no items retrieved)"


def _judge(question: str, context: str, answer: str) -> dict[str, int]:
    judge_client = openai.OpenAI(base_url=JUDGE_BASE_URL, api_key="local")
    prompt = JUDGE_PROMPT.format(question=question, context=context, answer=answer)
    response = judge_client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=64,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if the model wraps its output anyway
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1]).strip()
    return json.loads(raw)


def test_generation_quality(client):
    for item in SEED_ITEMS:
        r = client.post("/api/v1/items", json=item)
        assert r.status_code == 201

    results = []
    for case in EVAL_CASES:
        r = client.post("/api/v1/ask", json={"question": case["question"]})
        assert r.status_code == 200, f"/ask failed ({r.status_code}): {r.text}"

        data = r.json()
        answer = data["answer"]
        context = _build_context(client, data["sources"])
        scores = _judge(case["question"], context, answer)
        results.append({"question": case["question"], "answer": answer, **scores})

    print("\n--- Generation Eval Results ---")
    for result in results:
        short_answer = result["answer"][:120] + ("..." if len(result["answer"]) > 120 else "")
        print(f"\nQ: {result['question']}")
        print(f"A: {short_answer}")
        print(f"   faithfulness={result['faithfulness']}/3  relevance={result['relevance']}/3")

    avg_faithfulness = sum(r["faithfulness"] for r in results) / len(results)
    avg_relevance = sum(r["relevance"] for r in results) / len(results)
    print(f"\nAvg faithfulness: {avg_faithfulness:.1f}/3")
    print(f"Avg relevance:    {avg_relevance:.1f}/3")

    assert avg_faithfulness >= FAITHFULNESS_THRESHOLD, (
        f"Avg faithfulness {avg_faithfulness:.1f} below {FAITHFULNESS_THRESHOLD}"
    )
    assert avg_relevance >= RELEVANCE_THRESHOLD, (
        f"Avg relevance {avg_relevance:.1f} below {RELEVANCE_THRESHOLD}"
    )
