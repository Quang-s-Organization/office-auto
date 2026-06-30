#!/usr/bin/env python3
"""profile_synth.py — synthesize a genre OVERLAY profile from _base at runtime.

WHY THIS EXISTS
---------------
The pipeline adapts to a document genre through a `profiles/<id>.json` file
(role vocabulary + keyword rules + placement). The design assumed those files
are hand-authored ahead of time — so when the incoming document is a genre with
NO matching profile, the only thing on disk is `_base.json`, which is an
ABSTRACT parent ("This file is NOT used directly"): empty keyword_rules, empty
front_matter handling. Running on it directly silently mis-handles the document
(every heading collapses to `generic`, the template's placeholder front matter
survives, etc. — see docs/research-adaptation-gaps-2026-06-26.md).

This tool closes that gap deterministically: given the template IR and the
content's heading tree, it REASONS about the genre (which canonical sections are
present, whether the content carries its own front matter) and emits an overlay
profile that `extends _base` — exactly the layering the resolver already
supports. The output is a *candidate*: it is schema-valid and immediately
usable by the pipeline, and an LLM may further refine it (add genre-specific
roles, fix a placement) before use. Either way `contracts.resolve_profile`
validates the result, so a bad synthesis can never reach the planner.

It is the deterministic floor of the user's idea — "from _base, reason about the
template's semantics and produce a specific profile" — without requiring a model
to be online for the common cases.

Usage:
    python3 tools/profile_synth.py \
        --content content.ir.json \
        --template-ir .cache/template.ir.json \
        --id auto-paper \
        --out profiles/auto-paper.json
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contracts
import capabilities


# ── genre signal table ──────────────────────────────────────────────
# Each signal: a role, the heading surface forms that imply it, and (for roles
# NOT already in _base) the logical placement to add. `base=True` ⇒ the role and
# its role_to_logical already live in _base; we only contribute keyword_rules.
# Order matters: more specific roles first so keyword priority resolves right.
_SIGNALS = [
    # role,                  base,  keywords,                                                  section,        toc
    ("competing_interests",  False, ["COMPETING INTEREST", "CONFLICT OF INTEREST", "DECLARATION"], "BackMatter",  False),
    ("ethics",               False, ["ETHICS", "ETHICAL", "CONSENT", "IRB"],                    "BackMatter",   False),
    ("acknowledgments",      False, ["ACKNOWLEDG", "FUNDING"],                                  "BackMatter",   False),
    ("references",           True,  ["REFERENCES", "BIBLIOGRAPHY", "WORKS CITED"],              None,           None),
    ("appendix",             True,  ["APPENDIX", "SUPPLEMENT", "ANNEX"],                        None,           None),
    ("abstract",             True,  ["ABSTRACT", "TÓM TẮT", "SUMMARY"],                         None,           None),
    ("introduction",         False, ["INTRODUCTION", "GIỚI THIỆU", "MỞ ĐẦU"],                   "Introduction", True),
    ("literature_review",    True,  ["RELATED WORK", "BACKGROUND", "LITERATURE", "TỔNG QUAN",
                                     "ARCHITECTURE", "ENCODER", "MECHANISM", "TRANSFORMER", "ATTENTION"], None, None),
    ("methodology",          True,  ["METHOD", "PHƯƠNG PHÁP", "TRAINING", "AUGMENTATION",
                                     "STRATEGIES", "LEARNING", "LOSS", "MODEL"],                None,           None),
    ("results",              True,  ["RESULT", "EXPERIMENT", "EVALUATION", "KẾT QUẢ",
                                     "DATASET", "METRIC"],                                      None,           None),
    ("discussion",           True,  ["DISCUSSION", "BÀN LUẬN", "ANALYSIS"],                     None,           None),
    ("conclusion",           True,  ["CONCLUSION", "FUTURE", "KẾT LUẬN"],                       None,           None),
]

_ROLE_DESCRIPTIONS = {
    "competing_interests": "Competing / conflict of interest statement.",
    "ethics":              "Ethics approval / consent statement.",
    "acknowledgments":     "Funding and acknowledgments.",
    "introduction":        "Problem statement, motivation, contributions.",
}

_LOGICAL_DEFAULTS = {"presentation": "FROM_LEVEL", "outline_level": "FROM_LEVEL"}


def _iter_titles(tree: list[dict]):
    for n in tree:
        yield n.get("title", "")
        yield from _iter_titles(n.get("children", []))


# Abstract/Keywords surface forms (the hallmark of a self-contained paper's front
# matter). `từ kho` prefix covers both "từ khóa" and "từ khoá" diacritic variants.
_FM_MARKER = re.compile(r"(abstract|keywords?|tóm tắt|từ kho)", re.IGNORECASE)
# An author email — language-agnostic signal that a section is a title/author
# block, which the template's cover already provides (so it would duplicate).
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _section_texts(sec: dict) -> list[str]:
    out = list(sec.get("body_paragraphs", []) or [])
    for blk in sec.get("body_blocks", []) or []:
        t = blk.get("text") or " ".join(
            r.get("text", "") for r in blk.get("runs", []) or [])
        out.append(t)
    return out


def _content_has_front_matter(content_ir: dict) -> bool:
    """True when the document carries its own title/author/abstract block (so the
    template's placeholder cover must be REPLACED, not preserved, or it duplicates).

    Two independent signals — either suffices:
      (A) an Abstract/Keywords/Tóm tắt heading among the TOP-LEVEL sections. The
          previous version only scanned the FIRST section's BODY, so it missed the
          common layout where the title/author block is section 1 and "Tóm tắt" /
          "Abstract" are their OWN H1 headings (the case that shipped a duplicated
          AXKI cover — docs/report-format-diagnosis-2026-06-27-run2.md).
      (B) the first top-level section reads as a title/author block — its body
          carries author emails, or opens a paragraph with an Abstract/Keywords
          marker. (Email rarely appears in a bare thesis-chapter opening, so this
          does not mis-fire `replace` on genuine chapters.)
    """
    secs = content_ir.get("sections", [])
    if not secs:
        return False
    for s in secs:                                            # (A)
        if s.get("level", 1) == 1 and _FM_MARKER.search(s.get("title", "") or ""):
            return True
    first = secs[0]                                           # (B)
    if first.get("level", 1) != 1:
        return False
    return any(_EMAIL.search(t or "") or _FM_MARKER.match((t or "").strip())
               for t in _section_texts(first))


def _template_has_front_matter(template_ir: dict) -> bool:
    """True when the template has placeholder paragraphs before its first heading."""
    seq = template_ir.get("body_sequence", [])
    for p in seq:
        if p.get("is_heading"):
            return False
        if p.get("has_text"):
            return True
    return False


def synthesize(content_ir: dict, template_ir: dict, profile_id: str,
               base_id: str = "_base") -> dict:
    titles_u = [t.upper() for t in _iter_titles(content_ir.get("document_tree", []))]
    blob = " || ".join(titles_u)

    active = []
    for role, base, keywords, section, toc in _SIGNALS:
        if any(kw in blob for kw in keywords):
            active.append((role, base, keywords, section, toc))

    keyword_rules = [{"role": r, "any": kws} for (r, _b, kws, _s, _t) in active]
    new_roles = [r for (r, base, *_rest) in active if not base]
    role_descriptions = {r: _ROLE_DESCRIPTIONS[r] for r in new_roles
                         if r in _ROLE_DESCRIPTIONS}
    role_to_logical = {
        r: {"section": s, "intent": "replace", "toc": bool(t), **_LOGICAL_DEFAULTS}
        for (r, base, _kw, s, t) in active if not base and s
    }

    fm_strategy = ("replace"
                   if _content_has_front_matter(content_ir)
                   and _template_has_front_matter(template_ir)
                   else "preserve")

    feats = capabilities.detect_features(content_ir)
    caps = {capabilities.FEATURE_CAPABILITY.get(f, f): True for f in feats}

    profile: dict = {
        "id": profile_id,
        "extends": base_id,
        "description": (f"Auto-synthesized overlay for '{profile_id}' "
                        f"(profile_synth.py). Detected roles: "
                        f"{', '.join(r for r, *_ in active) or 'none'}. "
                        f"front_matter_strategy={fm_strategy}. Review/refine before reuse."),
        "front_matter_strategy": fm_strategy,
        "keyword_rules": keyword_rules,
    }
    if new_roles:
        profile["role_vocabulary"] = new_roles
    if role_descriptions:
        profile["role_descriptions"] = role_descriptions
    if role_to_logical:
        profile["role_to_logical"] = role_to_logical
    if caps:
        profile["capabilities"] = caps
    return profile


def main():
    ap = argparse.ArgumentParser(description="Synthesize a genre overlay profile from _base.")
    ap.add_argument("--content", required=True, help="content.ir.json (has document_tree)")
    ap.add_argument("--template-ir", required=True, help=".cache/template.ir.json")
    ap.add_argument("--id", required=True, help="new profile id (also the filename stem)")
    ap.add_argument("--base", default="_base", help="parent profile id to extend (default _base)")
    ap.add_argument("--out", "-o", help="output path (default profiles/<id>.json)")
    args = ap.parse_args()

    content_ir = contracts.load_and_validate(args.content, "content.ir", "content IR")
    with open(args.template_ir, encoding="utf-8") as f:
        template_ir = json.load(f)

    profile = synthesize(content_ir, template_ir, args.id, base_id=args.base)

    out_path = args.out or os.path.join("profiles", f"{args.id}.json")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(f"[synth] wrote {out_path}: extends={args.base}, "
          f"{len(profile['keyword_rules'])} keyword rules, "
          f"front_matter_strategy={profile['front_matter_strategy']}", file=sys.stderr)

    # Resolve+validate the merged profile so a bad synthesis fails loudly here,
    # not three tiers downstream.
    resolved = contracts.resolve_profile(out_path)
    print(f"[synth] validated: resolved '{resolved.get('id')}' "
          f"({len(resolved.get('role_vocabulary', []))} roles, "
          f"{len(resolved.get('keyword_rules', []))} rules)", file=sys.stderr)


if __name__ == "__main__":
    main()
