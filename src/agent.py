# --- Javier: tool-calling agent loop (code written with help from Claude) ---
# Design: docs/tool_calling.md. The model, not the code, decides which ratio set to compute and what to search
# in the MD&A. The code resolves the ticker, exposes the tools, executes whatever the model asks for, and logs it.
#
# Run from the repository root:
#   python -m src.agent CAT            # one ticker, prints the tool log and the answer
#   python -m src.agent CAT JPM        # several
# Set EARNINGS_ORACLE_STUBS=0 once the real ratio / MD&A tools exist (see IMPL below).
import json
import os
import sys
import time
from pathlib import Path

from google.genai import types

from src import edgar
from src.llm import client, MODEL
from src.prompts import TOOL_SYSTEM_V1

USE_STUBS = os.environ.get("EARNINGS_ORACLE_STUBS", "1") != "0"
if USE_STUBS:
    from src import tools_stub as ratio_impl
    from src import tools_stub as mdna_impl
else:                                                   # swap in the real modules as they land
    from src import ratios as ratio_impl               # noqa: F401  (issue: ratio calculator)
    from src import retrieval as mdna_impl             # noqa: F401  (issue: retrieval over MD&A)

MAX_TOOL_CALLS = 6          # hard stop so one ticker cannot burn the free tier
LOG_PATH = Path("eval/tool_log.jsonl")

# --- 1. What the model is allowed to call -------------------------------------------------------------------
S = types.Schema
TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="get_company_card",
        description="Company identity, industry (SIC code and description), fiscal year end, which 10-K filings exist, "
                    "and whether it reports an operating income line. Call this first.",
        parameters=S(type="OBJECT", properties={"ticker": S(type="STRING")}, required=["ticker"]),
    ),
    types.FunctionDeclaration(
        name="compute_general_ratios",
        description="Operating margin, revenue growth, opex ratio, asset turnover and leverage for the last two fiscal years. "
                    "For non-financial companies.",
        parameters=S(type="OBJECT", properties={"cik": S(type="STRING")}, required=["cik"]),
    ),
    types.FunctionDeclaration(
        name="compute_financial_sector_ratios",
        description="Net interest income or premium growth, efficiency ratio, provision ratio, net interest margin and "
                    "equity to assets for the last two fiscal years. For banks and insurers.",
        parameters=S(type="OBJECT", properties={"cik": S(type="STRING")}, required=["cik"]),
    ),
    types.FunctionDeclaration(
        name="search_mdna",
        description="Retrieve the most relevant Management's Discussion and Analysis passages from the last two 10-Ks "
                    "for a question you write, e.g. 'management outlook on demand and margins next year'.",
        parameters=S(type="OBJECT",
                     properties={"cik": S(type="STRING"), "query": S(type="STRING"), "k": S(type="INTEGER")},
                     required=["cik", "query"]),
    ),
])

IMPL = {
    "get_company_card": edgar.company_card,
    "compute_general_ratios": ratio_impl.compute_general_ratios,
    "compute_financial_sector_ratios": ratio_impl.compute_financial_sector_ratios,
    "search_mdna": mdna_impl.search_mdna,
}


# --- 2. The loop -------------------------------------------------------------------------------------------
def _generate(contents, config):
    """One model call with the same retry policy as src/llm.ask_gemini."""
    for attempt in range(4):
        try:
            return client.models.generate_content(model=MODEL, contents=contents, config=config)
        except Exception as error:
            if "429" in str(error) or "503" in str(error) or "RESOURCE_EXHAUSTED" in str(error) or "UNAVAILABLE" in str(error):
                print("   (rate limit or overload, waiting 15 seconds...)")
                time.sleep(15)
                continue
            raise
    raise RuntimeError("gave up after repeated retries")


def run(ticker, anonymize=False, system_instruction=TOOL_SYSTEM_V1, verbose=True):
    """Let the model investigate one ticker with the tools. Returns (answer_text, log).
    log is a list of {"tool", "args", "ok"} in the order the model called them: that list is the evidence
    that tool calling is the model's decision (compare the log for an industrial vs a bank)."""
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[TOOLS],
        temperature=0,
        thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
    )
    contents = [types.Content(role="user", parts=[types.Part(text=f"Ticker: {ticker}")])]
    log, calls, usage = [], 0, {"prompt_tokens": 0, "output_tokens": 0, "model_calls": 0}

    while True:
        response = _generate(contents, config)
        usage["model_calls"] += 1
        if response.usage_metadata:
            usage["prompt_tokens"] += response.usage_metadata.prompt_token_count or 0
            usage["output_tokens"] += response.usage_metadata.candidates_token_count or 0

        if not response.function_calls:                               # final answer
            answer = response.text or "[the model returned no text]"
            _write_log(ticker, log, answer, usage, anonymize)
            if verbose:
                print(f"\n=== {ticker}: {len(log)} tool calls, {usage['model_calls']} model calls ===")
                for entry in log:
                    print(f"   {entry['tool']}({entry['args']}) -> {'ok' if entry['ok'] else 'error'}")
                print(answer)
            return answer, log

        contents.append(response.candidates[0].content)               # keep the model's tool request (and thought signatures)
        response_parts = []
        for call in response.function_calls:
            calls += 1
            if calls > MAX_TOOL_CALLS:
                answer = "no data found (tool budget exceeded)"
                _write_log(ticker, log, answer, usage, anonymize)
                return answer, log
            args = dict(call.args or {})
            try:
                result = IMPL[call.name](**args)
            except Exception as error:                                # a crashing tool must not crash the run
                result = {"error": f"{type(error).__name__}: {error}"}
            if anonymize:
                result = _anonymize(result)                           # placeholder until src/anonymize.py exists
            log.append({"tool": call.name, "args": args, "ok": not (isinstance(result, dict) and "error" in result)})
            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))
        contents.append(types.Content(role="user", parts=response_parts))


def _anonymize(result):
    """Placeholder: the real one (issue: anonymization) strips company name, ticker and product names."""
    if isinstance(result, dict):
        return {k: ("[redacted]" if k in ("name", "ticker") else v) for k, v in result.items()}
    return result


def _write_log(ticker, log, answer, usage, anonymize):
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"ticker": ticker, "anonymized": anonymize, "stubs": USE_STUBS, "tools": log,
                            "usage": usage, "answer": answer, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")


if __name__ == "__main__":
    for t in sys.argv[1:] or ["CAT", "JPM"]:
        run(t)
