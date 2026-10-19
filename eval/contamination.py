# --- Vicente: contamination test with a control year (code written with help from Claude) ---
# Checks whether the model already remembers the result we want it to predict.
# Run from the repository root:  python -m eval.contamination
from typing import Literal, Optional
from pydantic import BaseModel, Field

from src.edgar import ticker_to_cik, annual_operating_income
from src.llm import ask_gemini


class MemoryCheck(BaseModel):
    knows_result: bool = Field(description="True only if you have reliable knowledge of this specific fiscal year's reported results")
    direction: Literal["increase", "decrease", "unknown"] = Field(description="Change in operating income versus the previous fiscal year")
    operating_income_billion_usd: Optional[float] = Field(None, description="Reported operating income for that fiscal year in billions of USD, or null if unknown")


def contamination_check(name, fiscal_year_end):
    """Ask the model, from memory only, what happened in a given fiscal year."""
    prompt = (f"From memory only, what operating income did {name} report for the fiscal year "
              f"ending {fiscal_year_end}, and did it increase or decrease versus the previous fiscal year? "
              f"If you do not have reliable knowledge of that specific year, say so. Do not guess.")
    raw = ask_gemini(prompt, response_schema=MemoryCheck, temperature=0)
    return MemoryCheck.model_validate_json(raw)


def check_company(ticker, target_end, control_end):
    """Target = the year we want to predict. Control = an earlier year the model should know."""
    cik, name = ticker_to_cik(ticker)
    income = annual_operating_income(cik)
    ends = list(income.keys())                               # newest first
    prior_end = ends[ends.index(target_end) + 1]
    truth = "increase" if income[target_end] > income[prior_end] else "decrease"

    target = contamination_check(name, target_end)
    control = contamination_check(name, control_end)
    contaminated = target.knows_result and target.direction == truth

    print(f"\n{ticker}")
    print(f"   target  {target_end}: truth={truth}, ${income[target_end] / 1e9:,.1f} B | "
          f"model={target.direction}, {target.operating_income_billion_usd} B, knows={target.knows_result}")
    print(f"   control {control_end}: truth=${income[control_end] / 1e9:,.1f} B | "
          f"model={control.operating_income_billion_usd} B, knows={control.knows_result}")
    print(f"   -> {'CONTAMINATED: drop or anonymize' if contaminated else 'ok to use'}")


if __name__ == "__main__":
    check_company("AAPL", target_end="2025-09-27", control_end="2024-09-28")
    check_company("MSFT", target_end="2025-06-30", control_end="2024-06-30")
