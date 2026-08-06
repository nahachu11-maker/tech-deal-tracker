"""
gate.py — the materiality filter that keeps the review queue worth opening.

The extractor is deliberately eager: it would rather surface a marginal deal
than miss a real one. That is the right instinct for recall and the wrong one
for a human queue — a queue holding $38M bolt-ons next to a $111B merger is a
queue nobody clears.

This module is the deterministic counterweight. Four rules, each crisply
decidable, applied after extraction and before anything reaches review:

  1. NO COUNTERPARTY  — "Meta / Unknown Target", "TBD / 3DEO". A deal record
     with an unnamed side can't be verified, compared, or charted.
  2. BELOW FLOOR      — disclosed value under MIN_VALUE_B (default $250M).
  3. OUT OF COVERAGE  — pharma/biotech/medical/consumer signals, unless the
     record also carries a tech signal (semiconductor materials and health-IT
     are in scope for a tech/semis desk; a peptide CDMO is not).
  4. UNDISCLOSED + UNKNOWN PARTIES — value undisclosed AND neither side is a
     tracked or major-tech name. SEC-filing-backed records are exempt: a filed
     IPO is material by virtue of being filed.

Everything dropped is returned with a reason so the run log stays auditable —
a silent filter is how you lose deals without noticing. Tune the floor with
DEAL_MIN_VALUE_B; set it to 0 to disable rule 2 entirely.
"""

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WATCHLIST = ROOT / "config" / "watchlist.json"

MIN_VALUE_B = float(os.environ.get("DEAL_MIN_VALUE_B", "0.25"))

# Rule 1: a named side that isn't actually a name.
NO_COUNTERPARTY_RE = re.compile(
    r"\b(unknown target|undisclosed target|unnamed target|unknown buyer|"
    r"undisclosed buyer|undisclosed company|unnamed|undisclosed cdmo|tbd)\b|"
    r"\(\s*undisclosed[^)]*\)", re.I)

# Rule 3: strong out-of-coverage signals for a technology & semiconductor desk.
OUT_OF_COVERAGE_RE = re.compile(
    r"pharmaceutic|biopharm|biotech|therapeutic|\bcdmo\b|peptide|\bapi manufact|"
    r"clinical|vaccine|oncolog|diagnostic|medical device|life scien|drug develop|"
    r"hospital|dental|veterinar|"
    r"flow control|actuation|industrial automation|mining|oil (and|&) gas|"
    r"apparel|restaurant|grocery|beverage|tobacco|hotel|airline|"
    r"mortgage|insurance broker|wealth management|financial advisory",
    re.I)

# ...unless the record is clearly technology after all. Semiconductor
# materials, health-IT and fintech belong to this desk even though they trip
# the patterns above.
TECH_RESCUE_RE = re.compile(
    r"semiconduct|wafer|foundry|chip|fabless|lithograph|\bhbm\b|\beda\b|packaging|"
    r"software|saas|platform|cloud|data cent|datacent|\bai\b|artificial intelligen|"
    r"machine learning|cyber|fintech|payments|e-?commerce|internet|"
    r"quantum|robotic|sensor|electronic|telecom|network|silicon|compute",
    re.I)


def notable_names() -> set[str]:
    """Watchlist companies plus the major acquirers whose bolt-ons matter
    even when the price isn't disclosed."""
    names = {
        # mega-cap and platform
        "apple", "microsoft", "alphabet", "google", "amazon", "meta", "oracle",
        "ibm", "cisco", "salesforce", "adobe", "sap", "dell", "hp", "hpe",
        "siemens", "dassault", "tesla", "netflix", "spotify", "uber", "airbnb",
        "bytedance", "tencent", "alibaba", "baidu", "naver", "kakao", "softbank",
        "sony", "panasonic", "lg", "hyundai", "nintendo", "shopify", "block",
        "paypal", "stripe", "coinbase", "snap", "pinterest", "reddit", "zoom",
        "atlassian", "servicenow", "workday", "snowflake", "datadog",
        "cloudflare", "twilio", "soundcloud", "figma", "canva", "databricks",
        # AI-native
        "openai", "anthropic", "mistral", "midjourney", "perplexity", "xai",
        "deepmind", "cohere", "hugging face", "scale ai", "runway", "stability",
        "coreweave", "nebius", "lambda", "together ai", "physical intelligence",
        # semiconductors: designers, foundries, equipment, materials, packaging
        "nvidia", "tsmc", "samsung", "sk hynix", "intel", "amd", "broadcom",
        "qualcomm", "micron", "asml", "arm", "marvell", "analog devices",
        "texas instruments", "nxp", "infineon", "stmicro", "renesas",
        "onsemi", "on semiconductor", "microchip", "synaptics", "skyworks",
        "qorvo", "lattice", "rambus", "ambarella", "wolfspeed", "globalfoundries",
        "umc", "smic", "kioxia", "western digital", "seagate", "sandisk",
        "applied materials", "lam research", "kla", "tokyo electron", "advantest",
        "teradyne", "screen", "disco", "entegris", "mks", "coherent", "lumentum",
        "shin-etsu", "sumco", "siltronic", "globalwafers", "amkor", "ase",
        "powertech", "jcet", "cadence", "synopsys", "keysight", "arteris",
        # sponsors that lead tech take-privates
        "blackrock", "kkr", "blackstone", "vista", "thoma bravo", "silver lake",
        "eqt", "advent", "carlyle", "apollo", "bain", "permira", "francisco",
        "general atlantic", "insight partners", "warburg", "cvc", "tpg",
        "sequoia", "andreessen", "a16z", "softbank vision",
    }
    try:
        wl = json.loads(WATCHLIST.read_text()).get("watchlist", [])
        names |= {str(c.get("name", "")).lower() for c in wl if c.get("name")}
    except (OSError, json.JSONDecodeError):
        pass
    return {n for n in names if n}


def _has_notable(name: str, notable: set[str]) -> bool:
    low = (name or "").lower()
    return any(n in low for n in notable)


def judge(rec: dict, notable: set[str] | None = None) -> str | None:
    """Return a drop reason, or None to keep the record."""
    notable = notable if notable is not None else notable_names()
    name = rec.get("name", "") or ""
    blob = f"{name} {rec.get('sector','')} {rec.get('note','')}"

    if NO_COUNTERPARTY_RE.search(name):
        return "no named counterparty"

    v = rec.get("v")
    if isinstance(v, (int, float)) and MIN_VALUE_B > 0 and v < MIN_VALUE_B:
        return f"below ${MIN_VALUE_B*1000:.0f}M materiality floor (${v*1000:.0f}M)"

    if OUT_OF_COVERAGE_RE.search(blob) and not TECH_RESCUE_RE.search(blob):
        return "outside technology & semiconductor coverage"

    if v is None:
        sec_backed = "sec.gov" in (rec.get("source_url") or "").lower()
        if not sec_backed and not _has_notable(name, notable):
            return "undisclosed value and no tracked or major-tech party"

    return None


def apply(records: list[dict], verbose: bool = True) -> tuple[list[dict], list[dict]]:
    """Split records into (kept, dropped). Dropped records carry _gate_reason."""
    notable = notable_names()
    kept, dropped = [], []
    for r in records:
        reason = judge(r, notable)
        if reason:
            r["_gate_reason"] = reason
            dropped.append(r)
        else:
            kept.append(r)
    if verbose:
        print(f"[gate] {len(records)} extracted -> {len(kept)} kept, "
              f"{len(dropped)} filtered (floor=${MIN_VALUE_B*1000:.0f}M)", flush=True)
        for r in dropped:
            print(f"[gate]   drop: {r.get('name','?')[:52]} — {r['_gate_reason']}",
                  flush=True)
    return kept, dropped
