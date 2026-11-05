# --- Javier: preflight for the test set (code written with help from Claude) ---
# A company only counts toward the 20 if the whole pipeline can run on it. The contamination test checks the model;
# this checks the data. For every usable company in eval/contamination_results.csv it runs:
#   1. RATIOS  compute_general_ratios(cik, last_year_end=prior_end): the two years the model will see (FY2024 and
#              FY2023) must both have revenue and operating income, and the newest year must be exactly prior_end.
#   2. MD&A    the two 10-Ks the model will read, chosen BY DATE (fiscal year end <= prior_end), must both yield an
#              MD&A section with Nicolas's extractor.
#   3. LEAK    EARNINGS_ORACLE_SKIP_NEWEST=1 skips the newest 10-K BY COUNT. If the company has already filed a 10-K
#              after the target year (fiscal years ending mid-year), skipping one is not enough and the model would
#              read the answer year. Flagged so the backtest uses the accession numbers in eval/test_set.csv instead.
# No Gemini calls; only EDGAR. Expect a few minutes (each 10-K is downloaded once).
#
# Run from the repository root:
#   python -m eval.preflight                 # every OK / OK_BUT_UNKNOWN_COMPANY company, writes eval/preflight_results.csv
#   python -m eval.preflight HD CAT          # just these tickers (still read from contamination_results.csv), no CSV written
import csv
import sys
from pathlib import Path

from src.edgar import ticker_to_cik, list_10ks
from src.mdna import extract_mdna_from_url
from src.ratios import compute_general_ratios, NOT_REPORTED

CONTAMINATION_PATH = Path("eval/contamination_results.csv")
RESULTS_PATH = Path("eval/preflight_results.csv")
FIELDS = ["ticker", "name", "target_end", "prior_end", "truth", "contamination", "ratios_ok", "ratios_issue",
          "mdna_years_found", "mdna_chars", "mdna_filings", "skip_newest_safe", "ready", "notes"]


def check_ratios(cik, prior_end):
    """(ok, issue). The model sees fy_current = prior_end and fy_prior = the year before."""
    r = compute_general_ratios(cik, last_year_end=prior_end)
    if "error" in r:
        return False, r["error"]
    if r["fy_current"]["fiscal_year_end"] != prior_end:
        return False, f"newest year is {r['fy_current']['fiscal_year_end']}, expected {prior_end}"
    missing = [f"{label}.{key}" for label in ("fy_current", "fy_prior")
               for key in ("revenue_billion_usd", "operating_income_billion_usd")
               if r[label][key] == NOT_REPORTED]
    if missing:
        return False, "not reported: " + ", ".join(missing)
    return True, ""


def check_mdna(cik, prior_end):
    """The two most recent 10-Ks with fiscal year end <= prior_end, and whether the MD&A was found in each."""
    filings = [f for f in list_10ks(cik, how_many=8) if f["fiscal_year_end"] and f["fiscal_year_end"] <= prior_end][:2]
    found = []
    for f in filings:
        text = extract_mdna_from_url(f["url"])
        found.append((f, len(text) if text else 0))
    return found


def check_skip_newest(cik, target_end, chosen_ends):
    """True if skipping the newest 10-K by count lands on the same filings we chose by date."""
    by_count = [f["fiscal_year_end"] for f in list_10ks(cik, how_many=3)][1:3]
    return by_count == chosen_ends and (list_10ks(cik, how_many=1) or [{}])[0].get("fiscal_year_end") == target_end


def preflight(row):
    out = {k: row.get(k, "") for k in ("ticker", "name", "target_end", "prior_end", "truth")}
    out["contamination"] = row["verdict"]
    cik, _ = ticker_to_cik(row["ticker"])
    if cik is None:
        return {**out, "ready": False, "notes": "ticker not found"}

    out["ratios_ok"], out["ratios_issue"] = check_ratios(cik, row["prior_end"])

    found = check_mdna(cik, row["prior_end"])
    out["mdna_filings"] = " | ".join(f["fiscal_year_end"] for f, _ in found)
    out["mdna_chars"] = " | ".join(str(n) for _, n in found)
    out["mdna_years_found"] = sum(1 for _, n in found if n)

    chosen_ends = [f["fiscal_year_end"] for f, _ in found]
    out["skip_newest_safe"] = check_skip_newest(cik, row["target_end"], chosen_ends)

    notes = []
    if len(found) < 2:
        notes.append(f"only {len(found)} 10-K(s) on or before {row['prior_end']}")
    if out["mdna_years_found"] < 2:
        notes.append("MD&A not found in " + str(len(found) - out["mdna_years_found"]) + " filing(s)")
    if not out["skip_newest_safe"]:
        notes.append("SKIP_NEWEST=1 would not pick these filings; use accession numbers")
    out["ready"] = bool(out["ratios_ok"]) and out["mdna_years_found"] == 2
    out["notes"] = "; ".join(notes)
    return out


def show(r):
    mark = "READY" if r["ready"] else "NOT READY"
    print(f"\n{r['ticker']} ({r.get('name')})  -> {mark}")
    print(f"   ratios up to {r['prior_end']}: {'ok' if r.get('ratios_ok') else 'FAIL ' + str(r.get('ratios_issue'))}")
    print(f"   MD&A found in {r.get('mdna_years_found')} of 2 filings [{r.get('mdna_filings')}] chars [{r.get('mdna_chars')}]")
    print(f"   skip_newest safe: {r.get('skip_newest_safe')}")
    if r.get("notes"):
        print(f"   notes: {r['notes']}")


def main(tickers=None):
    with open(CONTAMINATION_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    if tickers:
        wanted = {t.upper() for t in tickers}
        rows = [r for r in rows if r["ticker"] in wanted]
    else:
        rows = [r for r in rows if r["verdict"].startswith("OK")]

    results = []
    for row in rows:
        if not row.get("prior_end"):
            print(f"\n{row['ticker']}: no target year in contamination results, skipped")
            continue
        try:
            r = preflight(row)
        except Exception as error:                      # network hiccup, odd filing: record it and keep going
            r = {"ticker": row["ticker"], "name": row.get("name"), "prior_end": row["prior_end"],
                 "contamination": row["verdict"], "ready": False, "notes": f"error: {type(error).__name__}: {error}"}
        show(r)
        results.append(r)

    if not tickers:
        with open(RESULTS_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
    ready = [r for r in results if r["ready"]]
    print(f"\n{len(ready)} of {len(results)} companies ready for the test set"
          + ("" if tickers else f". Results in {RESULTS_PATH}"))
    if ready:
        inc = sum(r.get("truth") == "increase" for r in ready)
        print(f"Among the ready ones: {inc} increase, {len(ready) - inc} decrease")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
