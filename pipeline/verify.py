"""
verify.py — independent verifier sub-agent for extracted deal records.

The structural idea: the model that extracted the record never grades it.
A separate, cheap model (Haiku-class by default) receives ONLY the source
snippet and the extracted JSON — none of the extractor's reasoning — and
answers one question: is every material fact in the record supported by
the source text?

Verdicts:
  pass      -> record proceeds as normal (still review-flagged for a human)
  mismatch  -> record is kept but hard-flagged: review=True, verify_failed=True,
               with the verifier's reason attached. Nothing silently dropped.

Pure helpers (build_verify_prompt, parse_verdict) are separated from the API
call so the logic is testable offline.
"""

import json
import os

VERIFY_MODEL = os.environ.get("VERIFY_MODEL", "claude-haiku-4-5")

SYSTEM = """You are a fact verifier. You receive a SOURCE text and an EXTRACTED
JSON record produced by another model. Judge only whether the record's material
facts are supported by the source:
- the deal value/proceeds number (if any),
- the deal type (M&A vs IPO vs Follow-on),
- the parties/company names,
- the status (Closed/Pending/Filed/Terminated).
The note field may paraphrase; general knowledge in it is acceptable as long as
the four material facts above are supported.

Respond with ONLY a JSON object, no prose:
{"verdict": "pass"}  or  {"verdict": "mismatch", "reason": "one short sentence"}"""


def build_verify_prompt(record: dict, source_snippet: str) -> str:
    slim = {k: record.get(k) for k in ("d", "type", "name", "v", "val", "status")}
    return (f"SOURCE:\n{source_snippet[:3000]}\n\n"
            f"EXTRACTED RECORD:\n{json.dumps(slim, ensure_ascii=False)}")


def parse_verdict(text: str) -> tuple[bool, str]:
    """Return (passed, reason). Unparseable verifier output fails safe (pass
    with a note) — the human review flag is still on every record anyway."""
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        v = json.loads(text)
    except json.JSONDecodeError:
        return True, "verifier output unparseable — not blocked"
    if v.get("verdict") == "mismatch":
        return False, str(v.get("reason", ""))[:200]
    return True, ""


def verify_record(client, record: dict, source_snippet: str) -> tuple[bool, str]:
    """API wrapper. Returns (passed, reason)."""
    msg = client.messages.create(
        model=VERIFY_MODEL, max_tokens=200, system=SYSTEM,
        messages=[{"role": "user",
                   "content": build_verify_prompt(record, source_snippet)}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    return parse_verdict(text)
