# Ablation on set A: V5 with and without the MD&A (issue #52)

200 of 200 companies run without the MD&A tools. Plan fixed before the run (docs/test_plan.md, Nov 10). Missing answers count as wrong.

## Accuracy

| Predictor | Correct | Accuracy | 95% interval |
|---|---|---|---|
| Full V5 | 121 of 200 | 60% | 54% to 67% |
| Without the MD&A | 111 of 200 | 56% | 49% to 62% |
| Always increase | 126 of 200 | 63% | 56% to 69% |
| Momentum | 104 of 200 | 52% | 45% to 59% |

## Main result: with vs without the MD&A (exact McNemar, same companies)

| Right only with the MD&A | Right only without the MD&A | p-value | Verdict at 0.05 |
|---|---|---|---|
| 37 | 27 | 0.260 | no clear difference |

The two runs gave the same direction on 133 of 200 companies (66%).

## Each against always-increase (exact McNemar)

| Run | Right, always-increase wrong | Always-increase right, run wrong | p-value |
|---|---|---|---|
| Full V5 | 24 | 29 | 0.583 |
| Without the MD&A | 33 | 48 | 0.119 |

## How each run calls direction

| Run | Said increase | Said decrease | No answer | Decrease calls right | Increase calls right |
|---|---|---|---|---|---|
| Full V5 | 146 | 50 | 4 | 24 of 50 (48%) | 97 of 146 (66%) |
| Without the MD&A | 119 | 81 | 0 | 33 of 81 (41%) | 78 of 119 (66%) |

## Calibration (accuracy by stated probability)

| Stated probability | Full V5 | Without the MD&A |
|---|---|---|
| below 0.60 | 1 of 2 (50%) | 7 of 17 (41%) |
| 0.60 to 0.69 | 42 of 74 (57%) | 47 of 78 (60%) |
| 0.70 to 0.79 | 51 of 86 (59%) | 42 of 84 (50%) |
| 0.80 and up | 27 of 34 (79%) | 15 of 21 (71%) |

## Cost per run (median)

| Run | Input tokens | Model calls | Seconds |
|---|---|---|---|
| Full V5 | 93,362 | 5 | 54 |
| Without the MD&A | 20,763 | 6 | 15 |

## Exploratory: where the difference comes from

Chosen after seeing the first ablation's results, so these cuts explain the result; they do not test it.

Calls in the same direction as last year (momentum): Full V5 139, Without the MD&A 167, of 200.

| Last year, then this year | Companies | Full V5 right | Without the MD&A right |
|---|---|---|---|
| rose, then rose | 80 | 70 | 71 |
| rose, then fell | 50 | 11 | 13 |
| fell, then rose | 46 | 27 | 7 |
| fell, then fell | 24 | 13 | 20 |

Companies where the two runs disagree, by direction of the change from Without the MD&A to Full V5:

| Without the MD&A said | Full V5 said | Full V5 right | Full V5 wrong |
|---|---|---|---|
| decrease | increase | 28 | 18 |
| increase | decrease | 9 | 8 |

When both runs give the same call (133 companies) they are right 84 times (63%); always-increase on the same companies: 65%.


Run-to-run variation (issue #51) means some disagreements between the two runs would happen even with identical tools; the McNemar test counts only the companies where they disagree, and the verdict should be read with that in mind.
