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
DASH = "[.:\\-\u2013\u2014]"   # Javier, Nov 5: also en and em dashes ("ITEM 7 \u2013 MANAGEMENT'S", Martin Marietta)
START_PATTERN = r"\bitem\s+7\s*" + DASH + r"?\s*management"
START_CONFIRM = r"results of operations\s*\.?\s+the following\b"     # separates the real heading from the table of contents
END_PATTERN = r"\bitem\s+(?:7a\s*" + DASH + r"?\s*quantitative|8\s*" + DASH + r"?\s*financial)"
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
    """Position of the first 'Item 7A' or 'Item 8' heading at least MIN_SECTION_CHARS after the start, or None.
    Javier, Nov 5: cross-references ('...in Item 8 - Financial Statements of this report') are skipped (PLBC)."""
    for ending in re.finditer(END_PATTERN, text[start + MIN_SECTION_CHARS:], re.IGNORECASE):
        position = start + MIN_SECTION_CHARS + ending.start()
        if not is_cross_reference(text, position):
            return position
    return None


# --- Javier: headings vs references (code written with help from Claude) ---
# "Item 7" and "Item 8" appear in three roles: real headings, table-of-contents lines, and cross-references inside
# other sections. Only headings may start or end the MD&A. PLBC (Nov 5) started at 'see "Item 7. Management's ... -
# Capital Standards."' inside Item 1 and ended at '...in Item 8 - Financial Statements ... of this Annual Report'.
CROSS_REFERENCE_BEFORE = re.compile(
    r"(?:\bsee|\bin|\bunder|\bto|\bwithin|\bincluded\s+in|[\u201c\u2018\"'])\s*(?:part\s+ii\s*[,.]?\s*)?"
    r"[\u201c\u2018\"']?\s*$", re.IGNORECASE)
TOC_LINE_AFTER = re.compile(r"(?:\b\d{1,3}|\bF-\d{1,3})\s+item\s+\d", re.IGNORECASE)   # "...Operations 24 Item 7A"
TOC_WINDOW = 250


def is_cross_reference(text, position):
    """True if the Item heading at this position is a reference ('see "Item 7...', 'in Item 8 -'), not a heading."""
    return CROSS_REFERENCE_BEFORE.search(text[max(0, position - 30):position]) is not None


def is_toc_entry(text, position):
    """True if the Item heading at this position is a table-of-contents line: its title is followed by a page number
    and the next Item ('... Results of Operations 24 Item 7A.'). A real heading is followed by its first paragraph."""
    return TOC_LINE_AFTER.search(text[position:position + TOC_WINDOW]) is not None


def extract_mdna_from_text(text, validate=True):
    """The MD&A section as a string, or None if the boundaries cannot be found or what they enclose is not an MD&A.
    validate=False returns what the rules found without the check (eval/mdna_coverage.py uses it to report rejections)."""
    ok = (lambda section: validate_section(section)[0]) if validate else (lambda section: True)
    candidates = []
    start = find_mdna_start(text)                   # Nicolas's rule
    if start is not None:
        end = find_mdna_end(text, start)
        if end is not None and ok(text[start:end]):
            candidates.append((start, end))
    span = fallback_span(text, validate)            # the earliest valid heading
    if span:
        candidates.append(span)
    if not candidates:
        return None
    # Javier, Nov 5: if both rules find a section, keep the one that starts first. On MLM, Nicolas's confirm phrase
    # matched a running page header ("...Results of Operations The following table..."), half-way into the MD&A.
    start, end = min(candidates)
    return text[start:end]


# --- Javier: one validation rule for every way of finding the MD&A (code written with help from Claude) ---
# JPM (Nov 2026): its Item 7 is a two-sentence pointer ("appears on pages 46-160"), so the fallback paired the table of
# contents with the pointer's Item 7A and returned Items 1 to 6 (158,000 characters of business description and risk
# factors). The section looked fine by length. These checks catch that, and src/locate_mdna.py uses the same function
# to accept or reject what its agent extracts, so the parser and the agent are held to one rule.
ITEM_HEADING = r"\bitem\s+(\d{1,2}[a-c]?)\s*" + DASH
ITEMS_ALLOWED_INSIDE = {"7", "7A", "8"}          # the MD&A's own heading and the ones right after it
MAX_OTHER_ITEMS = 3                              # a real MD&A cross-references a few items at most
MDNA_LANGUAGE = r"\b(?:compared (?:with|to)|increased?|decreased?|results of operations)\b"
MIN_MDNA_LANGUAGE = 3        # Nov 5: was 10; small companies with little activity (MWH, KOAN, LATA) were rejected


def validate_section(section):
    """(True, "ok") if the text looks like an MD&A, else (False, reason)."""
    if not section or len(section) < MIN_SECTION_CHARS:
        return False, f"too short ({len(section or ''):,} characters, an MD&A has at least {MIN_SECTION_CHARS:,})"
    others = {m.group(1).upper() for m in re.finditer(ITEM_HEADING, section, re.IGNORECASE)} - ITEMS_ALLOWED_INSIDE
    if len(others) > MAX_OTHER_ITEMS:
        return False, f"contains headings of other 10-K items ({', '.join(sorted(others)[:8])}): not only the MD&A"
    language = len(re.findall(MDNA_LANGUAGE, section, re.IGNORECASE))
    if language < MIN_MDNA_LANGUAGE:
        return False, f"little MD&A language ({language} comparisons like 'compared with' or 'increased')"
    return True, "ok"


# --- Javier: fallback when the confirm phrase is missing (code written with help from Claude) ---
# Preflight (Nov 3, 2026) found the MD&A in only 10 of 31 test candidates: most 10-Ks open Item 7 with "Overview" or
# "Executive Summary", not "results of operations. The following". In PEP's FY2024 10-K the pattern matches 6 times:
# the table of contents, cross-references in Items 1 and 7A/8, and the real heading (the 4th). Rule: for every Item 7
# match, find where the section would end (first Item 7A / Item 8 heading at least MIN_SECTION_CHARS later). The real
# end is shared by the TOC entry, the early cross-references and the real heading, so for each end we keep only the
# CLOSEST heading before it, then take the longest of those sections.
#
# Nov 5, 2026: replaced "closest heading" with "earliest heading that passes validation". Martin Marietta prints
# "Item 7 - Management's Discussion..." as a running header on every page, so the closest heading was the LAST page
# header and the section lost its first half (53k of ~110k characters). Now: skip table-of-contents entries (another
# Item heading follows within TOC_WINDOW characters), try the remaining headings from earliest to latest, and keep the
# first whose section passes validate_section(). Early cross-references (PEP, Item 1) produce sections that contain
# other Items, fail validation and are skipped, which is what the closest-heading rule was protecting against.
def fallback_span(text, validate=True):
    """(start, end) of the MD&A by the earliest-valid-heading rule, or None. Table-of-contents lines and
    cross-references are skipped. validate=False returns the earliest candidate unchecked."""
    for match in re.finditer(START_PATTERN, text, re.IGNORECASE):
        start = match.start()
        if is_toc_entry(text, start) or is_cross_reference(text, start):
            continue
        end = find_mdna_end(text, start)
        if end is None:
            continue
        if not validate or validate_section(text[start:end])[0]:
            return start, end
    return None


def extract_mdna_fallback(text, validate=True):
    """MD&A by the earliest-valid-heading rule, or None."""
    span = fallback_span(text, validate)
    return text[span[0]:span[1]] if span else None


@lru_cache(maxsize=8)
def fetch_html(url):
    """The 10-K's HTML, or None. Cached (a few filings only: some are over 10 MB) so src/locate_mdna.py reuses it."""
    response = _get(url)
    return response.text if response.status_code == 200 else None


@lru_cache(maxsize=64)
def extract_mdna_from_url(url):
    """Download one 10-K and return its MD&A text, or None. Cached: each filing is downloaded once per session."""
    html = fetch_html(url)
    if html is None:
        return None
    return extract_mdna_from_text(html_to_text(html))


def filings_to_read(cik, skip_newest=SKIP_NEWEST, how_many=FILINGS_TO_READ):
    """The 10-Ks whose MD&A the tools read, newest first (the newest is skipped in backtest mode)."""
    return list_10ks(cik, how_many=how_many + skip_newest)[skip_newest:]


def extract_mdna(cik, skip_newest=SKIP_NEWEST, how_many=FILINGS_TO_READ):
    """MD&A for the company's recent 10-Ks, newest first: [{"fiscal_year_end", "url", "text"}].
    Filings where the section could not be found are left out, so an empty list means 'MD&A not found'."""
    found = []
    for filing in filings_to_read(cik, skip_newest, how_many):
        text = extract_mdna_from_url(filing["url"])
        if text:
            found.append({"fiscal_year_end": filing["fiscal_year_end"], "url": filing["url"], "text": text})
    return found


# --- The tool ----------------------------------------------------------------------------------------------
def get_mdna(cik, skip_newest=SKIP_NEWEST):
    """The agent's tool. Returns {"filings": [{"fiscal_year_end", "url", "chars", "text"}]} with the MD&A of each
    filing read, or {"error": "MD&A not found", "cik": cik} when no section could be extracted."""
    sections = extract_mdna(cik, skip_newest=skip_newest)
    hint = "call locate_mdna to find the section through the filing's table of contents"
    if not sections:
        return {"error": "MD&A not found", "cik": cik, "next_step": hint}
    filings = []
    for s in sections:
        text = s["text"] if MAX_CHARS_PER_FILING is None else s["text"][:MAX_CHARS_PER_FILING]
        filings.append({"fiscal_year_end": s["fiscal_year_end"], "url": s["url"], "chars": len(s["text"]),
                        "truncated": len(text) < len(s["text"]), "text": text})
    result = {"cik": cik, "filings": filings}
    missing = [f["fiscal_year_end"] for f in filings_to_read(cik, skip_newest)
               if f["fiscal_year_end"] not in {s["fiscal_year_end"] for s in sections}]
    if missing:
        result["missing_filings"] = missing             # found in one 10-K but not the other
        result["next_step"] = hint
    return result


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
