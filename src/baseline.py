# --- Javier: the two baselines the model must beat (code written with help from Claude) ---
# docs/success_metric.md: the app is doing its job if its accuracy beats both of these on the same companies.
#   momentum:        "increase" if the target metric grew in the last year the model was allowed to see, else "decrease".
#                    A fixed, transparent rule on the numbers alone, with no model call.
#   always_increase: the naive rule.
# Same target as the agent: operating income, or pre-tax income when a company reports no operating income line
# (edgar.choose_target), and the same strict rule as the truth: "increase" means strictly greater.
#
# Run from the repository root:   python -m src.baseline CAT 2024-12-31
import sys
from datetime import date

from src.edgar import choose_target, ticker_to_cik


def momentum(cik, last_year_end):
    """Direction of the target metric from the year before last_year_end to last_year_end.
    Returns {"direction", "target", "previous", "latest"} or {"direction": None, "reason": ...}."""
    target, series = choose_target(cik, last_year_end)
    if not target:
        return {"direction": None, "reason": "no operating income or pre-tax income reported"}
    cutoff = date.fromisoformat(last_year_end)
    years = sorted((end for end in series if (date.fromisoformat(end) - cutoff).days <= 10), reverse=True)
    if len(years) < 2:
        return {"direction": None, "reason": "fewer than two years of the target metric"}
    latest, previous = series[years[0]], series[years[1]]
    return {"direction": "increase" if latest > previous else "decrease", "target": target,
            "previous": previous, "latest": latest, "years": years[:2]}


def always_increase():
    return {"direction": "increase"}


if __name__ == "__main__":
    ticker, last = (sys.argv[1].upper(), sys.argv[2]) if len(sys.argv) > 2 else ("CAT", "2024-12-31")
    cik, name = ticker_to_cik(ticker)
    print(ticker, name, momentum(cik, last))
