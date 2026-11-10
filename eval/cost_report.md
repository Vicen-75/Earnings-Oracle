# Cost and speed per analysis

Issues #55 and #59. Owner: Vicente. Drafted with help from Claude; numbers produced by code in this repo.
Data: `eval/backtest_200_results.jsonl` (200-company backtest, prompt V5, Nov 5 to 6) and
`eval/cost_per_analysis.csv` (5 fresh runs, Nov 6). Script: `eval/cost_analysis.py`.

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

The financial model (#59, `Earnings_Oracle_financial_model.xlsx` in the team Drive) uses $0.030 as the base cost
per analysis and the most expensive measured run ($0.073, JPM) in the worst case.

## How to run it again

```
python -m eval.cost_analysis                      # reads eval/backtest_200_results.jsonl
python -m eval.cost_analysis --run CAT HD ADBE    # fresh analyses, every call counted
```
A backtest run after Nov 6 records every call (`usage["billed"]`), so the next one will not need the estimate in point 2.
