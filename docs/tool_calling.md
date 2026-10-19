# Tool calling design — the model decides

Owner: Javier · Issue #11 · Drafted Oct 19, 2026

## Why this exists

Proposal feedback: "If every ticker always triggers the EDGAR fetch and the ratio calculator in a fixed order, that's a pipeline, not tool calling. For example, the model could decide which ratios to compute based on the industry." §5.1 counts tool calling only when the model genuinely chooses to invoke a function and the result changes the answer, and Q&A will ask us to show where it fires.

## The decision we hand to the model

Code does the parts that are not decisions: the ticker is resolved to a CIK, the filing index is pulled, and a short **company card** is built (name, SIC code and description, fiscal year end, which 10-Ks exist, whether the `OperatingIncomeLoss` tag exists). That card goes to the model with a set of tools, and the model decides:

1. **Which ratio set to compute.** A general industrial set (operating margin, revenue growth, opex ratio, asset turnover, leverage) or a financial-sector set (net interest income or premiums, efficiency ratio, provision ratio, equity to assets). A bank with no `OperatingIncomeLoss` tag should push the model to the financial set; a software company should not. The model may also call both if the company is a conglomerate with a finance arm.
2. **Whether it needs the MD&A at all, and what to look for.** The model calls `search_mdna(query)` with its own query (for example "management outlook on operating margin" for an industrial, "credit loss provisions and net interest margin outlook" for a bank). It can call it more than once with different queries, or skip it when the ratios are decisive. This is where retrieval (card 13) plugs in, and it makes the retrieval query a model decision too.
3. **When to stop and answer.** After the tool results come back, the model produces the final structured prediction (card 14).

What stays fixed in code: the two-10-K rule, the SEC fair-access headers, the anonymization pass (applied to every tool result before it goes back to the model when the anonymized flag is on), and the request cap.

## Tools

Four function declarations, all thin wrappers over code that already exists or is on the board.

| Tool | Args | Returns | Backed by |
| --- | --- | --- | --- |
| `get_company_card` | `ticker` | name, CIK, SIC code + description, fiscal year end, list of 10-Ks (fiscal_year_end, filed, url), `has_operating_income_tag` | `src/edgar.py` (card 10 adds the SIC lookup from the submissions JSON) |
| `compute_general_ratios` | `cik` | dict of ratios for the last two fiscal years, with `"not reported"` per missing tag | `src/ratios.py` (card 11) |
| `compute_financial_sector_ratios` | `cik` | same shape, financial-sector tags | `src/ratios.py` (card 11) |
| `search_mdna` | `cik`, `query`, `k` (default 4) | list of passages `{text, fiscal_year, position}` from the FY2023 and FY2024 MD&A, or `{"error": "MD&A not found"}` | `src/mdna.py` (card 5) + `src/retrieval.py` (card 13) |

`get_company_card` is cheap and the system instruction tells the model to call it first; the real choice is among the other three.

## System instruction (goes into `src/prompts.py` as `TOOL_SYSTEM_V1`)

> You are an equity research assistant. Your job is to predict whether the company's operating income in its next fiscal year will increase or decrease versus the current year, using only the tools provided. Start by calling `get_company_card`. Then decide what evidence you need: choose the ratio set that fits the company's industry (banks and insurers report net interest income or premiums rather than operating income, so use the financial-sector set for them; use the general set for everyone else; use both only if the business is a mix). Decide whether the MD&A would change your view and, if so, search it with specific questions about outlook, demand, margins, costs or risks; you may search more than once. Do not call a tool whose result you would not use. When you have enough evidence, answer in the required JSON schema with direction, probability, three cited passages and a short rationale. If a tool reports that data is missing, say so and base your answer on what remains; if nothing usable remains, answer "no data found".

## The loop (`src/agent.py`)

Pseudocode against the `google-genai` SDK already used in `src/llm.py`:

```python
from google.genai import types
from src.llm import client, MODEL
from src import edgar, ratios, mdna_search          # the four tool implementations

TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="get_company_card",
        description="Company identity, industry (SIC) and which 10-K filings exist.",
        parameters={"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]},
    ),
    types.FunctionDeclaration(
        name="compute_general_ratios",
        description="Operating margin, revenue growth, opex ratio, asset turnover and leverage for the last two fiscal years. For non-financial companies.",
        parameters={"type": "object", "properties": {"cik": {"type": "string"}}, "required": ["cik"]},
    ),
    types.FunctionDeclaration(
        name="compute_financial_sector_ratios",
        description="Net interest income or premiums, efficiency ratio, provision ratio and equity to assets for the last two fiscal years. For banks and insurers.",
        parameters={"type": "object", "properties": {"cik": {"type": "string"}}, "required": ["cik"]},
    ),
    types.FunctionDeclaration(
        name="search_mdna",
        description="Retrieve the most relevant MD&A passages from the last two 10-Ks for a question you write.",
        parameters={"type": "object",
                    "properties": {"cik": {"type": "string"}, "query": {"type": "string"}, "k": {"type": "integer"}},
                    "required": ["cik", "query"]},
    ),
])

IMPL = {"get_company_card": edgar.company_card,
        "compute_general_ratios": ratios.general,
        "compute_financial_sector_ratios": ratios.financial_sector,
        "search_mdna": mdna_search.search}

MAX_TOOL_CALLS = 6      # hard stop so one ticker cannot burn the free tier


def run(ticker, anonymize=False, log=None):
    config = types.GenerateContentConfig(system_instruction=TOOL_SYSTEM_V1, tools=[TOOLS], temperature=0)
    contents = [types.Content(role="user", parts=[types.Part(text=f"Ticker: {ticker}")])]
    calls = 0
    while True:
        response = client.models.generate_content(model=MODEL, contents=contents, config=config)
        if not response.function_calls:
            return response.text, log                     # final answer; card 14 parses it
        contents.append(response.candidates[0].content)   # keep the model's tool request in history
        for call in response.function_calls:
            calls += 1
            if calls > MAX_TOOL_CALLS:
                return '{"direction": "no data found", "reason": "tool budget exceeded"}', log
            result = IMPL[call.name](**call.args)
            if anonymize:
                result = anonymize_result(result)         # card 15
            log.append({"tool": call.name, "args": call.args, "ok": "error" not in result})
            contents.append(types.Content(role="user", parts=[
                types.Part.from_function_response(name=call.name, response={"result": result})]))
```

The `log` is the evidence. It is written per ticker to `eval/tool_log.jsonl` and shown in an expander in the Streamlit UI, so in Q&A we can open two tickers and show that the model called `compute_financial_sector_ratios` for the bank and `compute_general_ratios` for the industrial, with different `search_mdna` queries.

## How we show it is a decision, not a pipeline

Two tickers run side by side in the checkpoint and later in the report:

| | Industrial (e.g. CAT) | Bank (e.g. JPM) |
| --- | --- | --- |
| Expected ratio tool | general | financial-sector |
| Expected MD&A queries | demand, backlog, margin outlook | provisions, net interest margin, deposit costs |
| Expected calls | 3 to 4 | 3 to 4 |

If the model picks the same tools in the same order for both, the design has failed and we tighten the system instruction (that becomes a before-and-after candidate). A third test, a ticker where `search_mdna` returns "MD&A not found", checks that the model falls back to a ratio-only answer and says so.

## Risks and the cut

- **Flash Lite may call tools in a fixed habit regardless of the card.** Mitigation: the card states explicitly whether the operating income tag exists and the SIC description; if that is not enough, add one few-shot example per branch to the system instruction.
- **Tool loops.** `MAX_TOOL_CALLS = 6` and `temperature=0`.
- **Free-tier cost.** Each tool round trip is a model call; a full run is 4 to 5 calls. Develop against two tickers, cache every EDGAR response (card 10).
- **If behind on Oct 23:** keep the model's choice between the two ratio sets (the minimum that satisfies §5.1) and make the MD&A search a single fixed call. Record the cut in slot 2.

## What goes in the checkpoint

Slot 2: "Tool calling redesigned so the model chooses the ratio set from the company's industry and writes its own MD&A search queries; design in `docs/tool_calling.md`, prototype in `src/agent.py`." Slot 3: tool calling fires in `src/agent.py` `run()`; status in progress (or working, if the two-ticker log is committed).
