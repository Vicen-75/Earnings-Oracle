# --- Javier: load test for the key pool, before the fresh-set runs (code written with help from Claude) ---
# Can the keys carry real analyses at the same time? eval/check_keys.py makes one tiny call per key, one key at a time,
# which proves a key is valid but not that it survives a full analysis (about 5 calls of up to 120k input tokens each)
# while every other key is busy too. This runs N real analyses at once and records, per key, what Google allowed.
#
# The analyses are V5 in backtest mode on the 20-company development set (eval/test_set.csv), so they are not wasted:
# eval/load_test_runs.jsonl doubles as the V5 development baseline for V6.
#
# Run from the repository root (keys from .streamlit/secrets.toml, as for eval/run_backtest.py):
#   python -m eval.check_keys                  # first: which keys work at all
#   python -m eval.load_test                   # one analysis per ACTIVE key (4 by default), all at once
#   python -m eval.load_test --runs 6          # a chosen number at once (Nov 9: 6 passed, 12 failed twice)
#   python -m eval.load_test --app             # the app's shorter patience instead of the batch runs' longer one
#
# Writes eval/load_test_report.md (overwritten each time) and appends every finished analysis to
# eval/load_test_runs.jsonl. About 5.5 model calls and ~100k input tokens per analysis.
import json
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src import key_pool as kp
from src.agent import DEFAULT_PROMPT, investigate
from src.backtest import load_test_set, run_test
from src.key_pool import pool

DEV_SET_PATH = Path("eval/test_set.csv")
RUNS_PATH = Path("eval/load_test_runs.jsonl")
REPORT_PATH = Path("eval/load_test_report.md")
SAMPLE_SECONDS = 5

events = []                                     # (seconds since start, key label, what happened, detail)
_events_lock = threading.Lock()
_write_lock = threading.Lock()
T0 = time.time()


def _event(key, kind, detail=""):
    with _events_lock:
        events.append((round(time.time() - T0, 1), key, kind, detail))


# --- listen to the pool without changing what it does -------------------------------------------------------------
_original_report, _original_rest, _original_move, _original_wait = kp._report_limit, pool._rest, pool._move, pool._wait
_original_retire = pool._retire


def _report_limit(key, error):
    names = re.findall(r"quota(?:_?[Ii]d|Metric)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_./-]+)", str(error))
    _event(key.label, "limit", names[0] if names else str(error)[:120].replace("\n", " "))
    _original_report(key, error)


def _rest(key):
    _event(key.label, "rest")
    _original_rest(key)


def _move(old):
    new = _original_move(old)
    _event(old.label, "moved run", f"to {new.label}")
    return new


def _wait(on_event=None, reason="rate_limit", seconds=None):
    _event("all keys" if reason != "overloaded" else "busy", "wait", f"{reason} {seconds or kp.WAIT_SECONDS}s")
    _original_wait(on_event, reason, seconds)


def _retire(key):
    _event(key.label, "retired", "daily quota used up")
    _original_retire(key)


kp._report_limit, pool._rest, pool._move, pool._wait, pool._retire = _report_limit, _rest, _move, _wait, _retire


def sampler(stop, peaks):
    """Every few seconds, the highest calls and tokens per minute each key reached."""
    while not stop.is_set():
        for s in pool.status():
            p = peaks[s["key"]]
            p["calls"] = max(p["calls"], s["calls_last_minute"])
            p["tokens"] = max(p["tokens"], s["tokens_last_minute"])
            p["running"] = max(p["running"], s["running"])
        stop.wait(SAMPLE_SECONDS)


def run_one(row, prompt):
    started = time.time()
    try:
        res = run_test(row, investigate, prompt=prompt, log_path=RUNS_PATH.with_suffix(".trace.jsonl"))
        record = {"ticker": row["ticker"], "prompt": prompt, "direction": res["direction"],
                  "probability": res["probability"], "truth": row["truth"], "correct": res["correct"],
                  "seconds": round(time.time() - started), "usage": res["out"]["usage"],
                  "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    except Exception as error:
        record = {"ticker": row["ticker"], "prompt": prompt, "error": f"{type(error).__name__}: {str(error)[:200]}",
                  "seconds": round(time.time() - started), "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    with _write_lock:
        with open(RUNS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    return record


def main(args):
    n = int(args[args.index("--runs") + 1]) if "--runs" in args else pool.capacity()
    pool.patient = "--app" not in args
    prompt = args[args.index("--prompt") + 1] if "--prompt" in args else DEFAULT_PROMPT
    rows = load_test_set(DEV_SET_PATH)
    rows = (rows * (n // len(rows) + 1))[:n]                  # more runs than companies repeats the list
    print(f"{len(pool.keys)} key(s), active: {', '.join(k.label for k in pool.active_keys())}; starting {n} analyses "
          f"at once ({prompt}, development set, backtest mode, {'batch' if pool.patient else 'app'} patience).")
    peaks = defaultdict(lambda: {"calls": 0, "tokens": 0, "running": 0})
    stop = threading.Event()
    threading.Thread(target=sampler, args=(stop, peaks), daemon=True).start()
    results = []
    with ThreadPoolExecutor(max_workers=n) as executor:
        for future in as_completed([executor.submit(run_one, r, prompt) for r in rows]):
            r = future.result()
            results.append(r)
            status = r.get("error") or f"{r['direction'] or 'no answer'} ({'correct' if r['correct'] else 'wrong'})"
            print(f"[{len(results)}/{n}, {time.time() - T0:.0f}s] {r['ticker']:<6} {r['seconds']:>4}s  {status}")
    stop.set()
    write_report(n, prompt, results, peaks)


def write_report(n, prompt, results, peaks):
    ok = [r for r in results if not r.get("error")]
    limits = Counter((k, d) for _, k, kind, d in events if kind == "limit")
    per_key = defaultdict(Counter)
    for _, k, kind, _ in events:
        per_key[k][kind] += 1
    daily = sum(c for (k, d), c in limits.items() if "PerDay" in d)
    total = time.time() - T0
    out = [f"# Load test, {time.strftime('%Y-%m-%d %H:%M')}", "",
           f"{n} analyses started at once on {len(pool.keys)} key(s), prompt {prompt}, development set. "
           f"{len(ok)} finished, {n - len(ok)} failed, in {total / 60:.1f} minutes "
           f"(median analysis {sorted(r['seconds'] for r in results)[len(results) // 2]} s).", "",
           f"Pool settings: {pool.active_size} keys active at a time (rolling replacement); "
           f"{kp.REQUESTS_PER_MINUTE} requests and {kp.TOKENS_PER_MINUTE:,} tokens per minute assumed per key; a key "
           f"with a named limit rests {kp.REST_SECONDS} s; a busy Google is waited out for up to "
           f"{(kp.PATIENT_SECONDS if pool.patient else kp.APP_BUSY_SECONDS) // 60} min.", "",
           "Active at the end: " + ", ".join(k.label for k in pool.active_keys())
           + ". Retired today (daily quota): " + (", ".join(k.label for k in pool.keys if k.retired()) or "none") + ".", "",
           "| Key | Most analyses at once | Peak calls / min | Peak tokens / min | Limits hit | Rests | Runs moved away |",
           "|---|---|---|---|---|---|---|"]
    for key in pool.keys:
        p, e = peaks[key.label], per_key[key.label]
        out.append(f"| {key.label} | {p['running']} | {p['calls']} | {p['tokens']:,} | {e['limit']} | {e['rest']} | "
                   f"{e['moved run']} |")
    out += ["", f"Times every key was resting at once (the run had to wait): {per_key['all keys']['wait']}. "
            f"Waits for a busy Google (503 or unnamed 429, run kept its key): {per_key['busy']['wait']}.", ""]
    if limits:
        out += ["## Limits Google reported", "", "| Key | Quota | Times |", "|---|---|---|"]
        out += [f"| {k} | {d} | {c} |" for (k, d), c in sorted(limits.items())]
        out.append("")
    failed = [r for r in results if r.get("error")]
    if failed:
        out += ["## Failed analyses", ""] + [f"- {r['ticker']}: {r['error']}" for r in failed] + [""]
    clean = not limits and not failed
    limited = sorted({k for (k, _) in limits}, key=lambda k: int(k.split()[-1]) if k[-1].isdigit() else 0)
    alone = [k for k in limited if peaks[k]["running"] <= 1]
    stacked = [k.label for k in pool.keys if peaks[k.label]["running"] > 1]
    if clean:
        verdict = f"All {n} analyses ran at once with no rate limit: the keys can carry {n} at a time."
    elif daily:
        verdict = "Daily quota reached on some keys: wait for the reset (midnight Pacific) or add keys."
    else:
        verdict = (f"Rate limits on {len(limited)} of {len(pool.keys)} keys ({', '.join(limited)}). "
                   + (f"{', '.join(alone)} hit a limit while carrying a single analysis: one full analysis is "
                      "already too much for that key's minute, so the fix is fewer tokens per analysis (send the "
                      "MD&A once), not more keys. " if alone else "")
                   + ("Every limited key was carrying more than one analysis at the time: more keys, or fewer "
                      "analyses at once, would fix it. " if limited and not alone else ""))
    if stacked:
        verdict = verdict.rstrip() + (f" Keys that carried more than one analysis at some point: {', '.join(stacked)}. The pool moves a "
                    "run away from a key it counts as full, so runs can pile up on other keys.")
    out += ["## Verdict", "", verdict, ""]
    out += ["Every event, in order (seconds from start):", "", "```"]
    out += [f"{t:>7}  {k:<9} {kind:<10} {d}" for t, k, kind, d in events] or ["(none)"]
    out.append("```")
    REPORT_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}.")


if __name__ == "__main__":
    main(sys.argv[1:])
