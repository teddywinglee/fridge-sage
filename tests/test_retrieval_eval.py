from datetime import date, timedelta

from app.services import ask_service


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

# Each case: question + which item names must appear in retrieved sources (any one suffices).
EVAL_CASES = [
    {
        "question": "What dairy products do I have?",
        "expected": ["Whole Milk", "Cheddar Cheese"],
    },
    {
        "question": "Do I have anything to drink?",
        "expected": ["Orange Juice"],
    },
    {
        "question": "What protein do I have?",
        "expected": ["Chicken Breast"],
    },
    {
        "question": "What should I use up before it expires?",
        "expected": ["Chicken Breast", "Leftover Pasta"],
    },
    {
        "question": "What has already gone bad?",
        "expected": ["Expired Yogurt"],
    },
]

PASS_THRESHOLD = 0.80


def test_retrieval_hit_rate(client):
    name_to_id = {}
    for item in SEED_ITEMS:
        r = client.post("/api/v1/items", json=item)
        assert r.status_code == 201
        name_to_id[r.json()["name"]] = r.json()["id"]

    hits = 0
    misses = []

    for case in EVAL_CASES:
        _, source_ids = ask_service._retrieve_context(case["question"])
        retrieved = {name for name, id_ in name_to_id.items() if id_ in source_ids}
        hit = any(exp in retrieved for exp in case["expected"])
        if hit:
            hits += 1
        else:
            misses.append({
                "question": case["question"],
                "expected": case["expected"],
                "got": sorted(retrieved),
            })

    if misses:
        for m in misses:
            print(f"\nMISS: '{m['question']}'")
            print(f"  expected any of: {m['expected']}")
            print(f"  retrieved:       {m['got']}")

    hit_rate = hits / len(EVAL_CASES)
    print(f"\nRetrieval hit rate: {hit_rate:.0%} ({hits}/{len(EVAL_CASES)})")
    assert hit_rate >= PASS_THRESHOLD, f"Hit rate {hit_rate:.0%} below {PASS_THRESHOLD:.0%} threshold"
