"""
review.py — human approval step for auto-extracted deals.

  python pipeline/review.py            # list deals flagged 'needs review'
  python pipeline/review.py approve 3            # approve item #3
  python pipeline/review.py approve 1 3 7       # several at once
  python pipeline/review.py approve 1-12        # a range
  python pipeline/review.py approve 1-5 9 14-16 # ranges and singles mixed
  python pipeline/review.py reject 3 value wrong  # reject with a reason
  python pipeline/review.py reject 92 87 78 duplicate rows
                                       # (reasons teach the weekly distiller)
  Numbers are resolved against the list BEFORE anything changes, so order
  never matters and the queue re-indexing after a delete cannot bite you.
  python pipeline/review.py approve-all          # everything pending
  python pipeline/review.py approve-all capiq    # only one source (safe bulk)
  python pipeline/review.py flag semrush         # UNDO an approval: put the
                                                 # deal (matched by name) back
                                                 # in the review queue
"""

import datetime as dt
import json
import re
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



def parse_indices(tokens: list[str], count: int) -> tuple[list[int], list[str]]:
    """Leading '3', '1-5', '1,2,3' tokens -> 0-based indices (deduped, in the
    order given). Parsing stops at the first token that isn't index-like; the
    rest is the reason. Raises ValueError naming any out-of-range number so a
    typo aborts the whole batch instead of half-applying it."""
    idx: list[int] = []
    seen: set[int] = set()
    i = 0
    for i, tok in enumerate(tokens):
        pieces = [p for p in tok.replace(",", " ").split() if p]
        if not pieces or not all(re.fullmatch(r"\d+(-\d+)?", p) for p in pieces):
            break
        for p in pieces:
            if "-" in p:
                lo, hi = (int(x) for x in p.split("-", 1))
                if lo > hi:
                    lo, hi = hi, lo
                rng = range(lo, hi + 1)
            else:
                rng = [int(p)]
            for n in rng:
                if not 1 <= n <= count:
                    raise ValueError(f"#{n} is out of range (queue has {count} items)")
                if n - 1 not in seen:
                    seen.add(n - 1)
                    idx.append(n - 1)
    else:
        i = len(tokens)
    return idx, tokens[i:]


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
        try:
            idxs, rest = parse_indices(sys.argv[2:], len(items))
        except ValueError as e:
            print(f"Nothing changed — {e}")
            return
        if not idxs:
            print(f"Usage: review.py {cmd} 3   |   {cmd} 1 4 9   |   {cmd} 2-11 [reason]")
            return
        reason = " ".join(rest)
        # Resolve to the record objects first: after this point index numbers
        # are irrelevant, so removals can't shift anything out from under us.
        targets = [items[i] for i in idxs]

        if cmd == "approve":
            for t in targets:
                t["review"] = False
                t.pop("verify_failed", None)
                log_feedback(t, "approved", reason)
            print(f"Approved {len(targets)} deal(s):")
        else:
            for t in targets:
                doc["deals"].remove(t)
                log_feedback(t, "rejected", reason)
            print(f"Rejected {len(targets)} deal(s)"
                  + (f" — {reason}" if reason
                     else "  (tip: add a reason — it teaches the pipeline)") + ":")
        for n, t in zip(idxs, targets):
            print(f"  [{n+1}] {t['name']}")
        left = len([d for d in doc["deals"] if d.get("review")])
        print(f"{left} item(s) still pending.")
        save(doc)
    elif cmd == "flag":
        term = " ".join(sys.argv[2:]).strip().lower()
        if not term:
            print("Usage: review.py flag <part of the deal name>  e.g. flag semrush")
            return
        matches = [d for d in doc["deals"] if term in d["name"].lower()]
        if not matches:
            print(f"No deal name contains '{term}'.")
        elif len(matches) > 1:
            print(f"'{term}' matches {len(matches)} deals — be more specific:")
            for d in matches[:10]:
                print(f"  {d['d']}  {d['name']}")
        else:
            d = matches[0]
            if d.get("review"):
                print(f"'{d['name']}' is already in the review queue.")
            else:
                d["review"] = True
                log_feedback(d, "re-flagged", "approval undone by reviewer")
                save(doc)
                print(f"Re-flagged for review: {d['name']} ({d['d']}). "
                      "It's back in the pending queue.")

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
