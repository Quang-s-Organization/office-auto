#!/usr/bin/env python3
"""Semantic classifier (v6) — document_tree → semantic.ir.json.

LAYER: Semantic tier (the only tier allowed to be non-deterministic).
It assigns each heading node a `semantic_role` from the active profile's
vocabulary — "what this node *is*", independent of any template style.

Two ways to produce semantic.ir.json:

  1. Deterministic stub (this script, default). Rule-based keyword matching
     against the profile's `keyword_rules` over the heading titles. Adds real
     value for standard Vietnamese headings (references/conclusion/appendix…)
     and is the guaranteed fallback. Runs offline, no model.

  2. LLM (the OpenCode/Qwen agent). For ambiguous or non-standard headings the
     agent may write semantic.ir.json by hand, reading ONLY the heading tree
     (titles + levels + word_count from content.ir.json `document_tree`), never
     the full body. Same schema as below. `--check` validates that file.

Hard rule: semantic_role MUST be in the profile vocabulary. Unknown roles are
clamped to the profile default (never flow downstream). Style/section/paraId do
NOT belong here — that is the deterministic logical/physical tiers' job.

Usage:
    python3 tools/semantic_classifier.py \\
        --content content.ir.json \\
        --profile profiles/vn-thesis.json \\
        --output semantic.ir.json
    python3 tools/semantic_classifier.py --check semantic.ir.json \\
        --profile profiles/vn-thesis.json
"""

from __future__ import annotations
import argparse
import json
import sys

# confidence assigned by the deterministic stub
CONF_KEYWORD = 0.9     # matched a profile keyword rule
CONF_FALLBACK = 0.3    # nothing matched → default role (LLM stage-2 candidate)
LOW_CONF = 0.7         # below this → flagged for lazy stage-2 (heading+summary)


def _load_json(path: str, label: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[semantic] ERROR: cannot load {label}: {e}", file=sys.stderr)
        sys.exit(1)


def _iter_tree(nodes: list[dict]):
    """Yield every node in document_tree, depth-first (document order)."""
    for n in nodes:
        yield n
        yield from _iter_tree(n.get("children", []))


def classify_stub(content_ir: dict, profile: dict) -> list[dict]:
    """Rule-based role assignment from heading titles (deterministic)."""
    rules = profile.get("keyword_rules", [])
    default_role = profile.get("default_role", "generic")
    tree = content_ir.get("document_tree")
    if not tree:
        print("[semantic] ERROR: content IR has no document_tree (re-run the "
              "parser; P0 adds it)", file=sys.stderr)
        sys.exit(1)

    out: list[dict] = []
    for node in _iter_tree(tree):
        title_u = node["title"].upper()
        role = default_role
        evidence = "fallback"
        conf = CONF_FALLBACK
        for rule in rules:
            if any(kw.upper() in title_u for kw in rule.get("any", [])):
                role = rule["role"]
                evidence = "heading"
                conf = CONF_KEYWORD
                break
        out.append({
            "node_id": node["node_id"],
            "semantic_role": role,
            "confidence": conf,
            "evidence": evidence,
        })
    return out


def validate_roles(nodes: list[dict], profile: dict) -> tuple[list[dict], list[str]]:
    """Clamp unknown roles to the profile default; return (clean, warnings)."""
    vocab = set(profile.get("role_vocabulary", []))
    default_role = profile.get("default_role", "generic")
    warnings: list[str] = []
    clean: list[dict] = []
    for n in nodes:
        role = n.get("semantic_role")
        if role not in vocab:
            warnings.append(f"node {n.get('node_id')}: role '{role}' not in "
                            f"profile vocabulary → clamped to '{default_role}'")
            n = {**n, "semantic_role": default_role, "confidence": CONF_FALLBACK,
                 "evidence": "clamped"}
        clean.append(n)
    return clean, warnings


def quality_gate(nodes: list[dict], profile: dict) -> list[str]:
    """Soft warnings (not fatal): high generic ratio / low mean confidence
    suggest the heading set is unusual for this profile → consider the LLM
    path or a different profile."""
    if not nodes:
        return ["no nodes classified"]
    default_role = profile.get("default_role", "generic")
    generic = sum(1 for n in nodes if n["semantic_role"] == default_role)
    mean_conf = sum(n["confidence"] for n in nodes) / len(nodes)
    warns: list[str] = []
    if generic / len(nodes) > 0.6:
        warns.append(f"{generic}/{len(nodes)} nodes are '{default_role}' "
                     f"(>60%): headings may not match profile '{profile.get('id')}'")
    if mean_conf < 0.5:
        warns.append(f"mean confidence {mean_conf:.2f} is low: consider the "
                     f"LLM semantic pass or a different profile")
    return warns


def build_ir(nodes: list[dict], profile: dict, model: str) -> dict:
    low = sum(1 for n in nodes if n["confidence"] < LOW_CONF)
    return {
        "model": model,
        "profile": profile.get("id"),
        "evidence_budget": {
            "heading_only": len(nodes) - low,
            "needs_stage2": low,
        },
        "nodes": nodes,
    }


def main():
    ap = argparse.ArgumentParser(description="Semantic classifier v6 (stub + validator)")
    ap.add_argument("--content", help="content.ir.json (with document_tree)")
    ap.add_argument("--profile", required=True, help="profiles/<id>.json")
    ap.add_argument("--output", "-o", default="semantic.ir.json")
    ap.add_argument("--check", metavar="SEMANTIC_IR",
                    help="validate an existing semantic.ir.json (e.g. LLM-written) "
                         "against the profile vocabulary, rewrite it clamped, and exit")
    args = ap.parse_args()

    profile = _load_json(args.profile, "profile")

    if args.check:
        ir = _load_json(args.check, "semantic IR")
        nodes, warns = validate_roles(ir.get("nodes", []), profile)
        for w in warns:
            print(f"[semantic] WARN: {w}", file=sys.stderr)
        for w in quality_gate(nodes, profile):
            print(f"[semantic] GATE: {w}", file=sys.stderr)
        ir["nodes"] = nodes
        ir["profile"] = profile.get("id")
        with open(args.check, "w", encoding="utf-8") as f:
            json.dump(ir, f, ensure_ascii=False, indent=2)
        print(f"[semantic] checked {args.check}: {len(nodes)} nodes, "
              f"{len(warns)} clamped", file=sys.stderr)
        return

    if not args.content:
        ap.error("--content is required unless --check is used")
    content_ir = _load_json(args.content, "content IR")
    nodes = classify_stub(content_ir, profile)
    nodes, warns = validate_roles(nodes, profile)
    for w in warns:
        print(f"[semantic] WARN: {w}", file=sys.stderr)
    for w in quality_gate(nodes, profile):
        print(f"[semantic] GATE: {w}", file=sys.stderr)

    ir = build_ir(nodes, profile, model="deterministic-stub")
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(ir, f, ensure_ascii=False, indent=2)
    matched = sum(1 for n in nodes if n["evidence"] == "heading")
    print(f"[semantic] Wrote {args.output}: {len(nodes)} nodes "
          f"({matched} keyword-matched, {ir['evidence_budget']['needs_stage2']} "
          f"low-confidence)", file=sys.stderr)


if __name__ == "__main__":
    main()
