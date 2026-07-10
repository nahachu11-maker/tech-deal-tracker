"""
extract.py — turn raw candidates (EDGAR hits, news items) into structured
deal records matching the app's schema, using the Claude API.

Requires ANTHROPIC_API_KEY in the environment.
Each extracted record:
  {d, type, name, v, val?, sector, status, note, review: true,
   source_url, extracted_at}

Records that Claude judges not to be a tech M&A/IPO/follow-on event are
dropped (the model returns "skip": true for them).
"""

import datetime as dt
import json
import os
from pathlib import Path

import anthropic

from verify import verify_record
from comps import extract_comps

OUT = Path(__file__).parent / "out"
LESSONS = Path(__file__).parent / "LESSONS.md"
MODEL = os.environ.get("EXTRACT_MODEL", "claude-sonnet-4-6")


def lessons_text() -> str:
    """Procedural memory injected into every prompt (capped)."""
    if LESSONS.exists():
        return LESSONS.read_text()[:6000]
    return ""

SYSTEM = """You extract technology deal data for a capital-markets tracker.
Given a raw item (an SEC filing snippet or a news headline+summary), respond with
ONLY a JSON object, no prose, no markdown fences.

If the item is a technology-sector M&A announcement, IPO filing/pricing,
follow-on equity/convertible raise, DEBT financing (bonds, leveraged loans,
private credit, infrastructure SPVs), SPAC/de-SPAC merger, or PRIVATE funding
round, return:
{
 "skip": false,
 "d": "YYYY-MM-DD",              // announcement/filing/pricing date
 "type": "M&A" | "IPO" | "Follow-on" | "Debt" | "SPAC" | "Private",
 "name": "Acquirer / Target" or "Company",   // M&A uses "A / B" format
 "v": number or null,            // deal value or proceeds in USD billions (2.65 = $2.65B); null if undisclosed
 "val": number or null,          // IPOs only: valuation at pricing/target, USD billions
 "sector": "short sector label",
 "status": "Closed" | "Pending" | "Filed" | "Terminated",
 "note": "2-3 sentence analyst-style note: structure, price/share, strategic rationale",
 "advisors": ["Bank Name", ...]   // financial advisors/bookrunners ONLY if named in the text; else []
}

If it is NOT a tech deal event (earnings, ETF launches, analyst notes, rumors
without a filing, non-tech sectors), return exactly: {"skip": true}

Be conservative with numbers: only state a value you can see in the text.

Accumulated lessons from past reviewed runs — follow these strictly:
{lessons}"""


def extract_one(client: anthropic.Anthropic, candidate: dict) -> dict | None:
    raw = json.dumps(candidate, ensure_ascii=False)[:6000]
    msg = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM.replace("{lessons}", lessons_text()),
        messages=[{"role": "user", "content": f"Raw item:\n{raw}"}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        rec = json.loads(text)
    except json.JSONDecodeError:
        return None
    if rec.get("skip"):
        return None
    rec["review"] = True
    rec["source_url"] = candidate.get("url", "")
    rec["source_snippet"] = (candidate.get("snippet") or candidate.get("title", ""))[:500]
    rec["extracted_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    # independent verifier: different model, sees only source + record
    passed, reason = verify_record(client, rec, rec["source_snippet"])
    if not passed:
        rec["verify_failed"] = True
        rec["verify_reason"] = reason
    # precedent-transaction metrics for M&A (maker/checker inside comps.py)
    if rec.get("type") == "M&A":
        try:
            c = extract_comps(client, rec, rec["source_snippet"])
            if c:
                rec["comps"] = c
        except Exception as ex:  # noqa: BLE001 — comps are additive, never blocking
            print(f"[extract] comps failed for {rec.get('name')}: {ex}")
    return rec


def run() -> list[dict]:
    client = anthropic.Anthropic(timeout=90.0, max_retries=2)  # reads ANTHROPIC_API_KEY
    candidates = []
    for f in ("candidates_edgar.json", "candidates_news.json"):
        p = OUT / f
        if p.exists():
            candidates += json.loads(p.read_text())

    extracted = []
    for c in candidates:
        try:
            rec = extract_one(client, c)
            if rec:
                extracted.append(rec)
        except anthropic.APIError as e:
            print(f"[extract] API error, skipping item: {e}")

    path = OUT / "extracted.json"
    path.write_text(json.dumps(extracted, indent=1))
    print(f"[extract] {len(candidates)} candidates -> {len(extracted)} deals -> {path}")
    return extracted


if __name__ == "__main__":
    run()
