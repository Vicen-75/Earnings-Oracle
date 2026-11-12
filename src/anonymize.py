# --- Vicente: anonymizer, issue #27 (code written with help from Claude) ---
# Removes the company's identity from everything the model sees, so an anonymized run measures reading, not memory
# (docs/success_metric.md: the headline number is anonymized accuracy).
#
# What is removed, and how it is found:
#   company name and former names   EDGAR submissions (name, formerNames)              -> "the Company"
#   ticker(s) and CIK               EDGAR submissions; the CIK becomes an alias the tools still accept
#   products, brands, subsidiaries  one model call per company on its MD&A, schema-checked (see find_brand_names)
# What stays visible on purpose: the SIC code and industry (the model needs them to pick its playbook), and numbers.
#
# Used by src/agent.py: investigate(ticker, anonymize=True). Checked by eval/anonymize_check.py.
import json
import re
from typing import List

from google.genai import types
from pydantic import BaseModel, Field

from src import edgar
from src.llm import MODEL

COMPANY = "the Company"
PRODUCT = "[PRODUCT]"
TICKER_ALIAS = "COMPANY"            # what the model is told the ticker is; the tools translate it back
CIK_ALIAS = "CIK-HIDDEN"
BRAND_SCAN_CHARS = 30_000           # how much MD&A the brand scan reads (the opening has the business overview)

# Legal-form words that are not part of how a company names itself in prose ("HOME DEPOT, INC." -> "Home Depot")
_SUFFIXES = {"inc", "incorporated", "corp", "corporation", "co", "company", "companies", "ltd", "limited", "plc",
             "llc", "lp", "holdings", "holding", "nv", "sa", "ag", "se", "the", "de", "new"}


class BrandNames(BaseModel):
    names: List[str] = Field(description="Product names, brand names, trademarks, subsidiary names and short names the "
                                         "company uses for itself, exactly as written in the text. Empty if none.")


BRAND_PROMPT = """Below is an excerpt from a company's annual report (MD&A). List every name in it that would reveal \
which company this is: the company's own product names, brand names, trademarks, subsidiary names, and short names \
the company uses for itself. Copy each exactly as written. Do not list generic words (for example "revenue", \
"segment", "North America"), competitors, customers, regulators, people, or places.

Excerpt:
"""


def _clean_name(name):
    """'PROCTER & GAMBLE Co' -> 'Procter & Gamble'; 'COCA COLA CO' -> 'Coca Cola'."""
    name = re.sub(r"/[A-Z]{2,}/?", " ", name)                 # EDGAR state tags like /DE/
    words = [w for w in re.split(r"[\s,.]+", name) if w]
    while words and words[-1].lower().strip(".") in _SUFFIXES:
        words.pop()
    while words and words[0].lower() == "the":
        words.pop(0)
    return " ".join(words)


def _name_pattern(name):
    """A regex for a company name as it appears in prose: spaces or hyphens between words, '&' or 'and', an optional
    leading 'the', an optional legal suffix ('Inc.', 'Corporation').
    Several words: any case. One word: only 'Target' or 'TARGET', never 'target', because one-word names are often
    ordinary words (Target, Progressive, Visa) and the MD&A uses them in their ordinary sense."""
    words = name.split()
    suffix = r"(?:,?\s+(?:Inc\.?|Corp\.?|Corporation|Co\.|Company|Ltd\.?|plc|LLC|Holdings))?"
    if len(words) == 1:
        core = "(?:" + "|".join(re.escape(v) for v in {name.title(), name.upper()}) + ")"
        return re.compile(rf"\b(?:[Tt]he\s+)?{core}{suffix}(?!\w)")
    core = r"[\s\-]+".join(re.escape(w) if w != "&" else r"(?:&|and)" for w in words)
    return re.compile(rf"\b(?:the\s+)?{core}{suffix}(?!\w)", re.IGNORECASE)


def find_brand_names(text, generate):
    """One model call: the names in this MD&A that reveal the company. Returns (names, status).
    The answer must parse into BrandNames; if it does not, or the call fails, the scan is marked failed and the run
    goes on with company names and ticker removed only (the leak check then shows what got through)."""
    config = types.GenerateContentConfig(temperature=0, response_mime_type="application/json",
                                         response_schema=BrandNames)
    try:
        response = generate(MODEL, BRAND_PROMPT + text[:BRAND_SCAN_CHARS], config)
        names = BrandNames.model_validate_json(response.text).names
    except Exception as error:                                   # API error or unparseable answer
        return [], f"failed ({type(error).__name__})"
    # keep only names that really appear in the text and are long enough to be specific
    return _keep_specific(names, text), "ok"


def _brand_pattern(brand):
    """Several words: any case. One word: exactly as written, so the brand 'Space' does not erase the word 'space'."""
    if len(brand.split()) == 1:
        return re.compile(rf"\b{re.escape(brand)}\b")
    return re.compile(rf"\b{re.escape(brand)}\b", re.IGNORECASE)


def _keep_specific(names, text):
    """Drop names that are ordinary words (Nov 6, first run on the 20: ITW's scan returned 'Company' and LMT's
    'Space', which erased those words everywhere). A one-word name is kept only if it appears in the text as
    written more often than in lower case; our own replacement words are never kept."""
    kept = set()
    for n in (n.strip() for n in names):
        if len(n) < 3 or n.lower() in {"company", "the company", "product", "products"} or n.lower() not in text.lower():
            continue
        if len(n.split()) == 1 and n == n.lower():   # Nov 12, set A check: the scan returned 'our' and '3000', which
            continue                                   # erased every 'our' and that number from the MD&A
        if len(n.split()) == 1 and n != n.lower():
            as_written = len(re.findall(rf"\b{re.escape(n)}\b", text))
            lower = len(re.findall(rf"\b{re.escape(n.lower())}\b", text))
            if as_written <= lower:
                continue
        kept.add(n)
    return sorted(kept, key=len, reverse=True)


class Anonymizer:
    """One per analysis. scrub() cleans every tool result before the model sees it; unalias() turns the aliases the
    model uses in its tool calls back into the real ticker and CIK."""

    def __init__(self, ticker, generate=None):
        self.ticker = ticker.upper().strip()
        self.cik, name = edgar.ticker_to_cik(self.ticker)
        submissions = (edgar._get_json(f"https://data.sec.gov/submissions/CIK{self.cik}.json") or {}) if self.cik else {}
        names = [name or ""] + [f.get("name", "") for f in submissions.get("formerNames", [])]
        self.company_names = sorted({c for c in (_clean_name(n) for n in names) if len(c) >= 3}, key=len, reverse=True)
        self.tickers = sorted({t.upper() for t in [self.ticker, *submissions.get("tickers", [])] if len(t) >= 2},
                              key=len, reverse=True)
        self.generate = generate                 # model call for the brand scan; None skips it (names and ticker only)
        self.brands, self.brand_scan = [], "not run"
        self._patterns = [_name_pattern(n) for n in self.company_names]

    # --- what the model sends to the tools ---
    def unalias(self, args):
        real = {TICKER_ALIAS: self.ticker, CIK_ALIAS: self.cik}
        return {k: real.get(v, v) if isinstance(v, str) else v for k, v in args.items()}

    # --- what the tools send to the model ---
    def scrub(self, value):
        """Clean a tool result (dict, list or text), recursively."""
        if isinstance(value, dict):
            if self.generate and self.brand_scan == "not run" and isinstance(value.get("filings"), list):
                text = " ".join(f.get("text", "") for f in value["filings"] if isinstance(f, dict))
                if text:
                    self.brands, self.brand_scan = find_brand_names(text, self.generate)
            out = {}
            for k, v in value.items():
                if k == "url":                    # EDGAR URLs contain the CIK and the company's file names
                    continue
                out[k] = self.scrub(v)            # name, ticker and cik fields are caught by scrub_text
            return out
        if isinstance(value, list):
            return [self.scrub(v) for v in value]
        if isinstance(value, str):
            return self.scrub_text(value)
        return value

    def scrub_text(self, text):
        for pattern in self._patterns:
            text = pattern.sub(COMPANY, text)
        for brand in self.brands:
            text = _brand_pattern(brand).sub(PRODUCT, text)
        for t in self.tickers:
            text = re.sub(rf"\b{re.escape(t)}\b", TICKER_ALIAS, text)          # case-sensitive: 'HD' not 'hd'
        if self.cik:
            text = re.sub(rf"\b0*{int(self.cik)}\b", CIK_ALIAS, text)    # with or without the leading zeros
        return text

    # --- the check ---
    def leaks(self, seen):
        """{term: count} for every identifying term still present in what the model saw (a dict or text).
        Empty means nothing got through. The deterministic check for the 'done when' of issue #27."""
        text = seen if isinstance(seen, str) else json.dumps(seen)
        found = {}
        for name, pattern in zip(self.company_names, self._patterns):
            n = len(pattern.findall(text))
            if n:
                found[name] = n
        for term in self.brands:
            n = len(_brand_pattern(term).findall(text))
            if n:
                found[term] = n
        for t in self.tickers:
            n = len(re.findall(rf"\b{re.escape(t)}\b", text))
            if n:
                found[t] = n
        if self.cik:
            n = len(re.findall(rf"\b0*{int(self.cik)}\b", text))
            if n:
                found[self.cik] = n
        return found
