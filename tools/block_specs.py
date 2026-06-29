#!/usr/bin/env python3
"""block_specs.py — the BlockSpec registry (axis B: content-elements).

ONE place per block kind, holding all three operations that used to be scattered
across markdown-parser.py and planner.py:

    parse(lines, i)  -> (action, payload, next_i) | None   # reader
    emit(block, ctx) -> None                                # writer (officecli ops)
    count(block)     -> int                                 # validator para-count

Adding a content element (figure, footnote, citation, cross-ref…) is now ONE new
BlockSpec here — markdown-parser.py and planner.py iterate this registry and need
no edits. This is the Expression-Problem fix from adaptation_research.md §1
(BlockSpec self-describing, ProseMirror-style co-location).

Unknown kinds degrade to a paragraph at emit AND count (B3 generic escape hatch),
so a forward/extra block kind never crashes or miscounts the build.

Both processes import this module, so the three operations stay in lock-step.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from inline import tokenize_inline, strip_inline, parse_table_cells, RE_SPAN

# ── block-level patterns (parse side) ──────────────────────────────────────
RE_HEADINGLIKE = re.compile(r'^#{4,6}\s+(.+)$')          # #### / ##### / ######
RE_NUMBERED = re.compile(r'^\d+(\.\d+)*\.?\s')           # 1.1.1  / 2.1.  etc.
RE_TABLE_ROW = re.compile(r'^\s*\|.*\|\s*$')
RE_TABLE_SEP = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$')
RE_CODE_FENCE = re.compile(r'^\s*(```|~~~)\s*([A-Za-z0-9_+-]*)\s*$')
RE_THEMATIC = re.compile(r'^\s*([-*_])\1{2,}\s*$')       # --- / *** / ___ alone
RE_BULLET = re.compile(r'^\s*[-*+]\s+(.*)$')             # - item / * item / + item
RE_ORDERED = re.compile(r'^\s*\d+[.)]\s+(.*)$')          # 1. item / 2) item
RE_BLOCKQUOTE = re.compile(r'^\s*>\s?(.*)$')
RE_MATH_FENCE = re.compile(r'^\s*\$\$')                  # $$ display-math line
RE_TAG = re.compile(r'\\tag\{[^}]*\}')                   # \tag{1} — not auto-numbered
CALLOUT_LABELS = {"important", "definition", "warning", "example",
                  "note", "tip", "caution", "remark", "theorem", "lemma"}

# parse-handler actions
A_BLOCK = "flush_block"   # flush buffered text, then append payload as a block
A_SKIP = "skip_flush"     # flush buffered text, drop this line (thematic break)
A_BUFFER = "buffer"       # append payload (a string) to the text buffer; no flush
A_ADVANCE = "advance"     # consume lines as nothing; no flush, no buffer (degenerate table)


# ── paragraph / callout construction (the paragraph spec's "parse") ────────

def paragraph_block(para: str) -> dict:
    """Build a paragraph/callout block; heading-like single lines become bold.
    Used by the reader's text flush (paragraphs accumulate across blank lines)."""
    single = para.replace("\n", " ").strip()
    m = RE_HEADINGLIKE.match(para.strip())
    if m:
        runs = tokenize_inline(m.group(1).strip(), base_bold=True)
        return {"kind": "paragraph", "runs": runs, "text": strip_inline(m.group(1).strip()),
                "heading_like": True}
    full = RE_SPAN.fullmatch(para.strip())
    if full and (full.group(1) is not None or full.group(2) is not None):
        inner = (full.group(1) or full.group(2)).strip()
        if RE_NUMBERED.match(inner):
            return {"kind": "paragraph",
                    "runs": [{"text": inner, "bold": True, "italic": True}],
                    "text": inner, "heading_like": True}
    runs = tokenize_inline(single)
    if runs and runs[0].get("bold") and runs[0]["text"].strip().lower() in CALLOUT_LABELS:
        return {"kind": "callout", "label": runs[0]["text"].strip(),
                "runs": runs, "text": strip_inline(single)}
    return {"kind": "paragraph", "runs": runs, "text": strip_inline(single)}


# ── per-kind parse handlers: (lines, i) -> (action, payload, next_i) | None ──

def _parse_code(lines, i):
    m = RE_CODE_FENCE.match(lines[i])
    if not m:
        return None
    lang = m.group(2) or ""
    n = len(lines)
    j = i + 1
    code_lines = []
    while j < n and not RE_CODE_FENCE.match(lines[j]):
        code_lines.append(lines[j])
        j += 1
    block = {"kind": "code", "lang": lang, "lines": code_lines}
    return (A_BLOCK, block, j + 1 if j < n else j)


def _parse_math(lines, i):
    line = lines[i]
    if not RE_MATH_FENCE.match(line):
        return None
    n = len(lines)
    buf = [line]
    j = i
    if line.count("$$") < 2:
        j = i + 1
        while j < n:
            buf.append(lines[j])
            if "$$" in lines[j]:
                break
            j += 1
    raw = "\n".join(buf)
    formula = raw.replace("$$", " ")
    formula = RE_TAG.sub("", formula).strip()
    if formula:
        return (A_BLOCK, {"kind": "equation", "formula": formula, "mode": "display"}, j + 1)
    return (A_SKIP, None, j + 1)


def _parse_thematic(lines, i):
    if RE_THEMATIC.match(lines[i]):
        return (A_SKIP, None, i + 1)
    return None


def _parse_list(lines, i):
    if not (RE_BULLET.match(lines[i]) or RE_ORDERED.match(lines[i])):
        return None
    ordered = RE_ORDERED.match(lines[i]) is not None
    n = len(lines)
    items = []
    j = i
    while j < n:
        mb, mo = RE_BULLET.match(lines[j]), RE_ORDERED.match(lines[j])
        if mo:
            items.append(tokenize_inline(mo.group(1).strip()))
        elif mb:
            items.append(tokenize_inline(mb.group(1).strip()))
        else:
            break
        j += 1
    return (A_BLOCK, {"kind": "list", "ordered": ordered, "items": items}, j)


def _parse_table(lines, i):
    if not RE_TABLE_ROW.match(lines[i]):
        return None
    n = len(lines)
    j = i
    rows_raw = []
    while j < n and RE_TABLE_ROW.match(lines[j]):
        if not RE_TABLE_SEP.match(lines[j]):
            rows_raw.append(parse_table_cells(lines[j]))
        j += 1
    if not rows_raw:
        # all-separator region: consumed but yields no block AND no text flush
        # (matches the original parser, which did `i = j; continue`).
        return (A_ADVANCE, None, j) if j > i else None
    ncols = max(len(r) for r in rows_raw)
    rows = [[tokenize_inline(c, base_bold=False) for c in (r + [""] * (ncols - len(r)))]
            for r in rows_raw]
    return (A_BLOCK, {"kind": "table", "ncols": ncols, "header": len(rows) > 1, "rows": rows}, j)


def _parse_blockquote(lines, i):
    mq = RE_BLOCKQUOTE.match(lines[i])
    if mq:
        return (A_BUFFER, mq.group(1), i + 1)
    return None


# Ordered = priority. First handler that returns non-None wins; if none match,
# the reader buffers the raw line (default paragraph text accumulation).
BLOCK_PARSERS: list[Callable] = [
    _parse_code, _parse_math, _parse_thematic, _parse_list, _parse_table, _parse_blockquote,
]


# ── formula normalization (shared by inline + display equation emit) ────────

# officecli's KaTeX→OMML converter cannot parse `\left…`/`\right…` delimiters
# when they wrap subscript/accent terms (e.g. `\left[ \hat{y}_i \right]` →
# "Subscript→Run cast" error). Dropping ONLY the sizing wrappers and keeping the
# bare delimiter is meaning-preserving (it just makes brackets non-stretchy), so
# the equation renders instead of forcing a hand-edit of the content. Verified
# against the report's loss/objective/Shapley equations.
_LEFT_RIGHT = [
    (r"\left[", "["), (r"\right]", "]"),
    (r"\left(", "("), (r"\right)", ")"),
    (r"\left\{", r"\{"), (r"\right\}", r"\}"),
    (r"\left|", "|"), (r"\right|", "|"),
    (r"\left.", ""), (r"\right.", ""),
]


def normalize_formula(formula: str) -> str:
    """Make a LaTeX formula safe for officecli's converter without changing its
    mathematical meaning (currently: strip `\\left`/`\\right` sizing wrappers)."""
    for a, b in _LEFT_RIGHT:
        formula = formula.replace(a, b)
    return formula


# ── emit side: officecli ops per block kind ────────────────────────────────

@dataclass
class EmitCtx:
    """Context handed to every block emit handler. Wraps the planner's program
    list + discovered body props + run emission, so emit handlers carry no
    planner-internal closures.

    `run_props` are RUN-level defaults (e.g. body font/size) applied to every
    body run. They matter when the body paragraphs ride on a style that does
    NOT define size/font (a style-less template): a run inherits from its STYLE,
    not from the paragraph mark, so size must be set on the run itself. Empty by
    default ⇒ runs inherit from their named style (parity for styled templates).
    Heading runs pass `run_props={}` so they keep inheriting from the heading
    style."""
    program: list
    body_props: dict
    run_props: dict = field(default_factory=dict)

    def emit_runs(self, parent_path: str, runs, mono: bool = False,
                  run_props: dict | None = None):
        base = self.run_props if run_props is None else run_props
        if isinstance(runs, str):
            runs = [{"text": runs}] if runs else []
        for r in runs:
            text = r.get("text", "")
            if not text:
                continue
            # Inline math → an inline equation anchored at the current paragraph,
            # so `$...$` renders as real OMML instead of literal LaTeX text.
            if r.get("math"):
                self.program.append({"command": "add", "parent": parent_path,
                                     "type": "equation",
                                     "props": {"formula": normalize_formula(text),
                                               "mode": "inline"}})
                continue
            props = {**base, "text": text}
            if mono:
                props["font.latin"] = "Courier New"
            else:
                if r.get("bold"):
                    props["bold"] = True
                if r.get("italic"):
                    props["italic"] = True
                if r.get("sup"):
                    props["vertAlign"] = "superscript"
                elif r.get("sub"):
                    props["vertAlign"] = "subscript"
            self.program.append({"command": "add", "parent": parent_path,
                                 "type": "r", "props": props})

    def add_paragraph(self, props: dict, runs, mono: bool = False,
                      run_props: dict | None = None):
        self.program.append({"command": "add", "parent": "/body", "type": "p",
                             "props": dict(props)})
        self.emit_runs("/body/p[last()]", runs, mono=mono, run_props=run_props)


def _emit_paragraph(block, ctx: EmitCtx):
    ctx.add_paragraph(ctx.body_props, block.get("runs") or block.get("text", ""))


def _emit_table(block, ctx: EmitCtx):
    ncols = max(1, block.get("ncols", 1))
    col_w = max(1200, int(9000 / ncols))
    col_widths = ",".join([str(col_w)] * ncols)
    ctx.program.append({"command": "add", "parent": "/body", "type": "table",
                        "props": {"colWidths": col_widths}})
    for ri, row in enumerate(block.get("rows", [])):
        if ri > 0:
            ctx.program.append({"command": "add", "parent": "/body/tbl[last()]",
                                "type": "row", "props": {}})
        for ci in range(ncols):
            cell = row[ci] if ci < len(row) else []
            ctx.emit_runs(f"/body/tbl[last()]/tr[last()]/tc[{ci + 1}]/p[last()]", cell)


def _emit_code(block, ctx: EmitCtx):
    for line in block.get("lines", []):
        ctx.add_paragraph(ctx.body_props, [{"text": line}] if line else [{"text": " "}], mono=True)


def _emit_equation(block, ctx: EmitCtx):
    mode = block.get("mode", "display")
    ctx.program.append({"command": "add", "parent": "/body", "type": "equation",
                        "props": {"formula": normalize_formula(block.get("formula", "")),
                                  "mode": mode}})


def _emit_list(block, ctx: EmitCtx):
    list_style = "ordered" if block.get("ordered") else "bullet"
    for item in block.get("items", []):
        ctx.add_paragraph({**ctx.body_props, "listStyle": list_style}, item)


def _emit_callout(block, ctx: EmitCtx):
    ctx.add_paragraph({**ctx.body_props, "leftIndent": "360"}, block.get("runs", []))


# ── count side: number of `add p` ops a block yields (validator S7 / para_count) ──

def _count_one(block):       # paragraph, callout
    return 1


def _count_list(block):
    return len(block.get("items", []))


def _count_code(block):
    return len(block.get("lines", []))


def _count_zero(block):      # table, equation — emit no body `add p`
    return 0


@dataclass
class BlockSpec:
    kind: str
    emit: Callable[[dict, EmitCtx], None]
    count: Callable[[dict], int]


# The single source of truth. Add a row here to support a new element.
BLOCK_SPECS: list[BlockSpec] = [
    BlockSpec("paragraph", _emit_paragraph, _count_one),
    BlockSpec("callout",   _emit_callout,   _count_one),
    BlockSpec("list",      _emit_list,      _count_list),
    BlockSpec("code",      _emit_code,      _count_code),
    BlockSpec("table",     _emit_table,     _count_zero),
    BlockSpec("equation",  _emit_equation,  _count_zero),
]
_BY_KIND = {s.kind: s for s in BLOCK_SPECS}

# B3 escape hatch: an unknown/forward block kind degrades to a paragraph at BOTH
# emit and count, so the two stay consistent and the build never breaks.
_DEFAULT = BlockSpec("paragraph", _emit_paragraph, _count_one)


def emit_block(block: dict, ctx: EmitCtx) -> None:
    _BY_KIND.get(block.get("kind"), _DEFAULT).emit(block, ctx)


def count_block(block: dict) -> int:
    return _BY_KIND.get(block.get("kind"), _DEFAULT).count(block)
