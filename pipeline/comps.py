"""
comps.py — precedent-transaction metrics for M&A deals.

Called from extract.py after a new M&A record passes through: a Sonnet call
extracts premium/multiples/consideration from the source text, a Haiku call
verifies the numbers against the source (maker/checker, as everywhere else),
and the result is attached as record["comps"]. Null beats a guess throughout.
"""

import json
import os

EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "claude-sonnet-4-6")
VERIFY_MODEL = os.environ.get("VERIFY_MODEL", "claude-haiku-4-5")

SYSTEM_EXTRACT = """You extract precedent-transaction metrics from M&A announcement text for a
comps database. You receive the announcement text and the deal record
(acquirer, target, value).

Respond with ONLY a JSON object, no prose, no fences:
{
 "premium_pct": number or null,
 "premium_basis": "string or null",
 "ev_revenue": number or null,
 "ev_ebitda": number or null,
 "consideration": "cash" | "stock" | "cash-and-stock" | "unstated",
 "price_per_share": number or null,
 "financing": "string or null",
 "termination_fee": number or null,
 "computed_fields": []
}

Rules:
1. null beats a guess. An unstated premium is null, not an estimate.
2. If you compute a multiple from two stated figures, list it in computed_fields
   and round to one decimal.
3. Percentages as numbers (32.5 not "32.5%"). Money in USD billions.
4. If the text is not an M&A announcement, return {"skip": true}."""

SYSTEM_VERIFY = """You verify extracted numbers against a source text. You receive SOURCE and
EXTRACTED (a JSON of deal metrics).

For each non-null number in EXTRACTED, check it appears in SOURCE (allowing
computed fields listed in computed_fields to derive from two stated numbers).

Respond with ONLY:
{"verdict":"pass"}
or
{"verdict":"mismatch","fields":["field1"],"reason":"one short sentence"}"""

FIELDS = ("premium_pct", "premium_basis", "ev_revenue", "ev_ebitda",
          "consideration", "price_per_share", "financing", "termination_fee",
          "computed_fields")


def parse_comps(text: str) -> dict | None:
    """Pure: parse extractor output into a clean comps dict, or None."""
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        c = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(c, dict) or c.get("skip"):
        return None
    clean = {k: c.get(k) for k in FIELDS}
    if clean.get("consideration") not in ("cash", "stock", "cash-and-stock", "unstated"):
        clean["consideration"] = "unstated"
    if all(clean.get(k) in (None, "unstated", []) for k in FIELDS):
        return None  # nothing extracted — don't attach an empty shell
    return clean


def has_signal(comps: dict | None) -> bool:
    """Pure: worth attaching only if at least one hard number came out."""
    if not comps:
        return False
    return any(comps.get(k) is not None for k in
               ("premium_pct", "ev_revenue", "ev_ebitda", "price_per_share", "termination_fee"))


def extract_comps(client, record: dict, source: str) -> dict | None:
    """Sonnet extraction + Haiku verify. Returns comps dict (possibly with
    verify_failed flag) or None."""
    ctx = {"acquirer_target": record.get("name"), "value_bn": record.get("v")}
    msg = client.messages.create(
        model=EXTRACT_MODEL, max_tokens=500, system=SYSTEM_EXTRACT,
        messages=[{"role": "user",
                   "content": f"DEAL:\n{json.dumps(ctx)}\n\nANNOUNCEMENT TEXT:\n{source[:3000]}"}])
    comps = parse_comps("".join(b.text for b in msg.content if b.type == "text"))
    if not has_signal(comps):
        return None
    vmsg = client.messages.create(
        model=VERIFY_MODEL, max_tokens=200, system=SYSTEM_VERIFY,
        messages=[{"role": "user",
                   "content": f"SOURCE:\n{source[:3000]}\n\nEXTRACTED:\n{json.dumps(comps)}"}])
    vtext = "".join(b.text for b in vmsg.content if b.type == "text")
    vtext = vtext.replace("```json", "").replace("```", "").strip()
    try:
        verdict = json.loads(vtext)
    except json.JSONDecodeError:
        verdict = {"verdict": "pass"}
    if verdict.get("verdict") == "mismatch":
        comps["verify_failed"] = True
        comps["verify_reason"] = str(verdict.get("reason", ""))[:200]
    return comps
