# --- Javier: stub tool bodies for the agent prototype (code written with help from Claude) ---
# These return canned data so the tool-calling loop can be built and demonstrated before the real
# ratio calculator (issue: ratios), MD&A extractor (#10) and retrieval exist. Swap them out in src/agent.py IMPL
# as the real functions land. Every stub returns plain dicts/lists so they serialize into a function response.
#
# The company card is NOT stubbed: src/edgar.company_card() is real and gives the model a real industry signal.


def compute_general_ratios(cik):
    return {
        "note": "STUB DATA, not from XBRL",
        "cik": cik,
        "fy_current": {"operating_margin": 0.168, "revenue_growth": 0.042, "opex_ratio": 0.221,
                       "asset_turnover": 0.78, "leverage_debt_to_equity": 1.9},
        "fy_prior": {"operating_margin": 0.159, "revenue_growth": 0.071, "opex_ratio": 0.226,
                     "asset_turnover": 0.81, "leverage_debt_to_equity": 2.1},
    }


def compute_financial_sector_ratios(cik):
    return {
        "note": "STUB DATA, not from XBRL",
        "cik": cik,
        "fy_current": {"net_interest_income_growth": 0.031, "efficiency_ratio": 0.56, "provision_to_loans": 0.011,
                       "equity_to_assets": 0.084, "net_interest_margin": 0.027},
        "fy_prior": {"net_interest_income_growth": 0.118, "efficiency_ratio": 0.54, "provision_to_loans": 0.008,
                     "equity_to_assets": 0.081, "net_interest_margin": 0.026},
    }


_PASSAGES = {
    "outlook": "We expect demand to moderate in the coming year as customers work through elevated inventory levels, "
               "partially offset by pricing actions taken in the second half.",
    "margin": "Operating margin improved 90 basis points, driven by favorable price realization and lower freight costs, "
              "partially offset by higher warranty expense.",
    "cost": "We anticipate continued inflation in labor and material costs and are implementing productivity initiatives "
            "to mitigate the impact.",
    "credit": "The provision for credit losses increased, reflecting a deterioration in the macroeconomic outlook and "
              "growth in card balances, while net charge-offs remained below pre-pandemic levels.",
    "interest": "Net interest income is expected to decline modestly as deposit repricing continues and the benefit of "
                "higher asset yields moderates.",
}


def search_mdna(cik, query, k=4):
    """Return canned passages whose topic words appear in the query; empty list if none match.
    The real version embeds the FY2023/FY2024 MD&A chunks and retrieves by similarity."""
    q = query.lower()
    hits = [{"text": text, "fiscal_year": "FY_current", "position": i, "topic": topic}
            for i, (topic, text) in enumerate(_PASSAGES.items())
            if topic in q or (topic == "outlook" and any(w in q for w in ["demand", "guidance", "expect"]))
            or (topic == "interest" and "margin" in q and "net" in q)]
    return {"note": "STUB DATA, not from a 10-K", "query": query, "passages": hits[:k]}
