# --- Javier: the development-set check before freezing V6 (issue #45; code written with help from Claude) ---
# After `python -m eval.run_backtest --set dev --prompt V6`, this prints what #45 says to watch on the 20 development
# companies: how many decrease calls, whether each names a concrete driver (printed for reading by hand), whether any
# "strongest evidence against" is "none", how often the three runs disagree, and whether the model uses
# read_mdna_items. 20 companies are too few to judge accuracy; the accuracy line is there only to catch a model that
# calls decrease everywhere. The development set may be looked at freely; set B may not (docs/test_plan.md).
#
#   python -m eval.dev_check                 # V6
#   python -m eval.dev_check --prompt V5     # the same view of another prompt, if it was run on the dev set
import json
import re
import sys
from pathlib import Path
from statistics import median

RESULTS = Path("eval/dev_results.jsonl")
RUNS = Path("eval/dev_runs.jsonl")


def _load(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _section(answer, name):
    """The text after a heading such as 'Strongest evidence against', up to the next heading."""
    m = re.search(rf"{name}[^\n:]*:?\s*(.+?)(?:\n\s*\n|\n(?:\*\*)?[A-Z][A-Za-z ,]+:|\Z)", answer or "", re.S | re.I)
    return m.group(1).strip() if m else ""


def main(args):
    prompt = args[args.index("--prompt") + 1] if "--prompt" in args else "V6"
    rows = [r for r in _load(RESULTS) if r.get("prompt") == prompt and not r.get("error") and not r.get("ablation")]
    rows = list({r["ticker"]: r for r in rows}.values())                    # the latest result per company
    traces = [t for t in _load(RUNS) if t.get("prompt") == prompt and not t.get("ablation")]
    if not rows:
        print(f"No {prompt} results in {RESULTS}. Run: python -m eval.run_backtest --set dev --prompt {prompt}")
        return
    n = len(rows)
    print(f"Development set, prompt {prompt}: {n} companies, {len(traces)} runs logged\n")

    calls = [r["direction"] for r in rows]
    dec = [r for r in rows if r["direction"] == "decrease"]
    print(f"Calls: {calls.count('increase')} increase, {len(dec)} decrease, {calls.count(None)} no answer")
    print(f"Decrease calls right: {sum(r['correct'] for r in dec)} of {len(dec)}")
    print(f"Correct: {sum(r['correct'] for r in rows)} of {n} (too few to judge accuracy; a check, not a score)")
    if any("runs" in r for r in rows):
        split = [r for r in rows if len({x["direction"] for x in r["runs"]}) > 1]
        avg_vs_vote = [r for r in rows if r.get("majority_direction") and r["majority_direction"] != r["direction"]]
        print(f"Runs disagree on the direction: {len(split)} of {n} companies"
              + (f" ({', '.join(r['ticker'] for r in split)})" if split else ""))
        print(f"Averaged call differs from the majority vote: {len(avg_vs_vote)}")
        spread = [max(x["probability"] or 0 for x in r["runs"]) - min(x["probability"] or 0 for x in r["runs"])
                  for r in rows if all(x["probability"] is not None for x in r["runs"])]
        if spread:
            print(f"Probability spread across a company's runs: median {median(spread):.2f}, max {max(spread):.2f}")

    against_none = [t for t in traces
                    if re.match(r"^(none|n/a|nothing)\b", _section(t["answer"], "Strongest evidence against").lower())]
    print(f"\n'Strongest evidence against' is none: {len(against_none)} of {len(traces)} runs"
          + (f" ({', '.join(t['ticker'] for t in against_none)})" if against_none else ""))
    used = [t for t in traces if any(s["tool"] == "read_mdna_items" for s in t["tools"])]
    raw = [t for t in traces if any(s["tool"] in ("get_mdna", "locate_mdna") for s in t["tools"])]
    removed = sum(1 for t in traces for s in t["tools"] if "unverified quote" in (s.get("observation") or ""))
    print(f"Runs that called read_mdna_items: {len(used)} of {len(traces)}; also read the full MD&A: {len(raw)}; "
          f"runs where unverified quotes were removed: {removed}")
    kinds, tables, below = {}, 0, 0
    for t in traces:
        for s in t["tools"]:
            if s["tool"] == "read_mdna_items":
                obs = s.get("observation") or ""
                for count, kind in re.findall(r"(\d+) (guidance|one_off|headwind|tailwind|segment_trend)", obs):
                    kinds[kind] = kinds.get(kind, 0) + int(count)
                tables += sum(int(c) for c in re.findall(r"(\d+) from tables", obs))
                below += sum(int(c) for c in re.findall(r"(\d+) below operating", obs))
    if kinds:
        print("MD&A items by kind: " + ", ".join(f"{k} {kinds.get(k, 0)}" for k in
              ("guidance", "one_off", "headwind", "tailwind", "segment_trend"))
              + f"; from tables {tables}; below operating income {below}")
    billed = [t["usage"]["billed"].get("prompt_tokens", 0) for t in traces if (t.get("usage") or {}).get("billed")]
    if billed:
        print(f"Median input tokens per run, every call included: {median(billed):,.0f}; all runs: {sum(billed):,.0f}")
    tokens = [t["usage"].get("prompt_tokens", 0) for t in traces if t.get("usage")]
    if tokens:
        print(f"Median input tokens per run: {median(tokens):,.0f}")

    print("\nDecrease calls, for reading by hand (does each name a concrete driver?):")
    for t in traces:
        direction = re.search(r"direction\W+(increase|decrease)", t["answer"] or "", re.I)
        if direction and direction.group(1).lower() == "decrease":
            why = _section(t["answer"], "Rationale") or (t["answer"] or "")[-400:]
            print(f"- {t['ticker']}: {' '.join(why.split())[:400]}")


if __name__ == "__main__":
    main(sys.argv[1:])
