# --- Javier: what does each tool add? Ablations on set A, issue #52 (code written with help from Claude) ---
# Compares V5's set A answers (eval/backtest_200_results.jsonl, Nov 6) with the same agent run with one kind of tool
# taken away, on the same companies: no_mdna (no MD&A tools) or no_ratios (no ratio tool). Plans fixed before each run:
# docs/test_plan.md, Nov 10.
#
#   Main result: full V5 vs the ablated run, exact two-sided McNemar test, p < 0.05. A missing answer counts as wrong.
#   Also: each against the baselines, the confusion tables, decrease-call precision, calibration, cost per run, and an
#   exploratory breakdown (chosen after seeing the no_mdna results, so it explains rather than tests).
#
# Run from the repository root:
#   python -m eval.ablation_report --ablation no_mdna      (writes eval/ablation_no_mdna_report.md)
#   python -m eval.ablation_report --ablation no_ratios    (writes eval/ablation_no_ratios_report.md)
import csv
import json
import sys
from pathlib import Path

from eval.analyze_backtest import wilson, mcnemar_exact, pct, BANDS

TEST_SET_PATH = Path("eval/test_set_200.csv")
WHAT = {"no_mdna": ("the MD&A", "MD&A tools"), "no_ratios": ("the ratios", "ratio tool")}
WITH_PATH = Path("eval/backtest_200_results.jsonl")
PROMPT = "V5"


def latest(path, prompt):
    out = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r["prompt"] == prompt and not r.get("error"):
                        out[r["ticker"]] = r               # the last successful run per company
    return out


def main(args):
    ablation = args[args.index("--ablation") + 1] if "--ablation" in args else "no_mdna"
    without_path = Path(f"eval/ablation_{ablation}_results.jsonl")
    report_path = Path(f"eval/ablation_{ablation}_report.md")
    with open(TEST_SET_PATH, newline="", encoding="utf-8") as f:
        test_set = list(csv.DictReader(f))
    with_mdna, without = latest(WITH_PATH, PROMPT), latest(without_path, PROMPT)
    rows = [t for t in test_set if t["ticker"] in without]       # companies the ablation has run
    n = len(rows)
    if n == 0:
        sys.exit(f"No ablation results yet in {without_path}.")

    def pred(results, t):
        r = results.get(t["ticker"])
        return r["direction"] if r else None

    def prob(results, t):
        r = results.get(t["ticker"])
        return r["probability"] if r else None

    ok = lambda p, t: p is not None and p == t["truth"]           # noqa: E731
    thing, tools = WHAT.get(ablation, (ablation, ablation))
    WITH, WITHOUT = "Full V5", f"Without {thing}"
    a = [ok(pred(with_mdna, t), t) for t in rows]
    b = [ok(pred(without, t), t) for t in rows]
    out = [f"# Ablation on set A: V5 with and without {thing} (issue #52)", "",
           f"{n} of {len(test_set)} companies run without the {tools}. Plan fixed before the run "
           "(docs/test_plan.md, Nov 10). Missing answers count as wrong.", ""]
    if n < len(test_set):
        out += [f"**Incomplete run:** {len(test_set) - n} companies still to run. Numbers cover the {n} done.", ""]

    out += ["## Accuracy", "", "| Predictor | Correct | Accuracy | 95% interval |", "|---|---|---|---|"]
    for label, flags in ((WITH, a), (WITHOUT, b)):
        k = sum(flags)
        lo, hi = wilson(k, n)
        out.append(f"| {label} | {k} of {n} | {pct(k, n)} | {lo:.0%} to {hi:.0%} |")
    for label, key in (("Always increase", None), ("Momentum", "momentum")):
        k = sum(ok("increase" if key is None else t[key], t) for t in rows)
        lo, hi = wilson(k, n)
        out.append(f"| {label} | {k} of {n} | {pct(k, n)} | {lo:.0%} to {hi:.0%} |")

    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    p = mcnemar_exact(only_a, only_b)
    verdict = (f"{thing} helps" if only_a > only_b else f"{thing} hurts") if p < 0.05 else "no clear difference"
    same = sum(pred(with_mdna, t) == pred(without, t) for t in rows)
    out += ["", f"## Main result: with vs without {thing} (exact McNemar, same companies)", "",
            f"| Right only with {thing} | Right only without {thing} | p-value | Verdict at 0.05 |", "|---|---|---|---|",
            f"| {only_a} | {only_b} | {p:.3f} | {verdict} |", "",
            f"The two runs gave the same direction on {same} of {n} companies ({pct(same, n)}).", ""]

    out += ["## Each against always-increase (exact McNemar)", "",
            "| Run | Right, always-increase wrong | Always-increase right, run wrong | p-value |", "|---|---|---|---|"]
    base = [t["truth"] == "increase" for t in rows]
    for label, flags in ((WITH, a), (WITHOUT, b)):
        x = sum(f and not g for f, g in zip(flags, base))
        y = sum(g and not f for f, g in zip(flags, base))
        out.append(f"| {label} | {x} | {y} | {mcnemar_exact(x, y):.3f} |")

    out += ["", "## How each run calls direction", "",
            "| Run | Said increase | Said decrease | No answer | Decrease calls right | Increase calls right |",
            "|---|---|---|---|---|---|"]
    for label, results in ((WITH, with_mdna), (WITHOUT, without)):
        ps = [pred(results, t) for t in rows]
        dec = [t for t, x in zip(rows, ps) if x == "decrease"]
        inc = [t for t, x in zip(rows, ps) if x == "increase"]
        dk = sum(t["truth"] == "decrease" for t in dec)
        ik = sum(t["truth"] == "increase" for t in inc)
        out.append(f"| {label} | {len(inc)} | {len(dec)} | {ps.count(None)} | {dk} of {len(dec)} ({pct(dk, len(dec))}) | "
                   f"{ik} of {len(inc)} ({pct(ik, len(inc))}) |")

    out += ["", "## Calibration (accuracy by stated probability)", "",
            f"| Stated probability | {WITH} | {WITHOUT} |", "|---|---|---|"]
    for lo, hi, label in BANDS:
        cells = []
        for results in (with_mdna, without):
            band = [t for t in rows if prob(results, t) is not None and lo <= prob(results, t) < hi]
            k = sum(ok(pred(results, t), t) for t in band)
            cells.append(f"{k} of {len(band)} ({pct(k, len(band))})" if band else "none")
        out.append(f"| {label} | {cells[0]} | {cells[1]} |")

    out += ["", "## Cost per run (median)", "", "| Run | Input tokens | Model calls | Seconds |", "|---|---|---|---|"]
    for label, results in ((WITH, with_mdna), (WITHOUT, without)):
        rs = [results[t["ticker"]] for t in rows if t["ticker"] in results]
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0       # noqa: E731
        out.append(f"| {label} | {med([r['usage'].get('prompt_tokens', 0) for r in rs]):,} | "
                   f"{med([r['usage'].get('model_calls', 0) for r in rs])} | {med([r.get('seconds', 0) for r in rs])} |")
    out += exploratory(rows, with_mdna, without, WITH, WITHOUT, pred, ok)
    out += ["", "Run-to-run variation (issue #51) means some disagreements between the two runs would happen even with "
            "identical tools; the McNemar test counts only the companies where they disagree, and the verdict should be "
            "read with that in mind.", ""]
    report_path.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {report_path}: {WITH} {sum(a)}/{n}, {WITHOUT} {sum(b)}/{n}, p = {p:.3f} ({verdict}).")


def exploratory(rows, full, ablated, WITH, WITHOUT, pred, ok):
    """Breakdown chosen after seeing the no_mdna results (Nov 10): explanatory, not a test."""
    out = ["", "## Exploratory: where the difference comes from", "",
           "Chosen after seeing the first ablation's results, so these cuts explain the result; they do not test it.", "",
           f"Calls in the same direction as last year (momentum): {WITH} {sum(pred(full, t) == t['momentum'] for t in rows)}, "
           f"{WITHOUT} {sum(pred(ablated, t) == t['momentum'] for t in rows)}, of {len(rows)}.", "",
           f"| Last year, then this year | Companies | {WITH} right | {WITHOUT} right |", "|---|---|---|---|"]
    for m in ("increase", "decrease"):
        for tr in ("increase", "decrease"):
            g = [t for t in rows if t["momentum"] == m and t["truth"] == tr]
            out.append(f"| {'rose' if m == 'increase' else 'fell'}, then {'rose' if tr == 'increase' else 'fell'} | {len(g)} | "
                       f"{sum(ok(pred(full, t), t) for t in g)} | {sum(ok(pred(ablated, t), t) for t in g)} |")
    flips = {}
    for t in rows:
        x, y = pred(ablated, t), pred(full, t)
        if x != y and x and y:
            k = (x, y)
            flips.setdefault(k, [0, 0])[0 if ok(y, t) else 1] += 1
    out += ["", f"Companies where the two runs disagree, by direction of the change from {WITHOUT} to {WITH}:", "",
            f"| {WITHOUT} said | {WITH} said | Full V5 right | Full V5 wrong |", "|---|---|---|---|"]
    out += [f"| {x} | {y} | {r} | {w} |" for (x, y), (r, w) in sorted(flips.items(), key=lambda kv: -sum(kv[1]))]
    agree = [t for t in rows if pred(full, t) == pred(ablated, t) and pred(full, t)]
    k = sum(ok(pred(full, t), t) for t in agree)
    inc = sum(t["truth"] == "increase" for t in agree)
    out += ["", f"When both runs give the same call ({len(agree)} companies) they are right {k} times ({pct(k, len(agree))}); "
            f"always-increase on the same companies: {pct(inc, len(agree))}.", ""]
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
