"""
scrub_publish.py — licensing guard for public deployment.

deals.json mixes freely-publishable records (EDGAR/RSS extraction, manual
seeds) with records imported from licensed databases (tagged "licensed":
true). Deal facts like "X acquired Y for $Z" are independently public, but
the licensed provider's derived analytics (multiples, premia, LTM
financials) are their product — republishing those on a public site is a
terms-of-service problem.

Modes:
  --check                Report what a scrub would remove. Read-only.
  --write PATH           Write a scrubbed copy (default data/deals.public.json).
  --strategy fields      (default) Keep licensed deals but strip the
                         licensed-only analytics: comps, ltm figures,
                         sellers, attitude, resolution, uid. Basic deal
                         facts (name/date/value/status) remain — they are
                         verifiable from public reporting.
  --strategy records     Drop licensed records entirely. Strictest.
  --in-place             DANGEROUS: overwrite data/deals.json itself.
                         Use only right before a public push, on a branch.

If you deploy to GitHub Pages, point the workflow at the scrubbed file or
keep the repo private and skip this entirely.
"""

import argparse
import copy
import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "deals.json"
LICENSED_ONLY_FIELDS = ("comps", "sellers", "attitude", "resolution", "uid",
                        "ticker", "licensed", "advisor_source")


def scrub(doc: dict, strategy: str) -> tuple[dict, dict]:
    doc = copy.deepcopy(doc)
    stats = {"total": len(doc["deals"]), "licensed": 0,
             "records_dropped": 0, "fields_stripped": 0}
    kept = []
    for d in doc["deals"]:
        if not d.get("licensed"):
            # merge() backfills licensed analytics onto pipeline-sourced deals;
            # those comps blocks are tagged source="import" — strip them too,
            # along with fields that only ever originate from licensed imports.
            if isinstance(d.get("comps"), dict) and d["comps"].get("source") == "import":
                del d["comps"]
                stats["fields_stripped"] += 1
            for f in ("sellers", "attitude", "resolution", "uid", "advisor_source"):
                if f in d:
                    del d[f]
                    stats["fields_stripped"] += 1
            kept.append(d)
            continue
        stats["licensed"] += 1
        if strategy == "records":
            stats["records_dropped"] += 1
            continue
        for f in LICENSED_ONLY_FIELDS:
            if f in d:
                del d[f]
                stats["fields_stripped"] += 1
        d["source_note"] = "facts verifiable from public reporting; licensed analytics removed"
        kept.append(d)
    doc["deals"] = kept
    doc.setdefault("meta", {})["scrubbed"] = strategy
    return doc, stats


def run(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    p.add_argument("--write", default=str(DATA.parent / "deals.public.json"))
    p.add_argument("--strategy", choices=["fields", "records"], default="fields")
    p.add_argument("--in-place", action="store_true")
    args = p.parse_args(argv)

    doc = json.loads(DATA.read_text())
    scrubbed, stats = scrub(doc, args.strategy)
    print(f"[scrub] {stats['total']} deals · {stats['licensed']} licensed · "
          f"strategy={args.strategy} -> {stats['records_dropped']} records dropped, "
          f"{stats['fields_stripped']} fields stripped")
    if args.check:
        print("[check] read-only, nothing written.")
        return
    out = DATA if args.in_place else Path(args.write)
    out.write_text(json.dumps(scrubbed, indent=1, ensure_ascii=False))
    print(f"[done] wrote {out}"
          + (" — deals.json OVERWRITTEN, licensed analytics are gone from the working file."
             if args.in_place else
             " — deploy this file publicly; keep deals.json local/private."))


if __name__ == "__main__":
    run()
