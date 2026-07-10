# Lessons — procedural memory for the pipeline

This file is injected into the extraction and classification prompts on every
run. It starts nearly empty and accumulates verified lessons via the weekly
distillation loop (pipeline/distill.py -> pull request -> your approval).
Keep it under 6,000 characters — the distiller must consolidate, not append forever.

## Verified extraction rules
- Deal values: only state a number that appears in the source text. "v" is USD billions (a $500M deal is 0.5).
- Minority stakes, strategic investments, and tender offers for <50% are still M&A, but the note must state the stake percentage.

- Debt: "v" is the amount raised; banks listed are bookrunners/underwriters. Bank loans, bonds, converts issued by an ALREADY-public company with no equity component are Debt, not Follow-on.
- Private rounds: "v" is the amount raised, "val" is post-money valuation — never swap them.
- SPAC/de-SPAC: "v" is the announced deal valuation; treat these figures as aspirational and say so in the note.

## Known failure modes
- Licensing agreements, partnerships, and commercial contracts are NOT M&A, whatever the dollar size — skip them.
- "Definitive agreement" language means status Pending, not Closed. Only "completed"/"closed" language means Closed.

## Anti-patterns (do NOT do)
- Never infer an advisor, value, or date that is not in the text.
- Never upgrade importance to 3 for routine product launches, whatever the company size.
