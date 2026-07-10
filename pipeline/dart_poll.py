"""
dart_poll.py — Korean layer: DART disclosures + Korean-language news.

Two sources:
  1. DART (opendart.fss.or.kr) — Korea's EDGAR. Free API key required
     (register at opendart.fss.or.kr, set DART_API_KEY). We download the
     corp-code directory once (cached in pipeline/out/), look up each company
     in config's korea section by name, then pull its recent disclosures.
  2. Google News Korean edition — one query per Korean company/topic,
     using the same RSS machinery as news_feed_poll.py. No key needed,
     so this half works even without DART_API_KEY.

Output appends to pipeline/out/news_candidates.json with hint "korea",
so classify.py processes Korean items in the same batch flow (its prompt
asks for English summaries regardless of source language).
"""

import io
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = Path(__file__).parent / "out"
CONFIG = json.loads((ROOT / "config" / "watchlist.json").read_text())
KOREA = CONFIG.get("korea", {})
DART_KEY = os.environ.get("DART_API_KEY", "")

sys.path.insert(0, str(Path(__file__).parent))
from news_feed_poll import fetch, parse_rss  # noqa: E402  (reuse RSS machinery)


# ── DART ────────────────────────────────────────────────────────────────
def corp_code_map() -> dict:
    """Download & cache DART's corp-code directory; return {name: corp_code}."""
    cache = OUT / "dart_corpcodes.json"
    if cache.exists():
        return json.loads(cache.read_text())
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_KEY}"
    raw = fetch(url)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml_bytes = z.read(z.namelist()[0])
    mapping = {}
    wanted = {c["name_kr"] for c in KOREA.get("companies", [])}
    for el in ET.fromstring(xml_bytes).iter("list"):
        name = (el.findtext("corp_name") or "").strip()
        if name in wanted:
            mapping[name] = el.findtext("corp_code").strip()
    OUT.mkdir(exist_ok=True)
    cache.write_text(json.dumps(mapping, ensure_ascii=False))
    return mapping


def dart_disclosures(days_back: int) -> list[dict]:
    if not DART_KEY:
        print("[dart_poll] DART_API_KEY not set — skipping DART (news half still runs)")
        return []
    items = []
    try:
        codes = corp_code_map()
    except Exception as e:  # noqa: BLE001
        print(f"[dart_poll] corp-code download failed: {e}", file=sys.stderr)
        return []
    end = datetime.now(timezone.utc) + timedelta(hours=9)  # KST
    start = end - timedelta(days=days_back)
    by_code = {}
    for c in KOREA.get("companies", []):
        code = codes.get(c["name_kr"])
        if code:
            by_code[code] = c
    for code, comp in by_code.items():
        url = ("https://opendart.fss.or.kr/api/list.json?"
               f"crtfc_key={DART_KEY}&corp_code={code}"
               f"&bgn_de={start:%Y%m%d}&end_de={end:%Y%m%d}&page_count=20")
        try:
            data = json.loads(fetch(url))
        except Exception as e:  # noqa: BLE001
            print(f"[dart_poll] list failed for {comp['name']}: {e}", file=sys.stderr)
            continue
        for r in data.get("list", []):
            items.append({
                "title": f"[DART] {comp['name']}: {r.get('report_nm','')}",
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r.get('rcept_no','')}",
                "published": datetime.now(timezone.utc).isoformat(),
                "outlet": "DART",
                "hint": "korea",
                "snippet": f"{comp['name_kr']} regulatory disclosure filed "
                           f"{r.get('rcept_dt','')}: {r.get('report_nm','')}",
            })
    return items


# ── Korean Google News ──────────────────────────────────────────────────
def korean_news() -> list[dict]:
    tmpl = KOREA.get("google_news_template_kr", "")
    if not tmpl:
        return []
    items = []
    queries = [c["name_kr"] for c in KOREA.get("companies", [])] + KOREA.get("topics_kr", [])
    for q in queries:
        try:
            got = parse_rss(fetch(tmpl.format(query=urllib.parse.quote(q))), tag_hint="korea")
            items += got
        except Exception as e:  # noqa: BLE001
            print(f"[dart_poll] KR news failed '{q}': {e}", file=sys.stderr)
    return items


def run(days_back: int = 1) -> list[dict]:
    items = dart_disclosures(days_back) + korean_news()
    OUT.mkdir(exist_ok=True)
    path = OUT / "news_candidates.json"
    existing = json.loads(path.read_text()) if path.exists() else []
    path.write_text(json.dumps(existing + items, indent=1, ensure_ascii=False))
    print(f"[dart_poll] appended {len(items)} Korean items -> {path}")
    return items


if __name__ == "__main__":
    run(days_back=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
