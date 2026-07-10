"""
news_poll.py — pull tech-deal headlines from RSS feeds.

EDGAR misses most private-target M&A (the bulk of AI deals), so we supplement
with news feeds and keyword-filter headlines before handing them to extract.py.
Uses only the standard library so it runs anywhere.
"""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).parent / "out"

FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.prnewswire.com/rss/financial-services-latest-news/acquisitions-mergers-and-takeovers-list.rss",
    "https://www.globenewswire.com/RssFeed/subjectcode/24-Mergers%2520And%2520Acquisitions/feedTitle/GlobeNewswire%2520-%2520Mergers%2520and%2520Acquisitions",
]

DEAL_RE = re.compile(
    r"\b(acquir\w+|merger|to buy|buys|takeover|take[- ]private|"
    r"IPO|initial public offering|files to go public|S-1|prices? (its )?offering|"
    r"follow-on|convertible (senior )?notes|secondary offering|registered direct)\b",
    re.I,
)
TECH_RE = re.compile(
    r"\b(AI|artificial intelligence|software|cloud|cyber|semiconductor|chip|"
    r"SaaS|fintech|crypto|quantum|data center|datacenter|platform|app|tech)\b",
    re.I,
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "DealTracker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse_items(xml_bytes: bytes) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items
    for item in root.iter("item"):
        get = lambda tag: (item.findtext(tag) or "").strip()
        items.append({
            "title": get("title"),
            "url": get("link"),
            "published": get("pubDate"),
            "snippet": re.sub(r"<[^>]+>", " ", get("description"))[:1200],
        })
    return items


def run() -> list[dict]:
    candidates = []
    for feed in FEEDS:
        try:
            for it in parse_items(fetch(feed)):
                text = f"{it['title']} {it['snippet']}"
                if DEAL_RE.search(text) and TECH_RE.search(text):
                    candidates.append({"kind": "news", "source": "rss", **it})
        except Exception as e:  # noqa: BLE001 — feed failures shouldn't kill the run
            print(f"[news_poll] failed {feed}: {e}", file=sys.stderr)

    OUT.mkdir(exist_ok=True)
    path = OUT / "candidates_news.json"
    path.write_text(json.dumps(candidates, indent=1))
    print(f"[news_poll] wrote {len(candidates)} candidates -> {path}")
    return candidates


if __name__ == "__main__":
    run()
