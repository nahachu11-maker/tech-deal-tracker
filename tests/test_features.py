"""Offline tests for alerts, digest context, and DART parsing — run: python tests/test_features.py"""
import sys, json, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

# ── alerts: collect() fires once, dedupes on second run ──
import alerts, shutil, tempfile
_tmp = Path(tempfile.mkdtemp())
for _n in ("deals.json", "news.json", "trends.json"):
    shutil.copy(Path("data")/_n, _tmp/_n)
alerts.DEALS, alerts.NEWS, alerts.TRENDS = _tmp/"deals.json", _tmp/"news.json", _tmp/"trends.json"
msgs1, state = alerts.collect({"news_ids": [], "deal_keys": [], "spike_dates": {}})
assert any(m.startswith("🔴") for m in msgs1), "expected importance-3 news alerts from seed data"
first_deal_flood = [m for m in msgs1 if m.startswith("💼")]
assert not first_deal_flood, "first run must not flood deal alerts"
msgs2, state = alerts.collect(state)
assert not [m for m in msgs2 if m.startswith("🔴")], f"news alerts must dedupe: {msgs2}"

# a new deal after baseline DOES alert
deals_doc = json.loads((_tmp/"deals.json").read_text())
deals_doc["deals"].insert(0, {"d":"2026-07-06","type":"M&A","name":"TestCo / Target","v":1.0,"status":"Pending","note":"","review":True})
(_tmp/"deals.json").write_text(json.dumps(deals_doc))
msgs3, state = alerts.collect(state)
assert any("TestCo" in m for m in msgs3), f"new deal should alert: {msgs3}"

# ── digest: context assembly picks up recent important items ──
import digest
digest.NEWS, digest.DEALS, digest.TRENDS = _tmp/"news.json", _tmp/"deals.json", _tmp/"trends.json"
from digest import build_context
ctx = build_context()
assert isinstance(ctx["news"], list) and isinstance(ctx["deals"], list)
assert all(n["importance"] >= 2 for n in ctx["news"]), "digest context must filter importance"
assert any("TestCo" in d["name"] for d in ctx["deals"]), "review-flagged/new deals included"

# ── dart: corp-code XML parsing (mocked, no network) ──
import xml.etree.ElementTree as ET
xml = b"""<result><list><corp_code>00126380</corp_code><corp_name>\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90</corp_name></list>
<list><corp_code>99999999</corp_code><corp_name>OtherCo</corp_name></list></result>"""
wanted = {"삼성전자"}
found = {el.findtext("corp_name"): el.findtext("corp_code")
         for el in ET.fromstring(xml).iter("list") if el.findtext("corp_name") in wanted}
assert found == {"삼성전자": "00126380"}

print("all feature tests passed")
