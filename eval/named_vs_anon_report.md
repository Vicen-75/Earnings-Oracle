# Named vs anonymized: prompt V5

Companies run both ways: 200 of 200 (named: 200, anonymized: 200). Missing answers count as wrong.

## All companies run both ways

| Run | Correct | Accuracy | 95% interval | Average stated probability |
|---|---|---|---|---|
| Named | 121 of 200 | 60% | 54% to 67% | 0.71 |
| Anonymized | 118 of 200 | 59% | 52% to 66% | 0.71 |

| Named right, anonymized wrong | Anonymized right, named wrong | p-value (exact McNemar) | Verdict at 0.05 |
|---|---|---|---|
| 12 | 9 | 0.664 | no clear difference |

Same direction in both runs: 176 of 200 (88%).

**How to read it.** If named accuracy is clearly higher, part of the named score comes from what the model remembers about the company, and the anonymized number is the honest one. No clear difference is consistent with the model reading the filings, but it is only strong evidence for the companies the model could not identify (next section).

## Could the model still tell which company it was?

From eval/anonymize_check_200.csv: the model named the company from the anonymized MD&A for 169 of 199 companies checked.

### Company still identifiable

| Run | Correct | Accuracy | 95% interval | Average stated probability |
|---|---|---|---|---|
| Named | 101 of 169 | 60% | 52% to 67% | 0.71 |
| Anonymized | 99 of 169 | 59% | 51% to 66% | 0.71 |

| Named right, anonymized wrong | Anonymized right, named wrong | p-value (exact McNemar) | Verdict at 0.05 |
|---|---|---|---|
| 11 | 9 | 0.824 | no clear difference |

Same direction in both runs: 147 of 169 (87%).

### Company hidden (the cleaner test)

| Run | Correct | Accuracy | 95% interval | Average stated probability |
|---|---|---|---|---|
| Named | 20 of 30 | 67% | 49% to 81% | 0.70 |
| Anonymized | 19 of 30 | 63% | 46% to 78% | 0.70 |

| Named right, anonymized wrong | Anonymized right, named wrong | p-value (exact McNemar) | Verdict at 0.05 |
|---|---|---|---|
| 1 | 0 | 1.000 | no clear difference |

Same direction in both runs: 28 of 30 (93%).

Groups are smaller than the full set: read the split as a hint, not as a result.

