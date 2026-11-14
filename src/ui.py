# --- German: look and feel of the Analyze tab (Nov 12; code written with help from Claude) ---
# A research-note layout: the call first (direction, probability against a coin flip, the baseline), then the
# evidence the model gave, split into the sections the V5 answer format already has, then the ratios with their
# change. Colours and fonts live in .streamlit/config.toml; this file only styles its own HTML.
# Nothing here changes what the model sees or answers: it reads the answer text and the tools' results.
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

@media (max-width: 760px) {{
  .eo-call {{ grid-template-columns: 1fr; gap: 1.2rem; padding: 1.2rem 1.2rem; }}
  .eo-verdict {{ font-size: 2.4rem; }}
}}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def header():
    st.markdown(
        "<div class='eo-head'><h1>Earnings Oracle</h1>"
        "<p>Type a US ticker. An AI agent reads the company's last two annual reports (10-Ks) on SEC EDGAR, picks the "
        "ratios that matter for its industry, and predicts whether operating income will rise or fall next year, "
        "with the passages it relied on.</p>"
        "<p class='eo-fine'>For banks and insurers it predicts pre-tax income. Output comes from a language model and "
        "can be wrong. It is not financial advice.</p></div>",
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
    arrow = "▲" if d > 0 else ("▼" if d < 0 else "▬")
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
    head = (f"<tr><th>Ratio</th><th>FY ending {new}</th>" + (f"<th>FY ending {old}</th><th>Change</th>" if old else "")
            + "<th>Why it matters here</th></tr>")
    rows = []
    for name, by_year in ratios["values"].items():
        kind = ratios["kinds"][name]
        cells = f"<td class='num'>{_fmt(by_year.get(new), kind)}</td>"
        if old:
            cells += (f"<td class='num'>{_fmt(by_year.get(old), kind)}</td>"
                      f"<td class='num chg'>{_change(by_year.get(new), by_year.get(old), kind)}</td>")
        rows.append(f"<tr><td>{html.escape(name.replace('_', ' ').capitalize())}</td>{cells}"
                    f"<td class='why'>{html.escape(why.get(name, 'added by the model'))}</td></tr>")
    st.markdown(f"<table class='eo-ratios'>{head}{''.join(rows)}</table>", unsafe_allow_html=True)
    notes = []
    if ratios.get("check_before_relying"):
        notes.append(f"Flagged for the model: {ratios['check_before_relying']}")
    if ratios.get("unknown_ratios"):
        notes.append(f"Asked for but not in the directory: {', '.join(ratios['unknown_ratios'])}")
    st.caption("Computed from EDGAR XBRL data: these are the tool's numbers, not the model's retelling. "
               + " ".join(notes))
