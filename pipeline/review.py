"""
review.py — human approval step for auto-extracted deals.

  python pipeline/review.py            # list deals flagged 'needs review'
  python pipeline/review.py approve 3            # approve item #3
  python pipeline/review.py reject 3 value wrong  # reject with a reason
                                       # (reasons teach the weekly distiller)
  python pipeline/review.py approve-all          # everything pending
  python pipeline/review.py approve-all capiq    # only one source (safe bulk)
"""

import datetime as dt
import json
import sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "deals.json"
FEEDBACK = Path(__file__).parent.parent / "data" / "feedback.jsonl"


def log_feedback(record: dict, verdict: str, reason: str = "") -> None:
    """Layer 1 of the self-improving loop: every human verdict becomes a
    labeled example. The weekly distiller mines this file for patterns."""
    entry = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": verdict,               # approved | rejected
        "reason": reason,
        "record": {k: record.get(k) for k in
                   ("d", "type", "name", "v", "val", "sector", "status",
                    "verify_failed", "verify_reason")},
        "source_snippet": record.get("source_snippet", ""),
        "source_url": record.get("source_url", ""),
    }
    with FEEDBACK.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load():
    return json.loads(DATA.read_text())


def save(doc):
    DATA.write_text(json.dumps(doc, indent=1, ensure_ascii=False))


def pending(doc):
    return [d for d in doc["deals"] if d.get("review")]


def main():
    doc = load()
    items = pending(doc)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "list":
        if not items:
            print("Nothing awaiting review.")
        for i, d in enumerate(items, 1):
            v = f"${d['v']}B" if d.get("v") is not None else "undisclosed"
            print(f"[{i}] {d['d']} {d['type']:9} {d['name']} — {v} ({d.get('status')})")
            print(f"     {d.get('note','')[:140]}")
            if d.get("source_url"):
                print(f"     src: {d['source_url']}")
    elif cmd in ("approve", "reject"):
        idx = int(sys.argv[2]) - 1
        target = items[idx]
        reason = " ".join(sys.argv[3:])  # optional: why (rejects especially)
        if cmd == "approve":
            target["review"] = False
            target.pop("verify_failed", None)
            log_feedback(target, "approved", reason)
            print(f"Approved: {target['name']}")
        else:
            doc["deals"].remove(target)
            log_feedback(target, "rejected", reason)
            print(f"Rejected: {target['name']}"
                  + (f" — {reason}" if reason else "  (tip: add a reason — it teaches the pipeline)"))
        save(doc)
    elif cmd == "approve-all":
        source = sys.argv[2] if len(sys.argv) > 2 else None
        batch = [d for d in items if source is None or d.get("source") == source]
        for d in batch:
            d["review"] = False
            log_feedback(d, "approved", f"batch approve-all {source or 'all'}")
        save(doc)
        print(f"Approved {len(batch)} deals"
              + (f" from source '{source}' ({len(items) - len(batch)} others still pending)." if source else "."))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
