#!/usr/bin/env python3
"""Logical mapper (v6) — semantic.ir.json + profile → logical.ir.json.

LAYER: Logical tier (100% deterministic). Translates "what a node *is*"
(semantic_role) into "what template section / outline position it occupies"
using the active profile as DATA. No model, no hardcoded template constants.

Output `logical.ir.json` is a strict superset of the old `intent.json`: it
carries `node_id` + `intent` + `presentation` (so planner.py reads it
unchanged) plus `logical_section`, `outline_level`, `toc`, `resolved_by`.

The one non-trivial bit is the OUTLINE SHIFT. Real body content can start
below the top markdown level (e.g. everything lives under a single preserved
title chapter). We compute `shift = min(level of emitted nodes) - 1` so the
shallowest emitted heading becomes the top presentation tier. This reproduces
the hand-written intent.json behaviour and generalises to other documents.

Usage:
    python3 tools/logical_mapper.py \\
        --semantic semantic.ir.json \\
        --content content.ir.json \\
        --profile profiles/vn-thesis.json \\
        --output logical.ir.json
"""

from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contracts
import capabilities

INTENT_PRESERVE = "preserve"
INTENT_REMOVE = "remove"

# Confidence gate: a preserve-role (front matter the template already provides)
# is honoured ONLY when the classifier is this sure. Preserve means "do not
# re-emit", so a wrong low-confidence preserve silently DROPS real content.
# Below the threshold we demote to the safe default role (which replaces).
# This is the deterministic enforcement the skill cannot guarantee (docs A.1).
TAU_PRESERVE = 0.85

# presentation tier index (after outline shift) → planner presentation vocab
TIER_TO_PRESENTATION = {1: "major_section", 2: "minor_section", 3: "sub_section"}


def _load_json(path: str, label: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[logical] ERROR: cannot load {label}: {e}", file=sys.stderr)
        sys.exit(1)


def _tier_to_presentation(tier: int) -> str:
    tier = max(1, tier)
    return TIER_TO_PRESENTATION.get(tier, "sub_section")


def build_logical(semantic_ir: dict, content_ir: dict, profile: dict) -> dict:
    role_map = profile.get("role_to_logical", {})
    default_role = profile.get("default_role", "generic")
    front_matter_roles = set(profile.get("front_matter_roles", []))
    level_by_tag = {s["tag"]: s["level"] for s in content_ir.get("sections", [])}

    nodes = semantic_ir.get("nodes", [])

    # Resolve role -> logical entry first so we know which nodes are emitted.
    demotions: list[str] = []
    resolved = []
    for n in nodes:
        role = n.get("semantic_role", default_role)
        conf = n.get("confidence")
        entry = role_map.get(role) or role_map.get(default_role, {})
        intent = entry.get("intent", "replace")
        # Confidence gate (deterministic): never preserve front matter on a
        # low-confidence label — demote to the safe default role + replace.
        if (intent == INTENT_PRESERVE and role in front_matter_roles
                and conf is not None and conf < TAU_PRESERVE):
            demotions.append(f"{n['node_id']} ({role} conf={conf:.2f})")
            role = default_role
            entry = role_map.get(default_role, {})
            intent = entry.get("intent", "replace")
        resolved.append((n, role, entry, intent))

    # Outline shift: shallowest EMITTED (non-preserve/remove) heading = tier 1.
    emitted_levels = [
        level_by_tag.get(n["node_id"], 1)
        for (n, _r, _e, intent) in resolved
        if intent not in (INTENT_PRESERVE, INTENT_REMOVE)
        and n["node_id"] in level_by_tag
    ]
    shift = (min(emitted_levels) - 1) if emitted_levels else 0

    for d in demotions:
        print(f"[logical] GATE: demoted low-confidence preserve {d} -> "
              f"'{default_role}'/replace", file=sys.stderr)

    sections = []
    for (n, role, entry, intent) in resolved:
        tag = n["node_id"]
        level = level_by_tag.get(tag, 1)
        tier = level - shift

        pres_cfg = entry.get("presentation", "FROM_LEVEL")
        presentation = (_tier_to_presentation(tier)
                        if pres_cfg == "FROM_LEVEL" else pres_cfg)

        outline_cfg = entry.get("outline_level", "FROM_LEVEL")
        outline_level = (max(1, tier) if outline_cfg == "FROM_LEVEL" else outline_cfg)

        sections.append({
            "node_id": tag,
            "intent": intent,
            "presentation": presentation,
            "logical_section": entry.get("section", "Body"),
            "outline_level": outline_level,
            "toc": entry.get("toc", True),
            "resolved_by": f"role:{role}",
            "confidence": n.get("confidence"),
        })

    out = {
        "profile": profile.get("id"),
        "strategy": profile.get("strategy", "clone"),
        "front_matter_strategy": profile.get("front_matter_strategy", "preserve"),
        "outline_shift": shift,
        "sections": sections,
    }

    # Capability negotiation (§5) — opt-in: only when the profile declares what
    # its matched template can render. No `capabilities` block ⇒ no change.
    caps = profile.get("capabilities")
    if caps:
        feats = capabilities.detect_features(content_ir)
        report = capabilities.negotiate(feats, caps)
        # concrete degradation: a template with no TOC can't carry TOC marks.
        if caps.get("toc") is False:
            for s in sections:
                s["toc"] = False
        for r in report:
            print(f"[logical] CAPABILITY: '{r['feature']}' used but template "
                  f"lacks '{r['capability']}' → {r['note']}", file=sys.stderr)
        out["capability_report"] = report

    return out


def main():
    ap = argparse.ArgumentParser(description="Logical mapper v6")
    ap.add_argument("--semantic", required=True, help="semantic.ir.json")
    ap.add_argument("--content", required=True, help="content.ir.json")
    ap.add_argument("--profile", required=True, help="profiles/<id>.json")
    ap.add_argument("--output", "-o", default="logical.ir.json")
    args = ap.parse_args()

    semantic_ir = _load_json(args.semantic, "semantic IR")
    content_ir = contracts.load_and_validate(args.content, "content.ir", "content IR")
    profile = contracts.resolve_profile(args.profile)

    logical = build_logical(semantic_ir, content_ir, profile)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(logical, f, ensure_ascii=False, indent=2)

    preserved = sum(1 for s in logical["sections"] if s["intent"] == INTENT_PRESERVE)
    emitted = len(logical["sections"]) - preserved
    print(f"[logical] Wrote {args.output}: profile={logical['profile']} "
          f"shift={logical['outline_shift']} "
          f"({emitted} emitted, {preserved} preserved)", file=sys.stderr)


if __name__ == "__main__":
    main()
