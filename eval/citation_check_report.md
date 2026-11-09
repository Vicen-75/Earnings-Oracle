# Citation check: 200-company backtest, prompt V5 (issue #53)

Text cached for 200 of 200 companies. 561 quotes from 194 answers (6 answers had no quotes: the 4 empty answers and answers without a 'Cited passages' section).

## Are the quotes real?

| Category | Quotes | Share |
|---|---|---|
| Verbatim in the MD&A | 510 | 91% |
| Near-verbatim in the MD&A | 20 | 4% |
| Real, but from outside the MD&A | 27 | 5% |
| Reworded or stitched | 4 | 1% |

**557 of 561 quotes (99%) are real text from the filings the model read** (verbatim or near-verbatim). 530 (94%) come from the MD&A itself.

Answers whose every quote is real (and, where read by hand, has the right numbers): 189 of 194 (97%).

**Look-ahead check.** The hidden target-year 10-K (the filing the model was not allowed to read) was searched for 200 of 200 companies. Quotes that match only that filing: 0.

## Do bad citations go with wrong answers?

| Answers | Count | Correct | Accuracy |
|---|---|---|---|
| Every quote real | 189 | 117 | 62% |
| At least one quote not confirmed | 5 | 3 | 60% |

## Where the problems are

| Group | Quotes | Real | Share real |
|---|---|---|---|
| Locator used (agent found the MD&A itself) | 27 | 26 | 96% |
| Standard extractor | 534 | 531 | 99% |
| general | 165 | 165 | 100% |
| industrials | 60 | 60 | 100% |
| retail | 47 | 46 | 98% |
| insurance | 43 | 42 | 98% |
| materials chemicals | 37 | 37 | 100% |
| software internet | 35 | 35 | 100% |
| utilities waste | 33 | 32 | 97% |
| semis hardware | 32 | 32 | 100% |
| pharma medtech | 23 | 23 | 100% |
| banks | 22 | 22 | 100% |
| energy mining | 21 | 20 | 95% |
| consumer staples | 19 | 19 | 100% |
| transportation | 12 | 12 | 100% |
| restaurants | 12 | 12 | 100% |

Which year's filing the real quotes come from: FY2025 88, FY2024 468, FY2023 1.

## Are the numbers right?

Verbatim quotes carry the filing's numbers by definition. Of the 51 other quotes, 4 contain a number that is not in the passage they match: PTEN #2 (885), AEP #2 (2024), BELFA #3 (2.7), HRTG #3 (31). Each is read by hand below; a number added as framing (a date stated elsewhere in the filing) is harmless, a changed figure is not.

## Quotes that need a hand reading

5 quotes. Verdicts go in `eval/citation_check_notes.csv` (ticker, quote_no, verdict, note); verdict is one of paraphrase (meaning kept), stitched (real pieces joined), wrong_number (a figure that differs from the filing), invented (no basis in the filings), from_tool (a number from the ratio tool written as a quote), boilerplate.

| Hand verdict | Quotes |
|---|---|
| paraphrase | 3 |
| stitched | 1 |
| wrong_number | 1 |
| not read yet | 0 |

| Company | # | Category | Coverage | Quote (start) | Hand note |
|---|---|---|---|---|---|
| BELFA | 3 | near_verbatim | 0.95 | Inventory turns were 2.1 times for the year ended December 31, 2024 and 2.7 times for the year ended December ... | wrong_number: Says 2023 inventory turns were 2.7; the filing says 3.1. 2.7 is the 2022 figure from the next sentence. The error understates the decline, so it did not push the call toward decrease. |
| PTEN | 2 | paraphrase | 0.80 | During the third quarter of 2024, we viewed the reduction in activity forecasts combined with the recent decli... | stitched: First sentence verbatim from the MD&A; the $885 million goodwill charge is reworded from a later MD&A sentence. Facts match the filing. |
| HRTG | 3 | paraphrase | 0.81 | The net combined ratio was 94.2% for the year ended December 31, 2024, a 2.1 point improvement from 96.3% in t... | paraphrase: Light rewording ('net combined ratio of 94.2%' became 'was 94.2% for the year ended December 31, 2024'); all figures match. |
| AEP | 2 | paraphrase | 0.83 | In November 2024, AEP announced a five-year, $54 billion capital investment plan that continues to build the e... | paraphrase: From the strategy section, outside the MD&A. 'In November 2024, AEP announced' was added; the same 10-K gives that date elsewhere. |
| ARHS | 1 | paraphrase | 0.89 | The decrease [in net revenue] was driven primarily by the non-recurrence of prior year abnormal backlog delive... | paraphrase: Verbatim except for an editorial insertion, '[in net revenue]'. |
