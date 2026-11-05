# --- Javier: MD&A coverage on random tickers (code written with help from Claude) ---
# The preflight only covers our hand-picked candidates. A user can type ANY ticker, so this measures how often
# get_mdna() fails on a random sample of EDGAR companies, reading the newest two 10-Ks exactly as the app does.
# For every failure it records a quick diagnosis so we know which fix would recover the most companies:
#   NO_ITEM7_HEADING  the words "Item 7" barely appear: reorganized 10-K (Honeywell style) -> title-based fallback
#   EXHIBIT_13        MD&A lives in the annual-report exhibit, not the main 10-K document -> read EX-13
#   OTHER             Item 7 is there but our boundaries fail -> look at the filing by hand
# No Gemini calls; EDGAR only. About 10-15 minutes for 50 companies.
#
#   REJECTED          the rules found a section but validate_section() rejected it (Nov 5): is the check too strict?
# Run from the repository root:
#   python -m eval.mdna_coverage            # 50 random companies, seed 883, writes eval/mdna_coverage.csv
#   python -m eval.mdna_coverage 100 7      # 100 companies, seed 7
import csv
import random
import re
import sys
from pathlib import Path

from src.edgar import _get_json, list_10ks
from src.mdna import _get, html_to_text, extract_mdna_from_text, validate_section

OUT = Path("eval/mdna_coverage.csv")
FIELDS = ["ticker", "cik", "name", "fiscal_year_end", "url", "found", "chars", "item7_hits", "mdna_title_hits",
          "mentions_exhibit_13", "diagnosis"]


def diagnose(text):
    item7 = len(re.findall(r"\bitem\s+7\b", text, re.IGNORECASE))
    titles = len(re.findall(r"discussion\s+and\s+analysis\s+of\s+financial\s+condition", text, re.IGNORECASE))
    ex13 = bool(re.search(r"exhibit\s+13|annual\s+report\s+to\s+(share|stock)holders", text, re.IGNORECASE))
    if ex13 and titles <= 3:
        label = "EXHIBIT_13"
    elif item7 <= 2:
        label = "NO_ITEM7_HEADING"
    else:
        label = "OTHER"
    return item7, titles, ex13, label


def sample_companies(n, seed):
    """Random companies that file 10-Ks (one row per CIK; funds and 20-F filers are skipped)."""
    by_cik = {}
    for row in _get_json("https://www.sec.gov/files/company_tickers.json").values():
        by_cik.setdefault(str(row["cik_str"]).zfill(10), (row["ticker"], row["title"]))
    ciks = sorted(by_cik)
    random.Random(seed).shuffle(ciks)
    picked = []
    for cik in ciks:
        if len(picked) >= n:
            break
        try:
            filings = list_10ks(cik, how_many=2)
        except Exception:
            continue
        if filings:
            picked.append((cik, *by_cik[cik], filings))
    return picked


def main(n=50, seed=883):
    rows = []
    for cik, ticker, name, filings in sample_companies(n, seed):
        for f in filings:
            row = {"ticker": ticker, "cik": cik, "name": name, "fiscal_year_end": f["fiscal_year_end"], "url": f["url"]}
            try:
                response = _get(f["url"])
                text = html_to_text(response.text) if response.status_code == 200 else ""
                mdna = extract_mdna_from_text(text) if text else None
                row["found"], row["chars"] = bool(mdna), len(mdna or "")
                if not mdna:
                    row["item7_hits"], row["mdna_title_hits"], row["mentions_exhibit_13"], row["diagnosis"] = diagnose(text)
                    # Nov 5: the parser's output now has to pass validate_section(). Report when the rules found a
                    # section and the check rejected it, so we can tell a real miss from a strict check.
                    raw = extract_mdna_from_text(text, validate=False) if text else None
                    if raw:
                        row["diagnosis"] = f"REJECTED ({len(raw):,} chars): {validate_section(raw)[1]}"
            except Exception as error:
                row["found"], row["diagnosis"] = False, f"error: {type(error).__name__}"
            rows.append(row)
            status = f"ok {row['chars']:,} chars" if row["found"] else f"NOT FOUND ({row.get('diagnosis')})"
            print(f"{ticker:6} {f['fiscal_year_end']}  {status}")

    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    companies = {r["ticker"] for r in rows}
    failed_any = {r["ticker"] for r in rows if not r["found"]}
    failed_all = {t for t in companies if all(not r["found"] for r in rows if r["ticker"] == t)}
    print(f"\nFilings: {sum(r['found'] for r in rows)} of {len(rows)} with MD&A found")
    print(f"Companies: {len(companies) - len(failed_all)} of {len(companies)} get at least one MD&A "
          f"({len(failed_any)} miss at least one filing)")
    labels = {}
    for r in rows:
        if not r["found"]:
            key = r["diagnosis"].split(" (")[0]
            labels[key] = labels.get(key, 0) + 1
    print("Failures by diagnosis:", labels or "none", f"\nResults in {OUT}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else 50, int(args[1]) if len(args) > 1 else 883)
