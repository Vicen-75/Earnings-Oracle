# Ablation on set A: V5 with and without the ratios (issue #52)

200 of 200 companies run without the ratio tool. Plan fixed before the run (docs/test_plan.md, Nov 10). Missing answers count as wrong.

## Accuracy

| Predictor | Correct | Accuracy | 95% interval |
|---|---|---|---|
| Full V5 | 121 of 200 | 60% | 54% to 67% |
| Without the ratios | 127 of 200 | 64% | 57% to 70% |
| Always increase | 126 of 200 | 63% | 56% to 69% |
| Momentum | 104 of 200 | 52% | 45% to 59% |

## Main result: with vs without the ratios (exact McNemar, same companies)

| Right only with the ratios | Right only without the ratios | p-value | Verdict at 0.05 |
|---|---|---|---|
| 7 | 13 | 0.263 | no clear difference |

The two runs gave the same direction on 178 of 200 companies (89%).

## Each against always-increase (exact McNemar)

| Run | Right, always-increase wrong | Always-increase right, run wrong | p-value |
|---|---|---|---|
| Full V5 | 24 | 29 | 0.583 |
| Without the ratios | 27 | 26 | 1.000 |

## How each run calls direction

| Run | Said increase | Said decrease | No answer | Decrease calls right | Increase calls right |
|---|---|---|---|---|---|
| Full V5 | 146 | 50 | 4 | 24 of 50 (48%) | 97 of 146 (66%) |
| Without the ratios | 147 | 53 | 0 | 27 of 53 (51%) | 100 of 147 (68%) |

## Calibration (accuracy by stated probability)

| Stated probability | Full V5 | Without the ratios |
|---|---|---|
| below 0.60 | 1 of 2 (50%) | 2 of 4 (50%) |
| 0.60 to 0.69 | 42 of 74 (57%) | 54 of 94 (57%) |
| 0.70 to 0.79 | 51 of 86 (59%) | 51 of 78 (65%) |
| 0.80 and up | 27 of 34 (79%) | 20 of 24 (83%) |

## Cost per run (median)

| Run | Input tokens | Model calls | Seconds |
|---|---|---|---|
| Full V5 | 93,362 | 5 | 54 |
| Without the ratios | 73,458 | 5 | 19 |

## Exploratory: where the difference comes from

Chosen after seeing the first ablation's results, so these cuts explain the result; they do not test it.

Calls in the same direction as last year (momentum): Full V5 139, Without the ratios 143, of 200.

| Last year, then this year | Companies | Full V5 right | Without the ratios right |
|---|---|---|---|
| rose, then rose | 80 | 70 | 74 |
| rose, then fell | 50 | 11 | 14 |
| fell, then rose | 46 | 27 | 26 |
| fell, then fell | 24 | 13 | 13 |

Companies where the two runs disagree, by direction of the change from Without the ratios to Full V5:

| Without the ratios said | Full V5 said | Full V5 right | Full V5 wrong |
|---|---|---|---|
| decrease | increase | 6 | 4 |
| increase | decrease | 1 | 7 |

When both runs give the same call (178 companies) they are right 114 times (64%); always-increase on the same companies: 62%.


Run-to-run variation (issue #51) means some disagreements between the two runs would happen even with identical tools; the McNemar test counts only the companies where they disagree, and the verdict should be read with that in mind.
