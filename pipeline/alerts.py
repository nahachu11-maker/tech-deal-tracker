"""
alerts.py — push notifications via Slack or Discord webhook.

Fires for: importance-3 news, new trend SPIKEs, and new deal-tracker entries.
Set ALERT_WEBHOOK_URL (repo secret). Discord URLs are auto-detected;
anything else is treated as Slack-compatible ({"text": ...}).

Dedupe: data/.alert_state.json (committed) remembers what was already sent,
so re-runs never double-ping. Stdlib only.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
NEWS = ROOT / "data" / "news.json"
DEALS = ROOT / "data" / "deals.json"
TRENDS = ROOT / "data" / "trends.json"
STATE = ROOT / "data" / ".alert_state.json"
WEBHOOK = os.environ.get("ALERT_WEBHOOK_URL", "")
CONFIG = json.loads((ROOT / "config" / "watchlist.json").read_text()).get("alerts", {})


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"news_ids": [], "deal_keys": [], "spike_dates": {}}


def collect(state: dict) -> tuple[list[str], dict]:
    """Return (messages, new_state). Pure — testable without a webhook."""
    msgs = []
    min_imp = int(CONFIG.get("min_importance", 3))

    news = json.loads(NEWS.read_text())["items"] if NEWS.exists() else []
    sent = set(state["news_ids"])
    for n in news:
        if n.get("importance", 1) >= min_imp and n["id"] not in sent:
            tag = "/".join(n.get("ib_tags", [])[:2])
            msgs.append(f"🔴 {n['title']}" + (f" [{tag}]" if tag else "")
                        + (f"\n{n.get('summary','')}" if n.get("summary") else ""))
            state["news_ids"].append(n["id"])
    state["news_ids"] = state["news_ids"][-500:]

    if CONFIG.get("alert_on_spikes", True) and TRENDS.exists():
        today = datetime.now(timezone.utc).date().isoformat()
        for t in json.loads(TRENDS.read_text())["trends"]:
            if t.get("spiking") and state["spike_dates"].get(t["entity"]) != today:
                msgs.append(f"📈 SPIKE: {t['entity']} — {t['today']} mentions today "
                            f"vs {t['avg']}/day average ({t['score']}×)")
                state["spike_dates"][t["entity"]] = today

    if CONFIG.get("alert_on_new_deals", True) and DEALS.exists():
        known = set(state["deal_keys"])
        first_run = not known  # baseline run: record everything, alert nothing
        for d in json.loads(DEALS.read_text())["deals"]:
            key = f"{d['name']}|{d['d']}"
            if key not in known:
                if not first_run:
                    v = f"${d['v']}B" if d.get("v") is not None else "undisclosed"
                    msgs.append(f"💼 New {d['type']}: {d['name']} — {v} ({d.get('status')})")
                state["deal_keys"].append(key)
    state["deal_keys"] = state["deal_keys"][-500:]
    if len(state["spike_dates"]) > 200:  # keep the most recent entries only
        state["spike_dates"] = dict(sorted(state["spike_dates"].items(),
                                           key=lambda kv: kv[1])[-200:])
    return msgs, state


def send(text: str) -> None:
    is_discord = "discord.com" in WEBHOOK or "discordapp.com" in WEBHOOK
    payload = {"content": text[:1900]} if is_discord else {"text": text[:3000]}
    req = urllib.request.Request(
        WEBHOOK, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=15).read()


def run() -> None:
    state = load_state()
    msgs, state = collect(state)
    if not WEBHOOK:
        print(f"[alerts] ALERT_WEBHOOK_URL not set — {len(msgs)} alert(s) suppressed")
    else:
        for m in msgs[:10]:  # cap per run
            try:
                send(m)
            except Exception as e:  # noqa: BLE001
                print(f"[alerts] send failed: {e}", file=sys.stderr)
        print(f"[alerts] sent {min(len(msgs),10)} alert(s)")
    STATE.write_text(json.dumps(state, indent=1))


if __name__ == "__main__":
    run()
