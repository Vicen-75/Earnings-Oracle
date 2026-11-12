# --- Javier: the structured pass over the MD&A for prompt V6 (issue #45; code written with help from Claude) ---
# read_mdna_items is a tool the agent may call instead of reading the raw MD&A: one focused model call reads the MD&A
# of the last two 10-Ks and lists the specific items in it (guidance, last year's one-offs, named headwinds and
# tailwinds, segment trends), each with a verbatim quote. The agent still decides whether to call it, and get_mdna stays
# available for the full text. Every quote is checked against the MD&A text in code; a quote that is not found word for
# word is removed, so the agent can only cite what is really there (the #53 citation check stays meaningful).
# Nov 11, after the first dev-set run (CAT): (1) items below operating income (interest, other income, pension
# mark-to-market, taxes) are flagged, because the agent counted lower interest income against operating income;
# (2) a quote must be a sentence of prose, because table rows ("Other restructuring (income) costs 445 0.73") passed
# the word-for-word check but say nothing a reader can follow. An item whose only support is a table (often last
# year's one-offs) is kept with source "table" and no quote: the agent can weigh it but not cite it.
# Nov 11, after the dev-set run: 60 runs listed 78 headwinds but only 12 tailwinds and 12 segment trends, a lean the
# tool could pass on to the agent. The extractor is now told to look for positives with the same care.
#
# The extraction runs at temperature 0: the three V6 runs per company differ in judgment, not in what was read.
#
# Run by hand from the repository root:  python -m src.mdna_items CAT
import json
import re
import sys

from google.genai import types

from src.edgar import ticker_to_cik
from src.key_pool import pool
from src.llm import MODEL
from src.locate_mdna import locate_mdna
from src.mdna import SKIP_NEWEST, get_mdna

MAX_ITEMS = 25
KINDS = ["guidance", "one_off", "headwind", "tailwind", "segment_trend"]

EXTRACT_SYSTEM_V1 = """You read the Management's Discussion and Analysis (MD&A) of a company's last two 10-K filings and \
list the specific items in it that bear on next year's operating income (or pre-tax income for banks and insurers). \
You do not predict anything; you list what the text says.

Kinds of item:
- guidance: what management expects for next year (revenue, margins, costs, volumes, orders, backlog, capex, planned \
price or cost actions), with its direction and size when stated.
- one_off: gains or charges in the latest year that management or the numbers show will not recur (impairments, \
write-offs, restructuring, litigation, gains or losses on sales, unusual reserve changes).
- headwind: a named factor that will push results down next year.
- tailwind: a named factor that will push results up next year.
- segment_trend: how a major segment moved and why, when segments move differently.

For every item, say whether it sits below operating income: interest income or expense, other income (expense), \
pension and OPEB mark-to-market or other non-service pension items, foreign exchange gains or losses reported below \
operating profit, equity-method income, and income taxes. These move pre-tax or net income but not operating income.

Rules:
- Look for what pushes results up with the same care as what pushes them down. For every headwind you list, check \
whether management names factors working the other way (demand, orders, pricing, new products, cost savings, easier \
comparisons) and list those as tailwinds or guidance. When the company reports segments, list the trend and outlook of \
each major segment, not only the weak ones.
- Quote one whole sentence of prose that supports the item, copied character for character from the MD&A text \
given, and set source to "sentence". Never quote a table row, a heading or a list of figures, never paraphrase inside \
the quote and never quote from memory.
- If the only support for an item is a table (common for last year's unusual charges and gains), still list it: set \
source to "table", leave quote empty, and give the amount and the table line in "what".
- Prefer the newest filing; use the older one for context on what changed.
- Size is "large", "moderate" or "small" only when the text gives an amount or calls it significant, material or \
minor; otherwise "not stated".
- At most %d items. Leave out boilerplate risk language that names no specific factor.""" % MAX_ITEMS

S = types.Schema
ITEMS_SCHEMA = S(type="OBJECT", properties={
    "items": S(type="ARRAY", items=S(type="OBJECT", properties={
        "kind": S(type="STRING", enum=KINDS),
        "fiscal_year_end": S(type="STRING", description="fiscal year end of the filing the quote comes from"),
        "what": S(type="STRING", description="one short sentence: the item in your words"),
        "effect_on_next_year": S(type="STRING", enum=["up", "down", "unclear"]),
        "size": S(type="STRING", enum=["large", "moderate", "small", "not stated"]),
        "below_operating_line": S(type="BOOLEAN", description="true for interest, other income, pension "
                                  "mark-to-market, equity-method income, taxes: items that do not move operating income"),
        "source": S(type="STRING", enum=["sentence", "table"]),
        "quote": S(type="STRING", description="a whole sentence copied from the MD&A; empty when source is table"),
    }, required=["kind", "fiscal_year_end", "what", "effect_on_next_year", "size", "below_operating_line", "source",
                 "quote"])),
}, required=["items"])


def _norm(text):
    """Compare quotes the way a reader would: same words, ignoring spacing, case and typographic quotes and dashes."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("—", "-").replace("–", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def is_sentence(quote):
    """A quote a reader can follow: at least 8 words, and mostly words rather than figures (a table row such as
    "Other restructuring (income) costs 445 0.73" fails)."""
    tokens = quote.split()
    words = [t for t in tokens if any(c.isalpha() for c in t)]
    return len(tokens) >= 8 and len(words) / len(tokens) >= 0.7


def verify_quotes(items, filings):
    """Keep each quote only if it is a sentence and appears word for word in one of the MD&A texts.
    Returns (items, removed)."""
    sources = [_norm(f["text"]) for f in filings]
    kept, removed = [], 0
    for item in items:
        if item.get("source") == "table":                  # weighed, never cited
            kept.append({**item, "quote": None, "quote_verified": False})
            continue
        quote = _norm(item.get("quote") or "").strip(" .\"'")
        if quote and is_sentence(quote) and any(quote in source for source in sources):
            kept.append({**item, "quote_verified": True})
        else:
            removed += 1
            kept.append({**item, "quote": None, "quote_verified": False})
    return kept, removed


def _source(cik, skip_newest):
    """The MD&A text: the parser's (get_mdna) when it finds both filings, the table-of-contents locator otherwise."""
    found = get_mdna(cik, skip_newest=skip_newest)
    if "error" in found or found.get("missing_filings"):
        located = locate_mdna(cik, skip_newest=skip_newest)
        if "error" not in located:
            return located
    return found


def read_mdna_items(cik, skip_newest=SKIP_NEWEST):
    """The agent's tool (V6). Returns {"cik", "filings": [{fiscal_year_end, url, chars, how_found}], "items": [...],
    "quotes_removed": n} or {"error": ...} when no MD&A could be found."""
    found = _source(cik, skip_newest)
    if "error" in found:
        return {"error": found["error"], "cik": cik}
    filings = found["filings"]
    text = "\n\n".join(f"=== MD&A, 10-K for the fiscal year ending {f['fiscal_year_end']} ===\n{f['text']}"
                       for f in filings)
    config = types.GenerateContentConfig(system_instruction=EXTRACT_SYSTEM_V1, temperature=0,
                                         response_mime_type="application/json", response_schema=ITEMS_SCHEMA,
                                         thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"))
    response = pool.generate(MODEL, text, config)
    try:
        items = json.loads(response.text or "{}").get("items", [])[:MAX_ITEMS]
    except (json.JSONDecodeError, AttributeError):
        return {"error": "the MD&A was found but could not be read into items; call get_mdna for the full text",
                "cik": cik}
    items, removed = verify_quotes(items, filings)
    result = {"cik": cik,
              "filings": [{k: f[k] for k in ("fiscal_year_end", "url", "chars", "truncated", "how_found") if k in f}
                          for f in filings],
              "items": items, "quotes_removed": removed}
    if found.get("missing_filings"):
        result["missing_filings"] = found["missing_filings"]
    notes = []
    if removed:
        notes.append(f"{removed} quote(s) were removed (not found word for word in the MD&A, or not a sentence); "
                     "do not cite them.")
    if any(item.get("source") == "table" for item in items):
        notes.append("Items with source \"table\" come from a table in the MD&A and have no quote: weigh them, do not "
                     "cite them.")
    if any(item.get("below_operating_line") for item in items):
        notes.append("Items with below_operating_line true (interest, other income, pension mark-to-market, taxes) do "
                     "not move operating income; use them only when the target metric is pre-tax income.")
    if notes:
        result["note"] = " ".join(notes)
    return result


if __name__ == "__main__":
    for ticker in sys.argv[1:] or ["CAT"]:
        cik, name = ticker_to_cik(ticker.upper())
        with pool.run():
            out = read_mdna_items(cik)
        print(f"\n=== {ticker.upper()} ({name}) ===")
        print(json.dumps(out, indent=2)[:6000])
