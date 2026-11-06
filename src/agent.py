# --- Javier: tool-calling agent loop (code written with help from Claude) ---
# Design: docs/tool_calling.md and docs/ratio_directory.md. The model, not the code, decides which industry playbook to
# read, which ratios to compute and whether to read the MD&A. The code resolves the ticker, exposes the tools, executes whatever the model asks for, and logs it.
#
# Run from the repository root:
#   python -m src.agent CAT            # one ticker, prints the tool log and the answer
#   python -m src.agent CAT JPM        # several
# Tools whose real implementation does not exist yet answer 'under construction' (see IMPL below); nothing is simulated.
import json
import sys
import time
from pathlib import Path

from google.genai import types

from src import edgar
from src.llm import MODEL
from src.key_pool import pool                       # several API keys, one per analysis (Nov 6)
from src.prompts import PROMPTS
from src import ratio_directory

from src import mdna as mdna_impl                      # real MD&A extractor (Nicolas)
from src.locate_mdna import locate_mdna                # fallback: a small agent finds the MD&A via the contents
try:
    from src import ratios as ratio_impl               # noqa: F401  (issue: ratio calculator, Vicente)
except ImportError:
    ratio_impl = None
RATIOS_AVAILABLE = ratio_impl is not None


def _under_construction(tool_name):
    """Stand-in for a tool that is not built yet. It never invents data: it tells the model the tool is unavailable
    so the answer rests on what remains (or becomes "no data found")."""
    def tool(**kwargs):
        return {"error": f"{tool_name} is under construction: no data available from this tool yet"}
    return tool


MAX_TOOL_CALLS = 9          # hard stop so one ticker cannot burn the free tier (V5 leaves room to go back and check)
DEFAULT_PROMPT = "V5"
THINKING_LEVEL = "LOW"      # Nov 5: was MINIMAL; LOW lets the model plan its investigation instead of following a script
LOG_PATH = Path("eval/tool_log.jsonl")          # command-line runs (committed: evidence for the report)
APP_LOG_PATH = Path("eval/app_runs.jsonl")      # app runs (git-ignored: local record so a run can be reviewed later)

# --- 1. What the model is allowed to call -------------------------------------------------------------------
# ReAct: every tool takes a required "reason" argument, the model's thought before it acts ("the card says SIC 7372,
# software, so I want the software playbook"). The loop removes it before running the tool and logs it, so the log
# reads thought -> action -> observation, step by step.
S = types.Schema
REASON = S(type="STRING", description="One sentence: why you are calling this tool now and what you expect to learn.")


def _declare(name, description, properties, required):
    return types.FunctionDeclaration(
        name=name, description=description,
        parameters=S(type="OBJECT", properties={"reason": REASON, **properties}, required=["reason", *required]),
    )


TOOLS = types.Tool(function_declarations=[
    _declare("get_company_card",
             "Company identity, industry (SIC code and description), fiscal year end, which 10-K filings exist, "
             "the target metric (operating income or pre-tax income), and the CIK the other tools need.",
             {"ticker": S(type="STRING")}, ["ticker"]),
    _declare("get_industry_playbook",
             "Retrieve the ratio directory entry for an industry: what drives operating income there, which ratios to "
             "compute and why (with definitions), which to avoid, and what to look for in the MD&A. Pass the SIC code "
             "from the company card, or a group name if the SIC code does not fit the business (a conglomerate, or a "
             "second segment). Groups: " + "; ".join(f"{name} = {g['label']}"
                                                    for name, g in ratio_directory.INDUSTRY_GROUPS.items()) + ".",
             {"sic_code": S(type="INTEGER"),
              # Nov 5: only existing group names (ARRY asked for an invented "Renewable Energy Equipment")
              "group": S(type="STRING", enum=list(ratio_directory.INDUSTRY_GROUPS))}, []),
    _declare("compute_ratios",
             "Compute the ratios you choose (up to 10, by name from the ratio directory) for the company's two latest "
             "fiscal years, from its XBRL data on EDGAR. Values are numbers or 'not reported'.",
             {"cik": S(type="STRING"),
              # Nov 5: only names from the directory are allowed (ADBE invented "Research and Development Expense Ratio")
              "ratios": S(type="ARRAY", items=S(type="STRING", enum=list(ratio_directory.RATIOS)))},
             ["cik", "ratios"]),
    _declare("get_mdna",
             "The full text of Management's Discussion and Analysis (Item 7) from the last two 10-Ks. "
             "Read it for the topics the playbook names: outlook, demand, pricing, margins, costs and risks. "
             "Returns an error if the section cannot be found.",
             {"cik": S(type="STRING")}, ["cik"]),
    _declare("locate_mdna",
             "Fallback when get_mdna returns 'MD&A not found' or lists missing_filings: a slower search that finds the "
             "MD&A through the filing's table of contents (for companies whose Item 7 only points elsewhere). "
             "Returns the same sections as get_mdna, or an error if it also fails.",
             {"cik": S(type="STRING")}, ["cik"]),
])

IMPL = {
    "get_company_card": edgar.company_card,
    "get_industry_playbook": ratio_directory.get_industry_playbook,
    "compute_ratios": ratio_impl.compute_ratios if RATIOS_AVAILABLE else _under_construction("compute_ratios"),
    "get_mdna": mdna_impl.get_mdna,
    "locate_mdna": locate_mdna,
}


# --- 2. The loop -------------------------------------------------------------------------------------------
def _generate(contents, config, on_event=None):
    """One model call. src/key_pool.py picks the key, moves to another key on a rate limit, and waits only when
    every key is busy (on_event gets {"type": "wait"} so the page can say so)."""
    return pool.generate(MODEL, contents, config, on_event)


def observe(tool, result):
    """One line saying what a tool returned: the 'observation' in the ReAct trace (thought, action, observation).
    Built from the result itself, so it is a fact about the data, not the model's reading of it."""
    if not isinstance(result, dict):
        return "unexpected result"
    if "error" in result:
        return f"Error: {result['error']}"
    if tool == "get_company_card":
        filings = result.get("ten_k_filings") or []
        latest = f", latest fiscal year ending {filings[0]['fiscal_year_end']}" if filings else ""
        return (f"{result.get('name')}: SIC {result.get('sic_code')} ({result.get('sic_description')}); "
                f"{len(filings)} 10-K filing(s){latest}; target: {result.get('target')}")
    if tool == "get_industry_playbook":
        names = ", ".join(r["ratio"] for r in result.get("recommended_ratios", []))
        caution = f" Caution: {result['caution']}" if result.get("caution") else ""
        return f"{result.get('label')} playbook (matched from {result.get('matched_from')}). Recommends: {names}.{caution}"
    if tool == "compute_ratios":
        values = result.get("values", {})
        missing = [n for n, by_year in values.items() if all(not isinstance(v, (int, float)) for v in by_year.values())]
        years = " and ".join(result.get("fiscal_years", []))
        text = f"{len(values)} ratio(s) computed for fiscal years ending {years}"
        if missing:
            text += f"; not reported: {', '.join(missing)}"
        if result.get("check_before_relying"):
            text += f"; flagged: {result['check_before_relying'].split(': ', 1)[-1]}"
        if result.get("unknown_ratios"):
            text += f"; unknown names: {', '.join(result['unknown_ratios'])}"
        return text
    if tool == "get_mdna":
        parts = [f"FY ending {f['fiscal_year_end']} ({f['chars']:,} characters)" for f in result.get("filings", [])]
        text = f"MD&A found in {len(parts)} filing(s): " + ", ".join(parts)
        if result.get("missing_filings"):
            text += f"; not found for FY ending {', '.join(result['missing_filings'])}"
        return text
    if tool == "locate_mdna":
        parts = [f"FY ending {f['fiscal_year_end']} ({f['chars']:,} characters, {f['how_found']}"
                 f"{', truncated' if f['truncated'] else ''})" for f in result.get("filings", [])]
        checks = len(result.get("locator_steps", []))
        return f"MD&A in {len(parts)} filing(s) after {checks} locator step(s): " + "; ".join(parts)
    return "ok"


def _keep_for_display(tool, result):
    """What the app shows from each tool result. The MD&A text itself is not kept (it can be 250,000 characters)."""
    if not isinstance(result, dict) or "error" in result:
        return result
    if tool in ("get_mdna", "locate_mdna"):
        shown = {"filings": [{k: f[k] for k in ("fiscal_year_end", "url", "chars", "truncated", "how_found") if k in f}
                             for f in result["filings"]]}
        if result.get("missing_filings"):
            shown["missing_filings"] = result["missing_filings"]
        return shown
    return result


SELF_CHECK = """Before you finalize, run the check: does the MD&A attribute the results or the outlook to something a \
ratio could confirm or contradict (pricing or mix: gross_margin; cost discipline: sga_to_revenue or cost_ratio; \
volume: revenue_growth; inventory: inventory_turnover; investment: capex_to_revenue or rnd_to_revenue; credit: \
provision_to_core_income)? If such a ratio is not among the ones you computed, call compute_ratios now, then give your \
final answer, changed if the new evidence changes it. If everything relevant is already computed, say so. Either way, \
use the same answer format and end it with one line "Self-check: ..." after the Rationale."""


def _draft_summary(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()][:2]
    return "Draft answer: " + " | ".join(lines)[:200] + ". Asked to run the self-check before finalizing."


def _tools_for_run(skip_newest):
    """The tool implementations for one run. skip_newest=1 is backtest mode: every tool hides the newest 10-K, so the
    model predicts the latest reported year from the two before it. None keeps each module's default (live mode).
    Nov 5: passed per run so the app's Tests tab never changes what the Analyze tab sees."""
    if skip_newest is None:
        return IMPL
    hide = {"skip_newest": skip_newest}
    return {**IMPL,
            "get_company_card": lambda **a: edgar.company_card(**a, **hide),
            "compute_ratios": lambda **a: ratio_impl.compute_ratios(**a, **hide),
            "get_mdna": lambda **a: mdna_impl.get_mdna(**a, **hide),
            "locate_mdna": lambda **a: locate_mdna(**a, **hide)}


def investigate(ticker, anonymize=False, prompt=DEFAULT_PROMPT, on_event=None, write_log=True, log_path=None,
                skip_newest=None):
    """Run one analysis on one API key from the pool (the locator agent inside it uses the same key)."""
    with pool.run():
        return _investigate(ticker, anonymize, prompt, on_event, write_log, log_path, skip_newest)


def _investigate(ticker, anonymize=False, prompt=DEFAULT_PROMPT, on_event=None, write_log=True, log_path=None,
                 skip_newest=None):
    """Let the model investigate one ticker with the tools.
    Returns {"answer", "steps", "results", "usage"}:
      steps    [{"reason", "tool", "args", "ok"}] in the order the model called them (the ReAct trace; the evidence
               that tool calling is the model's decision)
      results  {tool name: what that tool returned, the last call of each}, so the app can show the real numbers
               instead of the model's retelling of them
    on_event(event) is called after every tool call ({"type": "step", ...}) and on rate-limit waits, so the app can
    show progress live. write_log=False keeps app runs out of eval/tool_log.jsonl."""
    config = types.GenerateContentConfig(
        system_instruction=PROMPTS[prompt],
        tools=[TOOLS],
        temperature=0,
        thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
    )
    contents = [types.Content(role="user", parts=[types.Part(text=f"Ticker: {ticker}")])]
    log, results, calls, draft = [], {}, 0, None
    tools = _tools_for_run(skip_newest)
    usage = {"prompt_tokens": 0, "output_tokens": 0, "model_calls": 0}

    def finish(answer):
        usage["billed"] = pool.usage()            # every call of the run, thinking tokens included (issue #55)
        if write_log:
            _write_log(ticker, log, answer, usage, anonymize, prompt, log_path or LOG_PATH, skip_newest)
        return {"answer": answer, "steps": log, "results": results, "usage": usage, "prompt": prompt}

    while True:
        response = _generate(contents, config, on_event)
        usage["model_calls"] += 1
        if response.usage_metadata:
            usage["prompt_tokens"] += response.usage_metadata.prompt_token_count or 0
            usage["output_tokens"] += response.usage_metadata.candidates_token_count or 0

        if not response.function_calls:
            text = response.text or "[the model returned no text]"
            if draft is not None or "no data found" in text.lower()[:300]:
                return finish(text)                                   # final answer (after the self-check)
            # --- Self-check (Nov 5): the first answer is a draft. The code asks once whether the MD&A makes a claim a
            # ratio could test; the model decides whether to compute one or to confirm. Prompt wording alone was
            # ignored in every test run; this turn guarantees the moment to reflect, the choice stays the model's.
            draft = text
            entry = {"model_call": usage["model_calls"], "reason": "", "tool": "draft_answer", "args": {}, "ok": True,
                     "observation": _draft_summary(text)}
            log.append(entry)
            if on_event:
                on_event({"type": "step", **entry})
            contents.append(response.candidates[0].content)
            contents.append(types.Content(role="user", parts=[types.Part(text=SELF_CHECK)]))
            continue

        contents.append(response.candidates[0].content)               # keep the model's tool request (and thought signatures)
        response_parts = []
        for call in response.function_calls:
            calls += 1
            if calls > MAX_TOOL_CALLS:                                # out of budget: keep the draft if there is one
                return finish(draft or "no data found (tool budget exceeded)")
            args = dict(call.args or {})
            reason = args.pop("reason", "")
            try:
                result = tools[call.name](**args)
            except Exception as error:                                # a crashing tool must not crash the run
                result = {"error": f"{type(error).__name__}: {error}"}
            if anonymize:
                result = _anonymize(result)                           # placeholder until src/anonymize.py exists
            entry = {"model_call": usage["model_calls"],     # which model turn asked for this (one step per turn)
                     "reason": reason, "tool": call.name, "args": args,
                     "ok": not (isinstance(result, dict) and "error" in result),
                     "observation": observe(call.name, result)}
            if isinstance(result, dict) and result.get("locator_steps"):
                entry["substeps"] = result["locator_steps"]                # the locator agent's own trace
            log.append(entry)
            shown = _keep_for_display(call.name, result)
            previous = results.get(call.name)
            if call.name == "compute_ratios" and isinstance(previous, dict) and "values" in previous \
                    and isinstance(shown, dict) and "values" in shown:   # a second call adds ratios, keep both
                shown = {**previous, "values": {**previous["values"], **shown["values"]},
                         "kinds": {**previous["kinds"], **shown["kinds"]}}
            results[call.name] = shown
            if on_event:
                on_event({"type": "step", **entry})
            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))
        contents.append(types.Content(role="user", parts=response_parts))


def run(ticker, anonymize=False, prompt=DEFAULT_PROMPT, verbose=True):
    """Command-line version of investigate(): prints the ReAct trace (thought, action, observation) and the answer.
    Returns (answer_text, steps)."""
    out = investigate(ticker, anonymize=anonymize, prompt=prompt)
    if verbose:
        print(f"\n=== {ticker} (prompt {prompt}): {len(out['steps'])} tool calls, "
              f"{out['usage']['model_calls']} model calls ===")
        for entry in out["steps"]:
            print(f"   [model call {entry.get('model_call')}]")
            print(f"   thought: {entry['reason']}")
            print(f"   action:  {entry['tool']}({entry['args']})")
            print(f"   observe: {entry['observation']}")
            for sub in entry.get("substeps", []):
                print(f"      [locator, FY {sub['filing']}] thought: {sub['reason']}")
                print(f"      [locator, FY {sub['filing']}] action:  {sub['tool']}({sub['args']})")
                print(f"      [locator, FY {sub['filing']}] observe: {sub['observation']}")
        print(out["answer"])
    return out["answer"], out["steps"]


def _anonymize(result):
    """Placeholder: the real one (issue: anonymization) strips company name, ticker and product names."""
    if isinstance(result, dict):
        return {k: ("[redacted]" if k in ("name", "ticker") else v) for k, v in result.items()}
    return result


def _write_log(ticker, log, answer, usage, anonymize, prompt, path=LOG_PATH, skip_newest=None):
    path.parent.mkdir(exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ticker": ticker, "prompt": prompt, "thinking": THINKING_LEVEL, "anonymized": anonymize,
                            "backtest_skip_newest": skip_newest,
                            "ratios_available": RATIOS_AVAILABLE, "tools": log,
                            "usage": usage, "answer": answer, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")


if __name__ == "__main__":
    # python -m src.agent CAT ADBE            (default prompt)
    # python -m src.agent --prompt V4 CAT     (compare prompt versions on the same tickers)
    args = sys.argv[1:]
    chosen = DEFAULT_PROMPT
    if "--prompt" in args:
        i = args.index("--prompt")
        chosen = args[i + 1].upper()
        args = args[:i] + args[i + 2:]
    for t in args or ["CAT", "ADBE"]:
        run(t, prompt=chosen)
