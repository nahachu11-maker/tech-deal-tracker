"""
distill.py — the loop that closes. Weekly, this:
  1. reads data/feedback.jsonl (human approve/reject verdicts),
  2. asks Claude to propose additions/edits to LESSONS.md that would have
     prevented the rejections, keeping the file under the size cap,
  3. gates the proposal through the eval harness — a proposed LESSONS.md that
     regresses accuracy on the golden cases is REJECTED automatically,
  4. writes the winning proposal to pipeline/LESSONS.md.

Critically, it does NOT commit to main. The workflow opens a PULL REQUEST for
human approval — an agent editing its own instructions unsupervised is exactly
how quality silently drifts, so a person stays in the loop.

Env: ANTHROPIC_API_KEY. Optional DISTILL_MODEL (defaults to a strong model
since this runs weekly and quality matters more than cost here).
"""

import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
FEEDBACK = ROOT / "data" / "feedback.jsonl"
LESSONS = Path(__file__).parent / "LESSONS.md"
MODEL = os.environ.get("DISTILL_MODEL", "claude-opus-4-8")
SIZE_CAP = 6000
MIN_REJECTS = 3  # don't bother the loop until there's a real signal

SYSTEM = """You maintain LESSONS.md, the procedural memory injected into a
deal-extraction model's prompt. You are given the CURRENT LESSONS.md and a batch
of REJECTED extractions (human verdicts with reasons) plus some approved ones.

Propose a REVISED LESSONS.md that would have prevented the rejections, by adding
or sharpening rules under the existing sections (Verified extraction rules /
Known failure modes / Anti-patterns). Rules:
- Consolidate; do not just append. Merge overlapping rules. The file MUST stay
  under 6000 characters.
- Every new rule must generalize beyond one deal — no company-specific trivia.
- Keep the markdown structure and section headers intact.
- Do not weaken existing correct rules.

Respond with ONLY the full revised LESSONS.md content, no prose, no fences."""


def load_feedback(days: int = 7) -> tuple[list, list]:
    if not FEEDBACK.exists():
        return [], []
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    rejects, approves = [], []
    for line in FEEDBACK.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("ts", "") < cutoff:
            continue
        (rejects if e.get("verdict") == "rejected" else approves).append(e)
    return rejects, approves


def propose(client, rejects: list, approves: list) -> str:
    payload = {
        "current_lessons": LESSONS.read_text() if LESSONS.exists() else "",
        "rejected": [{"record": r["record"], "reason": r.get("reason", ""),
                      "source": r.get("source_snippet", "")[:400]} for r in rejects],
        "approved_sample": [a["record"] for a in approves[:10]],
    }
    msg = client.messages.create(
        model=MODEL, max_tokens=2000, system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    return text.replace("```markdown", "").replace("```", "").strip()


def run() -> None:
    import anthropic
    rejects, approves = load_feedback()
    if len(rejects) < MIN_REJECTS:
        print(f"[distill] only {len(rejects)} rejections this week "
              f"(need {MIN_REJECTS}) — nothing to distill.")
        return

    client = anthropic.Anthropic()
    proposed = propose(client, rejects, approves)

    if len(proposed) > SIZE_CAP:
        print(f"[distill] proposal {len(proposed)} chars exceeds cap — discarding.")
        return

    # ── the eval gate ──
    from eval_harness import evaluate
    try:
        before = evaluate()                       # current LESSONS.md
        after = evaluate(lessons_override=proposed)  # proposed LESSONS.md
    except Exception as e:  # noqa: BLE001 — if eval can't run, do not auto-change memory
        print(f"[distill] eval failed ({e}); not modifying LESSONS.md.")
        return

    print(f"[distill] eval accuracy before={before['accuracy']} after={after['accuracy']}")
    if after["accuracy"] < before["accuracy"] - 0.001:
        print("[distill] proposal REGRESSED accuracy — rejected. LESSONS.md unchanged.")
        return

    LESSONS.write_text(proposed)
    # leave a marker the workflow uses for the PR body
    (ROOT / "data" / ".distill_summary.md").write_text(
        f"Distilled {len(rejects)} rejections into LESSONS.md.\n\n"
        f"Eval accuracy: {before['accuracy']} -> {after['accuracy']} "
        f"({before['cases']} golden cases).\n\n"
        f"Reasons addressed:\n" +
        "\n".join(f"- {r.get('reason','(no reason given)')}" for r in rejects[:10]))
    print(f"[distill] LESSONS.md updated (accuracy held). PR will open for review.")


if __name__ == "__main__":
    run()
