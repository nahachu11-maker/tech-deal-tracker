"""
dedupe.py — collapse duplicates already sitting inside deals.json.

The merge in update_deals only ever checks *incoming* records against the
existing list. Nothing checks the existing list against itself, so any
duplicate that arrived before the dedupe logic existed — or arrived in the
same batch as its twin — lives forever. The janitor flags these; this pass
fixes the safe ones.

SAFETY IS THE WHOLE POINT. A false merge destroys data; a false flag just
costs a glance. So auto-merge only fires when a pair clears every gate:

  - same type
  - same_deal() agrees (handles provider ids, party overlap, consortium
    subsets, and the per-type date window)
  - dates within DEDUPE_DAYS (tighter than same_deal's window)
  - values within DEDUPE_VALUE_TOL, or one side missing a value

Anything short of that stays a janitor flag for human review. Multi-stage
sagas (KKR / Fuji Soft, 99 days apart) and different-target pairs (TCL's two
display deals) deliberately fail these gates.

The survivor is the more complete record (more fields, better status, richer
note); the loser back-fills the survivor's gaps and unions advisors. Every
auto-merge is written to the feedback log so it shows in the Audit Room.
"""

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "deals.json"
FEEDBACK = ROOT / "data" / "feedback.jsonl"

sys.path.insert(0, str(Path(__file__).parent))
from update_deals import same_deal, note_chopped  # noqa: E402

DEDUPE_DAYS = 7
DEDUPE_VALUE_TOL = 0.10       # 10%


def _val(d: dict):
    return d.get("v")


def values_compatible(a: dict, b: dict) -> bool:
    va, vb = _val(a), _val(b)
    if va is None or vb is None:
        return True                       # one side just hasn't got it yet
    hi = max(abs(va), abs(vb))
    if hi == 0:
        return True
    return abs(va - vb) / hi <= DEDUPE_VALUE_TOL


def days_apart(a: dict, b: dict) -> int:
    try:
        return abs((dt.date.fromisoformat(a["d"]) - dt.date.fromisoformat(b["d"])).days)
    except (ValueError, KeyError):
        return 9999


def safe_pair(a: dict, b: dict) -> bool:
    return (a.get("type") == b.get("type")
            and same_deal(a, b)
            and days_apart(a, b) <= DEDUPE_DAYS
            and values_compatible(a, b))


def completeness(d: dict) -> tuple:
    """Higher sorts first -> becomes the survivor."""
    from update_deals import STATUS_RANK
    note = d.get("note") or ""
    return (
        sum(1 for k in ("uid", "comps", "advisors", "ticker", "sellers",
                        "attitude", "resolution", "val", "stake_pct") if d.get(k)),
        STATUS_RANK.get(d.get("status"), -1),
        0 if note_chopped(note) else 1,
        len(note),
        1 if d.get("v") is not None else 0,
    )


def fuse(survivor: dict, loser: dict) -> None:
    """Loser back-fills survivor's gaps only; survivor identity is kept.
    Exception: adopt the loser's name if it spells out strictly more parties
    (e.g. keep 'Blackstone & Vista / Smartsheet' over 'Vista / Smartsheet')."""
    from update_deals import norm_parties
    ps, pl = norm_parties(survivor["name"]), norm_parties(loser["name"])
    if ps < pl:
        survivor["name"] = loser["name"]
    for k, v in loser.items():
        if k in ("d", "name", "type"):
            continue
        if k == "advisors":
            union, seen = [], set()
            for adv in (survivor.get("advisors") or []) + (v or []):
                if adv.lower() not in seen:
                    seen.add(adv.lower()); union.append(adv)
            if union:
                survivor["advisors"] = union
            continue
        if k == "comps" and isinstance(v, dict):
            mc = survivor.setdefault("comps", {})
            for ck, cv in v.items():
                if cv is not None and mc.get(ck) in (None, "", "unstated"):
                    mc[ck] = cv
            continue
        cur = survivor.get(k)
        if cur in (None, "", [], {}) or (k == "note" and note_chopped(cur)):
            survivor[k] = v


def log(survivor: dict, loser: dict) -> None:
    entry = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "auto-merged",
        "reason": f"self-dedupe: folded duplicate into '{survivor['name']}' "
                  f"({loser['d']} / {loser.get('sector','?')} -> {survivor['d']} / {survivor.get('sector','?')})",
        "record": {k: survivor.get(k) for k in ("d", "type", "name", "v", "sector", "status")},
    }
    with FEEDBACK.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def dedupe(deals: list[dict], dry_run: bool = False) -> tuple[list[dict], list[dict]]:
    survivors: list[dict] = []
    merges: list[dict] = []
    for d in deals:
        hit = None
        for s in survivors:
            if safe_pair(s, d):
                hit = s
                break
        if hit is None:
            survivors.append(d)
            continue
        winner, loser = sorted([hit, d], key=completeness, reverse=True)
        merges.append({"kept": winner["name"], "kept_date": winner["d"],
                       "dropped_date": loser["d"],
                       "kept_sector": winner.get("sector"),
                       "dropped_sector": loser.get("sector")})
        if not dry_run:
            fuse(winner, loser)
            log(winner, loser)
        if winner is not hit:              # incoming record won: swap it in
            survivors[survivors.index(hit)] = winner
    return survivors, merges


def run(argv=None) -> None:
    dry = "--dry-run" in (argv or sys.argv[1:])
    doc = json.loads(DATA.read_text())
    survivors, merges = dedupe(doc["deals"], dry_run=dry)
    print(f"[dedupe] {len(doc['deals'])} -> {len(survivors)} deals · "
          f"{len(merges)} duplicate(s) {'found (dry-run)' if dry else 'merged'}")
    for m in merges:
        note = "" if m["kept_sector"] == m["dropped_sector"] else \
               f"  (sector: kept '{m['kept_sector']}', dropped '{m['dropped_sector']}')"
        print(f"    · {m['kept']}: {m['dropped_date']} -> {m['kept_date']}{note}")
    if not dry and merges:
        doc["deals"] = survivors
        DATA.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
        print("[dedupe] deals.json rewritten.")
    elif dry:
        print("[dedupe] dry-run, nothing written.")


if __name__ == "__main__":
    run()
