# Review: Architecture Restructure for OpenCode Pipeline

## 1. Role of Root-Level MD Files

### Current problem

`AGENTS.md`, `CONTENT_RULES.md`, `STRUCTURAL_SPEC.md` sit in the repo root.
OpenCode only loads from `.opencode/agents/` and `.opencode/skills/`.
These files are **static documentation** — the LLM won't discover them unless explicitly told.

| Root File | Content | What should happen |
|-----------|---------|-------------------|
| `AGENTS.md` | Agent constraints (determinism, SDT migration, skills required) | **Redundant** — already encoded in `agents/docgen-orchestrator.md` and skill files. Should be deleted or consolidated. |
| `CONTENT_RULES.md` | Verbatim extraction rules | **Duplicated** — `docgen-workflow/skills.md` Step 4 already has the same rules. Should become a **reference doc** at `.opencode/skills/docgen-workflow/references/content-rules.md` |
| `STRUCTURAL_SPEC.md` | Template-specific SDT→section mapping | **Should not exist as a standalone file** — this is per-template config that belongs in `manifests/<id>.struct-spec.json` alongside the manifest |

### Recommendation: Clean up

1. **Delete `AGENTS.md`** — its content is already in the agent+skill definitions
2. **Move `CONTENT_RULES.md`** → `.opencode/skills/docgen-workflow/references/content-rules.md` (so the skill's Step 4 can reference it directly)
3. **Convert `STRUCTURAL_SPEC.md`** → `manifests/format_template.struct-spec.json` (structured data, not prose)

---

## 2. Concrete Improvement Plan

### 2a. Template-specific config should be structured, not prose

Replace `STRUCTURAL_SPEC.md` with:
```
manifests/
  format_template.manifest.json   (already exists or should)
  format_template.struct-spec.json  (NEW — section registry)
```

`struct-spec.json` schema:
```json
{
  "template_id": "format_template",
  "sections": [
    { "tag": "gioi_thieu_body", "mode": "replace", "source": "noidung.md#gioi-thieu" },
    { "tag": "chuong1_heading", "mode": "replace", "source": "noidung.md#chuong-1-heading" },
    { "tag": "chuong1_tamquantrong_body", "mode": "replace", "source": "noidung.md#chuong-1-tam-quan-trong" },
    { "tag": "tlthamkhao_list", "mode": "replace", "source": "noidung.md#tai-lieu-tham-khao" }
  ],
  "preserve": ["toc", "danh-muc-hinh", "cover-page", "header", "footer"],
  "post_process": ["officecli refresh"]
}
```

### 2b. Phase 0 automation

The "human-only" Phase 0 steps should be converted to either:
- A **bash script** the LLM can run (e.g., `scripts/onboard-template.sh`)
- A **new skill** `template-onboarding` that guides the LLM through audit→classify→registry

---

## 3. Summary of Files to Change

| Action | File |
|--------|------|
| DELETE | `AGENTS.md` (content redundant with agent+skills) |
| MOVE | `CONTENT_RULES.md` → `.opencode/skills/docgen-workflow/references/content-rules.md` |
| CONVERT | `STRUCTURAL_SPEC.md` → `manifests/format_template.struct-spec.json` |
| AMEND | `.opencode/skills/docgen-workflow/SKILL.md` — add Step 5b (dump/batch fallback), Step 6b (refresh), expand validation |
| AMEND | `.opencode/skills/docgen-workflow/SKILL.md` — Step 4 reference content-rules.md instead of duplicating |
| CREATE | `.opencode/skills/docx-template/references/section-registry.md` — section classification guide |
| CREATE | `manifests/format_template.struct-spec.json` — structured section registry |

---

## 4. Verification

After restructuring:
1. `opencode.json` still loads `docgen-orchestrator` as default agent
2. Agent's `skills:` list still references `docgen-workflow`, `officecli`, `manifest`
3. `docgen-workflow/skills.md` Step 4 reads from `references/content-rules.md` (not inline or from root)
4. No dangling imports — all references resolve to `.opencode/` paths
5. Run a test generation to verify pipeline still works end-to-end
