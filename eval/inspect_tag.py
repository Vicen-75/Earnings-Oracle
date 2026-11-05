# --- Javier: look at the raw XBRL rows behind a ratio (code written with help from Claude) ---
# When a ratio looks wrong (e.g. CAT backlog_growth = 98%), print every 10-K value EDGAR has for that tag,
# so we can see which number src/ratios.py picked and why.
#
# Run from the repository root:
#   python -m eval.inspect_tag CAT RevenueRemainingPerformanceObligation
#   python -m eval.inspect_tag CAT RevenueRemainingPerformanceObligation ContractWithCustomerLiabilityCurrent
import sys

from src.edgar import ticker_to_cik, _get_json

ticker, tags = sys.argv[1].upper(), sys.argv[2:]
cik, name = ticker_to_cik(ticker)
facts = (_get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json") or {}).get("facts", {}).get("us-gaap", {})
print(f"{ticker} ({name}), CIK {cik}")
for tag in tags:
    rows = [r for r in facts.get(tag, {}).get("units", {}).get("USD", []) if r.get("form") == "10-K"]
    print(f"\n{tag}: {len(rows)} rows from 10-Ks (in the order src/ratios.py reads them)")
    print(f"   {'start':10}  {'end':10}  {'value (USD bn)':>15}  {'fy':>4} {'fp':>3}  {'filed':10}  frame")
    for r in rows[-20:]:
        print(f"   {r.get('start', ''):10}  {r['end']:10}  {r['val'] / 1e9:15.3f}  {r.get('fy', ''):>4} "
              f"{r.get('fp', ''):>3}  {r.get('filed', ''):10}  {r.get('frame', '')}")
