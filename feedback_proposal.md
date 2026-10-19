This is the Feedback we recieved from the instructor:

Very strong proposal. Two baselines, a backtest with public answers, and naming look-ahead bias as a risk makes it a well-tought project. A few things to think about before the Oct 22 checkpoint:
•	Make tool calling the model’s decision. If every ticker always triggers the EDGAR fetch and the ratio calculator in a fixed order, that’s a pipeline, not tool calling. For example, the model could decide which ratios to compute based on the industry.
•	The MD&A parsing risk is real. Build against two or three filings first and fail early (show “MD&A not found” with the ratio-only call) rather than passing the wrong section to the model.
On your question: the training cutoff on its own probably isn’t enough. If the model’s cutoff falls during FY2025, it has likely seen Q1-Q3 2025 earnings reports and news coverage, which give away the full-year direction. The cutoff has to come before the period you’re predicting, not just before the 10-K was filed. We'd suggest to: 
•	Run a contamination test. Ask the model directly about each test company’s FY2025 operating income. If it knows, drop the company or anonymize it.
•	Anonymize as a robustness check. Remove the company name, ticker and product names, then compare accuracy with and without. If accuracy drops sharply once the names are gone, the model was remembering, not reading.

