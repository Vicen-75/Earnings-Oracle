# --- Javier, Nov 25: five runs per company per version, PROJECT_DIRECTIVES §5.5 element 4 (code written with help
# from Claude) ---
# Plan: docs/test_plan.md, Nov 25 note. 20 companies of set B (the first 20 in file order, skipping tickers that end
# in Q), V5 and V6, five fresh runs each, in rounds: round r runs every company once with V5 and once with V6 before
# round r + 1 starts. Backtest mode (the target year's 10-K is hidden), exactly as run_backtest.py does it.
#
# It picks up where it stopped: a run counts once it has a finished result in eval/five_runs_results.jsonl; failed
# runs (an outage, a quota stop) are written with an "error" field and run again on the next pass. A pass stops early
# after several failures in a row with nothing finished, so the overnight wrapper (eval/run_remaining.py) can wait
# and come back. It prints progress only, never correct or wrong; the numbers come from eval/analyze_five_runs.py.
#
#   python -m eval.five_runs                    one pass over whatever is missing
#   python -m eval.five_runs --until <epoch>    no new run starts after that time (the wrapper passes its deadline)
#   python -m eval.five_runs --status           counts only; nothing is run
import argparse
import csv
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

SET_B = Path("eval/test_set_200b.csv")
RESULTS = Path("eval/five_runs_results.jsonl")
RUN_LOG = Path("eval/five_runs_runs.jsonl")
PLAN = Path("docs/test_plan.md")
PLAN_MARK = "five runs per company per version"
VERSIONS = ("V5", "V6")
ROUNDS = 5
SIZE = 20
STOP_AFTER_FAILURES = 6           # failures in a row with nothing finished: end this pass, the wrapper waits
RELEASE = "presentation"          # src/ must match the code of this tag
MUST_BE_COMMITTED = [PLAN, Path("eval/five_runs.py"), Path("eval/analyze_five_runs.py"),
                     Path("eval/run_remaining.py")]

_lock = threading.Lock()


def companies():
    """The 20 of the plan: set B in file order, tickers ending in Q skipped."""
    with open(SET_B, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if not r["ticker"].upper().endswith("Q")]
    return rows[:SIZE]


def finished():
    """{(ticker, version): number of finished runs}. A run with an error field is not finished."""
    counts = {}
    if RESULTS.exists():
        with open(RESULTS, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if not r.get("error"):
                        key = (r["ticker"], r["prompt"])
                        counts[key] = counts.get(key, 0) + 1
    return counts


def missing_runs():
    done = finished()
    return sum(max(0, ROUNDS - done.get((c["ticker"], v), 0)) for c in companies() for v in VERSIONS)


def plan_problem():
    """Why the run may not start, or None: the plan and this code committed, and src/ as in the release."""
    if not PLAN.exists() or PLAN_MARK not in PLAN.read_text(encoding="utf-8"):
        return f"{PLAN} has no Nov 25 note."
    status = subprocess.run(["git", "status", "--porcelain", "--", *map(str, MUST_BE_COMMITTED)],
                            capture_output=True, text=True)
    if status.returncode != 0 or status.stdout.strip():
        return "commit these first:\n" + (status.stdout or status.stderr).rstrip()
    src = subprocess.run(["git", "diff", "--quiet", RELEASE, "--", "src/"])
    if src.returncode != 0:
        return f"src/ differs from the {RELEASE} release; these runs must use the released code."
    return None


def run_one(row, version, round_no):
    from src.agent import investigate
    from src.backtest import run_test
    try:
        res = run_test(row, investigate, log_path=RUN_LOG, prompt=version)
        record = {"ticker": row["ticker"], "prompt": version, "round": round_no, "direction": res["direction"],
                  "probability": res["probability"], "truth": row["truth"], "correct": res["correct"],
                  "seconds": res["seconds"], "usage": res["out"]["usage"],
                  "tools": [s["tool"] for s in res["out"]["steps"]], "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    except Exception as error:
        record = {"ticker": row["ticker"], "prompt": version, "round": round_no,
                  "error": f"{type(error).__name__}: {str(error)[:200]}", "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    with _lock:
        with open(RESULTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    return record


def one_pass(until=None):
    """Runs what is missing, round by round. Returns 0 when all are done, 2 when stopped early."""
    from src.key_pool import pool
    from src.run_limiter import waiting_line
    pool.patient = True                       # wait out a busy Google for up to 15 minutes per call, as backtests do
    rows = companies()
    for round_no in range(1, ROUNDS + 1):
        done = finished()
        jobs = [(row, v) for row in rows for v in VERSIONS if done.get((row["ticker"], v), 0) < round_no]
        if not jobs:
            continue
        print(f"Round {round_no}: {len(jobs)} run(s) to do, up to {waiting_line.limit} at a time.", flush=True)
        failures, stop = 0, False
        queue = list(jobs)
        with ThreadPoolExecutor(max_workers=waiting_line.limit) as executor:
            running = set()
            while queue or running:
                while queue and not stop and len(running) < waiting_line.limit:      # a few at a time, in order
                    if until and time.time() >= until:
                        print("Time limit reached: no new runs.", flush=True)
                        stop = True
                        break
                    row, v = queue.pop(0)
                    running.add(executor.submit(_slot, waiting_line, row, v, round_no, until))
                if not running:
                    break
                done_now, running = wait(running, return_when=FIRST_COMPLETED)
                for future in done_now:
                    record = future.result()
                    if record is None:
                        continue
                    if record.get("error"):
                        failures += 1
                        print(f"   {record['ticker']} {record['prompt']}: failed ({record['error'][:80]})", flush=True)
                        if failures >= STOP_AFTER_FAILURES:
                            stop = True                    # no new runs; the ones already running finish
                    else:
                        failures = 0
                        print(f"   {record['ticker']} {record['prompt']}: done ({record['seconds']} s)", flush=True)
        if stop or missing_for_round(rows, round_no):
            print(f"Pass stopped in round {round_no}; {missing_runs()} run(s) still missing.", flush=True)
            return 2
    return 0


def _slot(waiting_line, row, version, round_no, until):
    with waiting_line.slot():
        if until and time.time() >= until:
            return None
        return run_one(row, version, round_no)


def missing_for_round(rows, round_no):
    done = finished()
    return any(done.get((r["ticker"], v), 0) < round_no for r in rows for v in VERSIONS)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--until", type=float, help="epoch seconds after which no new run starts")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-guard", action="store_true", help=argparse.SUPPRESS)      # stub tests only
    args = parser.parse_args(argv)
    total = SIZE * len(VERSIONS) * ROUNDS
    if args.status:
        print(f"{total - missing_runs()}/{total} runs finished.")
        return 0
    problem = None if args.no_guard else plan_problem()
    if problem:
        sys.exit(f"Not started. {problem}")
    print(f"Five runs: {total - missing_runs()}/{total} finished before this pass.", flush=True)
    code = one_pass(args.until)
    print(f"Five runs: {total - missing_runs()}/{total} finished after this pass.", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
