"""Offline tests for the licensed-source importer — run: python tests/test_importer.py"""
import sys, json, csv, io, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
from import_deals import (parse_date, parse_value, parse_advisors,
                          normalize_type, normalize_status, normalize_row, enrich)

# ── field parsers ──
assert parse_date("07/30/2025") == "2025-07-30"
assert parse_date("30 Jul 2025") == "2025-07-30"
assert parse_date("July 30, 2025") == "2025-07-30"
assert parse_date("garbage") is None
assert parse_value("110.4", "millions") == 0.1104          # $M -> $B
assert parse_value("1,234.5", "millions") == 1.2345         # comma handling
assert parse_value("4", "billions") == 4
assert parse_value("Undisclosed", "millions") is None
assert parse_advisors("BofA Securities; UBS; UBS ", ";") == ["BofA Securities", "UBS"]  # dedupe
assert normalize_type("Take-Private") == "M&A" and normalize_type("De-SPAC") == "SPAC"
assert normalize_type("interpretive dance") is None
assert normalize_status("Completed") == "Closed" and normalize_status("Withdrawn") == "Terminated"
assert normalize_status("???") == "Pending"                 # unknown fails safe
print("field parsers OK")

# ── row normalization with the dealytics mapping ──
mapping = json.loads((Path(__file__).parent.parent / "config" / "import_mappings.json").read_text())["dealytics"]
row = {"Deal Type": "IPO", "Announced Date": "07/30/2025", "Company": "Ambiq Micro",
       "Deal Value ($M)": "110.4", "Valuation ($M)": "550", "Deal Status": "Completed",
       "Industry": "Semiconductors", "Financial Advisors": "BofA Securities; UBS Investment Bank",
       "Description": "Edge AI chipmaker IPO"}
rec = normalize_row(row, mapping, "dealytics")
assert rec["type"] == "IPO" and rec["d"] == "2025-07-30" and rec["v"] == 0.1104
assert rec["val"] == 0.55 and rec["advisors"] == ["BofA Securities", "UBS Investment Bank"]
assert rec["review"] is True and rec["licensed"] is True and rec["source"] == "dealytics"

# M&A rows need both parties; broken rows return None instead of garbage
ma = normalize_row({"Deal Type": "Merger", "Announced Date": "01/18/2022",
                    "Acquirer": "Microsoft", "Target": "Activision Blizzard",
                    "Deal Value ($M)": "68,700", "Deal Status": "Completed"}, mapping, "dealytics")
assert ma["name"] == "Microsoft / Activision Blizzard" and ma["v"] == 68.7
assert normalize_row({"Deal Type": "Merger", "Announced Date": "01/18/2022",
                      "Acquirer": "Microsoft", "Target": ""}, mapping, "dealytics") is None
assert normalize_row({"Deal Type": "IPO", "Announced Date": "not a date",
                      "Company": "X"}, mapping, "dealytics") is None
print("row normalization OK")

# ── enrichment mode: fills only empty advisors on matched deals ──
existing = [
 {"d": "2025-07-30", "type": "IPO", "name": "Ambiq Micro", "v": 0.11, "status": "Closed"},           # no advisors -> fill
 {"d": "2025-03-28", "type": "IPO", "name": "CoreWeave", "v": 1.5, "status": "Closed",
  "advisors": ["Morgan Stanley"]},                                                                   # has advisors -> keep
]
imported = [
 {"d": "2025-07-30", "type": "IPO", "name": "Ambiq Micro Inc", "advisors": ["BofA Securities", "UBS"], "source": "dealytics"},
 {"d": "2025-03-27", "type": "IPO", "name": "CoreWeave, Inc.", "advisors": ["Wrong Bank"], "source": "dealytics"},
 {"d": "2024-01-01", "type": "M&A", "name": "Unknown / Deal", "advisors": ["X"], "source": "dealytics"},
]
stats = enrich(existing, imported)
assert existing[0]["advisors"] == ["BofA Securities", "UBS"], "should fill empty advisors via name-variant match"
assert existing[0]["advisor_source"] == "dealytics"
assert existing[1]["advisors"] == ["Morgan Stanley"], "must NEVER overwrite existing advisors"
assert stats["matched"] == 2 and stats["enriched"] == 1 and stats["unmatched"] == ["Unknown / Deal"]
print("enrichment mode OK (fills, never overwrites, reports unmatched)")

print("all importer tests passed")

# ── CapIQ/FactSet upgrades: multi-column advisors, comps, reconcile ──
from import_deals import parse_metric, collect_advisors, build_comps, reconcile
mp = json.loads((Path(__file__).parent.parent / "config" / "import_mappings.json").read_text())

assert parse_metric("32.5%") == 32.5 and parse_metric("8.2x") == 8.2
assert parse_metric("$210.00") == 210.0 and parse_metric("NM") is None

capiq = mp["capiq"]
row = {"Advisors To Target": "Qatalyst Partners, L.P. (Financial Advisor); Goldman Sachs & Co. LLC (Financial Advisor); Fenwick & West LLP (Legal Advisor)",
       "Advisors To Buyers": "Goldman Sachs & Co. LLC (Financial Advisor); J.P. Morgan Securities LLC (Financial Advisor)"}
assert collect_advisors(row, capiq) == ["Qatalyst Partners", "Goldman Sachs", "JPMorgan"], "cross-column merge must dedupe + drop law firms"

crow = {"Target Stock Premium - 1 Day Prior (%)": "31.4", "Implied Enterprise Value/Revenues (x)": "12.3",
        "Implied Enterprise Value/EBITDA (x)": "-", "Sell-Side Termination Fee ($USDmm, Historical rate)": "235",
        "Consideration Offered": "Cash"}
c = build_comps(crow, capiq)
assert c["premium_pct"] == 31.4 and c["ev_revenue"] == 12.3 and c["ev_ebitda"] is None
assert c["termination_fee"] == 0.235 and c["consideration"] == "cash"
assert build_comps({}, capiq) is None, "no numbers -> no comps object"

# full CapIQ M&A row end-to-end with comps + two-sided advisors
full = {"Transaction Types": "Merger/Acquisition", "All Transactions Announced Date": "2022-01-31",
        "Buyers/Investors": "Vista Equity Partners (NasdaqGS:V); Elliott Investment Management L.P.",
        "Target/Issuer": "Citrix Systems, Inc. (NasdaqGS:CTXS)",
        "Total Transaction Value ($USDmm, Historical rate)": "16,500",
        "Transaction Status": "Closed", "Primary Industry [Target/Issuer]": "Software",
        "Advisors To Target": "Qatalyst Partners, L.P. (Financial Advisor)",
        "Advisors To Buyers": "Goldman Sachs & Co. LLC (Financial Advisor)",
        "Target Stock Premium - 1 Day Prior (%)": "30", "Implied Enterprise Value/Revenues (x)": "5.1",
        "Percent Sought (%)": "100", "Transaction Comments": "Take-private."}
rec = normalize_row(full, capiq, "capiq")
assert rec["v"] == 16.5 and rec["name"] == "Vista Equity Partners / Citrix Systems"
assert rec["advisors"] == ["Qatalyst Partners", "Goldman Sachs"]
assert rec["comps"]["premium_pct"] == 30.0 and rec["licensed"] is True

# enrich fills comps but never overwrites existing ones
ex = [{"d": "2022-01-31", "type": "M&A", "name": "Vista & Elliott / Citrix", "v": 16.5, "status": "Closed"}]
stats = enrich(ex, [rec])
assert ex[0].get("comps", {}).get("premium_pct") == 30.0 and stats["enriched"] == 1
stats2 = enrich(ex, [dict(rec, comps={"premium_pct": 99})])
assert ex[0]["comps"]["premium_pct"] == 30.0, "must never overwrite existing comps"

# reconcile flags magnitude and status discrepancies, read-only
tracked = [{"d": "2025-03-18", "type": "M&A", "name": "Google / Wiz", "v": 3.2, "status": "Pending"}]  # unit typo!
imp = [{"d": "2025-03-18", "type": "M&A", "name": "Google / Wiz Inc", "v": 32, "status": "Closed"}]
findings = reconcile(tracked, imp)
fields = sorted(f["field"] for f in findings)
assert fields == ["status", "value"], findings
assert tracked[0]["v"] == 3.2, "reconcile must not modify data"
print("capiq/factset upgrades OK (multi-column, comps, reconcile)")

# ── July 2026 upgrade: uid dedupe, expanded comps, sellers/attitude/resolution ──
from update_deals import same_deal

full2 = dict(full)
full2.update({
    "CIQ Transaction ID": "IQTR123456789",
    "Exchange:Ticker": "NasdaqGS:CTXS",
    "Sellers": "Sequoia Capital Operations, LLC; Insight Venture Management, LLC; Sequoia Capital Operations, LLC",
    "Deal Attitude": "Friendly",
    "Target Stock Premium - 1 Week Prior (%)": "34.1",
    "Target Stock Premium - 1 Month Prior (%)": "41.7",
    "Implied Enterprise Value/EBIT (x)": "22.5",
    "Implied Equity Value/LTM Net Income (x)": "48.2",
    "Implied Equity Value/Book Value (x)": "6.7",
    "Implied Enterprise Value ($USDmm, Historical rate)": "16,900",
    "Target/Issuer LTM Financials - Total Revenue (at Announcement) ($USDmm, Historical rate)": "3,236.7",
    "Target/Issuer LTM Financials - EBITDA (at Announcement) ($USDmm, Historical rate)": "751",
})
rec2 = normalize_row(full2, capiq, "capiq")
assert rec2["uid"] == "IQTR123456789" and rec2["ticker"] == "NasdaqGS:CTXS"
assert rec2["sellers"] == ["Sequoia Capital Operations", "Insight Venture Management"], rec2["sellers"]
assert rec2["attitude"] == "friendly"
assert "resolution" not in rec2, "resolution only stored on Terminated deals"
c2 = rec2["comps"]
assert c2["premium_1w"] == 34.1 and c2["premium_1m"] == 41.7
assert c2["ev_ebit"] == 22.5 and c2["pe"] == 48.2 and c2["pb"] == 6.7
assert c2["implied_ev"] == 16.9 and c2["ltm_revenue"] == 3.2367 and c2["ltm_ebitda"] == 0.751

# resolution captured on broken deals
term = dict(full2, **{"Transaction Status": "Cancelled",
                      "Deal Resolution": "The parties terminated the agreement after regulatory review."})
rect = normalize_row(term, capiq, "capiq")
assert rect["status"] == "Terminated" and rect["resolution"].startswith("The parties terminated")

# uid short-circuits fuzzy matching in both directions
a = {"uid": "IQTR1", "type": "M&A", "name": "Vista / Citrix", "d": "2022-01-31"}
b = {"uid": "IQTR1", "type": "M&A", "name": "Totally Different / Names", "d": "2024-06-01"}
c = {"uid": "IQTR2", "type": "M&A", "name": "Vista / Citrix", "d": "2022-01-31"}
assert same_deal(a, b), "same uid must match even with different names/dates"
assert not same_deal(a, c), "different uids must never match"
nolegacy = {"type": "M&A", "name": "Vista / Citrix", "d": "2022-02-05"}
assert same_deal(a, nolegacy), "uid on one side only -> fall back to fuzzy match"

# merge backfills uid + new comps keys onto a legacy record without review flag
from update_deals import merge
legacy = [{"d": "2022-01-31", "type": "M&A", "name": "Vista / Citrix", "v": 16.5,
           "status": "Closed", "review": False,
           "comps": {"premium_pct": 30.0, "ev_revenue": 5.1, "ev_ebitda": None}}]
merged, mstats = merge(legacy, [rec2])
assert mstats["duplicates"] == 1 and len(merged) == 1
m = merged[0]
assert m["uid"] == "IQTR123456789" and m.get("review") is False, "backfill must not re-flag review"
assert m["comps"]["premium_pct"] == 30.0, "existing comps values never overwritten"
assert m["comps"]["ev_ebit"] == 22.5 and m["comps"]["premium_1m"] == 41.7, "missing comps keys filled"
assert m["sellers"] == rec2["sellers"] and m["ticker"] == "NasdaqGS:CTXS"
print("uid dedupe + expanded comps + qualitative backfill OK")

# ── note summarization: sentence-aware, boilerplate-free, self-healing ──
from import_deals import smart_note, split_sentences
from update_deals import note_chopped

long_note = ("Persistent Systems Limited (NSEI:PERSISTENT) proposed to acquire 79% stake in "
    "Nagarro SE (XTRA:NA9) for approximately €790 million on June 26, 2026. "
    "A cash consideration valued at €81 per share will be paid by Persistent Systems Limited. "
    "Persistent will fund the transaction with committed financing from Barclays. "
    "The Offer forms part of a taking-private strategy. "
    "J.P. Morgan acted as the exclusive financial advisor to Persistent Systems Limited. "
    "Freshfields Bruckhaus Deringer acted as legal counsel to Persistent Systems Limited. "
    "The transaction is subject to customary closing conditions and regulatory approvals. "
    "The board of directors of Nagarro SE unanimously approved the transaction. " * 4)
sn = smart_note(long_note, 600)
assert len(sn) <= 600 and sn.endswith(('.', '!', '?')), "must end on a sentence boundary"
assert "€790 million" in sn and "€81 per share" in sn and "Barclays" in sn, "key facts kept"
assert "acted as" not in sn and "subject to customary" not in sn, "boilerplate dropped"

assert smart_note("Short note.") == "Short note."
assert smart_note("-") == "" and smart_note(None) == ""
one_giant = "A" + " word" * 300 + "."
g = smart_note(one_giant, 120)
assert g.endswith("…") and len(g) <= 121, "unsplittable lead sentence gets word-boundary cut"
sents = split_sentences("Nagarro SE, Inc. was acquired. The deal closed.")
assert sents[0] == "Nagarro SE, Inc. was acquired.", "abbreviations must not split sentences"

# stake becomes a structured field, not a bracket suffix
staked = dict(full2, **{"Percent Sought (%)": "79.0"})
rs = normalize_row(staked, capiq, "capiq")
assert rs["stake_pct"] == 79.0 and "% stake]" not in rs["note"]
rall = normalize_row(dict(full2, **{"Percent Sought (%)": "100.0"}), capiq, "capiq")
assert "stake_pct" not in rall, "100% acquisitions carry no stake field"

# chopped-note detection + uid-keyed repair through merge
assert note_chopped("Following completion of the Offer, [79% stake]")
assert note_chopped("Persistent will fund the transaction with committed")
assert not note_chopped("A clean, complete sentence.")
assert not note_chopped("")
damaged = [{"d": rs["d"], "type": "M&A", "name": rs["name"], "v": rs["v"],
            "status": rs["status"], "review": False, "uid": rs["uid"],
            "note": "Persistent Systems Limited proposed to acquire [79% stake]"}]
healed, hstats = merge(damaged, [rs])
assert hstats["duplicates"] == 1
assert healed[0]["note"] == rs["note"] and not note_chopped(healed[0]["note"])
assert healed[0].get("review") is False, "note repair must not re-flag review"
assert healed[0]["stake_pct"] == 79.0
clean = [dict(damaged[0], note="A complete note the human may have edited.")]
healed2, _ = merge(clean, [rs])
assert healed2[0]["note"] == "A complete note the human may have edited.", "intact notes are never overwritten"
print("smart_note + stake_pct + note repair OK")
