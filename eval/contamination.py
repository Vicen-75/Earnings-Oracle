# --- Vicente + Javier: contamination test, v2 with quarter probe (code written with help from Claude) ---
# Checks whether the model already remembers the result we want it to predict.
#
# Why two probes. The first runs (Oct 19, 2026) showed the model knows FY2024 results for AAPL and MSFT
# but answers "unknown" for the FY2025 full year. That means its cutoff sits INSIDE the FY2025 window,
# so it may hold Q1-Q3 FY2025 without knowing the full year. Three quarters already give away the direction,
# which is exactly the leak the proposal feedback described. So we ask about the full year AND the quarters.
#
# Run from the repository root:
#   python -m eval.contamination                      # uses eval/candidates.csv, writes eval/contamination_results.csv
#   python -m eval.contamination AAPL MSFT JPM        # quick check on a few tickers, no CSV written
#
# candidates.csv columns: ticker, target_calendar_year (default 2025), target_end (optional, YYYY-MM-DD; overrides the year)
import csv
import sys
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from src.edgar import ticker_to_cik, annual_operating_income, fiscal_year_end_in
from src.llm import ask_gemini

RESULTS_PATH = Path("eval/contamination_results.csv")
CANDIDATES_PATH = Path("eval/candidates.csv")


class MemoryCheck(BaseModel):
    knows_result: bool = Field(description="True only if you have reliable knowledge of this specific fiscal year's reported results")
    direction: Literal["increase", "decrease", "unknown"] = Field(description="Change in operating income versus the previous fiscal year")
    operating_income_billion_usd: Optional[float] = Field(None, description="Reported operating income for that fiscal year in billions of USD, or null if unknown")


class QuarterMemory(BaseModel):
    quarter_label: str = Field(description="The quarter as the company labels it, e.g. 'Q3 FY2025' or 'quarter ended June 30, 2025'")
    period_end: Optional[str] = Field(None, description="Quarter end date, YYYY-MM-DD, or null if unknown")
    operating_income_billion_usd: Optional[float] = Field(None, description="Operating income for that quarter in billions of USD, or null")


class QuarterCheck(BaseModel):
    knows_any_quarter: bool = Field(description="True only if you have reliable knowledge of at least one quarterly result inside the stated fiscal year")
    quarters_known: List[QuarterMemory] = Field(default_factory=list, description="Each quarter of the stated fiscal year you reliably remember; empty if none")
    latest_period_you_know: Optional[str] = Field(None, description="The most recent quarter end date (YYYY-MM-DD) for this company whose results you reliably remember, from any year, or null")


def full_year_probe(name, fiscal_year_end):
    """Ask the model, from memory only, what happened in the full fiscal year."""
    prompt = (f"From memory only, what operating income did {name} report for the fiscal year "
              f"ending {fiscal_year_end}, and did it increase or decrease versus the previous fiscal year? "
              f"If you do not have reliable knowledge of that specific year, say so. Do not guess.")
    raw = ask_gemini(prompt, response_schema=MemoryCheck, temperature=0)
    return MemoryCheck.model_validate_json(raw)


def quarter_probe(name, fiscal_year_end, prior_year_end):
    """Ask the model, from memory only, which QUARTERS of the target fiscal year it already knows."""
    prompt = (f"From memory only. {name} has a fiscal year that started the day after {prior_year_end} and ended {fiscal_year_end}. "
              f"List every quarterly earnings result inside that fiscal year that you reliably remember "
              f"(quarter label, quarter end date, operating income). Also state the most recent quarter end date, from any year, "
              f"for which you reliably remember this company's results. If you remember nothing inside that fiscal year, say so. Do not guess.")
    raw = ask_gemini(prompt, response_schema=QuarterCheck, temperature=0)
    return QuarterCheck.model_validate_json(raw)


def check_company(ticker, target_end=None, target_calendar_year=2025, verbose=True):
    """Target = the fiscal year we want to predict. Control = the year before, which the model should know.
    Returns one result row (dict) or None if the company cannot be evaluated."""
    cik, name = ticker_to_cik(ticker)
    if cik is None:
        if verbose:
            print(f"\n{ticker}: not found on EDGAR")
        return {"ticker": ticker, "name": None, "verdict": "NOT_FOUND"}

    income = annual_operating_income(cik)
    if not income:
        if verbose:
            print(f"\n{ticker} ({name}): no OperatingIncomeLoss tag (bank/insurer?) -> needs the substitute tag before it can be tested")
        return {"ticker": ticker, "name": name, "verdict": "NO_OPERATING_INCOME_TAG"}

    target_end = target_end or fiscal_year_end_in(cik, target_calendar_year)
    ends = list(income.keys())                                     # newest first
    if target_end not in ends or ends.index(target_end) + 1 >= len(ends):
        if verbose:
            print(f"\n{ticker} ({name}): no full fiscal year ending in {target_calendar_year} with a prior year on file")
        return {"ticker": ticker, "name": name, "verdict": "NO_TARGET_YEAR"}
    prior_end = ends[ends.index(target_end) + 1]
    truth = "increase" if income[target_end] > income[prior_end] else "decrease"

    year = full_year_probe(name, target_end)
    quarters = quarter_probe(name, target_end, prior_end)
    control = full_year_probe(name, prior_end)

    full_year_leak = year.knows_result and year.direction == truth
    quarter_leak = quarters.knows_any_quarter or (
        quarters.latest_period_you_know is not None and prior_end < quarters.latest_period_you_know <= target_end)
    if full_year_leak:
        verdict = "CONTAMINATED_FULL_YEAR"
    elif quarter_leak:
        verdict = "CONTAMINATED_QUARTERS"
    elif not control.knows_result:
        verdict = "OK_BUT_UNKNOWN_COMPANY"     # model has not heard of it even for the control year; fine to use, but note it
    else:
        verdict = "OK"

    row = {
        "ticker": ticker, "name": name, "target_end": target_end, "prior_end": prior_end,
        "truth": truth, "truth_billion_usd": round(income[target_end] / 1e9, 2),
        "fy_model_direction": year.direction, "fy_model_value": year.operating_income_billion_usd, "fy_knows": year.knows_result,
        "quarters_known": len(quarters.quarters_known), "latest_period_known": quarters.latest_period_you_know,
        "control_knows": control.knows_result, "control_model_value": control.operating_income_billion_usd,
        "control_truth_billion_usd": round(income[prior_end] / 1e9, 2),
        "verdict": verdict,
    }
    if verbose:
        print(f"\n{ticker} ({name})")
        print(f"   target  FY ending {target_end}: truth={truth}, ${row['truth_billion_usd']} B | "
              f"model={year.direction}, {year.operating_income_billion_usd} B, knows={year.knows_result}")
        print(f"   quarters of target FY known: {len(quarters.quarters_known)} | latest period known: {quarters.latest_period_you_know}")
        print(f"   control FY ending {prior_end}: truth=${row['control_truth_billion_usd']} B | "
              f"model={control.operating_income_billion_usd} B, knows={control.knows_result}")
        print(f"   -> {verdict}")
    return row


def run_candidates(path=CANDIDATES_PATH, out=RESULTS_PATH):
    rows = []
    with open(path, newline="") as f:
        for cand in csv.DictReader(f):
            year = int(cand.get("target_calendar_year") or 2025)
            target_end = (cand.get("target_end") or "").strip() or None
            rows.append(check_company(cand["ticker"].strip(), target_end=target_end, target_calendar_year=year))
    fields = ["ticker", "name", "target_end", "prior_end", "truth", "truth_billion_usd", "fy_model_direction", "fy_model_value",
              "fy_knows", "quarters_known", "latest_period_known", "control_knows", "control_model_value",
              "control_truth_billion_usd", "verdict"]
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(r for r in rows if r)
    ok = sum(1 for r in rows if r and r["verdict"].startswith("OK"))
    print(f"\n{ok} of {len(rows)} candidates usable. Results written to {out}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for t in sys.argv[1:]:
            check_company(t)
    else:
        run_candidates()
