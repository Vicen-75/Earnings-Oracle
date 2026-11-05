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
import os
import sys
from datetime import date

from src.edgar import _get_json, list_10ks
from src.ratio_directory import RATIOS

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



# --- Javier: compute_ratios, the model picks the ratios (code written with help from Claude) ---
# Workshop feedback: the model must choose what to compute by industry. compute_ratios(cik, ratios=[...]) computes any
# ratio defined in src/ratio_directory.py. compute_general_ratios and compute_financial_sector_ratios above stay as they
# are (the app's ratio table uses them).
GROSS_PROFIT_TAGS = ["GrossProfit"]
COST_OF_REVENUE_TAGS = ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"]
SGA_TAGS = ["SellingGeneralAndAdministrativeExpense"]
SELLING_TAGS = ["SellingAndMarketingExpense"]                 # Nov 5: some companies (ADBE) report the two halves of
ADMIN_TAGS = ["GeneralAndAdministrativeExpense"]              # SG&A separately and never the combined tag
RND_TAGS = ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
            "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost"]   # Nov 5: ADBE uses the last one
DEFERRED_REVENUE_TAGS = ["ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent"]
RPO_TAGS = ["RevenueRemainingPerformanceObligation"]
INVENTORY_TAGS = ["InventoryNet"]
RECEIVABLES_TAGS = ["AccountsReceivableNetCurrent"]
CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment"]
DEPRECIATION_TAGS = ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation"]
OPERATING_CASH_FLOW_TAGS = ["NetCashProvidedByUsedInOperatingActivities"]
INTEREST_EXPENSE_TAGS = ["InterestExpense", "InterestExpenseNonoperating"]
PRETAX_INCOME_TAGS = ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]

MAX_RATIOS_PER_CALL = 10
EXTREME_GROWTH = 0.5          # +/-50%: flag, do not hide
SKIP_NEWEST = int(os.environ.get("EARNINGS_ORACLE_SKIP_NEWEST", "0"))   # same switch as src/mdna.py


def _backtest_cutoff(cik, skip_newest):
    """With skip_newest=1 the newest 10-K is hidden, so ratios stop at the fiscal year of the next one.
    Keeps ratios and MD&A on the same years, so the model never sees the year it predicts."""
    if not skip_newest:
        return None
    filings = list_10ks(cik, how_many=skip_newest + 1)
    return filings[skip_newest]["fiscal_year_end"] if len(filings) > skip_newest else "0000-00-00"


def _margin(a, b):
    return _ratio(a, b)


def _days(a, revenue):
    r = _ratio(a, revenue)
    return r if r == NOT_REPORTED else round(r * 365, 1)


def _minus(a, b):
    if a == NOT_REPORTED or b == NOT_REPORTED:
        return NOT_REPORTED
    return round(a - b, 4)


def _sum_by_year(a, b):
    """{year_end: a + b} for the years both series report (SG&A built from selling + general and administrative)."""
    return {end: a[end] + b[end] for end in a if end in b}


def compute_ratios(cik, ratios, last_year_end=None, skip_newest=SKIP_NEWEST):
    """The agent's tool. Computes the ratios the model asked for, for the two latest fiscal years before any cutoff.
    Returns {"fiscal_years": [...], "values": {ratio: {year_end: value}}, "unknown_ratios": [...]}.
    Every value is a number or "not reported" (the tag is missing), never an invented figure."""
    if isinstance(ratios, str):
        ratios = [r.strip() for r in ratios.split(",")]
    ratios = [r for r in dict.fromkeys(ratios or []) if r]                 # drop duplicates, keep order
    unknown = [r for r in ratios if r not in RATIOS]
    wanted = [r for r in ratios if r in RATIOS][:MAX_RATIOS_PER_CALL]
    if not wanted:
        return {"error": "no valid ratio names given", "unknown_ratios": unknown, "valid_ratio_names": list(RATIOS)}

    facts = _facts(cik)
    if not facts:
        return {"error": f"no XBRL financial data on EDGAR for CIK {cik}"}
    if last_year_end is None:
        last_year_end = _backtest_cutoff(cik, skip_newest)

    f = lambda tags, flow=True: _annual(facts, tags, flow)                  # noqa: E731
    revenue, op_income = f(REVENUE_TAGS), f(OPERATING_INCOME_TAGS)
    core = f(NET_INTEREST_INCOME_TAGS) or f(PREMIUMS_TAGS)
    pretax = f(PRETAX_INCOME_TAGS)
    ends = _year_ends(revenue or op_income or core or pretax, last_year_end)
    if len(ends) < 2:
        return {"error": "fewer than two full fiscal years of data before the cutoff"}
    ends = ends[:3]                                                          # 3 year ends give growth for 2 years

    gross = f(GROSS_PROFIT_TAGS)
    cogs = f(COST_OF_REVENUE_TAGS)
    if not gross and cogs:
        gross = {e: revenue[e] - cogs[e] for e in cogs if e in revenue}
    data = {
        "costs": f(TOTAL_COSTS_TAGS), "sga": f(SGA_TAGS) or _sum_by_year(f(SELLING_TAGS), f(ADMIN_TAGS)),
        "rnd": f(RND_TAGS), "capex": f(CAPEX_TAGS),
        "dna": f(DEPRECIATION_TAGS), "ocf": f(OPERATING_CASH_FLOW_TAGS), "interest": f(INTEREST_EXPENSE_TAGS),
        "nonint": f(NONINTEREST_EXPENSE_TAGS), "provision": f(PROVISION_TAGS),
        "deferred": f(DEFERRED_REVENUE_TAGS, False), "rpo": f(RPO_TAGS, False),
        "inventory": f(INVENTORY_TAGS, False), "receivables": f(RECEIVABLES_TAGS, False),
        "assets": f(ASSETS_TAGS, False), "liabilities": f(LIABILITIES_TAGS, False), "equity": f(EQUITY_TAGS, False),
    }

    def one(name, end, prev):
        d = {k: v.get(end) for k, v in data.items()}
        rev, oi = revenue.get(end), op_income.get(end)
        if name == "revenue_growth":                 return _growth(revenue, end, prev)
        if name == "operating_income_growth":        return _growth(op_income, end, prev)
        if name == "pretax_income_growth":           return _growth(pretax, end, prev)
        if name == "pretax_margin":                  return _margin(pretax.get(end), rev)
        if name == "deferred_revenue_growth":        return _growth(data["deferred"], end, prev)
        if name == "rpo_growth":                     return _growth(data["rpo"], end, prev)
        if name == "gross_margin":                   return _margin(gross.get(end), rev)
        if name == "operating_margin":               return _margin(oi, rev)
        if name == "sga_to_revenue":                 return _margin(d["sga"], rev)
        if name == "rnd_to_revenue":                 return _margin(d["rnd"], rev)
        if name == "cost_ratio":                     return _margin(d["costs"], rev)
        if name == "inventory_turnover":             return _ratio(cogs.get(end), d["inventory"])
        if name == "inventory_growth_minus_revenue_growth":
            return _minus(_growth(data["inventory"], end, prev), _growth(revenue, end, prev))
        if name == "receivables_days":               return _days(d["receivables"], rev)
        if name == "asset_turnover":                 return _ratio(rev, d["assets"])
        if name == "capex_to_revenue":               return _margin(d["capex"], rev)
        if name == "depreciation_to_revenue":        return _margin(d["dna"], rev)
        if name == "cash_conversion":                return _ratio(d["ocf"], oi)
        if name == "liabilities_to_equity":          return _ratio(d["liabilities"], d["equity"])
        if name == "interest_coverage":              return _ratio(oi, d["interest"])
        if name == "core_income_growth":             return _growth(core, end, prev)
        if name == "efficiency_ratio":               return _margin(d["nonint"], rev)
        if name == "provision_to_core_income":       return _margin(d["provision"], core.get(end))
        if name == "equity_to_assets":               return _margin(d["equity"], d["assets"])
        return NOT_REPORTED

    years = ends[:2]
    values = {}
    for name in wanted:
        values[name] = {end: one(name, end, ends[i + 1] if i + 1 < len(ends) else None) for i, end in enumerate(years)}
    result = {"cik": cik, "fiscal_years": years, "values": values,
              "kinds": {name: RATIOS[name]["kind"] for name in wanted}}
    # Sanity flag: a growth figure beyond +/-50% is usually a one-off (acquisition, big contract, a tag that changed
    # scope), not a trend. The number stays as reported; the model is told to check it before leaning on it.
    extreme = [f"{name} {end}: {v:+.0%}" for name in wanted if RATIOS[name]["kind"] == "growth"
               for end, v in values[name].items() if isinstance(v, (int, float)) and abs(v) > EXTREME_GROWTH]
    if extreme:
        result["check_before_relying"] = ("unusually large changes, likely one-off or a change in what the tag covers; "
                                          "confirm in the MD&A: " + "; ".join(extreme))
    if unknown:
        result["unknown_ratios"] = unknown
    if len(ratios) - len(unknown) > MAX_RATIOS_PER_CALL:
        result["note"] = f"only the first {MAX_RATIOS_PER_CALL} ratios were computed"
    return result

if __name__ == "__main__":
    import json
    from src.edgar import ticker_to_cik
    for ticker in sys.argv[1:] or ["MSFT", "PG"]:
        cik, name = ticker_to_cik(ticker)
        print(f"\n{ticker} ({name})")
        print(json.dumps(compute_general_ratios(cik), indent=2) if cik else "   not found")
