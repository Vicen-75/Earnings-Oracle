# --- Javier: the 20-company backtest behind the app's Tests tab (code written with help from Claude) ---
# The test set lives in eval/test_set.csv (ticker, name, industry, prior_end, target_end, truth, contamination).
# Chosen Nov 5, before any test was run: contamination-clean companies from eval/preflight_results.csv, spread across
# industries, 11 increases and 9 decreases. Replacing the CSV changes the test set without touching code.
#
# One test = the agent in backtest mode (skip_newest=1: the newest 10-K, the year being predicted, is hidden from
# every tool), compared with the truth and with the two baselines in src/baseline.py.
import csv
import re
import time
from pathlib import Path

from src.baseline import always_increase, momentum, reverse_momentum
from src.edgar import ticker_to_cik

TEST_SET_PATH = Path("eval/test_set.csv")
SKIP_NEWEST = 1


def load_test_set(path=TEST_SET_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def baselines(row):
    """Both baselines for one test row, computed only from the years the model is allowed to see."""
    cik, _ = ticker_to_cik(row["ticker"])
    m = momentum(cik, row["prior_end"]) if cik else {"direction": None, "reason": "ticker not found"}
    return {"momentum": m, "reverse_momentum": reverse_momentum(m), "always_increase": always_increase()}


def is_correct(direction, truth):
    """A missing direction ("no data found", a parse failure) counts as wrong (docs/success_metric.md)."""
    return direction is not None and direction == truth


def parse_answer(answer):
    """Direction and probability from the model's text. Returns (direction, probability); either can be None.
    Same rules as the app's headline (app.parse_headline), here so command-line runs need no Streamlit."""
    text = answer or ""
    direction = re.search(r"\*\*(increase|decrease)\*\*", text, re.I) \
        or re.search(r"direction\W+(increase|decrease)", text, re.I) \
        or re.search(r"(?:will|to)\s+(?:\*\*)?(increase|decrease)\b", text, re.I)
    probability = re.search(r"probability\W*(?:of\W*)?(0?\.\d+|1(?:\.0+)?)\b", text, re.I)
    return (direction.group(1).lower() if direction else None,
            float(probability.group(1)) if probability else None)


def run_test(row, investigate, parse=parse_answer, on_event=None, log_path=None, prompt=None, anonymize=False):
    """Run the agent on one test company in backtest mode. parse(answer) -> (direction, probability).
    The row's skip_newest column (eval/test_set_200.csv) says how many 10-Ks to hide: 1 when the target year is the
    newest filing, 2 when the company has already filed the following year too (fiscal years ending mid-year).
    anonymize=True hides the company's name, ticker, CIK and brands from the model (src/anonymize.py; Nov 12)."""
    started = time.time()
    skip = int(row.get("skip_newest") or SKIP_NEWEST)
    extra = {"prompt": prompt} if prompt else {}
    if anonymize:
        extra["anonymize"] = True
    out = investigate(row["ticker"], on_event=on_event, log_path=log_path, skip_newest=skip, **extra)
    direction, probability = parse(out["answer"])
    if "no data found" in out["answer"].lower()[:300]:
        direction = None
    return {"ticker": row["ticker"], "out": out, "direction": direction, "probability": probability,
            "correct": is_correct(direction, row["truth"]), "seconds": round(time.time() - started), "ts": time.time(),
            "anonymized": anonymize}
