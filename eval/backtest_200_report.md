# Backtest report: prompt V5

200 of 200 companies run. Missing answers count as wrong. Test set and analysis fixed in advance (docs/test_plan.md).

## Accuracy

| Predictor | Correct | Accuracy | 95% interval |
|---|---|---|---|
| **Model** | 121 of 200 | **60%** | 54% to 67% |
| Always increase | 126 of 200 | 63% | 56% to 69% |
| Momentum | 104 of 200 | 52% | 45% to 59% |
| Reverse momentum | 96 of 200 | 48% | 41% to 55% |

## Model vs each baseline (same companies, exact McNemar test)

Only the companies where the two disagree carry evidence.

| Baseline | Model right, baseline wrong | Baseline right, model wrong | p-value | Verdict at 0.05 |
|---|---|---|---|---|
| Always increase | 24 | 29 | 0.583 | no clear difference |
| Momentum | 38 | 21 | 0.036 | model better |
| Reverse momentum | 83 | 58 | 0.043 | model better |

## Confusion

| | Truth: increase | Truth: decrease |
|---|---|---|
| Model: increase | 97 | 49 |
| Model: decrease | 26 | 24 |
| No answer | 3 | 1 |

Base rate: 126 increases, 74 decreases. Model said increase 146 times.

## Calibration (is a higher stated probability more often right?)

| Stated probability | Companies | Correct | Accuracy |
|---|---|---|---|
| below 0.60 | 2 | 1 | 50% |
| 0.60 to 0.69 | 74 | 42 | 57% |
| 0.70 to 0.79 | 86 | 51 | 59% |
| 0.80 and up | 34 | 27 | 79% |
| no probability given | 4 | | |

## By target metric

| Group | Companies | Model | Always increase | Momentum |
|---|---|---|---|---|
| operating income | 161 | 63% | 63% | 53% |
| pretax income | 39 | 51% | 62% | 49% |

## By industry group

| Group | Companies | Model | Always increase | Momentum |
|---|---|---|---|---|
| general | 59 | 61% | 68% | 49% |
| industrials | 22 | 73% | 59% | 45% |
| retail | 17 | 47% | 71% | 35% |
| insurance | 16 | 44% | 56% | 56% |
| materials chemicals | 13 | 38% | 38% | 54% |
| software internet | 12 | 83% | 92% | 83% |
| utilities waste | 11 | 55% | 45% | 55% |
| semis hardware | 11 | 73% | 91% | 64% |
| banks | 8 | 62% | 62% | 50% |
| pharma medtech | 8 | 75% | 75% | 50% |
| consumer staples | 7 | 86% | 29% | 29% |
| energy mining | 7 | 43% | 43% | 43% |
| restaurants | 5 | 60% | 40% | 80% |
| transportation | 4 | 50% | 75% | 75% |

Groups are small: read them as hints for where to look, not as results.
