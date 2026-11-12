# Test plan: the 200-company backtest

Written Nov 6, 2026, before the test set was drawn and before any model run on it. This file, `eval/universe.csv` (the
random order) and the code below are committed first; the commit date is the record that nothing was chosen after
seeing results. Any later change gets a dated note at the bottom.

## Why

The first backtest (Nov 5, 20 companies, prompt V5) scored 15 of 20, against 11 for always-increase and 8 for momentum.
With 20 companies that is not evidence: only the companies where the model and a baseline disagree count (6 against
always-increase), and the 95% interval on accuracy is about ±19 points. A simulation with the pilot's rates showed that
200 companies give about an 85% chance of detecting a real edge even if the model wins only 65 to 70% of disagreements,
and an interval of about ±6 points. Repeat runs on the same companies would not help; only more companies do.

## Sets

| Set | Companies | Use |
|---|---|---|
| Development | the 20 in `eval/test_set.csv` | trying prompt changes; the Tests tab |
| Test | 200 in `eval/test_set_200.csv` | run once per finished prompt version; the reported result |

Prompt changes are tried on the development set only, so the prompt is never tuned to the test set.

## How the 200 are chosen (`eval/build_test_set.py`)

1. **Universe.** SEC frames API, calendar 2024: every filer with a US address, revenue of at least $500M, and operating
   income or pre-tax income reported, with a ticker on EDGAR. Shuffled with seed 883. No hand picking.
2. **Data gate** (EDGAR only), in the shuffled order:
   - a 10-K for a fiscal year ending between 2025-07-01 and 2026-06-30 (the target year; same window as
     `docs/success_metric.md`), and the 10-K for the year before it, about one year earlier;
   - the target metric reported for the target year, the prior year and the year before that (the momentum baseline
     needs three years).
3. **Contamination gate** (3 short model calls, `eval/contamination.py`): the model, asked from memory, must not know the
   target year's result or any quarter of it. Verdicts OK and OK_BUT_UNKNOWN_COMPANY pass.
4. The first 200 companies, in the shuffled order, that pass both gates form the test set.

Every company tried is recorded in `eval/sample_checks.csv` with the reason it passed or failed.

## Definitions

- **Target metric:** operating income; pre-tax income from continuing operations for companies that report no operating
  income line (banks, insurers and some others), as in `edgar.choose_target`. Banks and insurers stay in.
- **Truth:** `increase` if the target year's value is strictly greater than the prior year's, else `decrease`.
- **Hidden year:** every tool hides the target year's 10-K and anything filed after it (`skip_newest` per company: 1
  normally, 2 when the following year's 10-K is already filed).
- **Prediction:** the direction parsed from the agent's answer. A missing or unparseable direction counts as wrong.
- **Mode:** named (company names visible). The anonymizer is not built yet; when it is, the anonymized run is a
  second, separate result on the same 200.

## Baselines (fixed when the set is built, stored in `eval/test_set_200.csv`)

- **Always increase.**
- **Momentum:** the direction of the target metric from two years before to the prior year.
- **Reverse momentum:** the opposite of momentum. Added because direction reversed in 12 of the pilot's 20 companies.

## Analysis (`eval/analyze_backtest.py`)

- **Main result:** model accuracy vs each baseline on the same companies, with an exact two-sided McNemar test (a
  binomial test on the companies where the two disagree), significance level 0.05. The model "beats the baselines" only
  if it is significantly better than **all three**.
- **Also reported:** accuracy with 95% Wilson intervals, the confusion table, calibration (accuracy by stated probability
  band), and accuracy by target metric and by industry group (descriptive only, groups are small).

## Known limits, stated up front

- Excluding companies the model remembers tilts the sample toward less famous companies. The result holds for companies
  the model had no memory of for the target year.
- The contamination probe relies on the model saying what it remembers; it can miss a leak.
- One target window (one economic year). A year with many reversals favors reverse momentum; that is why it is a
  baseline.

## Running it

```
python -m eval.build_test_set universe      # writes eval/universe.csv; commit it with this file
python -m eval.build_test_set check         # the two gates; about 900 short model calls, resumable
python -m eval.run_backtest                 # the 200 runs; about 1,100 model calls, resumable
python -m eval.analyze_backtest             # writes eval/backtest_200_report.md
```

With 3 keys (about 1,500 calls a day on the free tier), plan one day for the gates and one for the runs.

## Changes after this date

### Nov 10, 2026: set B, a fresh test for V6, in two stages

Written before any company in set B is checked and before V6 exists. The commit that adds this note, the set B code in
`eval/build_test_set.py` and nothing from set B's runs is the record that the companies, the version scored and the
analysis were fixed in advance.

**Why.** V5 on the 200 above did not beat always-increase. The changes planned for V6 come from reading V5's answers on
those 200 (`eval/error_analysis_200.md`, issue #54), so a V6 score on the same companies would be inflated. V6 is scored
on companies nobody has looked at.

**Set B.** Same universe, same shuffled order (seed 883), same two gates, same definitions, target window, truth rule
and baselines as above. It starts at universe order 218, right after set A's 200th company (HGV, order 217), and
skips the companies of the development set and of set A. The first 200 companies that pass both gates form set B.
Files: `eval/sample_checks_b.csv` and `eval/test_set_200b.csv` (`python -m eval.build_test_set check --set b`).

**What is scored.** V6 is the agent (prompt and code) at the commit tagged `v6-frozen`, made before the first run on set
B. Until then V6 is tried on the 20-company development set only. After the tag nothing changes: no prompt edits, no
reruns of companies that came out wrong. Named mode and thinking level as in V5. A run that fails or gives no direction
counts as wrong; a run stopped by a quota or network error is retried, since no answer was seen.

**Main result.** As above: V6 against each of the three baselines on the same companies, exact two-sided McNemar test.
V6 "beats the baselines" only if it is significantly better than all three.

**Two stages** (group sequential design, Haybittle-Peto boundaries):

| Stage | Companies | Analysed when | Significance threshold, each comparison | Reported |
|---|---|---|---|---|
| 1 | the first 100 of set B, in set order | all 100 are done | p < 0.005 | Nov 16 presentation |
| 2 | all 200 | all 200 are done | p < 0.048 | Nov 30 report |

- Stage 2 is run and reported whatever stage 1 shows. A stage 1 result below 0.005 is reported as significant; a stage
  1 result above it is reported as "not yet significant", not as a failure.
- These are the only two looks at accuracy. While the runs are going, only errors and progress are watched: the
  runner prints no correct or wrong per company for set B.
- With these thresholds the chance of a false "V6 is better" across both looks stays under 5% (1.8% for this exact
  test, by simulation).

**Power, stated up front** (simulation, assuming V6 and always-increase disagree on 26% of companies, as V5 did):

| V6 accuracy gain over always-increase | Stage 1 significant | Stage 2 significant |
|---|---|---|
| +8 points | 7% | 53% |
| +10 points | 17% | 80% |
| +13 points | 34% | 95% |
| +16 points | 57% | 99% |

Stage 1 detects only a large improvement. The stage 2 result is the one the project stands on.

**Secondary, not part of the test.** If keys allow, V5 also runs on set B. That gives V5's accuracy on fresh companies
and a V6 vs V5 McNemar comparison, both reported as descriptive.

**Known limits.** Set B has the same target year as set A, so it is a second sample from one economic year, not a test
on a different year. Set B is drawn later in the same random order, so it is a fresh random sample from the same
universe, with the same tilt toward companies the model does not remember.

### Nov 10, 2026: ablation on set A, does the MD&A add anything? (issue #52)

Written before the ablation run.

**Question.** Is V5 more accurate when it can read the MD&A than when it cannot, on the same companies?

**Run.** Set A (the same 200 companies), prompt V5, same model, thinking level and hidden-year rule as the Nov 6 run.
The only changes: the two MD&A tools (`get_mdna`, `locate_mdna`) are removed, a note in the instructions says they are
not available, and the self-check asks about ratios instead of the MD&A (`src/agent.py`, `ABLATIONS["no_mdna"]`). The
empty-answer fix (#60) is not included, so both runs share the same failure modes. Results:
`eval/ablation_no_mdna_results.jsonl`.

**Comparison.** V5's Nov 6 answers on set A against the ablation's answers, exact two-sided McNemar test, p < 0.05. A
missing answer counts as wrong. Also reported, descriptive only: each run against always-increase, the confusion of
calls, decrease-call precision, calibration, and cost per run (`eval/ablation_report.py`).

**Known limits.** The two runs are days apart, and at temperature 0 the model still varies from run to run (#51), so
some disagreements would appear even with identical tools. Set A's answers were read for the error analysis, but no
choice in this ablation depends on them.

### Nov 10, 2026: second ablation on set A, do the ratios add anything? (issue #52)

Written after the first ablation's results and before this run.

**Question.** Is V5 more accurate with the ratio tool than without it, on the same companies?

**Run.** As the first ablation, with the other tool removed: the ratio tool (`compute_ratios`) goes; the company card,
the industry playbook and both MD&A tools stay. A note in the instructions says the ratio tool is not available, and
the self-check asks the model to reread the MD&A for a statement that contradicts its call (`src/agent.py`,
`ABLATIONS["no_ratios"]`). Results: `eval/ablation_no_ratios_results.jsonl`.

**Comparison.** V5's Nov 6 answers on set A against this run's, exact two-sided McNemar test, p < 0.05, missing answer
counts as wrong; the same descriptive tables as the first ablation. The exploratory breakdown in
`eval/ablation_report.py` was chosen after seeing the first ablation, so for this run too it explains, it does not
test.

**Known limits.** As the first ablation. In addition, the MD&A itself reports last year's figures, so this measures
what the computed, comparable ratios add, not what numbers add in general.
