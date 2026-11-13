# --- Javier: the 200-company test set (code written with help from Claude) ---
# Plan: docs/test_plan.md. Same three gates as the 20-company set (data, contamination, hidden year), with no hand
# picking: the order in which companies are tried is fixed by a random seed before any model call.
#
#   Step 1  universe   SEC "frames" API: every filer with a US address, revenue of at least $500M in calendar 2024,
#                      and operating income or pre-tax income reported for 2024. Shuffled with SEED.
#                      Writes eval/universe.csv. Commit it (with docs/test_plan.md) BEFORE step 2: that commit is the
#                      proof that the order was fixed before we knew how the model would do.
#   Step 2  check      Walks the universe in order. Per company:
#                        data gate (EDGAR only): a 10-K for a fiscal year ending in the target window, the 10-K before
#                          it, and the target metric for both years plus the year before (for the momentum baseline);
#                        contamination gate (3 short Gemini calls, eval/contamination.py): the model must not remember
#                          the target year or any quarter of it.
#                      Stops once TARGET_SIZE companies pass. Resumable: run it again after a crash or a quota stop.
#                      Writes eval/sample_checks.csv (every company tried, with the reason it passed or failed) and
#                      eval/test_set_200.csv (the accepted ones, in order).
#
# Target year (same window as docs/success_metric.md): the fiscal year ending between 2025-07-01 and 2026-06-30.
# Every company has exactly one fiscal year ending in that window (Dec 2025 for most, Jan-Feb 2026 for retailers,
# Sep 2025 or Jun 2026 for others). Target metric: operating income, or pre-tax income when the company reports no
# operating income line (edgar.choose_target, banks and insurers). Truth: "increase" means strictly greater.
#
# Run from the repository root:
#   python -m eval.build_test_set universe
#   python -m eval.build_test_set check            # add --limit 10 for a short trial
#   python -m eval.build_test_set status
#
# Nov 10, set B (fresh 200 for V6, pre-registered in docs/test_plan.md): add --set b to check or status. Same gates and
# same order; it starts after set A's last company (universe order 217) and skips the development set's companies.
# Writes eval/sample_checks_b.csv and eval/test_set_200b.csv; set A's files are not touched.
#   python -m eval.build_test_set check --set b
#   python -m eval.build_test_set status --set b
#
# Nov 11, set C (docs/test_plan.md): 200 fresh companies used once, to choose between V6 and V7 before the freeze.
# Same gates and order; starts after set B's last company (universe order 433) and skips the development set, set A
# and set B. Writes eval/sample_checks_c.csv and eval/test_set_200c.csv.
#   python -m eval.build_test_set check --set c
#
# Nov 13, set D (docs/test_plan.md): 400 fresh companies for one more test of V6, with one run per company. Same gates
# and order; starts after set C's last company (universe order 651) and skips the development set and sets A, B and C.
# Writes eval/sample_checks_d.csv and eval/test_set_400d.csv.
#   python -m eval.build_test_set check --set d
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from src.edgar import _get_json, list_10ks, choose_target, TARGETS
from src.ratio_directory import group_for_sic

SEED = 883                                  # the course number; fixed before any model call
TARGET_SIZE = 200
REVENUE_FLOOR = 500_000_000                 # USD, calendar 2024
WINDOW = ("2025-07-01", "2026-06-30")       # fiscal year end of the year being predicted
ACCEPTED_VERDICTS = ("OK", "OK_BUT_UNKNOWN_COMPANY")

UNIVERSE_PATH = Path("eval/universe.csv")
CHECKS_PATH = Path("eval/sample_checks.csv")
TEST_SET_PATH = Path("eval/test_set_200.csv")
DEV_SET_PATH = Path("eval/test_set.csv")
START_AFTER_ORDER = 0                       # set B: 217, the universe order of set A's 200th company
EXCLUDED = set()                            # set B: the development set's tickers and set A's
SETS = {"b": {"checks": Path("eval/sample_checks_b.csv"), "test": Path("eval/test_set_200b.csv"), "start_after": 217,
              "exclude": [Path("eval/test_set_200.csv")]},
        "c": {"checks": Path("eval/sample_checks_c.csv"), "test": Path("eval/test_set_200c.csv"), "start_after": 433,
              "exclude": [Path("eval/test_set_200.csv"), Path("eval/test_set_200b.csv")]},
        "d": {"checks": Path("eval/sample_checks_d.csv"), "test": Path("eval/test_set_400d.csv"), "start_after": 651,
              "size": 400, "exclude": [Path("eval/test_set_200.csv"), Path("eval/test_set_200b.csv"),
                                       Path("eval/test_set_200c.csv")]}}

REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                "InterestAndDividendIncomeOperating"]          # the last one: banks' size (interest income)
INCOME_TAGS = ["OperatingIncomeLoss",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]

UNIVERSE_FIELDS = ["order", "cik", "ticker", "name", "state", "revenue_2024_billion_usd"]
CHECK_FIELDS = ["order", "ticker", "cik", "name", "sic", "industry_group", "target", "prior_end", "target_end",
                "skip_newest", "truth", "momentum", "reverse_momentum", "contamination", "status", "detail"]
TEST_FIELDS = ["ticker", "name", "industry", "industry_group", "target", "prior_end", "target_end", "skip_newest",
               "truth", "momentum", "reverse_momentum", "contamination"]


# --- Step 1: the universe ---------------------------------------------------------------------------------------
def _frame(tag, period="CY2024"):
    data = _get_json(f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json")
    return data["data"] if data else []


def build_universe():
    revenue, location, names = {}, {}, {}
    for tag in REVENUE_TAGS:
        for row in _frame(tag):
            cik = row["cik"]
            revenue[cik] = max(revenue.get(cik, 0), row["val"])
            location[cik], names[cik] = row.get("loc", ""), row["entityName"]
        print(f"   revenue frame {tag}: {len(revenue)} companies so far")
    has_income = set()
    for tag in INCOME_TAGS:
        has_income |= {row["cik"] for row in _frame(tag)}
    tickers = {}
    for row in _get_json("https://www.sec.gov/files/company_tickers.json").values():
        tickers.setdefault(row["cik_str"], row["ticker"])        # first listed share class

    ciks = sorted(cik for cik, value in revenue.items()
                  if value >= REVENUE_FLOOR and cik in has_income and cik in tickers
                  and str(location.get(cik, "")).startswith("US-"))
    random.Random(SEED).shuffle(ciks)
    with open(UNIVERSE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=UNIVERSE_FIELDS)
        writer.writeheader()
        for i, cik in enumerate(ciks, start=1):
            writer.writerow({"order": i, "cik": str(cik).zfill(10), "ticker": tickers[cik], "name": names[cik],
                             "state": location[cik][3:], "revenue_2024_billion_usd": round(revenue[cik] / 1e9, 2)})
    print(f"\n{len(ciks)} companies in the universe (US address, revenue >= ${REVENUE_FLOOR / 1e9:.1f}B in 2024, "
          f"operating or pre-tax income reported). Shuffled with seed {SEED}. Written to {UNIVERSE_PATH}.")
    print("Commit eval/universe.csv and docs/test_plan.md now, before running the check step.")


# --- Step 2: the gates ------------------------------------------------------------------------------------------
def _value_at(series, end):
    """Value in an XBRL series for a fiscal year end (keys can differ from the filing's date by a few days)."""
    target = date.fromisoformat(end)
    for key, value in series.items():
        if abs((date.fromisoformat(key) - target).days) <= 10:
            return key, value
    return None, None


def data_gate(cik):
    """EDGAR-only checks. Returns (fields, None) if the company can be tested, or (partial fields, reason) if not."""
    submissions = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json") or {}
    sic = submissions.get("sic")
    fields = {"sic": sic, "industry_group": group_for_sic(sic)}
    filings = list_10ks(cik, how_many=4)
    if not filings:
        return fields, "NO_10K (files 20-F, 40-F or nothing)"
    in_window = [i for i, f in enumerate(filings) if f["fiscal_year_end"] and WINDOW[0] <= f["fiscal_year_end"] <= WINDOW[1]]
    if not in_window:
        return fields, f"NO_TARGET_10K (newest 10-K: {filings[0]['fiscal_year_end']})"
    t = in_window[0]
    if t + 1 >= len(filings):
        return fields, "NO_PRIOR_10K"
    target_end, prior_end = filings[t]["fiscal_year_end"], filings[t + 1]["fiscal_year_end"]
    gap = (date.fromisoformat(target_end) - date.fromisoformat(prior_end)).days
    if not 350 <= gap <= 380:
        return fields, f"NOT_A_FULL_YEAR ({prior_end} to {target_end}: fiscal year change or missing 10-K)"
    fields.update(target_end=target_end, prior_end=prior_end, skip_newest=t + 1)   # hide the target and anything newer

    target, series = choose_target(cik, target_end)
    if not target:
        return fields, "NO_TARGET_METRIC (neither operating income nor pre-tax income for the target year)"
    _, now = _value_at(series, target_end)
    prior_key, before = _value_at(series, prior_end)
    if before is None:
        return fields, f"NO_PRIOR_VALUE ({TARGETS[target]} missing for {prior_end})"
    older = [k for k in series if date.fromisoformat(k) < date.fromisoformat(prior_key) - timedelta(days=300)]
    if not older:
        return fields, "NO_THIRD_YEAR (momentum baseline needs the year before the prior year)"
    momentum = "increase" if before > series[older[0]] else "decrease"
    fields.update(target=target, truth="increase" if now > before else "decrease", momentum=momentum,
                  reverse_momentum="decrease" if momentum == "increase" else "increase")
    return fields, None


def contamination_gate(name, fields):
    from eval.contamination import probe_verdict           # imported here: step 1 needs no model client
    verdict, _ = probe_verdict(name, fields["target_end"], fields["prior_end"], fields["truth"],
                               metric=TARGETS[fields["target"]])
    return verdict


def _read(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_test_set(checks):
    accepted = [r for r in checks if r["status"] == "ACCEPTED"][:TARGET_SIZE]
    rows = [{**r, "industry": r["industry_group"].replace("_", " ").capitalize()} for r in accepted]
    _write(TEST_SET_PATH, rows, TEST_FIELDS)
    return accepted


def check(limit=None):
    universe = _read(UNIVERSE_PATH)
    if not universe:
        sys.exit("No eval/universe.csv yet: run  python -m eval.build_test_set universe  first.")
    checks = {r["ticker"]: r for r in _read(CHECKS_PATH) if not r["status"].startswith("ERROR")}
    tried, errors_in_a_row = 0, 0
    for company in universe:
        ticker = company["ticker"]
        if ticker in checks or int(company["order"]) <= START_AFTER_ORDER:
            continue
        if ticker in EXCLUDED:                           # set B: never reuse a development-set or set A company
            checks[ticker] = {"order": company["order"], "ticker": ticker, "cik": company["cik"],
                              "name": company["name"], "status": "SKIPPED_OTHER_SET",
                              "detail": "in the development set or an earlier test set"}
            continue
        # Stop once TARGET_SIZE companies EARLIER in the order are accepted. Counting earlier ones only (Nov 6 fix)
        # means a company that errored is retried even when 200 were already accepted after it: if it passes, it
        # takes its place by order and the last one drops out, exactly as the pre-registered rule says.
        earlier = sum(r["status"] == "ACCEPTED" and int(r["order"]) < int(company["order"]) for r in checks.values())
        if earlier >= TARGET_SIZE:
            break
        if limit is not None and tried >= limit:
            break
        tried += 1
        row = {"order": company["order"], "ticker": ticker, "cik": company["cik"], "name": company["name"]}
        try:
            fields, problem = data_gate(company["cik"])
            row.update(fields)
            if problem:
                row.update(status="REJECTED_DATA", detail=problem)
            else:
                verdict = contamination_gate(company["name"], fields)
                row.update(contamination=verdict,
                           status="ACCEPTED" if verdict in ACCEPTED_VERDICTS else "REJECTED_CONTAMINATION",
                           detail="" if verdict in ACCEPTED_VERDICTS else verdict)
        except Exception as error:                       # EDGAR hiccup, Gemini quota, odd JSON: retried next run
            row.update(status="ERROR_RETRY_LATER", detail=f"{type(error).__name__}: {str(error)[:150]}")
        checks[ticker] = row
        errors_in_a_row = errors_in_a_row + 1 if row["status"].startswith("ERROR") else 0
        print(f"#{row['order']:>4} {ticker:<6} {row['status']:<23} {row.get('detail', '')}")
        ordered = sorted(checks.values(), key=lambda r: int(r["order"]))
        _write(CHECKS_PATH, ordered, CHECK_FIELDS)        # saved after every company
        _write_test_set(ordered)
        if errors_in_a_row >= 3:
            print("\nThree errors in a row (daily quota used up, or EDGAR/Gemini down). Stopping; run again later "
                  "and it continues where it stopped.")
            break
    status()


def status():
    checks = sorted(_read(CHECKS_PATH), key=lambda r: int(r["order"]))
    if not checks:
        print("Nothing checked yet.")
        return
    count = lambda s: sum(r["status"] == s for r in checks)               # noqa: E731
    accepted = _write_test_set(checks)
    print(f"\nTried {len(checks)} companies: {count('ACCEPTED')} accepted, {count('REJECTED_DATA')} failed the data "
          f"gate, {count('REJECTED_CONTAMINATION')} failed the contamination gate, {count('ERROR_RETRY_LATER')} "
          f"errors (run again to retry)"
          + (f", {count('SKIPPED_OTHER_SET')} skipped (development set or set A)." if count('SKIPPED_OTHER_SET') else "."))
    if accepted:
        inc = sum(r["truth"] == "increase" for r in accepted)
        pre = sum(r["target"] == "pretax_income" for r in accepted)
        print(f"Test set: {len(accepted)} of {TARGET_SIZE} companies in {TEST_SET_PATH}: {inc} increase, "
              f"{len(accepted) - inc} decrease; {pre} on pre-tax income; "
              f"{sum(r['skip_newest'] != '1' and r['skip_newest'] != 1 for r in accepted)} hide two 10-Ks.")


def use_set(name):
    """Point the check and status steps at set B's files (set A stays the default, unchanged)."""
    global CHECKS_PATH, TEST_SET_PATH, START_AFTER_ORDER, EXCLUDED, TARGET_SIZE
    chosen = SETS[name]
    TARGET_SIZE = chosen.get("size", TARGET_SIZE)          # set D: 400 companies
    CHECKS_PATH, TEST_SET_PATH, START_AFTER_ORDER = chosen["checks"], chosen["test"], chosen["start_after"]
    EXCLUDED = {r["ticker"] for r in _read(DEV_SET_PATH)}
    for path in chosen["exclude"]:
        if not path.exists():
            sys.exit(f"{path} is missing: set {name.upper()} must exclude its companies.")
        EXCLUDED |= {r["ticker"] for r in _read(path)}
    print(f"Set {name.upper()}: {TEST_SET_PATH}, starting after universe order {START_AFTER_ORDER}, "
          f"{len(EXCLUDED)} tickers excluded (development set and earlier test sets).")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--set" in args:
        use_set(args[args.index("--set") + 1].lower())
    step = args[0] if args else "status"
    if step == "universe":
        build_universe()
    elif step == "check":
        from src.key_pool import pool                  # Nov 10: the contamination calls wait out a busy Google
        pool.patient = True
        check(limit=int(args[args.index("--limit") + 1]) if "--limit" in args else None)
    else:
        status()
