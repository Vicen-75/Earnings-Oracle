# --- Vicente: cost and speed per analysis, issue #55 (code written with help from Claude) ---
# Measured cost per interaction (§5.6, element 1): tokens counted by the model itself on every call of an analysis
# (main agent, MD&A locator, anonymizer brand scan), priced at Google's published paid-tier rate.
#
# Run from the repository root:
#   python -m eval.cost_analysis --run CAT HD ADBE JPM MCD   # run fresh analyses now and measure them
#   python -m eval.cost_analysis                             # read eval/backtest_200_results.jsonl if it exists
# Writes eval/cost_per_analysis.csv and prints the summary (median, mean, 90th percentile).
import csv
import json
import statistics
import sys
import time
from pathlib import Path

# Gemini 3.1 Flash-Lite, paid tier, Standard (ai.google.dev/gemini-api/docs/pricing, read Nov 6, 2026).
# Output includes thinking tokens. Our app runs on the free tier; these are the prices a real deployment would pay.
MODEL_PRICE = {"input_per_million": 0.25, "output_per_million": 1.50}
BACKTEST = Path("eval/backtest_200_results.jsonl")
OUT = Path("eval/cost_per_analysis.csv")


def cost_usd(billed):
    """Cost of one analysis from its billed usage. Thinking tokens are billed at the output price."""
    tokens_out = billed.get("output_tokens", 0) + billed.get("thinking_tokens", 0)
    return (billed.get("prompt_tokens", 0) * MODEL_PRICE["input_per_million"]
            + tokens_out * MODEL_PRICE["output_per_million"]) / 1_000_000


def row_from(ticker, usage, seconds, source):
    billed = usage.get("billed") or usage          # older results have only the main agent's counts
    return {"ticker": ticker, "source": source, "complete_count": "billed" in usage,
            "model_calls": billed.get("model_calls", 0), "prompt_tokens": billed.get("prompt_tokens", 0),
            "output_tokens": billed.get("output_tokens", 0), "thinking_tokens": billed.get("thinking_tokens", 0),
            "seconds": round(seconds, 1) if seconds is not None else "", "cost_usd": round(cost_usd(billed), 5)}


def run_fresh(tickers):
    from src.agent import investigate
    rows = []
    for t in tickers:
        start = time.time()
        out = investigate(t, write_log=False)
        rows.append(row_from(t, out["usage"], time.time() - start, "fresh run"))
        print(f"{t}: {rows[-1]['model_calls']} calls, {rows[-1]['prompt_tokens']:,} in, "
              f"{rows[-1]['output_tokens'] + rows[-1]['thinking_tokens']:,} out, {rows[-1]['seconds']}s, "
              f"${rows[-1]['cost_usd']:.4f}")
    return rows


def from_backtest():
    rows = []
    for line in BACKTEST.read_text().splitlines():
        r = json.loads(line)
        if r.get("usage"):
            rows.append(row_from(r.get("ticker"), r["usage"], r.get("seconds"), "200-company backtest"))
    return rows


def summary(rows):
    def stats(key):
        values = sorted(r[key] for r in rows if r[key] != "")
        if not values:
            return "n/a"
        p90 = values[min(len(values) - 1, int(0.9 * len(values)))]
        return f"median {statistics.median(values):,.4g} | mean {statistics.mean(values):,.4g} | 90th pct {p90:,.4g}"
    print(f"\n{len(rows)} analyses ({sum(r['complete_count'] for r in rows)} with every call counted)")
    for key in ["model_calls", "prompt_tokens", "output_tokens", "thinking_tokens", "seconds", "cost_usd"]:
        print(f"  {key:16s} {stats(key)}")
    print(f"Prices: ${MODEL_PRICE['input_per_million']}/M input, ${MODEL_PRICE['output_per_million']}/M output "
          "(thinking included), Gemini 3.1 Flash-Lite paid tier.")


def main(args):
    if args and args[0] == "--run":
        rows = run_fresh(args[1:] or ["CAT", "HD", "ADBE"])
    elif BACKTEST.exists():
        rows = from_backtest()
    else:
        print(f"{BACKTEST} not found. Use --run TICKER ... to measure fresh analyses.")
        return
    with open(OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary(rows)
    print(f"Rows in {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
