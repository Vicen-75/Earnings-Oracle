# --- Javier: run everything on set B with one command, unattended (code written with help from Claude) ---
# Plan: docs/test_plan.md, Nov 12 note. Runs, in the pre-registered order:
#   1. V6 stage 1   (first 100 companies of set B, three runs each)
#   2. V6 stage 2   (the other 100)
#   3. V5           (all 200, one run each; the secondary test)
#   4. ablation arms: no_downward, no_oneoff, no_structured (all 200, one run each)
# Each step is repeated until every company is done: a quota stop or a Google outage just means a wait and a retry
# (the daily limits reset at midnight Pacific). It is blind like the runner: it prints progress and counts, never
# correct or wrong, and computes no accuracy.
#
# The freeze: before the first run it writes the SHA-256 of every file V6 depends on to eval/v6_frozen_manifest.txt.
# Before every step it checks them again and stops if anything changed. The commit tagged v6-frozen must match it.
# The computer is kept awake while it runs (Windows).
#
#   python -m eval.run_set_b              # everything, as long as it takes
#   python -m eval.run_set_b --status     # what is done so far, nothing is run
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

SET_B = Path("eval/test_set_200b.csv")
MAIN_RESULTS = Path("eval/backtest_200b_results.jsonl")
MANIFEST = Path("eval/v6_frozen_manifest.txt")
LOG = Path("eval/set_b_overnight.log")
FROZEN = sorted(Path("src").glob("*.py")) + [Path("eval/run_backtest.py"), Path("eval/run_set_b.py"), SET_B,
                                               Path("docs/test_plan.md")]
STEPS = [  # (label, runner arguments, results file, prompt, how many companies from the top of set B)
    ("V6 stage 1", ["--set", "b", "--prompt", "V6", "--limit", "100"], MAIN_RESULTS, "V6", 100),
    ("V6 stage 2", ["--set", "b", "--prompt", "V6"], MAIN_RESULTS, "V6", 200),
    ("V5", ["--set", "b", "--prompt", "V5"], MAIN_RESULTS, "V5", 200),
    ("arm no_downward", ["--set", "b", "--prompt", "V6", "--ablation", "no_downward"],
     Path("eval/ablation_b_no_downward_results.jsonl"), "V6", 200),
    ("arm no_oneoff", ["--set", "b", "--prompt", "V6", "--ablation", "no_oneoff"],
     Path("eval/ablation_b_no_oneoff_results.jsonl"), "V6", 200),
    ("arm no_structured", ["--set", "b", "--prompt", "V6", "--ablation", "no_structured"],
     Path("eval/ablation_b_no_structured_results.jsonl"), "V6", 200),
]
WAIT_AFTER_PROGRESS = 5 * 60        # seconds: a run stopped early but got some companies done
WAIT_NO_PROGRESS = [10, 20, 30, 30]  # minutes: nothing got done (quota used up); then every 30 minutes


def log(text):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_freeze():
    """Write the manifest the first time; afterwards, stop if any frozen file changed."""
    current = {str(p).replace("\\", "/"): sha(p) for p in FROZEN}
    if not MANIFEST.exists():
        lines = [f"# V6 frozen for set B, written {time.strftime('%Y-%m-%d %H:%M:%S %Z')} before the first set B run",
                 "# The commit tagged v6-frozen must have these exact files (sha256).", ""]
        lines += [f"{h}  {name}" for name, h in sorted(current.items())]
        MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(f"Freeze recorded: {MANIFEST} ({len(current)} files).")
        return
    recorded = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            h, name = line.split("  ", 1)
            recorded[name] = h
    changed = sorted(n for n in set(recorded) | set(current) if recorded.get(n) != current.get(n))
    if changed:
        log(f"STOP: frozen files changed since the manifest was written: {', '.join(changed)}")
        sys.exit(1)


def done_count(results, prompt, top):
    """Companies among the first `top` of set B with a finished (non-error) result for this prompt."""
    tickers = [r["ticker"] for r in csv.DictReader(open(SET_B, encoding="utf-8"))][:top]
    if not results.exists():
        return 0, len(tickers)
    done = set()
    with open(results, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r.get("prompt") == prompt and not r.get("error"):
                    done.add(r["ticker"])
    return sum(t in done for t in tickers), len(tickers)


def keep_awake(on):
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def status():
    for label, _, results, prompt, top in STEPS:
        n, total = done_count(results, prompt, top)
        log(f"{label:<18} {n}/{total} companies done")


def run_step(label, args, results, prompt, top):
    misses = 0
    while True:
        before, total = done_count(results, prompt, top)
        if before >= total:
            log(f"{label}: complete ({total}/{total}).")
            return
        check_freeze()
        log(f"{label}: {before}/{total} done, starting the runner.")
        code = subprocess.call([sys.executable, "-m", "eval.run_backtest", *args])
        after, _ = done_count(results, prompt, top)
        log(f"{label}: runner exited ({code}); now {after}/{total}.")
        if after >= total:
            continue
        if after > before:
            misses = 0
            time.sleep(WAIT_AFTER_PROGRESS)
        else:
            minutes = WAIT_NO_PROGRESS[min(misses, len(WAIT_NO_PROGRESS) - 1)]
            misses += 1
            log(f"{label}: no progress (quota used up or Google down); waiting {minutes} minutes.")
            time.sleep(minutes * 60)


def main(argv):
    if "--status" in argv:
        status()
        return
    log("=== Set B, unattended run: V6 stage 1, V6 stage 2, V5, three ablation arms ===")
    check_freeze()
    keep_awake(True)
    try:
        for step in STEPS:
            run_step(*step)
    finally:
        keep_awake(False)
    log("=== Everything on set B is done. Nothing has been scored; accuracy is looked at only at the two stages. ===")
    status()


if __name__ == "__main__":
    main(sys.argv[1:])
