# --- Javier: run the agent on the 200-company test set (code written with help from Claude) ---
# Plan: docs/test_plan.md. Runs from the command line, off the deployed app, with the keys in .streamlit/secrets.toml
# (GEMINI_API_KEYS). Several companies run at the same time: the waiting line (src/run_limiter.py) caps them at two per
# key and the key pool (src/key_pool.py) spreads them across keys.
#
# Every finished company is appended to eval/backtest_200_results.jsonl right away, so a crash or a quota stop loses at
# most the companies in progress; running again skips what is done. Results are kept per prompt version, so V5 and a
# later V6 can be compared on the same companies.
#
# Run from the repository root:
#   python -m eval.run_backtest                    # the whole test set with the default prompt
#   python -m eval.run_backtest --limit 5          # a short trial
#   python -m eval.run_backtest --prompt V4
#   python -m eval.analyze_backtest                # the report, when the runs are done
#
# Nov 10, set B (docs/test_plan.md, fresh test for V6): --set b runs eval/test_set_200b.csv and writes
# eval/backtest_200b_results.jsonl and eval/backtest_200b_runs.jsonl. It is blind: it prints progress and errors only,
# never correct or wrong, because the plan allows exactly two looks at accuracy (after 100 and after 200 companies).
#   python -m eval.run_backtest --set b --prompt V6 --limit 100     # stage 1: the first 100, in set order
#   python -m eval.run_backtest --set b --prompt V6                 # stage 2: the rest
#
# Nov 10, issue #52: --ablation no_mdna runs set A with the MD&A tools taken away (src/agent.py, ABLATIONS) and writes
# eval/ablation_no_mdna_results.jsonl and eval/ablation_no_mdna_runs.jsonl. Not blind: set A is already analyzed.
#   python -m eval.run_backtest --ablation no_mdna
#   python -m eval.ablation_report
#
# Nov 11, V6 (#45): V6 runs each company three times and averages (src/consensus.py); --runs N overrides. Every run's
# direction and probability is kept in the results, which also gives the "run 1 only" and "majority vote" arms.
# --set dev runs the 20-company development set (eval/test_set.csv, not blind) to try V6 before the freeze. On set B,
# --ablation <arm> runs one arm of V6's component ablation, blind, once per company (docs/test_plan.md):
#   python -m eval.run_backtest --set dev --prompt V6
#   python -m eval.run_backtest --set b --prompt V6 --ablation no_downward
import functools
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.agent import DEFAULT_PROMPT, investigate
from src.backtest import load_test_set, run_test
from src.consensus import combine
from src.key_pool import pool
from src.run_limiter import waiting_line

TEST_SET_PATH = Path("eval/test_set_200.csv")
RESULTS_PATH = Path("eval/backtest_200_results.jsonl")
RUN_LOG_PATH = Path("eval/backtest_200_runs.jsonl")      # full ReAct traces, one line per company
_write_lock = threading.Lock()


def done_tickers(prompt):
    if not RESULTS_PATH.exists():
        return set()
    with open(RESULTS_PATH, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {r["ticker"] for r in rows if r["prompt"] == prompt and not r.get("error")}


def run_one(row, prompt, ablation=None, runs=1):
    agent = functools.partial(investigate, ablation=ablation) if ablation else investigate
    with waiting_line.slot():
        try:
            if runs == 1:
                res = run_test(row, agent, log_path=RUN_LOG_PATH, prompt=prompt)
                record = {"ticker": row["ticker"], "prompt": prompt, "ablation": ablation,
                          "direction": res["direction"], "probability": res["probability"], "truth": row["truth"],
                          "correct": res["correct"], "seconds": res["seconds"], "usage": res["out"]["usage"],
                          "tools": [s["tool"] for s in res["out"]["steps"]], "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
            else:                                   # V6: the same company several times, then averaged
                each = [run_test(row, agent, log_path=RUN_LOG_PATH, prompt=prompt) for _ in range(runs)]
                combined = combine(each)
                record = {"ticker": row["ticker"], "prompt": prompt, "ablation": ablation, **combined,
                          "truth": row["truth"], "correct": combined["direction"] == row["truth"],
                          "seconds": sum(r["seconds"] for r in each),
                          "runs": [{"direction": r["direction"], "probability": r["probability"],
                                    "correct": r["correct"], "seconds": r["seconds"], "usage": r["out"]["usage"],
                                    "tools": [s["tool"] for s in r["out"]["steps"]]} for r in each],
                          "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        except Exception as error:
            record = {"ticker": row["ticker"], "prompt": prompt, "error": f"{type(error).__name__}: {str(error)[:200]}",
                      "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    with _write_lock:
        with open(RESULTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    return record


def prompt_arg(args):
    return args[args.index("--prompt") + 1] if "--prompt" in args else DEFAULT_PROMPT


def main(args):
    global TEST_SET_PATH, RESULTS_PATH, RUN_LOG_PATH
    pool.patient = True                  # Nov 10: wait out a busy Google instead of failing the company (key_pool.py)
    ablation = args[args.index("--ablation") + 1] if "--ablation" in args else None
    which = args[args.index("--set") + 1].lower() if "--set" in args else "a"
    blind = which == "b"
    if which == "dev":
        TEST_SET_PATH = Path("eval/test_set.csv")
        RESULTS_PATH = Path("eval/dev_results.jsonl")
        RUN_LOG_PATH = Path("eval/dev_runs.jsonl")
        print("Development set (20 companies): for trying prompts before a freeze, not a test.")
    elif which == "c":
        # Nov 11: set C, used once to choose between V6 and V7 (docs/test_plan.md). Blind like set B: progress only;
        # the choice is made by python -m eval.choose_version after both have run.
        blind = True
        TEST_SET_PATH = Path("eval/test_set_200c.csv")
        RESULTS_PATH = Path("eval/setc_results.jsonl")
        RUN_LOG_PATH = Path("eval/setc_runs.jsonl")
        print(f"Set C, blind: progress and errors only. Writing {RESULTS_PATH}.")
    elif blind:
        TEST_SET_PATH = Path("eval/test_set_200b.csv")
        RESULTS_PATH = Path(f"eval/ablation_b_{ablation}_results.jsonl" if ablation else "eval/backtest_200b_results.jsonl")
        RUN_LOG_PATH = Path(f"eval/ablation_b_{ablation}_runs.jsonl" if ablation else "eval/backtest_200b_runs.jsonl")
        print(f"Set B, blind: progress and errors only (docs/test_plan.md). Writing {RESULTS_PATH}.")
    elif prompt_arg(args) != DEFAULT_PROMPT and not ablation:
        # Nov 11: a newer prompt on set A is an exploratory, in-sample check (V6 was designed from V5's set A errors),
        # kept in its own file so it never mixes with the committed V5 results
        tag = prompt_arg(args).lower()
        RESULTS_PATH = Path(f"eval/backtest_200_{tag}_results.jsonl")
        RUN_LOG_PATH = Path(f"eval/backtest_200_{tag}_runs.jsonl")
        print(f"Set A with {prompt_arg(args)}: exploratory, in-sample. Writing {RESULTS_PATH}.")
    elif ablation:
        RESULTS_PATH = Path(f"eval/ablation_{ablation}_results.jsonl")
        RUN_LOG_PATH = Path(f"eval/ablation_{ablation}_runs.jsonl")
        print(f"Ablation {ablation} on set A: {RESULTS_PATH}")
    prompt = args[args.index("--prompt") + 1] if "--prompt" in args else DEFAULT_PROMPT
    # V6 and V7 average three runs; an ablation arm is compared with V6's first run, so it runs once (docs/test_plan.md)
    runs = int(args[args.index("--runs") + 1]) if "--runs" in args else (3 if prompt in ("V6", "V7") and not ablation else 1)
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    rows = load_test_set(TEST_SET_PATH)
    finished = done_tickers(prompt)
    todo = [r for r in rows if r["ticker"] not in finished][:limit]
    print(f"{len(rows)} companies in the test set, {len(finished)} already done with {prompt}, running {len(todo)}. "
          f"{len(pool.keys)} key(s), up to {waiting_line.limit} at a time, {runs} run(s) per company.")
    if not todo:
        return
    started, correct, errors, errors_in_a_row = time.time(), 0, 0, 0
    with ThreadPoolExecutor(max_workers=waiting_line.limit) as executor:
        futures = [executor.submit(run_one, row, prompt, ablation, runs) for row in todo]
        for i, future in enumerate(as_completed(futures), start=1):
            r = future.result()
            if r.get("error"):
                errors += 1
                errors_in_a_row += 1
                line = f"ERROR {r['error']}"
            else:
                errors_in_a_row = 0
                correct += r["correct"]
                line = "done" if blind else \
                    f"{r['direction'] or 'no answer':<9} p={r['probability']}  truth={r['truth']:<9} " \
                    f"{'correct' if r['correct'] else 'wrong'}"
            minutes = (time.time() - started) / 60
            print(f"[{i}/{len(todo)}, {minutes:.0f} min] {r['ticker']:<6} {line}")
            if errors_in_a_row >= 5:
                print("\nFive errors in a row (daily quota used up, or Gemini/EDGAR down). Stopping after the runs in "
                      "progress; run again later and it continues where it stopped.")
                for f in futures:
                    f.cancel()
                break
    done = i - errors
    if blind:
        print(f"\nThis run: {done} finished, {errors} errors (run again to retry them). Accuracy is looked at only "
              "at the two stages in docs/test_plan.md.")
        return
    print(f"\nThis run: {correct} of {done} correct, {errors} errors (run again to retry them). "
          + (f"Report: python -m eval.dev_check --prompt {prompt}" if which == "dev" else
             f"Report: python -m eval.ablation_report --ablation {ablation}" if ablation else
             f"Report: python -m eval.analyze_backtest" + (f" --prompt {prompt}" if prompt != DEFAULT_PROMPT else "")))


if __name__ == "__main__":
    main(sys.argv[1:])
