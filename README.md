## Workshop checkpoint
Group Assignment
Team 6

German Cifuentes
Javier Berain Garza
Nicolas Rios Cabo
Vicente Llinares Llata
 
0. LOGISTICS
   Attending the Oct 23 workshop? (yes / no): Yes
   Project board link (§5.7): https://github.com/users/Vicen-75/projects/1/views/1
   Streamlit app URL (must load; it does not yet have to do anything): https://earnings-oracle.streamlit.app/
 
 
1. THE PROJECT, AS IT STANDS TODAY
   Update these from your proposal — do not copy them across if they have changed.
   Who the user is: junior financial analyst building a stock pitch who wants a quick sense of the direction of a listed company's             earnings. (Unchanged from the proposal.)
   The task, in one sentence: The user gives a ticker, the tool reads the company's last two 10-Ks, and it predicts whether operating          income in the next fiscal year will increase or decrease versus the current one (or says "no data found").
   The user's input, and what comes back to the user: Input: a ticker. Back: the direction (increase / decrease) with a probability, up to     three cited passages from the filings, a summary table of financial ratios, a ratio-only baseline verdict next to it, and a disclaimer.     Today the deployed app only returns a placeholder message (see section 3).
   Every source the app reads (§3.2):
   - SEC EDGAR, public data from the US Securities and Exchange Commission, read with the required User-Agent header and a self-imposed        limit  of 8 requests/second (the SEC allows 10): company_tickers.json (ticker to CIK), the submissions API (filing index, SIC code), the    XBRL company concept API (OperatingIncomeLoss), and the 10-K primary documents (MD&A text).
  - Gemini API, free tier (gemini-3.1-flash-lite), for the model calls.
  - No data about real, identifiable people.
 
 
2. WHAT CHANGED SINCE THE PROPOSAL
   What you changed in what you build or how you build it, and why (write "none" if nothing):
   1. Tool calling is now the model's decision, not a fixed pipeline. The model gets a short company card (industry, fiscal year end, which       filings exist, whether the operating income tag exists) and chooses the ratio set and writes its own MD&A search queries. Why:              proposal feedback (see below). Design in docs/tool_calling.md, prototype in src/agent.py.
   2. Contamination test v2 (quarter probe added). Our first runs (Oct 19) showed the model answers "unknown" for the FY2025 full year but        remembers quarters of it, so its cutoff sits inside FY2025 and the proposal's idea of "pick 10-Ks after the cutoff" is not enough.          eval/contamination.py now asks about the full year, the quarters of the target year, and a control year, and treats any remembered          result after the prior year end as a leak.
   3. Metric sharpened. The headline number is now anonymized directional accuracy on 20 scored companies, compared against named accuracy,       the ratio-only baseline and "always increase". The four robustness inputs (invalid ticker, one 10-K, 20-F filer, MD&A not found)            moved out of the 20 and are reported pass/fail separately, so trivial "no data" answers do not inflate accuracy. See                        docs/success_metric.md.
   4. Engineering additions: EDGAR cache plus SEC rate limit, a usage cap (10 analyses per session) and a disclaimer in the app, versioned        prompts in src/prompts.py, and a crash-proof contamination run that saves after every company.
   5. Possible scope cut: banks and insurers have no OperatingIncomeLoss tag (JPM and PGR are flagged NO_OPERATING_INCOME_TAG). We keep           them only if the substitute tag is defined before the test set is fixed; otherwise we cut them and record it in the report.


   What the proposal feedback asked for, and what you did about it:
    1.	Make tool calling the model's decision, a fixed order is a pipeline:	Redesigned (docs/tool_calling.md) and prototyped                       (src/agent.py): four tools, the model picks the ratio set from the industry and writes its own MD&A queries, hard cap of 6 tool             calls. eval/tool_log.json shows CAT (industrial) getting compute_general_ratios and JPM (bank) getting                                      compute_financial_sector_ratios, with different MD&A queries. Caveat: the ratio and MD&A tool bodies are still stubs, so this shows         the model's choice, not real analysis yet.
    2.	MD&A parsing is a real risk: build against 2-3 filings, fail early with "MD&A not found" and fall back to ratio-only: Designed in:          search_mdna returns {"error": "MD&A not found"} and the system prompt tells the model to answer from what remains or say "no data           found". Not built yet: the real MD&A extractor (issue #10) and retrieval; today search_mdna returns canned passages.
    3.	Run a contamination test: Done and extended: eval/contamination.py v2 with full-year, quarter and control probes over the 24                candidates in eval/candidates.csv; results in eval/contamination_results.csv. Results on the 24 candidates: 10 usable (HD and PEP           OK; CAT, UNH, LMT, ADBE, MCD, TXN, WM and ROST OK_BUT_UNKNOWN_COMPANY, meaning the model does not even know the control year, so            there is nothing to leak), 5 contaminated (AAPL, MSFT, SBUX, UNP and CSCO: the model answers "unknown" for the full year but                remembers 2-3 quarters of FY2025, exactly the leak the feedback described), 7 with no OperatingIncomeLoss tag (JPM and PGR as               expected, plus KO, XOM, CVX, PFE and NKE, which need a substitute tag) and 2 with no usable target year (DE and ETN). We need at            least 10 more candidates, or a substitute tag that recovers some of the 7, to reach 20 scored companies.
    4.	Anonymize as a robustness check and compare accuracy with and without names: Part of the metric (named vs anonymized accuracy on the        same 20). The agent has an anonymize flag that is logged, but it is only a placeholder that redacts the name and ticker fields; the         real anonymizer (removing company, ticker and product names) is not built yet.
 
3. WHERE THE BUILD STANDS
   What a user can do on the deployed app today: Open the URL, type a ticker, click Analyze, and see the disclaimer, a counter of analyses     used (cap of 10 per session) and the message "Analysis for <TICKER> is under construction". The app is not connected to the agent yet.
   For each §5.1 capability you plan to use: where it will fire, and whether it is working / in progress / not started:

   1. Capability: Versioned prompts. Where it fires: src/prompts.py (TOOL_SYSTEM_V1), used by src/agent.py; PROMPT_V2 is the planned              before/after change.	Status: working (V1), V2 not started
   2. Capability: Tool calling.	Where it fires: src/agent.py run(): the model chooses ratio set and MD&A queries, every call logged to             eval/tool_log.jsonl.	Status: in progress: loop and company card are real; ratio and MD&A tools are stubs (src/tools_stub.py)
   3. Capability: Retrieval over the MD&A. Where it fires:	search_mdna tool (needs MD&A extractor #10 and retrieval. Status:	not started          (stub passages only)
   4. Capability: Structured output. Where it fires:	Pydantic response_schema in the contamination probes (eval/contamination.py); the            final prediction schema (direction, probability, three cited passages) is still free text in V1. Status:	working for probes, in             progress for the final answer
   A first sketch of your architecture diagram (§5.2) — a photo of a whiteboard, committed and linked, is fine: 

 
4. SUCCESS METRIC (§5.5)
   The one number that says whether your app is doing its job: Directional accuracy, anonymized: the share of the 20 scored test companies     for which the predicted direction of FY2025 operating income (increase or decrease vs FY2024) matches the direction reported in the         FY2025 10-K, with company name, ticker and product names removed from everything the model sees. The app is doing its job if this beats     both the ratio-only baseline and "always increase" on the same 20. With n = 20, one company is 5 points, so the report will give counts     and say that a 1-company difference is not evidence. Full definition: docs/success_metric.md.
   Where your test inputs will come from: FY2023 and FY2024 10-Ks from EDGAR (by accession number, listed in eval/test_set.csv) for            companies whose FY2025 10-K is already filed. Candidates are in eval/candidates.csv (24 large and mid-cap filers across industries); the    contamination test decides which of them make the final 20.
 
 
5. PROOF OF CONCEPT — TWO TEST INPUTS
   For each: the input · the result you expect, written before you run anything ·
   if your app can already run it, what it returned.
   Input A — an ordinary input your app should handle:  
   HD (Home Depot), a large-cap non-financial that passed the contamination test (verdict OK, 0 quarters remembered, the model knows the       control year).
   - Expected result (written before the run): The model calls get_company_card, then compute_general_ratios (not the financial-sector         set), then search_mdna with a query about demand or outlook, and returns a direction, a probability and a cited passage without             crashing. We did not use the known FY2025 result as our prediction.
   - What it returned: Analysis for HD is under construction.

   Input B — an input you expect it to get wrong:
   TSM (Taiwan Semiconductor Manufacturing, CIK 0001046179), a 20-F filer: EDGAR shows no 10-K filings, so list_10ks() should return an        empty list.
   - Expected result (written before the run): The correct answer is "no data found". We expect the model may still give a direction and a     probability, because the stub ratio tools ignore the company and return canned numbers. If it does, we count it as wrong, and it becomes    a fix for the real ratio tools and the system prompt.
   - What it returned: Analysis for TSM is under construction.

 
5. THE PLAN TO YOUR PRESENTATION
   What is left to build, and who owns each piece (it should match your board):
   What you will cut first if you fall behind:
   - Real ratio calculator, general and financial-sector (src/ratios.py): Vicente
   - MD&A extractor (#10) and retrieval over the last two 10-Ks, with the "MD&A not found" fallback: Nicolas
   - Final answer schema and parser (direction, probability, three cited passages): German
   - Anonymizer (src/anonymize.py): German/Nicolas
   - Ratio-only baseline (src/baseline.py) and the "always increase" rule: Javier
   - Final 20-company eval/test_set.csv (finish contamination run, substitute tag for banks/insurers): Vicente    
   - Connect the agent to the Streamlit app (replace the placeholder): Javier
   - Backtest runs (named vs anonymized), PROMPT_V2 before/after, report and slides: All
 
6. WHAT YOU NEED FROM US
   The one thing blocking you, or the question you want answered at your table: Our model's cutoff falls inside FY2025: 5 of our 24            candidates are contaminated and only 10 are usable so far. How many more companies should we add or drop, and how much should we lean on    anonymization, before the 20-company set stops being a fair test? Is anonymized accuracy plus the named-vs-anonymized gap enough            evidence that the model is reading and not remembering?


