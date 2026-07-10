"""
janitor.py — weekly data-quality sweep over deals.json.

Honest design note: the plan document specced this as a Haiku call, but all
five checks are deterministic pattern checks — so this implements them in pure
Python instead. Zero cost, fully testable offline, same output schema the
Haiku prompt would have produced. Deterministic beats a model whenever
deterministic is possible.

Output: data/janitor_report.json — flags only, never edits the data.
The morning digest surfaces the open-issue count.
"""

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEALS = ROOT / "data" / "deals.json"
REPORT = ROOT / "data" / "janitor_report.json"

import re

# words that describe instruments, not parties — never evidence of a duplicate
GENERIC = set("""convertible converts notes note equity offering offerings stake
placement registered direct directs senior due government us follow on ipo
shares stock deal acquisition inc corp company holdings the and
data center centers spv financing bond bonds bonds buyout raise round series
facility resolution separation loans debt funding led capital acquisition
technologies technology group display electronic manufacturing site facilities
systems solutions software semiconductor international global""".split())
DUP_WINDOW = {"M&A": 365, "IPO": 365, "Follow-on": 90}


def name_tokens(name: str) -> frozenset:
    words = re.findall(r"[a-z0-9]+", name.lower())
    return frozenset(w for w in words if w not in GENERIC and len(w) > 1)


def _sides(name: str) -> tuple[frozenset, frozenset]:
    """Acquirer-side and target-side token sets for 'A / B' names."""
    parts = name.split("/", 1)
    left = name_tokens(parts[0])
    right = name_tokens(parts[1]) if len(parts) > 1 else frozenset()
    return left, right


def _is_dup_pair(a: dict, b: dict) -> bool:
    if a["type"] == "M&A":
        # serial acquirers (Thoma Bravo x5 in 2022) must NOT self-match:
        # a duplicate needs overlap on BOTH the acquirer and target side.
        al, ar = _sides(a["name"])
        bl, br = _sides(b["name"])
        return bool(al & bl) and bool(ar & br)
    return len(name_tokens(a["name"]) & name_tokens(b["name"])) >= 2


def check_duplicates(deals: list[dict]) -> list[dict]:
    issues = []
    for i, a in enumerate(deals):
        for b in deals[i + 1:]:
            if a["type"] != b["type"]:
                continue
            if not _is_dup_pair(a, b):
                continue
            try:
                gap = abs((dt.date.fromisoformat(a["d"]) - dt.date.fromisoformat(b["d"])).days)
            except ValueError:
                gap = 0
            if gap <= DUP_WINDOW.get(a["type"], 90):
                issues.append({"issue": "possible_duplicate",
                               "deals": [a["name"], b["name"]],
                               "detail": f"Same type, overlapping names, {gap} days apart."})
    return issues


def check_stale(deals: list[dict], today: dt.date) -> list[dict]:
    issues = []
    for d in deals:
        try:
            age = (today - dt.date.fromisoformat(d["d"])).days
        except (ValueError, KeyError):
            continue
        if d.get("status") == "Pending" and age > 548:
            issues.append({"issue": "stale_pending", "deals": [d["name"]],
                           "detail": f"Pending for {age} days — probably closed or dead; verify."})
        if d.get("status") == "Filed" and age > 365:
            issues.append({"issue": "stale_filed", "deals": [d["name"]],
                           "detail": f"Filed {age} days ago with no pricing — check for withdrawal."})
    return issues


def check_outliers(deals: list[dict]) -> list[dict]:
    issues = []
    for d in deals:
        v = d.get("v")
        if v is None:
            continue
        if d["type"] == "M&A" and (v > 100 or v < 0.01):
            issues.append({"issue": "value_outlier", "deals": [d["name"]],
                           "detail": f"M&A value ${v}B looks like a unit error."})
        if d["type"] == "IPO" and v is not None and v > 15:
            issues.append({"issue": "value_outlier", "deals": [d["name"]],
                           "detail": f"IPO proceeds ${v}B exceed any historical raise — check units."})
        if d["type"] == "Debt" and (v > 60 or v < 0.05):
            issues.append({"issue": "value_outlier", "deals": [d["name"]],
                           "detail": f"Debt raise ${v}B outside plausible range — check units."})
        if d["type"] == "Private" and (v > 70 or v < 0.05):
            issues.append({"issue": "value_outlier", "deals": [d["name"]],
                           "detail": f"Private round ${v}B outside plausible range — check units."})
        if d["type"] == "SPAC" and (v > 100 or v < 0.1):
            issues.append({"issue": "value_outlier", "deals": [d["name"]],
                           "detail": f"De-SPAC value ${v}B outside plausible range — check units."})
    return issues


SENTINELS = ("testco", "mockco", "example", "hotco", "quietco", "bigco / newstartup")


def check_test_artifacts(deals: list[dict]) -> list[dict]:
    """Test fixtures leaking into real data via backup/restore cycles is a
    failure mode this project has actually hit — twice. Tripwire it."""
    return [{"issue": "test_artifact", "deals": [d["name"]],
             "detail": "Name matches a known test fixture — purge it."}
            for d in deals if any(s in d.get("name", "").lower() for s in SENTINELS)]


def check_missing(deals: list[dict]) -> list[dict]:
    issues = []
    for d in deals:
        missing = [f for f in ("sector", "d", "status") if not d.get(f)]
        if missing:
            issues.append({"issue": "missing_field", "deals": [d.get("name", "?")],
                           "detail": f"Missing: {', '.join(missing)}."})
    return issues


def sweep(deals: list[dict], today: dt.date | None = None) -> list[dict]:
    """Pure: run all checks, return the issue list."""
    today = today or dt.date.today()
    return (check_duplicates(deals) + check_stale(deals, today)
            + check_outliers(deals) + check_missing(deals) + check_test_artifacts(deals))


def run() -> None:
    deals = json.loads(DEALS.read_text())["deals"]
    issues = sweep(deals)
    REPORT.write_text(json.dumps({
        "meta": {"last_run": dt.datetime.now(dt.timezone.utc).isoformat(),
                 "deals_checked": len(deals), "issues": len(issues)},
        "issues": issues}, indent=1, ensure_ascii=False))
    print(f"[janitor] {len(deals)} deals checked, {len(issues)} issue(s) flagged")
    for i in issues[:10]:
        print(f"  - {i['issue']}: {i['deals']} — {i['detail']}")


if __name__ == "__main__":
    run()
