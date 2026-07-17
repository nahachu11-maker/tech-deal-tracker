"""
memo.py — the weekly sector memo (Opus-class, Fridays).

Synthesizes the week's tracked news, deals, and trends into a client-style
industry update. Stored in data/memo.json (last 8 weeks) and rendered by
memo.html. One call a week — quality over cost, hence the senior model.
"""

import datetime as dt
import json
import os
import sys
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

Voice — this matters as much as the content:
- Write like a sharp sell-side author with a thesis, not a cataloger of the
  week's inventory. Blog-energy prose in a banker's vocabulary.
- **Bold the 4-6 numbers or names the reader must not miss** — the week's
  defining figure, the biggest print, the tell. Bold is for emphasis, not
  decoration.
- Open sections with a punchy short sentence that states the takeaway, then
  support it. "The week belonged to one number: **$26.5 billion**." is the
  house cadence — declarative, concrete, a little theatrical.
- Vary sentence length; land at least one dry, witty observation per memo.
  Wit means a sharp framing of something true, never a joke for its own sake.
- Never list more than three company names in a sentence; if the week was a
  pile of small deals, name the pattern and the two best examples, and let
  the rest go.

Quality bar and constraints:
- Every factual claim must trace to the provided context. If the context is
  thin on a section, write less rather than padding.
- Numbers over adjectives. "Three take-privates totaling $70B" beats
  "significant take-private activity."
- One idea per paragraph. No bullet-point spam — this is prose a person wrote.
- Never invent client-specific advice, price targets, or predictions with
  false precision.
- Close with a single-sentence bottom line, not a summary of the summary."""


def build_context(days: int = 7, as_of: str | None = None) -> dict:
    """Pure-ish (reads files): the week's material for the memo.

    as_of (YYYY-MM-DD) rebuilds the context window for a PAST week — the 7
    days ending on that date — so a botched memo can be regenerated. Honest
    caveat: it reconstructs from whatever news/deals are still retained, so
    it's a faithful re-telling of that week, not a byte-identical replay."""
    if as_of:
        now = dt.datetime.fromisoformat(as_of).replace(tzinfo=dt.timezone.utc)
    else:
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



def complete_text(msg) -> str:
    """Join text blocks; if the response hit the token ceiling, trim back to
    the last complete sentence so a truncation never reads as a cut-off
    thought. Works for English and Korean sentence endings."""
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if getattr(msg, "stop_reason", None) == "max_tokens":
        print(f"[warn] generation hit max_tokens — trimming to last sentence "
              f"({len(text)} chars)", flush=True)
        cut = max(text.rfind(p) for p in (".", "!", "?", "\u3002", ")", "\u201d"))
        # a dangling fragment is at most one sentence; trim it if the cut
        # point is close to the end, never if it would gut the document
        if cut > 0 and (len(text) - cut) < 600:
            text = text[:cut + 1]
    return text

def run() -> None:
    import anthropic
    as_of = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MEMO_AS_OF", "")).strip() or None
    if as_of:
        print(f"[memo] regenerating memo for week ending {as_of}", flush=True)
    ctx = build_context(as_of=as_of)
    if not ctx["news"] and not ctx["deals"]:
        print("[memo] empty week — skipping memo")
        return
    client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    msg = client.messages.create(
        model=MODEL, max_tokens=2500, system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}])
    md = complete_text(msg)

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
