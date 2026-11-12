# --- Javier: "How it works" tab: one model of the app's flow, drawn two ways (code written with help from Claude) ---
# Two renderings of the SAME nodes and edges, so they always agree; the team keeps the better one:
#   B. Mermaid, drawn in the browser, with mouse-wheel zoom and drag to pan (svg-pan-zoom). Both libraries load from
#      the jsDelivr CDN in the viewer's browser; nothing to install.
#   C. React Flow through the streamlit-flow-component package: draggable boxes, zoom, minimap, controls.
# Nov 5, second pass: every path ends at Results (side branches excepted), tool results come back as an Observation,
# both agent loops are drawn as shaded regions, three line styles, and a legend.
# Nov 12 (German): brought in line with the code as of PR #67: session cap and waiting line (run_limiter), the API
# key pool between the agents and Gemini (key_pool), the anonymizer on tool results (anonymize, off in the app),
# and the one retry on an empty reply.
# Keep NODES and EDGES in sync with the code: they name real files and functions.
import html
import json

# --- 1. The model ----------------------------------------------------------------------------------------------
# Colour categories: (legend label, fill, border)
CATEGORIES = {
    "app":     ("app.py: the Streamlit page", "#FFF4D6", "#D9A520"),
    "agent":   ("src/agent.py: the main agent", "#E3EEFF", "#3B6FD8"),
    "prompts": ("src/prompts.py, src/llm.py: prompts and model client", "#EFE6FF", "#7B57C9"),
    "tool":    ("Tools the model can call (file named in each box)", "#E2F5E9", "#2E9A5C"),
    "locate":  ("src/locate_mdna.py: the MD&A locator agent", "#DDF3F2", "#1F8A84"),
    "anon":    ("src/anonymize.py: the anonymizer (anonymized test runs only)", "#FDE8EC", "#C2416B"),
    "ext":     ("External services", "#F2F2F2", "#8A8A8A"),
}

# Loop regions: id -> (title, fill, border, React Flow box (x, y, width, height))
REGIONS = {
    "main": ("Main agent: ReAct loop (up to 9 tool calls)", "#F2F6FE", "#3B6FD8",
             (520, 150, 1000, 720)),
    "loc":  ("MD&A locator agent: its own loop (up to 8 calls per filing)", "#EEF8F7", "#1F8A84",
             (1160, 1240, 780, 620)),
}

# id, category, file, title, functions, detail, region (or ""), (x, y) for React Flow
NODES = [
    ("input",   "app",    "app.py",               "Ticker or example",    "st.form · pick_example()",           "The user starts a run", "", (0, 0)),
    ("load",    "app",    "app.py",               "EDGAR check",          "load_company()",                     "Ticker known? 10-K filings?", "", (330, 0)),
    ("cache",   "app",    "app.py",               "6-hour cache",         "cached_analysis()",                  "Analyzed recently?", "", (660, 0)),
    ("limit",   "app",    "app.py · src/run_limiter.py", "Session cap and waiting line", "MAX_REQUESTS_PER_SESSION · waiting_line()", "10 new analyses per visitor; a few runs at once, the rest queue", "", (990, 0)),
    ("prompts", "prompts", "src/prompts.py",      "System prompt",        "TOOL_SYSTEM_V5",                     "How the agent should investigate", "", (160, 300)),
    ("llm",     "prompts", "src/llm.py",          "Model client",         "client · MODEL",                     "gemini-3.1-flash-lite, thinking LOW", "", (160, 460)),
    ("inv",     "agent",  "src/agent.py",         "Start the run",        "investigate(ticker, prompt='V5')",   "Builds the conversation", "main", (560, 200)),
    ("think",   "agent",  "src/agent.py",         "Think and decide",     "_generate()",                        "Gemini writes a thought, then calls tools or answers; an empty reply is asked once more", "main", (860, 200)),
    ("run",     "agent",  "src/agent.py",         "Run the chosen tool",  "IMPL[tool] (**args)",                 "One or more tools per turn", "main", (560, 420)),
    ("obs",     "agent",  "src/agent.py",         "Observation",          "observe()",                          "Tool result goes back to the model", "main", (860, 420)),
    ("draft",   "agent",  "src/agent.py",         "Draft answer",         "_draft_summary()",                   "Model answers without a tool", "main", (1200, 200)),
    ("check",   "agent",  "src/agent.py",         "Self-check",           "SELF_CHECK",                         "Could a ratio test a claim in the MD&A?", "main", (1200, 420)),
    ("final",   "agent",  "src/agent.py",         "Final answer",         "",                                   "Direction, probability, signals, passages", "main", (1200, 640)),
    ("keys",    "prompts", "src/key_pool.py",     "API key pool",         "pool.generate()",                    "One key per analysis; moves to another key on rate limits", "", (1640, 200)),
    ("gemini",  "ext",    "",                     "Gemini API",           "",                                   "Every model call", "", (1640, 420)),
    ("anon",    "anon",   "src/anonymize.py",     "Anonymizer (optional)", "Anonymizer.unalias() · scrub()",    "Off in the app. Name, ticker, CIK, brands become 'the Company'", "", (160, 640)),
    ("trace",   "app",    "app.py",               "Live trace",           "TraceWriter",                        "One step per model call, as it happens", "", (1640, 640)),
    ("result",  "app",    "app.py",               "Results",              "show_result()",                      "Headline, answer, playbook, ratio table", "", (1640, 860)),
    ("log",     "agent",  "src/agent.py",         "Run log",              "_write_log()",                       "eval/app_runs.jsonl, eval/tool_log.jsonl", "", (1640, 1060)),
    ("card",    "tool",   "src/edgar.py",         "Company card",         "company_card()",                     "SIC, filings, CIK, target metric", "", (0, 980)),
    ("pb",      "tool",   "src/ratio_directory.py", "Industry playbook",  "get_industry_playbook()",            "14 industry groups, 24 ratios", "", (290, 980)),
    ("cr",      "tool",   "src/ratios.py",        "Compute ratios",       "compute_ratios()",                   "Ratios the model chose; flags ±50%", "", (580, 980)),
    ("gm",      "tool",   "src/mdna.py",          "Read the MD&A",        "get_mdna() · extract_mdna_from_text()", "Headings vs contents vs cross-references", "", (870, 980)),
    ("val",     "tool",   "src/mdna.py",          "Validate the section", "validate_section()",                 "Length, other Items, MD&A language", "", (870, 1160)),
    ("lm",      "locate", "src/locate_mdna.py",   "Find the MD&A via the contents", "locate_mdna()",            "Only if get_mdna found nothing", "", (1200, 1100)),
    ("outline", "locate", "src/locate_mdna.py",   "Build the outline",    "build_document() · outline_text()",  "Every table-of-contents link", "loc", (1200, 1300)),
    ("ldecide", "locate", "src/locate_mdna.py",   "Think and decide",     "locate_in_filing()",                 "Gemini picks: peek or extract", "loc", (1200, 1480)),
    ("peek",    "locate", "src/locate_mdna.py",   "Peek",                 "peek(doc, anchor)",                  "First lines at an anchor", "loc", (1600, 1300)),
    ("extract", "locate", "src/locate_mdna.py",   "Extract and check",    "extract(doc, start, end)",           "validate_section() + must end at the next 10-K part", "loc", (1600, 1660)),
    ("sec",     "ext",    "",                     "SEC EDGAR",            "edgar._get()",                       "8 requests/s, cached", "", (330, 1340)),
]

# source, target, label, style: "flow" (solid: what runs next), "data" (dashed: inputs and external services),
# "shared" (dotted: the same code used in two places)
EDGES = [
    ("input", "load", "", "flow"),
    ("load", "cache", "found", "flow"),
    ("load", "result", "not found or 20-F: message, no model call", "flow"),
    ("cache", "result", "yes: cached run", "flow"),
    ("cache", "limit", "no", "flow"),
    ("limit", "inv", "slot free", "flow"),
    ("inv", "think", "", "flow"),
    ("think", "run", "tool call(s)", "flow"),
    ("run", "card", "", "flow"), ("run", "pb", "", "flow"), ("run", "cr", "", "flow"), ("run", "gm", "", "flow"),
    ("run", "lm", "if get_mdna failed", "flow"),
    ("card", "obs", "", "flow"), ("pb", "obs", "", "flow"), ("cr", "obs", "", "flow"),
    ("run", "anon", "anonymized runs", "data"), ("anon", "obs", "scrubbed result", "data"),
    ("gm", "val", "", "flow"), ("val", "obs", "section, or not found", "flow"),
    ("lm", "outline", "", "flow"), ("outline", "ldecide", "", "flow"),
    ("ldecide", "peek", "peek", "flow"), ("peek", "ldecide", "", "flow"),
    ("ldecide", "extract", "extract", "flow"), ("extract", "ldecide", "rejected: reason", "flow"),
    ("extract", "obs", "valid: section returned", "flow"),
    ("obs", "think", "next thought", "flow"),
    ("think", "draft", "answer", "flow"), ("draft", "check", "", "flow"),
    ("check", "run", "yes: compute that ratio", "flow"), ("check", "final", "no: covered", "flow"),
    ("final", "trace", "", "flow"), ("trace", "result", "", "flow"),
    ("prompts", "think", "", "data"), ("llm", "think", "", "data"),
    ("think", "keys", "", "data"), ("ldecide", "keys", "", "data"), ("anon", "keys", "brand scan", "data"),
    ("keys", "gemini", "", "data"),
    ("obs", "trace", "each step, live", "data"), ("final", "log", "", "data"),
    ("load", "sec", "", "data"), ("card", "sec", "", "data"), ("cr", "sec", "", "data"), ("gm", "sec", "", "data"),
    ("outline", "sec", "", "data"),
    ("extract", "val", "same rule", "shared"),
]

LINE_STYLES = {
    "flow":   {"label": "Solid: what runs next", "color": "#55607A", "dash": ""},
    "data":   {"label": "Dashed: inputs and calls to external services", "color": "#8A8A8A", "dash": "7 5"},
    "shared": {"label": "Dotted: the same code used in two places", "color": "#B07A00", "dash": "2 4"},
}

# One line per file: what it is responsible for.
LEGEND = [
    ("app.py", "Streamlit page: input, EDGAR check before any model call, 6-hour cache, live trace, results."),
    ("src/agent.py", "Main agent: tool definitions, the ReAct loop, the self-check turn, observations, logs."),
    ("src/prompts.py", "Versioned system prompts (V3, V4, V5; V5 the default) and the locator's prompt."),
    ("src/llm.py", "Model name and the simple one-call helper used by eval scripts."),
    ("src/key_pool.py", "Several API keys from different projects: one key per analysis, failover on rate limits."),
    ("src/run_limiter.py", "Waiting line: a few analyses run at once across all visitors; the rest see their place."),
    ("src/edgar.py", "SEC EDGAR access (rate-limited, cached), company card, 10-K list, target metric."),
    ("src/ratio_directory.py", "The ratio directory: 24 ratio definitions, 14 industry playbooks, SIC mapping."),
    ("src/ratios.py", "Computes the ratios the model picks from XBRL data; flags growth beyond +/-50%."),
    ("src/mdna.py", "MD&A parser: headings vs contents vs cross-references, and validate_section()."),
    ("src/locate_mdna.py", "Locator agent: finds the MD&A through the filing's table of contents when the parser fails."),
    ("src/anonymize.py", "Anonymizer for test runs: removes name, ticker, CIK and brands from every tool result."),
    ("src/baseline.py", "The three baselines the model must beat: always increase, momentum (last year's direction), reverse momentum."),
    ("src/backtest.py", "Tests tab: loads eval/test_set.csv, runs one test with FY2025 hidden, scores it."),
    ("src/flowchart.py", "This tab: the flow model, drawn as a Mermaid diagram or a React Flow graph."),
]


def legend_html():
    """Colour, line and region key, shown above either diagram."""
    def swatch(fill, border):
        return (f"<span style='display:inline-block;width:14px;height:14px;border-radius:4px;background:{fill};"
                f"border:2px solid {border};vertical-align:-2px;margin-right:6px'></span>")

    def line(color, dash):
        return (f"<svg width='34' height='10' style='vertical-align:middle;margin-right:6px'><line x1='0' y1='5' "
                f"x2='34' y2='5' stroke='{color}' stroke-width='2' stroke-dasharray='{dash}'/></svg>")

    boxes = "".join(f"<div style='margin:2px 0'>{swatch(fill, border)}{html.escape(label)}</div>"
                    for label, fill, border in CATEGORIES.values())
    lines = "".join(f"<div style='margin:2px 0'>{line(s['color'], s['dash'])}{html.escape(s['label'])}</div>"
                    for s in LINE_STYLES.values())
    regions = "".join(f"<div style='margin:2px 0'>{swatch(fill, border)}{html.escape(title)}</div>"
                      for title, fill, border, _ in REGIONS.values())
    col = "flex:1;min-width:240px"
    return (f"<div style='display:flex;flex-wrap:wrap;gap:24px;font-size:14px;line-height:1.5;margin:4px 0 10px'>"
            f"<div style='{col}'><b>Boxes: which file</b>{boxes}</div>"
            f"<div style='{col}'><b>Lines</b>{lines}<b>Shaded areas: the two agent loops</b>{regions}</div></div>")


# --- 2. Option B: Mermaid with zoom and pan ---------------------------------------------------------------------
MERMAID_VERSION = "11.4.1"
PANZOOM_VERSION = "3.6.1"


def mermaid_source():
    """The flow as Mermaid text: nodes coloured by file, one subgraph per agent loop, three line styles."""
    esc = lambda t: html.escape(t, quote=False)                          # noqa: E731

    def label(file, title, funcs, detail):
        parts = [f"<span class='f'>{esc(file)}</span>"] if file else []
        parts.append(f"<b>{esc(title)}</b>")
        if funcs:
            parts.append(f"<code>{esc(funcs)}</code>")
        if detail:
            parts.append(f"<span class='d'>{esc(detail)}</span>")
        return '"' + "<br/>".join(parts).replace('"', "'") + '"'

    lines = ["flowchart TB"]
    for node_id, category, file, title, funcs, detail, region, _ in NODES:
        if not region:
            lines.append(f"  {node_id}[{label(file, title, funcs, detail)}]:::{category}")
    for region_id, (title, fill, border, _) in REGIONS.items():
        lines.append(f'  subgraph {region_id}["{title}"]')
        lines.append("    direction TB")
        for node_id, category, file, title_, funcs, detail, region, _ in NODES:
            if region == region_id:
                lines.append(f"    {node_id}[{label(file, title_, funcs, detail)}]:::{category}")
        lines.append("  end")
        lines.append(f"  style {region_id} fill:{fill},stroke:{border},stroke-width:2px,stroke-dasharray:6 4,color:#1d1d1f")
    for category, (_, fill, border) in CATEGORIES.items():
        lines.append(f"  classDef {category} fill:{fill},stroke:{border},stroke-width:2px,color:#1d1d1f")
    for i, (source, target, text, style) in enumerate(EDGES):
        arrow = "-->" if style == "flow" else "-.->"
        edge_label = '|"' + esc(text).replace('"', "'") + '"|' if text else ""    # quoted: labels contain ( ) :
        lines.append(f"  {source} {arrow}{edge_label} {target}")
        s = LINE_STYLES[style]
        dash = f",stroke-dasharray:{s['dash']}" if s["dash"] else ""
        lines.append(f"  linkStyle {i} stroke:{s['color']},stroke-width:2px{dash}")
    return "\n".join(lines)


def mermaid_html(height=900):
    """A self-contained HTML page: renders the diagram in the browser and adds zoom and pan."""
    source = json.dumps(mermaid_source())
    return f"""
<div style="font:12px Helvetica,Arial;color:#666;margin:0 0 6px 2px">
  Scroll to zoom · drag to move · double-click to zoom in · buttons at the bottom right</div>
<div id="wrap" style="height:{height - 40}px;border:1px solid #ddd;border-radius:10px;background:#fcfcfd;
     position:relative;overflow:hidden">
  <div id="graph" style="width:100%;height:100%"></div>
</div>
<style>
  #graph svg {{ width:100%; height:100%; }}
  #graph .nodeLabel {{ font-family: Helvetica, Arial, sans-serif; font-size: 15px; line-height: 1.35; }}
  #graph .nodeLabel code {{ font-size: 13px; background:rgba(255,255,255,0.7); padding:1px 4px; border-radius:4px; }}
  #graph .nodeLabel .d {{ font-size: 12.5px; color:#555; }}
  #graph .nodeLabel .f {{ font-size: 11.5px; color:#666; font-style: italic; }}
  #graph .edgeLabel {{ font-size: 12px; }}
  #graph .cluster-label .nodeLabel {{ font-weight: bold; font-size: 15px; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@{PANZOOM_VERSION}/dist/svg-pan-zoom.min.js"></script>
<script>
  mermaid.initialize({{ startOnLoad: false, securityLevel: "loose", theme: "base",
    flowchart: {{ htmlLabels: true, curve: "basis", nodeSpacing: 45, rankSpacing: 60, padding: 14 }},
    themeVariables: {{ fontFamily: "Helvetica, Arial, sans-serif", fontSize: "15px", lineColor: "#55607A" }} }});
  mermaid.render("eoGraph", {source}).then(({{svg}}) => {{
    const box = document.getElementById("graph");
    box.innerHTML = svg;
    const el = box.querySelector("svg");
    el.removeAttribute("style"); el.setAttribute("width", "100%"); el.setAttribute("height", "100%");
    svgPanZoom(el, {{ zoomEnabled: true, controlIconsEnabled: true, fit: true, center: true,
                     minZoom: 0.3, maxZoom: 6, zoomScaleSensitivity: 0.3 }});
  }});
</script>
"""


# --- 3. Option C: React Flow (streamlit-flow-component) ---------------------------------------------------------
# Handles: which side of a box its arrows leave from / arrive at (default: leave at the bottom, arrive at the top).
HANDLES = {
    "input": ("right", "left"), "load": ("right", "left"), "cache": ("right", "left"),
    "prompts": ("right", "left"), "llm": ("right", "left"),
    "limit": ("bottom", "left"), "keys": ("bottom", "left"), "anon": ("right", "right"),
    "inv": ("right", "top"), "think": ("bottom", "left"), "run": ("bottom", "top"), "obs": ("top", "bottom"),
    "draft": ("bottom", "left"), "check": ("bottom", "top"), "final": ("right", "top"),
    "gemini": ("bottom", "top"), "trace": ("bottom", "left"), "result": ("bottom", "left"),
    "peek": ("bottom", "right"), "extract": ("left", "right"),
}


def flow_state():
    """Nodes and edges for streamlit_flow, positioned by hand (the x, y in NODES); regions are background boxes."""
    from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
    from streamlit_flow.state import StreamlitFlowState

    nodes = []
    for region_id, (title, fill, border, (x, y, w, h)) in REGIONS.items():
        nodes.append(StreamlitFlowNode(
            id=f"region_{region_id}", pos=(x, y), data={"content": f"**{title}**"}, node_type="default",
            draggable=False, selectable=False, connectable=False, z_index=-1,
            style={"background": fill, "border": f"2px dashed {border}", "borderRadius": "16px",
                   "width": f"{w}px", "height": f"{h}px", "textAlign": "left", "fontSize": "15px",
                   "padding": "8px 12px", "color": border}))
    for node_id, category, file, title, funcs, detail, _, (x, y) in NODES:
        _, fill, border = CATEGORIES[category]
        content = (f"*{file}*  \n" if file else "") + f"**{title}**"
        if funcs:
            content += f"  \n`{funcs}`"
        if detail:
            content += f"  \n{detail}"
        source, target = HANDLES.get(node_id, ("bottom", "top"))
        nodes.append(StreamlitFlowNode(
            id=node_id, pos=(x, y), data={"content": content}, node_type="default",
            source_position=source, target_position=target, draggable=True,
            style={"background": fill, "border": f"2px solid {border}", "borderRadius": "12px", "padding": "10px",
                   "width": "260px", "fontSize": "14px", "textAlign": "left", "color": "#1d1d1f",
                   "boxShadow": "0 1px 3px rgba(0,0,0,0.12)"}))
    edges = []
    for i, (source, target, text, style) in enumerate(EDGES):
        s = LINE_STYLES[style]
        edges.append(StreamlitFlowEdge(
            id=f"e{i}", source=source, target=target, edge_type="default", label=text, label_show_bg=bool(text),
            label_style={"fontSize": "12px"}, marker_end={"type": "arrowclosed", "color": s["color"]},
            style={"stroke": s["color"], "strokeWidth": 2, **({"strokeDasharray": s["dash"]} if s["dash"] else {})}))
    return StreamlitFlowState(nodes, edges)


if __name__ == "__main__":
    print(mermaid_source())
