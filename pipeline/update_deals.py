"""
update_deals.py — merge freshly extracted deals into data/deals.json.

Responsibilities:
  1. Dedupe: a new record matching an existing deal (same normalized parties,
     within 120 days) is treated as an UPDATE, not a new row.
  2. Status changes (Pending -> Closed, Filed -> Closed/Priced) are applied
     but flagged review=True so a human confirms them in the UI.
  3. Brand-new deals are appended with review=True.
  4. meta.last_updated is bumped, and deals older than the rolling 5-year
     window are pruned.

Run the full pipeline:
  python pipeline/edgar_poll.py && python pipeline/news_poll.py \
    && python pipeline/extract.py && python pipeline/update_deals.py
"""

import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "deals.json"
EXTRACTED = Path(__file__).parent / "out" / "extracted.json"

WINDOW_DAYS = 5 * 365
STATUS_RANK = {"Filed": 0, "Pending": 1, "Terminated": 2, "Closed": 2}

# How far apart two records can be dated and still be the same deal.
# M&A: announcement -> close can take ~2 years (HPE/Juniper, Google/Wiz).
# IPO: confidential filing -> pricing is typically 3-12 months.
# Follow-on: serial issuers (AST SpaceMobile raised twice in 7 months),
# so a tight window prevents distinct raises from collapsing into one.
MATCH_WINDOW = {"M&A": 900, "IPO": 400, "Follow-on": 120, "Debt": 120, "SPAC": 400, "Private": 120}


ALIASES = {"alphabet": "google", "hewlett": "hpe", "meta platforms": "meta",
           "block": "square", "x corp": "twitter"}


def norm_parties(name: str) -> frozenset:
    """'Google / Wiz' -> {'google','wiz'}; strips suffixes so variants match."""
    parts = re.split(r"[/—&+]| and ", name)
    drop = re.compile(r"\b(inc|corp|corporation|holdings?|technologies|systems|"
                      r"company|ltd|plc|co|the|—.*)\b\.?", re.I)
    cleaned = set()
    for p in parts:
        p = drop.sub("", p.lower())
        p = re.sub(r"[^a-z0-9 ]", "", p).strip()
        if p:
            tok = p.split()[0] if p.split() else p
            cleaned.add(ALIASES.get(tok, tok))
    return frozenset(cleaned)


def note_chopped(note) -> bool:
    """True if a note looks truncated mid-sentence or carries the legacy
    '[NN% stake]' suffix that older importers welded onto a chopped note."""
    n = str(note or "").rstrip()
    if not n:
        return False
    if n.endswith("% stake]"):
        return True
    return n[-1] not in ".!?…\"')"


def same_deal(a: dict, b: dict) -> bool:
    # Exact match on provider IDs (e.g. CapIQ's IQTR...) trumps fuzzy logic:
    # same uid = same deal, two different uids = two different deals.
    ua, ub = a.get("uid"), b.get("uid")
    if ua and ub:
        return ua == ub
    if a["type"] != b["type"]:
        return False
    pa, pb = norm_parties(a["name"]), norm_parties(b["name"])
    if not (pa & pb) or (a["type"] == "M&A" and len(pa & pb) < 2 and pa != pb):
        # Consortium subset: "Blackstone & Vista / Smartsheet" vs
        # "Vista / Smartsheet" — same target, one buyer set contains the
        # other. Accept when the shared side is a strict superset/subset and
        # at least the target (the smaller side) fully overlaps.
        if a["type"] == "M&A" and (pa < pb or pb < pa) and (pa & pb):
            pass
        else:
            return False
    try:
        da = dt.date.fromisoformat(a["d"])
        db = dt.date.fromisoformat(b["d"])
    except ValueError:
        return True
    return abs((da - db).days) <= MATCH_WINDOW.get(a["type"], 120)


def merge(existing: list[dict], new: list[dict]) -> tuple[list[dict], dict]:
    stats = {"added": 0, "updated": 0, "duplicates": 0}
    for rec in new:
        match = next((e for e in existing if same_deal(e, rec)), None)
        if match is None:
            existing.append(rec)
            stats["added"] += 1
            continue
        # status progression or value discovery -> update in place, flag for review
        changed = False
        if STATUS_RANK.get(rec.get("status"), -1) > STATUS_RANK.get(match.get("status"), -1):
            match["status"] = rec["status"]
            changed = True
        if match.get("v") is None and rec.get("v") is not None:
            match["v"] = rec["v"]
            changed = True
        # silent backfill (no review flag): provider id, comps fields the
        # match lacks, and qualitative fields — fill-only, never overwrite.
        if rec.get("uid") and not match.get("uid"):
            match["uid"] = rec["uid"]
        # note repair: an identical deal (same provider id) whose stored note
        # was chopped mid-sentence by an older importer gets the clean summary.
        if (rec.get("uid") and rec.get("uid") == match.get("uid")
                and rec.get("note") and note_chopped(match.get("note"))):
            match["note"] = rec["note"]
        if rec.get("stake_pct") is not None and match.get("stake_pct") is None:
            match["stake_pct"] = rec["stake_pct"]
        if rec.get("comps"):
            mc = match.setdefault("comps", {})
            for k, v in rec["comps"].items():
                if v is not None and mc.get(k) in (None, "", "unstated"):
                    mc[k] = v
        for k in ("sellers", "attitude", "ticker", "resolution"):
            if rec.get(k) and not match.get(k):
                match[k] = rec[k]
        if rec.get("advisors") and not match.get("advisors"):
            match["advisors"] = rec["advisors"]
        if changed:
            match["review"] = True
            match["note"] = match.get("note", "") + f" [Auto-update {dt.date.today()}: {rec.get('note','')[:200]}]"
            stats["updated"] += 1
        else:
            stats["duplicates"] += 1
    return existing, stats


def prune(deals: list[dict]) -> list[dict]:
    cutoff = (dt.date.today() - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    return [d for d in deals if d.get("d", "9999") >= cutoff]


def run() -> None:
    doc = json.loads(DATA.read_text())
    new = json.loads(EXTRACTED.read_text()) if EXTRACTED.exists() else []

    deals, stats = merge(doc["deals"], new)
    deals = prune(deals)
    deals.sort(key=lambda x: x.get("d", ""), reverse=True)

    doc["deals"] = deals
    doc["meta"]["last_updated"] = dt.datetime.now(dt.timezone.utc).isoformat()
    doc["meta"]["last_run_stats"] = stats
    DATA.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"[update_deals] {stats} | total deals: {len(deals)}")


if __name__ == "__main__":
    run()
