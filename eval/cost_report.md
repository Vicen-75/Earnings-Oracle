# Cost and speed per analysis

Issues #55 and #59. Owner: Vicente. Drafted with help from Claude; numbers produced by code in this repo.
Data: `eval/backtest_200_results.jsonl` (200-company backtest, prompt V5, Nov 5 to 6),
`eval/cost_per_analysis.csv` (5 fresh runs, Nov 6), and for the version the app runs since Nov 14,
`eval/set_b_cost_variation_report.md` (set B, Nov 13) and `eval/setd_results.jsonl` (set D, Nov 14).
Script: `eval/cost_analysis.py`.

## Nov 14: the app runs V6 with one run

The team chose V6 with one run for the app on Nov 13 (it is as accurate as the other two options on set B, 135 of 200
against 134 for V5 and 135 for V6 with three runs). Every call is counted in these runs (main agent, MD&A item pass,
locator, thinking tokens), so no estimate is needed.

| Version | Set | Companies | Cost per analysis, median | Mean | 90th percentile | Model calls | Input tokens, median |
|---|---|---|---|---|---|---|---|
| V5 | B | 200 | $0.028 | $0.031 | $0.046 | 5 (median) | 92,000 |
| **V6, one run (the app)** | B | 200 | $0.021 | **$0.024** | $0.036 | 7 (median) | 62,000 |
| **V6, one run (the app)** | D | 400 | $0.021 | **$0.024** | $0.033 | 7.4 (mean) | 61,000 |
| V6, three runs | B | 200 | $0.065 | $0.072 | $0.102 | 21 (median) | 190,000 |

1. **V6 with one run is the cheapest.** It reads a structured list of MD&A items instead of the whole MD&A, so input
   falls by about a third. It is cheaper than V5 for 77% of the set B companies. Input is now about 75% of the cost
   (92% for V5). Set D, 400 new companies, gives the same mean, $0.024.
2. **Three runs cost three times as much for no gain** (135 of 200 either way, `eval/set_b_stage2_report.md`).
3. **Speed.** Median 34 s on set B against 44 s for V5 (`eval/set_b_cost_variation_report.md`); batch runs on shared
   free keys include waits for rate limits, so these are upper bounds for a single analysis in the app.
4. **One outlier.** The most expensive set D company cost $0.26 (long tool loop); the 90th percentile is $0.033.

The financial model (#59) now uses **$0.024** as the base cost per analysis and the V5 worst case ($0.073, JPM) as the
high case. The sections below are the Nov 6 to 9 measurement of V5, kept as they were.

## Price used

Gemini 3.1 Flash-Lite, paid tier, Standard: $0.25 per million input tokens, $1.50 per million output tokens,
thinking tokens billed as output (ai.google.dev/gemini-api/docs/pricing, read Nov 6, 2026).
The class app runs on the free tier and pays nothing; these are the prices a real deployment would pay.

## Results

| | 200-company backtest | 5 fresh runs (CAT, HD, ADBE, JPM, MCD) |
|---|---|---|
| What is counted | main agent only | every call: main agent, MD&A locator, brand scan, thinking |
| Cost per analysis, median | $0.026 | $0.028 |
| Cost per analysis, mean | $0.029 | $0.035 |
| Cost per analysis, 90th percentile | $0.046 | $0.073 |
| Most expensive | $0.082 (TPG) | $0.073 (JPM) |
| Model calls, mean | 5.5 | 7 |
| Input tokens, median | 93,000 | 98,000 |
| Output tokens, mean | 1,500 | 1,550 + 1,130 thinking |
| Seconds, median | 54 | 44 |
| Total for the 200 | $5.75 | |

## What the numbers say

1. **Input is the cost.** 92% of the backtest cost is input tokens, almost all of it the MD&A the agent reads.
   Cutting the MD&A excerpt is the main lever on cost; cutting the answer length is not.
2. **The backtest undercounts a little.** It ran before the full meter existed (merged Nov 6, PR #58), so it misses
   thinking tokens (about 1,100 per analysis, about $0.002) and the MD&A locator's own calls (10 of the 200
   companies needed the locator; their main agent alone already cost $0.038 against $0.028 for the rest).
   Our estimate of the full cost per analysis on the 200 is **about $0.030**.
3. **Why the 5 fresh runs look higher.** Two of the five (JPM, a bank, and MCD) needed the locator: 40% of that
   sample against 5% of the 200. The 200 are the better estimate of an average company; the 5 show what a hard
   case costs.
4. **Seconds include waiting.** The backtest ran several companies at once on free keys, so its times include
   waits for rate limits. One analysis alone in the app took 17 to 84 seconds (median 44).

## Used in

Until Nov 14 the financial model (#59, `Earnings_Oracle_financial_model.xlsx` in the team Drive) used $0.030 (V5) as
the base cost per analysis and the most expensive measured run ($0.073, JPM) in the worst case. Since Nov 14 the base
is V6 with one run, $0.024 (section above).

## How to run it again

```
python -m eval.cost_analysis                      # reads eval/backtest_200_results.jsonl
python -m eval.cost_analysis --run CAT HD ADBE    # fresh analyses, every call counted
```
A backtest run after Nov 6 records every call (`usage["billed"]`), so the next one will not need the estimate in point 2.
