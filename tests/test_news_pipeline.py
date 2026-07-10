"""Offline tests for news clustering + trend math — run: python tests/test_news_pipeline.py"""
import sys, json, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
from news_feed_poll import cluster, word_set
from update_news import compute_trends, TRENDS

now = dt.datetime.now(dt.timezone.utc)
ts = lambda h: (now - dt.timedelta(hours=h)).isoformat()

# 1. near-identical headlines from different outlets collapse into one cluster
items = [
 {"title":"Qualcomm to acquire Modular for $4 billion","url":"a","published":ts(3),"outlet":"Reuters","snippet":""},
 {"title":"Qualcomm acquires AI startup Modular in $4 billion deal","url":"b","published":ts(2),"outlet":"Bloomberg","snippet":""},
 {"title":"TSMC June sales jump on AI demand","url":"c","published":ts(1),"outlet":"Nikkei","snippet":""},
]
cl = cluster(items)
assert len(cl) == 2, f"expected 2 clusters, got {len(cl)}: {[c['title'] for c in cl]}"
qc = next(c for c in cl if "Qualcomm" in c["title"])
assert qc["source_count"] == 2 and qc["also"][0]["outlet"] == "Bloomberg"

# 2. unrelated headlines never merge
a = word_set("Nvidia earnings beat expectations")
b = word_set("Apple launches new iPhone in India")
assert len(a & b) / len(a | b) < 0.55

# 3. trend math: entity mentioned 4x today vs quiet history -> spiking
today = now.date().isoformat()
def mk(day_offset, comp):
    return {"ts": (now - dt.timedelta(days=day_offset)).isoformat(), "companies":[comp]}
items = [mk(0,"HotCo")]*4 + [mk(k,"HotCo") for k in (5,9)] + [mk(0,"QuietCo")]
compute_trends(items)
trends = json.loads(TRENDS.read_text())["trends"]
hot = next(t for t in trends if t["entity"]=="HotCo")
assert hot["today"] == 4 and hot["spiking"] is True, hot
quiet = next(t for t in trends if t["entity"]=="QuietCo")
assert quiet["spiking"] is False

print("all 3 news-pipeline tests passed")
