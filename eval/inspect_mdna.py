# --- Javier: see what the MD&A extractor actually returned (code written with help from Claude) ---
# Diagnostic only, it changes nothing. For each 10-K the tool would read, prints:
#   - every "Item 7. Management..." heading found, where, its context, and whether the confirm phrase follows it
#   - every "Item 7A / Item 8" ending found
#   - which rule produced the section (Nicolas's main rule or the closest-heading fallback), its start, end, length
#   - which other "Item N" headings appear INSIDE the extracted text (a real MD&A should contain none, or only
#     cross-references), plus its first and last 300 characters
# Run from the repository root:   python -m eval.inspect_mdna JPM        (add 1 at the end to skip the newest 10-K)
import re
import sys

from src import mdna
from src.edgar import ticker_to_cik, list_10ks, _get

ITEM_HEADING = r"\bitem\s+(\d{1,2}[a-c]?)\s*[.:\-]"


def role(text, pos):
    if mdna.is_toc_entry(text, pos):
        return "contents"
    return "reference" if mdna.is_cross_reference(text, pos) else "heading"


def context(text, pos, width=120):
    return text[max(0, pos - 20):pos + width].replace("\n", " ")


ticker = sys.argv[1].upper()
skip = int(sys.argv[2]) if len(sys.argv) > 2 else 0
cik, name = ticker_to_cik(ticker)
print(f"{ticker} ({name}), CIK {cik}, skipping newest: {skip}")

for filing in list_10ks(cik, how_many=mdna.FILINGS_TO_READ + skip)[skip:]:
    print("\n" + "=" * 100)
    print(f"10-K for FY ending {filing['fiscal_year_end']}: {filing['url']}")
    response = _get(filing["url"])
    text = mdna.html_to_text(response.text)
    print(f"Document: {len(text):,} characters of text")

    print("\nItem 7 headings (START_PATTERN):")
    for m in re.finditer(mdna.START_PATTERN, text, re.IGNORECASE):
        confirmed = bool(re.search(mdna.START_CONFIRM, text[m.start():m.start() + 500], re.IGNORECASE))
        end = mdna.find_mdna_end(text, m.start())
        print(f"   at {m.start():>9,}  {role(text, m.start()):9}  confirm phrase: {'yes' if confirmed else 'no ':3}  "
              f"ending found at: {end if end is None else f'{end:,}'}  | {context(text, m.start())}")

    print("\nItem 7A / Item 8 endings (END_PATTERN):")
    for m in re.finditer(mdna.END_PATTERN, text, re.IGNORECASE):
        print(f"   at {m.start():>9,}  {role(text, m.start()):9}  | {context(text, m.start())}")

    start = mdna.find_mdna_start(text)
    main = None
    if start is not None:
        end = mdna.find_mdna_end(text, start)
        main = (start, end) if end is not None and mdna.validate_section(text[start:end])[0] else None
    span = mdna.fallback_span(text)
    section = mdna.extract_mdna_from_text(text)
    if not section:
        method = "none: MD&A not found"
    elif main and (not span or main[0] <= span[0]):
        method = "main rule (Nicolas's confirm phrase)"
    else:
        method = "fallback (earliest valid heading)"
    print(f"\nResult: {method}")
    if not section:
        continue
    begin = text.find(section)
    print(f"   section from {begin:,} to {begin + len(section):,}: {len(section):,} characters "
          f"({len(section) / len(text):.0%} of the document)")

    print("   'Item N' headings inside the section:")
    seen = {}
    for m in re.finditer(ITEM_HEADING, section, re.IGNORECASE):
        seen.setdefault(m.group(1).upper(), []).append(m.start())
    for item, positions in sorted(seen.items(), key=lambda kv: kv[1][0]):
        print(f"      Item {item:4} x{len(positions):<3} first at {positions[0]:>9,}  | {context(section, positions[0], 90)}")
    print(f"\n   FIRST 300: {section[:300]}")
    print(f"\n   LAST 300:  {section[-300:]}")
