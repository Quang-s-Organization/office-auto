#!/usr/bin/env python3
"""contracts.py — load-time JSON-Schema validation + profile resolution.

Phase 1 (C1+A1) of adaptation_research.md. Two jobs:

  1. validate(data, name)  — check an IR/profile against schemas/<name>.schema.json
     so a malformed input fails LOUDLY at the boundary instead of silently
     producing wrong DOCX downstream.
  2. resolve_profile(path) — load a profile, merge any `extends` overlay chain
     onto its base (Phase 3 layering), strip `//` human-comment keys, and
     validate the RESOLVED profile. Profiles with no `extends` just get
     comment-stripped + validated.

No new third-party dep beyond `jsonschema` (already present). Import-safe: if
jsonschema is unavailable, validation degrades to a no-op with a stderr note so
the pipeline never hard-breaks on the contract layer alone.
"""

from __future__ import annotations
import json
import os
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(os.path.dirname(_HERE), "schemas")

try:
    import jsonschema  # type: ignore
    _HAVE_JSONSCHEMA = True
except Exception:  # pragma: no cover - environment without jsonschema
    _HAVE_JSONSCHEMA = False

_SCHEMA_CACHE: dict[str, dict] = {}


class ContractError(Exception):
    """Raised when data violates its schema."""


def _load_schema(name: str) -> dict | None:
    if name in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[name]
    path = os.path.join(_SCHEMA_DIR, f"{name}.schema.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        schema = json.load(f)
    _SCHEMA_CACHE[name] = schema
    return schema


def validate(data: Any, name: str, *, source: str = "<data>") -> Any:
    """Validate `data` against schemas/<name>.schema.json. Returns `data`.

    Raises ContractError with a short, actionable message on the first failure.
    A no-op (returns data) if jsonschema or the schema file is absent.
    """
    if not _HAVE_JSONSCHEMA:
        print("[contract] note: jsonschema unavailable; skipping validation",
              file=sys.stderr)
        return data
    schema = _load_schema(name)
    if schema is None:
        return data
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:  # type: ignore[attr-defined]
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        raise ContractError(
            f"{source} violates '{name}' contract at {loc}: {e.message}"
        ) from None
    return data


def load_and_validate(path: str, name: str, label: str | None = None) -> dict:
    """Load a JSON file and validate it. Exits(1) with a clear message on error."""
    label = label or name
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[contract] ERROR: cannot load {label}: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        validate(data, name, source=path)
    except ContractError as e:
        print(f"[contract] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    return data


# ── profile resolution (layering: `extends` + role_overrides) ──────────────

def _strip_comments(d: dict) -> dict:
    """Drop human-comment keys (those starting with '//')."""
    return {k: v for k, v in d.items() if not (isinstance(k, str) and k.startswith("//"))}


def _merge_profile(base: dict, overlay: dict) -> dict:
    """Merge a child overlay onto a resolved parent. Deltas win; lists union
    (overlay keeps priority for keyword rules by PREPENDING extras)."""
    out = dict(base)
    # scalar / identity fields: overlay wins when present
    for k in ("id", "description", "strategy", "default_role"):
        if k in overlay:
            out[k] = overlay[k]
    # role_vocabulary: union, base order preserved, new roles appended
    if "role_vocabulary" in overlay:
        seen = list(base.get("role_vocabulary", []))
        for r in overlay["role_vocabulary"]:
            if r not in seen:
                seen.append(r)
        out["role_vocabulary"] = seen
    # role_descriptions / capabilities: dict merge, overlay wins
    for k in ("role_descriptions", "capabilities"):
        if k in base or k in overlay:
            out[k] = {**base.get(k, {}), **overlay.get(k, {})}
    # front_matter_roles: union
    if "front_matter_roles" in overlay:
        out["front_matter_roles"] = list(dict.fromkeys(
            list(base.get("front_matter_roles", [])) + list(overlay["front_matter_roles"])))
    # keyword_rules: overlay's `keyword_rules` replaces; `keyword_rules_extra`
    # prepends (higher priority than inherited rules).
    if "keyword_rules" in overlay:
        out["keyword_rules"] = overlay["keyword_rules"]
    if "keyword_rules_extra" in overlay:
        out["keyword_rules"] = list(overlay["keyword_rules_extra"]) + list(out.get("keyword_rules", []))
    # role_to_logical: dict merge; `role_overrides` merged on top (per-role).
    if "role_to_logical" in base or "role_to_logical" in overlay:
        merged = {**base.get("role_to_logical", {}), **overlay.get("role_to_logical", {})}
        out["role_to_logical"] = merged
    if "role_overrides" in overlay:
        rl = dict(out.get("role_to_logical", {}))
        rl.update(overlay["role_overrides"])
        out["role_to_logical"] = rl
    return out


def resolve_profile(path: str, *, _seen: set[str] | None = None) -> dict:
    """Load a profile and return its fully-resolved, comment-stripped, validated
    form. Follows `extends` (relative to the same directory, by `<id>.json`)."""
    _seen = _seen or set()
    if path in _seen:
        print(f"[contract] ERROR: circular profile extends at {path}", file=sys.stderr)
        sys.exit(1)
    _seen.add(path)
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[contract] ERROR: cannot load profile {path}: {e}", file=sys.stderr)
        sys.exit(1)
    raw = _strip_comments(raw)

    if "extends" in raw:
        parent_id = raw["extends"]
        parent_path = os.path.join(os.path.dirname(path) or ".", f"{parent_id}.json")
        base = resolve_profile(parent_path, _seen=_seen)
        resolved = _merge_profile(base, raw)
        resolved.pop("extends", None)
        resolved.pop("keyword_rules_extra", None)
        resolved.pop("role_overrides", None)
    else:
        resolved = raw

    # the resolved profile must satisfy the (base) profile contract
    try:
        validate(resolved, "profile", source=path)
    except ContractError as e:
        print(f"[contract] ERROR: resolved profile invalid: {e}", file=sys.stderr)
        sys.exit(1)
    return resolved


# ── tiny CLI: `python3 tools/contracts.py <file> <schema-name>` ────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Validate a JSON file against a schema.")
    ap.add_argument("file")
    ap.add_argument("schema", help="schema name (content.ir | profile) or 'profile-resolve'")
    args = ap.parse_args()
    if args.schema == "profile-resolve":
        prof = resolve_profile(args.file)
        print(f"OK: resolved profile '{prof.get('id')}' "
              f"({len(prof.get('role_vocabulary', []))} roles)")
        return
    load_and_validate(args.file, args.schema)
    print(f"OK: {args.file} satisfies '{args.schema}'")


if __name__ == "__main__":
    main()
