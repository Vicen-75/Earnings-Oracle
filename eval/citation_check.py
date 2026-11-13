# --- Javier: citation check for the 200-company backtest, issue #53 (code written with help from Claude) ---
# Are the passages the model quotes real, and do they come from the filings it was allowed to read?
# Every answer ends with "Cited passages:", usually 3 quotes. Each quote is looked up, in this order, in:
#   1. the MD&A the agent read (same extractor and same hidden-year rule as the run: src.mdna, skip_newest),
#   2. the rest of those same 10-Ks (real text, but from outside the MD&A),
#   3. optionally, the hidden target-year 10-K the model was NOT allowed to see (a match there only is a red flag).
#
# Two steps:
#   python -m eval.citation_check fetch            # EDGAR only, no model calls. Downloads the 10-Ks the agent read
#                                                  # (about 400), keeps their text in cache/citation_check/ (ignored by
#                                                  # git). Resumable: companies already cached are skipped.
#   python -m eval.citation_check fetch --hidden   # also the hidden target-year 10-K (about 200 more downloads)
#   python -m eval.citation_check                  # no network: writes eval/citation_check_results.csv and
#                                                  # eval/citation_check_report.md
#
# Matching ignores case, spacing, curly vs straight quotes and dash types. A quote with "..." is split at the
# ellipsis and each piece is looked up. Categories, best first:
#   verbatim         the quote appears word for word in the MD&A
#   near_verbatim    at least 90% of its words appear in order in one MD&A passage (a dropped word, a table row)
#   outside_mdna     verbatim or near-verbatim, but in another part of the same 10-K
#   paraphrase       60% to 90% of its words in order: the model reworded or stitched a passage
#   not_found        under 60%: no passage in the filings it read comes close
#   hidden_year      not in the filings it read, but verbatim or near-verbatim in the hidden target-year 10-K
#   no_text          the filings could not be downloaded or parsed
# A low-scoring quote is not proof of invention: eval/citation_check_notes.csv records the hand reading of each one.
import csv
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

TEST_SET_PATH = Path("eval/test_set_200.csv")
RESULTS_PATH = Path("eval/backtest_200_results.jsonl")
RUNS_PATH = Path("eval/backtest_200_runs.jsonl")
CHECKS_PATH = Path("eval/sample_checks.csv")
NOTES_PATH = Path("eval/citation_check_notes.csv")
CACHE_DIR = Path("cache/citation_check")
OUT_CSV = Path("eval/citation_check_results.csv")
REPORT_PATH = Path("eval/citation_check_report.md")
PROMPT = "V5"

NEAR, PARTIAL = 0.90, 0.60          # share of the quote's words found in order in one passage
MIN_PIECE_WORDS = 4                 # pieces of an ellipsis quote shorter than this are skipped
CATEGORIES = ["verbatim", "near_verbatim", "outside_mdna", "paraphrase", "not_found", "hidden_year", "no_text"]
LABELS = {"verbatim": "Verbatim in the MD&A", "near_verbatim": "Near-verbatim in the MD&A",
          "outside_mdna": "Real, but from outside the MD&A", "paraphrase": "Reworded or stitched",
          "not_found": "Not found", "hidden_year": "Found only in the hidden target-year 10-K",
          "no_text": "Filing text unavailable"}


# --- loading -------------------------------------------------------------------------------------------------------
def load_runs():
    with open(TEST_SET_PATH, newline="", encoding="utf-8") as f:
        test_set = {r["ticker"]: r for r in csv.DictReader(f)}
    results, runs = {}, {}
    with open(RESULTS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r["prompt"] == PROMPT and not r.get("error"):
                    results[r["ticker"]] = r
    with open(RUNS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r["prompt"] == PROMPT:
                    runs[r["ticker"]] = r
    return test_set, results, runs


def extract_quotes(answer):
    """The quotes listed under 'Cited passages:', one per bullet. Nested quotes ("SG&A") and a note in brackets after
    the closing quote are handled by taking everything between the first and the last quote mark of the bullet."""
    m = re.search(r"Cited passages:\s*\n(.*?)(?:\n\s*\n|\n(?:Strongest evidence|Ratios that|Rationale))",
                  answer or "", re.S)
    if not m:
        return []
    quotes = []
    for line in m.group(1).splitlines():
        s = re.sub(r"^\s*(?:[-*•]|\d+\.)\s*", "", line).strip()
        marks = [i for i, ch in enumerate(s) if ch in "\"“”"]
        if len(marks) >= 2:
            quotes.append(s[marks[0] + 1:marks[-1]].strip())
        elif s:
            quotes.append(s)
    return [q for q in quotes if q]


# --- step 1: fetch (EDGAR) -----------------------------------------------------------------------------------------
def _cache_path(ticker):
    return CACHE_DIR / f"{re.sub(r'[^A-Za-z0-9_-]', '_', ticker)}.json.gz"


def fetch(hidden=False):
    from src.edgar import list_10ks                              # only this step needs the network
    from src.mdna import fetch_html, html_to_text, extract_mdna_from_text

    with open(CHECKS_PATH, newline="", encoding="utf-8") as f:
        cik = {r["ticker"]: r["cik"] for r in csv.DictReader(f) if r["status"] == "ACCEPTED"}
    test_set, _, runs = load_runs()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for i, (ticker, t) in enumerate(test_set.items(), 1):
        path = _cache_path(ticker)
        cached = json.loads(gzip.decompress(path.read_bytes())) if path.exists() else None
        if cached and (cached.get("hidden") is not None or not hidden):
            continue
        skip = int(runs.get(ticker, {}).get("backtest_skip_newest", t["skip_newest"]))
        filings = list_10ks(cik[ticker], how_many=2 + skip)        # newest first; [skip:] are the ones the agent read
        record = {"ticker": ticker, "skip_newest": skip, "read": [], "hidden": None}
        for f in filings[skip:skip + 2]:
            html = fetch_html(f["url"])
            text = html_to_text(html) if html else ""
            record["read"].append({"fiscal_year_end": f["fiscal_year_end"], "url": f["url"], "full": text,
                                   "mdna": (extract_mdna_from_text(text) or "") if text else ""})
        if hidden and skip >= 1:
            f = filings[skip - 1]                                    # the target year: hidden during the run
            html = fetch_html(f["url"])
            record["hidden"] = {"fiscal_year_end": f["fiscal_year_end"], "url": f["url"],
                                "full": html_to_text(html) if html else ""}
        path.write_bytes(gzip.compress(json.dumps(record).encode("utf-8")))
        sizes = ", ".join(f"{len(f['mdna']):,}/{len(f['full']):,}" for f in record["read"])
        print(f"{i:3}/{len(test_set)} {ticker:8} MD&A/10-K chars: {sizes}{'  + hidden' if record['hidden'] else ''}")
    print(f"Cached in {CACHE_DIR}. Next: python -m eval.citation_check")


# --- matching ------------------------------------------------------------------------------------------------------
def normalize(text):
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"[‘’‚‛′`]", "'", text)
    text = re.sub(r"[“”„″]", '"', text)
    text = re.sub(r"[‐-―−]", "-", text)
    text = text.replace(" ", " ").lower()
    return re.sub(r"\s+", " ", text).strip()


def words(text):
    return re.findall(r"[a-z0-9$%]+(?:[.,'][a-z0-9]+)*", normalize(text))


class Doc:
    """One searchable text: its normalized string and an index from 3-word phrases to word positions."""

    def __init__(self, text):
        self.text = normalize(text)
        self.words = words(text)
        self.joined = " " + " ".join(self.words) + " "
        self.index = defaultdict(list)
        for i in range(len(self.words) - 2):
            self.index[tuple(self.words[i:i + 3])].append(i)

    def exact(self, piece):
        q = words(piece)
        return bool(q) and f" {' '.join(q)} " in self.joined

    def coverage(self, piece):
        """Share of the piece's words found in order in the best-matching passage (1.0 = every word)."""
        return self.best_passage(piece)[0]

    def best_passage(self, piece):
        """(coverage, passage words) for the passage that best matches the piece."""
        q = words(piece)
        if not q:
            return 0.0, []
        if self.exact(piece):
            return 1.0, q
        votes = Counter()
        for j in range(len(q) - 2):
            for pos in self.index.get(tuple(q[j:j + 3]), ()):
                votes[(pos - j) // 10] += 1                       # anchors that agree on where the quote starts
        best = (0.0, [])
        for bucket, _ in votes.most_common(5):
            start = max(0, bucket * 10 - len(q))
            window = self.words[start:bucket * 10 + 2 * len(q) + 10]
            matched = sum(b.size for b in SequenceMatcher(None, q, window, autojunk=False).get_matching_blocks())
            if matched / len(q) > best[0]:
                best = (matched / len(q), window)
        return best


def pieces(quote):
    parts = [p for p in re.split(r"\.\.\.|…|\[\.\.\.\]", quote) if len(words(p)) >= MIN_PIECE_WORDS]
    return parts or [quote]


def score(quote, docs):
    """Lowest coverage across the quote's pieces, each piece at its best doc; returns (coverage, doc label)."""
    worst, where = 2.0, None                                   # above any coverage, so the first piece always sets it
    for p in pieces(quote):
        best, label = 0.0, None
        for name, doc in docs:
            c = doc.coverage(p)
            if c > best:
                best, label = c, name
        if best < worst:
            worst, where = best, label
    return min(worst, 1.0), where


NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers(text):
    """Numbers in a text, without thousands separators ('$1,271.1 million' gives '1271.1')."""
    return [n.replace(",", "").rstrip(".") for n in NUMBER.findall(normalize(text))]


def numbers_not_in_passage(quote, docs):
    """Numbers in the quote that do not appear in the filing passage it best matches. Catches a near-verbatim quote
    with a changed figure (a wrong year, a value taken from the next sentence). Verbatim quotes pass by definition."""
    if docs is None:
        return []
    mdna, full, _ = docs
    missing = []
    for p in pieces(quote):
        passage = max((d.best_passage(p) for _, d in mdna + full), key=lambda x: x[0], default=(0.0, []))[1]
        text = " ".join(passage)
        found = set(numbers(text)) | set(numbers(text.replace(" ", "")))
        missing += [n for n in numbers(p) if n not in found]
    return missing


def build_docs(record):
    """Search indexes for one company, built once: (MD&A docs, full 10-K docs, hidden-year doc or None)."""
    if record is None or not any(f["full"] for f in record["read"]):
        return None
    mdna = [(f"MD&A FY{f['fiscal_year_end'][:4]}", Doc(f["mdna"])) for f in record["read"] if f["mdna"]]
    full = [(f"10-K FY{f['fiscal_year_end'][:4]}", Doc(f["full"])) for f in record["read"] if f["full"]]
    hidden = record.get("hidden")
    hidden_doc = (f"hidden 10-K FY{hidden['fiscal_year_end'][:4]}", Doc(hidden["full"])) if hidden and hidden["full"] else None
    return mdna, full, hidden_doc


def classify(quote, docs):
    if docs is None:
        return "no_text", 0.0, ""
    mdna, full, hidden_doc = docs
    c, where = score(quote, mdna) if mdna else (0.0, None)
    exact = [name for name, d in mdna if all(d.exact(p) for p in pieces(quote))]
    if exact:
        return "verbatim", 1.0, exact[0]
    if c >= NEAR:
        return "near_verbatim", c, where
    c_full, where_full = score(quote, full)
    if c_full >= NEAR:
        return "outside_mdna", c_full, where_full
    best, best_where = max((c, where), (c_full, where_full), key=lambda x: x[0])
    if hidden_doc:
        c_hidden, _ = score(quote, [hidden_doc])
        if c_hidden >= NEAR and c_hidden > best:
            return "hidden_year", c_hidden, hidden_doc[0]
    return ("paraphrase" if best >= PARTIAL else "not_found"), best, best_where or ""


# --- step 2: report ------------------------------------------------------------------------------------------------
def pct(k, n):
    return f"{k / n:.0%}" if n else "n/a"


def report():
    test_set, results, runs = load_runs()
    notes = {}
    if NOTES_PATH.exists():
        with open(NOTES_PATH, newline="", encoding="utf-8") as f:
            notes = {(r["ticker"], int(r["quote_no"])): r for r in csv.DictReader(f)}
    rows, cached, with_hidden = [], 0, 0
    for ticker, t in test_set.items():
        path = _cache_path(ticker)
        record = json.loads(gzip.decompress(path.read_bytes())) if path.exists() else None
        cached += record is not None
        with_hidden += bool(record and record.get("hidden") and record["hidden"]["full"])
        run = runs.get(ticker, {})
        used_locator = any(x["tool"] == "locate_mdna" for x in run.get("tools", []))
        res = results.get(ticker)
        quotes = extract_quotes(run.get("answer"))
        docs = build_docs(record) if quotes else None
        for n, q in enumerate(quotes, 1):
            cat, cov, where = classify(q, docs)
            off = numbers_not_in_passage(q, docs) if cat not in ("verbatim", "no_text") else []
            note = notes.get((ticker, n), {})
            rows.append({"ticker": ticker, "quote_no": n, "category": cat, "coverage": round(cov, 2),
                         "found_in": where, "numbers_not_in_passage": " ".join(off), "words": len(words(q)), "locator_used": used_locator,
                         "industry_group": t["industry_group"], "answer_correct": bool(res and res["direction"] == t["truth"]),
                         "hand_verdict": note.get("verdict", ""), "hand_note": note.get("note", ""), "quote": q})
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    by_cat = Counter(r["category"] for r in rows)
    answers = defaultdict(list)
    for r in rows:
        answers[r["ticker"]].append(r)
    good = {"verbatim", "near_verbatim", "outside_mdna"}
    clean = [t for t, qs in answers.items()
             if all(q["category"] in good and q["hand_verdict"] not in ("wrong_number", "invented") for q in qs)]
    out = ["# Citation check: 200-company backtest, prompt V5 (issue #53)", "",
           f"Text cached for {cached} of {len(test_set)} companies. {n} quotes from {len(answers)} answers "
           f"({len(test_set) - len(answers)} answers had no quotes: the 4 empty answers and answers without a "
           "'Cited passages' section).", "",
           "## Are the quotes real?", "", "| Category | Quotes | Share |", "|---|---|---|"]
    for c in CATEGORIES:
        if by_cat.get(c):
            out.append(f"| {LABELS[c]} | {by_cat[c]} | {pct(by_cat[c], n)} |")
    real = sum(by_cat[c] for c in good)
    out += ["", f"**{real} of {n} quotes ({pct(real, n)}) are real text from the filings the model read** "
            f"(verbatim or near-verbatim). {by_cat['verbatim'] + by_cat['near_verbatim']} ({pct(by_cat['verbatim'] + by_cat['near_verbatim'], n)}) "
            f"come from the MD&A itself.", "",
            f"Answers whose every quote is real (and, where read by hand, has the right numbers): {len(clean)} of "
            f"{len(answers)} ({pct(len(clean), len(answers))}).", ""]

    if with_hidden:
        out += [f"**Look-ahead check.** The hidden target-year 10-K (the filing the model was not allowed to read) "
                f"was searched for {with_hidden} of {len(test_set)} companies. Quotes that match only that filing: "
                f"{by_cat.get('hidden_year', 0)}.", ""]
    if by_cat.get("hidden_year"):
        out += ["**Look-ahead warning.** These quotes match only the target-year 10-K the model was not allowed to "
                "read: " + ", ".join(f"{r['ticker']} #{r['quote_no']}" for r in rows if r["category"] == "hidden_year")
                + ". Check each by hand (it can also be boilerplate repeated from year to year).", ""]

    out += ["## Do bad citations go with wrong answers?", "", "| Answers | Count | Correct | Accuracy |",
            "|---|---|---|---|"]
    for label, group in (("Every quote real", clean), ("At least one quote not confirmed",
                                                       [t for t in answers if t not in clean])):
        k = sum(answers[t][0]["answer_correct"] for t in group)
        out.append(f"| {label} | {len(group)} | {k} | {pct(k, len(group))} |")

    out += ["", "## Where the problems are", "", "| Group | Quotes | Real | Share real |", "|---|---|---|---|"]
    for label, key in (("Locator used (agent found the MD&A itself)", True), ("Standard extractor", False)):
        g = [r for r in rows if r["locator_used"] == key]
        k = sum(r["category"] in good for r in g)
        out.append(f"| {label} | {len(g)} | {k} | {pct(k, len(g))} |")
    for v, c in Counter(r["industry_group"] for r in rows).most_common():
        g = [r for r in rows if r["industry_group"] == v]
        k = sum(r["category"] in good for r in g)
        out.append(f"| {v.replace('_', ' ')} | {len(g)} | {k} | {pct(k, len(g))} |")
    srcs = Counter(r["found_in"].split(" FY")[-1] for r in rows if r["category"] in good and r["found_in"])
    out += ["", "Which year's filing the real quotes come from: "
            + ", ".join(f"FY{y} {c}" for y, c in sorted(srcs.items(), reverse=True)) + ".", ""]

    with_numbers = [r for r in rows if r["numbers_not_in_passage"]]
    out += ["## Are the numbers right?", "",
            f"Verbatim quotes carry the filing's numbers by definition. Of the {sum(r['category'] not in ('verbatim', 'no_text') for r in rows)} "
            f"other quotes, {len(with_numbers)} contain a number that is not in the passage they match: "
            + (", ".join(f"{r['ticker']} #{r['quote_no']} ({r['numbers_not_in_passage']})" for r in with_numbers) or "none")
            + ". Each is read by hand below; a number added as framing (a date stated elsewhere in the filing) is "
            "harmless, a changed figure is not.", ""]

    flagged = [r for r in rows if r["category"] in ("paraphrase", "not_found", "hidden_year") or r["numbers_not_in_passage"]]
    out += ["## Quotes that need a hand reading", "",
            f"{len(flagged)} quotes. Verdicts go in `{NOTES_PATH.as_posix()}` (ticker, quote_no, verdict, note); verdict is one of "
            "paraphrase (meaning kept), stitched (real pieces joined), wrong_number (a figure that differs from the "
            "filing), invented (no basis in the filings), from_tool (a number from the ratio tool written as a quote), "
            "boilerplate.", ""]
    if notes:
        v = Counter(r["hand_verdict"] for r in flagged if r["hand_verdict"])
        out += ["| Hand verdict | Quotes |", "|---|---|"] + [f"| {k} | {c} |" for k, c in v.most_common()]
        out.append(f"| not read yet | {sum(not r['hand_verdict'] for r in flagged)} |")
        out.append("")
    out += ["| Company | # | Category | Coverage | Quote (start) | Hand note |", "|---|---|---|---|---|---|"]
    for r in sorted(flagged, key=lambda r: (r["category"], r["coverage"])):
        q = r["quote"][:110].replace("|", "/") + ("..." if len(r["quote"]) > 110 else "")
        out.append(f"| {r['ticker']} | {r['quote_no']} | {r['category']} | {r['coverage']:.2f} | {q} | "
                   f"{r['hand_verdict']}{': ' if r['hand_note'] else ''}{r['hand_note']} |")
    REPORT_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_CSV} and {REPORT_PATH}: {real} of {n} quotes real ({pct(real, n)}).")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch(hidden="--hidden" in sys.argv)
    else:
        report()
