"""
update_news.py — merge classified items into data/news.json and recompute
data/trends.json.

news.json keeps a rolling 14 days of items (capped at 800) — enough history
for the trend baseline without bloating the fetch.

Trend math: for every company/topic, compare today's mention count to the
trailing 14-day daily average. score = today / max(avg, 0.5). Entities with
score >= 2 and today >= 3 are "spiking".
"""

import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
NEWS = ROOT / "data" / "news.json"
TRENDS = ROOT / "data" / "trends.json"
CLASSIFIED = Path(__file__).parent / "out" / "news_classified.json"

KEEP_DAYS = 14
CAP = 800


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def merge_news() -> list[dict]:
    doc = json.loads(NEWS.read_text()) if NEWS.exists() else {"meta": {}, "items": []}
    new = json.loads(CLASSIFIED.read_text()) if CLASSIFIED.exists() else []

    seen_ids = {i["id"] for i in doc["items"]}
    seen_urls = {i["url"] for i in doc["items"]}
    added = 0
    for rec in new:
        if rec["id"] in seen_ids or rec["url"] in seen_urls:
            continue
        doc["items"].append(rec)
        added += 1

    cutoff = (now_utc() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    doc["items"] = [i for i in doc["items"] if i["ts"] >= cutoff]
    doc["items"].sort(key=lambda x: x["ts"], reverse=True)
    doc["items"] = doc["items"][:CAP]
    doc["meta"] = {"last_updated": now_utc().isoformat(),
                   "item_count": len(doc["items"]), "added_last_run": added}
    NEWS.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"[update_news] +{added} new, {len(doc['items'])} total")
    return doc["items"]


def compute_trends(items: list[dict]) -> None:
    today = now_utc().date()
    daily: dict[str, Counter] = defaultdict(Counter)  # entity -> {date: count}
    for it in items:
        d = it["ts"][:10]
        for c in it.get("companies", []):
            daily[c][d] += 1

    trends = []
    for entity, counts in daily.items():
        today_n = counts.get(today.isoformat(), 0)
        history = [counts.get((today - dt.timedelta(days=k)).isoformat(), 0)
                   for k in range(1, KEEP_DAYS)]
        avg = sum(history) / max(len(history), 1)
        score = today_n / max(avg, 0.5)
        trends.append({
            "entity": entity,
            "today": today_n,
            "avg": round(avg, 2),
            "score": round(score, 2),
            "spiking": bool(score >= 2 and today_n >= 3),
            "spark": list(reversed(history))[-7:] + [today_n],  # last 8 days
        })
    trends.sort(key=lambda t: (t["spiking"], t["score"], t["today"]), reverse=True)
    TRENDS.write_text(json.dumps(
        {"meta": {"last_updated": now_utc().isoformat()}, "trends": trends[:25]},
        indent=1, ensure_ascii=False))
    print(f"[update_news] trends computed for {len(trends)} entities "
          f"({sum(t['spiking'] for t in trends)} spiking)")


if __name__ == "__main__":
    items = merge_news()
    compute_trends(items)
