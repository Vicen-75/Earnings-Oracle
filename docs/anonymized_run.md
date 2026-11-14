# The anonymized run: plan

Written Nov 12, 2026, before any anonymized run on the 200. Owner: German. The commit that adds this file and the code
below is the record that the analysis was fixed before seeing results.

## Why

The headline metric in `docs/success_metric.md` is anonymized accuracy, and the proposal feedback asked us to compare
accuracy with and without names to show the model reads rather than remembers. The 200-company result
(`eval/backtest_200_report.md`) is a named run. `docs/test_plan.md` already plans the anonymized run as a second,
separate result on the same 200. This file says how it is run and read.

## What is run

- **Companies, prompt and settings:** the same 200 in `eval/test_set_200.csv`, prompt V5, the same agent code and the
  same hidden years (`skip_newest` per company). Only the anonymizer is switched on.
- **Anonymizer** (`src/anonymize.py`): every tool result has the company name and former names replaced by
  "the Company", brand and product names by "[PRODUCT]", the ticker by "COMPANY" and the CIK by an alias. The SIC
  code, industry and all numbers stay visible. Brand names come from one extra model call per company.
- **Files:** `eval/backtest_200_anon_results.jsonl` and `eval/backtest_200_anon_runs.jsonl`, apart from the named
  run's files.

## How it is read

1. **Anonymized accuracy against the three baselines**, with the same exact McNemar test and 0.05 level as the named run
   (`python -m eval.analyze_backtest --anonymize`). This is the headline number.
2. **Named against anonymized on the same companies**, exact McNemar test (`python -m eval.named_vs_anon`).
   - Named clearly better: part of the named score comes from memory, and the anonymized number is the honest one.
   - No clear difference: consistent with reading, but not proof. Absence of a significant difference is not
     evidence of no difference.
3. **Can the model still tell which company it is?** On the 20 development companies (`eval/anonymize_check.csv`) the
   anonymized text was leak-free for 19 of 20, yet the model named the company for 17 of 20. So hiding the name often
   does not hide the company. `python -m eval.anonymize_check --set 200 --guess` measures this on the 200, and
   `eval/named_vs_anon.py` then splits the comparison into companies the model could and could not identify. The
   second group is the cleaner test. This split is exploratory, because the groups are smaller.

A company with a missing answer counts as wrong, as in the named run.

## Running it

```
python -m eval.run_backtest --anonymize --limit 3     # short trial first: check the answers parse
python -m eval.run_backtest --anonymize               # the rest; resumable
python -m eval.anonymize_check --set 200 --guess      # about 2 model calls per company
python -m eval.analyze_backtest --anonymize           # writes eval/backtest_200_anon_report.md
python -m eval.named_vs_anon                          # writes eval/named_vs_anon_report.md
```

About 1,300 model calls for the run and 400 for the check. With 3 keys on the free tier (about 1,500 calls a day),
plan a bit more than one day. The Tests tab in the app also has an anonymized toggle for the 20 development companies.
