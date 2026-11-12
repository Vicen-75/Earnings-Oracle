# --- German: named vs anonymized, company by company (Nov 12; code written with help from Claude) ---
# The question from the proposal feedback: is the model reading the filings, or remembering the company? The same 200
# companies are run twice with the same prompt, once with names (eval/backtest_200_results.jsonl) and once anonymized
# (eval/backtest_200_anon_results.jsonl, python -m eval.run_backtest --anonymize). This script compares the two runs on
# the companies both have answered. No model calls, no EDGAR calls.
#
#   Main comparison: named accuracy vs anonymized accuracy on the SAME companies, exact McNemar test (the same test
#                    docs/test_plan.md uses for the baselines). Only companies where one run is right and the other
#                    wrong carry evidence.
#   Also:            how often the two runs give the same direction, and the average stated probability.
#   If it exists:    eval/anonymize_check_200.csv (python -m eval.anonymize_check --set 200 --guess) splits the result
#                    by whether the model could still name the company from the anonymized text. Hiding the name only
#                    hides the company where the model cannot guess it, so that group is the cleaner test.
#
# Run from the repository root:
#   python -m eval.named_vs_anon                   # default prompt; writes eval/named_vs_anon_report.md
#   python -m eval.named_vs_anon --prompt V6
import csv
import sys
from pathlib import Path

from eval.analyze_backtest import ANON_RESULTS_PATH, RESULTS_PATH, load, mcnemar_exact, pct, wilson
from src.agent import DEFAULT_PROMPT

CHECK_PATH = Path("eval/anonymize_check_200.csv")
REPORT_PATH = Path("eval/named_vs_anon_report.md")


def load_guesses():
    """{ticker: True/False}: could the model name the company from the anonymized text? Empty if not run yet."""
    if not CHECK_PATH.exists():
        return {}
    with open(CHECK_PATH, newline="", encoding="utf-8") as f:
        return {r["ticker"]: r.get("guessed_right") == "True" for r in csv.DictReader(f) if r.get("status") == "checked"}


def compare(rows, label):
    """Markdown lines comparing the two runs on rows: [{"truth", "named", "anon", "p_named", "p_anon"}]."""
    n = len(rows)
    if n == 0:
        return [f"No companies in {label}.", ""]
    ok = lambda pred, r: pred is not None and pred == r["truth"]                 # noqa: E731
    named_ok = [ok(r["named"], r) for r in rows]
    anon_ok = [ok(r["anon"], r) for r in rows]
    kn, ka = sum(named_ok), sum(anon_ok)
    (nl, nh), (al, ah) = wilson(kn, n), wilson(ka, n)
    named_only = sum(a and not b for a, b in zip(named_ok, anon_ok))
    anon_only = sum(b and not a for a, b in zip(named_ok, anon_ok))
    p = mcnemar_exact(named_only, anon_only)
    if p >= 0.05:
        verdict = "no clear difference"
    else:
        verdict = "named better: names help the model" if named_only > anon_only else "anonymized better"
    same = sum(r["named"] == r["anon"] for r in rows)
    probs = lambda key: [r[key] for r in rows if r[key] is not None]           # noqa: E731
    mean = lambda xs: f"{sum(xs) / len(xs):.2f}" if xs else "n/a"               # noqa: E731
    return ["| Run | Correct | Accuracy | 95% interval | Average stated probability |", "|---|---|---|---|---|",
            f"| Named | {kn} of {n} | {pct(kn, n)} | {nl:.0%} to {nh:.0%} | {mean(probs('p_named'))} |",
            f"| Anonymized | {ka} of {n} | {pct(ka, n)} | {al:.0%} to {ah:.0%} | {mean(probs('p_anon'))} |", "",
            "| Named right, anonymized wrong | Anonymized right, named wrong | p-value (exact McNemar) | Verdict at 0.05 |",
            "|---|---|---|---|",
            f"| {named_only} | {anon_only} | {p:.3f} | {verdict} |", "",
            f"Same direction in both runs: {same} of {n} ({pct(same, n)}).", ""]


def report(prompt):
    test_set, named = load(prompt, RESULTS_PATH)
    _, anon = load(prompt, ANON_RESULTS_PATH)
    rows = [{"ticker": t["ticker"], "truth": t["truth"],
             "named": named[t["ticker"]]["direction"], "anon": anon[t["ticker"]]["direction"],
             "p_named": named[t["ticker"]]["probability"], "p_anon": anon[t["ticker"]]["probability"]}
            for t in test_set if t["ticker"] in named and t["ticker"] in anon]
    out = [f"# Named vs anonymized: prompt {prompt}", "",
           f"Companies run both ways: {len(rows)} of {len(test_set)} (named: {len(named)}, anonymized: {len(anon)}). "
           "Missing answers count as wrong.", ""]
    if not rows:
        return "\n".join(out + ["No company has both runs yet. Run: python -m eval.run_backtest --anonymize"])

    out += ["## All companies run both ways", ""] + compare(rows, "all companies")
    out += ["**How to read it.** If named accuracy is clearly higher, part of the named score comes from what the model "
            "remembers about the company, and the anonymized number is the honest one. No clear difference is "
            "consistent with the model reading the filings, but it is only strong evidence for the companies the model "
            "could not identify (next section).", ""]

    guesses = load_guesses()
    if not guesses:
        out += ["## Could the model still tell which company it was?", "",
                "Not measured on these companies yet. Run python -m eval.anonymize_check --set 200 --guess (one or "
                "two model calls per company) and run this report again.", ""]
    else:
        known = [r for r in rows if r["ticker"] in guesses]
        guessed = [r for r in known if guesses[r["ticker"]]]
        hidden = [r for r in known if not guesses[r["ticker"]]]
        out += ["## Could the model still tell which company it was?", "",
                f"From eval/anonymize_check_200.csv: the model named the company from the anonymized MD&A for "
                f"{len(guessed)} of {len(known)} companies checked.", "",
                "### Company still identifiable", ""] + compare(guessed, "this group")
        out += ["### Company hidden (the cleaner test)", ""] + compare(hidden, "this group")
        out += ["Groups are smaller than the full set: read the split as a hint, not as a result.", ""]
    return "\n".join(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    prompt = args[args.index("--prompt") + 1] if "--prompt" in args else DEFAULT_PROMPT
    text = report(prompt)
    path = REPORT_PATH if prompt == DEFAULT_PROMPT else REPORT_PATH.with_name(f"named_vs_anon_report_{prompt}.md")
    path.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nWritten to {path}")
