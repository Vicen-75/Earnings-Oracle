# Set B: cost, time and run-to-run variation by version (descriptive)

Not pre-registered: written on Nov 13, 2026, after the set B result was known, to help choose the version the app runs. It describes runs already collected on set B's 200 companies and tests nothing. Seconds come from batch runs on shared free keys and include waits for rate limits.

## 1. Cost and time per analysis

Prices: $0.25 per million input tokens, $1.50 per million output tokens, thinking billed as output (eval/cost_analysis.py). The app runs on the free tier; these are what a paid deployment would pay.

| Version | Companies | Model calls, median | Input tokens, median | Output and thinking tokens, median | Cost, median | Cost, mean | Cost, 90th percentile | Seconds, median | Seconds, 90th percentile | Total for these companies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V5, one run | 200 | 5 | 92,448 | 2,780 | $0.0276 | $0.0311 | $0.0456 | 44 | 112 | $6.22 |
| V6, one run (run 1) | 200 | 7 | 61,759 | 3,735 | $0.0212 | $0.0242 | $0.0358 | 34 | 89 | $4.84 |
| V6, three runs | 200 | 21 | 189,909 | 11,168 | $0.0646 | $0.0718 | $0.1019 | 104 | 262 | $14.37 |
| V6 without the structured pass, one run | 200 | 6 | 98,294 | 2,856 | $0.0290 | $0.0334 | $0.0489 | 103 | 464 | $6.67 |

- V6, one run (run 1) against V5 on the same 200 companies: the median company costs 0.75 times V5; cheaper than V5 for 154 of 200 (77.0%).
- V6, three runs against V5 on the same 200 companies: the median company costs 2.30 times V5; cheaper than V5 for 0 of 200 (0.0%).
- V6 without the structured pass, one run against V5 on the same 200 companies: the median company costs 1.05 times V5; cheaper than V5 for 70 of 200 (35.0%).

## 2. How much V6 varies from run to run

200 companies, 3 runs each, same prompt, same tools, temperature 1.0.

| | Correct | Decrease calls | No answer |
| --- | --- | --- | --- |
| Run 1 alone | 135 of 200 (67.5%) | 80 | 0 |
| Run 2 alone | 134 of 200 (67.0%) | 82 | 1 |
| Run 3 alone | 132 of 200 (66.0%) | 77 | 0 |
| The 3 runs averaged | 135 of 200 (67.5%) | 80 | 0 |

| Two runs of the same company | Companies both answered | Different direction |
| --- | --- | --- |
| Run 1 and run 2 | 199 | 23 of 199 (11.6%) |
| Run 1 and run 3 | 200 | 25 of 200 (12.5%) |
| Run 2 and run 3 | 199 | 21 of 199 (10.6%) |

All 3 runs answered for 199 companies: the same direction every time for 165 of 199 (82.9%), a split for 34 of 199 (17.1%).

Stated probability of an increase, highest minus lowest run for the same company (200 companies): median 0.05; 77 of 200 (38.5%) differ by 0.10 or more, 38 of 200 (19.0%) by 0.20 or more.

For scale: how often something else calls a different direction from V6 run 1. A change to the prompt or tools shows only in what it adds on top of the run 2 and run 3 rows.

| Against V6 run 1 | Companies both answered | Different direction |
| --- | --- | --- |
| V6 run 2 (nothing changed) | 199 | 23 of 199 (11.6%) |
| V6 run 3 (nothing changed) | 200 | 25 of 200 (12.5%) |
| V6 without the downward rules (one run) | 199 | 18 of 199 (9.0%) |
| V6 without the one-off adjustment (one run) | 199 | 25 of 199 (12.6%) |
| V6 without the structured pass (one run) | 199 | 42 of 199 (21.1%) |
| V5 (one run) | 199 | 43 of 199 (21.6%) |

## 3. Which tools each version called

| Version | Runs | get_company_card | get_industry_playbook | compute_ratios | read_mdna_items | get_mdna | locate_mdna |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V5 | 200 | 200 of 200 (100.0%) | 200 of 200 (100.0%) | 200 of 200 (100.0%) | 0 of 200 (0.0%) | 200 of 200 (100.0%) | 14 of 200 (7.0%) |
| V6, all runs | 600 | 600 of 600 (100.0%) | 585 of 600 (97.5%) | 599 of 600 (99.8%) | 600 of 600 (100.0%) | 74 of 600 (12.3%) | 7 of 600 (1.2%) |
| V6, run 1 only | 200 | 200 of 200 (100.0%) | 194 of 200 (97.0%) | 200 of 200 (100.0%) | 200 of 200 (100.0%) | 28 of 200 (14.0%) | 3 of 200 (1.5%) |

V6 runs that used the structured pass (read_mdna_items): 600 of 600 (100.0%); of those, 79 also read the full text. Runs that read only the full text: 0. Runs that read no MD&A at all: 0.
