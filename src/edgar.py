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
