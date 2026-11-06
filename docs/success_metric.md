# Success metric — Earnings Oracle

Fixed at the workshop checkpoint, Thu Oct 22, 2026 (§4.3, §5.5). Any later change gets a dated note below this section and an explanation in the report.

## The one number

**Directional accuracy, anonymized:** the share of the 20 scored test companies for which the app's predicted direction of FY2025 operating income (increase or decrease versus FY2024) matches the direction actually reported in the FY2025 10-K, with the company name, ticker and product names removed from everything the model sees.

## Definitions

**Prediction.** The app reads the FY2023 and FY2024 10-Ks only and returns `increase` or `decrease` with a probability. Direction is what is scored; the probability is reported but not part of the metric. A probability of exactly 0.5 counts as `increase`.

**Truth.** From the EDGAR XBRL `OperatingIncomeLoss` value in the FY2025 10-K compared with FY2024, as returned by `annual_operating_income()` in `src/edgar.py`. `increase` means strictly greater; equal or lower is `decrease`. For companies where that tag is absent (banks, insurers), the substitute tag is fixed in `eval/test_set.csv` before any prediction is run and is used for both prediction inputs and truth.

**Scored set.** 20 companies, listed in `eval/test_set.csv` before the first backtest, each with (a) at least two 10-Ks on EDGAR covering FY2023 and FY2024, (b) a FY2025 10-K already filed, and (c) a pass on the contamination test (`eval/contamination.py`): the model, asked from memory, does not claim to know the FY2025 full-year result **or any quarter of FY2025**. The quarter probe matters because the model's cutoff can fall inside FY2025: it may answer "unknown" for the full year while holding two or three quarters of it, which already gives away the direction. First runs on Oct 19, 2026 showed the model knows FY2024 results for AAPL and MSFT but reports FY2025 as unknown, so the cutoff sits inside the window where quarters can leak. A control probe on FY2024 confirms the model has heard of the company at all. Companies that fail (c) are replaced, and the replacements are recorded in `eval/contamination_results.csv`. The set spans at least four industries and includes at least two financial firms (a bank and an insurer) unless the ratio calculator cannot handle them, in which case the cut is recorded in slot 2 and the report.

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


## Dated notes (changes after Oct 22)

The text above is the metric as fixed on Oct 22 and is left unchanged. Each note below says what changed, why, and where it is implemented.

### Nov 6, 2026

1. **Two test sets; the reported result moves to 200 companies.** The first backtest on the 20 (Nov 5, prompt V5, named) scored 15/20 against 11/20 for always-increase and 8/20 for momentum. With n = 20 that is not evidence: only 6 companies separated the model from always-increase, and the 95% interval on accuracy is about ±19 points. The 20 in `eval/test_set.csv` become the **development set** (for trying prompt changes); the reported result is a **200-company test set** (`eval/test_set_200.csv`), with the design, gates and analysis fixed in advance in `docs/test_plan.md`. Everything above that says "the same 20" now applies to the 200.
2. **How test companies are chosen.** Hand-picked S&P 500 and mid-cap candidates are replaced by a random draw: US filers with revenue of at least $500M in 2024, from the SEC frames API, shuffled with seed 883 (`eval/universe.csv`, committed before any model run). The same gates apply: data available, and the contamination test (full year, quarters, control year). Every company tried and the reason it passed or failed is in `eval/sample_checks.csv`.
3. **Target year, defined by date.** "FY2025" means the fiscal year ending between 2025-07-01 and 2026-06-30, so every company has exactly one. Inputs are the 10-Ks before it, selected by date: every tool hides the target year's 10-K and anything filed after it (`skip_newest`, stored per company), instead of listing accession numbers.
4. **Target metric for banks and insurers.** The substitute is fixed in code: pre-tax income from continuing operations when a company reports no `OperatingIncomeLoss` (`edgar.choose_target`), used for inputs, truth and baselines alike, and stored per company in the `target` column. Banks and insurers stay in (39 of the 200 use pre-tax income).
5. **Baselines.** The ratio-only `baseline_direction()` was not built. The ratio-only comparison is **momentum** instead: a fixed rule on the target metric, with no model call (next year moves the way last year did; `src/baseline.py`). **Reverse momentum** is added, because direction reversed in 12 of the first 20 companies. The model "beats the baselines" only if it is significantly better than all three on the same companies (exact McNemar test, 0.05), as set in `docs/test_plan.md`.
6. **Named before anonymized.** The anonymizer is not built yet (issue #27), so the first runs are named. The headline metric stays anonymized accuracy; it will be reported, with the named-vs-anonymized gap, once #27 and #41 are done.
7. **Before-and-after.** `PROMPT_V1` to `PROMPT_V2` is superseded: the prompts are now `TOOL_SYSTEM_V3` to `V5` (`src/prompts.py`, V5 the default). The comparison is V5 against a V6, tried on the 20 and measured once on the 200 (issue #45).
8. **Robustness set.** The invalid-ticker case now expects a helpful answer (suggesting the company the user likely meant) instead of only an error (issue #50).
