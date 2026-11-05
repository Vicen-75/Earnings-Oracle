# --- Javier: industry ratio directory, the corpus the model retrieves from (code written with help from Claude) ---
# Workshop feedback (Oct 28): "A directory with definitions on how to calculate ratios depending on the industry needs
# to be added to make the model retrieve information from it and correctly execute tool calling."
#
# This file is the single source of truth for that directory:
#   RATIOS           every ratio the model may ask compute_ratios() for: definition, formula, XBRL tags, how to read it
#   INDUSTRY_GROUPS  what drives operating income in each industry, which ratios matter there and why,
#                    and what to look for in the MD&A
# The model reaches it through the get_industry_playbook tool (src/agent.py). docs/ratio_directory.md is generated
# from this file so the human-readable version never drifts:   python -m src.ratio_directory > docs/ratio_directory.md
#
# Design choice: the code maps a SIC code to a group, but the model can ask for any other group by name (a conglomerate,
# or a company whose SIC code is misleading). The playbook recommends; the model decides what to compute.

# --- 1. Ratio definitions --------------------------------------------------------------------------------------------
# kind: "margin" (share of revenue), "growth" (change vs prior year), "multiple" (x times), "days"
RATIOS = {
    # Growth
    "revenue_growth": {
        "kind": "growth", "family": "growth",
        "definition": "Change in revenue versus the prior fiscal year.",
        "formula": "(Revenue[t] - Revenue[t-1]) / |Revenue[t-1]|",
        "tags": "Revenues, RevenueFromContractWithCustomerExcludingAssessedTax, SalesRevenueNet",
        "read_it": "Top-line momentum. Operating income rarely grows for long when revenue shrinks, unless costs are cut.",
    },
    "operating_income_growth": {
        "kind": "growth", "family": "growth",
        "definition": "Change in operating income versus the prior fiscal year.",
        "formula": "(OperatingIncome[t] - OperatingIncome[t-1]) / |OperatingIncome[t-1]|",
        "tags": "OperatingIncomeLoss",
        "read_it": "Last year's direction. Momentum is real but mean reversion after an unusual year is common.",
    },
    "deferred_revenue_growth": {
        "kind": "growth", "family": "growth",
        "definition": "Change in current deferred revenue (contract liabilities) versus the prior year end.",
        "formula": "(DeferredRevenue[t] - DeferredRevenue[t-1]) / |DeferredRevenue[t-1]|",
        "tags": "ContractWithCustomerLiabilityCurrent, DeferredRevenueCurrent",
        "read_it": "Cash billed but not yet recognized. For subscription businesses it leads next year's revenue.",
    },
    "rpo_growth": {
        "kind": "growth", "family": "growth",
        "definition": "Change in remaining performance obligations (RPO): revenue under signed contracts not yet recognized.",
        "formula": "(RPO[t] - RPO[t-1]) / |RPO[t-1]|",
        "tags": "RevenueRemainingPerformanceObligation",
        "read_it": "Contracted future revenue. RPO is NOT the same as the backlog management quotes: it often covers only "
                   "firm, non-cancellable contracts and can be a fraction of total backlog, so a few large multi-year "
                   "contracts can double it. Read it as direction, check the size against the backlog in the MD&A.",
    },
    # Profitability
    "gross_margin": {
        "kind": "margin", "family": "profitability",
        "definition": "Gross profit as a share of revenue.",
        "formula": "GrossProfit / Revenue  (or (Revenue - CostOfRevenue) / Revenue)",
        "tags": "GrossProfit; CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsSold",
        "read_it": "Pricing power and input costs. A falling gross margin flows straight into operating income.",
    },
    "operating_margin": {
        "kind": "margin", "family": "profitability",
        "definition": "Operating income as a share of revenue.",
        "formula": "OperatingIncome / Revenue",
        "tags": "OperatingIncomeLoss; revenue tags",
        "read_it": "Overall operating efficiency. Compare the trend across the two years, not the level across industries.",
    },
    "sga_to_revenue": {
        "kind": "margin", "family": "profitability",
        "definition": "Selling, general and administrative expense as a share of revenue.",
        "formula": "SG&A / Revenue",
        "tags": "SellingGeneralAndAdministrativeExpense",
        "read_it": "Overhead discipline. Rising SG&A share with flat revenue squeezes operating income.",
    },
    "rnd_to_revenue": {
        "kind": "margin", "family": "profitability",
        "definition": "Research and development expense as a share of revenue.",
        "formula": "R&D / Revenue",
        "tags": "ResearchAndDevelopmentExpense, ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
        "read_it": "Investment intensity. A step up depresses this year's operating income; a pullback can lift it.",
    },
    "cost_ratio": {
        "kind": "margin", "family": "profitability",
        "definition": "Total costs and expenses as a share of revenue.",
        "formula": "CostsAndExpenses / Revenue",
        "tags": "CostsAndExpenses, OperatingExpenses",
        "read_it": "The mirror of operating margin when a company does not report gross profit.",
    },
    # Efficiency
    "inventory_turnover": {
        "kind": "multiple", "family": "efficiency",
        "definition": "Cost of revenue divided by year-end inventory.",
        "formula": "CostOfRevenue / Inventory",
        "tags": "CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsSold; InventoryNet",
        "read_it": "Falling turnover means inventory is piling up, which often leads to markdowns and lower margins.",
    },
    "inventory_growth_minus_revenue_growth": {
        "kind": "growth", "family": "efficiency",
        "definition": "Inventory growth minus revenue growth, in percentage points.",
        "formula": "InventoryGrowth - RevenueGrowth",
        "tags": "InventoryNet; revenue tags",
        "read_it": "Positive and large: inventory building faster than sales, a classic warning sign for next year's margins.",
    },
    "receivables_days": {
        "kind": "days", "family": "efficiency",
        "definition": "Days of revenue sitting in accounts receivable at year end.",
        "formula": "AccountsReceivable / Revenue * 365",
        "tags": "AccountsReceivableNetCurrent",
        "read_it": "Rising days can mean looser credit terms to hold up sales, or weaker customers.",
    },
    "asset_turnover": {
        "kind": "multiple", "family": "efficiency",
        "definition": "Revenue divided by year-end total assets.",
        "formula": "Revenue / Assets",
        "tags": "Assets; revenue tags",
        "read_it": "How hard the asset base works. Most useful in capital-heavy industries.",
    },
    # Capital intensity and cash
    "capex_to_revenue": {
        "kind": "margin", "family": "capital_and_cash",
        "definition": "Capital expenditure as a share of revenue.",
        "formula": "PaymentsToAcquirePropertyPlantAndEquipment / Revenue",
        "tags": "PaymentsToAcquirePropertyPlantAndEquipment",
        "read_it": "Heavy recent capex raises next year's depreciation, which weighs on operating income until it pays off.",
    },
    "depreciation_to_revenue": {
        "kind": "margin", "family": "capital_and_cash",
        "definition": "Depreciation, depletion and amortization as a share of revenue.",
        "formula": "D&A / Revenue",
        "tags": "DepreciationDepletionAndAmortization, DepreciationAndAmortization, Depreciation",
        "read_it": "The fixed cost of the asset base. High D&A means high operating leverage to volume.",
    },
    "cash_conversion": {
        "kind": "multiple", "family": "capital_and_cash",
        "definition": "Operating cash flow divided by operating income.",
        "formula": "NetCashProvidedByUsedInOperatingActivities / OperatingIncome",
        "tags": "NetCashProvidedByUsedInOperatingActivities; OperatingIncomeLoss",
        "read_it": "Earnings quality. Well below 1 means profits are not turning into cash and may not be sustainable.",
    },
    "liabilities_to_equity": {
        "kind": "multiple", "family": "capital_and_cash",
        "definition": "Total liabilities divided by shareholders' equity.",
        "formula": "Liabilities / StockholdersEquity",
        "tags": "Liabilities; StockholdersEquity",
        "read_it": "Leverage. Matters for resilience, less for next year's operating income direction.",
    },
    "interest_coverage": {
        "kind": "multiple", "family": "capital_and_cash",
        "definition": "Operating income divided by interest expense.",
        "formula": "OperatingIncome / InterestExpense",
        "tags": "OperatingIncomeLoss; InterestExpense, InterestExpenseNonoperating",
        "read_it": "Below about 3x the company may cut spending to protect cash, which can help or hurt operating income.",
    },
    # Financial sector
    "core_income_growth": {
        "kind": "growth", "family": "financial_sector",
        "definition": "Growth in net interest income (banks) or net premiums earned (insurers).",
        "formula": "(Core[t] - Core[t-1]) / |Core[t-1]|",
        "tags": "InterestIncomeExpenseNet, InterestIncomeExpenseAfterProvisionForLoanLoss; PremiumsEarnedNet",
        "read_it": "The revenue engine of a financial firm, in place of revenue growth.",
    },
    "efficiency_ratio": {
        "kind": "margin", "family": "financial_sector",
        "definition": "Noninterest expense as a share of revenue.",
        "formula": "NoninterestExpense / Revenue",
        "tags": "NoninterestExpense; revenue tags",
        "read_it": "Lower is better for a bank. A rising ratio means costs grow faster than income.",
    },
    "provision_to_core_income": {
        "kind": "margin", "family": "financial_sector",
        "definition": "Credit loss provisions as a share of net interest income.",
        "formula": "ProvisionForCreditLosses / NetInterestIncome",
        "tags": "ProvisionForLoanLeaseAndOtherLosses, ProvisionForCreditLosses",
        "read_it": "Credit cost. Provisions swing bank earnings more than anything else in a downturn.",
    },
    "equity_to_assets": {
        "kind": "margin", "family": "financial_sector",
        "definition": "Shareholders' equity as a share of total assets.",
        "formula": "StockholdersEquity / Assets",
        "tags": "StockholdersEquity; Assets",
        "read_it": "Capital cushion. Thin capital can force a bank to shrink lending.",
    },
}

# --- 2. Industry groups ----------------------------------------------------------------------------------------------
# sic: list of inclusive (low, high) ranges of SIC codes. First match wins, so narrow ranges come before wide ones.
INDUSTRY_GROUPS = {
    "software_internet": {
        "label": "Software and internet services",
        "sic": [(7370, 7379)],
        "drivers": "Recurring subscription revenue, high gross margins, and how much is reinvested in R&D and sales. "
                   "Operating income moves with revenue growth and with management's choice between growth spend and margin.",
        "key_ratios": {
            "revenue_growth": "the core signal; deceleration usually precedes margin pressure",
            "deferred_revenue_growth": "leads next year's subscription revenue",
            "rpo_growth": "contracted future revenue (RPO); confirm with bookings or ARR in the MD&A",
            "gross_margin": "shifts in cloud hosting costs show up here first",
            "rnd_to_revenue": "a big reinvestment year depresses operating income",
            "sga_to_revenue": "sales and marketing efficiency",
            "operating_margin": "trend of the overall payoff",
        },
        "avoid": "inventory_turnover and capex ratios carry little signal here.",
        "mdna_topics": "net revenue retention, bookings or ARR, pricing changes, AI or cloud transition costs, "
                       "headcount plans, guidance on operating margin",
    },
    "semis_hardware": {
        "label": "Semiconductors and technology hardware",
        "sic": [(3570, 3579), (3660, 3699)],
        "drivers": "Cyclical demand, high fixed costs (fabs, depreciation) and inventory cycles across customers. "
                   "Small revenue changes produce large operating income swings (operating leverage).",
        "key_ratios": {
            "revenue_growth": "where the cycle is",
            "gross_margin": "factory utilization shows up here",
            "inventory_growth_minus_revenue_growth": "inventory building ahead of sales signals a downturn",
            "inventory_turnover": "same signal from the other side",
            "capex_to_revenue": "heavy capex means more depreciation next year",
            "depreciation_to_revenue": "fixed cost base, operating leverage",
            "rnd_to_revenue": "investment intensity",
        },
        "avoid": "deferred revenue is usually small and noisy here.",
        "mdna_topics": "end-market demand by segment, customer inventory levels, utilization, capacity additions, "
                       "pricing, outlook for the next quarter",
    },
    "pharma_medtech": {
        "label": "Pharmaceuticals, biotech and medical devices",
        "sic": [(2830, 2836), (3840, 3851)],
        "drivers": "Product launches and patent expiries, procedure volumes for devices, pricing and reimbursement, "
                   "and lumpy R&D or acquired in-process R&D charges.",
        "key_ratios": {
            "revenue_growth": "launches versus losses of exclusivity",
            "gross_margin": "mix and pricing",
            "rnd_to_revenue": "R&D steps and one-off acquired R&D move operating income a lot",
            "sga_to_revenue": "launch spending",
            "operating_margin": "overall trend",
        },
        "avoid": "asset turnover and leverage say little about next year here.",
        "mdna_topics": "loss of exclusivity dates, launches, pipeline milestones, pricing and reimbursement changes, "
                       "procedure volumes, acquired in-process R&D, litigation charges",
    },
    "energy_mining": {
        "label": "Energy, mining and aggregates (commodity producers)",
        "sic": [(1000, 1499), (2900, 2999)],
        "drivers": "Commodity prices first, volumes second. Costs are largely fixed, so price swings pass almost fully into "
                   "operating income. Ratios describe last year's price environment, not next year's.",
        "key_ratios": {
            "revenue_growth": "mostly a price signal",
            "operating_margin": "how much of price moves reaches the bottom line",
            "depreciation_to_revenue": "depletion and fixed costs, operating leverage",
            "capex_to_revenue": "production growth ahead",
            "cash_conversion": "earnings quality",
        },
        "avoid": "gross margin and inventory ratios are distorted by commodity accounting; R&D is negligible.",
        "mdna_topics": "realized prices versus prior year, production or shipment guidance, hedging, cost per unit, "
                       "pricing actions (aggregates), reserve or project updates",
        "caution": "Lean on the MD&A for price outlook; past ratios are weak predictors when prices turn.",
    },
    "materials_chemicals": {
        "label": "Chemicals, paper, metals and other materials",
        "sic": [(2600, 2699), (2800, 2829), (2850, 2899), (3200, 3399)],
        "drivers": "Spread between selling prices and raw material or energy costs, plus volumes tied to industrial demand.",
        "key_ratios": {
            "revenue_growth": "price and volume combined",
            "gross_margin": "price versus raw material spread",
            "operating_margin": "overall trend",
            "inventory_turnover": "demand slowing",
            "capex_to_revenue": "capacity coming on line",
        },
        "avoid": "R&D and deferred revenue are minor.",
        "mdna_topics": "price versus volume split, raw material and energy costs, pricing actions, end-market demand",
    },
    "consumer_staples": {
        "label": "Consumer staples (food, beverages, household and personal products)",
        "sic": [(2000, 2199), (2840, 2844)],
        "drivers": "Steady volumes, pricing power against input costs, and marketing spend. "
                   "After big price increases, volumes and margins often normalize.",
        "key_ratios": {
            "revenue_growth": "price plus volume",
            "gross_margin": "pricing versus commodity input costs",
            "sga_to_revenue": "advertising and promotion spend",
            "operating_margin": "overall trend",
            "inventory_turnover": "demand or destocking",
        },
        "avoid": "R&D and backlog are minor.",
        "mdna_topics": "organic growth split into price and volume, input cost inflation, productivity programs, "
                       "currency, restructuring charges, divestitures",
    },
    "restaurants": {
        "label": "Restaurants",
        "sic": [(5810, 5819)],
        "drivers": "Same-store sales, new unit growth, food and labor costs, and the franchise mix "
                   "(franchise fees carry very high margins).",
        "key_ratios": {
            "revenue_growth": "units plus same-store sales",
            "operating_margin": "food and labor cost pressure",
            "sga_to_revenue": "overhead",
            "capex_to_revenue": "new unit build-out",
        },
        "avoid": "gross margin is often not reported; inventory is negligible.",
        "mdna_topics": "comparable or same-store sales, traffic versus check, unit openings, food and labor inflation, "
                       "refranchising",
    },
    "retail": {
        "label": "Retail",
        "sic": [(5200, 5809), (5820, 5999)],
        "drivers": "Comparable sales, gross margin (markdowns, freight, shrink) and store cost leverage. "
                   "Inventory problems show up before margin problems.",
        "key_ratios": {
            "revenue_growth": "comparable sales plus new stores",
            "gross_margin": "markdowns and freight",
            "inventory_growth_minus_revenue_growth": "inventory building ahead of sales means markdowns next year",
            "inventory_turnover": "same signal",
            "sga_to_revenue": "store cost leverage",
            "operating_margin": "overall trend",
        },
        "avoid": "R&D and backlog are not relevant.",
        "mdna_topics": "comparable sales, traffic and ticket, big-ticket demand, housing activity (home improvement), "
                       "markdowns, shrink, store openings",
    },
    "industrials": {
        "label": "Industrials, machinery, aerospace and defense, distribution",
        "sic": [(3400, 3569), (3580, 3659), (3700, 3839), (5000, 5199)],
        "drivers": "Order backlog, pricing versus material costs, and volume across the economic cycle. "
                   "Defense revenue follows government budgets and contracted backlog.",
        "key_ratios": {
            "rpo_growth": "contracted future revenue; RPO is often narrower than quoted backlog, so check the MD&A backlog figure",
            "revenue_growth": "where the cycle is",
            "gross_margin": "price versus cost",
            "operating_margin": "overall trend",
            "inventory_growth_minus_revenue_growth": "dealer or channel inventory building",
            "receivables_days": "customer health",
        },
        "avoid": "deferred revenue and R&D are secondary except in aerospace.",
        "mdna_topics": "orders and backlog, book-to-bill, dealer inventory, price realization, material and labor costs, "
                       "program charges (defense), segment outlook",
    },
    "transportation": {
        "label": "Transportation (rail, trucking, airlines, logistics)",
        "sic": [(4000, 4799)],
        "drivers": "Volumes tied to the economy, pricing, fuel costs and fixed network costs.",
        "key_ratios": {
            "revenue_growth": "volume plus price",
            "operating_margin": "operating ratio trend (rail reports 1 minus this)",
            "cost_ratio": "fuel and labor pressure",
            "depreciation_to_revenue": "fixed network cost",
            "capex_to_revenue": "fleet or network investment",
        },
        "avoid": "inventory and R&D are not relevant.",
        "mdna_topics": "volumes by segment, pricing, fuel, labor agreements, network productivity",
    },
    "utilities_waste": {
        "label": "Utilities and waste management",
        "sic": [(4900, 4999)],
        "drivers": "Regulated or contracted pricing, steady volumes, and capital investment that earns a return. "
                   "Operating income usually grows slowly and steadily.",
        "key_ratios": {
            "revenue_growth": "pricing plus volume",
            "operating_margin": "overall trend",
            "capex_to_revenue": "rate base or fleet investment",
            "depreciation_to_revenue": "fixed cost",
            "interest_coverage": "heavy debt use",
        },
        "avoid": "inventory and R&D are not relevant.",
        "mdna_topics": "price increases, volume, rate cases, acquisitions, recycling commodity prices (waste)",
    },
    "banks": {
        "label": "Banks and lending institutions",
        "sic": [(6000, 6199)],
        "drivers": "Net interest income (loan growth and interest rates), credit losses and cost control. "
                   "Banks usually do not report an operating income line.",
        "key_ratios": {
            "core_income_growth": "net interest income trend",
            "efficiency_ratio": "cost control",
            "provision_to_core_income": "credit costs",
            "equity_to_assets": "capital cushion",
        },
        "avoid": "general ratios (gross margin, inventory, capex) do not apply.",
        "mdna_topics": "net interest margin outlook, rate sensitivity, loan growth, credit quality and reserve builds, "
                       "expense guidance",
        "caution": "If the company card says has_operating_income_tag is false, the target is not defined; "
                   "say so instead of guessing.",
    },
    "insurance": {
        "label": "Insurance (property and casualty, life, health)",
        "sic": [(6300, 6411)],
        "drivers": "Premium growth, claims (loss ratio, catastrophes, medical costs) and investment income. "
                   "Health insurers often do report operating income; most others do not.",
        "key_ratios": {
            "core_income_growth": "premiums earned trend",
            "efficiency_ratio": "expense control",
            "equity_to_assets": "capital cushion",
            "operating_margin": "if the company reports operating income (health insurers)",
            "revenue_growth": "if premiums are not tagged",
        },
        "avoid": "inventory and capex ratios do not apply.",
        "mdna_topics": "premium rate increases, loss or medical cost ratio trends, catastrophe losses, reserve development, "
                       "membership (health), utilization trends",
    },
    "general": {
        "label": "General (no specific playbook)",
        "sic": [],
        "drivers": "Use the broad set and let the MD&A explain what drives the business.",
        "key_ratios": {
            "revenue_growth": "top-line momentum",
            "operating_margin": "overall trend",
            "operating_income_growth": "last year's direction",
            "gross_margin": "pricing versus costs",
            "sga_to_revenue": "overhead",
        },
        "avoid": "",
        "mdna_topics": "management's outlook, demand, pricing, cost pressures, one-off charges",
    },
}


def group_for_sic(sic_code):
    """Name of the industry group for a SIC code; 'general' if none matches."""
    try:
        sic = int(sic_code)
    except (TypeError, ValueError):
        return "general"
    for name, group in INDUSTRY_GROUPS.items():
        if any(low <= sic <= high for low, high in group["sic"]):
            return name
    return "general"


# --- 3. The tool --------------------------------------------------------------------------------------------------
def get_industry_playbook(sic_code=None, group=None):
    """The agent's retrieval tool over this directory.
    Give a SIC code (from the company card) or a group name. Returns what drives operating income in that industry,
    the recommended ratios with reasons and full definitions, the ratios to avoid, and what to look for in the MD&A.
    The list of other groups comes back too, so the model can ask for a second one (conglomerates)."""
    if group and group not in INDUSTRY_GROUPS:
        return {"error": f"unknown group '{group}'", "available_groups": list(INDUSTRY_GROUPS)}
    name = group or group_for_sic(sic_code)
    g = INDUSTRY_GROUPS[name]
    return {
        "group": name,
        "label": g["label"],
        "matched_from": "group name" if group else f"SIC code {sic_code}",
        "what_drives_operating_income": g["drivers"],
        "recommended_ratios": [
            {"ratio": r, "why_here": why, "definition": RATIOS[r]["definition"], "formula": RATIOS[r]["formula"],
             "how_to_read": RATIOS[r]["read_it"]}
            for r, why in g["key_ratios"].items()
        ],
        "ratios_to_avoid": g["avoid"],
        "mdna_topics": g["mdna_topics"],
        "caution": g.get("caution", ""),
        "all_ratio_names": list(RATIOS),
        "available_groups": {k: v["label"] for k, v in INDUSTRY_GROUPS.items()},
    }


# --- 4. Human-readable version (docs/ratio_directory.md) ------------------------------------------------------------
def to_markdown():
    lines = ["# Ratio directory by industry", "",
             "Generated from `src/ratio_directory.py` (do not edit by hand: "
             "`python -m src.ratio_directory > docs/ratio_directory.md`).", "",
             "The model retrieves from this directory with the `get_industry_playbook` tool, then chooses which ratios "
             "to compute with `compute_ratios`. The playbook recommends; the model decides.", "",
             "## Industry groups", ""]
    for name, g in INDUSTRY_GROUPS.items():
        sic = ", ".join(f"{lo}-{hi}" for lo, hi in g["sic"]) or "fallback"
        lines += [f"### {g['label']} (`{name}`, SIC {sic})", "", f"**What drives operating income.** {g['drivers']}", "",
                  "| Ratio | Why it matters here |", "|---|---|"]
        lines += [f"| `{r}` | {why} |" for r, why in g["key_ratios"].items()]
        lines += ["", f"**Avoid.** {g['avoid'] or 'nothing specific'}", "", f"**MD&A topics.** {g['mdna_topics']}", ""]
        if g.get("caution"):
            lines += [f"**Caution.** {g['caution']}", ""]
    lines += ["## Ratio definitions", "", "| Ratio | Definition | Formula | XBRL tags | How to read it |",
              "|---|---|---|---|---|"]
    lines += [f"| `{r}` | {d['definition']} | {d['formula']} | {d['tags']} | {d['read_it']} |" for r, d in RATIOS.items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(to_markdown(), end="")
