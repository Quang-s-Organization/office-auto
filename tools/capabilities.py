#!/usr/bin/env python3
"""capabilities.py — content ⇄ template capability negotiation (adaptation_research.md §5).

"Support the most document types" is really "never break when content and
template don't line up". Content declares the features it USES (tables, math,
code, images…); a profile declares what its matched template CAN render
(`capabilities`). The logical tier negotiates: anything used-but-unsupported is
recorded + warned, and a few concrete degradations are applied (e.g. drop TOC
marking when the template has no table of contents). The build never crashes and
never silently drops content — it degrades on purpose, on the record.

Opt-in: a profile with no `capabilities` block negotiates nothing (parity).
"""

from __future__ import annotations

# content feature → the template capability that renders it faithfully
FEATURE_CAPABILITY = {
    "table": "table",
    "code": "code",
    "equation": "equation",
    "math": "equation",     # inline $…$ also needs equation support
    "image": "image",
    "list": "list",
    "callout": "callout",
}

# how a missing capability degrades (advisory text shown to the user/log)
DEGRADE_NOTE = {
    "table": "tables render as plain paragraphs",
    "code": "code renders as plain monospace paragraphs",
    "equation": "equations/inline math render as raw text",
    "image": "images are dropped (no anchor in template)",
    "list": "list items render as plain paragraphs",
    "callout": "callouts render as indented paragraphs",
}


def detect_features(content_ir: dict) -> set[str]:
    """Which content features the document actually uses."""
    feats: set[str] = set()
    for sec in content_ir.get("sections", []):
        for blk in sec.get("body_blocks", []):
            k = blk.get("kind")
            if k in ("table", "code", "equation", "list", "callout"):
                feats.add(k)
        if sec.get("has_math"):
            feats.add("math")
        if sec.get("has_image"):
            feats.add("image")
    return feats


def negotiate(features: set[str], capabilities: dict) -> list[dict]:
    """Report features the matched template cannot render faithfully.

    A capability is 'supported' when its key is present AND truthy. Unknown
    capability keys default to supported (assume the template can handle a
    feature unless it explicitly opts out) — except features with an explicit
    `false` are flagged."""
    reports: list[dict] = []
    for feat in sorted(features):
        cap_key = FEATURE_CAPABILITY.get(feat, feat)
        if cap_key in capabilities and not capabilities[cap_key]:
            reports.append({
                "feature": feat,
                "capability": cap_key,
                "status": "degraded",
                "note": DEGRADE_NOTE.get(feat, f"{feat} not supported"),
            })
    return reports
