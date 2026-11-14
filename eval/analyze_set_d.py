# --- Javier: the pre-registered analysis of set D (code written with help from Claude) ---
# Plan: docs/test_plan.md, Nov 13 note. One look at accuracy, after all 400 companies have run:
#   python -m eval.analyze_set_d
# 1. The test. Set D alone: V6 (one run per company) against the three baselines, exact two-sided McNemar on correct
#    answers, significant at p < 0.05. V6 beats the baselines only if it is significantly better than all three.
#    A company with no answer counts as wrong. It refuses to run until every company has a finished result.
# 2. The combined view, descriptive. Sets B (run 1 of its three), C and D together, 800 companies V6 was not tuned on,
#    all with one run. Sets B and C were already known to favour V6 when set D was planned, so the combined numbers
#    estimate the size of the edge; they are not a second test and their p-values are not verdicts.
# Report: eval/set_d_report.md.
import csv
import sys
from math import sqrt
from pathlib import Path

from eval.analyze_set_b import BASELINES, calls_table, load, mcnemar

SET_D = Path("eval/test_set_400d.csv")
RESULTS_D = Path("eval/setd_results.jsonl")
REPORT = Path("eval/set_d_report.md")
ALPHA = 0.05
# (label, test set, results, how to read V6's one-run call from a record)
COMBINED = [("Set B (run 1 of 3)", Path("eval/test_set_200b.csv"), Path("eval/backtest_200b_results.jsonl"),
             lambda r: r.get("run1_direction")),
            ("Set C", Path("eval/test_set_200c.csv"), Path("eval/setc_results.jsonl"), lambda r: r.get("direction")),
            ("Set D", SET_D, RESULTS_D, lambda r: r.get("direction"))]


def pval(p):
    return "< 0.0001" if p < 0.0001 else f"{p:.4f}"


def paired(set_path, results_path, call):
    """(companies, V6 right?, {baseline: right?}) for one set, or None if its files or some results are missing."""
    if not set_path.exists() or not results_path.exists():
        return None
    companies = list(csv.DictReader(open(set_path, encoding="utf-8")))
    v6 = load(results_path, "V6")
    if any(c["ticker"] not in v6 for c in companies):
        return None
    truth = [c["truth"] for c in companies]
    v6_right = [call(v6[c["ticker"]]) == t for c, t in zip(companies, truth)]
    base = {name: [rule(c) == t for c, t in zip(companies, truth)] for name, rule in BASELINES.items()}
    return companies, v6_right, base


def interval(a_only, b_only, n):
    """Difference in accuracy (points) with an approximate 95% interval, from the paired counts."""
    d = (a_only - b_only) / n
    se = sqrt(max(a_only + b_only - (a_only - b_only) ** 2 / n, 0)) / n
    return 100 * d, 100 * (d - 1.96 * se), 100 * (d + 1.96 * se)


def main():
    if not SET_D.exists():
        sys.exit(f"{SET_D} not found: run  python -m eval.run_set_d  first.")
    companies = list(csv.DictReader(open(SET_D, encoding="utf-8")))
    tickers = [c["ticker"] for c in companies]
    truth = [c["truth"] for c in companies]
    v6 = load(RESULTS_D, "V6")
    missing = [t for t in tickers if t not in v6]
    if missing or len(tickers) != 400:
        sys.exit(f"Set D is not complete: {len(tickers)} companies in the list, {len(missing)} without a finished V6 "
                 f"result. Finish the runs first (python -m eval.run_set_d); accuracy is looked at once.")
    out = [f"# Set D: {len(tickers)} companies, V6 with one run", "",
           "Pre-registered in docs/test_plan.md (Nov 13 note), one look. Exact two-sided McNemar on correct answers; "
           f"significant at p < {ALPHA}. V6 beats the baselines only if it is significantly better than all three. "
           "No answer counts as wrong.", "",
           "| Version | Correct | Decrease calls | No answer |", "| --- | --- | --- | --- |"]
    line, v6_right = calls_table("V6 (one run)", [v6[t].get("direction") for t in tickers], truth)
    out.append(line)
    base_right = {}
    for name, rule in BASELINES.items():
        line, base_right[name] = calls_table(name, [rule(c) for c in companies], truth)
        out.append(line)
    out += ["", "| V6 against | V6 only right | Baseline only right | p | Significant |", "| --- | --- | --- | --- | --- |"]
    wins = []
    for name in BASELINES:
        a, b, p = mcnemar(v6_right, base_right[name])
        wins.append(p < ALPHA and a > b)
        out.append(f"| {name} | {a} | {b} | {pval(p)} | {'yes' if wins[-1] else 'no'} |")
    out += ["", f"**Result: {'V6 beats all three baselines' if all(wins) else 'V6 does not beat all three baselines'}.**"]

    out += ["", "## Combined view: sets B, C and D (descriptive, not a test)", "",
            "Sets B and C were already known to favour V6 when set D was planned, so these numbers estimate the size "
            "of the edge over always increase; the p-values are not verdicts. V6 with one run everywhere.", "",
            "| Set | Companies | V6 correct | Always increase correct | V6 only right | Always increase only right | "
            "Difference, points (approx. 95% interval) | p (descriptive) |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    all_v6, all_base, skipped = [], {name: [] for name in BASELINES}, []
    for label, set_path, results_path, call in COMBINED:
        got = paired(set_path, results_path, call)
        if got is None:
            skipped.append(label)
            continue
        rows, right, base = got
        all_v6 += right
        for name in BASELINES:
            all_base[name] += base[name]
        a, b, p = mcnemar(right, base["Always increase"])
        d, lo, hi = interval(a, b, len(rows))
        out.append(f"| {label} | {len(rows)} | {sum(right)} ({100 * sum(right) / len(rows):.1f}%) | "
                   f"{sum(base['Always increase'])} ({100 * sum(base['Always increase']) / len(rows):.1f}%) | {a} | {b} | "
                   f"{d:+.1f} ({lo:+.1f} to {hi:+.1f}) | {pval(p)} |")
    if all_v6:
        n = len(all_v6)
        a, b, p = mcnemar(all_v6, all_base["Always increase"])
        d, lo, hi = interval(a, b, n)
        out.append(f"| **All together** | {n} | {sum(all_v6)} ({100 * sum(all_v6) / n:.1f}%) | "
                   f"{sum(all_base['Always increase'])} ({100 * sum(all_base['Always increase']) / n:.1f}%) | {a} | {b} | "
                   f"{d:+.1f} ({lo:+.1f} to {hi:+.1f}) | {pval(p)} |")
        out += ["", "| All together, V6 against | V6 only right | Baseline only right | p (descriptive) |",
                "| --- | --- | --- | --- |"]
        for name in BASELINES:
            a, b, p = mcnemar(all_v6, all_base[name])
            out.append(f"| {name} | {a} | {b} | {pval(p)} |")
    if skipped:
        out += ["", "Left out (files or results missing here): " + ", ".join(skipped) + "."]
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    print(f"\nSaved {REPORT}")


if __name__ == "__main__":
    main()
