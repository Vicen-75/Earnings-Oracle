# Contamination test: does the model already remember the answer?

Issue #42. Owner: Vicente (test design and first runs, Oct 19 to 23); Javier (quarter probe, 200-company sampler).
Code: `eval/contamination.py`. Results: `eval/contamination_results.csv` (hand-picked candidates) and
`eval/sample_checks.csv` (200-company sampler). 

## Why

The app predicts whether next year's operating income rises or falls. In a backtest the "next year" has already
happened. If Gemini read about that result during training, a correct prediction could come from memory instead of
from reading the 10-K, and the accuracy number would measure memory. The proposal feedback (Oct 12) asked us to test
for this directly before choosing the test set.

## How it works

For each company the script asks the model three questions from memory only, with no document attached
(temperature 0, answer forced into a Pydantic schema so code can compare it with the truth):

| Probe | Question | Why |
|---|---|---|
| Full year | Operating income of the target year, and did it rise or fall? | The direct leak. |
| Quarters | Which quarters of the target year do you remember, and what is the latest period you know? | Added after feedback: two or three known quarters already give away the full-year direction. |
| Control | Operating income of the year before the target year | Checks that the model knows the company at all, so an "unknown" on the target year means something. |

The truth comes from EDGAR XBRL (`OperatingIncomeLoss`, full fiscal years only), not from the model.

| Verdict | Rule | Used in tests? |
|---|---|---|
| CONTAMINATED_FULL_YEAR | Claims to know the target year and gets the direction right | No |
| CONTAMINATED_QUARTERS | Knows any quarter of the target year, or remembers any period after the prior year end | No |
| OK | Knows the control year, not the target year | Yes |
| OK_BUT_UNKNOWN_COMPANY | Knows neither year | Yes, with the caveat below |
| NO_OPERATING_INCOME_TAG / NO_TARGET_YEAR | EDGAR data missing | No (data problem, not contamination) |

## What we found, in order

**Oct 19, first probe (AAPL, MSFT).** The model knew both FY2024 results (MSFT 109.43 B, exactly right; AAPL
134.01 B against a real 123.22 B, a confident wrong number) and answered "unknown" for FY2025. So its knowledge ends
somewhere inside 2025, where quarters can leak. This is why the quarter probe was added.

**Oct 22, 24 hand-picked candidates, target FY2025.** 10 usable, 5 contaminated through quarters (AAPL, MSFT, SBUX,
UNP, CSCO: two or three FY2025 quarters known), 7 with no `OperatingIncomeLoss` tag (including KO, XOM, PFE, NKE,
not only banks), 2 with no target year (DE stopped using the tag after FY2024, ETN after 2019). The candidate file
has since grown to 48 rows: 31 usable, 6 contaminated (FAST added), 8 without the tag, 3 without a target year.

**Oct 23, older model.** We tried to switch to a Gemini 2.5 model, whose training would end before the target year.
Both `gemini-2.5-flash` and `gemini-2.5-flash-lite` returned 404, "no longer available to new users". Not an option on
our accounts.

**Latest period the model remembers.** In the candidate runs, the latest period any company was remembered up to is
2025-09-30 (UNP, FAST). That date sets the risk: a target year ending in December 2025 overlaps the model's memory.

**Nov 5 to 6, 200-company sampler (`eval/build_test_set.py`).** Companies drawn at random (seed 883) with a fiscal
year ending between 2025-07-01 and 2026-06-30. Of 222 checked, 205 passed, 13 failed on data and 4 on
contamination (AAL, APD, DXCM, BDX, all through quarters). The 200 kept: 191 OK_BUT_UNKNOWN_COMPANY, 9 OK; 126 increase, 74 decrease.

## What it changed in the project

1. Contaminated companies never enter a test set.
2. The quarter probe is part of the gate, not just the full-year question.
3. Banks, insurers and other firms without an operating income line use pre-tax income as the target (`edgar.choose_target`).
4. A second check that does not rely on the model's own word is still needed: the anonymized run (#41).

## Limits

- **The test relies on what the model says it remembers.** It can deny knowing something it does know. Example:
  it claims not to know McDonald's FY2024 operating income, which is not believable for one of the best-known
  companies in the world.
- **OK_BUT_UNKNOWN_COMPANY is 95.5% of the 200-company set (191 of 200).** For those the control probe tells us nothing: we cannot
  separate "the model does not know this company" from "the model is being cautious". This is the main weakness.
- **Excluding remembered companies tilts the sample toward less famous firms.** Results hold for companies the model
  did not remember, not for the whole market.
- **It cannot see indirect knowledge:** news, guidance or analyst comments about the target year that never mention
  a number.

## How to run it

```
python -m eval.contamination              # the candidates in eval/candidates.csv; resumes, retries failed ones
python -m eval.contamination --fresh      # ignore previous results and check every candidate again
python -m eval.contamination AAPL MSFT    # quick check, nothing saved
```
