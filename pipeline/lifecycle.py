"""
lifecycle.py — tag deal-related news with confirmation status (Haiku).

Runs after classify.py. Items with deal-ish tags (M&A / IPO / Capital Raise)
get a deal_status: rumor | talks | announced | closed | terminated | not_deal,
plus status_confidence. Rumor -> announced transitions are the interesting
signal; the news UI shows the tag.

Model: VERIFY_MODEL (Haiku-class) — fixed-label classification at volume.
"""

import json
import os
from pathlib import Path

OUT = Path(__file__).parent / "out"
MODEL = os.environ.get("VERIFY_MODEL", "claude-haiku-4-5")
BATCH = 20
DEAL_TAGS = {"M&A", "IPO", "Capital Raise"}

SYSTEM = """You classify deal-related headlines by confirmation status. You receive a JSON
array of items (title + snippet). Respond with ONLY a JSON array of the same
length, no prose.

For each item:
{
 "status": "rumor" | "talks" | "announced" | "closed" | "terminated" | "not_deal",
 "confidence": "high" | "low"
}

Definitions — apply mechanically:
- rumor: unnamed sources, "reportedly", "said to be", "exploring", no company confirmation.
- talks: named parties confirm discussions but no agreement ("in advanced talks").
- announced: definitive agreement, signed deal, priced offering.
- closed: completion language ("completed", "closed the acquisition").
- terminated: deal abandoned, rejected, or blocked.
- not_deal: anything else (earnings, products, partnerships without equity).

Rules:
1. Judge ONLY from the given text. "Reportedly agreed" is still rumor.
2. confidence:"low" whenever the text is ambiguous between two labels.
3. Same array length as input, same order. No other fields."""


def needs_tag(item: dict) -> bool:
    """Pure: does this classified news item warrant a lifecycle tag?"""
    return bool(DEAL_TAGS & set(item.get("ib_tags", [])))


def parse_labels(text: str, expected: int) -> list[dict] | None:
    """Pure: parse Haiku output; None on any shape problem (fail open, no tags)."""
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        labels = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(labels, list) or len(labels) != expected:
        return None
    valid = {"rumor", "talks", "announced", "closed", "terminated", "not_deal"}
    return [l if isinstance(l, dict) and l.get("status") in valid
            else {"status": "not_deal", "confidence": "low"} for l in labels]


def run() -> None:
    import anthropic
    src = OUT / "news_classified.json"
    if not src.exists():
        print("[lifecycle] nothing classified this run")
        return
    items = json.loads(src.read_text())
    todo = [i for i in items if needs_tag(i)]
    client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    tagged = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        slim = [{"title": b["title"], "snippet": b.get("summary", "")[:250]} for b in batch]
        try:
            msg = client.messages.create(
                model=MODEL, max_tokens=1200, system=SYSTEM,
                messages=[{"role": "user", "content": json.dumps(slim, ensure_ascii=False)}])
            text = "".join(b.text for b in msg.content if b.type == "text")
        except anthropic.APIError as e:
            print(f"[lifecycle] batch failed: {e}")
            continue
        labels = parse_labels(text, len(batch))
        if labels is None:
            continue
        for item, lab in zip(batch, labels):
            if lab["status"] != "not_deal":
                item["deal_status"] = lab["status"]
                item["status_confidence"] = lab["confidence"]
                tagged += 1
    src.write_text(json.dumps(items, indent=1, ensure_ascii=False))
    print(f"[lifecycle] tagged {tagged}/{len(todo)} deal-related items")


if __name__ == "__main__":
    run()
