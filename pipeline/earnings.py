"""
earnings.py — IB-style earnings notes for watchlist companies.

Scans this run's classified news for Earnings-tagged items about watchlist
companies (importance >= 2), generates a structured note per the earnings
prompt, and stores them in data/earnings.json (rolling 90 days). Surfaced on
each company's dossier page.

Model: Sonnet — structured summarization with domain rules.
"""

import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = Path(__file__).parent / "out"
STORE = ROOT / "data" / "earnings.json"
MODEL = os.environ.get("EXTRACT_MODEL", "claude-sonnet-4-6")

SYSTEM = """You write earnings notes for an investment-banking analyst covering technology
and semiconductors. You receive the text of an earnings press release or 8-K,
plus the company name and ticker.

Write a note in EXACTLY this markdown structure:

**{Company} ({ticker}) — {quarter} results**
**The number:** one line — revenue and EPS vs. expectations IF the release
states consensus or prior guidance; otherwise report growth rates only and say
"vs. consensus: not stated in release."
**Guidance:** raised / lowered / maintained / not given, with the specific
figures quoted from the release.
**Capex & AI read-through:** 1-2 sentences on anything relevant to data-center,
AI, or semiconductor demand (capex plans, AI revenue, supply comments). If
nothing, write "No AI/capex read-through this quarter."
**Morning-meeting line:** one sentence a banker would actually say — the
so-what for deal activity, financing needs, or sector sentiment.

Rules:
1. Use ONLY numbers that appear in the provided text. Never estimate consensus
   or fill in figures from memory.
2. Quote figures with their period (e.g., "Q2 revenue $8.1B, +31% y/y").
3. If the release is not an earnings release, respond only: NOT_EARNINGS.
4. Total length under 150 words. No preamble, no sign-off."""


def watchlist_names() -> set:
    cfg = json.loads((ROOT / "config" / "watchlist.json").read_text())
    names = {w["name"] for w in cfg.get("watchlist", [])}
    names |= {c["name"] for c in cfg.get("korea", {}).get("companies", [])}
    return names


def select_items(classified: list[dict], watch: set) -> list[dict]:
    """Pure: which classified items deserve an earnings note?"""
    return [i for i in classified
            if "Earnings" in i.get("ib_tags", [])
            and i.get("importance", 1) >= 2
            and set(i.get("companies", [])) & watch]


def run() -> None:
    import anthropic
    src = OUT / "news_classified.json"
    if not src.exists():
        print("[earnings] no classified items this run")
        return
    items = select_items(json.loads(src.read_text()), watchlist_names())
    if not items:
        print("[earnings] no watchlist earnings items this run")
        return

    doc = json.loads(STORE.read_text()) if STORE.exists() else {"notes": []}
    seen = {n["source_title"] for n in doc["notes"]}
    client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    added = 0
    for it in items:
        if it["title"] in seen:
            continue
        company = (it.get("companies") or ["Unknown"])[0]
        user = (f"Company: {company}\n"
                f"Release/report text:\n{it['title']}\n{it.get('summary','')}")
        msg = client.messages.create(
            model=MODEL, max_tokens=400, system=SYSTEM,
            messages=[{"role": "user", "content": user}])
        md = "".join(b.text for b in msg.content if b.type == "text").strip()
        if md == "NOT_EARNINGS" or not md:
            continue
        doc["notes"].insert(0, {"company": company, "date": it["ts"][:10],
                                "markdown": md, "source_title": it["title"],
                                "source_url": it.get("url", "")})
        added += 1

    cutoff = (dt.date.today() - dt.timedelta(days=90)).isoformat()
    doc["notes"] = [n for n in doc["notes"] if n["date"] >= cutoff][:100]
    doc["meta"] = {"last_updated": dt.datetime.now(dt.timezone.utc).isoformat()}
    STORE.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"[earnings] {added} note(s) added, {len(doc['notes'])} on file")


if __name__ == "__main__":
    run()
