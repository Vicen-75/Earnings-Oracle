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

### Nov 11, 2026: V6 and its component ablation on set B (issue #45)

Written before V6 is frozen and before any V6 run on set B. Completes the Nov 10 set B note: what V6 is, how its call
is made, and a secondary test of which of its parts matter. The main result, the two stages and their thresholds are
unchanged.

**What V6 is.** Prompt V6 (`src/prompts.py`, `build_v6`) and the agent at the commit tagged `v6-frozen`. Changes from
V5, one switch per component:

| # | Component | In the code |
|---|---|---|
| 1 | Structured pass over the MD&A | the `read_mdna_items` tool lists guidance, last year's one-offs, headwinds, tailwinds and segment trends, each with a quote checked word for word against the MD&A (`src/mdna_items.py`); the model chooses whether to call it, `get_mdna` stays |
| 2 | One-off adjustment | a paragraph: judge next year against last year with unusual gains and charges set aside |
| 3 | Downward rules | replaces V5's "weigh the evidence" paragraph: a trend alone justifies neither a call nor a probability above 0.60; a concrete near-term negative is sized against the positives; the strongest evidence against is never "none" |
| 4 | Three runs, averaged | each company runs three times at temperature 1.0 (`src/consensus.py`) |
| 5 | Decision rule | the prompt asks for the direction the model would take even odds on; the averaged probability of an increase decides the call, and a tie goes to decrease. No threshold is tuned |
| 6 | Empty-answer fallback | #60 |

V5 and every earlier prompt keep temperature 0 and never see the new tool. Nothing in V6 is a number learned from set
A's or set B's outcomes: no base rate, no industry rate, no threshold.

**V6's call on a company.** Each run's direction and probability become a probability of an increase (p for an
increase call, 1 - p for a decrease call). The mean over the runs that gave both a direction and a probability decides:
increase above 0.5, decrease at or below it. If no run gives both, the company has no answer and counts as wrong. A run
stopped by a quota or network error is retried with the company's other runs. The main result in the Nov 10 note uses
this call.

**Component ablation (secondary, not part of the main test).**

| Arm | V6 with this removed | Compared with | Extra runs on set B |
|---|---|---|---|
| Self-consistency | run 1 alone | V6's averaged call | none: same records |
| Decision rule | majority vote of the three directions (a tie of one against one, when a run fails, goes to decrease) | V6's averaged call | none: same records |
| Downward rules | V5's "weigh the evidence" paragraph back (`--ablation no_downward`) | V6 run 1 | 200 |
| One-off adjustment | the one-off paragraph removed (`--ablation no_oneoff`) | V6 run 1 | 200 |
| Structured pass | the `read_mdna_items` tool removed; the V6 rules work inside V5's agent loop (`--ablation no_structured`) | V6 run 1 | 200 |

- Each arm runs once per company on all 200 companies of set B, blind like the main run, at V6's temperature and with
  the same frozen code. Results: `eval/ablation_b_<arm>_results.jsonl`.
- **Test.** For each arm, exact two-sided McNemar test of correct answers against its comparison, on all 200
  companies. Holm correction across the five arms, family-wise alpha 0.05. A missing answer counts as wrong.
- **When.** Only after stage 2 is analysed. The arms may run before that, but no arm's accuracy is looked at earlier.
- **Also reported, descriptive only:** for each arm, the number of decrease calls and how many were right, how many
  answers say the strongest evidence against is "none", and median tokens and seconds per run.
- **If keys run short,** arms run in this order: downward rules, one-off adjustment, structured pass. An arm that does
  not finish all 200 companies is reported as not run, not on part of the set.

**Known limits.** At temperature 1.0 two runs of the same version disagree on some companies by chance, so each arm's
difference must exceed run-to-run variation to show up; with 200 companies, small effects will read as "no clear
difference". Removing the one-off paragraph leaves `read_mdna_items` listing one-offs as information; the arm measures
the instruction, not the information. The structured-pass arm changes how the MD&A is read, not whether it is read.

### Nov 11, 2026 (later): V7, and the choice between V6 and V7 on set C

Written before set C is drawn and before any V6 or V7 run on it. Amends the two notes above: set B will score
whichever of V6 and V7 this choice picks, not V6 by default.

**Why.** V6 was tried on set A after the note above was written (one run per company, exploratory and in-sample:
128 of 199, V5 120, always-increase 125; `eval/error_analysis_v6.md`). Reading its errors showed two reasoning
mechanisms behind most wrong decrease calls. Set A has now informed the design twice, so set A cannot judge the
result; a fresh set does.

**V7.** V6 plus four reasoning rules, each on its own switch (`src/prompts.py`, `build_v7`): planned cost increases
count against income only if they outgrow revenue; ratios that worsened last year are part of the trend unless
management ties them to next year; the target is the reported figure, so one-offs move it; divestitures and
acquisitions change the income base. Same tools, temperature and three-run averaging as V6. Nothing in V7 is fitted
to an outcome: no threshold, base rate, industry rule or nudge toward a direction. On the development set V7 made the
same 20 calls as V6.

**Set C.** Same universe, shuffled order, gates, definitions and truth rule as sets A and B. It starts after set B's
last company (universe order 433) and skips the development set, set A and set B. The first 200 companies that pass
both gates form set C (`python -m eval.build_test_set check --set c`; `eval/test_set_200c.csv`).

**The choice.** V6 and V7 each run once per company on set C, blind (progress only). The version with more correct
answers is frozen and scored on set B; a tie goes to V6. A finished run with no direction counts as wrong; a run
stopped by a quota or network error is retried. The choice is made by `python -m eval.choose_version` only after
both versions have finished all 200; the McNemar comparison it prints is descriptive. Set C is used for this one
decision and never again, and no change is made to either version after its first set C run starts.

**Still to be fixed before set B runs** (a dated note): the tag of the frozen version, the new date of stage 1, and
the component ablation arms for the chosen version (for V7, also an arm with the four V7 rules switched off).

### Nov 12, 2026: set C chose V6; V6 is frozen for set B

Written after the set C choice and before any run on set B. Completes the notes above.

**Set C result** (`python -m eval.choose_version`; `eval/setc_results.jsonl`). V6 132 of 200, V7 129; they disagreed
on 23 companies (V6 only right 13, V7 only right 10; McNemar p = 0.68, descriptive). By the rule fixed before set C
was drawn, V6 is frozen. V7 stays in the code with its switches, as a documented attempt; it is not run on set B. Set
C is not used again.

**What is scored on set B.** V6, as defined in the Nov 11 note: prompt V6, the `read_mdna_items` tool, temperature
1.0, three runs per company averaged (`src/consensus.py`), the #60 fallback. Before the first set B run,
`eval/run_set_b.py` writes the SHA-256 of every file V6 depends on (all of `src/`, the runner, set B's list and this
plan) to `eval/v6_frozen_manifest.txt`, and it stops if any of them changes before a later step. The commit tagged
`v6-frozen` must contain exactly those files; nothing changes after it.

**Main result and stages.** Unchanged from the Nov 10 note: V6 against each of the three baselines, exact two-sided
McNemar; stage 1 on the first 100 companies at p < 0.005, stage 2 on all 200 at p < 0.048. Stage 1 runs from Nov 12
and is analysed once all 100 are done; if that happens before the Nov 16 presentation it is reported there,
otherwise the presentation reports it as pending. Stage 2 is reported in the Nov 30 report.

**Secondary test: V6 against V5** (replaces the Nov 10 note's descriptive "if keys allow" comparison). V5, unchanged
(prompt V5, temperature 0, one run per company), runs blind on all 200 companies of set B. V6's averaged call against
V5's call, exact two-sided McNemar on correct answers, p < 0.05, examined only after stage 2, together with the main
result. A missing answer counts as wrong for both. Not part of the "beats the baselines" claim. Power, stated up front:
on set A the two disagreed on 46 of 199 companies; with that many disagreements V6 needs about 31 of them (against 15)
for p < 0.05, so "no clear difference" is the likely outcome unless V6 is much better.

**Component ablation.** The five arms of the Nov 11 note, for V6, unchanged: self-consistency and decision rule from
V6's own records; downward rules, one-off adjustment and structured pass as one-run arms (`--ablation no_downward`,
`no_oneoff`, `no_structured`). Holm across the five arms, examined only after stage 2.

**Run order, if keys run short:** V6 stage 1, V6 stage 2, V5, then the ablation arms in the order downward rules,
one-off adjustment, structured pass. A comparison whose runs do not finish on all 200 companies is reported as not
run.

**Commands** (all of them in order, unattended: `python -m eval.run_set_b`; each one blind on set B):
- `python -m eval.run_backtest --set b --prompt V6 --limit 100` (stage 1), then without `--limit` (stage 2)
- `python -m eval.run_backtest --set b --prompt V5`
- `python -m eval.run_backtest --set b --prompt V6 --ablation no_downward` (and `no_oneoff`, `no_structured`)

### Nov 13, 2026: set D, 400 fresh companies for V6 with one run

Written after set B was analysed and before any company of set D is checked or run. Drafted with help from Claude; the
decisions are the team's.

**What is already known.** Set B, the pre-registered test: V6 135 of 200 against 123 for always increase (V6 only
right 46, always increase only right 34, p = 0.22), so V6 does not beat all three baselines. Set C, used to choose V6
over V7: V6 132 of 200 against 121 (42 against 31). On both sets V6 is about 6 points ahead, and neither result rules
out chance. Set B's ablation: one run alone scores the same as three runs averaged (135 and 135) at a third of the
cost (`eval/set_b_cost_variation_report.md`).

**Why set D.** One more test of whether V6 beats the baselines, on twice as many companies, and a tighter estimate of
how large the edge over always increase is.

**Companies.** The universe order (`eval/universe.csv`, fixed on Nov 5) continues from position 652, after the last
position checked for set C, through the same data and contamination gates as sets A, B and C
(`python -m eval.build_test_set check --set d`), until 400 companies pass. Companies of the development set and of
sets A, B and C are skipped. Every company tried is recorded in `eval/sample_checks_d.csv`; the accepted 400 are
`eval/test_set_400d.csv`. The runs start only when that list is final.

**What is scored.** V6 exactly as frozen for set B: the same prompt, tools and temperature (1.0), and the files under
`src/` must match `eval/v6_frozen_manifest.txt`, which the runner checks before every step. One difference, decided
here: one run per company instead of three averaged, because the set B ablation showed no gain from averaging and one
run is what the app would use. The runner is blind: it prints progress only.

**The test, one look.** When all 400 companies have a finished result: V6 against each of the three baselines on set
D alone, exact two-sided McNemar on correct answers, significant at p < 0.05. V6 beats the baselines only if it is
significantly better than all three. A company with no answer counts as wrong. No interim look, no early stop, and no
companies added afterwards. If the 400 runs are not complete, the test is reported as not run.

**Combined view, descriptive.** Sets B (run 1 of its three), C and D together: 800 companies V6 was not tuned on, one
run each, with the difference from always increase and an approximate 95% interval. This is not a second test. Sets B
and C were already known to favour V6 when this note was written (together: V6 only right 88, always increase only
right 65), so a combined p-value would cross 0.05 far more often than one time in twenty even with no real edge. The
combined numbers estimate the size of the edge; the verdict is the test on set D alone.

**Power, stated up front.** If V6's true edge over always increase is the 6 points seen so far and the two disagree on
about 40% of companies, set D alone reaches p < 0.05 somewhat less than half the time. "No clear difference" is a
likely outcome even if the edge is real.

**Timing.** If the runs finish and the analysis is done before the `presentation` tag on Nov 16, the result is
presented; otherwise it is reported as pending and goes in the Nov 30 report.

**Commands.** `python -m eval.run_set_d` (the set, then the runs, unattended; it does not start until this note and
the code are committed), then `python -m eval.analyze_set_d`, once.

**Files that were in the set B freeze.** `eval/run_backtest.py` gains a set D mode and this plan gains this note. Set
B is finished and the commit tagged `v6-frozen` is unchanged. No file under `src/` changes.
