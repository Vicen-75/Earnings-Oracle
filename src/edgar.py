# --- Vicente: EDGAR fetch and XBRL operating income (code written with help from Claude) ---
import os
import time
from datetime import date
from functools import lru_cache

import requests

# The SEC requires a User-Agent with a name and contact email on every request (fair access rule).
HEADERS = {"User-Agent": "Earnings Oracle IS883 vicente@bu.edu"}

# --- Vicente: speed limit and cache for every SEC request (code written with help from Claude) ---
SECONDS_BETWEEN_REQUESTS = 0.125      # at most 8 requests per second; the SEC allows 10
_last_request_time = [0.0]


def _get(url):
    """Every request to the SEC goes through here, so we never go over the SEC speed limit."""
    wait = SECONDS_BETWEEN_REQUESTS - (time.time() - _last_request_time[0])
    if wait > 0:
        time.sleep(wait)
    _last_request_time[0] = time.time()
    return requests.get(url, headers=HEADERS, timeout=30)


@lru_cache(maxsize=256)
def _get_json(url):
    """Same as _get, but remembers each answer: the same URL is downloaded only once per session.
    Returns None if the SEC answers with an error (e.g. 404 when a company does not report a tag)."""
    response = _get(url)
    if response.status_code != 200:
        return None
    return response.json()


def ticker_to_cik(ticker):
    """Translate a ticker (AAPL) into EDGAR's company ID (CIK, 10 digits)."""
    url = "https://www.sec.gov/files/company_tickers.json"
    companies = _get_json(url)
    for row in companies.values():
        if row["ticker"] == ticker.upper().strip():
            return str(row["cik_str"]).zfill(10), row["title"]
    return None, None        # failure path: ticker not found


def _ten_ks_in(block, cik):
    """10-K filings listed in one block of the submissions API (same column layout in 'recent' and older pages)."""
    found = []
    for form, filed, period, acc, doc in zip(block["form"], block["filingDate"], block["reportDate"],
                                             block["accessionNumber"], block["primaryDocument"]):
        if form == "10-K":
            link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
            found.append({"fiscal_year_end": period, "filed": filed, "url": link})
    return found


def list_10ks(cik, how_many=3):
    """Return the most recent 10-K filings of a company, newest first.
    An empty list means the company does not file 10-Ks (e.g. foreign filers use 20-F)."""
    data = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    filings = _ten_ks_in(data["filings"]["recent"], cik)
    # --- Javier: older pages (code written with help from Claude) ---
    # 'recent' holds only the last 1,000 filings. Big issuers (JPM files thousands of prospectuses a year) push
    # their older 10-Ks off that list, into extra pages listed under filings.files. Read those until we have enough.
    for page in data["filings"].get("files", []):
        if len(filings) >= how_many:
            break
        older = _get_json(f"https://data.sec.gov/submissions/{page['name']}")
        if older:
            filings += _ten_ks_in(older, cik)
    return filings[:how_many]


def _annual_concept(cik, tag):
    """{fiscal_year_end: USD value} for full fiscal years of one XBRL tag, newest first. None if not reported."""
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
    data = _get_json(url)
    if data is None:
        return None
    annual = {}
    for row in data.get("units", {}).get("USD", []):
        if row.get("form") != "10-K" or "start" not in row:
            continue
        days = (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days
        if 350 <= days <= 380:          # keep full years only, drop quarters
            annual[row["end"]] = row["val"]
    return dict(sorted(annual.items(), reverse=True))


def annual_operating_income(cik):
    """Return {fiscal_year_end: operating income in USD}, one value per full fiscal year, newest first.
    None means the company does not report this tag (e.g. banks)."""
    return _annual_concept(cik, "OperatingIncomeLoss")


# --- Javier: substitute target for companies without an operating income line (code written with help from Claude) ---
# Banks, insurers and some others (KO, XOM, PFE, NKE in our candidates) do not tag OperatingIncomeLoss. Team decision
# (Nov 4, 2026): for them the target is pre-tax income from continuing operations, the closest line they all report.
PRETAX_INCOME_TAGS = [
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
]
TARGETS = {"operating_income": "operating income", "pretax_income": "pre-tax income"}


def annual_pretax_income(cik):
    """{fiscal_year_end: pre-tax income in USD}, newest first, from the first tag that has values. None if neither."""
    for tag in PRETAX_INCOME_TAGS:
        values = _annual_concept(cik, tag)
        if values:
            return values
    return None


def _covers(series, year_end):
    """True if the series has a value for this fiscal year end (within 10 days, XBRL and filing dates can differ)."""
    if not series or not year_end:
        return False
    target = date.fromisoformat(year_end)
    return any(abs((date.fromisoformat(end) - target).days) <= 10 for end in series)


def choose_target(cik, latest_year_end):
    """Which number we predict for this company: 'operating_income' if it reports it for its latest fiscal year,
    otherwise 'pretax_income', otherwise None (nothing to predict). Returns (target, series)."""
    income = annual_operating_income(cik)
    if _covers(income, latest_year_end):
        return "operating_income", income
    pretax = annual_pretax_income(cik)
    if _covers(pretax, latest_year_end):
        return "pretax_income", pretax
    return None, {}


# --- Javier: company card for tool calling (code written with help from Claude) ---

def company_card(ticker):
    """Everything the model needs to decide what to fetch next, in one small dict.
    Returns {"error": ...} on failure so the model can read why (tool calling needs a handled path)."""
    cik, name = ticker_to_cik(ticker)
    if cik is None:
        return {"error": f"ticker '{ticker}' not found on EDGAR"}
    submissions = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    skip = int(os.environ.get("EARNINGS_ORACLE_SKIP_NEWEST", "0"))   # backtest: hide the year being predicted
    filings = list_10ks(cik, how_many=3 + skip)[skip:]
    latest = filings[0]["fiscal_year_end"] if filings else None
    target, series = choose_target(cik, latest) if filings else (None, {})
    years = [end for end in series if not latest or end <= latest][:3]
    return {
        "ticker": ticker.upper().strip(),
        "name": name,
        "cik": cik,
        "sic_code": submissions.get("sic"),
        "sic_description": submissions.get("sicDescription"),
        "fiscal_year_end_mmdd": submissions.get("fiscalYearEnd"),
        "ten_k_filings": filings,                                   # [] means the company files 20-F or similar
        "has_operating_income_tag": target == "operating_income",   # False for most banks and insurers
        "target": TARGETS.get(target, "none: no operating income or pre-tax income reported"),
        "target_years_available": years,
    }


def fiscal_year_end_in(cik, calendar_year):
    """Return the fiscal-year-end date (YYYY-MM-DD) whose calendar year matches, e.g. 2025 -> '2025-09-27' for AAPL.
    None if the company does not report OperatingIncomeLoss or has no full year ending in that calendar year."""
    income = annual_operating_income(cik)
    if not income:
        return None
    for end in income:                                               # newest first
        if end.startswith(str(calendar_year)):
            return end
    return None
