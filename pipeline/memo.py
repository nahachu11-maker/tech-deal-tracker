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

Voice — this matters as much as the content. Write in the register of Scott
Galloway's newsletter: a professor-operator who is funny, blunt, numerate,
and never boring. You are not impersonating him and never mention him; you
are borrowing the technique:
- **Short declarative sentences.** Then a longer one that does the analytical
  work. Then a fragment. The rhythm is the point.
- Open with a broad observation — a pattern, a historical rhyme, a piece of
  human behavior — and land it on the week's hardest number within three
  sentences. Never open with "This week saw."
- **Bold the 4-6 numbers or claims the reader must not miss.** Bold is
  emphasis, not decoration.
- One good analogy per section, drawn from outside finance (biology, sports,
  dating markets, physics, history). It must clarify, not decorate: if the
  analogy doesn't make the economics easier to grasp, cut it.
- Take a position. "This is a bet on X, and the market is pricing Y" beats
  neutral recitation. Verdicts are welcome; false precision is not.
- Dry wit, always in service of a true observation — never a joke for its own
  sake, never snark at a named person, no profanity. This goes to clients.
- Name the pattern, not the inventory: at most three company names in a
  sentence, and if the week was a pile of small deals, give the two best
  examples and let the rest go.
- Close with one sentence that lands — a verdict or a forward-looking line
  with some teeth. Not a summary of the summary.

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
