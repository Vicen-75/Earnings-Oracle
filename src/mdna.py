# --- Nicolas: MD&A extractor (code developed with assistance from ChatGPT) ---
# --- Javier: wrapped as an importable tool for src/agent.py (code written with help from Claude) ---
#
# get_mdna(cik) is the tool the model can call: it downloads the company's recent 10-Ks, cuts out Item 7
# (Management's Discussion and Analysis) from each one and returns the text. No retrieval happens here: the model
# reads the section itself and quotes from it. If the section cannot be found the tool returns
# {"error": "MD&A not found"} so the model falls back to the ratios (the fail-early path from the proposal feedback).
#
# Run by hand from the repository root:
#   python -m src.mdna CAT            # prints where the MD&A was found in each filing
#
# Which filings are read: the two most recent 10-Ks by default. For the backtest the newest filing is the answer
# year (FY2025) and must stay hidden, so set EARNINGS_ORACLE_SKIP_NEWEST=1 (or pass skip_newest=1) to read the two
# before it. The exact accession numbers for the test set live in eval/test_set.csv.
#
# Size: one MD&A is roughly 100k characters (about 25k tokens). MAX_CHARS_PER_FILING caps what goes back to the
# model; None means the whole section. Team decision, see docs/tool_calling.md.
import os
import re
import sys
from functools import lru_cache

from bs4 import BeautifulSoup

from src.edgar import ticker_to_cik, list_10ks, _get

SKIP_NEWEST = int(os.environ.get("EARNINGS_ORACLE_SKIP_NEWEST", "0"))
FILINGS_TO_READ = 2
MAX_CHARS_PER_FILING = None

# --- Finding the section (Nicolas's logic, unchanged) ------------------------------------------------------
START_PATTERN = r"\bitem\s+7\s*[.:\-]?\s*management"
START_CONFIRM = r"results of operations\s*\.?\s+the following\b"     # separates the real heading from the table of contents
END_PATTERN = r"\bitem\s+(?:7a\s*[.:\-]?\s*quantitative|8\s*[.:\-]?\s*financial)"
MIN_SECTION_CHARS = 5000                                             # an MD&A is never shorter than this


def html_to_text(html):
    """Flatten the 10-K HTML into one string of readable text."""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def find_mdna_start(text):
    """Position of the real 'Item 7. Management's Discussion...' heading, or None.
    A heading counts only if 'results of operations. The following' appears within 500 characters: that rejects
    the table of contents and cross-references to earlier reports. Exactly one match is required."""
    detected = []
    for match in re.finditer(START_PATTERN, text, re.IGNORECASE):
        snippet = text[match.start():match.start() + 500]
        if re.search(START_CONFIRM, snippet, re.IGNORECASE):
            detected.append(match.start())
    return detected[0] if len(detected) == 1 else None


def find_mdna_end(text, start):
    """Position of the first 'Item 7A' or 'Item 8' heading at least MIN_SECTION_CHARS after the start, or None."""
    ending = re.search(END_PATTERN, text[start + MIN_SECTION_CHARS:], re.IGNORECASE)
    return start + MIN_SECTION_CHARS + ending.start() if ending else None


def extract_mdna_from_text(text):
    """The MD&A section as a string, or None if the boundaries cannot be found."""
    start = find_mdna_start(text)
    if start is None:
        return None
    end = find_mdna_end(text, start)
    if end is None:
        return None
    return text[start:end]


@lru_cache(maxsize=64)
def extract_mdna_from_url(url):
    """Download one 10-K and return its MD&A text, or None. Cached: each filing is downloaded once per session."""
    response = _get(url)
    if response.status_code != 200:
        return None
    return extract_mdna_from_text(html_to_text(response.text))


def extract_mdna(cik, skip_newest=SKIP_NEWEST, how_many=FILINGS_TO_READ):
    """MD&A for the company's recent 10-Ks, newest first: [{"fiscal_year_end", "url", "text"}].
    Filings where the section could not be found are left out, so an empty list means 'MD&A not found'."""
    filings = list_10ks(cik, how_many=how_many + skip_newest)[skip_newest:]
    found = []
    for filing in filings:
        text = extract_mdna_from_url(filing["url"])
        if text:
            found.append({"fiscal_year_end": filing["fiscal_year_end"], "url": filing["url"], "text": text})
    return found


# --- The tool ----------------------------------------------------------------------------------------------
def get_mdna(cik, skip_newest=SKIP_NEWEST):
    """The agent's tool. Returns {"filings": [{"fiscal_year_end", "url", "chars", "text"}]} with the MD&A of each
    filing read, or {"error": "MD&A not found", "cik": cik} when no section could be extracted."""
    sections = extract_mdna(cik, skip_newest=skip_newest)
    if not sections:
        return {"error": "MD&A not found", "cik": cik}
    filings = []
    for s in sections:
        text = s["text"] if MAX_CHARS_PER_FILING is None else s["text"][:MAX_CHARS_PER_FILING]
        filings.append({"fiscal_year_end": s["fiscal_year_end"], "url": s["url"], "chars": len(s["text"]),
                        "truncated": len(text) < len(s["text"]), "text": text})
    return {"cik": cik, "filings": filings}


# --- Run by hand -------------------------------------------------------------------------------------------
if __name__ == "__main__":
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "CAT").upper()
    cik, company = ticker_to_cik(ticker)
    if cik is None:
        print("Company not found")
        raise SystemExit
    print("Company:", company, "| CIK:", cik, "| skipping newest:", SKIP_NEWEST)
    result = get_mdna(cik)
    if "error" in result:
        print(result["error"])
        raise SystemExit
    for f in result["filings"]:
        print(f"\nFY ending {f['fiscal_year_end']}  {f['url']}")
        print("  MD&A length:", f["chars"], "| truncated:", f["truncated"])
        print("  Beginning:", f["text"][:160])
        print("  Ending:   ", f["text"][-160:])
