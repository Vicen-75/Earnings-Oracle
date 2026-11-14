# Set B, stage 1: 100 companies

Pre-registered in docs/test_plan.md. Exact two-sided McNemar on correct answers; significant at p < 0.005. V6 beats the baselines only if it is significantly better than all three. No answer counts as wrong.

| Version | Correct | Decrease calls | No answer |
| --- | --- | --- | --- |
| V6 (three runs averaged) | 65 (65.0%) | 39 (21 right) | 0 |
| Always increase | 62 (62.0%) | 0 (0 right) | 0 |
| Momentum | 56 (56.0%) | 32 (13 right) | 0 |
| Reverse momentum | 44 (44.0%) | 68 (25 right) | 0 |

| V6 against | V6 only right | Baseline only right | p | Significant |
| --- | --- | --- | --- | --- |
| Always increase | 21 | 18 | 0.7493 | no |
| Momentum | 20 | 11 | 0.1496 | no |
| Reverse momentum | 45 | 24 | 0.0154 | no |

**Result: V6 does not beat all three baselines (not yet significant; stage 2 decides).**
