# Error analysis: set A, prompt V6, one run per company

Exploratory and in-sample. V6 was designed from V5's errors on these same companies (`eval/error_analysis_200.md`,
issue #54), so its score here is optimistic. This analysis looks for broken reasoning (mechanisms) to fix in V7. It
does not fit anything to set A's outcomes: no thresholds, base rates or nudges toward a direction (docs/test_plan.md).
Set B, scored once on companies nobody has looked at, stays the test.

Run: `python -m eval.run_backtest --prompt V6 --runs 1`, Nov 11, 2026. Results: `eval/backtest_200_v6_results.jsonl`,
traces: `eval/backtest_200_v6_runs.jsonl`. 199 of 200 companies (FOSL failed on a Google server error).

## 1. The result

| Same 199 companies | Correct | V6 only right / other only right | McNemar p |
|---|---|---|---|
| V6 | 128 (64.3%) | | |
| V5 | 120 | 27 / 19 | 0.30 |
| Always increase | 125 | 38 / 35 | 0.82 |
| Momentum | 103 | 48 / 23 | 0.004 |
| Reverse momentum | 96 | 80 / 48 | 0.006 |

| Last year, this year | Companies | V5 correct | V6 correct |
|---|---|---|---|
| rose, rose | 79 | 69 | 64 |
| rose, fell | 50 | 11 | 22 |
| fell, rose | 46 | 27 | 26 |
| fell, fell | 24 | 13 | 16 |

- V6 did what it was built to do: it caught twice as many good years turning bad (22 vs 11), gave an answer every time
  (V5: 4 empty), and repeated last year's direction less often (128 vs 138).
- It paid for it on companies that kept rising (64 vs 69). Of the 19 companies V5 got right and V6 got wrong, 18 are
  decrease calls on companies whose income rose.
- Its probabilities mean something: calls at 0.60-0.70 were right 56% of the time, 0.70-0.80 70%, above 0.80 82%.

**The bottleneck is the decrease call.** V6 called decrease 73 times and was right 38 times (52%; V5 24 of 50, 48%).
With increases about 63% of the time, a decrease call that is right half the time is no better than always-increase.
The increase calls are fine (90 of 126, 71%).

## 2. What drives a right or wrong call

Each rationale tagged by keywords (`re` patterns in the analysis; groups overlap; descriptive only).

| Rationale rests on | Increase calls | Right | Decrease calls | Right |
|---|---|---|---|---|
| A one-off item not recurring | 67 | 81% | 24 | 67% |
| Margins expanding | 33 | 76% | 4 | 2 of 4 |
| Guidance or outlook | 54 | 70% | 41 | 51% |
| Ratios worsening last year | 13 | 69% | 20 | 45% |
| **Costs or investment rising** | 33 | 73% | **16** | **31%** |

One-off reasoning, the V6 component added from #54, is the strongest signal in both directions. The weak spot is
specific: decrease calls built on rising costs or on last year's ratios.

## 3. Mechanisms behind the wrong decrease calls (35 read by hand)

**A. Cost guidance read as income guidance (11 of the 16 calls of this kind were wrong).** Management says operating
expenses will rise to support growth (headcount, R&D, marketing, new stores, a new segment), and the model calls
decrease without weighing those costs against revenue that is also growing. Growth companies say this every year.
Examples: KVYO ("rising costs across all major categories"), INSP, EXPO, PRLB, LMND, PGNY, UI, FRHC, NXH, BKE; FTNT
is the same pattern with explicit margin guidance. All had income rise.

**B. Last year's ratios counted as a near-term negative (8 calls rest on them with no guidance; 3 right).** The
downward rules say a trend alone justifies no call, but worsening ratios (inventory turnover down, SG&A share up,
margins compressed) get presented as "concrete negatives", so the rule is bypassed. Examples: CATO, BKE, BELFA, ROK,
SCI; AMC, MOS, AMKR, CIEN, QUAD lean the same way. Most were companies at a low point that recovered.

**C. Reported vs underlying (1 case, but a clear error).** SIRI: the rationale says reported operating income "will
mathematically increase" because a large impairment will not recur, then calls decrease on underlying profit. The
target is the reported figure. (When the model talks about underlying profit it is usually right: 15 of 17.)

**D. Negative guidance that turned out wrong (4).** KSS, NKE, AIZ, OPAD: management guided down and results came in
higher. Not fixable from the 10-K.

**Semiconductors and hardware: 0 of 5 decrease calls right** (BELFA, CIEN, AMKR, UI, FTNT; TXN on the dev set too).
These are mechanisms A and B at a cyclical low point. This must not be fixed with an industry rule: knowing that
chip companies recovered in this year is knowledge of the year being predicted, and set B predicts the same year.

## 4. Wrong increase calls (36)

- **Rising trend extended (about 15):** margin expansion or a recovery assumed to continue (ECL, NTRA, TXRH, HALO,
  ZBRA, WSM, GTES, NEU, TROX, GTBIF, CHE, AM). The same failure V5 had; V6 reduced it but did not remove it.
- **One-off bets that lost (8 of 67):** a charge that will not recur, but the business weakened more (HRI, STKS, IVZ,
  AHCO, HXL, AESI, PRM, BHE). An 81% hit rate; these are reasonable bets.
- **A named negative outweighed (about 6):** UNM (reinsurance deal expected to reduce income), ESI (divestiture
  removes a segment's income), HOV and ORA (last year's one-time gain will not recur), TXRH, PEBO.
- **Positive guidance that turned out wrong (about 5):** IOSP, ANDE, KNF, MLR, GTES.

## 5. Implications for V7 (to be agreed before any build)

Fixes for mechanisms only, worded as reasoning rules that hold in any year:

1. **Costs against revenue.** A planned cost increase is evidence of lower income only if it is expected to grow
   faster than revenue (or revenue is expected to fall). Compare the two before counting it. (Mechanism A.)
2. **Ratios describe last year.** A ratio that worsened last year is part of the trend, not a near-term negative,
   unless management ties it to next year (guidance, a markdown plan, a stated cost action). (Mechanism B.)
3. **The target is reported.** A charge last year that will not recur raises next year's reported figure even if the
   underlying business weakens; a one-time gain lowers it. (Mechanism C; also the HOV and ORA misses.)
4. **Changes in scope.** A divestiture removes that business's income; an acquisition adds it. (ESI; small.)

Not for V7: industry rules (semiconductors), any threshold or base rate, or a nudge toward increase or decrease. Those
would carry set A's year into set B.

**Rough size, in-sample and optimistic:** 23 decrease calls rest on mechanisms A or B, and 8 of them were right. If
all 23 turned into increase calls, V6 would go from 128 to 135 on set A (68%, 10 points over always-increase); the
ceiling, where the fix catches only the 15 wrong ones, is 143. In practice a fix catches part of them, and fresh
companies will show less. Set C (fresh companies) decides between V6 and V7.

## Known limits

Keyword tags are rough and overlap; the hand reading covers all 35 wrong decrease calls and all 36 wrong increase
calls, but the tags in section 2 cover every call only approximately. V6 ran once per company at temperature 1.0, so
some calls near 0.6 would flip on a rerun. Set A was already read for #54, and this is the second design pass over it.
