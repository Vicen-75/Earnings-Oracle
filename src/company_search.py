
# --- Nicolas: intelligent company search ---
# AI-assisted with ChatGPT (GPT-6).
# Matches company names, stock tickers, and spelling mistakes.

import re
from difflib import SequenceMatcher

from src.edgar import _get_json


SEC_URL = "https://www.sec.gov/files/company_tickers.json"

# Common names that may differ from SEC legal names.
ALIASES = {
    "GOOGL": ["google", "alphabet"],
    "GOOG": ["google", "alphabet"],
    "META": ["facebook", "meta"],
}

# Words that are often part of a company's legal name.
SUFFIXES = {
    "INC", "CORP", "CORPORATION", "LTD",
    "PLC", "CO", "INCORPORATED",
}


def normalize(text):
    """Make names easier to compare."""
    text = text.upper().strip()
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def similarity(a, b):
    """Return a similarity score between 0 and 1."""
    return SequenceMatcher(None, a, b).ratio()


def suggest_companies(query, limit=5):
    """Find companies using tickers, names, and approximate spelling."""

    query = normalize(query)

    if len(query) < 2:
        return []

    # Reuse the SEC data-loading function from Vicente's code.
    companies = _get_json(SEC_URL)

    if not companies:
        return []

    matches = []

    for company in companies.values():
        ticker = company["ticker"].upper()
        name = company["title"]
        normalized_name = normalize(name)

        # Remove common legal suffixes.
        short_name = " ".join(
            word for word in normalized_name.split()
            if word not in SUFFIXES
        )

        # Different ways a user might search for this company.
        alternatives = [
            ticker,
            normalized_name,
            short_name,
            *normalized_name.split(),
            *ALIASES.get(ticker, []),
        ]

        alternatives = [normalize(item) for item in alternatives]

        # Exact matches receive the highest score.
        if query in alternatives:
            score = 1.0

        # Names that start with the query are also strong matches.
        elif any(item.startswith(query) for item in alternatives):
            score = 0.95

        # Otherwise, compare approximate spelling.
        else:
            score = max(
                similarity(query, item)
                for item in alternatives
            )

        # Ignore companies with very weak matches.
        if score >= 0.57:
            matches.append({
                "ticker": ticker,
                "name": name,
                "cik": str(company["cik_str"]).zfill(10),
                "score": round(score, 3),
            })

    # Show the best matches first.
    matches.sort(key=lambda item: item["score"], reverse=True)

    return matches[:limit]
