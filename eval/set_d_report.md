# Set D: 400 companies, V6 with one run

Pre-registered in docs/test_plan.md (Nov 13 note), one look. Exact two-sided McNemar on correct answers; significant at p < 0.05. V6 beats the baselines only if it is significantly better than all three. No answer counts as wrong.

| Version | Correct | Decrease calls | No answer |
| --- | --- | --- | --- |
| V6 (one run) | 245 (61.2%) | 134 (64 right) | 5 |
| Always increase | 254 (63.5%) | 0 (0 right) | 0 |
| Momentum | 229 (57.2%) | 155 (65 right) | 0 |
| Reverse momentum | 171 (42.8%) | 245 (81 right) | 0 |

| V6 against | V6 only right | Baseline only right | p | Significant |
| --- | --- | --- | --- | --- |
| Always increase | 64 | 73 | 0.4944 | no |
| Momentum | 77 | 61 | 0.2015 | no |
| Reverse momentum | 168 | 94 | < 0.0001 | yes |

**Result: V6 does not beat all three baselines.**

## Combined view: sets B, C and D (descriptive, not a test)

Sets B and C were already known to favour V6 when set D was planned, so these numbers estimate the size of the edge over always increase; the p-values are not verdicts. V6 with one run everywhere.

| Set | Companies | V6 correct | Always increase correct | V6 only right | Always increase only right | Difference, points (approx. 95% interval) | p (descriptive) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Set B (run 1 of 3) | 200 | 135 (67.5%) | 123 (61.5%) | 46 | 34 | +6.0 (-2.7 to +14.7) | 0.2185 |
| Set C | 200 | 132 (66.0%) | 121 (60.5%) | 42 | 31 | +5.5 (-2.8 to +13.8) | 0.2416 |
| Set D | 400 | 245 (61.2%) | 254 (63.5%) | 64 | 73 | -2.2 (-8.0 to +3.5) | 0.4944 |
| **All together** | 800 | 512 (64.0%) | 498 (62.2%) | 152 | 138 | +1.8 (-2.4 to +5.9) | 0.4453 |

| All together, V6 against | V6 only right | Baseline only right | p (descriptive) |
| --- | --- | --- | --- |
| Always increase | 152 | 138 | 0.4453 |
| Momentum | 167 | 107 | 0.0003 |
| Reverse momentum | 345 | 181 | < 0.0001 |
