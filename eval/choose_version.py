# --- Javier: choose between V6 and V7 on set C (code written with help from Claude) ---
# The rule, fixed in docs/test_plan.md before set C was drawn: V6 and V7 each run once per company on set C's 200
# companies; the version with more correct answers is frozen and scored on set B; a tie goes to V6, the simpler one.
# A company counts only when both versions have a finished answer for it (a run that fails is retried, not dropped;
# a finished run with no direction counts as wrong). Set C is used for this one decision and never again.
#
#   python -m eval.run_backtest --set c --prompt V6 --runs 1
#   python -m eval.run_backtest --set c --prompt V7 --runs 1
#   python -m eval.choose_version
import csv
import json
from math import comb
from pathlib import Path

RESULTS = Path("eval/setc_results.jsonl")
TEST_SET = Path("eval/test_set_200c.csv")


def main():
    truth = {r["ticker"]: r["truth"] for r in csv.DictReader(open(TEST_SET, encoding="utf-8"))}
    rows = [json.loads(l) for l in open(RESULTS, encoding="utf-8") if l.strip()]
    done = {p: {r["ticker"]: r for r in rows if r["prompt"] == p and not r.get("error")} for p in ("V6", "V7")}
    missing = {p: sorted(set(truth) - set(d)) for p, d in done.items()}
    if any(missing.values()):
        print("Not finished yet, so no choice is made:", {p: len(m) for p, m in missing.items()}, "companies missing.")
        print("Run the set C commands again; they retry what is missing.")
        return
    right = {p: {t for t in truth if d[t]["direction"] == truth[t]} for p, d in done.items()}
    only6, only7 = len(right["V6"] - right["V7"]), len(right["V7"] - right["V6"])
    n = only6 + only7
    p = min(1, 2 * sum(comb(n, i) for i in range(min(only6, only7) + 1)) / 2 ** n) if n else 1
    winner = "V7" if len(right["V7"]) > len(right["V6"]) else "V6"
    print(f"Set C, {len(truth)} companies. V6 correct {len(right['V6'])}, V7 correct {len(right['V7'])}.")
    print(f"They disagree on {sum(done['V6'][t]['direction'] != done['V7'][t]['direction'] for t in truth)} companies; "
          f"V6 only right {only6}, V7 only right {only7} (McNemar p = {p:.2f}, descriptive).")
    print(f"By the rule fixed in advance, the version frozen for set B is {winner}.")


if __name__ == "__main__":
    main()
