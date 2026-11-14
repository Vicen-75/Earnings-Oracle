# --- Javier: build set D and run V6 on it with one command, unattended (code written with help from Claude) ---
# Plan: docs/test_plan.md, Nov 13 note. Two steps, in this order:
#   1. the set   Walk the universe from position 652 through the same data and contamination gates as sets A, B and C
#                until 400 companies pass (python -m eval.build_test_set check --set d).
#   2. the runs  V6, one run per company, on all 400 (python -m eval.run_backtest --set d --prompt V6 --runs 1).
# Each step is repeated until it is complete: a quota stop or a Google outage just means a wait and a retry (the daily
# limits reset at midnight Pacific). Step 2 starts only when the list of 400 is final. It is blind like the runner: it
# prints progress and counts, never correct or wrong, and computes no accuracy. The one look at accuracy is
# python -m eval.analyze_set_d, after all 400 are done.
#
# V6 is the frozen V6 of set B: before every step, the files under src/ listed in eval/v6_frozen_manifest.txt are
# compared with the hashes recorded there, and the script stops if any of them changed.
# The plan comes first: the script will not start until docs/test_plan.md has the set D note and it, the runner, the
# set builder and the analysis script are committed.
# The computer is kept awake while it runs (Windows).
#
#   python -m eval.run_set_d              # everything, as long as it takes
#   python -m eval.run_set_d --status     # what is done so far; nothing is run and nothing is written
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

SIZE = 400
CHECKS = Path("eval/sample_checks_d.csv")
SET_D = Path("eval/test_set_400d.csv")
RESULTS = Path("eval/setd_results.jsonl")
MANIFEST = Path("eval/v6_frozen_manifest.txt")
PLAN = Path("docs/test_plan.md")
PLAN_MARK = "set D, 400 fresh companies"                  # in the heading of the Nov 13 note
LOG = Path("eval/set_d_run.log")
MUST_BE_COMMITTED = [PLAN, Path("eval/build_test_set.py"), Path("eval/run_backtest.py"), Path("eval/run_set_d.py"),
                     Path("eval/analyze_set_d.py")]
WAIT_AFTER_PROGRESS = 5 * 60         # seconds: a step stopped early but got some companies done
WAIT_NO_PROGRESS = [10, 20, 30, 30]  # minutes: nothing got done (quota used up); then every 30 minutes


def log(text):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_changes():
    """Files under src/ in the V6 freeze manifest whose bytes no longer match it (or that are missing)."""
    changed = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            recorded, name = line.strip().split("  ", 1)
            if name.startswith("src/") and (not Path(name).exists() or sha(Path(name)) != recorded):
                changed.append(name)
    return changed


def check_freeze():
    changed = frozen_changes()
    if changed:
        log(f"STOP: V6 files differ from eval/v6_frozen_manifest.txt: {', '.join(changed)}")
        sys.exit(1)


def plan_problem():
    """Why the run may not start yet, or None. The plan and the code that carries it out are committed first."""
    if not PLAN.exists() or PLAN_MARK not in PLAN.read_text(encoding="utf-8"):
        return f"{PLAN} has no set D note yet."
    missing = [str(p) for p in MUST_BE_COMMITTED if not p.exists()]
    if missing:
        return "missing: " + ", ".join(missing)
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", *map(str, MUST_BE_COMMITTED)],
                             capture_output=True, text=True)
    except OSError:
        return "git was not found, so the commit of the plan cannot be checked."
    if out.returncode != 0:
        return f"git status failed: {out.stderr.strip()[:200]}"
    if out.stdout.strip():
        return "commit these before the first run (the commit is the record that the plan came first):\n" + out.stdout.rstrip()
    return None


def set_state():
    """(companies tried, accepted, errors still to retry, True when the list of 400 is final)."""
    if not CHECKS.exists():
        return 0, 0, 0, False
    with open(CHECKS, newline="", encoding="utf-8") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: int(r["order"]))
    accepted = [r for r in rows if r["status"] == "ACCEPTED"]
    errors = [r for r in rows if r["status"].startswith("ERROR")]
    tried = sum(not r["status"].startswith("ERROR") and r["status"] != "SKIPPED_OTHER_SET" for r in rows)
    if len(accepted) < SIZE:
        return tried, len(accepted), len(errors), False
    last = int(accepted[SIZE - 1]["order"])
    waiting = [r for r in errors if int(r["order"]) < last]         # a retry that passes would take a place by order
    listed = len(tickers())
    return tried, SIZE, len(waiting), not waiting and listed == SIZE


def tickers():
    if not SET_D.exists():
        return []
    with open(SET_D, newline="", encoding="utf-8") as f:
        return [r["ticker"] for r in csv.DictReader(f)]


def runs_done():
    """Companies of set D with a finished (non-error) V6 result."""
    if not RESULTS.exists():
        return 0
    done = set()
    with open(RESULTS, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r.get("prompt") == "V6" and not r.get("error"):
                    done.add(r["ticker"])
    return sum(t in done for t in tickers())


def keep_awake(on):
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def status(write=print):
    tried, accepted, errors, final = set_state()
    write(f"Step 1, the set:  {accepted}/{SIZE} companies accepted, {tried} tried, {errors} error(s) to retry"
          + (", list final." if final else "."))
    write(f"Step 2, the runs: {runs_done() if final else 0}/{SIZE} companies done with V6"
          + ("." if final else " (starts when the list is final)."))


def repeat(label, command, progress, complete, describe):
    misses = 0
    while not complete():
        check_freeze()
        before = progress()
        log(f"{label}: {describe()}, starting.")
        code = subprocess.call([sys.executable, "-m", *command])
        log(f"{label}: stopped (exit {code}); now {describe()}.")
        if complete():
            break
        if progress() > before:
            misses = 0
            time.sleep(WAIT_AFTER_PROGRESS)
        else:
            minutes = WAIT_NO_PROGRESS[min(misses, len(WAIT_NO_PROGRESS) - 1)]
            misses += 1
            log(f"{label}: no progress (quota used up, or Google or EDGAR down); waiting {minutes} minutes.")
            time.sleep(minutes * 60)
    log(f"{label}: complete ({describe()}).")


def main(argv):
    if "--status" in argv:
        status()
        return
    problem = plan_problem()
    if problem:
        sys.exit(f"Not started. {problem}")
    log("=== Set D, unattended: the 400 companies, then V6 with one run on each ===")
    check_freeze()
    keep_awake(True)
    try:
        repeat("Step 1, the set", ["eval.build_test_set", "check", "--set", "d"],
               progress=lambda: set_state()[0] + set_state()[1], complete=lambda: set_state()[3],
               describe=lambda: "{1}/{size} accepted, {0} tried, {2} error(s) to retry".format(*set_state(), size=SIZE))
        log(f"The list is final: {SET_D}, sha256 {sha(SET_D)}.")
        repeat("Step 2, the runs", ["eval.run_backtest", "--set", "d", "--prompt", "V6", "--runs", "1"],
               progress=runs_done, complete=lambda: runs_done() >= SIZE,
               describe=lambda: f"{runs_done()}/{SIZE} done")
    finally:
        keep_awake(False)
    log("=== Set D is done. Nothing has been scored. The one look at accuracy: python -m eval.analyze_set_d ===")
    status(log)


if __name__ == "__main__":
    main(sys.argv[1:])
