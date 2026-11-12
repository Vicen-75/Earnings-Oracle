# Backtest report: prompt V5, anonymized

Company name, ticker, CIK and brand names hidden from the model (src/anonymize.py). Compare with the named run: python -m eval.named_vs_anon.

191 of 200 companies run. Missing answers count as wrong. Test set and analysis fixed in advance (docs/test_plan.md).

**Incomplete run:** 9 companies still to run. Numbers below cover the 191 done.

## Accuracy

| Predictor | Correct | Accuracy | 95% interval |
|---|---|---|---|
| **Model** | 114 of 191 | **60%** | 53% to 66% |
| Always increase | 120 of 191 | 63% | 56% to 69% |
| Momentum | 101 of 191 | 53% | 46% to 60% |
| Reverse momentum | 90 of 191 | 47% | 40% to 54% |

## Model vs each baseline (same companies, exact McNemar test)

Only the companies where the two disagree carry evidence.

| Baseline | Model right, baseline wrong | Baseline right, model wrong | p-value | Verdict at 0.05 |
|---|---|---|---|---|
| Always increase | 26 | 32 | 0.512 | no clear difference |
| Momentum | 29 | 16 | 0.072 | no clear difference |
| Reverse momentum | 85 | 61 | 0.057 | no clear difference |

## Confusion

| | Truth: increase | Truth: decrease |
|---|---|---|
| Model: increase | 88 | 45 |
| Model: decrease | 31 | 26 |
| No answer | 1 | 0 |

Base rate: 120 increases, 71 decreases. Model said increase 133 times.

## Calibration (is a higher stated probability more often right?)

| Stated probability | Companies | Correct | Accuracy |
|---|---|---|---|
| below 0.60 | 1 | 0 | 0% |
| 0.60 to 0.69 | 72 | 39 | 54% |
| 0.70 to 0.79 | 81 | 49 | 60% |
| 0.80 and up | 36 | 26 | 72% |
| no probability given | 1 | | |

## By target metric

| Group | Companies | Model | Always increase | Momentum |
|---|---|---|---|---|
| operating income | 153 | 61% | 63% | 54% |
| pretax income | 38 | 53% | 61% | 47% |

## By industry group

| Group | Companies | Model | Always increase | Momentum |
|---|---|---|---|---|
| general | 54 | 61% | 70% | 54% |
| industrials | 20 | 70% | 55% | 40% |
| retail | 16 | 50% | 69% | 38% |
| insurance | 16 | 44% | 56% | 56% |
| materials chemicals | 13 | 31% | 38% | 54% |
| software internet | 11 | 73% | 91% | 82% |
| utilities waste | 11 | 55% | 45% | 55% |
| semis hardware | 11 | 73% | 91% | 64% |
| banks | 8 | 75% | 62% | 50% |
| pharma medtech | 8 | 62% | 75% | 50% |
| consumer staples | 7 | 86% | 29% | 29% |
| energy mining | 7 | 57% | 43% | 43% |
| restaurants | 5 | 60% | 40% | 80% |
| transportation | 4 | 50% | 75% | 75% |

Groups are small: read them as hints for where to look, not as results.
