"""
digest.py — generate the morning briefing.

Gathers the last 24h of classified news (importance >= 2), any deals added
or updated recently, and current trend spikes, then asks Claude to write a
tight analyst-style briefing. Saves to data/digest.json keeping the last 7
days so the digest page has a small archive.

Run daily at 07:00 Pacific via .github/workflows/digest.yml (14:00 UTC).
"""

import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
NEWS = ROOT / "data" / "news.json"
DEALS = ROOT / "data" / "deals.json"
TRENDS = ROOT / "data" / "trends.json"
DIGEST = ROOT / "data" / "digest.json"
MODEL = os.environ.get("DIGEST_MODEL", "claude-sonnet-4-6")

SYSTEM_KR = """You translate an investment-banking morning briefing from English into Korean
for a finance-professional reader in Seoul. You receive the English markdown.

Produce the Korean edition:
- Preserve the exact markdown structure and section headers, translating the
  headers ("Three things that matter" -> "오늘의 핵심 3가지", "Deal flow" ->
  "딜 동향", "Watching" -> "관전 포인트", "System health" -> omit this section
  entirely in the Korean edition).
- Use the register of Korean financial journalism: concise, 합니다체 for body text.
- Finance terms follow Korean market convention: M&A -> 인수합병(M&A) on first
  use then M&A; IPO -> 기업공개(IPO) then IPO; convertible notes -> 전환사채(CB);
  take-private -> 상장폐지 인수.
- Company names: global companies in Korean if a standard rendering exists
  (구글, 엔비디아, 마이크로소프트), otherwise keep English.
- Keep ALL numbers, dates, and dollar amounts identical — do not convert
  currency. $4B -> 40억 달러 style is correct.
- Do not add, remove, or soften any claims. This is an edition, not a rewrite."""


def translate_kr(client, markdown: str) -> str | None:
    try:
        msg = client.messages.create(
            model=MODEL, max_tokens=1400, system=SYSTEM_KR,
            messages=[{"role": "user", "content": markdown}])
        return "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception as e:  # noqa: BLE001 — KR edition is best-effort
        print(f"[digest] KR translation failed: {e}")
        return None

SYSTEM = """You are writing the 6am morning briefing for an investment-banking
analyst covering technology and semiconductors. You receive JSON context:
recent news items, recent deal-tracker entries, and trend data.

Write a briefing in plain markdown with EXACTLY this structure:
## Three things that matter
1-3 numbered items. Each: bold one-line headline, then 2-3 sentences of
so-what for a banker (valuation, financing, regulatory, or competitive angle).
## Deal flow
2-4 sentences on new/updated deals, or "Quiet on the tape." if none.
## Watching
2-3 sentences: trend spikes, upcoming catalysts implied by the news.
## System health
One line only: extraction review stats for the week (approved/rejected counts
from system_health), or omit this section entirely if both counts are zero.

Rules: only use facts present in the context — never invent numbers or events.
Total under 350 words. No preamble, no sign-off. Dry, specific, confident."""


def system_health() -> dict:
    """Self-improvement metrics: last 7 days of review verdicts."""
    fb = ROOT / "data" / "feedback.jsonl"
    if not fb.exists():
        return {"approved": 0, "rejected": 0, "reject_reasons": []}
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
    approved = rejected = 0
    reasons = []
    for line in fb.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("ts", "") < cutoff:
            continue
        if e.get("verdict") == "approved":
            approved += 1
        else:
            rejected += 1
            if e.get("reason"):
                reasons.append(e["reason"])
    jr = ROOT / "data" / "janitor_report.json"
    janitor_issues = 0
    if jr.exists():
        janitor_issues = json.loads(jr.read_text()).get("meta", {}).get("issues", 0)
    return {"approved": approved, "rejected": rejected,
            "reject_reasons": reasons[:5], "data_quality_issues_open": janitor_issues}


def build_context() -> dict:
    """Assemble the last-24h context. Pure function — testable offline."""
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(hours=24)).isoformat()

    news = json.loads(NEWS.read_text())["items"] if NEWS.exists() else []
    recent_news = [
        {"title": n["title"], "summary": n.get("summary", ""),
         "category": n["category"], "ib_tags": n.get("ib_tags", []),
         "importance": n.get("importance", 1), "companies": n.get("companies", [])}
        for n in news if n["ts"] >= cutoff and n.get("importance", 1) >= 2
    ][:25]

    deals = json.loads(DEALS.read_text())["deals"] if DEALS.exists() else []
    recent_deals = [
        {"name": d["name"], "type": d["type"], "v": d.get("v"),
         "status": d.get("status"), "note": d.get("note", "")[:200]}
        for d in deals
        if d.get("review") or d.get("d", "") >= (now - dt.timedelta(days=3)).date().isoformat()
    ][:10]

    trends = json.loads(TRENDS.read_text())["trends"] if TRENDS.exists() else []
    spikes = [t for t in trends if t.get("spiking")][:5]

    return {"as_of": now.isoformat(), "news": recent_news,
            "deals": recent_deals, "spikes": spikes,
            "system_health": system_health()}


def write_digest(markdown: str, markdown_kr: str | None = None) -> None:
    doc = json.loads(DIGEST.read_text()) if DIGEST.exists() else {"digests": []}
    today = dt.date.today().isoformat()
    doc["digests"] = [g for g in doc["digests"] if g["date"] != today]
    entry = {"date": today, "markdown": markdown,
             "generated": dt.datetime.now(dt.timezone.utc).isoformat()}
    if markdown_kr:
        entry["markdown_kr"] = markdown_kr
    doc["digests"].insert(0, entry)
    doc["digests"] = doc["digests"][:7]
    doc["meta"] = {"last_updated": dt.datetime.now(dt.timezone.utc).isoformat()}
    DIGEST.write_text(json.dumps(doc, indent=1, ensure_ascii=False))


def run() -> None:
    import anthropic
    ctx = build_context()
    if not ctx["news"] and not ctx["deals"]:
        write_digest("## Three things that matter\nQuiet overnight — no notable "
                     "items in the last 24 hours.\n## Deal flow\nQuiet on the tape."
                     "\n## Watching\nNormal service resumes with the next news cycle.")
        print("[digest] no material items; wrote quiet-day digest")
        return
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=900, system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}])
    md = "".join(b.text for b in msg.content if b.type == "text").strip()
    md_kr = translate_kr(client, md)
    write_digest(md, md_kr)
    print(f"[digest] wrote briefing for {dt.date.today()} ({len(md)} chars"
          + (", KR edition included)" if md_kr else ", KR edition skipped)"))


if __name__ == "__main__":
    run()
