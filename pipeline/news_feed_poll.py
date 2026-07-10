"""
news_feed_poll.py — pull tech/semis headlines for the news & trends app.

Sources:
  * Google News RSS, one query per watchlist company and per topic
    (free, no key, covers essentially every outlet)
  * Direct RSS feeds listed in config/watchlist.json

Dedupe/clustering: the same story arrives from many outlets. We cluster
headlines whose normalized word sets overlap heavily (Jaccard >= 0.55),
keep the earliest as the lead, and attach the rest as extra sources.

Output: pipeline/out/news_candidates.json for classify.py.
Stdlib only, same as news_poll.py, so it runs anywhere.
"""

import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = Path(__file__).parent / "out"
CONFIG = json.loads((ROOT / "config" / "watchlist.json").read_text())

STOP = set("the a an and or of to in on for with as at by from its is are "
           "says say said new after amid over up down report reports".split())


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "DealTracker-News/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse_rss(xml_bytes: bytes, tag_hint: str) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items
    for it in root.iter("item"):
        get = lambda t: (it.findtext(t) or "").strip()
        pub = get("pubDate")
        try:
            ts = parsedate_to_datetime(pub).astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            ts = datetime.now(timezone.utc).isoformat()
        title = re.sub(r"\s+", " ", get("title"))
        # Google News appends " - Outlet"; split it into a source field
        source = get("source") or (title.rsplit(" - ", 1)[1] if " - " in title else "")
        items.append({
            "title": title.rsplit(" - ", 1)[0] if " - " in title else title,
            "url": get("link"),
            "published": ts,
            "outlet": source,
            "hint": tag_hint,
            "snippet": re.sub(r"<[^>]+>", " ", get("description"))[:800],
        })
    return items


def _stem(w: str) -> str:
    """Crude suffix stemming: acquires/acquired/acquiring -> acquir."""
    for suf in ("ing", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def word_set(title: str) -> frozenset:
    words = re.findall(r"[a-z0-9']+", title.lower())
    return frozenset(_stem(w) for w in words if w not in STOP and len(w) > 2)


def cluster(items: list[dict]) -> list[dict]:
    """Greedy clustering by headline word overlap."""
    clusters: list[dict] = []
    for it in sorted(items, key=lambda x: x["published"]):
        ws = word_set(it["title"])
        if not ws:
            continue
        placed = False
        for c in clusters:
            inter = len(ws & c["_ws"])
            union = len(ws | c["_ws"])
            if union and inter / union >= 0.55:
                c["also"].append({"outlet": it["outlet"], "url": it["url"]})
                c["_ws"] = c["_ws"] | ws
                placed = True
                break
        if not placed:
            clusters.append({**it, "also": [], "_ws": ws})
    for c in clusters:
        del c["_ws"]
        c["source_count"] = 1 + len(c["also"])
    return clusters


def run(hours_back: int = 6) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    raw: list[dict] = []

    tmpl = CONFIG["google_news_template"]
    queries = [w["name"] for w in CONFIG["watchlist"]] + CONFIG["topics"]
    for q in queries:
        url = tmpl.format(query=urllib.parse.quote(q))
        try:
            raw += parse_rss(fetch(url), tag_hint=q)
        except Exception as e:  # noqa: BLE001
            print(f"[news_feed_poll] failed query '{q}': {e}", file=sys.stderr)

    for feed in CONFIG["feeds"]:
        try:
            raw += parse_rss(fetch(feed), tag_hint="")
        except Exception as e:  # noqa: BLE001
            print(f"[news_feed_poll] failed feed {feed}: {e}", file=sys.stderr)

    raw = [r for r in raw if r["published"] >= cutoff]
    clusters = cluster(raw)

    OUT.mkdir(exist_ok=True)
    path = OUT / "news_candidates.json"
    path.write_text(json.dumps(clusters, indent=1, ensure_ascii=False))
    print(f"[news_feed_poll] {len(raw)} raw items -> {len(clusters)} clusters -> {path}")
    return clusters


if __name__ == "__main__":
    run(hours_back=int(sys.argv[1]) if len(sys.argv) > 1 else 6)
