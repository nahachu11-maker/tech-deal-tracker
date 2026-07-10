"""Offline tests for the seven-feature pack — run: python tests/test_ideas.py"""
import sys, json, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

# ── lifecycle: selection + label parsing ──
from lifecycle import needs_tag, parse_labels
assert needs_tag({"ib_tags":["M&A","Regulatory"]}) and not needs_tag({"ib_tags":["Product"]})
labs = parse_labels('```json\n[{"status":"rumor","confidence":"high"},{"status":"closed","confidence":"low"}]\n```', 2)
assert labs[0]["status"]=="rumor" and labs[1]["status"]=="closed"
assert parse_labels('[{"status":"rumor"}]', 2) is None            # length mismatch -> fail open
assert parse_labels('[{"status":"banana","confidence":"high"}]', 1)[0]["status"]=="not_deal"  # invalid label sanitized
print("lifecycle: selection + parsing OK")

# ── comps: parsing + signal gate ──
from comps import parse_comps, has_signal
c = parse_comps('{"premium_pct":32.5,"premium_basis":"prior close","ev_revenue":null,"ev_ebitda":null,"consideration":"cash","price_per_share":210,"financing":"$20B committed debt","termination_fee":1.0,"computed_fields":[]}')
assert c["premium_pct"]==32.5 and has_signal(c)
assert parse_comps('{"skip": true}') is None
empty = parse_comps('{"premium_pct":null,"premium_basis":null,"ev_revenue":null,"ev_ebitda":null,"consideration":"unstated","price_per_share":null,"financing":null,"termination_fee":null,"computed_fields":[]}')
assert empty is None                                              # nothing extracted -> no attach
weird = parse_comps('{"premium_pct":30,"consideration":"gold bars","computed_fields":[]}')
assert weird["consideration"]=="unstated"                         # invalid enum sanitized
print("comps: parsing + signal gate OK")

# ── janitor: all five checks on synthetic data ──
from janitor import sweep
today = dt.date(2026, 7, 6)
deals = [
 {"d":"2026-06-01","type":"M&A","name":"Google / Wiz","v":32,"status":"Pending","sector":"Security"},
 {"d":"2026-06-15","type":"M&A","name":"Google Inc / Wiz Inc","v":32,"status":"Pending","sector":"Security"},  # dup
 {"d":"2024-11-01","type":"M&A","name":"OldCo / Target","v":5,"status":"Pending","sector":"SaaS"},             # stale pending (>548d)
 {"d":"2025-05-01","type":"IPO","name":"SlowIPO","v":None,"status":"Filed","sector":"Fintech"},                # stale filed (>365d)
 {"d":"2026-05-01","type":"M&A","name":"TypoCo / X","v":500,"status":"Closed","sector":"AI"},                  # outlier
 {"d":"2026-05-02","type":"IPO","name":"BigRaise","v":20,"status":"Closed","sector":"AI"},                     # IPO proceeds outlier
 {"d":"2026-05-03","type":"M&A","name":"NoSector / Y","v":1,"status":"Closed","sector":""},                    # missing field
]
issues = sweep(deals, today)
kinds = sorted({i["issue"] for i in issues})
assert kinds == ["missing_field","possible_duplicate","stale_filed","stale_pending","value_outlier"], kinds
assert sum(1 for i in issues if i["issue"]=="value_outlier") == 2
clean = sweep([{"d":"2026-06-01","type":"M&A","name":"A / B","v":5,"status":"Closed","sector":"AI"}], today)
assert clean == []
print("janitor: all five checks fire correctly, clean data passes")

# ── memo: context builder shape ──
from memo import build_context
ctx = build_context()
assert set(ctx) == {"week_of","news","deals","trends"} and isinstance(ctx["news"], list)
print("memo: context builder OK")

# ── earnings: item selection filter ──
from earnings import select_items
classified = [
 {"title":"NVDA beats","ib_tags":["Earnings"],"importance":3,"companies":["Nvidia"]},
 {"title":"random co earnings","ib_tags":["Earnings"],"importance":2,"companies":["RandomCo"]},   # not watchlist
 {"title":"NVDA product","ib_tags":["Product"],"importance":3,"companies":["Nvidia"]},            # not earnings
 {"title":"low imp","ib_tags":["Earnings"],"importance":1,"companies":["Nvidia"]},                # low importance
]
sel = select_items(classified, {"Nvidia","TSMC"})
assert len(sel)==1 and sel[0]["title"]=="NVDA beats"
print("earnings: selection filter OK")

print("all seven-feature tests passed")
