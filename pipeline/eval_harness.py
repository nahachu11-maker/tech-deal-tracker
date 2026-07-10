"""
eval_harness.py — the regression gate for the self-improving loop.

Runs the current extraction prompt (with whatever LESSONS.md currently says)
against a fixed set of golden cases with known-correct answers, and reports
accuracy on the material fields (type, value bucket, status, is-a-deal).

Used two ways:
  * `python pipeline/eval_harness.py`          -> score current LESSONS.md
  * imported by distill.py to compare a *proposed* LESSONS.md against the
    current one, so a lesson that regresses accuracy is rejected automatically.

Golden cases live in tests/eval_cases.jsonl (seeded, then grown from real
feedback). Each line: {"source": "...", "expect": {...}} where expect may set
"skip": true for non-deals, or the material fields for real deals.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
CASES = ROOT / "tests" / "eval_cases.jsonl"
LESSONS = Path(__file__).parent / "LESSONS.md"


def load_cases() -> list[dict]:
    if not CASES.exists():
        return []
    return [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]


def value_bucket(v):
    """Compare values by magnitude bucket, not exact number — the lesson loop
    cares about right-order-of-magnitude, not penny accuracy."""
    if v is None:
        return "none"
    if v < 1:
        return "sub-billion"
    if v < 10:
        return "1-10B"
    if v < 50:
        return "10-50B"
    return "50B+"


def score_one(expected: dict, got: dict | None) -> dict:
    """Return per-field correctness for one case. Pure — no API."""
    if expected.get("skip"):
        return {"is_deal": got is None, "n": 1}
    if got is None:
        return {"is_deal": False, "type": False, "value": False, "status": False, "n": 1}
    return {
        "is_deal": True,
        "type": got.get("type") == expected.get("type"),
        "value": value_bucket(got.get("v")) == value_bucket(expected.get("v")),
        "status": got.get("status") == expected.get("status"),
        "n": 1,
    }


def aggregate(scores: list[dict]) -> dict:
    total = len(scores)
    if not total:
        return {"cases": 0, "accuracy": 1.0}
    fields = ["is_deal", "type", "value", "status"]
    hits = {f: sum(1 for s in scores if s.get(f)) for f in fields}
    checked = {f: sum(1 for s in scores if f in s) for f in fields}
    per_field = {f: (hits[f] / checked[f] if checked[f] else 1.0) for f in fields}
    overall = sum(per_field.values()) / len(per_field)
    return {"cases": total, "accuracy": round(overall, 4), "per_field": per_field}


def run_extraction(lessons_override: str | None = None) -> list[dict]:
    """Run the live extractor over golden cases. Requires ANTHROPIC_API_KEY.
    lessons_override lets distill.py test a proposed LESSONS.md without writing it."""
    import anthropic
    import extract  # reuse the real extractor

    client = anthropic.Anthropic()
    lessons = lessons_override if lessons_override is not None else extract.lessons_text()
    system = extract.SYSTEM.replace("{lessons}", lessons)

    results = []
    for case in load_cases():
        msg = client.messages.create(
            model=extract.MODEL, max_tokens=600, system=system,
            messages=[{"role": "user", "content": f"Raw item:\n{case['source']}"}])
        text = "".join(b.text for b in msg.content if b.type == "text")
        text = text.replace("```json", "").replace("```", "").strip()
        try:
            rec = json.loads(text)
            rec = None if rec.get("skip") else rec
        except json.JSONDecodeError:
            rec = None
        results.append(score_one(case["expect"], rec))
    return results


def evaluate(lessons_override: str | None = None) -> dict:
    return aggregate(run_extraction(lessons_override))


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY to run the live eval. "
              f"{len(load_cases())} golden cases loaded.")
    else:
        print(json.dumps(evaluate(), indent=2))
