# IS883 Project Proposal — Fall 2026

**Team name:** Earnings Oracle
**Members:** Javier Berain Garza, German Cifuentes, Vicente Llinares Llata, Nicolas Rios Cabo

Submitted Mon Oct 5, 2026. This is the proposal as submitted; the workshop checkpoint in `README.md` records what changed afterwards.

## 0. Team infrastructure

- **GitHub repository:** https://github.com/Vicen-75/Earnings-Oracle
- **Project board (GitHub Projects, §5.7):** https://github.com/users/Vicen-75/projects/1/views/1
- **Streamlit app URL:** https://earnings-oracle.streamlit.app/

## 1. The user and the task

**Who the user is:** A junior financial analyst building a stock pitch that wants to have a quick sense of the directionality of a publicly listed company's earnings.

**The task, in one sentence:** The user sends a ticker, the tool analyzes the company's 10-Ks, and makes a judgment call: will next year's operating income reported in the 10-K increase or decrease versus the current year? No cop-outs: either increase, decrease, or no data found.

**What they do today instead, and what your app adds:** Today, an analyst must go to EDGAR or the company's investor relations page, download filings that can span 100+ pages, read them, and make a judgment call. This process also requires some expertise in the company's industry. Our app speeds up the process and provides a clear rationale for the prediction.

**Why this needs a language model rather than a query, a filter or a rule (§5.3):** Earnings forecasting relies on quantitative financial metrics from the income statement, but qualitative data from the MD&A section improves accuracy. Making an earnings prediction is a judgment call that requires contextual information, a task LLMs perform well, as shown by Kim et al. While 10-Ks contain legally required information, their formats vary, making rule-based systems unreliable. Financial ratios can be queried directly, but MD&A is unstructured text that requires interpretation of context, tone, and sentiment.

## 2. What the app does

**The user's input:** Ticker symbol.

**What comes back to the user:** Summary table of financial ratios, and direction and probability of earnings (earnings will increase/decrease in the next 10-K) with three cited passages, and the ratio-only baseline verdict next to it. A disclaimer, since this app advises on money.

## 3. Sources and data

**Every source the app reads, and why you are permitted to use it (§3.2):** Three EDGAR APIs: submissions for the filing index, full-text from the archive, and XBRL for financial data. EDGAR is a public database made available by the US Securities and Exchange Commission. They have a fair access rule that we intend to follow. We will use the Gemini free tier model.

**Does any of it concern real, identifiable people? If yes, explain:** No. We will only use publicly available information published in official government portals.

## 4. How you will know it works

**The one number you intend to report (you fix this in your workshop checkpoint, §4.3):** Directional accuracy: the percentage of test companies for which the predicted direction of FY2025 operating income matches the actual result, compared against the ratio-only baseline and a naive "always increase" rule.

**Where your 20 test inputs will come from:** Historical backtest: We will feed the app 20 companies using their FY2023 and FY2024 10-Ks, and we will try to predict their FY2025 outcomes. We will then compare each prediction with the company's actual FY2025 performance, which is already public, to measure the app's accuracy. These 20 companies should have their FY2025 10-Ks published after the model's training cutoff date. Will include invalid tickers, a recently listed firm with only one 10-K, a foreign filer with a 20-F, and a bank.

## 5. Scope

**What is in the version you demo on Nov 9 or Nov 16:** The user enters a ticker, and the app fetches the company's last two 10-Ks from EDGAR, retrieves the MD&A and financial statements, and computes key financial ratios. It returns the probability and direction of next year's operating income change, along with the three most influential filing passages. A ratio-only baseline is shown alongside the model's prediction to demonstrate what the text adds beyond the numbers.

**What you will cut first if you are behind on Oct 23:** First, we will narrow the universe to US non-financial companies, excluding banks and insurers, whose operating income is defined differently. Second, we will cut the evidence supporting the prediction from three passages to one. Finally we would drop retrieval of financial sections and read the MD&A section only.

## 6. Risks

We find 4 main risks. 1) We might not be able to figure out how to parse the MD&A section of the 10-Ks; 2) We might not be able to afford processing a full 10-K, which surpasses the free-tier context, retrieval is critical; 3) The metric is boolean, a coin flip could be as good as our app; and 4) Look-ahead bias could taint our results.

## 7. What you want from us

Is using the training cutoff date feasible and sufficient? We ask because we might struggle to identify the training cutoff date or, if we do, it may not be sufficient, and we might need to anonymize the firms in the testing set.

## Sources

1. https://www.investopedia.com/articles/stocks/06/earningsforecasts.asp
2. https://doi.org/10.1177/0148558X17722919
3. https://arxiv.org/html/2407.17866v1#abstract1

---

## Instructor feedback (received Oct 19, 2026)

Very strong proposal. Two baselines, a backtest with public answers, and naming look-ahead bias as a risk makes it a well-thought project. A few things to think about before the Oct 22 checkpoint:

- **Make tool calling the model's decision.** If every ticker always triggers the EDGAR fetch and the ratio calculator in a fixed order, that's a pipeline, not tool calling. For example, the model could decide which ratios to compute based on the industry.
- **The MD&A parsing risk is real.** Build against two or three filings first and fail early (show "MD&A not found" with the ratio-only call) rather than passing the wrong section to the model.

On your question: the training cutoff on its own probably isn't enough. If the model's cutoff falls during FY2025, it has likely seen Q1-Q3 2025 earnings reports and news coverage, which give away the full-year direction. The cutoff has to come before the period you're predicting, not just before the 10-K was filed. We'd suggest to:

- **Run a contamination test.** Ask the model directly about each test company's FY2025 operating income. If it knows, drop the company or anonymize it.
- **Anonymize as a robustness check.** Remove the company name, ticker and product names, then compare accuracy with and without. If accuracy drops sharply once the names are gone, the model was remembering, not reading.
