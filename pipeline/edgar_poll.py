"""
edgar_poll.py — pull recent SEC filings that typically signal tech deals.

Sources (all free, no key required):
  * EDGAR full-text search API:  https://efts.sec.gov/LATEST/search-index?q=...
  * EDGAR daily index:           https://www.sec.gov/Archives/edgar/daily-index/

What we look for:
  * S-1 / F-1        -> IPO filings
  * 424B1..424B5     -> IPO / follow-on pricings (prospectuses)
  * 8-K              -> M&A announcements (we keyword-filter the text)

SEC requires a descriptive User-Agent with contact info — set EDGAR_USER_AGENT.
Output: a list of "candidate" dicts written to pipeline/out/candidates_edgar.json,
which extract.py then turns into structured deal records.
"""

import json
import os
import sys
import time
import datetime as dt
from pathlib import Path

import requests

UA = os.environ.get("EDGAR_USER_AGENT", "DealTracker research script contact@example.com")
HEADERS = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
FTS_URL = "https://efts.sec.gov/LATEST/search-index"
OUT = Path(__file__).parent / "out"

IPO_FORMS = ["S-1", "F-1"]
PRICING_FORMS = ["424B1", "424B2", "424B3", "424B4", "424B5"]
MA_KEYWORDS = '"merger agreement" OR "agreement and plan of merger" OR "to acquire"'

# Tech-ish SIC code prefixes: services-software (737x), semiconductors (3674),
# computers (357x), communications equipment (366x), internet retail (5961 is not),
# telecom services (481x). Loose on purpose — extract.py does the real filtering.
TECH_SIC_PREFIXES = ("737", "357", "367", "366", "481", "7372", "7389")


def fts_search(query: str, forms: list[str], date_from: str, date_to: str) -> list[dict]:
    """Query EDGAR full-text search, return raw hit dicts."""
    params = {
        "q": query,
        "dateRange": "custom",
        "startdt": date_from,
        "enddt": date_to,
        "forms": ",".join(forms),
    }
    r = requests.get(FTS_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    hits = r.json().get("hits", {}).get("hits", [])
    time.sleep(0.5)  # stay well under SEC's 10 req/s limit
    return hits


def hit_to_candidate(hit: dict, kind: str) -> dict:
    src = hit.get("_source", {})
    acc = src.get("adsh", "")
    cik = (src.get("ciks") or [""])[0]
    return {
        "kind": kind,  # ipo_filing | pricing | ma_8k
        "source": "edgar",
        "form": src.get("file_type") or src.get("forms"),
        "company": (src.get("display_names") or [""])[0],
        "cik": cik,
        "sic": src.get("sics", [""])[0] if src.get("sics") else "",
        "filed": src.get("file_date"),
        "url": f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc.replace('-','')}"
               if cik and acc else "",
        "snippet": " ".join(hit.get("highlight", {}).get("content", []))[:1500],
    }


def looks_tech(cand: dict) -> bool:
    sic = str(cand.get("sic") or "")
    return sic.startswith(TECH_SIC_PREFIXES) or not sic  # keep unknowns; LLM filters later


def run(days_back: int = 1) -> list[dict]:
    today = dt.date.today()
    start = (today - dt.timedelta(days=days_back)).isoformat()
    end = today.isoformat()

    candidates: list[dict] = []
    try:
        for hit in fts_search('"initial public offering"', IPO_FORMS, start, end):
            candidates.append(hit_to_candidate(hit, "ipo_filing"))
        for hit in fts_search('"public offering"', PRICING_FORMS, start, end):
            candidates.append(hit_to_candidate(hit, "pricing"))
        for hit in fts_search(MA_KEYWORDS, ["8-K"], start, end):
            candidates.append(hit_to_candidate(hit, "ma_8k"))
    except requests.RequestException as e:
        print(f"[edgar_poll] network error: {e}", file=sys.stderr)

    candidates = [c for c in candidates if looks_tech(c)]

    OUT.mkdir(exist_ok=True)
    path = OUT / "candidates_edgar.json"
    path.write_text(json.dumps(candidates, indent=1))
    print(f"[edgar_poll] wrote {len(candidates)} candidates -> {path}")
    return candidates


if __name__ == "__main__":
    run(days_back=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
