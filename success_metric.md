# Success metric — Earnings Oracle

Fixed at the workshop checkpoint, Thu Oct 22, 2026 (§4.3, §5.5). Any later change gets a dated note below this section and an explanation in the report.

## The one number

**Directional accuracy, anonymized:** the share of the 20 scored test companies for which the app's predicted direction of FY2025 operating income (increase or decrease versus FY2024) matches the direction actually reported in the FY2025 10-K, with the company name, ticker and product names removed from everything the model sees.

## Definitions

**Prediction.** The app reads the FY2023 and FY2024 10-Ks only and returns `increase` or `decrease` with a probability. Direction is what is scored; the probability is reported but not part of the metric. A probability of exactly 0.5 counts as `increase`.

**Truth.** From the EDGAR XBRL `OperatingIncomeLoss` value in the FY2025 10-K compared with FY2024, as returned by `annual_operating_income()` in `src/edgar.py`. `increase` means strictly greater; equal or lower is `decrease`. For companies where that tag is absent (banks, insurers), the substitute tag is fixed in `eval/test_set.csv` before any prediction is run and is used for both prediction inputs and truth.

**Scored set.** 20 companies, listed in `eval/test_set.csv` before the first backtest, each with (a) at least two 10-Ks on EDGAR covering FY2023 and FY2024, (b) a FY2025 10-K already filed, and (c) a pass on the contamination test (`eval/contamination.py`): the model, asked from memory, does not claim to know the FY2025 result. Companies that fail (c) are replaced, and the replacements are recorded. The set spans at least four industries and includes at least two financial firms (a bank and an insurer) unless the ratio calculator cannot handle them, in which case the cut is recorded in slot 2 and the report.

**Wrong answers.** A prediction of `no data found` for a company in the scored set counts as wrong. A parse failure that falls back to the ratio-only verdict is scored as whatever that verdict says, and the fallback is logged.

**Robustness set (not scored).** Four inputs the app must handle without crashing: an invalid ticker, a recently listed firm with one 10-K, a foreign filer with a 20-F, and a ticker whose MD&A cannot be extracted. The expected output for each is `no data found` or the ratio-only verdict with a visible "MD&A not found" message. These are reported as pass/fail in the report, separately from the accuracy number. This is a change from the proposal, which folded them into the 20; keeping them out stops three trivially correct "no data" answers from inflating accuracy.

## Comparisons, all on the same 20

1. **Named accuracy:** the same app with names left in. The gap between named and anonymized is the memorization check the feedback asked for; a large gap means the model was remembering, not reading.
2. **Ratio-only baseline:** `baseline_direction()` in `src/baseline.py`, a fixed transparent rule on the ratios alone, with no model call.
3. **Naive rule:** always predict `increase`.

The app is doing its job if anonymized accuracy beats both the ratio-only baseline and the naive rule on the same 20. With n = 20 each company is 5 points, so a 1-company difference is not evidence; the report will say so and give the counts, not just the percentages.

## Where the test inputs come from

The FY2023 and FY2024 10-K primary documents from EDGAR, by accession number, listed in `eval/test_set.csv`. Candidates are chosen from S&P 500 and mid-cap filers whose FY2025 10-K is already on EDGAR (fiscal year 2025 ending on or before Jun 30, 2026, so the filing is in by now); the contamination test then decides which stay.

## Before-and-after (§5.5 element 4)

One prompt change, `PROMPT_V1` to `PROMPT_V2`, measured on the same 20, anonymized. Nothing else moves between the two runs.
