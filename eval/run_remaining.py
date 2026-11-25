# --- Javier, Nov 25: the remaining evaluation runs, unattended (code written with help from Claude) ---
# Plan: docs/test_plan.md, Nov 25 note, and eval/awkward_inputs.csv. Two steps, repeated until both are complete or
# the time limit (12 hours from the start, as the plan says) is reached:
#   1. awkward inputs  every row of eval/awkward_inputs.csv without a PASS or FAIL yet (python -m eval.awkward_inputs
#                      --only ...). The app's own patience is not changed: a row stopped by an outage is NOT RUN and
#                      is tried again on the next pass; every attempt stays in eval/awkward_inputs_runs.jsonl.
#   2. five runs       python -m eval.five_runs --until <deadline>
# Between passes it waits 5 minutes after progress and 20 minutes after none (Google busy, or quota used up). At the
# end it writes eval/five_runs_report.md (python -m eval.analyze_five_runs), whatever was finished by then.
# The computer is kept awake while it runs (Windows). Everything it does goes to eval/remaining_run.log.
#
#   python -m eval.run_remaining              everything, for up to 12 hours
#   python -m eval.run_remaining --status     what is done; nothing is run
import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

from eval.five_runs import ROUNDS, SIZE, VERSIONS, missing_runs, plan_problem

HOURS = 12
AWKWARD = Path("eval/awkward_inputs.csv")
AWKWARD_RESULTS = Path("eval/awkward_inputs_results.csv")
LOG = Path("eval/remaining_run.log")
WAIT_AFTER_PROGRESS = 5 * 60
WAIT_NO_PROGRESS = 20 * 60


def log(text):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def awkward_pending():
    """Rows of the expected-results file with no PASS or FAIL yet."""
    with open(AWKWARD, newline="", encoding="utf-8") as f:
        ids = [r["id"] for r in csv.DictReader(f)]
    verdict = {}
    if AWKWARD_RESULTS.exists():
        with open(AWKWARD_RESULTS, newline="", encoding="utf-8") as f:
            verdict = {r["id"]: r["verdict"] for r in csv.DictReader(f)}
    return [i for i in ids if verdict.get(i) not in ("PASS", "FAIL")]


def keep_awake(on):
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def describe():
    total = SIZE * len(VERSIONS) * ROUNDS
    pending = awkward_pending()
    return (f"awkward inputs: {len(pending)} row(s) without a verdict{' (' + ', '.join(pending) + ')' if pending else ''}; "
            f"five runs: {total - missing_runs()}/{total} finished")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--hours", type=float, default=HOURS, help=argparse.SUPPRESS)       # stub tests only
    parser.add_argument("--no-guard", action="store_true", help=argparse.SUPPRESS)          # stub tests only
    args = parser.parse_args(argv)
    if args.status:
        print(describe())
        return
    problem = None if args.no_guard else plan_problem()
    if problem:
        sys.exit(f"Not started. {problem}")
    deadline = time.time() + args.hours * 3600
    log(f"=== Remaining runs, unattended, until {time.strftime('%Y-%m-%d %H:%M', time.localtime(deadline))} ===")
    log(describe())
    keep_awake(True)
    try:
        while True:
            before = (len(awkward_pending()), missing_runs())
            pending = awkward_pending()
            if pending:
                log(f"Awkward inputs: running {', '.join(pending)}.")
                subprocess.call([sys.executable, "-m", "eval.awkward_inputs", "--only", ",".join(pending)])
            if missing_runs() and time.time() < deadline:
                log("Five runs: starting a pass.")
                extra = ["--no-guard"] if args.no_guard else []
                subprocess.call([sys.executable, "-m", "eval.five_runs", "--until", str(deadline), *extra])
            log(describe())
            if not awkward_pending() and not missing_runs():
                log("Everything is done.")
                break
            if time.time() >= deadline:
                log("Time limit reached.")
                break
            progressed = len(awkward_pending()) < before[0] or missing_runs() < before[1]
            wait = WAIT_AFTER_PROGRESS if progressed else WAIT_NO_PROGRESS
            wait = max(0, min(wait, deadline - time.time()))
            log(f"Waiting {wait / 60:.0f} minutes ({'progress' if progressed else 'no progress: Google busy or quota used up'}).")
            time.sleep(wait)
    finally:
        keep_awake(False)
    subprocess.call([sys.executable, "-m", "eval.analyze_five_runs"])
    log("=== Done. Reports: eval/awkward_inputs_report.md and eval/five_runs_report.md ===")
    log(describe())


if __name__ == "__main__":
    main()
