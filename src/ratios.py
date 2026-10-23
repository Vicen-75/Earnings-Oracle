# --- Vicente: real ratio calculator from EDGAR XBRL, issue #31 (code written with help from Claude) ---
# Replaces the canned numbers in src/tools_stub.py. src/agent.py already imports this module when
# EARNINGS_ORACLE_STUBS=0, and calls compute_general_ratios(cik) or compute_financial_sector_ratios(cik).
#
# How it works: one request to the SEC "companyfacts" API returns every XBRL number a company has ever reported.
# From it we keep full fiscal years (10-K, about 365 days) and compute ratios for the two latest years.
#
# Backtest rule (look-ahead): pass last_year_end="2025-06-30" to ignore every year after that date,
# so the model never sees the year it is asked to predict.
#
# Run from the repository root:  python -m src.ratios MSFT PG
import sys
from datetime import date

from src.edgar import _get_json

# Companies report the same idea under different XBRL names. We try them in this order.
REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]
OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]
TOTAL_COSTS_TAGS = ["CostsAndExpenses", "OperatingExpenses"]
ASSETS_TAGS = ["Assets"]
LIABILITIES_TAGS = ["Liabilities"]
EQUITY_TAGS = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
NET_INTEREST_INCOME_TAGS = ["InterestIncomeExpenseNet", "InterestIncomeExpenseAfterProvisionForLoanLoss"]
NONINTEREST_EXPENSE_TAGS = ["NoninterestExpense"]
PROVISION_TAGS = ["ProvisionForLoanLeaseAndOtherLosses", "ProvisionForCreditLosses"]
PREMIUMS_TAGS = ["PremiumsEarnedNet"]

NOT_REPORTED = "not reported"


def _facts(cik):
    """All XBRL facts of one company (one cached request)."""
    data = _get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    return (data or {}).get("facts", {}).get("us-gaap", {})


def _annual(facts, tags, flow=True):
    """{fiscal_year_end: value} for full fiscal years, trying each tag in order.
    flow=True: amounts over a year (revenue, income), kept only if the period is 350 to 380 days.
    flow=False: balances at a date (assets, equity), kept at each 10-K year end."""
    values = {}
    for tag in tags:
        for row in facts.get(tag, {}).get("units", {}).get("USD", []):
            if row.get("form") != "10-K":
                continue
            if flow:
                if "start" not in row:
                    continue
                days = (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days
                if not 350 <= days <= 380:
                    continue
            elif "start" in row:
                continue
            values.setdefault(row["end"], row["val"])      # first tag wins; later tags only fill gaps
    return values


def _ratio(a, b):
    """a / b rounded, or 'not reported' when a number is missing or b is zero."""
    if a is None or b in (None, 0):
        return NOT_REPORTED
    return round(a / b, 4)


def _growth(values, end, previous_end):
    """Change versus the previous fiscal year, e.g. 0.05 = +5%."""
    current, previous = values.get(end), values.get(previous_end)
    if current is None or previous in (None, 0):
        return NOT_REPORTED
    return round((current - previous) / abs(previous), 4)


def _year_ends(series, last_year_end):
    """Fiscal year ends we are allowed to use, newest first."""
    ends = sorted(series, reverse=True)
    if last_year_end:
        ends = [e for e in ends if e <= last_year_end]
    return ends


def _billions(value):
    return NOT_REPORTED if value is None else round(value / 1e9, 3)


def compute_general_ratios(cik, last_year_end=None):
    """Ratios for a non-financial company, for its two latest fiscal years (or the two up to last_year_end)."""
    facts = _facts(cik)
    if not facts:
        return {"error": f"no XBRL financial data on EDGAR for CIK {cik}"}

    revenue = _annual(facts, REVENUE_TAGS)
    op_income = _annual(facts, OPERATING_INCOME_TAGS)
    costs = _annual(facts, TOTAL_COSTS_TAGS)
    assets = _annual(facts, ASSETS_TAGS, flow=False)
    liabilities = _annual(facts, LIABILITIES_TAGS, flow=False)
    equity = _annual(facts, EQUITY_TAGS, flow=False)

    ends = _year_ends(revenue or op_income, last_year_end)
    if len(ends) < 2:
        return {"error": "fewer than two full fiscal years of data before the cutoff"}

    def year(i):
        end = ends[i]
        previous = ends[i + 1] if i + 1 < len(ends) else None
        return {
            "fiscal_year_end": end,
            "revenue_billion_usd": _billions(revenue.get(end)),
            "operating_income_billion_usd": _billions(op_income.get(end)),
            "operating_margin": _ratio(op_income.get(end), revenue.get(end)),
            "revenue_growth": _growth(revenue, end, previous),
            "operating_income_growth": _growth(op_income, end, previous),
            "cost_ratio": _ratio(costs.get(end), revenue.get(end)),
            "asset_turnover": _ratio(revenue.get(end), assets.get(end)),
            "liabilities_to_equity": _ratio(liabilities.get(end), equity.get(end)),
        }

    return {"cik": cik, "ratio_set": "general", "fy_current": year(0), "fy_prior": year(1)}


def compute_financial_sector_ratios(cik, last_year_end=None):
    """Ratios for a bank or insurer, for its two latest fiscal years (or the two up to last_year_end)."""
    facts = _facts(cik)
    if not facts:
        return {"error": f"no XBRL financial data on EDGAR for CIK {cik}"}

    nii = _annual(facts, NET_INTEREST_INCOME_TAGS)
    premiums = _annual(facts, PREMIUMS_TAGS)
    revenue = _annual(facts, REVENUE_TAGS)
    nonint_expense = _annual(facts, NONINTEREST_EXPENSE_TAGS)
    provision = _annual(facts, PROVISION_TAGS)
    assets = _annual(facts, ASSETS_TAGS, flow=False)
    equity = _annual(facts, EQUITY_TAGS, flow=False)

    core = nii or premiums                                   # banks: net interest income; insurers: premiums
    ends = _year_ends(core or revenue, last_year_end)
    if len(ends) < 2:
        return {"error": "fewer than two full fiscal years of data before the cutoff"}

    def year(i):
        end = ends[i]
        previous = ends[i + 1] if i + 1 < len(ends) else None
        return {
            "fiscal_year_end": end,
            "core_income_billion_usd": _billions(core.get(end)),
            "core_income_growth": _growth(core, end, previous),
            "efficiency_ratio": _ratio(nonint_expense.get(end), revenue.get(end)),
            "provision_to_core_income": _ratio(provision.get(end), core.get(end)),
            "equity_to_assets": _ratio(equity.get(end), assets.get(end)),
        }

    return {"cik": cik, "ratio_set": "financial_sector", "fy_current": year(0), "fy_prior": year(1)}


if __name__ == "__main__":
    import json
    from src.edgar import ticker_to_cik
    for ticker in sys.argv[1:] or ["MSFT", "PG"]:
        cik, name = ticker_to_cik(ticker)
        print(f"\n{ticker} ({name})")
        print(json.dumps(compute_general_ratios(cik), indent=2) if cik else "   not found")
