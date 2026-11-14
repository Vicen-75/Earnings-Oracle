# --- Javier: is the model more accurate when it is more confident? (code written with help from Claude) ---
# EXPLORATORY. This is not in docs/test_plan.md: it was written on Nov 12, after the set B result was known, and it is
# not a test of the project's success. It only describes answers already collected. No model calls, no EDGAR calls,
# and no results file is changed. The bands and cut-offs below were fixed before anyone looked at these numbers.
#
# "Confidence" is the probability the model gave for the direction it called (0.50 is a coin flip). For V6 on set B
# it is the average of three runs (src/consensus.py); everywhere else it is the single run's own number.
# Four questions, for each version and set that has results in eval/:
#   1. Is the model right more often when it is more confident? Accuracy by confidence band, and one summary number,
#      the concordance: how often a correct call carries a higher confidence than a wrong one (0.50 = no information).
#   2. Would answering only when confident help? Accuracy above each cut-off, next to "always increase" on the SAME
#      companies, because confident calls may simply be the easy increases.
#   3. Is the probability itself any good? Brier score (lower is better) against a forecast that always states the
#      set's own share of increases, and against a coin flip.
#   4. Set B, V6 only: is it right more often when the three runs agree on the direction?
# Set B is the pre-registered set. Sets A and C are shown as a check that a pattern is not a one-set accident; set A's
# V6 run is in-sample (V6 was written after reading set A's errors).
#
#   python -m eval.confidence_analysis          # summary of every version, detail for set B; writes the report
#   python -m eval.confidence_analysis --all    # detail for every version
import csv
import json
import sys
from math import comb, erfc, sqrt
from pathlib import Path

REPORT = Path("eval/confidence_report.md")
BANDS = [(0.0, 0.5, "below 0.50"), (0.5, 0.6, "0.50 to 0.59"), (0.6, 0.7, "0.60 to 0.69"),
         (0.7, 0.8, "0.70 to 0.79"), (0.8, 9.9, "0.80 and up")]
CUTS = [0.5, 0.6, 0.7, 0.8]
SPLIT = 0.7          # the summary table compares calls below this confidence with calls at or above it
EPS = 1e-9           # so that a stored 0.6 or 0.7 always lands in the band that starts there
DATASETS = [  # (label, test set, results file, prompt, detail by default)
    ("Set B, V6 (three runs averaged)", "eval/test_set_200b.csv", "eval/backtest_200b_results.jsonl", "V6", True),
    ("Set B, V5 (one run)", "eval/test_set_200b.csv", "eval/backtest_200b_results.jsonl", "V5", True),
    ("Set C, V6 (one run)", "eval/test_set_200c.csv", "eval/setc_results.jsonl", "V6", False),
    ("Set C, V7 (one run)", "eval/test_set_200c.csv", "eval/setc_results.jsonl", "V7", False),
    ("Set A, V5 (one run)", "eval/test_set_200.csv", "eval/backtest_200_results.jsonl", "V5", False),
    ("Set A, V6 (one run, in-sample)", "eval/test_set_200.csv", "eval/backtest_200_v6_results.jsonl", "V6", False),
]


def load(path, prompt):
    """Latest finished (non-error) record per ticker for this prompt, full agent only (no ablation arm)."""
    rows = {}
    for line in open(path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if r.get("prompt") == prompt and not r.get("error") and not r.get("ablation"):
                rows[r["ticker"]] = r
    return rows


def cases(set_path, results_path, prompt):
    """One dict per answered company of the test set, and the number of companies in the set.
    A company with no direction or no probability has no confidence to study, so it is left out and counted."""
    companies = list(csv.DictReader(open(set_path, encoding="utf-8")))
    records = load(results_path, prompt)
    out = []
    for c in companies:
        r = records.get(c["ticker"]) or {}
        direction, conf = r.get("direction"), r.get("probability")
        if direction not in ("increase", "decrease") or not isinstance(conf, (int, float)):
            continue
        p_inc = r.get("p_increase_mean")
        if not isinstance(p_inc, (int, float)):
            p_inc = conf if direction == "increase" else 1 - conf
        runs = [x.get("direction") for x in (r.get("runs") or []) if x.get("direction") in ("increase", "decrease")]
        out.append({"ticker": c["ticker"], "truth": c["truth"], "direction": direction, "conf": conf, "p_inc": p_inc,
                    "right": direction == c["truth"],
                    "agree": (len(set(runs)) == 1) if len(runs) >= 2 else None})
    return out, len(companies)


def concordance(rows):
    """(share of right/wrong pairs where the right call has the higher confidence, ties count half; two-sided p from
    the rank-sum test, normal approximation with the correction for ties). None if all calls are right or all wrong."""
    right = [r["conf"] for r in rows if r["right"]]
    wrong = [r["conf"] for r in rows if not r["right"]]
    if not right or not wrong:
        return None
    u = sum((a > b + EPS) + 0.5 * (abs(a - b) <= EPS) for a in right for b in wrong)
    n1, n2 = len(right), len(wrong)
    n = n1 + n2
    counts = {}
    for v in right + wrong:
        counts[round(v, 6)] = counts.get(round(v, 6), 0) + 1
    ties = sum(t ** 3 - t for t in counts.values())
    variance = n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1)))
    p = erfc(abs(u - n1 * n2 / 2) / sqrt(variance) / sqrt(2)) if variance > 0 else 1.0
    return u / (n1 * n2), p


def fisher(a, b, c, d):
    """Exact two-sided Fisher p for the table [[a, b], [c, d]]."""
    row1, col1, n = a + b, a + c, a + b + c + d
    if not n or not row1 or not col1 or row1 == n or col1 == n:
        return 1.0
    prob = lambda x: comb(col1, x) * comb(n - col1, row1 - x) / comb(n, row1)
    observed = prob(a)
    return min(1.0, sum(prob(x) for x in range(max(0, row1 - (n - col1)), min(row1, col1) + 1)
                        if prob(x) <= observed * (1 + 1e-9)))


def brier(rows):
    """(model, constant forecast of the set's own share of increases, coin flip). Lower is better."""
    y = [r["truth"] == "increase" for r in rows]
    share = sum(y) / len(y)
    return (sum((r["p_inc"] - t) ** 2 for r, t in zip(rows, y)) / len(y), share * (1 - share), 0.25)


def frac(k, n):
    return f"{k} of {n} ({100 * k / n:.1f}%)" if n else "none"


def pval(p):
    return "< 0.0001" if p < 0.0001 else f"= {p:.4f}"


def nright(rows):
    return sum(r["right"] for r in rows)


def detail(label, rows, total):
    out = [f"## {label}", "",
           f"Answered with a probability: {len(rows)} of {total} companies. Correct: {frac(nright(rows), len(rows))}.", "",
           "| Confidence | Companies | Correct | Average stated confidence | Increase calls right | Decrease calls right |",
           "| --- | --- | --- | --- | --- | --- |"]
    for lo, hi, name in BANDS:
        band = [r for r in rows if lo - EPS <= r["conf"] < hi - EPS]
        if not band:
            if lo < 0.5:
                continue
            out.append(f"| {name} | 0 | none | | none | none |")
            continue
        inc = [r for r in band if r["direction"] == "increase"]
        dec = [r for r in band if r["direction"] == "decrease"]
        out.append(f"| {name} | {len(band)} | {frac(nright(band), len(band))} | "
                   f"{sum(r['conf'] for r in band) / len(band):.2f} | {frac(nright(inc), len(inc))} | "
                   f"{frac(nright(dec), len(dec))} |")
    c = concordance(rows)
    if c:
        out += ["", f"Concordance: {c[0]:.3f} (0.500 means confidence says nothing about being right; rank-sum "
                    f"p {pval(c[1])}, exploratory)."]
    out += ["", "| Answer only when confidence is at least | Companies answered | Correct | "
                "Always increase on the same companies |", "| --- | --- | --- | --- |"]
    for cut in CUTS:
        kept = [r for r in rows if r["conf"] >= cut - EPS]
        out.append(f"| {cut:.2f} | {len(kept)} of {total} ({100 * len(kept) / total:.1f}%) | "
                   f"{frac(nright(kept), len(kept))} | "
                   f"{frac(sum(r['truth'] == 'increase' for r in kept), len(kept))} |")
    model, base, coin = brier(rows)
    out += ["", f"Brier score of the probability of an increase: model {model:.4f}; always stating the set's own "
                f"share of increases {base:.4f}; coin flip {coin:.4f}. Lower is better, and the constant forecast "
                "has the advantage of knowing the share in advance."]
    with_runs = [r for r in rows if r["agree"] is not None]
    if with_runs:
        same = [r for r in with_runs if r["agree"]]
        split = [r for r in with_runs if not r["agree"]]
        p = fisher(nright(same), len(same) - nright(same), nright(split), len(split) - nright(split))
        out += ["", "| The runs | Companies | Correct |", "| --- | --- | --- |",
                f"| all gave the same direction | {len(same)} | {frac(nright(same), len(same))} |",
                f"| disagreed on the direction | {len(split)} | {frac(nright(split), len(split))} |", "",
                f"Exact Fisher test of that difference: p {pval(p)} (exploratory)."]
    return out + [""]


def main(argv):
    everything = "--all" in argv
    out = ["# Confidence and accuracy (exploratory)", "",
           "Not pre-registered: written on Nov 12, 2026, after the set B result was known. It describes answers "
           "already collected and is not a test of the project's success. Confidence is the probability the model "
           "gave for the direction it called. The bands and cut-offs were fixed before the numbers were seen. Each "
           "band holds few companies, so its accuracy is uncertain by roughly 10 to 15 points either way.", "",
           f"| Version and set | Answered | Correct | Concordance | p | Confidence below {SPLIT:.2f}: correct | "
           f"Confidence {SPLIT:.2f} and up: correct | Brier, model | Brier, share of increases |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    details, skipped = [], []
    for label, set_path, results_path, prompt, by_default in DATASETS:
        if not Path(set_path).exists() or not Path(results_path).exists():
            skipped.append(label)
            continue
        rows, total = cases(set_path, results_path, prompt)
        if not rows:
            skipped.append(label)
            continue
        low = [r for r in rows if r["conf"] < SPLIT - EPS]
        high = [r for r in rows if r["conf"] >= SPLIT - EPS]
        c = concordance(rows)
        model, base, _ = brier(rows)
        out.append(f"| {label} | {len(rows)} of {total} | {frac(nright(rows), len(rows))} | "
                   f"{f'{c[0]:.3f}' if c else 'n/a'} | {pval(c[1]).lstrip('= ') if c else 'n/a'} | {frac(nright(low), len(low))} | "
                   f"{frac(nright(high), len(high))} | {model:.4f} | {base:.4f} |")
        if by_default or everything:
            details += detail(label, rows, total)
    out.append("")
    if skipped:
        out += ["No results found here for: " + "; ".join(skipped) + ".", ""]
    out += details
    REPORT.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"Saved {REPORT}")


if __name__ == "__main__":
    main(sys.argv[1:])
