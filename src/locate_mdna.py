# --- Javier: MD&A locator, a small bounded agent (code written with help from Claude) ---
# Used only when the parser in src/mdna.py cannot find a valid MD&A. Example: JPM's Item 7 is a two-sentence pointer
# ("appears on pages 46-160"); the real section is a GROUP of linked entries in the annual report's own table of
# contents later in the same file ("Management's discussion and analysis:" -> Introduction ... Forward-Looking
# Statements). Finding it takes judgment (follow the pointer, read the group structure), so a model does it, in a loop:
#
#   the code builds an OUTLINE of the filing: every internal link (text, page, group heading, contents table) plus
#   every place the text says "Management's discussion and analysis" or "Item 7/7A/8". Each entry is an anchor id.
#   the model may PEEK at an anchor (the first lines there) and EXTRACT between two anchors. extract() runs the same
#   validate_section() as the parser; if it fails the model gets the reason and tries again. Max MAX_CALLS calls.
#
# The model can only choose among anchors that exist in the file, so it cannot invent a location.
#
# Known limitation (Nov 5, team decision): one start and one end per filing. Reorganized 10-Ks can split the MD&A.
# Honeywell: MD&A (p. 15) and Review of Business Segments (p. 24), then Risk Factors (p. 30) and market risks (p. 40)
# in the middle, then Liquidity, Critical Accounting Estimates and Other Matters (p. 40-49). The locator returns the
# first block (overview, results, segments, which drive the prediction) and misses the second. Not worth a multi-range
# extract for a few reorganized filers before the presentation.
# Run by hand from the repository root:   python -m src.locate_mdna JPM
import re
import sys
import time
from functools import lru_cache

from bs4 import BeautifulSoup, NavigableString
from google.genai import types

from src.edgar import ticker_to_cik
from src.llm import client, MODEL
from src.mdna import (fetch_html, extract_mdna_from_url, filings_to_read, validate_section, START_PATTERN, DASH,
                      SKIP_NEWEST)
from src.prompts import LOCATE_SYSTEM_V1

MAX_CALLS = 8                     # tool calls per filing (Nov 5: was 6; the end check makes the model retry more)
MAX_OUTLINE_ENTRIES = 400
PEEK_CHARS = 700
LOCATED_MAX_CHARS = 200_000       # JPM's real MD&A is ~115 pages (~700,000 characters); more than the free tier takes
MARK = "\u0000"

TEXT_HITS = [
    (r"management.s discussion and analysis", "text says 'Management's discussion and analysis'"),
    (START_PATTERN, "Item 7 heading"),
    (r"\bitem\s+7a\s*" + DASH, "Item 7A heading"),
    (r"\bitem\s+8\s*" + DASH, "Item 8 heading"),
    (r"management.s report on internal control", "text says 'Management's report on internal control'"),
]
PAGE = re.compile(r"(\d{1,3}(?:\s*[-–]\s*\d{1,3})?)\s*$")
NUMBER_ONLY = re.compile(r"[\d\s\-–]+")
# The end check: a complete MD&A ends where ANOTHER part of the 10-K begins. Nov 5, round 1: MCD's first extraction
# stopped at "OUTLOOK", inside the MD&A. Round 2: the list was too narrow (MCD puts its MD&A first, followed by Item 5
# and Risk Factors, so the right answer was rejected) and too loose (HON passed because the first sentence of
# "Critical Accounting Estimates" says "consolidated financial statements"). Now: any 10-K part counts, and only
# HEADINGS are checked: the end anchor's own title and the first END_HEADING_CHARS characters of text after it.
NEXT_SECTION = re.compile(
    r"\bitem\s+\d|quantitative\s+and\s+qualitative|financial\s+statements|supplementary\s+data|"
    r"report\s+of\s+independent|internal\s+control\s+over\s+financial|management.s\s+report\s+on\s+internal|"
    r"consolidated\s+(?:statements?|balance)|risk\s+factors|market\s+for\s+(?:the\s+)?registrant|\bproperties\b|"
    r"legal\s+proceedings|controls\s+and\s+procedures|unresolved\s+staff|cybersecurity|mine\s+safety|"
    r"executive\s+compensation|directors,?\s+executive\s+officers|\bexhibits\b|\bsignatures\b|"
    r"changes\s+in\s+and\s+disagreements|principal\s+account", re.IGNORECASE)
END_HEADING_CHARS = 50


# --- 1. The outline -------------------------------------------------------------------------------------------
def _cells(row):
    return row.find_all(["td", "th"], recursive=False)


def _page_and_group(a, internal_link):
    """(page, group heading, row title) of a contents-table link. Works column by column, because some contents pages
    put two lists side by side in one table (JPM: MD&A sections on the left, notes on the right). The row title matters
    when the link itself is only a page number (MCD: the title sits in another cell, the link says '11')."""
    cell = a.find_parent(["td", "th"])
    row = cell.find_parent("tr") if cell is not None else None
    if row is None:
        return "", "", ""
    cells = _cells(row)
    col = next((i for i, c in enumerate(cells) if c is cell), 0)
    page = ""
    for c in cells[col + 1:col + 4]:                       # the page number sits in one of the next cells
        if c.find("a", href=internal_link):
            break
        m = PAGE.search(c.get_text(" ", strip=True))
        if m:
            page = m.group(1)
            break
    group = ""
    for previous in row.find_previous_siblings("tr", limit=60):   # nearest row above with text but no link there
        pcells = _cells(previous)
        if col < len(pcells):
            text = pcells[col].get_text(" ", strip=True)
            if (text and not pcells[col].find("a", href=internal_link) and not PAGE.fullmatch(text)
                    and text.lower() not in ("page", "pages")):
                group = text[:80]
                break
    title = ""
    if NUMBER_ONLY.fullmatch(a.get_text(" ", strip=True)):
        title = " ".join(c.get_text(" ", strip=True) for c in cells if not c.find("a", href=internal_link))
        title = re.sub(r"\s+", " ", re.sub(r"\b\d{1,3}\b", " ", title)).strip()[:100]
    return page, group, title


@lru_cache(maxsize=4)
def build_document(url):
    """{"text", "anchors": {id: {"pos", "label"}}} for one 10-K. Text positions of link targets are found by placing
    a marker before each target element and flattening the HTML once."""
    html = fetch_html(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    internal_link = re.compile(r"^#.+")

    targets = {}                                            # html id -> element
    for el in soup.find_all(attrs={"id": True}):
        targets.setdefault(el["id"], el)
    for el in soup.find_all("a", attrs={"name": True}):
        targets.setdefault(el["name"], el)

    tables, links, seen = {}, [], set()
    for a in soup.find_all("a", href=internal_link):
        target = a["href"][1:]
        text = a.get_text(" ", strip=True)
        if not text or target not in targets or (text.lower(), target) in seen:
            continue
        seen.add((text.lower(), target))
        table = a.find_parent("table")
        page, group, title = _page_and_group(a, internal_link)
        if NUMBER_ONLY.fullmatch(text):                     # the link is a page number: name it by its row
            page = page or text.strip()
            text = f"p. {text.strip()}: {title}" if title else f"p. {text.strip()}"
        if table is not None:
            tables.setdefault(id(table), len(tables) + 1)
        links.append({"text": text[:100], "target": target, "page": page, "group": group,
                      "table": tables.get(id(table), 0) if table is not None else 0})

    marked = {}
    for i, target in enumerate(dict.fromkeys(link["target"] for link in links)):
        if targets[target].parent is not None:
            targets[target].insert_before(NavigableString(f" {MARK}{i}{MARK} "))
            marked[target] = i
    links = [link for link in links if link["target"] in marked]

    raw = soup.get_text(separator=" ", strip=True)
    pieces, positions, last, length = [], {}, 0, 0
    for m in re.finditer(f"{MARK}(\\d+){MARK}", raw):
        pieces.append(raw[last:m.start()])
        length += m.start() - last
        positions[int(m.group(1))] = length
        last = m.end()
    pieces.append(raw[last:])
    text = "".join(pieces)

    anchors = {}
    for n, link in enumerate(links[:MAX_OUTLINE_ENTRIES], 1):
        where = f"contents table {link['table']}" if link["table"] else "link in text"
        group = f" | under '{link['group']}'" if link["group"] else ""
        page = f" | page {link['page']}" if link["page"] else ""
        anchors[f"L{n}"] = {"pos": positions[marked[link["target"]]], "title": link["text"],
                            "label": f"link '{link['text']}' ({where}{group}{page})"}
    n = 0
    for pattern, label in TEXT_HITS:
        for m in list(re.finditer(pattern, text, re.IGNORECASE))[:25]:
            n += 1
            anchors[f"T{n}"] = {"pos": m.start(), "label": label, "title": m.group(0)}
    return {"text": text, "anchors": anchors}


def outline_text(doc):
    """The outline the model reads: one line per anchor, in document order, with position as % of the document."""
    size = max(len(doc["text"]), 1)
    lines = [f"{a_id}: at {a['pos'] / size:.1%} of the document: {a['label']}"
             for a_id, a in sorted(doc["anchors"].items(), key=lambda kv: kv[1]["pos"])]
    return f"Document length: {size:,} characters. {len(lines)} anchors.\n" + "\n".join(lines)


# --- 2. The two tools the locator model can call ----------------------------------------------------------------
def peek(doc, anchor):
    if anchor not in doc["anchors"]:
        return {"error": f"unknown anchor {anchor}"}
    pos = doc["anchors"][anchor]["pos"]
    later = sorted(a["pos"] for a in doc["anchors"].values() if a["pos"] > pos + 50)
    return {"anchor": anchor, "label": doc["anchors"][anchor]["label"],
            "text_here": doc["text"][pos:pos + PEEK_CHARS],
            "characters_to_next_anchor": (later[0] - pos) if later else len(doc["text"]) - pos}


def extract(doc, start_anchor, end_anchor):
    for a in (start_anchor, end_anchor):
        if a not in doc["anchors"]:
            return {"ok": False, "reason": f"unknown anchor {a}"}
    start, end = doc["anchors"][start_anchor]["pos"], doc["anchors"][end_anchor]["pos"]
    if end <= start:
        return {"ok": False, "reason": "the end anchor is not after the start anchor"}
    section = doc["text"][start:end]
    ok, reason = validate_section(section)
    after = doc["text"][end:end + 400]
    heading = re.sub(r"^\W*(?:table\s+of\s+contents\W*)?", "", after, flags=re.IGNORECASE)[:END_HEADING_CHARS]
    title = doc["anchors"][end_anchor].get("title", "")
    if ok and not (NEXT_SECTION.search(title) or NEXT_SECTION.search(heading)):
        ok, reason = False, (f"the section does not end where another part of the 10-K begins: the end anchor is "
                             f"'{title}' and the text there reads \"{after[:120].strip()}...\". That looks like a "
                             f"subsection of the MD&A, so the MD&A probably continues. End at the next 10-K part: "
                             f"another Item (for example Item 7A, Item 8, Risk Factors, Market for Registrant's Common "
                             f"Equity), the financial statements or the report on internal control")
    return {"ok": ok, "reason": reason, "chars": len(section), "text_after_end": after[:200],
            "starts_with": section[:200], "ends_with": section[-200:], "_section": section if ok else None}


S = types.Schema
REASON = S(type="STRING", description="One sentence: what you know so far and what you expect to learn.")
TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="peek", description="Read the first lines of text at an anchor from the outline.",
        parameters=S(type="OBJECT", properties={"reason": REASON, "anchor": S(type="STRING")},
                     required=["reason", "anchor"])),
    types.FunctionDeclaration(
        name="extract",
        description="Cut the text from start_anchor up to (not including) end_anchor and check that it is an MD&A. "
                    "If the check passes you are done; if not, you get the reason and can try other anchors.",
        parameters=S(type="OBJECT", properties={"reason": REASON, "start_anchor": S(type="STRING"),
                                                "end_anchor": S(type="STRING")},
                     required=["reason", "start_anchor", "end_anchor"])),
])


def _generate(contents, config):
    for attempt in range(4):
        try:
            return client.models.generate_content(model=MODEL, contents=contents, config=config)
        except Exception as error:
            if any(code in str(error) for code in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")):
                time.sleep(15)
                continue
            raise
    raise RuntimeError("gave up after repeated retries")


def _observe(tool, result):
    if "error" in result:
        return f"Error: {result['error']}"
    if tool == "peek":
        return (f"{result['label']}: \"{result['text_here'][:160]}...\" "
                f"({result['characters_to_next_anchor']:,} characters to the next anchor)")
    if result["ok"]:
        return f"Valid MD&A: {result['chars']:,} characters, starting \"{result['starts_with'][:100]}...\""
    return f"Rejected ({result['reason']}): {result.get('chars', 0):,} characters"


# --- 3. The loop, one filing at a time --------------------------------------------------------------------------
def locate_in_filing(filing, hint=""):
    """Returns (section_text or None, steps, (start_label, end_label) or None)."""
    doc = build_document(filing["url"])
    if doc is None:
        return None, [{"reason": "", "tool": "download", "args": {}, "observation": "Error: filing not available"}], None
    if not doc["anchors"]:
        return None, [{"reason": "", "tool": "outline", "args": {},
                       "observation": "Error: no links or headings to navigate by"}], None

    config = types.GenerateContentConfig(system_instruction=LOCATE_SYSTEM_V1, tools=[TOOLS], temperature=0,
                                         thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"))
    message = (f"10-K for the fiscal year ending {filing['fiscal_year_end']}.\n{hint}\n\nOUTLINE\n{outline_text(doc)}")
    contents = [types.Content(role="user", parts=[types.Part(text=message)])]
    steps, model_calls = [], 0
    while len(steps) < MAX_CALLS:
        response = _generate(contents, config)
        model_calls += 1
        if not response.function_calls:                         # the model stopped without a section (it says why)
            steps.append({"call": model_calls, "reason": "", "tool": "stop", "args": {},
                          "observation": f"Stopped without a section: {(response.text or '').strip()[:300]}"})
            break
        contents.append(response.candidates[0].content)
        parts = []
        for call in response.function_calls:
            args = dict(call.args or {})
            reason = args.pop("reason", "")
            if call.name == "peek":
                result = peek(doc, args.get("anchor", ""))
            else:
                result = extract(doc, args.get("start_anchor", ""), args.get("end_anchor", ""))
            steps.append({"call": model_calls, "reason": reason, "tool": call.name, "args": args,
                          "observation": _observe(call.name, result)})
            if call.name == "extract" and result.get("ok"):
                labels = (doc["anchors"][args["start_anchor"]]["label"], doc["anchors"][args["end_anchor"]]["label"])
                return result["_section"], steps, labels
            shown = {k: v for k, v in result.items() if k != "_section"}
            parts.append(types.Part.from_function_response(name=call.name, response={"result": shown}))
            if len(steps) >= MAX_CALLS:
                break
        contents.append(types.Content(role="user", parts=parts))
    return None, steps, None


# --- 4. The tool the main agent calls ---------------------------------------------------------------------------
def locate_mdna(cik, skip_newest=SKIP_NEWEST):
    """MD&A for the last two 10-Ks: the parser's when it is valid, the locator agent's otherwise.
    Same shape as get_mdna, plus how each section was found and the locator's steps."""
    filings, steps, hint = [], [], ""
    for filing in filings_to_read(cik, skip_newest):
        text = extract_mdna_from_url(filing["url"])           # already validated by the parser
        how = "parser"
        if not text:
            text, filing_steps, labels = locate_in_filing(filing, hint)
            steps += [{"filing": filing["fiscal_year_end"], **s} for s in filing_steps]
            how = "located by the model from the table of contents"
            if labels:
                hint = (f"Hint: in a newer 10-K of the same company the MD&A ran from {labels[0]} up to {labels[1]}. "
                        "Filings of one company usually share this structure.")
        if text:
            cap = LOCATED_MAX_CHARS if how != "parser" else len(text)       # the parser's sections stay whole
            filings.append({"fiscal_year_end": filing["fiscal_year_end"], "url": filing["url"], "how_found": how,
                            "chars": len(text), "truncated": len(text) > cap, "text": text[:cap]})
    if not filings:
        return {"error": "MD&A not found, even through the table of contents", "cik": cik, "locator_steps": steps}
    return {"cik": cik, "filings": filings, "locator_steps": steps}


if __name__ == "__main__":
    for ticker in sys.argv[1:] or ["JPM"]:
        cik, name = ticker_to_cik(ticker.upper())
        print(f"\n=== {ticker.upper()} ({name}) ===")
        out = locate_mdna(cik)
        for s in out.get("locator_steps", []):
            print(f"   [{s['filing']}] thought: {s['reason']}")
            print(f"   [{s['filing']}] action:  {s['tool']}({s['args']})")
            print(f"   [{s['filing']}] observe: {s['observation']}")
        if "error" in out:
            print(out["error"])
        for f in out.get("filings", []):
            print(f"FY ending {f['fiscal_year_end']}: {f['how_found']}, {f['chars']:,} characters"
                  f"{' (truncated to ' + format(LOCATED_MAX_CHARS, ',') + ')' if f['truncated'] else ''}")
            print(f"   starts: {f['text'][:200]}")
