"""
audit.py — one-stop audit report for non-technical review.

Aggregates everything a human auditor needs into data/audit.json, which
audit.html renders as a dashboard:

  - the pending-review queue, numbered EXACTLY like pipeline/review.py
    numbers it (so "approve 3" on the Actions Review button matches item #3
    on the audit page)
  - data-quality flags from the janitor sweep (duplicates, stale deals,
    outliers, missing fields)
  - coverage statistics (comps, advisors, provider ids)
  - licensing exposure (what scrub_publish would remove before a public push)
  - recent human verdicts from the feedback log

Read-only over deals.json. Run it after anything that changes data — the
update, import, and review workflows all do.
"""

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "deals.json"
FEEDBACK = ROOT / "data" / "feedback.jsonl"
OUT = ROOT / "data" / "audit.json"

sys.path.insert(0, str(Path(__file__).parent))
from janitor import sweep                    # noqa: E402
from scrub_publish import scrub              # noqa: E402
from import_deals import smart_note          # noqa: E402


def pending_queue(deals: list[dict]) -> list[dict]:
    """Same order as review.py's pending() — numbering must match."""
    out = []
    for i, d in enumerate((x for x in deals if x.get("review")), 1):
        out.append({
            "n": i, "d": d.get("d"), "type": d.get("type"), "name": d.get("name"),
            "v": d.get("v"), "status": d.get("status"), "sector": d.get("sector"),
            "source": d.get("source", "pipeline"),
            "note": smart_note(d.get("note"), 280),
            "source_url": d.get("source_url", ""),
            "verify_failed": bool(d.get("verify_failed")),
        })
    return out


def coverage(deals: list[dict]) -> dict:
    ma = [d for d in deals if d.get("type") == "M&A"]
    comps = [d for d in deals if isinstance(d.get("comps"), dict)]
    return {
        "deals": len(deals),
        "ma": len(ma),
        "with_comps": len(comps),
        "with_premium": sum(1 for d in comps if d["comps"].get("premium_pct") is not None),
        "with_ev_revenue": sum(1 for d in comps if d["comps"].get("ev_revenue") is not None),
        "with_advisors": sum(1 for d in deals if d.get("advisors")),
        "with_uid": sum(1 for d in deals if d.get("uid")),
        "terminated_with_resolution": sum(1 for d in deals
                                          if d.get("status") == "Terminated" and d.get("resolution")),
        "by_source": _count_by(deals, "source"),
        "by_status": _count_by(deals, "status"),
    }


def _count_by(deals: list[dict], key: str) -> dict:
    out: dict = {}
    for d in deals:
        k = d.get(key) or "pipeline"
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _count_auto_merges() -> int:
    if not FEEDBACK.exists():
        return 0
    return sum(1 for ln in FEEDBACK.read_text().splitlines()
               if '"verdict": "auto-merged"' in ln)


def recent_feedback(limit: int = 12) -> list[dict]:
    if not FEEDBACK.exists():
        return []
    lines = FEEDBACK.read_text().strip().splitlines()
    out = []
    for line in reversed(lines[-400:]):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append({"ts": e.get("ts", "")[:10], "verdict": e.get("verdict"),
                    "reason": (e.get("reason") or "")[:120],
                    "name": (e.get("record") or {}).get("name", "")})
        if len(out) >= limit:
            break
    return out


def run() -> None:
    doc = json.loads(DATA.read_text())
    deals = doc["deals"]
    _, lic_stats = scrub(doc, "fields")
    issues = sweep(deals)
    by_check: dict = {}
    for i in issues:
        by_check.setdefault(i.get("issue", "other"), []).append(i)
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "data_last_updated": doc.get("meta", {}).get("last_updated"),
        "pending": pending_queue(deals),
        "quality": {"total_flags": len(issues),
                    "by_check": {k: v[:25] for k, v in by_check.items()}},
        "coverage": coverage(deals),
        "licensing": {"licensed_records": lic_stats["licensed"],
                      "fields_a_public_push_would_strip": lic_stats["fields_stripped"]},
        "auto_merges": _count_auto_merges(),
        "recent_feedback": recent_feedback(),
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"[audit] {len(report['pending'])} pending · {len(issues)} quality flags · "
          f"{lic_stats['licensed']} licensed records -> data/audit.json")


if __name__ == "__main__":
    run()
