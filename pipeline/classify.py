"""
classify.py — classify clustered headlines with the Claude API.

Batches ~15 items per request to keep cost low (a few cents/day at
30-minute polling). Output records match news.html's schema.
Items tagged "M&A" are ALSO copied to pipeline/out/candidates_news.json
so the deal-tracker pipeline picks them up — the two apps feed each other.
"""

import datetime as dt
import json
import os
from pathlib import Path

import anthropic

import hashlib
import re as _re

OUT = Path(__file__).parent / "out"
NEWS = Path(__file__).parent.parent / "data" / "news.json"


def _norm_title(t: str) -> str:
    return _re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def known_keys() -> tuple[set, set]:
    """URLs and normalized titles already in news.json — skip re-classifying them."""
    if not NEWS.exists():
        return set(), set()
    items = json.loads(NEWS.read_text()).get("items", [])
    return ({i.get("url", "") for i in items if i.get("url")},
            {_norm_title(i.get("title", "")) for i in items})
LESSONS = Path(__file__).parent / "LESSONS.md"
MODEL = os.environ.get("EXTRACT_MODEL", "claude-sonnet-4-6")
BATCH = 15

SYSTEM = """You classify technology news for an investment-banking-oriented tracker.
You receive a JSON array of headline items. Respond with ONLY a JSON array of the
same length, no prose, no markdown fences. For each item return:
{
 "keep": true|false,          // false for sports, celebrity, how-to guides, product reviews, listicles. KEEP credible deal rumors and reports — a separate step tags their confirmation status.
 "category": "Semiconductors" | "AI & Infrastructure" | "Big Tech" | "Startups & VC" | "Markets & Macro",
 "ib_tags": [ ... ],          // subset of: "M&A","Capital Raise","IPO","Earnings","Regulatory","Product","Management","Partnership"
 "companies": ["Nvidia", ...],// canonical company names mentioned (may be empty)
 "summary": "one sentence, factual, why a banker would care",
 "importance": 1|2|3          // 3 = market-moving (mega-deal, export-control change, guidance cut); 2 = notable; 1 = routine
}
Be strict with importance 3 — at most one or two per batch. Judge only from the
given title/snippet; do not invent facts.

Accumulated lessons from past reviewed runs — follow these strictly:
{lessons}"""


def classify_batch(client: anthropic.Anthropic, batch: list[dict]) -> list[dict]:
    slim = [{"title": b["title"], "snippet": b.get("snippet", "")[:300],
             "hint": b.get("hint", "")} for b in batch]
    lessons = LESSONS.read_text()[:6000] if LESSONS.exists() else ""
    msg = client.messages.create(
        model=MODEL, max_tokens=2500, system=SYSTEM.replace("{lessons}", lessons),
        messages=[{"role": "user", "content": json.dumps(slim, ensure_ascii=False)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    text = text.replace("```json", "").replace("```", "").strip()
    labels = json.loads(text)
    if len(labels) != len(batch):
        raise ValueError(f"label count mismatch {len(labels)} != {len(batch)}")
    return labels


def run() -> list[dict]:
    client = anthropic.Anthropic()
    src = OUT / "news_candidates.json"
    candidates = json.loads(src.read_text()) if src.exists() else []
    urls, titles = known_keys()
    fresh = [x for x in candidates
             if x.get("url", "") not in urls
             and _norm_title(x.get("title", "")) not in titles]
    print(f"[classify] {len(candidates)} candidates, {len(fresh)} new after dedupe "
          f"(saved {len(candidates)-len(fresh)} redundant classifications)")
    candidates = fresh

    classified, ma_candidates = [], []
    for i in range(0, len(candidates), BATCH):
        batch = candidates[i:i + BATCH]
        try:
            labels = classify_batch(client, batch)
        except (anthropic.APIError, ValueError, json.JSONDecodeError) as e:
            print(f"[classify] batch {i//BATCH} failed, skipping: {e}")
            continue
        for item, lab in zip(batch, labels):
            if not lab.get("keep"):
                continue
            rec = {
                "id": f"{item['published'][:10]}-{hashlib.md5(item['title'].encode()).hexdigest()[:10]}",
                "ts": item["published"],
                "title": item["title"],
                "url": item["url"],
                "outlet": item.get("outlet", ""),
                "also": item.get("also", []),
                "source_count": item.get("source_count", 1),
                "category": lab.get("category", "Big Tech"),
                "ib_tags": lab.get("ib_tags", []),
                "companies": lab.get("companies", []),
                "summary": lab.get("summary", ""),
                "importance": int(lab.get("importance", 1)),
            }
            classified.append(rec)
            if "M&A" in rec["ib_tags"]:
                # feed the deal tracker: same shape news_poll.py produces
                ma_candidates.append({
                    "kind": "news", "source": "news-app", "title": rec["title"],
                    "url": rec["url"], "published": rec["ts"],
                    "snippet": rec["summary"],
                })

    (OUT / "news_classified.json").write_text(
        json.dumps(classified, indent=1, ensure_ascii=False))
    if ma_candidates:
        p = OUT / "candidates_news.json"
        existing = json.loads(p.read_text()) if p.exists() else []
        p.write_text(json.dumps(existing + ma_candidates, indent=1, ensure_ascii=False))
        print(f"[classify] routed {len(ma_candidates)} M&A items to the deal pipeline")
    print(f"[classify] {len(candidates)} clusters -> {len(classified)} kept "
          f"at {dt.datetime.now(dt.timezone.utc).isoformat()}")
    return classified


if __name__ == "__main__":
    run()
