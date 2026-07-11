"""
earnings_intel.py — earnings-call intelligence for watchlist companies.

For each company in config/watchlist.json:
  1. DETECT  — find a new earnings document since the last analyzed period.
               Primary source: EDGAR 8-K earnings press releases (free, no key).
               Upgrade path: if FMP_API_KEY has transcript access (paid tier),
               the full call transcript is used instead — same pipeline, richer
               input. The free FMP tier returns 402/403/empty; we fall back
               silently.
  2. ANALYZE — one Claude call per document extracts a structured record:
               sentiment (score + the drivers behind it), guidance changes
               (raised/lowered/maintained per metric, with numbers), KPIs
               (standard + company-specific, kept name-consistent by feeding
               the prior quarter's KPI names back into the prompt), executive
               tone (confidence vs hedging), and any M&A commentary.
  3. STORE   — derived analysis only goes into data/earnings_intel.json.
               Transcripts/releases are copyrighted; we never store the text,
               only scores, extracted figures, and short attributed phrases.

Model: Haiku by default (EARNINGS_MODEL to override) — this is extraction,
not prose. Cost stays pennies per company per quarter.
"""

import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).parent.parent
STORE = ROOT / "data" / "earnings_intel.json"
WATCHLIST = ROOT / "config" / "watchlist.json"
MODEL = os.environ.get("EARNINGS_MODEL", "claude-haiku-4-5-20251001")
MAX_COMPANIES_PER_RUN = int(os.environ.get("EARNINGS_MAX_PER_RUN", "6"))
MAX_DOC_CHARS = 40_000

UA = os.environ.get("EDGAR_USER_AGENT",
                    "DealTracker research script contact@example.com")
HEADERS = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
FTS_URL = "https://efts.sec.gov/LATEST/search-index"

SYSTEM = """You analyze earnings communications for an investment-banking analyst
covering technology and semiconductors. You receive the text of an earnings
press release or call transcript for {company} ({ticker}), plus the KPI names
tracked last quarter (keep names IDENTICAL where the concept matches; flag
any tracked KPI the company stopped reporting).

Respond with ONLY a JSON object, no markdown fences:
{{
 "period": "e.g. Q2 FY2026 — as the company labels it",
 "sentiment": {{"score": -2 to 2 integer, "label": "bearish|cautious|neutral|constructive|bullish",
   "drivers": ["max 3 short reasons grounded in the text"]}},
 "guidance": [{{"metric": "...", "direction": "raised|lowered|maintained|initiated|withdrawn|not_given",
   "prior": "...or null", "new": "...or null"}}],
 "kpis": [{{"name": "...", "value": "...", "unit": "...", "yoy": "...or null"}}],
 "dropped_kpis": ["previously tracked names absent this period"],
 "tone": {{"confidence": 0 to 10, "hedging": 0 to 10,
   "notes": "one sentence on management's tone; if Q&A present, how directly questions were answered"}},
 "ma_commentary": {{"present": true/false, "summary": "one sentence or empty"}}
}}

Rules: extract only what the text states — never estimate or fill gaps. Max 5
standard KPIs (revenue, EPS, gross margin, operating income, FCF when stated)
plus up to 5 company-specific KPIs (segment revenue, utilization, HBM/AI mix,
book-to-bill, etc). Any quoted phrase must be under 15 words. If the document
is not an earnings communication, respond with {{"skip": true}}."""


def load_store() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text())
    return {"companies": {}, "meta": {}}


def watchlist() -> list[dict]:
    return json.loads(WATCHLIST.read_text()).get("watchlist", [])


def strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


# ── source A: FMP transcript (works only on paid tiers; fails soft) ──────
def try_fmp_transcript(ticker: str) -> tuple[str, str] | None:
    key = os.environ.get("FMP_API_KEY", "").strip()
    if not key:
        return None
    try:
        r = requests.get("https://financialmodelingprep.com/api/v3/"
                         f"earning_call_transcript/{ticker}",
                         params={"apikey": key, "limit": 1}, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        if isinstance(data, list) and data and data[0].get("content"):
            d = data[0]
            label = f"FMP transcript {d.get('date','')[:10]}"
            return d["content"][:MAX_DOC_CHARS], label
    except (requests.RequestException, ValueError):
        pass
    return None


# ── source B: EDGAR 8-K earnings press release (free, always on) ─────────
def edgar_earnings_doc(name: str, ticker: str, since: str) -> tuple[str, str, str] | None:
    """Return (text, source_label, source_url) for the newest earnings 8-K."""
    params = {"q": f'"{name}" "results of operations"', "forms": "8-K",
              "dateRange": "custom", "startdt": since,
              "enddt": dt.date.today().isoformat()}
    try:
        r = requests.get(FTS_URL, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
    except (requests.RequestException, ValueError):
        return None
    time.sleep(0.5)
    for hit in hits:
        src = hit.get("_source", {})
        names = " ".join(src.get("display_names") or []).lower()
        if name.lower().split()[0] not in names:
            continue
        cik = (src.get("ciks") or [""])[0]
        adsh = src.get("adsh", "")
        fid = hit.get("_id", "")
        fname = fid.split(":", 1)[1] if ":" in fid else ""
        if not (cik and adsh and fname):
            continue
        url = (f"https://www.sec.gov/Archives/edgar/data/"
               f"{cik.lstrip('0')}/{adsh.replace('-', '')}/{fname}")
        try:
            doc = requests.get(url, headers=HEADERS, timeout=30)
            doc.raise_for_status()
        except requests.RequestException:
            continue
        text = strip_html(doc.text)[:MAX_DOC_CHARS]
        if len(text) > 1500:            # too short = cover page, keep looking
            return text, f"EDGAR 8-K filed {src.get('file_date','')}", url
    return None


def analyze(client, company: dict, text: str, prior_kpis: list[str]) -> dict | None:
    import anthropic
    prompt = (f"KPI names tracked last quarter: {json.dumps(prior_kpis) if prior_kpis else 'none yet'}\n\n"
              f"Document text:\n{text}")
    try:
        msg = client.messages.create(
            model=MODEL, max_tokens=1500,
            system=SYSTEM.format(company=company["name"], ticker=company.get("ticker", "")),
            messages=[{"role": "user", "content": prompt}])
    except anthropic.APIError as e:
        print(f"[earnings-intel] API error for {company['name']}: {e}", flush=True)
        return None
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        rec = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[earnings-intel] unparseable response for {company['name']}", flush=True)
        return None
    return None if rec.get("skip") else rec


def run() -> None:
    import anthropic
    client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    store = load_store()
    analyzed = 0

    for comp in watchlist():
        if analyzed >= MAX_COMPANIES_PER_RUN:
            print("[earnings-intel] per-run cap reached; rest next run", flush=True)
            break
        key = comp.get("ticker") or comp["name"]
        hist = store["companies"].setdefault(key, {"name": comp["name"],
                                                   "ticker": comp.get("ticker", ""),
                                                   "quarters": []})
        last = hist["quarters"][-1] if hist["quarters"] else {}
        since = last.get("doc_date") or (dt.date.today() - dt.timedelta(days=100)).isoformat()

        got = try_fmp_transcript(comp.get("ticker", ""))
        if got:
            text, label = got
            url = ""
        else:
            found = edgar_earnings_doc(comp["name"], comp.get("ticker", ""), since)
            if not found:
                continue
            text, label, url = found
        # skip if we already analyzed this same document
        if label == last.get("source_label"):
            continue

        prior_kpis = [k["name"] for k in last.get("kpis", [])]
        rec = analyze(client, comp, text, prior_kpis)
        if not rec:
            continue
        rec.update({"analyzed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "doc_date": dt.date.today().isoformat(),
                    "source_label": label, "source_url": url,
                    "model": MODEL, "derived_only": True})
        hist["quarters"].append(rec)
        hist["quarters"] = hist["quarters"][-8:]         # keep 2 years
        analyzed += 1
        print(f"[earnings-intel] {comp['name']}: {rec.get('period','?')} "
              f"sentiment={rec.get('sentiment',{}).get('label','?')} "
              f"({label})", flush=True)

    store["meta"]["last_run"] = dt.datetime.now(dt.timezone.utc).isoformat()
    STORE.write_text(json.dumps(store, indent=1, ensure_ascii=False))
    print(f"[earnings-intel] {analyzed} new analyses -> {STORE}", flush=True)


if __name__ == "__main__":
    run()
