# Lessons — procedural memory for the pipeline

This file is injected into the extraction and classification prompts on every
run. It starts nearly empty and accumulates verified lessons via the weekly
distillation loop (pipeline/distill.py -> pull request -> your approval).
Keep it under 6,000 characters — the distiller must consolidate, not append forever.

## Verified extraction rules
- Deal values: only state a number that appears in the source text. "v" is USD billions (a $500M deal is 0.5, a $44M deal is 0.044, a $6.7M deal is 0.0067). Never off by 1000x.
- Convert foreign currency to USD billions and use the USD figure (e.g. KRW 60bn ≈ $44M → 0.044; €20B → use ~21.5, but only if a USD figure is derivable — otherwise state the given amount and note the currency). Never label €20B as "$22.0" without a conversion basis.
- When a deal value or per-share price IS in the source, capture it; do not leave "v"/"val" null. "Billions"/"low nine figures" without a specific number → leave value null (do not invent 0.1 or 5.0).
- Minority stakes, strategic investments, and tender offers for <50% are still M&A, but the note must state the stake percentage.
- Debt: "v" is the amount raised; banks listed are bookrunners/underwriters. Bank loans, bonds, converts issued by an ALREADY-public company with no equity component are Debt, not Follow-on.
- Private rounds: "v" is the amount raised, "val" is post-money valuation — never swap them.
- SPAC/de-SPAC: "v" is the announced deal valuation; treat these figures as aspirational and say so in the note. A de-SPAC that takes a company public is still type SPAC.

## Known failure modes
- Licensing agreements, partnerships, and commercial contracts are NOT M&A, whatever the dollar size — skip them.
- NOT transactions — skip entirely: capex/expansion announcements ("invest $Xb in fabs/US operations", groundbreakings), government/procurement contracts (Pentagon, CHIPS Act, OTA awards), supply/wafer/packaging agreements, compute/data-center leases or capacity deals, construction contracts, loan backstops merely "being considered," and any "deal" with no named counterparty or an unnamed target you cannot identify.
- A capital raise "in preparation to acquire" / "as a precursor to acquiring" is a funding round (type Private, "v" = amount raised), NOT the acquisition itself. Do not mark it status Pending as if the M&A were live.
- Joint ventures are type JV, not M&A or Private. A stake purchase / share conversion / third-party allotment is an investment (Private or M&A-minority with stake %), not a JV and not Debt.
- Status: "definitive agreement"/"agreed to acquire"/"entered into an agreement" = Pending, NOT Closed. Only "completed"/"closed"/"has acquired"/"acquired" (past tense) = Closed. "Shareholders approve" or "extended to [date]" is still Pending. Insolvency/asset sales with a future bid deadline are Pending.
- Empty source text → produce NO record. Never emit a record when the source is blank.
- Date must be supported by the source. If the source says an event occurred in a different year (e.g. "completed in 2025"), do not stamp it with the run date.
- Coverage: only tech and semiconductors. Skip energy, utilities, industrials/machinery, chemicals, medtech/biotech/pharma/CDMO, life-science tools, media, professional services, and other non-tech sectors even when a tech-sounding word appears.
- Materiality floor: skip immaterial tuck-ins, small-cap roll-ups, agency/consultancy acquisitions, undisclosed-value deals between two obscure private parties, and re-acquisitions of small studios. Keep deals only where at least one party is a recognizable public/large company OR a specific value is disclosed above the floor.

## Anti-patterns (do NOT do)
- Never infer an advisor, value, date, target name, or counterparty that is not in the text. If the target/acquirer is "undisclosed" or unnamed, do not fabricate one — and usually skip the record.
- Never classify a capex, contract, lease, JV, supply agreement, or stake-only investment as M&A or Debt to force it into scope.
- Never mark a completed ("acquired"/"completed") deal as Pending, or a "definitive agreement"/"agreed" deal as Closed.
- Never upgrade importance to 3 for routine product launches, whatever the company size.