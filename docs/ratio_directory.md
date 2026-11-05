# Ratio directory by industry

Generated from `src/ratio_directory.py` (do not edit by hand: `python -m src.ratio_directory > docs/ratio_directory.md`).

The model retrieves from this directory with the `get_industry_playbook` tool, then chooses which ratios to compute with `compute_ratios`. The playbook recommends; the model decides.

## Industry groups

### Software and internet services (`software_internet`, SIC 7370-7379)

**What drives operating income.** Recurring subscription revenue, high gross margins, and how much is reinvested in R&D and sales. Operating income moves with revenue growth and with management's choice between growth spend and margin.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | the core signal; deceleration usually precedes margin pressure |
| `deferred_revenue_growth` | leads next year's subscription revenue |
| `rpo_growth` | contracted future revenue (RPO); confirm with bookings or ARR in the MD&A |
| `gross_margin` | shifts in cloud hosting costs show up here first |
| `rnd_to_revenue` | a big reinvestment year depresses operating income |
| `sga_to_revenue` | sales and marketing efficiency |
| `operating_margin` | trend of the overall payoff |

**Avoid.** inventory_turnover and capex ratios carry little signal here.

**MD&A topics.** net revenue retention, bookings or ARR, pricing changes, AI or cloud transition costs, headcount plans, guidance on operating margin

### Semiconductors and technology hardware (`semis_hardware`, SIC 3570-3579, 3660-3699)

**What drives operating income.** Cyclical demand, high fixed costs (fabs, depreciation) and inventory cycles across customers. Small revenue changes produce large operating income swings (operating leverage).

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | where the cycle is |
| `gross_margin` | factory utilization shows up here |
| `inventory_growth_minus_revenue_growth` | inventory building ahead of sales signals a downturn |
| `inventory_turnover` | same signal from the other side |
| `capex_to_revenue` | heavy capex means more depreciation next year |
| `depreciation_to_revenue` | fixed cost base, operating leverage |
| `rnd_to_revenue` | investment intensity |

**Avoid.** deferred revenue is usually small and noisy here.

**MD&A topics.** end-market demand by segment, customer inventory levels, utilization, capacity additions, pricing, outlook for the next quarter

### Pharmaceuticals, biotech and medical devices (`pharma_medtech`, SIC 2830-2836, 3840-3851)

**What drives operating income.** Product launches and patent expiries, procedure volumes for devices, pricing and reimbursement, and lumpy R&D or acquired in-process R&D charges.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | launches versus losses of exclusivity |
| `gross_margin` | mix and pricing |
| `rnd_to_revenue` | R&D steps and one-off acquired R&D move operating income a lot |
| `sga_to_revenue` | launch spending |
| `operating_margin` | overall trend |

**Avoid.** asset turnover and leverage say little about next year here.

**MD&A topics.** loss of exclusivity dates, launches, pipeline milestones, pricing and reimbursement changes, procedure volumes, acquired in-process R&D, litigation charges

### Energy, mining and aggregates (commodity producers) (`energy_mining`, SIC 1000-1499, 2900-2999)

**What drives operating income.** Commodity prices first, volumes second. Costs are largely fixed, so price swings pass almost fully into operating income. Ratios describe last year's price environment, not next year's.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | mostly a price signal |
| `operating_margin` | how much of price moves reaches the bottom line |
| `depreciation_to_revenue` | depletion and fixed costs, operating leverage |
| `capex_to_revenue` | production growth ahead |
| `cash_conversion` | earnings quality |

**Avoid.** gross margin and inventory ratios are distorted by commodity accounting; R&D is negligible.

**MD&A topics.** realized prices versus prior year, production or shipment guidance, hedging, cost per unit, pricing actions (aggregates), reserve or project updates

**Caution.** Lean on the MD&A for price outlook; past ratios are weak predictors when prices turn.

### Chemicals, paper, metals and other materials (`materials_chemicals`, SIC 2600-2699, 2800-2829, 2850-2899, 3200-3399)

**What drives operating income.** Spread between selling prices and raw material or energy costs, plus volumes tied to industrial demand.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | price and volume combined |
| `gross_margin` | price versus raw material spread |
| `operating_margin` | overall trend |
| `inventory_turnover` | demand slowing |
| `capex_to_revenue` | capacity coming on line |

**Avoid.** R&D and deferred revenue are minor.

**MD&A topics.** price versus volume split, raw material and energy costs, pricing actions, end-market demand

### Consumer staples (food, beverages, household and personal products) (`consumer_staples`, SIC 2000-2199, 2840-2844)

**What drives operating income.** Steady volumes, pricing power against input costs, and marketing spend. After big price increases, volumes and margins often normalize.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | price plus volume |
| `gross_margin` | pricing versus commodity input costs |
| `sga_to_revenue` | advertising and promotion spend |
| `operating_margin` | overall trend |
| `inventory_turnover` | demand or destocking |

**Avoid.** R&D and backlog are minor.

**MD&A topics.** organic growth split into price and volume, input cost inflation, productivity programs, currency, restructuring charges, divestitures

### Restaurants (`restaurants`, SIC 5810-5819)

**What drives operating income.** Same-store sales, new unit growth, food and labor costs, and the franchise mix (franchise fees carry very high margins).

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | units plus same-store sales |
| `operating_margin` | food and labor cost pressure |
| `sga_to_revenue` | overhead |
| `capex_to_revenue` | new unit build-out |

**Avoid.** gross margin is often not reported; inventory is negligible.

**MD&A topics.** comparable or same-store sales, traffic versus check, unit openings, food and labor inflation, refranchising

### Retail (`retail`, SIC 5200-5809, 5820-5999)

**What drives operating income.** Comparable sales, gross margin (markdowns, freight, shrink) and store cost leverage. Inventory problems show up before margin problems.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | comparable sales plus new stores |
| `gross_margin` | markdowns and freight |
| `inventory_growth_minus_revenue_growth` | inventory building ahead of sales means markdowns next year |
| `inventory_turnover` | same signal |
| `sga_to_revenue` | store cost leverage |
| `operating_margin` | overall trend |

**Avoid.** R&D and backlog are not relevant.

**MD&A topics.** comparable sales, traffic and ticket, big-ticket demand, housing activity (home improvement), markdowns, shrink, store openings

### Industrials, machinery, aerospace and defense, distribution (`industrials`, SIC 3400-3569, 3580-3659, 3700-3839, 5000-5199)

**What drives operating income.** Order backlog, pricing versus material costs, and volume across the economic cycle. Defense revenue follows government budgets and contracted backlog.

| Ratio | Why it matters here |
|---|---|
| `rpo_growth` | contracted future revenue; RPO is often narrower than quoted backlog, so check the MD&A backlog figure |
| `revenue_growth` | where the cycle is |
| `gross_margin` | price versus cost |
| `operating_margin` | overall trend |
| `inventory_growth_minus_revenue_growth` | dealer or channel inventory building |
| `receivables_days` | customer health |

**Avoid.** deferred revenue and R&D are secondary except in aerospace.

**MD&A topics.** orders and backlog, book-to-bill, dealer inventory, price realization, material and labor costs, program charges (defense), segment outlook

### Transportation (rail, trucking, airlines, logistics) (`transportation`, SIC 4000-4799)

**What drives operating income.** Volumes tied to the economy, pricing, fuel costs and fixed network costs.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | volume plus price |
| `operating_margin` | operating ratio trend (rail reports 1 minus this) |
| `cost_ratio` | fuel and labor pressure |
| `depreciation_to_revenue` | fixed network cost |
| `capex_to_revenue` | fleet or network investment |

**Avoid.** inventory and R&D are not relevant.

**MD&A topics.** volumes by segment, pricing, fuel, labor agreements, network productivity

### Utilities and waste management (`utilities_waste`, SIC 4900-4999)

**What drives operating income.** Regulated or contracted pricing, steady volumes, and capital investment that earns a return. Operating income usually grows slowly and steadily.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | pricing plus volume |
| `operating_margin` | overall trend |
| `capex_to_revenue` | rate base or fleet investment |
| `depreciation_to_revenue` | fixed cost |
| `interest_coverage` | heavy debt use |

**Avoid.** inventory and R&D are not relevant.

**MD&A topics.** price increases, volume, rate cases, acquisitions, recycling commodity prices (waste)

### Banks and lending institutions (`banks`, SIC 6000-6199)

**What drives operating income.** Net interest income (loan growth and interest rates), credit losses and cost control. Banks usually do not report an operating income line.

| Ratio | Why it matters here |
|---|---|
| `pretax_income_growth` | last year's direction of the target (banks report no operating income line) |
| `core_income_growth` | net interest income trend |
| `efficiency_ratio` | cost control |
| `provision_to_core_income` | credit costs |
| `equity_to_assets` | capital cushion |

**Avoid.** general ratios (gross margin, inventory, capex) do not apply.

**MD&A topics.** net interest margin outlook, rate sensitivity, loan growth, credit quality and reserve builds, expense guidance

**Caution.** Banks usually report no operating income line. The company card names the target: when it says pre-tax income, predict the direction of pre-tax income, not operating income.

### Insurance (property and casualty, life, health) (`insurance`, SIC 6300-6411)

**What drives operating income.** Premium growth, claims (loss ratio, catastrophes, medical costs) and investment income. Health insurers often do report operating income; most others do not.

| Ratio | Why it matters here |
|---|---|
| `pretax_income_growth` | last year's direction of the target when no operating income line is reported |
| `core_income_growth` | premiums earned trend |
| `efficiency_ratio` | expense control |
| `equity_to_assets` | capital cushion |
| `operating_margin` | if the company reports operating income (health insurers) |
| `revenue_growth` | if premiums are not tagged |

**Avoid.** inventory and capex ratios do not apply.

**MD&A topics.** premium rate increases, loss or medical cost ratio trends, catastrophe losses, reserve development, membership (health), utilization trends

**Caution.** Check the company card's target: health insurers usually report operating income, property and casualty and life insurers usually do not (then the target is pre-tax income).

### General (no specific playbook) (`general`, SIC fallback)

**What drives operating income.** Use the broad set and let the MD&A explain what drives the business.

| Ratio | Why it matters here |
|---|---|
| `revenue_growth` | top-line momentum |
| `operating_margin` | overall trend |
| `operating_income_growth` | last year's direction |
| `gross_margin` | pricing versus costs |
| `sga_to_revenue` | overhead |

**Avoid.** nothing specific

**MD&A topics.** management's outlook, demand, pricing, cost pressures, one-off charges

## Ratio definitions

| Ratio | Definition | Formula | XBRL tags | How to read it |
|---|---|---|---|---|
| `revenue_growth` | Change in revenue versus the prior fiscal year. | (Revenue[t] - Revenue[t-1]) / |Revenue[t-1]| | Revenues, RevenueFromContractWithCustomerExcludingAssessedTax, SalesRevenueNet | Top-line momentum. Operating income rarely grows for long when revenue shrinks, unless costs are cut. |
| `operating_income_growth` | Change in operating income versus the prior fiscal year. | (OperatingIncome[t] - OperatingIncome[t-1]) / |OperatingIncome[t-1]| | OperatingIncomeLoss | Last year's direction. Momentum is real but mean reversion after an unusual year is common. |
| `pretax_income_growth` | Change in pre-tax income from continuing operations versus the prior fiscal year. | (PretaxIncome[t] - PretaxIncome[t-1]) / |PretaxIncome[t-1]| | IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest, IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments | Last year's direction of the substitute target, for companies that report no operating income line (banks, insurers, some consumer and energy companies). |
| `deferred_revenue_growth` | Change in current deferred revenue (contract liabilities) versus the prior year end. | (DeferredRevenue[t] - DeferredRevenue[t-1]) / |DeferredRevenue[t-1]| | ContractWithCustomerLiabilityCurrent, DeferredRevenueCurrent | Cash billed but not yet recognized. For subscription businesses it leads next year's revenue. |
| `rpo_growth` | Change in remaining performance obligations (RPO): revenue under signed contracts not yet recognized. | (RPO[t] - RPO[t-1]) / |RPO[t-1]| | RevenueRemainingPerformanceObligation | Contracted future revenue. RPO is NOT the same as the backlog management quotes: it often covers only firm, non-cancellable contracts and can be a fraction of total backlog, so a few large multi-year contracts can double it. Read it as direction, check the size against the backlog in the MD&A. |
| `gross_margin` | Gross profit as a share of revenue. | GrossProfit / Revenue  (or (Revenue - CostOfRevenue) / Revenue) | GrossProfit; CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsSold | Pricing power and input costs. A falling gross margin flows straight into operating income. |
| `operating_margin` | Operating income as a share of revenue. | OperatingIncome / Revenue | OperatingIncomeLoss; revenue tags | Overall operating efficiency. Compare the trend across the two years, not the level across industries. |
| `pretax_margin` | Pre-tax income from continuing operations as a share of revenue. | PretaxIncome / Revenue | pre-tax income tags; revenue tags | Overall profitability for companies without an operating income line. Includes interest and other non-operating items, so read one-offs in the MD&A before trusting a big move. |
| `sga_to_revenue` | Selling, general and administrative expense as a share of revenue. | SG&A / Revenue | SellingGeneralAndAdministrativeExpense; or SellingAndMarketingExpense + GeneralAndAdministrativeExpense | Overhead discipline. Rising SG&A share with flat revenue squeezes operating income. |
| `rnd_to_revenue` | Research and development expense as a share of revenue. | R&D / Revenue | ResearchAndDevelopmentExpense, ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost, ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost | Investment intensity. A step up depresses this year's operating income; a pullback can lift it. |
| `cost_ratio` | Total costs and expenses as a share of revenue. | CostsAndExpenses / Revenue | CostsAndExpenses, OperatingExpenses | The mirror of operating margin when a company does not report gross profit. |
| `inventory_turnover` | Cost of revenue divided by year-end inventory. | CostOfRevenue / Inventory | CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsSold; InventoryNet | Falling turnover means inventory is piling up, which often leads to markdowns and lower margins. |
| `inventory_growth_minus_revenue_growth` | Inventory growth minus revenue growth, in percentage points. | InventoryGrowth - RevenueGrowth | InventoryNet; revenue tags | Positive and large: inventory building faster than sales, a classic warning sign for next year's margins. |
| `receivables_days` | Days of revenue sitting in accounts receivable at year end. | AccountsReceivable / Revenue * 365 | AccountsReceivableNetCurrent | Rising days can mean looser credit terms to hold up sales, or weaker customers. |
| `asset_turnover` | Revenue divided by year-end total assets. | Revenue / Assets | Assets; revenue tags | How hard the asset base works. Most useful in capital-heavy industries. |
| `capex_to_revenue` | Capital expenditure as a share of revenue. | PaymentsToAcquirePropertyPlantAndEquipment / Revenue | PaymentsToAcquirePropertyPlantAndEquipment | Heavy recent capex raises next year's depreciation, which weighs on operating income until it pays off. |
| `depreciation_to_revenue` | Depreciation, depletion and amortization as a share of revenue. | D&A / Revenue | DepreciationDepletionAndAmortization, DepreciationAndAmortization, Depreciation | The fixed cost of the asset base. High D&A means high operating leverage to volume. |
| `cash_conversion` | Operating cash flow divided by operating income. | NetCashProvidedByUsedInOperatingActivities / OperatingIncome | NetCashProvidedByUsedInOperatingActivities; OperatingIncomeLoss | Earnings quality. Well below 1 means profits are not turning into cash and may not be sustainable. |
| `liabilities_to_equity` | Total liabilities divided by shareholders' equity. | Liabilities / StockholdersEquity | Liabilities; StockholdersEquity | Leverage. Matters for resilience, less for next year's operating income direction. |
| `interest_coverage` | Operating income divided by interest expense. | OperatingIncome / InterestExpense | OperatingIncomeLoss; InterestExpense, InterestExpenseNonoperating | Below about 3x the company may cut spending to protect cash, which can help or hurt operating income. |
| `core_income_growth` | Growth in net interest income (banks) or net premiums earned (insurers). | (Core[t] - Core[t-1]) / |Core[t-1]| | InterestIncomeExpenseNet, InterestIncomeExpenseAfterProvisionForLoanLoss; PremiumsEarnedNet | The revenue engine of a financial firm, in place of revenue growth. |
| `efficiency_ratio` | Noninterest expense as a share of revenue. | NoninterestExpense / Revenue | NoninterestExpense; revenue tags | Lower is better for a bank. A rising ratio means costs grow faster than income. |
| `provision_to_core_income` | Credit loss provisions as a share of net interest income. | ProvisionForCreditLosses / NetInterestIncome | ProvisionForLoanLeaseAndOtherLosses, ProvisionForCreditLosses | Credit cost. Provisions swing bank earnings more than anything else in a downturn. |
| `equity_to_assets` | Shareholders' equity as a share of total assets. | StockholdersEquity / Assets | StockholdersEquity; Assets | Capital cushion. Thin capital can force a bank to shrink lending. |
