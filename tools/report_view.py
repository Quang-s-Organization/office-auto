#!/usr/bin/env python3
"""report_view.py — make the "invisible" in a built DOCX visible to an LLM.

The pipeline's blind spot (docs/report-format-diagnosis-2026-06-27-run2.md): the
model never SEES the output it produced — it only reads green check-marks from
the validator/composer, so a structurally-broken document (e.g. the template's
foreign cover + TOC + tables left stacked on top of the real content) sails
through "validated-clean".

This is a PERCEPTION step, not another closed-set guard. It turns the output
into a compact, reading-order text VIEW (so the model can read what is actually
there), and — when given the source content IR — emits a few DESCRIPTIVE
observations that point the eye at anomalies (foreign text, extra tables,
oversized front matter). It deliberately does NOT pass/fail: the model reads the
view, compares it to what it intended, and decides. Open-set, not per-case.

Built on officecli ONLY (no new framework):
  • `officecli view <file> text`   → reading-order, one line per paragraph,
                                      tables shown as `[/body/tbl[N]] [Table: R×C]`.
  • `officecli query <file> p --json` → style/align per paragraph (joined by paraId).

Usage:
    python3 tools/report_view.py out/report.docx                 # human/LLM view
    python3 tools/report_view.py out/report.docx --content content.ir.json
    python3 tools/report_view.py out/report.docx --json
"""

from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata

# `view text` lines look like `[/body/p[@paraId=XXXX]] text` or
# `[/body/tbl[N]] [Table: R×C]`. The path ITSELF contains brackets, so anchor on
# the doubled `]]` (path's own closing bracket + the outer wrapper).
PARA_LINE_RE = re.compile(r"^\[/body/p\[@paraId=(?P<pid>[0-9A-Fa-f]+)\]\]\s?(?P<text>.*)$")
TBL_LINE_RE = re.compile(r"^\[/body/tbl\[(?P<idx>\d+)\]\]\s?(?P<text>.*)$")
# `view text` renders a table as "[Table: 5 rows]"; older builds used "5×7".
TABLE_DIM_RE = re.compile(r"\[Table:\s*(?P<r>\d+)\s*(?:[×x]\s*(?P<c>\d+)|rows?)\]")

_HEADING_STYLES = {"Heading1", "Heading2", "Heading3"}
_TOCISH = {"Toc1", "Toc2", "Toc3", "Tableofcontents"}


def _officecli(args: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(["officecli"] + args, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        return 124, ""


_BULLET_LEAD = re.compile(r"^[\s•·*▪◦‣\-–—]+")


def _norm(s: str) -> str:
    """Lowercase, strip diacritics + collapse whitespace — for robust text match."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def _is_foreign(text: str, blob: str, ngram: int = 4) -> bool:
    """True when a paragraph's text does NOT come from the source content.

    Robust to the transforms the builder applies (list-bullet prefixes, inline
    math extracted out as OMML leaving gaps): rather than require an exact
    substring, ask whether ANY contiguous `ngram`-word phrase of the paragraph
    appears in the content blob. Genuinely leaked/foreign text (a different
    paper's title/authors) shares no such phrase; a transformed-but-sourced
    paragraph still shares plenty. Short paragraphs fall back to substring."""
    t = _BULLET_LEAD.sub("", _norm(text))
    words = t.split()
    if len(words) < ngram:
        return bool(t) and t not in blob
    return not any(" ".join(words[i:i + ngram]) in blob
                   for i in range(len(words) - ngram + 1))


# ── read the document as ordered blocks (officecli only) ───────────────────

def read_blocks(docx: str) -> list[dict]:
    """Ordered list of body blocks: {kind: 'para'|'table', ...} via `view text`,
    enriched with style/align from `query p`."""
    # style/align lookup
    style_by_pid: dict[str, dict] = {}
    code, out = _officecli(["query", docx, "p", "--json"])
    if code == 0 and out.strip():
        try:
            for r in json.loads(out[out.find("{"):]).get("data", {}).get("results", []):
                fmt = r.get("format", {})
                pid = fmt.get("paraId")
                if pid:
                    st = fmt.get("style")
                    style_by_pid[pid] = {
                        "style": (st.title().replace(" ", "") if st else "Normal"),
                        "align": fmt.get("align"),
                    }
        except json.JSONDecodeError:
            pass

    code, out = _officecli(["view", docx, "text"])
    blocks: list[dict] = []
    for line in out.splitlines():
        mt = TBL_LINE_RE.match(line)
        if mt:
            dim = TABLE_DIM_RE.search(mt.group("text"))
            cols = dim.group("c") if dim else None
            blocks.append({"kind": "table", "idx": int(mt.group("idx")),
                           "rows": int(dim.group("r")) if dim else None,
                           "cols": int(cols) if cols else None})
            continue
        mp = PARA_LINE_RE.match(line)
        if not mp:
            continue
        pid, text = mp.group("pid"), mp.group("text")
        meta = style_by_pid.get(pid, {"style": "Normal", "align": None})
        style = meta["style"]
        blocks.append({
            "kind": "para", "paraId": pid, "style": style, "align": meta["align"],
            "text": text.strip(),
            "is_heading": style in _HEADING_STYLES,
            "is_toc": style in _TOCISH,
        })
    return blocks


# ── source-content corpus (what the output SHOULD contain) ─────────────────

def content_corpus(content_ir: dict) -> tuple[str, set, int]:
    """(normalized text blob, set of heading titles, table count) from content IR."""
    blob_parts: list[str] = []
    headings: set = set()
    tables = 0
    for s in content_ir.get("sections", []):
        title = s.get("title", "")
        headings.add(_norm(title))
        blob_parts.append(_norm(title))
        for blk in s.get("body_blocks", []) or []:
            k = blk.get("kind")
            if k == "table":
                tables += 1
                for row in blk.get("rows", []) or []:
                    for cell in row:
                        for r in cell:
                            blob_parts.append(_norm(r.get("text", "")))
                continue
            if k == "list":
                for item in blk.get("items", []) or []:
                    blob_parts.append(_norm(" ".join(r.get("text", "") for r in item)))
                continue
            if k == "equation":
                blob_parts.append(_norm(blk.get("formula", "")))
                continue
            t = blk.get("text") or " ".join(
                r.get("text", "") for r in blk.get("runs", []) or [])
            blob_parts.append(_norm(t))
        for p in s.get("body_paragraphs", []) or []:
            blob_parts.append(_norm(p))
    return " || ".join(b for b in blob_parts if b), headings, tables


# ── perception observations (descriptive, NOT pass/fail) ───────────────────

def observe(blocks: list[dict], content_ir: dict | None) -> list[dict]:
    obs: list[dict] = []
    paras = [b for b in blocks if b["kind"] == "para" and b["text"]]
    tables = [b for b in blocks if b["kind"] == "table"]

    first_heading = next((i for i, b in enumerate(blocks)
                          if b["kind"] == "para" and b["is_heading"]), None)
    if first_heading is not None:
        pre = sum(1 for b in blocks[:first_heading]
                  if b["kind"] == "para" and b["text"])
        obs.append({"signal": "front_matter_paragraphs", "value": pre,
                    "note": f"{pre} text paragraph(s) precede the first Heading."})

    dims = ", ".join((f"{t['rows']}×{t['cols']}" if t.get("cols")
                      else f"{t['rows']} rows") for t in tables)
    obs.append({"signal": "tables_in_output", "value": len(tables),
                "note": (f"{len(tables)} table(s): {dims}" if tables else "no tables")})

    if content_ir is not None:
        blob, headings, n_src_tables = content_corpus(content_ir)
        # Skip officecli render markers for math (e.g. "[Equation] …"): the visible
        # text is a placeholder, the real content is OMML, so it isn't "foreign".
        foreign = [b for b in paras
                   if len(b["text"]) >= 12 and not b["text"].startswith("[")
                   and _is_foreign(b["text"], blob)]
        if foreign:
            ex = " | ".join("“" + b["text"][:48] + "”" for b in foreign[:5])
            obs.append({
                "signal": "foreign_text_paragraphs",
                "value": len(foreign),
                "severity": "high",
                "note": (f"{len(foreign)} paragraph(s) carry text NOT found in the "
                         f"source content — likely leaked/duplicated template content. "
                         f"Examples: " + ex),
            })
        if len(tables) != n_src_tables:
            obs.append({
                "signal": "table_count_mismatch", "value": len(tables),
                "severity": "high",
                "note": (f"output has {len(tables)} table(s) but source content has "
                         f"{n_src_tables} — extra tables are leaked template tables."),
            })
        extra = [b["text"] for b in paras if b["is_heading"]
                 and _norm(b["text"]) not in headings]
        if extra:
            ex = " | ".join("“" + e[:40] + "”" for e in extra[:5])
            obs.append({"signal": "headings_not_in_source", "value": len(extra),
                        "severity": "high",
                        "note": "Heading-styled text not in source: " + ex})
    return obs


# ── render the compact view ────────────────────────────────────────────────

def render_view(blocks: list[dict], max_text: int = 70) -> str:
    lines: list[str] = []
    n = 0
    for b in blocks:
        n += 1
        if b["kind"] == "table":
            dim = f"{b['rows']}×{b['cols']}" if b.get("cols") else f"{b['rows']} rows"
            lines.append(f"{n:>3}  [TABLE {dim}]")
            continue
        if not b["text"]:
            lines.append(f"{n:>3}  [{b['style']}·empty]")
            continue
        tag = b["style"]
        if b["is_heading"]:
            tag = f"#{b['style'][-1]} {b['style']}"
        elif b["is_toc"]:
            tag = f"TOC·{b['style']}"
        al = f"·{b['align']}" if b.get("align") else ""
        txt = b["text"][:max_text] + ("…" if len(b["text"]) > max_text else "")
        lines.append(f"{n:>3}  [{tag}{al}] {txt}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="Reading-order readback of a built DOCX (officecli-only perception step).")
    ap.add_argument("docx")
    ap.add_argument("--content", help="content.ir.json — enables foreign-text / "
                                       "table-count / heading observations")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--max-text", type=int, default=70)
    args = ap.parse_args()

    if not os.path.exists(args.docx):
        print(f"ERROR: not found: {args.docx}", file=sys.stderr)
        sys.exit(2)

    content_ir = None
    if args.content:
        with open(args.content, encoding="utf-8") as f:
            content_ir = json.load(f)

    blocks = read_blocks(args.docx)
    obs = observe(blocks, content_ir)

    if args.json:
        print(json.dumps({"blocks": blocks, "observations": obs},
                         ensure_ascii=False, indent=2))
        return

    print(f"═══ READBACK: {args.docx} ({len(blocks)} blocks) ═══")
    print(render_view(blocks, args.max_text))
    print()
    print("═══ OBSERVATIONS (read, then compare to what you intended) ═══")
    if not obs:
        print("  (none)")
    for o in obs:
        sev = o.get("severity", "info").upper()
        print(f"  [{sev}] {o['signal']}={o['value']}: {o['note']}")


if __name__ == "__main__":
    main()
