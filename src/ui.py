# --- German: look and feel of the Analyze tab (Nov 12; code written with help from Claude) ---
# A research-note layout: the call first (direction, probability against a coin flip, the baseline), then the
# evidence the model gave, split into the sections the V5 answer format already has, then the ratios with their
# change. Colours and fonts live in .streamlit/config.toml; this file only styles its own HTML.
# Nothing here changes what the model sees or answers: it reads the answer text and the tools' results.
# Nov 14 (v2): a navy masthead, the trace as a step timeline with an icon per tool, sources and an at-a-glance table
# instead of two folded boxes, a scoreboard for the Tests tab, and financial icons while the app is working.
import html
import re

import streamlit as st

UP, DOWN, INK, MUTED, RULE = "#1F7A4D", "#B4373B", "#17233B", "#5D6778", "#DCE1E8"

CSS = f"""
<style>
.block-container {{ max-width: 1180px; padding-top: 2.2rem; }}
.eo-head h1 {{ font-family: 'Source Serif', serif; font-weight: 600; font-size: 2.6rem; letter-spacing: -0.01em;
              margin: 0; padding: 0; color: {INK}; }}
.eo-head p {{ color: {MUTED}; font-size: 1.02rem; margin: 0.35rem 0 0; max-width: 68ch; line-height: 1.5; }}
.eo-head p.eo-fine {{ font-size: 0.82rem; margin-top: 0.5rem; }}
.eo-head {{ margin-bottom: 1.4rem; }}

.eo-company {{ margin: 1.6rem 0 0.9rem; }}
.eo-company h2 {{ font-family: 'Source Serif', serif; font-weight: 600; font-size: 1.9rem; margin: 0; padding: 0;
                 color: {INK}; }}
.eo-company p {{ color: {MUTED}; margin: 0.2rem 0 0; font-size: 0.95rem; }}

.eo-call {{ display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 2.2rem; align-items: center;
           background: #fff; border: 1px solid {RULE}; border-left: 7px solid var(--eo-tone); border-radius: 8px;
           padding: 1.6rem 1.9rem; margin-bottom: 1.4rem; }}
.eo-call.up {{ --eo-tone: {UP}; }}
.eo-call.down {{ --eo-tone: {DOWN}; }}
.eo-call.none {{ --eo-tone: {MUTED}; }}
.eo-verdict {{ font-family: 'Source Serif', serif; font-weight: 600; font-size: 3.1rem; line-height: 1; color: var(--eo-tone); }}
.eo-verdict .arrow {{ font-size: 0.62em; vertical-align: 0.18em; margin-right: 0.12em; }}
.eo-what {{ color: {INK}; font-size: 1.02rem; margin-top: 0.55rem; }}
.eo-cache {{ color: {MUTED}; font-size: 0.82rem; margin-top: 0.7rem; }}

.eo-prob-top {{ display: flex; justify-content: space-between; align-items: baseline; }}
.eo-prob-top b {{ font-size: 1.7rem; font-weight: 600; color: {INK}; font-variant-numeric: tabular-nums; }}
.eo-prob-top span {{ color: {MUTED}; font-size: 0.88rem; }}
.eo-bar {{ position: relative; height: 10px; background: #ECEFF4; border-radius: 5px; margin: 0.5rem 0 0.3rem; }}
.eo-bar .fill {{ position: absolute; left: 0; top: 0; bottom: 0; border-radius: 5px; background: var(--eo-tone); }}
.eo-bar .coin {{ position: absolute; left: 50%; top: -5px; bottom: -5px; width: 2px; background: {INK}; opacity: .55; }}
.eo-bar-labels {{ position: relative; height: 1.1rem; color: {MUTED}; font-size: 0.76rem; }}
.eo-bar-labels span {{ position: absolute; transform: translateX(-50%); white-space: nowrap; }}
.eo-base {{ border-top: 1px solid {RULE}; margin-top: 0.9rem; padding-top: 0.8rem; font-size: 0.92rem; color: {INK};
           line-height: 1.45; }}
.eo-base .agree {{ font-weight: 600; }}

.eo-sec {{ font-family: 'Source Serif', serif; font-weight: 600; font-size: 1.28rem; color: {INK};
          margin: 1.5rem 0 0.6rem; }}
.eo-signals h4 {{ font-family: 'IBM Plex Sans', sans-serif; font-size: 0.98rem; font-weight: 600; margin: 0 0 0.4rem;
                 padding: 0; color: var(--eo-tone); }}
.eo-signals {{ border-top: 3px solid var(--eo-tone); padding-top: 0.7rem; }}
.eo-signals.up {{ --eo-tone: {UP}; }}
.eo-signals.down {{ --eo-tone: {DOWN}; }}
.eo-signals ul, .eo-list ul {{ margin: 0; padding-left: 1.1rem; }}
.eo-signals li, .eo-list li {{ margin: 0.3rem 0; line-height: 1.5; max-width: 70ch; }}
.eo-quote {{ font-family: 'Source Serif', serif; font-size: 1.08rem; line-height: 1.55; color: {INK};
            border-left: 3px solid {RULE}; padding: 0.15rem 0 0.15rem 1rem; margin: 0 0 0.9rem; max-width: 75ch; }}
.eo-against {{ background: #fff; border: 1px solid {RULE}; border-radius: 8px; padding: 0.9rem 1.1rem;
              line-height: 1.5; max-width: 80ch; }}
.eo-against b {{ display: block; margin-bottom: 0.25rem; }}
.eo-prose {{ line-height: 1.6; max-width: 75ch; margin-bottom: 0.6rem; }}

table.eo-ratios {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; background: #fff;
                  border: 1px solid {RULE}; border-radius: 8px; overflow: hidden; }}
table.eo-ratios th {{ text-align: left; font-weight: 500; color: {MUTED}; padding: 0.55rem 0.8rem;
                     border-bottom: 1px solid {RULE}; background: #FAFBFC; }}
table.eo-ratios td {{ padding: 0.55rem 0.8rem; border-bottom: 1px solid #EEF1F5; vertical-align: top; }}
table.eo-ratios tr:last-child td {{ border-bottom: 0; }}
table.eo-ratios td.num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
table.eo-ratios td.why {{ color: {MUTED}; }}
table.eo-ratios .chg {{ color: {MUTED}; }}
.eo-playbook {{ color: {MUTED}; font-size: 0.92rem; line-height: 1.5; margin: 0 0 0.7rem; max-width: 80ch; }}

/* masthead */
.eo-mast {{ position: relative; overflow: hidden; background: linear-gradient(120deg, #142B52 0%, #1D3A6B 60%, #24497F 100%);
           border-radius: 12px; padding: 2rem 2.2rem 1.7rem; margin-bottom: 1.6rem; color: #fff; }}
.eo-mast h1 {{ font-family: 'Source Serif', serif; font-weight: 600; font-size: 2.9rem; letter-spacing: -0.015em;
              margin: 0; padding: 0; color: #fff; line-height: 1.05; }}
.eo-mast .lede {{ color: #D6E0F0; font-size: 1.06rem; line-height: 1.55; margin: 0.7rem 0 0; max-width: 60ch; }}
.eo-mast .steps {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1.1rem; position: relative; z-index: 1; }}
.eo-mast .steps span {{ background: rgba(255,255,255,0.09); border: 1px solid rgba(255,255,255,0.22); border-radius: 999px;
                       padding: 0.28rem 0.8rem; font-size: 0.86rem; color: #EEF3FA; }}
.eo-mast .fine {{ color: #A9B9D3; font-size: 0.8rem; margin: 1rem 0 0; max-width: 70ch; }}
.eo-mast svg.motif {{ position: absolute; right: 2rem; top: 50%; transform: translateY(-50%); width: 230px; height: auto;
                     opacity: 0.95; }}
@media (max-width: 900px) {{ .eo-mast svg.motif {{ display: none; }} }}

/* trace: one card per model call */
.eo-step {{ display: grid; grid-template-columns: 2.1rem 1fr; gap: 0.8rem; margin: 0.15rem 0 0.1rem; }}
.eo-step .num {{ width: 2.1rem; height: 2.1rem; border-radius: 50%; display: flex; align-items: center; justify-content: center;
                font-weight: 600; font-size: 0.92rem; color: #fff; background: var(--eo-agent); }}
.eo-step .who {{ display: flex; align-items: center; gap: 0.5rem; min-height: 2.1rem; font-weight: 600; color: {INK}; }}
.eo-step .who small {{ font-weight: 500; font-size: 0.78rem; color: var(--eo-agent); background: var(--eo-agent-bg);
                      border-radius: 999px; padding: 0.1rem 0.6rem; }}
.eo-step.main {{ --eo-agent: #1D3A6B; --eo-agent-bg: #E6ECF6; }}
.eo-step.locator {{ --eo-agent: #1F8A84; --eo-agent-bg: #DDF3F2; }}
.eo-step.draft {{ --eo-agent: #A66F00; --eo-agent-bg: #FFF1D6; }}
.eo-step.done {{ --eo-agent: {UP}; --eo-agent-bg: #E6F3EC; }}
.eo-step.done.down {{ --eo-agent: {DOWN}; --eo-agent-bg: #F8E7E7; }}
.eo-act {{ margin: 0 0 0.35rem 2.9rem; border-left: 2px solid var(--eo-agent, {RULE}); padding: 0.1rem 0 0.2rem 1rem; }}
.eo-act.main {{ --eo-agent: #B9C7DE; }}
.eo-act.locator {{ --eo-agent: #A6D9D5; }}
.eo-act.draft {{ --eo-agent: #F0D59A; }}
.eo-act .thought {{ color: {MUTED}; font-style: italic; line-height: 1.45; margin-bottom: 0.4rem; }}
.eo-act .tool {{ display: inline-flex; flex-wrap: wrap; align-items: baseline; gap: 0.2rem 0.45rem; max-width: 100%; background: #fff; border: 1px solid {RULE};
                border-radius: 8px; padding: 0.25rem 0.65rem; font-size: 0.88rem; }}
.eo-act .tool .ico {{ font-size: 1.05rem; }}
.eo-act .tool b {{ font-weight: 600; color: {INK}; white-space: nowrap; }}
.eo-act .tool code {{ font-size: 0.8rem; color: {MUTED}; background: none; padding: 0; }}
.eo-act .obs {{ margin-top: 0.45rem; background: #fff; border: 1px solid #E7EBF1; border-radius: 8px; padding: 0.5rem 0.75rem;
               font-size: 0.9rem; line-height: 1.45; color: {INK}; }}
.eo-act .obs.bad {{ border-color: #EFC7C8; background: #FDF4F4; color: {DOWN}; }}
.eo-act .obs .tick {{ font-weight: 600; margin-right: 0.35rem; color: {UP}; }}
.eo-act .obs.bad .tick {{ color: {DOWN}; }}
.eo-act .note {{ font-size: 0.9rem; line-height: 1.45; color: {INK}; }}
.eo-usage {{ margin: 0.3rem 0 0 2.9rem; color: {MUTED}; font-size: 0.8rem; }}

/* while the app works: financial icons instead of the running figure (top right) */
[data-testid="stStatusWidget"] {{ display: flex; align-items: center; }}
[data-testid="stStatusWidget"] svg, [data-testid="stStatusWidget"] img {{ display: none !important; }}
[data-testid="stStatusWidget"]::before {{ content: "📈"; font-size: 1.25rem; margin-right: 0.35rem;
                                          animation: eo-ledger 2.4s steps(1) infinite; }}
@keyframes eo-ledger {{ 0% {{ content: "📈"; }} 20% {{ content: "🧾"; }} 40% {{ content: "📊"; }}
                        60% {{ content: "💵"; }} 80% {{ content: "📉"; }} }}
@media (prefers-reduced-motion: reduce) {{ [data-testid="stStatusWidget"]::before {{ animation: none; }} }}

/* sources and at a glance */
.eo-files {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.9rem; }}
.eo-file {{ background: #fff; border: 1px solid {RULE}; border-radius: 10px; padding: 0.95rem 1.1rem; display: flex; gap: 0.9rem; }}
.eo-file .doc {{ font-size: 1.7rem; line-height: 1; }}
.eo-file b {{ display: block; font-size: 1rem; color: {INK}; }}
.eo-file span {{ display: block; color: {MUTED}; font-size: 0.86rem; margin-top: 0.1rem; }}
.eo-file a {{ display: inline-block; margin-top: 0.45rem; font-size: 0.86rem; font-weight: 500; color: #1D3A6B;
             text-decoration: none; border-bottom: 1px solid #B9C7DE; }}
.eo-file a:hover {{ border-bottom-color: #1D3A6B; }}
.eo-mdna {{ margin-top: 0.8rem; display: flex; flex-wrap: wrap; gap: 0.45rem; align-items: center; color: {MUTED};
           font-size: 0.88rem; }}
.eo-mdna .chip {{ background: #ECEFF4; color: {INK}; border-radius: 999px; padding: 0.15rem 0.65rem; font-size: 0.82rem; }}
table.eo-ratios th {{ font-weight: 600 !important; color: {INK} !important; }}
table.eo-ratios th small {{ display: block; font-weight: 400; color: {MUTED}; font-size: 0.78rem; }}
table.eo-ratios td.lbl {{ font-weight: 500; }}

/* Tests tab scoreboard */
.eo-board {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.9rem; margin: 0.4rem 0 0.6rem; }}
.eo-score {{ background: #fff; border: 1px solid {RULE}; border-top: 4px solid #C9D1DD; border-radius: 10px; padding: 0.95rem 1.1rem; }}
.eo-score.model {{ border-top: 4px solid #1D3A6B; }}
.eo-score .lab {{ color: {MUTED}; font-size: 0.9rem; }}
.eo-score .val {{ font-family: 'Source Serif', serif; font-size: 2rem; font-weight: 600; color: {INK}; margin-top: 0.2rem;
                 font-variant-numeric: tabular-nums; }}
.eo-score .val.empty {{ font-family: 'IBM Plex Sans', sans-serif; font-size: 1rem; font-weight: 500; color: {MUTED};
                       padding: 0.75rem 0 0.4rem; }}
.eo-score .pct {{ color: {MUTED}; font-size: 0.88rem; }}
.eo-score .track {{ height: 6px; background: #ECEFF4; border-radius: 3px; margin-top: 0.55rem; overflow: hidden; }}
.eo-score .track div {{ height: 100%; background: #1D3A6B; border-radius: 3px; }}
.eo-score.base .track div {{ background: #8A96AA; }}

@media (max-width: 760px) {{
  .eo-call {{ grid-template-columns: 1fr; gap: 1.2rem; padding: 1.2rem 1.2rem; }}
  .eo-verdict {{ font-size: 2.4rem; }}
  .eo-mast {{ padding: 1.5rem 1.3rem 1.3rem; }}
  .eo-mast h1 {{ font-size: 2.2rem; }}
  .eo-board {{ grid-template-columns: 1fr; }}
}}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


MOTIF = """<svg class="motif" viewBox="0 0 230 130" aria-hidden="true">
  <line x1="6" y1="116" x2="224" y2="116" stroke="#8FA6CC" stroke-width="1.5"/>
  <rect x="22" y="62" width="40" height="54" rx="3" fill="#5E7FB3"/>
  <rect x="84" y="40" width="40" height="76" rx="3" fill="#8DA9D6"/>
  <rect x="146" y="22" width="40" height="94" rx="3" fill="none" stroke="#D6E0F0" stroke-width="2" stroke-dasharray="5 4"/>
  <text x="166" y="78" text-anchor="middle" font-family="Source Serif, serif" font-size="30" font-weight="600" fill="#D6E0F0">?</text>
  <text x="42" y="130" text-anchor="middle" font-size="10" fill="#A9B9D3">FY-1</text>
  <text x="104" y="130" text-anchor="middle" font-size="10" fill="#A9B9D3">FY</text>
  <text x="166" y="130" text-anchor="middle" font-size="10" fill="#A9B9D3">next year</text>
</svg>"""


def header():
    """The masthead: what the app does in one sentence, the three things it reads or does, and the fine print."""
    st.markdown(
        "<div class='eo-mast'>" + MOTIF +
        "<h1>Earnings Oracle</h1>"
        "<p class='lede'>Type a US ticker. An AI agent reads the company's last two annual reports and predicts whether "
        "operating income will rise or fall next year, showing the passages it relied on.</p>"
        "<div class='steps'><span>📄 Reads the 10-Ks on SEC EDGAR</span><span>🧮 Picks the ratios for its industry</span>"
        "<span>🔎 Quotes the MD&amp;A</span></div>"
        "<p class='fine'>For banks and insurers it predicts pre-tax income. Output comes from a language model and can be "
        "wrong. It is not financial advice.</p></div>",
        unsafe_allow_html=True)


# --- The answer, split into its sections -------------------------------------------------------------------------
# The V5 answer format names each section ("Signals for an increase:", "Cited passages:", ...). 196 of the 200
# backtest answers have all of them; the other 4 were empty. When fewer than three are found, the page falls back to
# the answer as written.
SECTIONS = {
    "up": r"signals?\s+(?:for|pointing to|toward)\s+(?:an?\s+)?increase",
    "down": r"signals?\s+(?:for|pointing to|toward)\s+(?:an?\s+)?decrease",
    "quotes": r"cited passages?",
    "against": r"(?:the\s+)?strongest (?:piece of )?evidence against(?: (?:your|the|my|this) call)?",
    "ratios": r"ratios? that mattered(?: and why)?",
    "rationale": r"rationale",
    "selfcheck": r"self[- ]check",
}
_HEAD = re.compile(r"^\s*(?:#+\s*)?\**\s*(" + "|".join(f"(?P<{k}>{v})" for k, v in SECTIONS.items())
                   + r")\s*\**\s*:?\s*\**\s*(?P<rest>.*)$", re.I)


def parse_sections(answer):
    """{section: text} for the sections found in the model's answer."""
    out, current = {}, None
    for line in (answer or "").splitlines():
        m = _HEAD.match(line)
        if m:
            current = next(k for k in SECTIONS if m.group(k))
            out[current] = [m.group("rest")] if m.group("rest").strip() else []
        elif current:
            out[current].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _inline(text):
    """Escape for HTML, keep **bold** and *italic* from the model's markdown."""
    text = html.escape(text.strip(), quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)


def items(text):
    """Bullet lines as a list of strings (a paragraph without bullets is one item)."""
    lines, current = [], []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^([-*•]|\d+[.)])\s+", line):
            if current:
                lines.append(" ".join(current))
            current = [re.sub(r"^([-*•]|\d+[.)])\s+", "", line)]
        else:
            current.append(line)
    if current:
        lines.append(" ".join(current))
    return lines


def _ul(text):
    return "<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in items(text)) + "</ul>"


# --- The call ----------------------------------------------------------------------------------------------------
def call_box(direction, probability, target_label, baseline=None, cached_at=None, no_data=False, reason=None):
    """The verdict panel: direction, probability against a coin flip, and the momentum baseline."""
    if no_data:
        tone, verdict = "none", "No data found"
        what = html.escape(reason) if reason else "There was nothing usable to predict from."
    elif direction:
        tone = "up" if direction == "increase" else "down"
        arrow = "▲" if direction == "increase" else "▼"
        verdict = f"<span class='arrow'>{arrow}</span>{direction.capitalize()}"
        what = f"{html.escape(target_label)}, next fiscal year compared with the latest one"
    else:
        tone, verdict, what = "none", "See the answer", "The direction could not be read from the model's text."
    left = (f"<div><div class='eo-verdict'>{verdict}</div><div class='eo-what'>{what}</div>"
            + (f"<div class='eo-cache'>{html.escape(cached_at)}</div>" if cached_at else "") + "</div>")

    right = ""
    if probability is not None and not no_data:
        pct = max(0.0, min(1.0, probability))
        right += (f"<div class='eo-prob-top'><b>{pct:.0%}</b><span>the model's stated probability</span></div>"
                  f"<div class='eo-bar'><div class='fill' style='width:{pct * 100:.1f}%'></div>"
                  f"<div class='coin' title='50%: a coin flip'></div></div>"
                  "<div class='eo-bar-labels'><span style='left:2%'>0%</span><span style='left:50%'>50%, a coin flip</span>"
                  "<span style='left:96%'>100%</span></div>")
    if baseline and baseline.get("direction") and not no_data:
        b_arrow = "▲" if baseline["direction"] == "increase" else "▼"
        older, newer = sorted(baseline["years"])
        verb = "rose" if baseline["direction"] == "increase" else "fell"
        metric = {"operating_income": "operating income", "pretax_income": "pre-tax income"}.get(
            baseline.get("target"), "the target metric")
        agree = ""
        if direction:
            agree = (" <span class='agree'>The model agrees.</span>" if direction == baseline["direction"] else
                     " <span class='agree'>The model goes against the trend.</span>")
        right += (f"<div class='eo-base'>Baseline without a model: {b_arrow} {baseline['direction']}. "
                  f"Last year {metric} {verb}, from ${baseline['previous'] / 1e9:,.2f}B (FY ending {older}) to "
                  f"${baseline['latest'] / 1e9:,.2f}B (FY ending {newer}), and the momentum rule assumes it keeps "
                  f"going.{agree}</div>")
    elif baseline and not no_data:
        right += f"<div class='eo-base'>Baseline without a model: not available ({html.escape(baseline.get('reason', 'unknown reason'))}).</div>"
    st.markdown(f"<div class='eo-call {tone}'>{left}<div>{right}</div></div>", unsafe_allow_html=True)


def _date(iso):
    """'2024-12-31' -> 'Dec 31, 2024'."""
    try:
        from datetime import date
        d = date.fromisoformat(iso)
        return f"{d:%b} {d.day}, {d.year}"
    except (TypeError, ValueError):
        return str(iso)


def company_header(name, card, filings):
    industry = card.get("sic_description") if isinstance(card, dict) else None
    ends = [_date(f["fiscal_year_end"]) for f in filings]
    years = " and ".join(ends) if len(ends) <= 2 else ", ".join(ends)
    sub = (f"{html.escape(industry.title())}. " if industry else "") + \
        f"Based on the 10-Ks for the fiscal years ending {years}."
    st.markdown(f"<div class='eo-company'><h2>{html.escape(name.title() if name.isupper() else name)}</h2>"
                f"<p>{sub}</p></div>", unsafe_allow_html=True)


# --- The evidence ------------------------------------------------------------------------------------------------
def evidence(sections):
    """Signals both ways, the quotes, and the strongest evidence against. Returns False if the answer has no sections."""
    if len(sections) < 3:
        return False
    st.markdown("<div class='eo-sec'>Why</div>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    left.markdown(f"<div class='eo-signals up'><h4>▲ Signals for an increase</h4>{_ul(sections.get('up', 'None given.'))}</div>",
                  unsafe_allow_html=True)
    right.markdown(f"<div class='eo-signals down'><h4>▼ Signals for a decrease</h4>{_ul(sections.get('down', 'None given.'))}</div>",
                   unsafe_allow_html=True)
    quotes = items(sections.get("quotes", ""))
    if quotes and not (len(quotes) == 1 and quotes[0].lower().startswith("none")):
        st.markdown("<div class='eo-sec'>What the filings say</div>", unsafe_allow_html=True)
        st.markdown("".join(f"<div class='eo-quote'>{_inline(q)}</div>" for q in quotes), unsafe_allow_html=True)
    if sections.get("against"):
        st.markdown(f"<div class='eo-against'><b>Strongest evidence against the call</b>{_inline(' '.join(items(sections['against'])))}</div>",
                    unsafe_allow_html=True)
    return True


def prose(title, text):
    if text:
        st.markdown(f"<div class='eo-sec'>{html.escape(title)}</div><div class='eo-prose'>{_inline(' '.join(items(text)))}</div>",
                    unsafe_allow_html=True)


# --- The ratios --------------------------------------------------------------------------------------------------
def _fmt(value, kind):
    if not isinstance(value, (int, float)):
        return "not reported"
    return {"margin": f"{value:.1%}", "growth": f"{value:+.1%}", "days": f"{value:,.0f} days"}.get(kind, f"{value:,.2f}x")


def _change(new, old, kind):
    """Change from the older to the newer year, in the ratio's own unit. Neutral colour: up is not always good."""
    if not (isinstance(new, (int, float)) and isinstance(old, (int, float))):
        return ""
    d = new - old
    if abs(d) < (0.0005 if kind in ("margin", "growth") else 0.005):
        return "no change"
    arrow = "▲" if d > 0 else "▼"
    if kind in ("margin", "growth"):
        return f"{arrow} {d * 100:+.1f} pt"
    if kind == "days":
        return f"{arrow} {d:+,.0f} days"
    return f"{arrow} {d:+,.2f}x"


def ratio_table(result, playbook):
    ratios = result.get("compute_ratios")
    st.markdown("<div class='eo-sec'>Ratios the model chose</div>", unsafe_allow_html=True)
    if isinstance(playbook, dict) and "error" not in playbook:
        st.markdown(f"<p class='eo-playbook'>Industry playbook: <b>{html.escape(playbook['label'])}</b>. "
                    f"{html.escape(playbook['what_drives_operating_income'])}</p>", unsafe_allow_html=True)
    if not isinstance(ratios, dict):
        st.info("The model did not compute any ratios.")
        return
    if "error" in ratios:
        st.warning(f"Ratios not available: {ratios['error']}")
        return
    why = {r["ratio"]: r["why_here"] for r in (playbook or {}).get("recommended_ratios", [])}
    years = sorted(ratios["fiscal_years"])
    new, old = years[-1], (years[-2] if len(years) > 1 else None)
    head = (f"<tr><th>Ratio</th><th>{_fy(new)}</th>" + (f"<th>{_fy(old)}</th><th>Change</th>" if old else "")
            + "<th>Why it matters here</th></tr>")
    rows = []
    for name, by_year in ratios["values"].items():
        kind = ratios["kinds"][name]
        cells = f"<td class='num'>{_fmt(by_year.get(new), kind)}</td>"
        if old:
            cells += (f"<td class='num'>{_fmt(by_year.get(old), kind)}</td>"
                      f"<td class='num chg'>{_change(by_year.get(new), by_year.get(old), kind)}</td>")
        rows.append(f"<tr><td class='lbl'>{html.escape(pretty_ratio(name))}</td>{cells}"
                    f"<td class='why'>{html.escape(why.get(name, 'added by the model'))}</td></tr>")
    st.markdown(f"<table class='eo-ratios'>{head}{''.join(rows)}</table>", unsafe_allow_html=True)
    notes = []
    if ratios.get("check_before_relying"):
        notes.append(f"Flagged for the model: {ratios['check_before_relying']}")
    if ratios.get("unknown_ratios"):
        notes.append(f"Asked for but not in the directory: {', '.join(ratios['unknown_ratios'])}")
    st.caption("Computed from EDGAR XBRL data: these are the tool's numbers, not the model's retelling. "
               + " ".join(notes))


# --- v2 helpers (Nov 14) -----------------------------------------------------------------------------------------
_WORDS = {"rnd": "R&D", "sga": "SG&A", "capex": "capex", "rpo": "RPO", "roa": "ROA", "roe": "ROE", "ebitda": "EBITDA",
          "nim": "NIM", "pp&e": "PP&E", "ppe": "PP&E", "fcf": "free cash flow", "dso": "DSO", "eps": "EPS"}


def pretty_ratio(name):
    """'sga_to_revenue' -> 'SG&A to revenue'."""
    words = [_WORDS.get(w, w) for w in name.split("_")]
    text = " ".join(words)
    return text[0].upper() + text[1:] if text else name


def _fy(iso):
    """Table header for a fiscal year: 'FY2025' with the exact year end under it."""
    try:
        from datetime import date
        d = date.fromisoformat(iso)
        return f"FY{d.year}<small>ends {d:%b} {d.day}, {d.year}</small>"
    except (TypeError, ValueError):
        return html.escape(str(iso))


# The trace: one card per model call. Icons say which kind of evidence each tool brings.
TOOL_ICONS = {"get_company_card": "🏢", "get_industry_playbook": "📘", "compute_ratios": "🧮", "get_mdna": "📄",
              "read_mdna_items": "🔎", "locate_mdna": "🧭", "peek": "👀", "extract": "✂️", "stop": "⏹️",
              "draft_answer": "📝", "empty_reply": "↻"}
TOOL_NAMES = {"get_company_card": "Company card", "get_industry_playbook": "Industry playbook",
              "compute_ratios": "Compute ratios", "get_mdna": "Read the MD&A", "read_mdna_items": "Structured MD&A pass",
              "locate_mdna": "Find the MD&A via the contents", "peek": "Peek at a section", "extract": "Extract a section"}


def step_header(n, label, kind):
    """kind: main, locator, draft, done (add ' down' for a decrease)."""
    head, _, rest = label.partition(" · ")
    chip = f"<small>{html.escape(rest)}</small>" if rest else ""
    st.markdown(f"<div class='eo-step {kind}'><div class='num'>{n}</div><div class='who'>{html.escape(head)}{chip}</div></div>",
                unsafe_allow_html=True)


def step_item(entry, action_text, kind="main"):
    """Thought, tool and observation for one tool call inside a step."""
    tool = entry["tool"]
    if tool in ("draft_answer", "empty_reply") or tool == "stop":
        icon = TOOL_ICONS.get(tool, "•")
        st.markdown(f"<div class='eo-act {kind}'><div class='note'>{icon} {_inline(str(entry.get('observation', '')))}</div></div>",
                    unsafe_allow_html=True)
        return
    ok = entry.get("ok", not str(entry.get("observation", "")).startswith(("Error", "Rejected")))
    observation = entry.get("observation") or ("ok" if ok else "the tool reported an error")
    thought = entry.get("reason") or "(no thought given)"
    name = TOOL_NAMES.get(tool, tool)
    detail = action_text[len(tool):].lstrip(" :") if action_text.startswith(tool) else action_text
    st.markdown(
        f"<div class='eo-act {kind}'><div class='thought'>💭 {_inline(thought)}</div>"
        f"<div class='tool'><span class='ico'>{TOOL_ICONS.get(tool, '🔧')}</span><b>{html.escape(name)}</b>"
        f"<code>{html.escape(detail)}</code></div>"
        f"<div class='obs{'' if ok else ' bad'}'><span class='tick'>{'✓' if ok else '✗'}</span>{_inline(str(observation))}</div></div>",
        unsafe_allow_html=True)


def step_conclusion(text, usage_line, kind="done"):
    st.markdown(f"<div class='eo-act draft' style='--eo-agent: transparent'><div class='note'>{_inline(text)}</div></div>"
                f"<div class='eo-usage'>{html.escape(usage_line)}</div>", unsafe_allow_html=True)


def sources(filings, results):
    """The filings read, as cards with a link, and how the MD&A was read."""
    st.markdown("<div class='eo-sec'>Sources</div>", unsafe_allow_html=True)
    cards = []
    for f in filings:
        cards.append(f"<div class='eo-file'><div class='doc'>📄</div><div><b>Form 10-K, {_fy(f['fiscal_year_end']).split('<')[0]}</b>"
                     f"<span>Fiscal year ending {_date(f['fiscal_year_end'])}</span><span>Filed {_date(f['filed'])}</span>"
                     f"<a href='{html.escape(f['url'])}' target='_blank' rel='noopener'>Open on SEC EDGAR ↗</a></div></div>")
    items_res, text_res = results.get("read_mdna_items"), results.get("locate_mdna") or results.get("get_mdna")
    notes = []
    if isinstance(items_res, dict) and "error" not in items_res:
        counts = {}
        for it in items_res.get("items", []):
            counts[it.get("kind", "item")] = counts.get(it.get("kind", "item"), 0) + 1
        chips = "".join(f"<span class='chip'>{n} {html.escape(k.replace('_', ' '))}</span>" for k, n in counts.items())
        notes.append(f"🔎 MD&amp;A read through the structured pass: {chips or 'no items found'}")
    if isinstance(text_res, dict) and "error" not in text_res:
        parts = ", ".join(f"FY{f['fiscal_year_end'][:4]}, {f['chars']:,} characters" for f in text_res.get("filings", []))
        notes.append(f"📄 Full MD&amp;A text read ({html.escape(parts)})")
    for res in (items_res, text_res):
        if isinstance(res, dict) and "error" in res:
            notes.append(f"⚠️ MD&amp;A: {html.escape(res['error'])}")
    if not notes:
        notes.append("The model did not read the MD&amp;A: the call rests on the ratios.")
    st.markdown(f"<div class='eo-files'>{''.join(cards)}</div>"
                + "".join(f"<div class='eo-mdna'>{n}</div>" for n in notes), unsafe_allow_html=True)


GLANCE = [("revenue_billion_usd", "Revenue", "usd"), ("operating_income_billion_usd", "Operating income", "usd"),
          ("operating_margin", "Operating margin", "margin"), ("revenue_growth", "Revenue growth", "growth"),
          ("operating_income_growth", "Operating income growth", "growth"), ("asset_turnover", "Asset turnover", "multiple"),
          ("liabilities_to_equity", "Liabilities to equity", "multiple")]


def at_a_glance(standard):
    """The same seven figures for every company, latest year first (as in the ratio table), with the change."""
    if not isinstance(standard, dict) or "error" in standard:
        return
    cur, pri = standard["fy_current"], standard["fy_prior"]
    def fmt(v, kind):
        if not isinstance(v, (int, float)):
            return "not reported"
        return f"${v:,.2f}B" if kind == "usd" else _fmt(v, kind)
    def chg(a, b, kind):
        if kind == "usd":
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b:
                d = (a - b) / abs(b)
                return f"{'▲' if d > 0 else '▼'} {d:+.1%}"
            return ""
        return _change(a, b, kind)
    rows = "".join(f"<tr><td class='lbl'>{lab}</td><td class='num'>{fmt(cur.get(k), kind)}</td>"
                   f"<td class='num'>{fmt(pri.get(k), kind)}</td><td class='num chg'>{chg(cur.get(k), pri.get(k), kind)}</td></tr>"
                   for k, lab, kind in GLANCE)
    st.markdown("<div class='eo-sec'>The company at a glance</div>"
                "<p class='eo-playbook'>The same figures for every company, from EDGAR XBRL data, so you can compare "
                "companies side by side.</p>"
                f"<table class='eo-ratios'><tr><th>Figure</th><th>{_fy(cur['fiscal_year_end'])}</th>"
                f"<th>{_fy(pri['fiscal_year_end'])}</th><th>Change</th></tr>{rows}</table>", unsafe_allow_html=True)


def scoreboard(cards):
    """Tests tab: cards = [(label, correct or None, total, help, is_model)]."""
    out = []
    for label, correct, total, help_text, is_model in cards:
        if correct is None or not total:
            val = "<div class='val empty'>Not run yet</div>"
            bar = ""
        else:
            val = f"<div class='val'>{correct} of {total}</div><div class='pct'>{correct / total:.0%} correct</div>"
            bar = f"<div class='track'><div style='width:{correct / total * 100:.0f}%'></div></div>"
        out.append(f"<div class='eo-score {'model' if is_model else 'base'}' title='{html.escape(help_text)}'>"
                   f"<div class='lab'>{html.escape(label)}</div>{val}{bar}</div>")
    st.markdown(f"<div class='eo-board'>{''.join(out)}</div>", unsafe_allow_html=True)
