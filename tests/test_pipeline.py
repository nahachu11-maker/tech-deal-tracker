"""Offline tests for the merge/dedupe logic — run: python tests/test_pipeline.py"""
import sys, json, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
from update_deals import merge, same_deal, norm_parties, prune

existing = [
 {"d":"2025-03-18","type":"M&A","name":"Google / Wiz","v":32,"sector":"Cloud Security","status":"Pending","note":"x","review":False},
 {"d":"2026-06-01","type":"IPO","name":"Anthropic","v":None,"val":965,"sector":"AI","status":"Filed","note":"x","review":False},
]

# 1. duplicate detection across name variants
dup = {"d":"2025-03-20","type":"M&A","name":"Google Inc / Wiz Inc.","v":32,"status":"Pending","note":"dup"}
assert same_deal(existing[0], dup), "variant names should match"

# 2. status progression Pending -> Closed applies and flags review
closed = {"d":"2026-05-01","type":"M&A","name":"Google / Wiz","v":32,"status":"Closed","note":"deal closed"}
deals, stats = merge([dict(x) for x in existing], [closed])
g = next(d for d in deals if "Wiz" in d["name"])
assert g["status"] == "Closed" and g["review"] is True, f"status update failed: {g}"
assert stats["updated"] == 1 and stats["added"] == 0

# 3. brand-new deal appends with review flag
new = {"d":"2026-07-01","type":"M&A","name":"BigCo / NewStartup","v":2.5,"sector":"AI","status":"Pending","note":"n","review":True}
deals, stats = merge([dict(x) for x in existing], [new])
assert stats["added"] == 1 and len(deals) == 3

# 4. IPO filing -> priced updates value
priced = {"d":"2026-09-10","type":"IPO","name":"Anthropic","v":12,"status":"Closed","note":"priced"}
deals, stats = merge([dict(x) for x in existing], [priced])
a = next(d for d in deals if d["name"] == "Anthropic")
assert a["v"] == 12 and a["status"] == "Closed"

# 5. pruning drops >3y old deals
old = [{"d":"2021-01-01","type":"IPO","name":"Old","v":1,"status":"Closed","note":""}]
assert prune(old + [dict(x) for x in existing]) == [dict(x) for x in existing] or len(prune(old+existing)) == 2

# 6. different companies never merge
assert not same_deal({"d":"2025-01-01","type":"M&A","name":"Apple / Foo"}, {"d":"2025-01-02","type":"M&A","name":"Google / Bar"})

print("all 6 merge-logic tests passed")

# ── self-dedupe: safe pairs merge, risky pairs never do ──
import importlib
import dedupe as _dd
importlib.reload(_dd)
from dedupe import safe_pair, dedupe as selfdedupe, fuse

# Mobileye pattern: same IPO, 1 day + ~2% value apart, different sector label
mob_a = {"d": "2022-10-26", "type": "IPO", "name": "Mobileye", "v": 0.86,
         "val": 16.7, "sector": "Automotive Semiconductors", "status": "Closed",
         "advisors": ["Goldman Sachs"], "note": "Intel carve-out priced at $16.7B."}
mob_b = {"d": "2022-10-25", "type": "IPO", "name": "Mobileye", "v": 0.86,
         "val": 17.0, "sector": "Autonomous Driving", "status": "Closed",
         "advisors": ["Morgan Stanley"], "note": "Intel spun it out at $17B."}
assert safe_pair(mob_a, mob_b), "1-day, same-value IPO must be a safe pair"
survivors, merges = selfdedupe([mob_a, mob_b])
assert len(survivors) == 1 and len(merges) == 1
kept = survivors[0]
assert set(kept["advisors"]) == {"Goldman Sachs", "Morgan Stanley"}, "advisors unioned"

# TCL pattern: same acquirer, DIFFERENT targets -> never merge
tcl_a = {"d": "2024-09-26", "type": "M&A", "name": "TCL / CSOT display stake", "v": 1.5, "status": "Closed"}
tcl_b = {"d": "2025-02-27", "type": "M&A", "name": "TCL / LG Display Guangzhou", "v": 2.0, "status": "Closed"}
assert not safe_pair(tcl_a, tcl_b), "different targets must never be a safe pair"

# Fuji Soft pattern: same parties but 99 days apart -> never auto-merge
fs_a = {"d": "2024-08-08", "type": "M&A", "name": "KKR & / Fuji Soft", "v": 4.0, "status": "Pending"}
fs_b = {"d": "2024-11-15", "type": "M&A", "name": "KKR & / Fuji Soft", "v": 4.0, "status": "Closed"}
assert same_deal(fs_a, fs_b), "same_deal still recognizes them as one story"
assert not safe_pair(fs_a, fs_b), "but 99 days apart must fail the tight dedupe gate"

# Value-outlier pattern: same name/date but values 27% apart -> never merge
dn_a = {"d": "2023-12-12", "type": "M&A", "name": "Dai Nippon / Shinko", "v": 2.16, "status": "Closed"}
dn_b = {"d": "2023-12-12", "type": "M&A", "name": "Dai Nippon / Shinko", "v": 2.75, "status": "Closed"}
assert not safe_pair(dn_a, dn_b), "27% value gap must block auto-merge"

# Consortium subset: two-buyer name matches its single-buyer subset, and the
# fuller name survives the fuse
con_full = {"d": "2024-09-24", "type": "M&A", "name": "Blackstone & Vista / Smartsheet",
            "v": 8.4, "status": "Closed"}
con_sub = {"d": "2024-09-24", "type": "M&A", "name": "Vista / Smartsheet", "v": 8.4,
           "status": "Closed", "advisors": ["Qatalyst"], "comps": {"ev_revenue": 9.0}}
assert safe_pair(con_full, con_sub), "consortium name must match its subset"
surv, mg = selfdedupe([con_sub, con_full])   # richer one first
assert len(surv) == 1 and mg
assert surv[0]["name"] == "Blackstone & Vista / Smartsheet", "fuller consortium name must survive"
assert surv[0]["comps"]["ev_revenue"] == 9.0, "richer data preserved"

# idempotent: running again changes nothing
again, mg2 = selfdedupe(surv)
assert len(again) == 1 and not mg2, "dedupe must be idempotent"
print("self-dedupe: safe merges, risky pairs preserved, idempotent OK")
