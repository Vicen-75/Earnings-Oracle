# --- Vicente: EDGAR fetch and XBRL operating income (code written with help from Claude) ---
import requests
from datetime import date

# The SEC requires a User-Agent with a name and contact email on every request (fair access rule).
HEADERS = {"User-Agent": "Earnings Oracle IS883 vicente@bu.edu"}


def ticker_to_cik(ticker):
    """Translate a ticker (AAPL) into EDGAR's company ID (CIK, 10 digits)."""
    url = "https://www.sec.gov/files/company_tickers.json"
    companies = requests.get(url, headers=HEADERS).json()
    for row in companies.values():
        if row["ticker"] == ticker.upper().strip():
            return str(row["cik_str"]).zfill(10), row["title"]
    return None, None        # failure path: ticker not found


def list_10ks(cik, how_many=3):
    """Return the most recent 10-K filings of a company, newest first.
    An empty list means the company does not file 10-Ks (e.g. foreign filers use 20-F)."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    recent = requests.get(url, headers=HEADERS).json()["filings"]["recent"]
    filings = []
    for form, filed, period, acc, doc in zip(recent["form"], recent["filingDate"],
                                             recent["reportDate"], recent["accessionNumber"],
                                             recent["primaryDocument"]):
        if form == "10-K":
            link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
            filings.append({"fiscal_year_end": period, "filed": filed, "url": link})
    return filings[:how_many]


def annual_operating_income(cik):
    """Return {fiscal_year_end: operating income in USD}, one value per full fiscal year, newest first.
    None means the company does not report this tag (e.g. banks)."""
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/OperatingIncomeLoss.json"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return None
    annual = {}
    for row in response.json()["units"]["USD"]:
        if row.get("form") != "10-K" or "start" not in row:
            continue
        days = (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days
        if 350 <= days <= 380:          # keep full years only, drop quarters
            annual[row["end"]] = row["val"]
    return dict(sorted(annual.items(), reverse=True))


# --- Javier: company card for tool calling (code written with help from Claude) ---

def company_card(ticker):
    """Everything the model needs to decide what to fetch next, in one small dict.
    Returns {"error": ...} on failure so the model can read why (tool calling needs a handled path)."""
    cik, name = ticker_to_cik(ticker)
    if cik is None:
        return {"error": f"ticker '{ticker}' not found on EDGAR"}
    submissions = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=HEADERS).json()
    filings = list_10ks(cik, how_many=3)
    income = annual_operating_income(cik)
    return {
        "ticker": ticker.upper().strip(),
        "name": name,
        "cik": cik,
        "sic_code": submissions.get("sic"),
        "sic_description": submissions.get("sicDescription"),
        "fiscal_year_end_mmdd": submissions.get("fiscalYearEnd"),
        "ten_k_filings": filings,                                   # [] means the company files 20-F or similar
        "has_operating_income_tag": income is not None,             # False for most banks and insurers
        "operating_income_years_available": list(income.keys())[:3] if income else [],
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
