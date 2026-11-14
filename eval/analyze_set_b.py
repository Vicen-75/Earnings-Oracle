# --- Javier: the pre-registered analysis of set B (code written with help from Claude) ---
# Plan: docs/test_plan.md (Nov 10, Nov 11 and Nov 12 notes). Two looks at accuracy, in this order:
#   python -m eval.analyze_set_b --stage 1    the first 100 companies, V6 against the three baselines, p < 0.005
#   python -m eval.analyze_set_b --stage 2    all 200, p < 0.048; then V6 against V5 (p < 0.05) and the five
#                                             ablation arms (Holm, family alpha 0.05), each only if complete
# Stage 2 refuses to run before the stage 1 report exists. A company with no answer counts as wrong. Every test is
# an exact two-sided McNemar test on correct answers. Reports: eval/set_b_stage1_report.md, set_b_stage2_report.md.
import csv
import json
import sys
from math import comb
from pathlib import Path

SET_B = Path("eval/test_set_200b.csv")
MAIN = Path("eval/backtest_200b_results.jsonl")
ARM_FILES = {"no_downward": Path("eval/ablation_b_no_downward_results.jsonl"),
             "no_oneoff": Path("eval/ablation_b_no_oneoff_results.jsonl"),
             "no_structured": Path("eval/ablation_b_no_structured_results.jsonl")}
ARM_NAMES = {"no_downward": "Without the downward rules (vs V6 run 1)",
             "no_oneoff": "Without the one-off adjustment (vs V6 run 1)",
             "no_structured": "Without the structured MD&A pass (vs V6 run 1)"}
REPORT = {1: Path("eval/set_b_stage1_report.md"), 2: Path("eval/set_b_stage2_report.md")}
ALPHA = {1: 0.005, 2: 0.048}
BASELINES = {"Always increase": lambda r: "increase",
             "Momentum": lambda r: r.get("momentum") or None,
             "Reverse momentum": lambda r: r.get("reverse_momentum") or None}


def mcnemar(a_right, b_right):
    """Exact two-sided McNemar p on paired correct/incorrect lists. Returns (a_only, b_only, p)."""
    a_only = sum(x and not y for x, y in zip(a_right, b_right))
    b_only = sum(y and not x for x, y in zip(a_right, b_right))
    n, k = a_only + b_only, min(a_only, b_only)
    p = min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    return a_only, b_only, p


def holm(pvalues, alpha=0.05):
    """Holm step-down: {name: significant?} for a dict of p-values."""
    order = sorted(pvalues, key=pvalues.get)
    out, still = {}, True
    for i, name in enumerate(order):
        still = still and pvalues[name] < alpha / (len(order) - i)
        out[name] = still
    return out


def load(path, prompt):
    """Latest finished (non-error) record per ticker for this prompt."""
    rows = {}
    if path.exists():
        for line in open(path, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("prompt") == prompt and not r.get("error"):
                    rows[r["ticker"]] = r
    return rows


def calls_table(name, directions, truth):
    right = [d == t for d, t in zip(directions, truth)]
    dec = [i for i, d in enumerate(directions) if d == "decrease"]
    none = sum(d is None for d in directions)
    return (f"| {name} | {sum(right)} ({100 * sum(right) / len(truth):.1f}%) | {len(dec)} "
            f"({sum(right[i] for i in dec)} right) | {none} |"), right


def main(argv):
    stage = int(argv[argv.index("--stage") + 1]) if "--stage" in argv else 1
    if stage == 2 and not REPORT[1].exists():
        sys.exit("Stage 1 comes first (docs/test_plan.md): run  python -m eval.analyze_set_b --stage 1")
    companies = list(csv.DictReader(open(SET_B, encoding="utf-8")))[: 100 if stage == 1 else 200]
    tickers = [c["ticker"] for c in companies]
    truth = [c["truth"] for c in companies]
    v6 = load(MAIN, "V6")
    missing = [t for t in tickers if t not in v6]
    if missing:
        sys.exit(f"V6 has no finished result for {len(missing)} of the {len(tickers)} companies "
                 f"(first: {', '.join(missing[:5])}). Finish the runs first.")
    v6_dir = [v6[t]["direction"] for t in tickers]
    out = [f"# Set B, stage {stage}: {len(tickers)} companies", "",
           f"Pre-registered in docs/test_plan.md. Exact two-sided McNemar on correct answers; significant at "
           f"p < {ALPHA[stage]}. V6 beats the baselines only if it is significantly better than all three. "
           "No answer counts as wrong.", "",
           "| Version | Correct | Decrease calls | No answer |", "| --- | --- | --- | --- |"]
    line, v6_right = calls_table("V6 (three runs averaged)", v6_dir, truth)
    out.append(line)
    base_right = {}
    for name, rule in BASELINES.items():
        line, base_right[name] = calls_table(name, [rule(c) for c in companies], truth)
        out.append(line)
    out += ["", "| V6 against | V6 only right | Baseline only right | p | Significant |", "| --- | --- | --- | --- | --- |"]
    wins = []
    for name in BASELINES:
        a, b, p = mcnemar(v6_right, base_right[name])
        sig = p < ALPHA[stage] and a > b
        wins.append(sig)
        out.append(f"| {name} | {a} | {b} | {p:.4f} | {'yes' if sig else 'no'} |")
    verdict = ("V6 beats all three baselines" if all(wins) else
               "V6 does not beat all three baselines" + (" (not yet significant; stage 2 decides)" if stage == 1 else ""))
    out += ["", f"**Result: {verdict}.**"]

    if stage == 2:
        out += ["", "## Secondary: V6 against V5 (p < 0.05)", ""]
        v5 = load(MAIN, "V5")
        if all(t in v5 for t in tickers):
            line, v5_right = calls_table("V5", [v5[t]["direction"] for t in tickers], truth)
            a, b, p = mcnemar(v6_right, v5_right)
            out += ["| Version | Correct | Decrease calls | No answer |", "| --- | --- | --- | --- |", line, "",
                    f"V6 only right {a}, V5 only right {b}, p = {p:.4f}: "
                    f"{'V6 is significantly better' if p < 0.05 and a > b else 'V5 is significantly better' if p < 0.05 else 'no clear difference'}."]
        else:
            out.append("Not run: V5 has not finished all 200 companies.")
        out += ["", "## Secondary: component ablation (Holm, family alpha 0.05)", ""]
        run1 = [((v6[t].get("runs") or [{}])[0]).get("direction") for t in tickers]
        run1_right = [d == x for d, x in zip(run1, truth)]
        arms = {"Self-consistency (run 1 alone vs averaged)": (run1, v6_right),
                "Decision rule (majority vote vs averaged)": ([v6[t].get("majority_direction") for t in tickers], v6_right)}
        not_done = []
        for arm, path in ARM_FILES.items():
            rows = load(path, "V6")
            if all(t in rows for t in tickers):
                arms[ARM_NAMES[arm]] = ([rows[t]["direction"] for t in tickers], run1_right)
            else:
                not_done.append(f"{arm} ({sum(t in rows for t in tickers)}/200)")
        if not_done:
            out.append("Arms not complete, so the ablation is not tested yet: " + ", ".join(not_done) + ".")
        else:
            rows_out, pvals = [], {}
            for name, (dirs, reference_right) in arms.items():
                right = [d == x for d, x in zip(dirs, truth)]
                a, b, p = mcnemar(reference_right, right)
                pvals[name] = p
                dec = [i for i, d in enumerate(dirs) if d == "decrease"]
                rows_out.append((name, sum(right), len(dec), sum(right[i] for i in dec), a, b, p))
            sig = holm(pvals)
            out += ["| Arm | Arm correct | Arm decrease calls (right) | Reference only right | Arm only right | p | Significant (Holm) |",
                    "| --- | --- | --- | --- | --- | --- | --- |"]
            out += [f"| {n} | {c} | {d} ({dr}) | {a} | {b} | {p:.4f} | {'yes' if sig[n] else 'no'} |" for n, c, d, dr, a, b, p in rows_out]
    REPORT[stage].write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    print(f"\nSaved {REPORT[stage]}")


if __name__ == "__main__":
    main(sys.argv[1:])
