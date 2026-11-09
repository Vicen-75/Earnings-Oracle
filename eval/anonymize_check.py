# --- Vicente: anonymizer check, issue #27 (code written with help from Claude) ---
# Two questions about the anonymizer, on the 20 development companies (eval/test_set.csv), in backtest mode:
#   1. Leak check (deterministic): after scrubbing, does any company name, former name, ticker, CIK or detected
#      brand still appear in what the model would see (company card + MD&A)? Code decides, not a model.
#   2. Guess check (--guess): shown the anonymized MD&A, can the model still name the company? If it usually can,
#      hiding the name does not hide the company, and named-vs-anonymized accuracy must be read with that in mind.
#
# Run from the repository root:
#   python -m eval.anonymize_check              # leak check only (1 model call per company: the brand scan)
#   python -m eval.anonymize_check --guess      # also the guess check (1 more call per company)
#   python -m eval.anonymize_check CAT HD       # a few tickers
# Writes eval/anonymize_check.csv.
import csv
import sys
from pathlib import Path

from google.genai import types
from pydantic import BaseModel, Field

from src import edgar
from src.anonymize import Anonymizer
from src.key_pool import pool
from src.llm import MODEL
from src.mdna import get_mdna
from src.locate_mdna import locate_mdna

TEST_SET = Path("eval/test_set.csv")
OUT = Path("eval/anonymize_check.csv")
SKIP_NEWEST = 1                     # backtest mode: the same filings the agent reads when predicting
GUESS_CHARS = 12_000


class Guess(BaseModel):
    company_name: str = Field(description="Your best guess of the company's name, or 'unknown'")
    ticker: str = Field(description="Your best guess of its stock ticker, or 'unknown'")
    confident: bool = Field(description="True only if you are confident the guess is right")


GUESS_PROMPT = """The text below is from a US company's annual report, with the company's name, ticker and brand \
names removed. Which company is it? If you cannot tell, answer 'unknown'.

"""


def generate(model, contents, config):
    return pool.generate(model, contents, config)


def guess_company(industry, text):
    config = types.GenerateContentConfig(temperature=0, response_mime_type="application/json", response_schema=Guess)
    try:
        response = generate(MODEL, GUESS_PROMPT + f"Industry: {industry}\n\n" + text[:GUESS_CHARS], config)
        return Guess.model_validate_json(response.text)
    except Exception:
        return None


def check(ticker, do_guess=False):
    anon = Anonymizer(ticker, generate=generate)
    row = {"ticker": ticker, "company_names": "; ".join(anon.company_names)}
    card = edgar.company_card(ticker, skip_newest=SKIP_NEWEST)
    if "error" in card:
        return {**row, "status": f"no card: {card['error']}"}
    mdna = get_mdna(card["cik"], skip_newest=SKIP_NEWEST)
    if "error" in mdna:                                   # same fallback the agent uses (MCD on Nov 6)
        mdna = locate_mdna(card["cik"], skip_newest=SKIP_NEWEST)
    if "error" in mdna:
        return {**row, "status": "MD&A not found, even with the locator"}
    seen = [anon.scrub(card), anon.scrub(mdna)]
    leaks = anon.leaks(seen)
    text = " ".join(f["text"] for f in seen[1]["filings"])
    row.update({"status": "checked", "chars_checked": len(text), "brand_scan": anon.brand_scan,
                "brands_removed": "; ".join(anon.brands), "leaks": "; ".join(f"{k} x{v}" for k, v in leaks.items()),
                "leak_free": not leaks})
    if do_guess:
        g = guess_company(card.get("sic_description"), text)
        if g is None:
            row["guess"] = "parse failed"
        else:
            right = g.ticker.upper() in anon.tickers or any(n.lower() in g.company_name.lower()
                                                            for n in anon.company_names)
            row.update({"guess": f"{g.company_name} ({g.ticker})", "guess_confident": g.confident,
                        "guessed_right": right})
    return row


def main(args):
    do_guess = "--guess" in args
    tickers = [a for a in args if not a.startswith("--")]
    if not tickers:
        with open(TEST_SET, newline="") as f:
            tickers = [r["ticker"] for r in csv.DictReader(f)]
    rows = []
    for t in tickers:
        try:
            row = check(t, do_guess)
        except Exception as error:
            row = {"ticker": t, "status": f"error: {type(error).__name__}: {error}"}
        rows.append(row)
        print(f"{t}: {row.get('status')} | leaks: {row.get('leaks') or 'none'} | brands: {row.get('brands_removed', '')}"
              + (f" | guess: {row.get('guess')} right={row.get('guessed_right')}" if do_guess else ""))
    fields = ["ticker", "status", "company_names", "chars_checked", "brand_scan", "brands_removed", "leaks",
              "leak_free", "guess", "guess_confident", "guessed_right"]
    with open(OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    checked = [r for r in rows if r.get("status") == "checked"]
    print(f"\n{sum(r['leak_free'] for r in checked)} of {len(checked)} checked companies leak-free.")
    if do_guess:
        guessed = [r for r in checked if r.get("guessed_right")]
        print(f"The model still named {len(guessed)} of {len(checked)} companies from the anonymized text.")
    print(f"Results in {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
