# Confidence and accuracy (exploratory)

Not pre-registered: written on Nov 12, 2026, after the set B result was known. It describes answers already collected and is not a test of the project's success. Confidence is the probability the model gave for the direction it called. The bands and cut-offs were fixed before the numbers were seen. Each band holds few companies, so its accuracy is uncertain by roughly 10 to 15 points either way.

| Version and set | Answered | Correct | Concordance | p | Confidence below 0.70: correct | Confidence 0.70 and up: correct | Brier, model | Brier, share of increases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Set B, V6 (three runs averaged) | 200 of 200 | 135 of 200 (67.5%) | 0.613 | 0.0093 | 89 of 138 (64.5%) | 46 of 62 (74.2%) | 0.2105 | 0.2368 |
| Set B, V5 (one run) | 199 of 200 | 134 of 199 (67.3%) | 0.595 | 0.0242 | 54 of 89 (60.7%) | 80 of 110 (72.7%) | 0.2146 | 0.2372 |
| Set C, V6 (one run) | 200 of 200 | 132 of 200 (66.0%) | 0.562 | 0.1281 | 65 of 105 (61.9%) | 67 of 95 (70.5%) | 0.2237 | 0.2390 |
| Set C, V7 (one run) | 200 of 200 | 129 of 200 (64.5%) | 0.602 | 0.0134 | 57 of 96 (59.4%) | 72 of 104 (69.2%) | 0.2247 | 0.2390 |
| Set A, V5 (one run) | 196 of 200 | 121 of 196 (61.7%) | 0.593 | 0.0232 | 43 of 76 (56.6%) | 78 of 120 (65.0%) | 0.2369 | 0.2337 |
| Set A, V6 (one run, in-sample) | 199 of 200 | 128 of 199 (64.3%) | 0.618 | 0.0039 | 65 of 114 (57.0%) | 63 of 85 (74.1%) | 0.2213 | 0.2336 |

## Set B, V6 (three runs averaged)

Answered with a probability: 200 of 200 companies. Correct: 135 of 200 (67.5%).

| Confidence | Companies | Correct | Average stated confidence | Increase calls right | Decrease calls right |
| --- | --- | --- | --- | --- | --- |
| 0.50 to 0.59 | 32 | 18 of 32 (56.2%) | 0.54 | 11 of 17 (64.7%) | 7 of 15 (46.7%) |
| 0.60 to 0.69 | 106 | 71 of 106 (67.0%) | 0.65 | 42 of 58 (72.4%) | 29 of 48 (60.4%) |
| 0.70 to 0.79 | 50 | 34 of 50 (68.0%) | 0.72 | 26 of 35 (74.3%) | 8 of 15 (53.3%) |
| 0.80 and up | 12 | 12 of 12 (100.0%) | 0.84 | 10 of 10 (100.0%) | 2 of 2 (100.0%) |

Concordance: 0.613 (0.500 means confidence says nothing about being right; rank-sum p = 0.0093, exploratory).

| Answer only when confidence is at least | Companies answered | Correct | Always increase on the same companies |
| --- | --- | --- | --- |
| 0.50 | 200 of 200 (100.0%) | 135 of 200 (67.5%) | 123 of 200 (61.5%) |
| 0.60 | 168 of 200 (84.0%) | 117 of 168 (69.6%) | 104 of 168 (61.9%) |
| 0.70 | 62 of 200 (31.0%) | 46 of 62 (74.2%) | 43 of 62 (69.4%) |
| 0.80 | 12 of 200 (6.0%) | 12 of 12 (100.0%) | 10 of 12 (83.3%) |

Brier score of the probability of an increase: model 0.2105; always stating the set's own share of increases 0.2368; coin flip 0.2500. Lower is better, and the constant forecast has the advantage of knowing the share in advance.

| The runs | Companies | Correct |
| --- | --- | --- |
| all gave the same direction | 165 | 115 of 165 (69.7%) |
| disagreed on the direction | 35 | 20 of 35 (57.1%) |

Exact Fisher test of that difference: p = 0.1669 (exploratory).

## Set B, V5 (one run)

Answered with a probability: 199 of 200 companies. Correct: 134 of 199 (67.3%).

| Confidence | Companies | Correct | Average stated confidence | Increase calls right | Decrease calls right |
| --- | --- | --- | --- | --- | --- |
| 0.50 to 0.59 | 2 | 1 of 2 (50.0%) | 0.55 | 1 of 2 (50.0%) | none |
| 0.60 to 0.69 | 87 | 53 of 87 (60.9%) | 0.64 | 27 of 46 (58.7%) | 26 of 41 (63.4%) |
| 0.70 to 0.79 | 73 | 49 of 73 (67.1%) | 0.72 | 40 of 55 (72.7%) | 9 of 18 (50.0%) |
| 0.80 and up | 37 | 31 of 37 (83.8%) | 0.82 | 27 of 30 (90.0%) | 4 of 7 (57.1%) |

Concordance: 0.595 (0.500 means confidence says nothing about being right; rank-sum p = 0.0242, exploratory).

| Answer only when confidence is at least | Companies answered | Correct | Always increase on the same companies |
| --- | --- | --- | --- |
| 0.50 | 199 of 200 (99.5%) | 134 of 199 (67.3%) | 122 of 199 (61.3%) |
| 0.60 | 197 of 200 (98.5%) | 133 of 197 (67.5%) | 121 of 197 (61.4%) |
| 0.70 | 110 of 200 (55.0%) | 80 of 110 (72.7%) | 79 of 110 (71.8%) |
| 0.80 | 37 of 200 (18.5%) | 31 of 37 (83.8%) | 30 of 37 (81.1%) |

Brier score of the probability of an increase: model 0.2146; always stating the set's own share of increases 0.2372; coin flip 0.2500. Lower is better, and the constant forecast has the advantage of knowing the share in advance.

## Set C, V6 (one run)

Answered with a probability: 200 of 200 companies. Correct: 132 of 200 (66.0%).

| Confidence | Companies | Correct | Average stated confidence | Increase calls right | Decrease calls right |
| --- | --- | --- | --- | --- | --- |
| 0.50 to 0.59 | 1 | 1 of 1 (100.0%) | 0.55 | 1 of 1 (100.0%) | none |
| 0.60 to 0.69 | 104 | 64 of 104 (61.5%) | 0.64 | 40 of 64 (62.5%) | 24 of 40 (60.0%) |
| 0.70 to 0.79 | 75 | 53 of 75 (70.7%) | 0.70 | 37 of 48 (77.1%) | 16 of 27 (59.3%) |
| 0.80 and up | 20 | 14 of 20 (70.0%) | 0.84 | 12 of 14 (85.7%) | 2 of 6 (33.3%) |

Concordance: 0.562 (0.500 means confidence says nothing about being right; rank-sum p = 0.1281, exploratory).

| Answer only when confidence is at least | Companies answered | Correct | Always increase on the same companies |
| --- | --- | --- | --- |
| 0.50 | 200 of 200 (100.0%) | 132 of 200 (66.0%) | 121 of 200 (60.5%) |
| 0.60 | 199 of 200 (99.5%) | 131 of 199 (65.8%) | 120 of 199 (60.3%) |
| 0.70 | 95 of 200 (47.5%) | 67 of 95 (70.5%) | 64 of 95 (67.4%) |
| 0.80 | 20 of 200 (10.0%) | 14 of 20 (70.0%) | 16 of 20 (80.0%) |

Brier score of the probability of an increase: model 0.2237; always stating the set's own share of increases 0.2390; coin flip 0.2500. Lower is better, and the constant forecast has the advantage of knowing the share in advance.

## Set C, V7 (one run)

Answered with a probability: 200 of 200 companies. Correct: 129 of 200 (64.5%).

| Confidence | Companies | Correct | Average stated confidence | Increase calls right | Decrease calls right |
| --- | --- | --- | --- | --- | --- |
| 0.50 to 0.59 | 1 | 0 of 1 (0.0%) | 0.55 | none | 0 of 1 (0.0%) |
| 0.60 to 0.69 | 95 | 57 of 95 (60.0%) | 0.64 | 33 of 53 (62.3%) | 24 of 42 (57.1%) |
| 0.70 to 0.79 | 75 | 49 of 75 (65.3%) | 0.71 | 38 of 54 (70.4%) | 11 of 21 (52.4%) |
| 0.80 and up | 29 | 23 of 29 (79.3%) | 0.85 | 18 of 21 (85.7%) | 5 of 8 (62.5%) |

Concordance: 0.602 (0.500 means confidence says nothing about being right; rank-sum p = 0.0134, exploratory).

| Answer only when confidence is at least | Companies answered | Correct | Always increase on the same companies |
| --- | --- | --- | --- |
| 0.50 | 200 of 200 (100.0%) | 129 of 200 (64.5%) | 121 of 200 (60.5%) |
| 0.60 | 199 of 200 (99.5%) | 129 of 199 (64.8%) | 120 of 199 (60.3%) |
| 0.70 | 104 of 200 (52.0%) | 72 of 104 (69.2%) | 69 of 104 (66.3%) |
| 0.80 | 29 of 200 (14.5%) | 23 of 29 (79.3%) | 21 of 29 (72.4%) |

Brier score of the probability of an increase: model 0.2247; always stating the set's own share of increases 0.2390; coin flip 0.2500. Lower is better, and the constant forecast has the advantage of knowing the share in advance.

## Set A, V5 (one run)

Answered with a probability: 196 of 200 companies. Correct: 121 of 196 (61.7%).

| Confidence | Companies | Correct | Average stated confidence | Increase calls right | Decrease calls right |
| --- | --- | --- | --- | --- | --- |
| 0.50 to 0.59 | 2 | 1 of 2 (50.0%) | 0.55 | 1 of 2 (50.0%) | none |
| 0.60 to 0.69 | 74 | 42 of 74 (56.8%) | 0.65 | 31 of 48 (64.6%) | 11 of 26 (42.3%) |
| 0.70 to 0.79 | 86 | 51 of 86 (59.3%) | 0.71 | 43 of 70 (61.4%) | 8 of 16 (50.0%) |
| 0.80 and up | 34 | 27 of 34 (79.4%) | 0.83 | 22 of 26 (84.6%) | 5 of 8 (62.5%) |

Concordance: 0.593 (0.500 means confidence says nothing about being right; rank-sum p = 0.0232, exploratory).

| Answer only when confidence is at least | Companies answered | Correct | Always increase on the same companies |
| --- | --- | --- | --- |
| 0.50 | 196 of 200 (98.0%) | 121 of 196 (61.7%) | 123 of 196 (62.8%) |
| 0.60 | 194 of 200 (97.0%) | 120 of 194 (61.9%) | 122 of 194 (62.9%) |
| 0.70 | 120 of 200 (60.0%) | 78 of 120 (65.0%) | 76 of 120 (63.3%) |
| 0.80 | 34 of 200 (17.0%) | 27 of 34 (79.4%) | 25 of 34 (73.5%) |

Brier score of the probability of an increase: model 0.2369; always stating the set's own share of increases 0.2337; coin flip 0.2500. Lower is better, and the constant forecast has the advantage of knowing the share in advance.

## Set A, V6 (one run, in-sample)

Answered with a probability: 199 of 200 companies. Correct: 128 of 199 (64.3%).

| Confidence | Companies | Correct | Average stated confidence | Increase calls right | Decrease calls right |
| --- | --- | --- | --- | --- | --- |
| 0.50 to 0.59 | 2 | 2 of 2 (100.0%) | 0.55 | 1 of 1 (100.0%) | 1 of 1 (100.0%) |
| 0.60 to 0.69 | 112 | 63 of 112 (56.2%) | 0.64 | 44 of 68 (64.7%) | 19 of 44 (43.2%) |
| 0.70 to 0.79 | 57 | 40 of 57 (70.2%) | 0.71 | 31 of 42 (73.8%) | 9 of 15 (60.0%) |
| 0.80 and up | 28 | 23 of 28 (82.1%) | 0.84 | 14 of 15 (93.3%) | 9 of 13 (69.2%) |

Concordance: 0.618 (0.500 means confidence says nothing about being right; rank-sum p = 0.0039, exploratory).

| Answer only when confidence is at least | Companies answered | Correct | Always increase on the same companies |
| --- | --- | --- | --- |
| 0.50 | 199 of 200 (99.5%) | 128 of 199 (64.3%) | 125 of 199 (62.8%) |
| 0.60 | 197 of 200 (98.5%) | 126 of 197 (64.0%) | 124 of 197 (62.9%) |
| 0.70 | 85 of 200 (42.5%) | 63 of 85 (74.1%) | 55 of 85 (64.7%) |
| 0.80 | 28 of 200 (14.0%) | 23 of 28 (82.1%) | 18 of 28 (64.3%) |

Brier score of the probability of an increase: model 0.2213; always stating the set's own share of increases 0.2336; coin flip 0.2500. Lower is better, and the constant forecast has the advantage of knowing the share in advance.
