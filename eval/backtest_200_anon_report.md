# Backtest report: prompt V5, anonymized

Company name, ticker, CIK and brand names hidden from the model (src/anonymize.py). Compare with the named run: python -m eval.named_vs_anon.

200 of 200 companies run. Missing answers count as wrong. Test set and analysis fixed in advance (docs/test_plan.md).

## Accuracy

| Predictor | Correct | Accuracy | 95% interval |
|---|---|---|---|
| **Model** | 118 of 200 | **59%** | 52% to 66% |
| Always increase | 126 of 200 | 63% | 56% to 69% |
| Momentum | 104 of 200 | 52% | 45% to 59% |
| Reverse momentum | 96 of 200 | 48% | 41% to 55% |

## Model vs each baseline (same companies, exact McNemar test)

Only the companies where the two disagree carry evidence.

| Baseline | Model right, baseline wrong | Baseline right, model wrong | p-value | Verdict at 0.05 |
|---|---|---|---|---|
| Always increase | 27 | 35 | 0.374 | no clear difference |
| Momentum | 30 | 16 | 0.054 | no clear difference |
| Reverse momentum | 88 | 66 | 0.090 | no clear difference |

## Confusion

| | Truth: increase | Truth: decrease |
|---|---|---|
| Model: increase | 91 | 47 |
| Model: decrease | 35 | 27 |
| No answer | 0 | 0 |

Base rate: 126 increases, 74 decreases. Model said increase 138 times.

## Calibration (is a higher stated probability more often right?)

| Stated probability | Companies | Correct | Accuracy |
|---|---|---|---|
| below 0.60 | 1 | 0 | 0% |
| 0.60 to 0.69 | 75 | 40 | 53% |
| 0.70 to 0.79 | 84 | 49 | 58% |
| 0.80 and up | 40 | 29 | 72% |

## By target metric

| Group | Companies | Model | Always increase | Momentum |
|---|---|---|---|---|
| operating income | 161 | 60% | 63% | 53% |
| pretax income | 39 | 54% | 62% | 49% |

## By industry group

| Group | Companies | Model | Always increase | Momentum |
|---|---|---|---|---|
| general | 59 | 58% | 68% | 49% |
| industrials | 22 | 68% | 59% | 45% |
| retail | 17 | 53% | 71% | 35% |
| insurance | 16 | 44% | 56% | 56% |
| materials chemicals | 13 | 31% | 38% | 54% |
| software internet | 12 | 75% | 92% | 83% |
| utilities waste | 11 | 55% | 45% | 55% |
| semis hardware | 11 | 73% | 91% | 64% |
| banks | 8 | 75% | 62% | 50% |
| pharma medtech | 8 | 62% | 75% | 50% |
| consumer staples | 7 | 86% | 29% | 29% |
| energy mining | 7 | 57% | 43% | 43% |
| restaurants | 5 | 60% | 40% | 80% |
| transportation | 4 | 50% | 75% | 75% |

Groups are small: read them as hints for where to look, not as results.
