"""
import_deals.py — bring deal data in from licensed sources (Dealytics,
PitchBook, Dealogic, ...) via CSV export. No API polling: these platforms are
login-gated, so the workflow is export -> import.

Two modes:
  import  Add new deals. Rows are normalized to the tracker schema, tagged
          with provenance, flagged review=True, and merged through the SAME
          type-aware dedupe as the live pipeline — an import can update a
          status or fill a value on an existing deal, never duplicate it.
  enrich  Fill advisors ONLY on deals you already track (matched by the same
          same_deal() logic). Never adds rows, never overwrites an existing
          advisors list. This is the mode that fixes coverage gaps at scale.

Column mappings live in config/import_mappings.json — one block per source.
Values are unit-converted (Dealytics exports in $M; the tracker stores $B).

LICENSING GUARD: data exported from a licensed platform is for YOUR use.
This repo deploys to a PUBLIC GitHub Pages site — republishing licensed data
there may violate the provider's terms. The importer prints this warning on
every run and requires --acknowledge-license to proceed. Imported records
carry "licensed": true so they can be audited or scrubbed before publishing.

Usage:
  python pipeline/import_deals.py export.csv --source dealytics --mode enrich --acknowledge-license
  python pipeline/import_deals.py export.csv --source dealytics --mode import --acknowledge-license --dry-run
"""

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "deals.json"
MAPPINGS = ROOT / "config" / "import_mappings.json"

sys.path.insert(0, str(Path(__file__).parent))
from update_deals import merge, same_deal  # noqa: E402 — reuse live dedupe

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y", "%d %b %Y",
                "%B %d, %Y", "%Y/%m/%d")
TYPE_ALIASES = {
    "m&a": "M&A", "merger": "M&A", "acquisition": "M&A", "takeover": "M&A",
    "merger/acquisition": "M&A", "m&a transaction": "M&A",
    "lbo": "M&A", "take-private": "M&A", "buyout": "M&A",
    "ipo": "IPO", "initial public offering": "IPO", "listing": "IPO",
    "follow-on": "Follow-on", "follow on": "Follow-on", "fo": "Follow-on",
    "secondary": "Follow-on", "convertible": "Follow-on",
    "debt": "Debt", "bond": "Debt", "loan": "Debt", "notes": "Debt",
    "spac": "SPAC", "de-spac": "SPAC",
    "private": "Private", "venture": "Private", "growth": "Private",
    "funding round": "Private",
}
STATUS_ALIASES = {
    "completed": "Closed", "closed": "Closed", "effective": "Closed",
    "pending": "Pending", "announced": "Pending", "definitive": "Pending",
    "filed": "Filed", "registered": "Filed",
    "withdrawn": "Terminated", "terminated": "Terminated", "cancelled": "Terminated",
    "abandoned": "Terminated",
}

LICENSE_WARNING = """
================== LICENSING NOTICE ==================
Data exported from a licensed platform (Dealytics, PitchBook, Dealogic, etc.)
is licensed for YOUR use. If this repository deploys to a PUBLIC site,
republishing that data may violate the provider's terms of service.
Options: keep the repo private, or use licensed data only as a finding aid
for facts that are independently public. Imported records are tagged
"licensed": true so you can audit or scrub them before publishing.
=======================================================
"""


# ── pure normalization helpers (fully offline-testable) ─────────────────
def parse_date(raw: str) -> str | None:
    raw = (raw or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_value(raw, unit: str) -> float | None:
    """'1,234.5' in millions -> 1.2345 (tracker stores USD billions)."""
    if raw in (None, "", "-", "n/a", "N/A", "undisclosed", "Undisclosed"):
        return None
    try:
        v = float(str(raw).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None
    if unit == "millions":
        v = v / 1000.0
    elif unit == "thousands":
        v = v / 1_000_000.0
    return round(v, 4) if v > 0 else None


import re

TICKER_RE = re.compile(r"\s*\([A-Za-z]+:[^)]*\)")
SUFFIX_RE = re.compile(r",?\s+(incorporated|corporation|inc\.?|corp\.?|company|co\.?|"
                       r"ltd\.?|limited|llc|l\.l\.c\.|lp|l\.p\.|plc|se|ag|nv|as|sa|holdings?)\s*$",
                       re.IGNORECASE)
CANONICAL_BANKS = {
    "j.p. morgan": "JPMorgan", "jp morgan": "JPMorgan", "jpmorgan": "JPMorgan",
    "morgan stanley": "Morgan Stanley", "goldman sachs": "Goldman Sachs", "goldman, sachs": "Goldman Sachs",
    "bofa": "BofA Securities", "bank of america": "BofA Securities", "merrill": "BofA Securities",
    "citigroup": "Citigroup", "citi ": "Citigroup",
    "ubs": "UBS", "barclays": "Barclays", "jefferies": "Jefferies",
    "qatalyst": "Qatalyst Partners", "centerview": "Centerview Partners",
    "evercore": "Evercore", "lazard": "Lazard", "moelis": "Moelis",
    "allen & company": "Allen & Company", "mizuho": "Mizuho", "mufg": "MUFG",
    "wells fargo": "Wells Fargo", "credit suisse": "Credit Suisse",
    "deutsche bank": "Deutsche Bank", "rbc": "RBC Capital Markets",
    "needham": "Needham & Company", "stifel": "Stifel", "piper sandler": "Piper Sandler",
    "houlihan lokey": "Houlihan Lokey", "guggenheim": "Guggenheim", "pjt": "PJT Partners",
    "perella": "Perella Weinberg", "raymond james": "Raymond James", "william blair": "William Blair",
    "tidal partners": "Tidal Partners", "bnp paribas": "BNP Paribas", "hsbc": "HSBC",
    "rothschild": "Rothschild & Co", "nomura": "Nomura", "td securities": "TD Securities",
    "td cowen": "TD Securities", "cowen": "TD Securities",
}
FINANCIAL_ROLES = ("financial advisor", "fairness opinion")


def clean_company(name: str) -> str:
    """'Synaptics Incorporated (NasdaqGS:SYNA)' -> 'Synaptics'."""
    n = TICKER_RE.sub("", str(name or "")).strip()
    prev = None
    while prev != n:  # strip stacked suffixes ('... Company, Inc.')
        prev = n
        n = SUFFIX_RE.sub("", n).strip().rstrip(",")
    return n


def canonical_bank(raw: str) -> str:
    low = raw.lower()
    for key, canon in CANONICAL_BANKS.items():
        if key in low:
            return canon
    return clean_company(raw)


def parse_role_advisors(raw: str) -> list[str]:
    """CapIQ style: 'Qatalyst Partners, L.P. (Fairness Opinion Provider);
    Baker & McKenzie LLP (Legal Advisor)' -> financial advisors only,
    canonical names, deduped. Law firms are dropped on purpose."""
    if not raw or str(raw).strip() in ("-", ""):
        return []
    out, seen = [], set()
    for part in str(raw).split(";"):
        part = part.strip()
        m = re.search(r"\(([^)]*)\)\s*$", part)
        role = (m.group(1).lower() if m else "")
        if m:
            part = part[:m.start()].strip()
        if role and not any(fr in role for fr in FINANCIAL_ROLES):
            continue  # legal advisor, accountant, PR, ...
        if not role and ("llp" in part.lower() or "law" in part.lower()):
            continue
        bank = canonical_bank(part)
        if bank and bank.lower() not in seen:
            seen.add(bank.lower())
            out.append(bank)
    return out


def parse_metric(raw) -> float | None:
    """'32.5%' -> 32.5, '8.2x' -> 8.2, '$210.00' -> 210.0, junk -> None."""
    if raw in (None, "", "-", "n/a", "N/A", "NM", "nm"):
        return None
    s = str(raw).replace(",", "").replace("%", "").replace("x", "").replace("$", "").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return round(v, 2)


def collect_advisors(row: dict, mapping: dict) -> list[str]:
    """Advisors may live in ONE column or SEVERAL (CapIQ splits target-side vs
    buyer-side; FactSet separates bookrunners and managers). The mapping's
    'advisors' key accepts a string or a list of column names — multi-column
    values are merged and deduped in order."""
    cols = mapping.get("advisors", "")
    if isinstance(cols, str):
        cols = [cols]
    merged = []
    for c in cols:
        raw = row.get(c, "")
        if mapping.get("advisor_roles"):
            merged += parse_role_advisors(raw)
        else:
            merged += parse_advisors(raw, mapping.get("advisor_delimiter", ";"))
    seen, out = set(), []
    for a in merged:
        if a.lower() not in seen:
            seen.add(a.lower()); out.append(a)
    return out


def build_comps(row: dict, mapping: dict) -> dict | None:
    """Optional valuation columns (CapIQ's real strength) -> the comps object
    the deal UI already renders. Only attached when a hard number exists."""
    fields = {
        "premium_pct": parse_metric(row.get(mapping.get("premium_pct", ""), "")),
        "premium_1w": parse_metric(row.get(mapping.get("premium_1w", ""), "")),
        "premium_1m": parse_metric(row.get(mapping.get("premium_1m", ""), "")),
        "ev_revenue": parse_metric(row.get(mapping.get("ev_revenue", ""), "")),
        "ev_ebitda": parse_metric(row.get(mapping.get("ev_ebitda", ""), "")),
        "ev_ebit": parse_metric(row.get(mapping.get("ev_ebit", ""), "")),
        "pe": parse_metric(row.get(mapping.get("pe", ""), "")),
        "pb": parse_metric(row.get(mapping.get("pb", ""), "")),
        "price_per_share": parse_metric(row.get(mapping.get("price_per_share", ""), "")),
    }
    # $mm columns -> stored in $B like everything else in the tracker
    for key in ("implied_ev", "ltm_revenue", "ltm_ebitda"):
        v = parse_metric(row.get(mapping.get(key, ""), ""))
        if v is not None and mapping.get("value_unit", "millions") == "millions":
            v = round(v / 1000.0, 4)
        fields[key] = v
    fee = parse_metric(row.get(mapping.get("termination_fee", ""), ""))
    if fee is not None and mapping.get("value_unit", "millions") == "millions":
        fee = round(fee / 1000.0, 4)
    fields["termination_fee"] = fee
    if all(v is None for v in fields.values()):
        return None
    cons = str(row.get(mapping.get("consideration", ""), "")).lower()
    fields["consideration"] = ("cash-and-stock" if ("cash" in cons and ("stock" in cons or "equity" in cons))
                               else "cash" if "cash" in cons
                               else "stock" if ("stock" in cons or "equity" in cons)
                               else "unstated")
    fields["source"] = "import"
    return fields


def parse_advisors(raw: str, delimiter: str) -> list[str]:
    if not raw:
        return []
    seen, out = set(), []
    for a in str(raw).split(delimiter):
        a = a.strip()
        if a and a.lower() not in seen:
            seen.add(a.lower())
            out.append(a)
    return out


def normalize_type(raw: str) -> str | None:
    return TYPE_ALIASES.get((raw or "").strip().lower())


def normalize_status(raw: str) -> str:
    return STATUS_ALIASES.get((raw or "").strip().lower(), "Pending")


# ── note summarization ────────────────────────────────────────────────────
# CapIQ transaction comments are formulaic: sentence 1 = who/what/price/date,
# 2 = consideration, 3 = funding — then boilerplate (closing conditions,
# board approvals, advisor listings we already capture in `advisors`).
# Keeping the leading non-boilerplate sentences IS the summary, and being
# deterministic it costs nothing and is identical on every re-import.

BOILERPLATE_RE = re.compile(
    r"acted as (?:the |a |an )?(?:exclusive |lead |sole |joint )*(?:financial advis|legal advis|"
    r"legal counsel|counsel|accountant|auditor|fairness opinion)|"
    r"served as (?:the |a |an )?(?:financial|legal)|"
    r"provided due diligence|due diligence services|"
    r"(?:is|are|was|were|remains?) subject to (?:customary|regulatory|certain|shareholder|the)|"
    r"subject to customary closing|"
    r"(?:unanimously )?approved by the board|board of directors (?:of .{0,60})?(?:unanimously )?approved",
    re.I)

_ABBR_END = re.compile(r"\b(?:Inc|Ltd|Corp|Co|LLC|S\.A|plc|Mr|Ms|Dr|No|Nos|approx|St|vs|U\.S|U\.K)\.$")


def split_sentences(text: str) -> list[str]:
    parts, buf = [], ""
    for chunk in re.split(r"(?<=[.!?])\s+", text):
        buf = f"{buf} {chunk}".strip() if buf else chunk
        if _ABBR_END.search(buf):        # "Nagarro SE, Inc." — not a real stop
            continue
        parts.append(buf)
        buf = ""
    if buf:
        parts.append(buf)
    return parts


def smart_note(raw, limit: int = 600) -> str:
    """Whole sentences only, boilerplate dropped, never a mid-sentence chop."""
    text = re.sub(r"\s+", " ", str(raw or "").strip())
    if not text or text == "-":
        return ""
    if len(text) <= limit and not BOILERPLATE_RE.search(text):
        return text
    kept: list[str] = []
    used = 0
    for s in split_sentences(text):
        if kept and BOILERPLATE_RE.search(s):   # never drop the lead sentence
            continue
        if used + len(s) + (1 if kept else 0) > limit:
            break
        kept.append(s)
        used += len(s) + 1
    if not kept:                                # lead sentence alone > limit
        return text[:limit].rsplit(" ", 1)[0].rstrip(",;:– ") + "…"
    return " ".join(kept)


def normalize_row(row: dict, mapping: dict, source: str) -> dict | None:
    """One CSV row -> tracker record, or None if it can't be normalized."""
    col = lambda key: (row.get(mapping.get(key, "")) or "").strip()
    dtype = normalize_type(col("type"))
    date = parse_date(col("date"))
    if not dtype or not date:
        return None
    if dtype == "M&A" and mapping.get("acquirer") and mapping.get("target"):
        acq_raw, tgt = col("acquirer"), col("target")
        if acq_raw in ("-", "") or tgt in ("-", ""):
            return None
        acq = clean_company(acq_raw.split(";")[0])  # lead buyer names the deal
        tgt = clean_company(tgt)
        if not (acq and tgt):
            return None
        name = f"{acq} / {tgt}"
    else:
        name = col("company") or col("target") or col("acquirer")
        if not name:
            return None
    rec = {
        "d": date, "type": dtype, "name": name,
        "v": parse_value(col("value"), mapping.get("value_unit", "millions")),
        "sector": col("sector") or "Technology",
        "status": normalize_status(col("status")),
        "note": smart_note(col("note")) or f"Imported from {source}.",
        "advisors": collect_advisors(row, mapping),
        "review": True, "source": source, "licensed": True,
    }
    stake = parse_metric(col("percent_sought")) if mapping.get("percent_sought") else None
    if stake is not None and stake != 100.0:
        rec["stake_pct"] = stake
    uid = col("uid")
    if uid and uid != "-":
        rec["uid"] = uid
    ticker = col("ticker")
    if ticker and ticker != "-":
        rec["ticker"] = ticker
    sellers_raw = col("sellers")
    if sellers_raw and sellers_raw != "-":
        sellers, seen = [], set()
        for s in sellers_raw.split(";"):
            s = clean_company(s)
            if s and s.lower() not in seen:
                seen.add(s.lower()); sellers.append(s)
        if sellers:
            rec["sellers"] = sellers[:8]
    attitude = col("attitude")
    if attitude and attitude != "-":
        rec["attitude"] = attitude.strip().lower()
    resolution = col("resolution")
    if rec["status"] == "Terminated" and resolution and resolution != "-":
        rec["resolution"] = resolution[:300]
    comps = build_comps(row, mapping)
    if comps:
        rec["comps"] = comps
    val = parse_value(col("valuation"), mapping.get("value_unit", "millions"))
    if val is not None:
        rec["val"] = val
    return rec


def enrich(existing: list[dict], imported: list[dict]) -> dict:
    """Fill advisors on matched deals only. Never adds, never overwrites."""
    stats = {"matched": 0, "enriched": 0, "unmatched": []}
    for rec in imported:
        match = next((e for e in existing if same_deal(e, rec)), None)
        if match is None:
            stats["unmatched"].append(rec["name"])
            continue
        stats["matched"] += 1
        filled = False
        if rec.get("advisors") and not match.get("advisors"):
            match["advisors"] = rec["advisors"]
            match["advisor_source"] = rec["source"]
            filled = True
        if rec.get("comps") and not match.get("comps"):
            match["comps"] = rec["comps"]
            filled = True
        if filled:
            stats["enriched"] += 1
    return stats


def reconcile(existing: list[dict], imported: list[dict]) -> list[dict]:
    """Licensed data auditing tracked data: for matched deals, flag where the
    import disagrees on value magnitude or shows a status the tracker lacks.
    Read-only — produces a report, never modifies anything."""
    from eval_harness import value_bucket
    STATUS_RANK = {"Filed": 0, "Pending": 1, "Terminated": 2, "Closed": 2}
    findings = []
    for rec in imported:
        match = next((e for e in existing if same_deal(e, rec)), None)
        if match is None:
            continue
        if (rec.get("v") is not None and match.get("v") is not None
                and value_bucket(rec["v"]) != value_bucket(match["v"])):
            findings.append({"deal": match["name"], "field": "value",
                             "tracked": match["v"], "imported": rec["v"],
                             "detail": "Different order of magnitude — check units or announced-vs-final value."})
        if STATUS_RANK.get(rec.get("status"), -1) > STATUS_RANK.get(match.get("status"), -1):
            findings.append({"deal": match["name"], "field": "status",
                             "tracked": match.get("status"), "imported": rec.get("status"),
                             "detail": "Import shows a later lifecycle stage — the tracked deal may have closed/terminated."})
    return findings


def load_rows(path: str, mapping: dict) -> tuple[list[dict], list[str]]:
    """CSV, or Excel (.xls/.xlsx) with automatic header-row detection —
    CapIQ reports carry ~7 branding rows above the real table."""
    if not path.lower().endswith((".xls", ".xlsx")):
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return list(reader), (reader.fieldnames or [])
    import pandas as pd
    engine = "xlrd" if path.lower().endswith(".xls") else None
    probe = pd.read_excel(path, engine=engine, header=None, nrows=15)
    wanted = {v for v in mapping.values() if isinstance(v, str)}
    for lst in (v for v in mapping.values() if isinstance(v, list)):
        wanted |= set(lst)
    header_row = 0
    for i in range(len(probe)):
        vals = {str(x).strip() for x in probe.iloc[i].tolist()}
        if len(vals & wanted) >= 3:
            header_row = i
            break
    df = pd.read_excel(path, engine=engine, header=header_row).dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    rows = []
    for _, r in df.iterrows():
        row = {}
        for c in df.columns:
            v = r[c]
            if hasattr(v, "isoformat"):          # Timestamp -> ISO date string
                v = v.date().isoformat() if hasattr(v, "date") else v.isoformat()
            row[c] = "" if str(v) == "nan" else str(v)
        rows.append(row)
    print(f"[load] Excel: header detected at row {header_row}, {len(rows)} data rows")
    return rows, list(df.columns)


# ── CLI ──────────────────────────────────────────────────────────────────
def run(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv_path")
    p.add_argument("--source", default="dealytics")
    p.add_argument("--mode", choices=["import", "enrich", "reconcile"], default="enrich")
    p.add_argument("--acknowledge-license", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--trust", action="store_true",
                   help="Structured data from a licensed database is not an LLM guess: "
                        "import with review=False so records don't clog the review queue.")
    args = p.parse_args(argv)

    print(LICENSE_WARNING)
    if not args.acknowledge_license:
        print("Refusing to run without --acknowledge-license. Read the notice above.")
        sys.exit(1)

    mappings = json.loads(MAPPINGS.read_text())
    if args.source not in mappings:
        print(f"No mapping for source '{args.source}'. Available: {list(mappings)}")
        sys.exit(1)
    mapping = mappings[args.source]

    rows, headers = load_rows(args.csv_path, mapping)
    # header sanity check: silent column misalignment (e.g. an unquoted comma
    # inside a header) is the most dangerous failure mode — catch it loudly.
    wanted = []
    for k, v in mapping.items():
        if k.startswith("_") or k in ("value_unit", "advisor_delimiter"):
            continue
        if isinstance(v, list):
            wanted += v
        elif isinstance(v, str):        # skip config flags like advisor_roles
            wanted.append(v)
    missing = [w for w in wanted if w and w not in headers]
    if missing:
        print(f"[WARNING] {len(missing)} mapped column(s) not found in this CSV: {missing}")
        print("          Data in those fields will be empty or MISALIGNED. Open the CSV,")
        print("          check the header row (quoting of commas!), and align "
              "config/import_mappings.json before trusting the output.")
    imported, skipped = [], 0
    for row in rows:
        rec = normalize_row(row, mapping, args.source)
        if rec is None:
            skipped += 1
        else:
            imported.append(rec)
    print(f"[import] {len(rows)} rows -> {len(imported)} normalized, {skipped} skipped")
    if args.trust:
        for rec in imported:
            rec["review"] = False

    doc = json.loads(DATA.read_text())
    if args.mode == "reconcile":
        findings = reconcile(doc["deals"], imported)
        out = Path(__file__).parent / "out"
        out.mkdir(exist_ok=True)
        (out / "reconcile_report.json").write_text(json.dumps(findings, indent=1, ensure_ascii=False))
        print(f"[reconcile] {len(findings)} discrepancy(ies) found -> pipeline/out/reconcile_report.json")
        for f_ in findings[:10]:
            print(f"  - {f_['deal']} · {f_['field']}: tracked={f_['tracked']} vs imported={f_['imported']}")
        print("[reconcile] read-only mode — nothing was modified.")
        return
    if args.mode == "enrich":
        stats = enrich(doc["deals"], imported)
        print(f"[enrich] matched {stats['matched']}, filled advisors on {stats['enriched']}")
        if stats["unmatched"]:
            print(f"[enrich] {len(stats['unmatched'])} unmatched (not added — use --mode import): "
                  + ", ".join(stats["unmatched"][:8]) + ("…" if len(stats["unmatched"]) > 8 else ""))
    else:
        doc["deals"], stats = merge(doc["deals"], imported)
        doc["deals"].sort(key=lambda x: x.get("d", ""), reverse=True)
        print(f"[import] {stats}")

    if args.dry_run:
        print("[dry-run] no changes written.")
        return
    doc["meta"]["last_updated"] = dt.datetime.now(dt.timezone.utc).isoformat()
    DATA.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"[done] deals.json updated ({len(doc['deals'])} deals). "
          "New/changed records carry review=True — approve via pipeline/review.py.")


if __name__ == "__main__":
    run()
