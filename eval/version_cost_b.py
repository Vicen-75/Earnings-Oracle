# --- Javier: what one V6 run costs against V5, and how much V6 varies from run to run (code written with help from Claude) ---
# DESCRIPTIVE. Not in docs/test_plan.md: written on Nov 13, after the set B result was known, to help choose the version
# the app runs. It reads results already collected on set B. No model calls, no EDGAR calls, no results file is changed.
#
# Three questions, all on the same 200 companies of set B:
#   1. Cost and time. Tokens the model itself counted on every call of an analysis (usage["billed"]: main agent, the
#      structured MD&A pass, the MD&A locator, thinking), priced with the same rates as eval/cost_analysis.py.
#      V5 (one run) against one V6 run, three V6 runs, and V6 without the structured pass.
#   2. Run-to-run variation. V6 ran every company three times: how often do two runs of the same company call a
#      different direction, how accurate is each run alone, how far apart are the stated probabilities? For scale, the
#      same count against V6 run 1 for V5 and for each ablation arm: an arm that differs from run 1 no more often than
#      run 2 does has not been shown to change anything.
#   3. Tool use. How often each version called each tool, in particular V6's read_mdna_items (the structured pass).
# Seconds are from batch runs that shared free keys, so they include waits for rate limits: an upper bound for one user.
#
#   python -m eval.version_cost_b        # prints the report and writes eval/set_b_cost_variation_report.md
import csv
import json
import statistics
from itertools import combinations
from pathlib import Path

from eval.cost_analysis import MODEL_PRICE, cost_usd

SET_B = Path("eval/test_set_200b.csv")
MAIN = Path("eval/backtest_200b_results.jsonl")
ARMS = {"no_downward": ("V6 without the downward rules", Path("eval/ablation_b_no_downward_results.jsonl")),
        "no_oneoff": ("V6 without the one-off adjustment", Path("eval/ablation_b_no_oneoff_results.jsonl")),
        "no_structured": ("V6 without the structured pass", Path("eval/ablation_b_no_structured_results.jsonl"))}
REPORT = Path("eval/set_b_cost_variation_report.md")
DIRECTIONS = ("increase", "decrease")
TOOLS = ["get_company_card", "get_industry_playbook", "compute_ratios", "read_mdna_items", "get_mdna", "locate_mdna"]


def load(path, prompt, ablation=None):
    """Latest finished (non-error) record per ticker for this prompt and arm (None = the full agent)."""
    rows = {}
    if path.exists():
        for line in open(path, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("prompt") == prompt and not r.get("error") and (r.get("ablation") or None) == ablation:
                    rows[r["ticker"]] = r
    return rows


def measure(usages, seconds):
    """One analysis made of one or more runs: every billed call added up."""
    billed = [u.get("billed") or u for u in usages]
    return {"calls": sum(b.get("model_calls", 0) for b in billed),
            "tokens_in": sum(b.get("prompt_tokens", 0) for b in billed),
            "tokens_out": sum(b.get("output_tokens", 0) + b.get("thinking_tokens", 0) for b in billed),
            "usd": sum(cost_usd(b) for b in billed), "seconds": seconds}


def p90(values):
    values = sorted(values)
    return values[min(len(values) - 1, int(0.9 * len(values)))]


def direction_of(x):
    return x.get("direction") if x.get("direction") in DIRECTIONS else None


def p_increase(x):
    d, p = direction_of(x), x.get("probability")
    if d is None or not isinstance(p, (int, float)):
        return None
    return p if d == "increase" else 1 - p


def share(k, n):
    return f"{k} of {n} ({100 * k / n:.1f}%)" if n else "none"


def cost_section(tickers, v5, v6, arms):
    versions = {
        "V5, one run": {t: measure([v5[t]["usage"]], v5[t].get("seconds")) for t in tickers if v5.get(t, {}).get("usage")},
        "V6, one run (run 1)": {t: measure([v6[t]["runs"][0]["usage"]], v6[t]["runs"][0].get("seconds"))
                                for t in tickers if v6.get(t, {}).get("runs")},
        "V6, three runs": {t: measure([x["usage"] for x in v6[t]["runs"]],
                                      sum(x.get("seconds") or 0 for x in v6[t]["runs"]))
                           for t in tickers if v6.get(t, {}).get("runs")},
        "V6 without the structured pass, one run": {t: measure([arms["no_structured"][t]["usage"]],
                                                              arms["no_structured"][t].get("seconds"))
                                                    for t in tickers if arms["no_structured"].get(t, {}).get("usage")},
    }
    out = ["## 1. Cost and time per analysis", "",
           f"Prices: ${MODEL_PRICE['input_per_million']:.2f} per million input tokens, ${MODEL_PRICE['output_per_million']:.2f} "
           "per million output tokens, thinking billed as output (eval/cost_analysis.py). The app runs on the free "
           "tier; these are what a paid deployment would pay.", "",
           "| Version | Companies | Model calls, median | Input tokens, median | Output and thinking tokens, median | "
           "Cost, median | Cost, mean | Cost, 90th percentile | Seconds, median | Seconds, 90th percentile | "
           "Total for these companies |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, rows in versions.items():
        if not rows:
            out.append(f"| {name} | 0 | | | | | | | | | |")
            continue
        col = lambda k: [r[k] for r in rows.values() if r[k] is not None]
        out.append(f"| {name} | {len(rows)} | {statistics.median(col('calls')):g} | "
                   f"{statistics.median(col('tokens_in')):,.0f} | {statistics.median(col('tokens_out')):,.0f} | "
                   f"${statistics.median(col('usd')):.4f} | ${statistics.mean(col('usd')):.4f} | ${p90(col('usd')):.4f} | "
                   f"{statistics.median(col('seconds')):.0f} | {p90(col('seconds')):.0f} | ${sum(col('usd')):.2f} |")
    base = versions["V5, one run"]
    out.append("")
    for name in list(versions)[1:]:
        both = [t for t in tickers if t in base and t in versions[name] and base[t]["usd"] > 0]
        if both:
            ratios = [versions[name][t]["usd"] / base[t]["usd"] for t in both]
            cheaper = sum(r < 1 for r in ratios)
            out.append(f"- {name} against V5 on the same {len(both)} companies: the median company costs "
                       f"{statistics.median(ratios):.2f} times V5; cheaper than V5 for {share(cheaper, len(both))}.")
    return out + [""]


def variation_section(tickers, truth, v5, v6, arms):
    have = [t for t in tickers if v6.get(t, {}).get("runs")]
    n_runs = max((len(v6[t]["runs"]) for t in have), default=0)
    runs = {t: [direction_of(x) for x in v6[t]["runs"]] + [None] * (n_runs - len(v6[t]["runs"])) for t in have}
    out = ["## 2. How much V6 varies from run to run", "",
           f"{len(have)} companies, {n_runs} runs each, same prompt, same tools, temperature 1.0.", "",
           "| | Correct | Decrease calls | No answer |", "| --- | --- | --- | --- |"]
    for i in range(n_runs):
        d = [runs[t][i] for t in have]
        out.append(f"| Run {i + 1} alone | {share(sum(x == truth[t] for x, t in zip(d, have)), len(have))} | "
                   f"{sum(x == 'decrease' for x in d)} | {sum(x is None for x in d)} |")
    avg = [direction_of(v6[t]) for t in have]
    out.append(f"| The {n_runs} runs averaged | {share(sum(x == truth[t] for x, t in zip(avg, have)), len(have))} | "
               f"{sum(x == 'decrease' for x in avg)} | {sum(x is None for x in avg)} |")
    out += ["", "| Two runs of the same company | Companies both answered | Different direction |", "| --- | --- | --- |"]
    for i, j in combinations(range(n_runs), 2):
        both = [t for t in have if runs[t][i] and runs[t][j]]
        out.append(f"| Run {i + 1} and run {j + 1} | {len(both)} | "
                   f"{share(sum(runs[t][i] != runs[t][j] for t in both), len(both))} |")
    full = [t for t in have if all(runs[t])]
    same = sum(len(set(runs[t])) == 1 for t in full)
    out += ["", f"All {n_runs} runs answered for {len(full)} companies: the same direction every time for "
                f"{share(same, len(full))}, a split for {share(len(full) - same, len(full))}."]
    spreads = []
    for t in have:
        ps = [p for p in (p_increase(x) for x in v6[t]["runs"]) if p is not None]
        if len(ps) >= 2:
            spreads.append(max(ps) - min(ps))
    if spreads:
        out += ["", f"Stated probability of an increase, highest minus lowest run for the same company "
                    f"({len(spreads)} companies): median {statistics.median(spreads):.2f}; "
                    f"{share(sum(s >= 0.10 - 1e-9 for s in spreads), len(spreads))} differ by 0.10 or more, "
                    f"{share(sum(s >= 0.20 - 1e-9 for s in spreads), len(spreads))} by 0.20 or more."]
    out += ["", "For scale: how often something else calls a different direction from V6 run 1. A change to the prompt "
                "or tools shows only in what it adds on top of the run 2 and run 3 rows.", "",
            "| Against V6 run 1 | Companies both answered | Different direction |", "| --- | --- | --- |"]
    others = {f"V6 run {i + 1} (nothing changed)": {t: runs[t][i] for t in have} for i in range(1, n_runs)}
    for key, (label, _) in ARMS.items():
        others[f"{label} (one run)"] = {t: direction_of(r) for t, r in arms[key].items()}
    others["V5 (one run)"] = {t: direction_of(r) for t, r in v5.items()}
    for label, d in others.items():
        both = [t for t in have if runs[t][0] and d.get(t)]
        out.append(f"| {label} | {len(both)} | {share(sum(runs[t][0] != d[t] for t in both), len(both))} |")
    return out + [""]


def tools_section(tickers, v5, v6, arms):
    groups = {"V5": [v5[t].get("tools") or [] for t in tickers if t in v5],
              "V6, all runs": [x.get("tools") or [] for t in tickers if t in v6 for x in v6[t].get("runs") or []],
              "V6, run 1 only": [v6[t]["runs"][0].get("tools") or [] for t in tickers if v6.get(t, {}).get("runs")]}
    out = ["## 3. Which tools each version called", "",
           "| Version | Runs | " + " | ".join(TOOLS) + " |", "| --- | --- | " + " | ".join("---" for _ in TOOLS) + " |"]
    for name, lists in groups.items():
        out.append(f"| {name} | {len(lists)} | " + " | ".join(share(sum(tool in x for x in lists), len(lists))
                                                               for tool in TOOLS) + " |")
    v6_runs = groups["V6, all runs"]
    if v6_runs:
        structured = sum("read_mdna_items" in x for x in v6_runs)
        full_only = sum("read_mdna_items" not in x and ("get_mdna" in x or "locate_mdna" in x) for x in v6_runs)
        both = sum("read_mdna_items" in x and ("get_mdna" in x or "locate_mdna" in x) for x in v6_runs)
        out += ["", f"V6 runs that used the structured pass (read_mdna_items): {share(structured, len(v6_runs))}; "
                    f"of those, {both} also read the full text. Runs that read only the full text: {full_only}. "
                    f"Runs that read no MD&A at all: {len(v6_runs) - structured - full_only}."]
    return out + [""]


def main():
    companies = list(csv.DictReader(open(SET_B, encoding="utf-8")))
    tickers = [c["ticker"] for c in companies]
    truth = {c["ticker"]: c["truth"] for c in companies}
    v5, v6 = load(MAIN, "V5"), load(MAIN, "V6")
    arms = {key: load(path, "V6", key) for key, (_, path) in ARMS.items()}
    out = ["# Set B: cost, time and run-to-run variation by version (descriptive)", "",
           "Not pre-registered: written on Nov 13, 2026, after the set B result was known, to help choose the version "
           "the app runs. It describes runs already collected on set B's 200 companies and tests nothing. Seconds "
           "come from batch runs on shared free keys and include waits for rate limits.", ""]
    out += cost_section(tickers, v5, v6, arms)
    out += variation_section(tickers, truth, v5, v6, arms)
    out += tools_section(tickers, v5, v6, arms)
    REPORT.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"Saved {REPORT}")


if __name__ == "__main__":
    main()
