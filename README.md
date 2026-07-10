# Tech Deal Tracker

An interactive tracker of technology M&A, IPOs, and follow-on raises over a rolling three-year window, with an automated pipeline that keeps the data current.

## How it works

```
 SEC EDGAR ──┐
             ├─> extract.py (Claude API) ─> update_deals.py ─> data/deals.json ─> index.html
 RSS feeds ──┘        structured JSON        dedupe + merge        committed         re-fetches
                                             + review flags        every run         every 5 min
```

- `index.html` — the app. Fetches `data/deals.json` on load and every 5 minutes. Filters by type/year/sector/status/quarter, sortable table, expandable deal notes, quarterly stacked-bar chart that doubles as a filter. Auto-added deals show a "needs review" badge until approved.
- `data/deals.json` — single source of truth. ~65 seed deals (Jul 2023 – Jul 2026) compiled from public reporting.
- `pipeline/edgar_poll.py` — pulls recent S-1/F-1 (IPO filings), 424B (pricings), and merger-related 8-Ks from SEC EDGAR full-text search, filtered to tech SIC codes.
- `pipeline/news_poll.py` — RSS layer (TechCrunch, PR wires) to catch private-target M&A that never touches EDGAR.
- `pipeline/extract.py` — sends each candidate to the Claude API and gets back a structured deal record (or a skip). Conservative on numbers by design.
- `pipeline/update_deals.py` — dedupes against existing deals (type-aware date windows: M&A can close 2 years after announcement; serial follow-ons must stay separate), applies status progressions (Pending→Closed, Filed→Priced), prunes beyond the 3-year window, bumps `last_updated`.
- `pipeline/review.py` — CLI to approve/reject flagged deals before they lose the badge.
- `.github/workflows/update.yml` — runs the whole thing every 6 hours and commits changes.

## Local setup

```bash
pip install -r pipeline/requirements.txt
python -m http.server 8000        # from the repo root
# open http://localhost:8000
```

Run the pipeline manually:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export EDGAR_USER_AGENT="Your Name your@email.com"   # SEC requires a real contact
python pipeline/edgar_poll.py 1    # look back 1 day
python pipeline/news_poll.py
python pipeline/extract.py
python pipeline/update_deals.py
python pipeline/review.py          # approve / reject what came in
```

## Deploy (free, ~10 minutes)

1. Push this folder to a new GitHub repo.
2. Settings → Pages → deploy from branch `main`, root. Your app is now live at `https://<you>.github.io/<repo>/`.
3. Settings → Secrets and variables → Actions: add `ANTHROPIC_API_KEY` and `EDGAR_USER_AGENT`.
4. Actions tab → enable workflows. It runs every 6 hours; use "Run workflow" to trigger manually.

Each run commits an updated `deals.json`, Pages redeploys it automatically, and any open tab picks it up within 5 minutes.

## Schema

```json
{
  "d": "2025-03-18",        // ISO date (announcement / filing / pricing)
  "type": "M&A",            // "M&A" | "IPO" | "Follow-on"
  "name": "Google / Wiz",   // M&A: "Acquirer / Target"; else company name
  "v": 32,                  // value or proceeds in $B; null = undisclosed
  "val": 54.5,              // IPOs only: valuation at pricing / target
  "sector": "Cloud Security",
  "status": "Pending",      // Closed | Pending | Filed | Terminated
  "note": "analyst-style context",
  "review": false           // true until a human approves
}
```

## CapIQ integration (July 2026 upgrade)

Re-importing a refreshed Capital IQ Transaction Screening Report is now the
standard way to keep M&A data authoritative:

```bash
python pipeline/import_deals.py report.xls --source capiq --mode import \
       --acknowledge-license --trust --dry-run    # inspect first
python pipeline/import_deals.py report.xls --source capiq --mode import \
       --acknowledge-license --trust              # then run
```

- **Idempotent re-imports** — records store CapIQ's `CIQ Transaction ID` as
  `uid`; `same_deal()` matches on it exactly, so re-running the same export
  can never duplicate. Fuzzy name/date matching remains the fallback for
  records without ids (pipeline extractions, old seeds).
- **Expanded comps** — beyond premium/EV-Rev/EV-EBITDA, imports now capture
  EV/EBIT, P/E, P/B, 1-week and 1-month premia, implied EV, and target LTM
  revenue/EBITDA (all $ figures stored in $B). Matched existing deals get
  missing comps fields backfilled silently, never overwritten.
- **Qualitative fields** — `sellers` (who exited — PE/VC exit tracking),
  `attitude` (friendly/hostile), `ticker`, and `resolution` (the break story,
  stored on Terminated deals only).
- **`--trust`** imports structured licensed data with `review=False`: it is
  not an LLM guess, so it skips the queue. The review badge stays meaningful
  for EDGAR/RSS extractions. Bulk-clear a backlog per source with
  `python pipeline/review.py approve-all capiq`.
- **`comps.html`** — precedent-transactions view: premium distribution,
  median multiples by year, a sortable comps table, and a broken-deals
  ledger with termination reasons.

### Publishing licensed data — read this before pushing

Deal *facts* are public; a licensed provider's *analytics* (multiples,
premia, LTM financials) are their product. If this repo deploys to public
GitHub Pages, generate a scrubbed data file first:

```bash
python pipeline/scrub_publish.py --check              # see what would be removed
python pipeline/scrub_publish.py                      # writes data/deals.public.json
python pipeline/scrub_publish.py --strategy records   # strictest: drop licensed rows
```

Then either point the deployed pages at `deals.public.json`, or keep the
repo private and skip scrubbing. The scrubber also catches licensed comps
that `merge()` backfilled onto pipeline-sourced deals.

## Caveats

- Seed data compiled from public reporting as of July 6, 2026; values approximate. Verify against primary sources before using figures anywhere that matters.
- EDGAR only covers US filings; the RSS layer is best-effort. For professional-grade coverage swap in a licensed source (Dealogic, PitchBook, Bloomberg) inside `edgar_poll.py`'s slot.
- Extraction is LLM-based and deliberately gated behind the review flag — approve before trusting.


## News & Trends app (`news.html`)

Second app in the same repo — a live feed of tech/semiconductor news with an IB lens.

```
 Google News RSS (per watchlist co. + topic) ─┐
                                              ├─> cluster dedupe ─> classify.py (Claude)
 Direct feeds (TechCrunch, EE Times, PR wires)┘        │
                    ┌──────────────────────────────────┤
                    v                                  v
        M&A items -> deal pipeline          update_news.py -> news.json + trends.json
```

- `config/watchlist.json` — **edit this** to change tracked companies, topics, and feeds.
- `pipeline/news_feed_poll.py` — polls Google News per watchlist entry + direct feeds; clusters duplicate headlines (Jaccard word overlap with light stemming).
- `pipeline/classify.py` — batches ~15 headlines per Claude call; tags category, IB relevance (M&A / Capital Raise / IPO / Earnings / Regulatory / Product / Management / Partnership), companies, one-line "why a banker cares" summary, and importance 1–3. **Anything tagged M&A is routed into the deal tracker's candidate queue** — the news app feeds the deal app.
- `pipeline/update_news.py` — merges into `data/news.json` (rolling 14 days, 800-item cap) and computes `data/trends.json`: each company's mentions today vs its trailing 14-day average; ≥2× with ≥3 mentions = "SPIKE".
- `.github/workflows/news.yml` — every 30 minutes; shares a concurrency group with the deals workflow so commits never collide.

Frontend: category + IB-tag filters, importance filter, search, day-grouped feed with expandable "why it matters," clustered source links, and a sticky "Heating up" panel with sparklines — click an entity to filter the feed. Auto-refetches every 2 minutes and flashes "+N new."

Seed items in `news.json` are illustrative (unlinked) and roll off within 14 days once the live pipeline runs.

## Feature pack 2

- **`digest.html` + `pipeline/digest.py`** — daily 7:00 am Pacific briefing (DST-proof: dual cron at 14:00/15:00 UTC with a local-hour guard; the off-season trigger self-skips) written by Claude from the last 24h of tracked news/deals/trends ("Three things that matter / Deal flow / Watching"), 7-day archive, quiet-day fallback. Workflow: `digest.yml`.
- **`league.html`** — advisor league tables computed client-side from `advisors` fields on deals (full-credit convention, filterable by M&A/IPO/Follow-on, expandable mandate lists). ~17 deals seeded with publicly reported roles; `extract.py` now captures advisors on new deals. Coverage is partial by nature — directional only.
- **`pipeline/alerts.py`** — Slack/Discord webhook alerts for importance-3 news, new trend SPIKEs, and new deals. Set repo secret `ALERT_WEBHOOK_URL`; state in `data/.alert_state.json` prevents duplicate pings; first run baselines silently.
- **Korean layer (`pipeline/dart_poll.py`)** — DART regulatory disclosures (free key from opendart.fss.or.kr → secret `DART_API_KEY`; auto-downloads the corp-code directory) plus Korean-language Google News for companies/topics in the config's `korea` section. Items flow through the same classify step with English summaries. The KR-news half works with no key at all.
- **`company.html?c=Name`** — one-name dossier: mention trend + sparkline, deal involvement (with advisors), and recent coverage. Company tags in the news feed link here.

New repo secrets (both optional): `ALERT_WEBHOOK_URL`, `DART_API_KEY`.

## Ask the Data (`ask.html`)

Natural-language Q&A over the tracker's own JSON. Bring-your-own-key pattern: the user pastes their Anthropic API key once (optionally remembered in browser localStorage — never committed, never sent anywhere but api.anthropic.com), and questions are answered by a direct browser call to the Messages API using the `anthropic-dangerous-direct-browser-access` CORS header. Context = compact serialization of deals + last 150 news items + trends, with scope checkboxes. The system prompt forces data-only answers with shown working (so sums/rankings are verifiable), flags advisor coverage as partial, and refuses questions the data can't answer. Multi-turn (last 3 exchanges kept). Suggested-question chips included. Cost per question is a fraction of a cent.

## Self-improving layer

The pipeline compounds: human review verdicts feed back into the prompts.

- **Feedback capture** — `review.py approve/reject [reason]` appends every verdict to `data/feedback.jsonl` (the labeled dataset). Reasons on rejects are what teach the loop.
- **Verifier sub-agent** (`verify.py`) — after extraction, an independent Haiku-class call sees ONLY the source + record (not the extractor's reasoning) and checks every material fact is supported. Failures get a `verify_failed` flag and a red "verify ⚠" badge in the deal UI — nothing is silently dropped.
- **Lessons** (`pipeline/LESSONS.md`) — procedural memory injected into the extraction and classification prompts on every run. Capped at 6,000 chars.
- **Distillation loop** (`distill.py` + `distill.yml`) — weekly, mines the week's rejections, proposes sharpened lessons, and **gates them through the eval harness**: a proposal that regresses accuracy on `tests/eval_cases.jsonl` is auto-rejected. Survivors open a **pull request** (never a direct commit) for your approval.
- **Eval harness** (`eval_harness.py`) — scores the current prompt against golden cases by material-field accuracy with value-bucket tolerance. Grow `tests/eval_cases.jsonl` from real feedback over time.
- **Model routing** — Sonnet extracts, Haiku verifies, a stronger model distills weekly. Orchestrator/worker/grader cost pattern.
- The **morning digest** now ends with a one-line system-health stat (approved/rejected this week) so you can watch the approval rate climb.

Design boundary: the loop only ever touches *memory* (`LESSONS.md`) and *flags* — never code, workflows, or the data itself unsupervised. A human approves every lesson change.

## Feature pack 3 (the seven ideas)

All seven ideas from IDEAS-AND-PROMPTS.md, built:
- **Lifecycle tracker** (`lifecycle.py`, Haiku) — tags deal news rumor/talks/announced/closed/terminated; classifier now keeps credible rumors; pills shown in the feed.
- **Comps extractor** (`comps.py`, Sonnet+Haiku maker/checker) — premiums, multiples, consideration, break fees attached to new M&A records; shown in the expanded deal row. Null beats a guess; empty extractions aren't attached.
- **Weekly sector memo** (`memo.py` + `memo.html` + `memo.yml`, Opus-class via `MEMO_MODEL`) — Friday client-style industry update, 8-week archive, seeded example included.
- **Interview prep** (`prep.html`, Sonnet, BYO-key) — pick any tracked deal, get the setup question, a 60-90s model answer from your own data, three follow-ups, and the trap. Reuses the Ask page's saved key.
- **Korean digest** (in `digest.py`) — daily 한국어 edition with financial-media register; EN/한국어 toggle on the digest page. Best-effort: failure never blocks the English digest.
- **Data janitor** (`janitor.py`, **no API** — the five checks are deterministic, so pure Python beats a model call: free and fully testable) — weekly sweep for duplicates, stale pendings/filings, value outliers, missing fields → `data/janitor_report.json`, count surfaced in digest system health.
- **Earnings notes** (`earnings.py`, Sonnet) — IB-style notes when watchlist companies report; shown on company dossier pages.

New env knob: `MEMO_MODEL` (default claude-opus-4-8). New workflow: `memo.yml` (Fridays: memo + janitor). `news.yml` gained lifecycle + earnings steps.

## Five-year edition
Window extended to Jul 2021 – Jul 2026 (104 deals; 48 with reported advisors). Deals page: era-shaded 20-quarter tape, bank filter, advisors in detail rows, terminated deals struck-through and excluded from value totals. `WINDOW_DAYS` is now 5×365 (do not reduce without expecting pruning). Standalone `tech-deal-tracker.html` regenerated from the same source with data embedded. Janitor duplicate rule now requires overlap on both acquirer and target sides (serial sponsors like Thoma Bravo no longer self-match).

## Licensed-source importer (`pipeline/import_deals.py`)

Bring in exports from Dealytics / PitchBook / Dealogic (login-gated platforms — export→import, no polling):

```bash
python pipeline/import_deals.py export.csv --source dealytics --mode enrich --acknowledge-license --dry-run
```

- **enrich mode** fills advisors ONLY on deals you already track (matched via the live `same_deal()` dedupe), never adds rows, never overwrites an existing advisor list, and reports unmatched names.
- **import mode** normalizes rows to the tracker schema (type/status aliases, date formats, $M→$B conversion, advisor dedupe) and runs them through the same merge as the live pipeline with `review=True`, `source`, and `licensed: true` provenance.
- **Licensing guard**: prints the republication warning on every run and requires `--acknowledge-license`. Licensed data on a public Pages site can violate provider terms — keep the repo private or use licensed exports as a finding aid for independently public facts. `licensed: true` tags make imported records auditable/scrubable.
- Column mappings in `config/import_mappings.json` (`dealytics` + `generic`); edit headers to match your actual export. Convert .xlsx to .csv first.
- Tests: `tests/test_importer.py` (parsers, normalization, enrichment semantics, guard behavior verified in dry runs).

### CapIQ / FactSet support (importer v2)
`--source capiq` and `--source factset` mappings added. Multi-column advisors (CapIQ's target-side + buyer-side merge and dedupe), comps fields (premium/EV multiples/price per share → the deal UI's Comps line, fill-never-overwrite), `--mode reconcile` (read-only discrepancy report: value-magnitude and status-lifecycle checks vs tracked data), and a header sanity check that warns loudly when mapped columns are missing — silent column misalignment is the failure mode that matters. Academic licenses: personal use, no automated extraction, no republication.
