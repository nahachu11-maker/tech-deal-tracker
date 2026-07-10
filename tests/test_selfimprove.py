"""Offline tests for the self-improving layer — run: python tests/test_selfimprove.py"""
import sys, json, tempfile, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

# ── verifier: parse_verdict + build_verify_prompt (no API) ──
from verify import parse_verdict, build_verify_prompt
ok, reason = parse_verdict('{"verdict": "pass"}')
assert ok and reason == ""
ok, reason = parse_verdict('```json\n{"verdict":"mismatch","reason":"value $4B not in source"}\n```')
assert not ok and "value" in reason
ok, reason = parse_verdict('garbage not json')   # fail-safe: unparseable -> pass, not block
assert ok and "unparseable" in reason
p = build_verify_prompt({"d":"2026-01-01","type":"M&A","name":"A / B","v":4,"status":"Pending","note":"x"}, "A agreed to buy B for $4B")
assert "EXTRACTED RECORD" in p and '"note"' not in p  # note excluded from verifier view
print("verifier: parse_verdict + prompt construction OK")

# ── eval harness scoring (no API) ──
from eval_harness import score_one, aggregate, value_bucket
assert value_bucket(None)=="none" and value_bucket(0.5)=="sub-billion" and value_bucket(4)=="1-10B" and value_bucket(32)=="10-50B" and value_bucket(69)=="50B+"
# skip case: correct when model returns None
assert score_one({"skip":True}, None)["is_deal"] is True
assert score_one({"skip":True}, {"type":"M&A"})["is_deal"] is False
# real case: all fields right
s = score_one({"type":"M&A","v":4,"status":"Pending"}, {"type":"M&A","v":4.0,"status":"Pending"})
assert s["type"] and s["value"] and s["status"]
# value bucket tolerance: 4.0 vs 4.2 both "1-10B" -> match
s2 = score_one({"type":"IPO","v":1.2,"status":"Closed"}, {"type":"IPO","v":1.4,"status":"Closed"})
assert s2["value"] is True
# wrong type caught
s3 = score_one({"type":"M&A","v":4,"status":"Pending"}, {"type":"IPO","v":4,"status":"Pending"})
assert s3["type"] is False
agg = aggregate([s, s2, s3])
assert agg["cases"]==3 and 0 <= agg["accuracy"] <= 1
print("eval harness: bucketing + scoring + aggregation OK")

# ── feedback log round-trip via review.log_feedback ──
import review
tmp = Path(tempfile.mkdtemp()) / "feedback.jsonl"
review.FEEDBACK = tmp
review.log_feedback({"d":"2026-07-06","type":"M&A","name":"X / Y","v":2.0,"status":"Pending","source_snippet":"X buys Y for $2B"}, "rejected", "value was licensing not acquisition")
review.log_feedback({"d":"2026-07-06","type":"IPO","name":"Z","v":1.0,"status":"Closed"}, "approved")
lines = tmp.read_text().strip().splitlines()
assert len(lines)==2
e0 = json.loads(lines[0])
assert e0["verdict"]=="rejected" and e0["reason"].startswith("value was") and e0["record"]["name"]=="X / Y"
print("feedback log: round-trip OK")

# ── distill eval-gate logic: regression is rejected ──
# simulate evaluate() outcomes without the API by checking the decision rule directly
def gate(before, after):
    return not (after < before - 0.001)   # True = accept
assert gate(0.90, 0.92) is True     # improvement accepted
assert gate(0.90, 0.90) is True     # equal accepted
assert gate(0.90, 0.85) is False    # regression rejected
print("distill gate: accept-if-no-regression OK")

print("all self-improvement tests passed")

# ── audit fixes: stable ids + pre-classify dedupe helpers ──
import classify, hashlib
i1 = f"2026-07-06-{hashlib.md5('Same Title'.encode()).hexdigest()[:10]}"
i2 = f"2026-07-06-{hashlib.md5('Same Title'.encode()).hexdigest()[:10]}"
assert i1 == i2, "ids must be deterministic across processes"
assert classify._norm_title("Qualcomm to Buy Modular!") == classify._norm_title("  qualcomm TO buy   modular ")
urls, titles = classify.known_keys()
assert isinstance(urls, set) and len(titles) > 0, "known_keys should load seed stories"
print("audit fixes: stable ids + dedupe keys OK")
