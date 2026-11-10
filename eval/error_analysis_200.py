# --- Javier: error analysis of the 200-company backtest, issue #54 (code written with help from Claude) ---
# Where and why the model (prompt V5) was wrong on the 200. Exploratory: this is NOT part of the pre-registered
# analysis in docs/test_plan.md, so nothing here changes the reported result, and any prompt change it suggests has to be
# tested on companies the model has not been tuned on (see the last section of the report).
#
# Two steps:
#   python -m eval.error_analysis_200 fetch    # EDGAR only, no model calls: the target metric for the target year, the
#                                              # prior year and the year before, for all 200; re-checks every truth label.
#                                              # Writes eval/error_analysis_values.csv. About 300 requests, 1 to 2 minutes.
#   python -m eval.error_analysis_200          # no network: writes eval/error_analysis_200.md
#
# The report works without the fetch step; the "size of the change" section and the label check appear once
# eval/error_analysis_values.csv exists.
#
# Inputs: eval/test_set_200.csv (truth, baselines), eval/backtest_200_results.jsonl (answers),
#         eval/backtest_200_runs.jsonl (full tool traces and answer text), eval/sample_checks.csv (CIKs),
#         eval/error_analysis_tags.csv (failure types, tagged by hand after reading 35 wrong answers).
import csv
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

TEST_SET_PATH = Path("eval/test_set_200.csv")
RESULTS_PATH = Path("eval/backtest_200_results.jsonl")
RUNS_PATH = Path("eval/backtest_200_runs.jsonl")
CHECKS_PATH = Path("eval/sample_checks.csv")
TAGS_PATH = Path("eval/error_analysis_tags.csv")
VALUES_PATH = Path("eval/error_analysis_values.csv")
REPORT_PATH = Path("eval/error_analysis_200.md")
PROMPT = "V5"

TAG_LABELS = {
    "trend_up": "Extended a rising trend with no specific reason it would continue",
    "overrode_named_risk": "Named a concrete near-term negative, then called increase anyway",
    "trend_down": "Extended a falling trend and missed the turnaround",
    "one_off_bet_lost": "Bet that a one-off item would (or would not) repeat, and lost",
    "guidance_wrong": "Followed management guidance; results went the other way",
}
ONE_OFF = re.compile(r"one-time|non-recurring|nonrecurring|one-off|not recur", re.I)
GUIDANCE = re.compile(r"guidance|outlook|management (expects|anticipates|forecasts|projects)|we expect", re.I)
NO_COUNTER = re.compile(r"Strongest evidence against your call:\s*-?\s*None", re.I)


# --- loading -------------------------------------------------------------------------------------------------------
def load():
    """One dict per company: test-set fields, the model's answer, and features read from its run."""
    with open(TEST_SET_PATH, newline="", encoding="utf-8") as f:
        test_set = list(csv.DictReader(f))
    results, runs = {}, {}
    with open(RESULTS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r["prompt"] == PROMPT and not r.get("error"):
                    results[r["ticker"]] = r                  # the last successful run, as in analyze_backtest.py
    with open(RUNS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r["prompt"] == PROMPT:
                    runs[r["ticker"]] = r
    rows = []
    for t in test_set:
        res, run = results.get(t["ticker"]), runs.get(t["ticker"], {})
        answer = run.get("answer") or ""
        rationale = answer.split("Rationale:", 1)[1] if "Rationale:" in answer else ""
        mdna = [x for x in run.get("tools", []) if x["tool"] == "get_mdna"]
        mdna_chars = sum(int(c.replace(",", "")) for x in mdna
                         for c in re.findall(r"\(([\d,]+) characters\)", x["observation"]))
        pred = res["direction"] if res else None
        rows.append({
            **t,
            "pred": pred,
            "p": res["probability"] if res else None,
            "ok": pred == t["truth"],
            "follows_momentum": pred == t["momentum"] if pred else None,
            "one_off": bool(ONE_OFF.search(rationale)),
            "guidance": bool(GUIDANCE.search(answer)),
            "no_counter": bool(NO_COUNTER.search(answer)),
            "mdna_chars": mdna_chars,
            "tokens": run.get("usage", {}).get("prompt_tokens", 0),
        })
    return rows


def load_tags():
    if not TAGS_PATH.exists():
        return {}
    with open(TAGS_PATH, newline="", encoding="utf-8") as f:
        return {r["ticker"]: r for r in csv.DictReader(f)}


def load_values():
    if not VALUES_PATH.exists():
        return {}
    with open(VALUES_PATH, newline="", encoding="utf-8") as f:
        return {r["ticker"]: r for r in csv.DictReader(f)}


# --- step 1: fetch (EDGAR) -----------------------------------------------------------------------------------------
def _value_near(series, end):
    """Value for a fiscal year end, allowing a few days of difference (same rule as build_test_set._value_at)."""
    target = date.fromisoformat(end)
    for key, value in series.items():
        if abs((date.fromisoformat(key) - target).days) <= 10:
            return key, value
    return None, None


def fetch():
    from src.edgar import annual_operating_income, annual_pretax_income   # only this step needs the network

    with open(CHECKS_PATH, newline="", encoding="utf-8") as f:
        cik = {r["ticker"]: r["cik"] for r in csv.DictReader(f) if r["status"] == "ACCEPTED"}
    with open(TEST_SET_PATH, newline="", encoding="utf-8") as f:
        test_set = list(csv.DictReader(f))
    out = []
    for i, t in enumerate(test_set, 1):
        getter = annual_operating_income if t["target"] == "operating_income" else annual_pretax_income
        series = getter(cik[t["ticker"]]) or {}
        _, now = _value_near(series, t["target_end"])
        prior_key, before = _value_near(series, t["prior_end"])
        older = None
        if prior_key:
            older_keys = [k for k in series if date.fromisoformat(k) < date.fromisoformat(prior_key) - timedelta(days=300)]
            older = series[older_keys[0]] if older_keys else None
        recheck = "" if now is None or before is None else ("increase" if now > before else "decrease")
        out.append({"ticker": t["ticker"], "target": t["target"], "older": older, "prior": before, "target_year": now,
                    "truth": t["truth"], "truth_recheck": recheck,
                    "label_ok": "" if not recheck else str(recheck == t["truth"])})
        print(f"{i:3}/{len(test_set)} {t['ticker']:8} {recheck or 'missing':9} {'' if recheck == t['truth'] else 'CHECK'}")
    with open(VALUES_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    bad = [r["ticker"] for r in out if r["label_ok"] == "False"]
    print(f"Wrote {VALUES_PATH}. Labels that do not match today's EDGAR data: {bad or 'none'}")


# --- step 2: report ------------------------------------------------------------------------------------------------
def pct(k, n):
    return f"{k / n:.0%}" if n else "n/a"


def acc_row(label, group):
    k = sum(r["ok"] for r in group)
    return f"| {label} | {len(group)} | {k} | {pct(k, len(group))} |"


def change(a, b):
    """Relative change from a to b, on the size of a (works for losses: -100 to -50 is +50%)."""
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    return None if a == 0 else (b - a) / abs(a)


SIZE_BANDS = [(0, 0.05, "under 5%"), (0.05, 0.20, "5% to 20%"), (0.20, 0.50, "20% to 50%"), (0.50, float("inf"), "50% or more")]


def report():
    rows, tags, values = load(), load_tags(), load_values()
    n = len(rows)
    wrong = [r for r in rows if not r["ok"]]
    answered_wrong = [r for r in wrong if r["pred"]]
    out = ["# Error analysis: 200-company backtest, prompt V5 (issue #54)", "",
           "Exploratory, done after the pre-registered result (`eval/backtest_200_report.md`). It explains the "
           "result; it does not change it.", "",
           f"The model was wrong on {len(wrong)} of {n}: {sum(r['pred'] == 'increase' for r in wrong)} times it said "
           f"increase and income fell, {sum(r['pred'] == 'decrease' for r in wrong)} times it said decrease and income "
           f"rose, and {sum(r['pred'] is None for r in wrong)} times it gave no answer (the empty-final-turn bug).", ""]

    # 1. momentum
    follows = [r for r in rows if r["follows_momentum"] is True]
    against = [r for r in rows if r["follows_momentum"] is False]
    reversed_ = sum(r["truth"] != r["momentum"] for r in rows)
    out += ["## 1. The main failure: carrying last year's direction forward", "",
            f"The model agreed with momentum (last year's direction) on {len(follows)} of {n} companies. "
            f"But in this sample last year's direction repeated only {n - reversed_} times out of {n} "
            f"({pct(n - reversed_, n)}), so momentum is close to a coin flip.", "",
            "| Last year | This year (truth) | Companies | Model said increase | Model correct | Accuracy |",
            "|---|---|---|---|---|---|"]
    for mom in ("increase", "decrease"):
        for truth in ("increase", "decrease"):
            g = [r for r in rows if r["momentum"] == mom and r["truth"] == truth]
            k = sum(r["ok"] for r in g)
            out.append(f"| {mom} | {truth} | {len(g)} | {sum(r['pred'] == 'increase' for r in g)} | {k} | {pct(k, len(g))} |")
    trend_wrong = [r for r in answered_wrong if r["follows_momentum"]]
    out += ["",
            f"{len(trend_wrong)} of the {len(answered_wrong)} answered misses are cases where the model repeated last "
            f"year's direction and the direction reversed. The worst cell is a rising year followed by a fall: the model "
            f"still said increase most of the time.", "",
            "| Model's call | Companies | Correct | Accuracy |", "|---|---|---|---|",
            acc_row("Same direction as last year", follows),
            acc_row("Opposite direction to last year", against), "",
            "When the model breaks from the trend, it is right more often than when it follows it.", ""]

    # 2. hand-tagged failure types
    if tags:
        counts = Counter(tags[t]["tag"] for t in tags)
        out += ["## 2. Why it was wrong: 35 misses read by hand", "",
                "All 7 confident misses (p ≥ 0.80), plus the highest-probability misses in each direction. "
                "Tags and one-line notes are in `eval/error_analysis_tags.csv`.", "",
                "| Failure type | Misses | Examples |", "|---|---|---|"]
        for tag, label in TAG_LABELS.items():
            ex = ", ".join(t for t in tags if tags[t]["tag"] == tag)
            out.append(f"| {label} | {counts.get(tag, 0)} | {ex} |")
        out += ["",
                "- **Trend extension (rising and falling) is the largest group.** The rationale reads like a description "
                "of last year (margin expansion, operating leverage, a recovery) with no specific driver for next year.",
                "- **Overriding its own warning is the most fixable.** In each case the answer names a concrete, near-term "
                "negative (a $400M write-off at VST, a premium deficiency reserve at CNC, guidance for SG&A deleverage at "
                "DKS) and then outweighs it with general strengths. Four of the seven are health or life insurers.",
                "- **One-off reasoning is mostly a strength.** See section 3: answers built on a one-off item are right "
                "more often than average. The losses here are reasonable bets.",
                "- **Guidance misses are mostly unforecastable from the 10-K.** Management said lower; results came in "
                "higher. Guidance is usually a good signal (section 3), so there is little to fix here.", ""]

    # 3. what kind of reasoning works
    out += ["## 3. Which kinds of answers are right more often", "",
            "Read from the answer text; descriptive only, groups overlap and are small.", "",
            "| Answer | Companies | Correct | Accuracy |", "|---|---|---|---|",
            acc_row("Rationale rests on a one-off item (charge, gain, catch-up revenue)", [r for r in rows if r["one_off"]]),
            acc_row("Rationale does not", [r for r in rows if not r["one_off"] and r["pred"]]),
            acc_row("Cites guidance or management's outlook", [r for r in rows if r["guidance"]]),
            acc_row("Does not", [r for r in rows if not r["guidance"] and r["pred"]]),
            acc_row("Says the strongest evidence against its call is 'None'", [r for r in rows if r["no_counter"]]), ""]
    with_mdna = sorted((r for r in rows if r["pred"]), key=lambda r: r["mdna_chars"])
    q = len(with_mdna) // 4
    out += ["| MD&A read (characters, both years) | Companies | Correct | Accuracy |", "|---|---|---|---|",
            acc_row(f"Shortest quarter (under {with_mdna[q]['mdna_chars']:,})", with_mdna[:q]),
            acc_row("The other three quarters", with_mdna[q:]), "",
            f"The self-check is meant to force a counterargument; 'None' still got through "
            f"{sum(r['no_counter'] for r in rows)} times, all at a stated probability of 0.80 or more. "
            "Answers that read less MD&A text are right less often; worth checking whether those MD&As were cut short "
            "or are just short.", ""]

    # 4. size of the change (needs the fetch step)
    out += ["## 4. Size of the change", ""]
    if values:
        for label, a, b in (("This year's change (how close the outcome was)", "prior", "target_year"),
                            ("Last year's change (how big the trend was)", "older", "prior")):
            out += [f"**{label}**", "", "| Size of change | Companies | Correct | Accuracy |", "|---|---|---|---|"]
            for lo, hi, band in SIZE_BANDS:
                g = [r for r in rows if r["ticker"] in values
                     and (c := change(values[r["ticker"]][a], values[r["ticker"]][b])) is not None and lo <= abs(c) < hi]
                out.append(acc_row(band, g))
            out.append("")
        size = {r["ticker"]: change(values[r["ticker"]]["prior"], values[r["ticker"]]["target_year"])
                for r in rows if r["ticker"] in values}
        flat = [r for r in rows if size.get(r["ticker"]) is not None and abs(size[r["ticker"]]) < 0.05]
        flat_wrong = [r for r in flat if not r["ok"]]
        confident = [r for r in wrong if r["p"] is not None and r["p"] >= 0.80 and size.get(r["ticker"]) is not None]
        out += [f"{len(flat_wrong)} of the {len(wrong)} misses are outcomes that moved less than 5% "
                f"({len(flat_wrong)} wrong of {len(flat)} such companies). Those are close to coin flips and not worth "
                "chasing in V6. Accuracy rises with the size of the move.", "",
                "Confident misses (p ≥ 0.80) and how much the target actually moved: "
                + ", ".join(f"{r['ticker']} {size[r['ticker']]:+.0%}" for r in confident)
                + ". The near-flat ones were close calls; the large ones are the real errors.", ""]
        bad = [t for t, v in values.items() if v["label_ok"] == "False"]
        missing = [t for t, v in values.items() if not v["label_ok"]]
        out += [f"Truth labels re-checked against EDGAR: {n - len(bad) - len(missing)} match, "
                f"{len(bad)} differ ({', '.join(bad) or 'none'}), {len(missing)} could not be re-checked "
                f"({', '.join(missing) or 'none'}).", ""]
    else:
        out += ["Not run yet: `python -m eval.error_analysis_200 fetch` adds how close each outcome was (a miss on a "
                "1% change is a coin flip; a miss on a 40% change is a real error) and re-checks every truth label "
                "against EDGAR.", ""]

    # 5. by target and group, misses only
    out += ["## 5. Where the misses sit", "", "| Group | Companies | Misses | Said increase, fell | Said decrease, rose |",
            "|---|---|---|---|---|"]
    for key, label in (("target", "Target: "), ("industry_group", "")):
        for v, c in Counter(r[key] for r in rows).most_common():
            g = [r for r in rows if r[key] == v]
            w = [r for r in g if not r["ok"]]
            out.append(f"| {label}{v.replace('_', ' ')} | {len(g)} | {len(w)} | "
                       f"{sum(r['pred'] == 'increase' for r in w)} | {sum(r['pred'] == 'decrease' for r in w)} |")
    out += ["", "Misses lean toward 'said increase, income fell' in most groups, most clearly in materials and chemicals "
            "and in utilities. For insurers, the misses read by hand named medical cost or reserve pressure and then "
            "discounted it.", ""]

    # 6. against the base rate
    def vs_base(label, g):
        k, a = sum(r["ok"] for r in g), sum(r["truth"] == "increase" for r in g)
        mo = sum(r["truth"] == r["momentum"] for r in g)
        return f"| {label} | {len(g)} | {pct(k, len(g))} | {pct(a, len(g))} | {pct(mo, len(g))} |"
    said_dec = [r for r in rows if r["pred"] == "decrease"]
    dec_ok = sum(r["ok"] for r in said_dec)
    out += ["## 6. Measured against the base rate", "",
            "The same companies scored three ways. A subset where the model looks good may simply be one where most "
            "companies grew.", "",
            "| Companies | Count | Model | Always increase | Momentum |", "|---|---|---|---|---|",
            vs_base("All", rows),
            vs_base("Model said increase", [r for r in rows if r["pred"] == "increase"]),
            vs_base("Model said decrease", said_dec),
            vs_base("Stated probability 0.80 or more", [r for r in rows if r["p"] is not None and r["p"] >= 0.80]),
            vs_base("Stated probability 0.70 or more", [r for r in rows if r["p"] is not None and r["p"] >= 0.70])]
    if values:
        out.append(vs_base("Outcome moved 5% or more", [r for r in rows if size.get(r["ticker"]) is not None
                                                         and abs(size[r["ticker"]]) >= 0.05]))
    out += ["",
            f"- **The decrease calls decide the result.** Every decrease call is a bet against a base rate of about 63% "
            f"increases, so it adds value only if it is right more than half the time. V5's were right {dec_ok} of "
            f"{len(said_dec)} ({pct(dec_ok, len(said_dec))}). They do point at weaker companies (only "
            f"{pct(len(said_dec) - dec_ok, len(said_dec))} of them grew, against {pct(sum(r['truth'] == 'increase' for r in rows), n)} "
            "of all 200), but not weak enough to cross one half. That is why the model ties always-increase instead "
            "of beating it.",
            "- **The increase calls pick growers only slightly better than chance.** On the two 'model said' rows, "
            "model and always-increase agree or disagree by definition; the useful comparison is the share that grew "
            "in that row against the share across all 200.",
            "- **Calibration needs this caveat.** Confident calls are right more often, but always-increase is also "
            "right more often on those companies: the model's confidence mostly picks companies likely to grow. Report "
            "the top band next to the always-increase figure, not alone.", ""]

    # 7. V6
    out += ["## 7. What this means for V6", "",
            "Ranked by what it takes to beat always-increase: better decrease calls. Making the model call more "
            "reversals at today's precision would make things worse.", "",
            "| Change | Misses it targets | Notes |", "|---|---|---|",
            f"| When the answer names a concrete, near-term negative (a charge, a reserve, guidance for lower margin), "
            f"make it size that item against the positives, and call decrease when the negative is larger | "
            f"{counts.get('overrode_named_risk', 0) if tags else 'n/a'} of 35 read | The source of high-precision "
            "decrease calls: these were correct decreases the model talked itself out of. Especially insurers. |",
            f"| Treat last year's direction as weak evidence in both directions: a trend alone justifies neither a call "
            f"nor a high probability, and a decrease call needs a specific driver | up to {len(trend_wrong)} "
            "(trend misses) | Aim is fewer confident trend calls, not more reversal calls (reverse momentum scored "
            "48%). |",
            f"| Self-check must return a real counterargument; 'None' is not accepted | "
            f"{sum(r['no_counter'] and not r['ok'] for r in rows)} wrong of {sum(r['no_counter'] for r in rows)} | "
            "Feeds the first change: the counterargument is where named negatives surface. |",
            f"| Fall back to the draft when the final turn is empty | {sum(r['pred'] is None for r in rows)} | "
            "Mechanical fix; drafts would have recovered 1 (CDP). |",
            "| Keep: one-off reasoning | n/a | Right more often than average; do not prompt it away. |", "",
            "**Testing V6 fairly.** These changes come from reading the 200 test answers, so a V6 score on the same 200 "
            "would be inflated. Try V6 on the 20-company development set, then score it once on a fresh set: the next "
            "200 companies in the shuffled `eval/universe.csv` that pass both gates. Report V5 on the 200 as the "
            "pre-registered result and V6 on the fresh set as a separate result.", ""]

    REPORT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
    else:
        report()
