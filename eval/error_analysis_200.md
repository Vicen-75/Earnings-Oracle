# Error analysis: 200-company backtest, prompt V5 (issue #54)

Exploratory, done after the pre-registered result (`eval/backtest_200_report.md`). It explains the result; it does not change it.

The model was wrong on 79 of 200: 49 times it said increase and income fell, 26 times it said decrease and income rose, and 4 times it gave no answer (the empty-final-turn bug).

## 1. The main failure: carrying last year's direction forward

The model agreed with momentum (last year's direction) on 139 of 200 companies. But in this sample last year's direction repeated only 104 times out of 200 (52%), so momentum is close to a coin flip.

| Last year | This year (truth) | Companies | Model said increase | Model correct | Accuracy |
|---|---|---|---|---|---|
| increase | increase | 80 | 70 | 70 | 88% |
| increase | decrease | 50 | 38 | 11 | 22% |
| decrease | increase | 46 | 27 | 27 | 59% |
| decrease | decrease | 24 | 11 | 13 | 54% |

56 of the 75 answered misses are cases where the model repeated last year's direction and the direction reversed. The worst cell is a rising year followed by a fall: the model still said increase most of the time.

| Model's call | Companies | Correct | Accuracy |
|---|---|---|---|
| Same direction as last year | 139 | 83 | 60% |
| Opposite direction to last year | 57 | 38 | 67% |

When the model breaks from the trend, it is right more often than when it follows it.

## 2. Why it was wrong: 35 misses read by hand

All 7 confident misses (p ≥ 0.80), plus the highest-probability misses in each direction. Tags and one-line notes are in `eval/error_analysis_tags.csv`.

| Failure type | Misses | Examples |
|---|---|---|
| Extended a rising trend with no specific reason it would continue | 10 | NTRA, ECL, HALO, GTBIF, ZBRA, WES, AFL, NEU, KNF, AENT |
| Named a concrete near-term negative, then called increase anyway | 7 | VST, CNC, OSCR, DKS, CI, UNM, MAX |
| Extended a falling trend and missed the turnaround | 6 | NXH, JBGS, PRG, TEAM, AMC, FAF |
| Bet that a one-off item would (or would not) repeat, and lost | 8 | ACHC, HXL, SAIC, PRM, DKL, EXR, IDCC, GEL |
| Followed management guidance; results went the other way | 4 | KSS, NKE, IBP, JNJ |

- **Trend extension (rising and falling) is the largest group.** The rationale reads like a description of last year (margin expansion, operating leverage, a recovery) with no specific driver for next year.
- **Overriding its own warning is the most fixable.** In each case the answer names a concrete, near-term negative (a $400M write-off at VST, a premium deficiency reserve at CNC, guidance for SG&A deleverage at DKS) and then outweighs it with general strengths. Four of the seven are health or life insurers.
- **One-off reasoning is mostly a strength.** See section 3: answers built on a one-off item are right more often than average. The losses here are reasonable bets.
- **Guidance misses are mostly unforecastable from the 10-K.** Management said lower; results came in higher. Guidance is usually a good signal (section 3), so there is little to fix here.

## 3. Which kinds of answers are right more often

Read from the answer text; descriptive only, groups overlap and are small.

| Answer | Companies | Correct | Accuracy |
|---|---|---|---|
| Rationale rests on a one-off item (charge, gain, catch-up revenue) | 36 | 26 | 72% |
| Rationale does not | 160 | 95 | 59% |
| Cites guidance or management's outlook | 136 | 91 | 67% |
| Does not | 60 | 30 | 50% |
| Says the strongest evidence against its call is 'None' | 7 | 4 | 57% |

| MD&A read (characters, both years) | Companies | Correct | Accuracy |
|---|---|---|---|
| Shortest quarter (under 89,460) | 49 | 23 | 47% |
| The other three quarters | 147 | 98 | 67% |

The self-check is meant to force a counterargument; 'None' still got through 7 times, all at a stated probability of 0.80 or more. Answers that read less MD&A text are right less often; worth checking whether those MD&As were cut short or are just short.

## 4. Size of the change

**This year's change (how close the outcome was)**

| Size of change | Companies | Correct | Accuracy |
|---|---|---|---|
| under 5% | 20 | 7 | 35% |
| 5% to 20% | 57 | 30 | 53% |
| 20% to 50% | 48 | 35 | 73% |
| 50% or more | 75 | 49 | 65% |

**Last year's change (how big the trend was)**

| Size of change | Companies | Correct | Accuracy |
|---|---|---|---|
| under 5% | 16 | 6 | 38% |
| 5% to 20% | 53 | 28 | 53% |
| 20% to 50% | 57 | 35 | 61% |
| 50% or more | 74 | 52 | 70% |

13 of the 79 misses are outcomes that moved less than 5% (13 wrong of 20 such companies). Those are close to coin flips and not worth chasing in V6. Accuracy rises with the size of the move.

Confident misses (p ≥ 0.80) and how much the target actually moved: ACHC -412%, NTRA -39%, HALO -15%, NKE +0%, IDCC +5%, ECL -2%, KSS +44%. The near-flat ones were close calls; the large ones are the real errors.

Truth labels re-checked against EDGAR: 200 match, 0 differ (none), 0 could not be re-checked (none).

## 5. Where the misses sit

| Group | Companies | Misses | Said increase, fell | Said decrease, rose |
|---|---|---|---|---|
| Target: operating income | 161 | 60 | 38 | 19 |
| Target: pretax income | 39 | 19 | 11 | 7 |
| general | 59 | 23 | 12 | 10 |
| industrials | 22 | 6 | 5 | 1 |
| retail | 17 | 9 | 4 | 4 |
| insurance | 16 | 9 | 6 | 2 |
| materials chemicals | 13 | 8 | 7 | 1 |
| software internet | 12 | 2 | 1 | 1 |
| utilities waste | 11 | 5 | 5 | 0 |
| semis hardware | 11 | 3 | 1 | 2 |
| banks | 8 | 3 | 2 | 1 |
| pharma medtech | 8 | 2 | 1 | 1 |
| consumer staples | 7 | 1 | 1 | 0 |
| energy mining | 7 | 4 | 2 | 2 |
| restaurants | 5 | 2 | 1 | 0 |
| transportation | 4 | 2 | 1 | 1 |

Misses lean toward 'said increase, income fell' in most groups, most clearly in materials and chemicals and in utilities. For insurers, the misses read by hand named medical cost or reserve pressure and then discounted it.

## 6. Measured against the base rate

The same companies scored three ways. A subset where the model looks good may simply be one where most companies grew.

| Companies | Count | Model | Always increase | Momentum |
|---|---|---|---|---|
| All | 200 | 60% | 63% | 52% |
| Model said increase | 146 | 66% | 66% | 55% |
| Model said decrease | 50 | 48% | 52% | 42% |
| Stated probability 0.80 or more | 34 | 79% | 74% | 62% |
| Stated probability 0.70 or more | 120 | 65% | 63% | 56% |
| Outcome moved 5% or more | 180 | 63% | 63% | 53% |

- **The decrease calls decide the result.** Every decrease call is a bet against a base rate of about 63% increases, so it adds value only if it is right more than half the time. V5's were right 24 of 50 (48%). They do point at weaker companies (only 52% of them grew, against 63% of all 200), but not weak enough to cross one half. That is why the model ties always-increase instead of beating it.
- **The increase calls pick growers only slightly better than chance.** On the two 'model said' rows, model and always-increase agree or disagree by definition; the useful comparison is the share that grew in that row against the share across all 200.
- **Calibration needs this caveat.** Confident calls are right more often, but always-increase is also right more often on those companies: the model's confidence mostly picks companies likely to grow. Report the top band next to the always-increase figure, not alone.

## 7. What this means for V6

Ranked by what it takes to beat always-increase: better decrease calls. Making the model call more reversals at today's precision would make things worse.

| Change | Misses it targets | Notes |
|---|---|---|
| When the answer names a concrete, near-term negative (a charge, a reserve, guidance for lower margin), make it size that item against the positives, and call decrease when the negative is larger | 7 of 35 read | The source of high-precision decrease calls: these were correct decreases the model talked itself out of. Especially insurers. |
| Treat last year's direction as weak evidence in both directions: a trend alone justifies neither a call nor a high probability, and a decrease call needs a specific driver | up to 56 (trend misses) | Aim is fewer confident trend calls, not more reversal calls (reverse momentum scored 48%). |
| Self-check must return a real counterargument; 'None' is not accepted | 3 wrong of 7 | Feeds the first change: the counterargument is where named negatives surface. |
| Fall back to the draft when the final turn is empty | 4 | Mechanical fix; drafts would have recovered 1 (CDP). |
| Keep: one-off reasoning | n/a | Right more often than average; do not prompt it away. |

**Testing V6 fairly.** These changes come from reading the 200 test answers, so a V6 score on the same 200 would be inflated. Try V6 on the 20-company development set, then score it once on a fresh set: the next 200 companies in the shuffled `eval/universe.csv` that pass both gates. Report V5 on the 200 as the pre-registered result and V6 on the fresh set as a separate result.
