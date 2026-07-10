"""
memo.py — the weekly sector memo (Opus-class, Fridays).

Synthesizes the week's tracked news, deals, and trends into a client-style
industry update. Stored in data/memo.json (last 8 weeks) and rendered by
memo.html. One call a week — quality over cost, hence the senior model.
"""

import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEMO = ROOT / "data" / "memo.json"
MODEL = os.environ.get("MEMO_MODEL", "claude-opus-4-8")

SYSTEM = """You are a senior technology investment banker writing the weekly sector update
memo your team sends to clients. You receive JSON context: the week's tracked
news items (with categories, companies, importance), deal records added or
updated this week, and trend data.

Audience: corporate development heads and CFOs at tech companies. They are
smart, busy, and allergic to filler.

Write a one-page memo (450-600 words) in markdown:
- A title that names the week's actual theme (never "Weekly Update").
- An opening paragraph that frames the theme with the two or three strongest
  data points from the context.
- "## Deal activity" — the week's transactions with values and the pattern they
  form, if any. If the week was quiet, say so plainly and explain what the
  silence itself suggests.
- "## Capital markets" — IPOs, follow-ons, converts, credit color from the context.
- "## What we're watching" — 2-3 forward-looking items grounded in the context
  (pending closings, filed IPOs, regulatory dates), not speculation.

Quality bar and constraints:
- Every factual claim must trace to the provided context. If the context is
  thin on a section, write less rather than padding.
- Numbers over adjectives. "Three take-privates totaling $70B" beats
  "significant take-private activity."
- One idea per paragraph. No bullet-point spam — this is prose a person wrote.
- Never invent client-specific advice, price targets, or predictions with
  false precision.
- Close with a single-sentence bottom line, not a summary of the summary."""


def build_context(days: int = 7) -> dict:
    """Pure-ish (reads files): the week's material for the memo."""
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(days=days)).isoformat()
    news_f = ROOT / "data" / "news.json"
    deals_f = ROOT / "data" / "deals.json"
    trends_f = ROOT / "data" / "trends.json"

    news = json.loads(news_f.read_text())["items"] if news_f.exists() else []
    week_news = [{"title": n["title"], "summary": n.get("summary", ""),
                  "category": n["category"], "companies": n.get("companies", []),
                  "importance": n.get("importance", 1),
                  "deal_status": n.get("deal_status")}
                 for n in news if n["ts"] >= cutoff][:60]

    deals = json.loads(deals_f.read_text())["deals"] if deals_f.exists() else []
    week_cut = (now - dt.timedelta(days=days)).date().isoformat()
    week_deals = [{"name": d["name"], "type": d["type"], "v": d.get("v"),
                   "status": d.get("status"), "sector": d.get("sector"),
                   "note": d.get("note", "")[:200]}
                  for d in deals if d.get("d", "") >= week_cut][:15]

    trends = json.loads(trends_f.read_text())["trends"] if trends_f.exists() else []
    return {"week_of": now.date().isoformat(), "news": week_news,
            "deals": week_deals, "trends": trends[:10]}


def run() -> None:
    import anthropic
    ctx = build_context()
    if not ctx["news"] and not ctx["deals"]:
        print("[memo] empty week — skipping memo")
        return
    client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    msg = client.messages.create(
        model=MODEL, max_tokens=1400, system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}])
    md = "".join(b.text for b in msg.content if b.type == "text").strip()

    doc = json.loads(MEMO.read_text()) if MEMO.exists() else {"memos": []}
    wk = ctx["week_of"]
    doc["memos"] = [m for m in doc["memos"] if m["week"] != wk]
    doc["memos"].insert(0, {"week": wk, "markdown": md,
                            "generated": dt.datetime.now(dt.timezone.utc).isoformat()})
    doc["memos"] = doc["memos"][:8]
    doc["meta"] = {"last_updated": dt.datetime.now(dt.timezone.utc).isoformat()}
    MEMO.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"[memo] wrote sector memo for week of {wk} ({len(md)} chars)")


if __name__ == "__main__":
    run()
