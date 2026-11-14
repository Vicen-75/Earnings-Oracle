# Set B, stage 2: 200 companies

Pre-registered in docs/test_plan.md. Exact two-sided McNemar on correct answers; significant at p < 0.048. V6 beats the baselines only if it is significantly better than all three. No answer counts as wrong.

| Version | Correct | Decrease calls | No answer |
| --- | --- | --- | --- |
| V6 (three runs averaged) | 135 (67.5%) | 80 (46 right) | 0 |
| Always increase | 123 (61.5%) | 0 (0 right) | 0 |
| Momentum | 120 (60.0%) | 79 (38 right) | 0 |
| Reverse momentum | 80 (40.0%) | 121 (39 right) | 0 |

| V6 against | V6 only right | Baseline only right | p | Significant |
| --- | --- | --- | --- | --- |
| Always increase | 46 | 34 | 0.2185 | no |
| Momentum | 41 | 26 | 0.0864 | no |
| Reverse momentum | 94 | 39 | 0.0000 | yes |

**Result: V6 does not beat all three baselines.**

## Secondary: V6 against V5 (p < 0.05)

| Version | Correct | Decrease calls | No answer |
| --- | --- | --- | --- |
| V5 | 134 (67.0%) | 66 (39 right) | 1 |

V6 only right 23, V5 only right 22, p = 1.0000: no clear difference.

## Secondary: component ablation (Holm, family alpha 0.05)

| Arm | Arm correct | Arm decrease calls (right) | Reference only right | Arm only right | p | Significant (Holm) |
| --- | --- | --- | --- | --- | --- | --- |
| Self-consistency (run 1 alone vs averaged) | 135 | 80 (46) | 7 | 7 | 1.0000 | no |
| Decision rule (majority vote vs averaged) | 136 | 79 (46) | 0 | 1 | 1.0000 | no |
| Without the downward rules (vs V6 run 1) | 133 | 75 (43) | 10 | 8 | 0.8145 | no |
| Without the one-off adjustment (vs V6 run 1) | 132 | 82 (46) | 14 | 11 | 0.6900 | no |
| Without the structured MD&A pass (vs V6 run 1) | 131 | 70 (39) | 23 | 19 | 0.6440 | no |
