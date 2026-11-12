# --- Javier: the report for the 200-company backtest (code written with help from Claude) ---
# Implements the analysis fixed in docs/test_plan.md before the run. No model calls and no EDGAR calls: everything
# comes from eval/test_set_200.csv (truth and baselines, fixed when the set was built) and
# eval/backtest_200_results.jsonl (the model's answers).
#
#   Main result: model accuracy vs each baseline on the SAME companies, exact McNemar test (two-sided binomial test on
#                the companies where the two disagree). A missing answer counts as wrong (docs/success_metric.md).
#   Secondary:   95% Wilson intervals, the confusion table, calibration by stated probability, accuracy by target
#                type and by industry group.
#
# Run from the repository root:
#   python -m eval.analyze_backtest                # default prompt; writes eval/backtest_200_report.md
#   python -m eval.analyze_backtest --prompt V4
#   python -m eval.analyze_backtest --anonymize     # the anonymized run (Nov 12); writes eval/backtest_200_anon_report.md
import csv
import json
import sys
from math import comb, sqrt
from pathlib import Path

from src.agent import DEFAULT_PROMPT

TEST_SET_PATH = Path("eval/test_set_200.csv")
RESULTS_PATH = Path("eval/backtest_200_results.jsonl")
REPORT_PATH = Path("eval/backtest_200_report.md")
ANON_RESULTS_PATH = Path("eval/backtest_200_anon_results.jsonl")       # Nov 12: python -m eval.run_backtest --anonymize
BASELINES = {"always_increase": "Always increase", "momentum": "Momentum", "reverse_momentum": "Reverse momentum"}
BANDS = [(0.0, 0.6, "below 0.60"), (0.6, 0.7, "0.60 to 0.69"), (0.7, 0.8, "0.70 to 0.79"), (0.8, 1.01, "0.80 and up")]


def wilson(k, n, z=1.96):
    """95% confidence interval for a proportion (Wilson), as (low, high)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


def mcnemar_exact(model_only, baseline_only):
    """Two-sided exact McNemar p-value: a binomial test on the discordant companies."""
    d = model_only + baseline_only
    if d == 0:
        return 1.0
    k = min(model_only, baseline_only)
    tail = sum(comb(d, i) for i in range(k + 1)) / 2 ** d
    return min(1.0, 2 * tail)


def pct(k, n):
    return f"{k / n:.0%}" if n else "n/a"


def load(prompt, results_path=None):
    results_path = results_path or RESULTS_PATH
    with open(TEST_SET_PATH, newline="", encoding="utf-8") as f:
        test_set = list(csv.DictReader(f))
    latest = {}
    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r["prompt"] == prompt and not r.get("error"):
                        latest[r["ticker"]] = r               # the last successful run per company
    return test_set, latest


def report(prompt, anonymize=False):
    test_set, results = load(prompt, ANON_RESULTS_PATH if anonymize else RESULTS_PATH)
    rows = [{**t, "model": results[t["ticker"]]["direction"], "probability": results[t["ticker"]]["probability"]}
            for t in test_set if t["ticker"] in results]
    n = len(rows)
    out = [f"# Backtest report: prompt {prompt}" + (", anonymized" if anonymize else ""), "",
           *(["Company name, ticker, CIK and brand names hidden from the model (src/anonymize.py). "
              "Compare with the named run: python -m eval.named_vs_anon.", ""] if anonymize else []),
           f"{n} of {len(test_set)} companies run. Missing answers count as wrong. "
           f"Test set and analysis fixed in advance (docs/test_plan.md).", ""]
    if n == 0:
        return "\n".join(out + ["No results yet."])
    if n < len(test_set):
        out += [f"**Incomplete run:** {len(test_set) - n} companies still to run. Numbers below cover the {n} done.", ""]

    ok = lambda pred, r: pred is not None and pred == r["truth"]                 # noqa: E731
    model_ok = [ok(r["model"], r) for r in rows]
    k = sum(model_ok)
    low, high = wilson(k, n)
    out += ["## Accuracy", "", "| Predictor | Correct | Accuracy | 95% interval |", "|---|---|---|---|",
            f"| **Model** | {k} of {n} | **{pct(k, n)}** | {low:.0%} to {high:.0%} |"]
    for key, label in BASELINES.items():
        b = sum(ok(r[key] if key != "always_increase" else "increase", r) for r in rows)
        bl, bh = wilson(b, n)
        out.append(f"| {label} | {b} of {n} | {pct(b, n)} | {bl:.0%} to {bh:.0%} |")

    out += ["", "## Model vs each baseline (same companies, exact McNemar test)", "",
            "Only the companies where the two disagree carry evidence.", "",
            "| Baseline | Model right, baseline wrong | Baseline right, model wrong | p-value | Verdict at 0.05 |",
            "|---|---|---|---|---|"]
    for key, label in BASELINES.items():
        base = [ok(r[key] if key != "always_increase" else "increase", r) for r in rows]
        model_only = sum(m and not b for m, b in zip(model_ok, base))
        base_only = sum(b and not m for m, b in zip(model_ok, base))
        p = mcnemar_exact(model_only, base_only)
        verdict = ("model better" if model_only > base_only else "baseline better") if p < 0.05 else "no clear difference"
        out.append(f"| {label} | {model_only} | {base_only} | {p:.3f} | {verdict} |")

    inc_truth = [r for r in rows if r["truth"] == "increase"]
    dec_truth = [r for r in rows if r["truth"] == "decrease"]
    count = lambda group, pred: sum(r["model"] == pred for r in group)              # noqa: E731
    out += ["", "## Confusion", "", "| | Truth: increase | Truth: decrease |", "|---|---|---|",
            f"| Model: increase | {count(inc_truth, 'increase')} | {count(dec_truth, 'increase')} |",
            f"| Model: decrease | {count(inc_truth, 'decrease')} | {count(dec_truth, 'decrease')} |",
            f"| No answer | {count(inc_truth, None)} | {count(dec_truth, None)} |", "",
            f"Base rate: {len(inc_truth)} increases, {len(dec_truth)} decreases. "
            f"Model said increase {sum(r['model'] == 'increase' for r in rows)} times."]

    out += ["", "## Calibration (is a higher stated probability more often right?)", "",
            "| Stated probability | Companies | Correct | Accuracy |", "|---|---|---|---|"]
    for lo, hi, label in BANDS:
        band = [(r, m) for r, m in zip(rows, model_ok) if r["probability"] is not None and lo <= r["probability"] < hi]
        out.append(f"| {label} | {len(band)} | {sum(m for _, m in band)} | {pct(sum(m for _, m in band), len(band))} |")
    missing_p = sum(r["probability"] is None for r in rows)
    if missing_p:
        out.append(f"| no probability given | {missing_p} | | |")

    for title, field in (("By target metric", "target"), ("By industry group", "industry_group")):
        groups = {}
        for r, m in zip(rows, model_ok):
            groups.setdefault(r[field], []).append((r, m))
        out += ["", f"## {title}", "", "| Group | Companies | Model | Always increase | Momentum |", "|---|---|---|---|---|"]
        for name, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            g = len(items)
            out.append(f"| {name.replace('_', ' ')} | {g} | {pct(sum(m for _, m in items), g)} | "
                       f"{pct(sum(r['truth'] == 'increase' for r, _ in items), g)} | "
                       f"{pct(sum(r['momentum'] == r['truth'] for r, _ in items), g)} |")
    out += ["", "Groups are small: read them as hints for where to look, not as results."]
    return "\n".join(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    prompt = args[args.index("--prompt") + 1] if "--prompt" in args else DEFAULT_PROMPT
    anonymize = "--anonymize" in args
    text = report(prompt, anonymize)
    stem = "backtest_200_anon_report" if anonymize else "backtest_200_report"
    path = REPORT_PATH.with_name(f"{stem}.md" if prompt == DEFAULT_PROMPT else f"{stem}_{prompt}.md")
    path.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nWritten to {path}")
