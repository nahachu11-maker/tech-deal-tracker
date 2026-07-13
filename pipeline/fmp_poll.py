"""
fmp_poll.py — pull recent M&A deals from Financial Modeling Prep.

Unlike edgar_poll/news_feed_poll (which produce *candidates* that extract.py
must run through Claude), FMP returns already-structured deal data: acquirer,
target, transaction date, and a link to the SEC filing. There is no free-text
to interpret, so these records skip LLM extraction entirely and are written
straight into out/extracted.json as trusted rows for update_deals to merge.

This makes deal announcements land in the tracker within hours — with an SEC
filing link attached — instead of waiting for the next manual CapIQ export.

Setup: free API key from financialmodelingprep.com -> set FMP_API_KEY.
If the key is absent the poller no-ops cleanly (the rest of the run continues).

Licensing: FMP's terms restrict redistribution, so every record is tagged
`licensed: true` and carries source="fmp". scrub_publish.py already strips
licensed analytics before anything is published, so these are handled by the
same guard as CapIQ rows — nothing extra to remember.
"""

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from import_deals import clean_company, smart_note   # reuse existing helpers

OUT = Path(__file__).parent / "out"
BASE = "https://financialmodelingprep.com/api/v4"
# stable v3 endpoint fallback for the search variant
SEARCH_BASE = "https://financialmodelingprep.com/api/v4"

# Tech-ish keyword gate on target/acquirer names + any SIC/industry hint FMP
# returns. Loose on purpose; dedupe + the human review queue catch strays.
TECH_HINTS = re.compile(
    r"semiconduct|chip|software|cloud|saas|cyber|data|ai\b|artificial intelligen|"
    r"platform|digital|internet|tech(nolog)?|computing|electronic|fintech|"
    r"e-?commerce|telecom|network|silicon|fabless|foundry|sensor|robotic",
    re.I)


def _get(url: str, params: dict) -> list | dict:
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_recent(api_key: str, pages: int = 2) -> list[dict]:
    """Latest M&A feed, newest first, a few pages deep."""
    rows: list[dict] = []
    for page in range(pages):
        try:
            data = _get(f"{BASE}/mergers-acquisitions-rss-feed",
                        {"page": page, "apikey": api_key})
        except requests.HTTPError as e:
            print(f"[fmp] feed page {page} HTTP error: {e}", flush=True)
            break
        if not data:
            break
        rows.extend(data)
    return rows


def is_tech(row: dict) -> bool:
    blob = " ".join(str(row.get(k, "")) for k in
                    ("companyName", "targetedCompanyName", "symbol", "targetedSymbol"))
    return bool(TECH_HINTS.search(blob))


def parse_date(raw: str) -> str | None:
    if not raw:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(raw))
    return m.group(1) if m else None


def normalize(row: dict) -> dict | None:
    acquirer = clean_company(row.get("companyName", ""))
    target = clean_company(row.get("targetedCompanyName", ""))
    date = parse_date(row.get("transactionDate") or row.get("acceptedDate"))
    if not (acquirer and target and date):
        return None
    # skip announcements dated absurdly in the future (bad data)
    if date > (dt.date.today() + dt.timedelta(days=3)).isoformat():
        return None

    url = row.get("link") or row.get("url") or ""
    sym = row.get("symbol") or ""
    tsym = row.get("targetedSymbol") or ""
    ticker = "/".join(t for t in (sym, tsym) if t)

    note_bits = []
    if row.get("transactionDate"):
        note_bits.append(f"Announced {parse_date(row['transactionDate'])}.")
    if ticker:
        note_bits.append(f"Tickers: {ticker}.")
    note_bits.append("Sourced from FMP M&A feed; see filing link.")

    rec = {
        "d": date,
        "type": "M&A",
        "name": f"{acquirer} / {target}",
        "v": None,                       # feed rarely carries a clean value
        "status": "Pending",             # RSS feed = freshly announced
        "sector": "Technology",          # coarse; CapIQ/refinement sharpens later
        "note": smart_note(" ".join(note_bits)),
        "source": "fmp",
        "licensed": True,
        "review": True,                  # public feed -> keep the human gate
        "source_url": url,
    }
    if ticker:
        rec["ticker"] = ticker
    # a stable-ish id so re-polls are idempotent even before CapIQ assigns a uid
    cik = row.get("cik") or ""
    if cik and date:
        rec["uid"] = f"fmp:{cik}:{date}"
    return rec


def run() -> list[dict]:
    api_key = os.environ.get("FMP_API_KEY", "").strip()
    if not api_key:
        print("[fmp] FMP_API_KEY not set — skipping FMP poll (this is fine).",
              flush=True)
        return []

    raw = fetch_recent(api_key)
    tech = [r for r in raw if is_tech(r)]
    records, seen = [], set()
    for r in tech:
        rec = normalize(r)
        if not rec:
            continue
        key = rec.get("uid") or rec["name"] + rec["d"]
        if key in seen:
            continue
        seen.add(key)
        records.append(rec)
    print(f"[fmp] {len(raw)} feed rows -> {len(tech)} tech -> "
          f"{len(records)} normalized deals", flush=True)

    # APPEND to extracted.json so FMP rows sit alongside Claude-extracted ones;
    # update_deals merges the union. Never overwrite extract.py's output.
    OUT.mkdir(exist_ok=True)
    path = OUT / "extracted.json"
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            existing = []
    path.write_text(json.dumps(existing + records, indent=1, ensure_ascii=False))
    print(f"[fmp] appended {len(records)} records -> {path} "
          f"({len(existing)} already present)", flush=True)
    return records


if __name__ == "__main__":
    run()
