# office-auto Pipeline: Bug Analysis, Risk Mitigation & Flexible Document Architecture

## Executive Summary

This report performs a comprehensive forensic analysis of the `office-auto` project (branch `test`) across three axes: (1) confirmed bugs in the current codebase with root-cause explanations and fixes, (2) latent architectural risks that will manifest as the system scales to new document types, and (3) a redesigned, document-type-agnostic pipeline that maximises OfficeCLI's native capabilities before reaching for custom tooling. The central finding is that the current infinite-loop behaviour in OpenCode is caused by a combination of a stale tool-routing assumption in the agent prompt, a missing `opencode.json` at project root, and two deterministic bugs in `binding-planner.ts` that corrupt repeater output. All three are fixable in one commit. The deeper architectural risk — tight coupling between `ContentSchema` and specific template shapes — is the primary blocker to supporting multiple document types flexibly.

***

## Part 1: Confirmed Bugs

### 1.1 Infinite Tool-Call Loop — Root Cause Triage

The OpenCode log shows the agent repeating `codegraph_codegraph_explore [query=office-auto_generate_document]` more than 80 times with thought times of 3–17 ms. This pattern is a textbook **blind tool retry** — the LLM receives no useful result from the tool but has no exit condition, so it retries indefinitely.[^1][^2]

Three contributing factors combine:

**Factor A — Config location mismatch.** The project has `.opencode/config.json` but OpenCode's documented lookup order is `opencode.json` (project root) → `.opencode/config.json`. In some versions the root-level file takes precedence; the agent may have loaded a stale or empty config, meaning the MCP servers (`officecli`, `office-auto`) were never registered, so `office-auto_generate_document` simply did not exist in the tool namespace. The agent then fell back to `codegraph_explore` to "find" the tool — which also returned nothing useful.

**Factor B — `LLAMA_BASE_URL` misconfiguration.** The `office-auto` MCP server is launched with `LLAMA_BASE_URL=http://127.0.0.1:8080`, but the actual serving backend is an sglang endpoint at `https://appresearchpublic83.aiplatform.vcntt.tech/v1`. This means L2 (`normalizer.ts`) will always fail with a connection error, and `runPipeline` returns `{ success: false, error: "Content normalization failed: ..." }`. The agent sees this error and has no explicit handling instruction for it in the agent markdown, so it loops trying to re-invoke the same tool.

**Factor C — No loop-guard in the agent prompt.** The `docgen-orchestrator.md` defines `HARD STOP CONDITIONS` for "Manifest not found" but has no hard stop for repeated tool failures or LLM backend unavailability. Per established agentic system design: *if an agent can loop forever, it will*. Without an explicit iteration budget or no-progress detector, any persistent tool error becomes an infinite loop.[^3][^2][^1]

**Fix:** (1) Ensure `opencode.json` exists at repo root (or that `.opencode/config.json` is the only config file — eliminate ambiguity). (2) Set `LLAMA_BASE_URL` in `.opencode/config.json` to the correct sglang endpoint OR pass it at launch time. (3) Add `HARD STOP: After 3 consecutive failures from the same tool call, stop and report the error to the user. Do NOT retry more than 3 times.` to `docgen-orchestrator.md`.

### 1.2 Repeater Anchor Drift — `binding-planner.ts`

```typescript
// BUG: lastAnchor is reset to the template path, not the newly-inserted node
lastAnchor = `${repeaterSpec.clone_from}`;
```

After the first clone, `lastAnchor` reverts to `repeaterSpec.clone_from` — the path of the **original template paragraph**. Every subsequent item is inserted `after` the same original node, which means:
- Items 2, 3, … are inserted at the same position as item 1 — they stack in **reverse order**.
- In the worst case, if `clone_from` path is stale after the first mutation, OfficeCLI returns an error and the batch fails entirely with `--stop-on-error`.

The master plan explicitly warns about this: *"when cloning repeatedly, the `after` anchor shifts after each insertion"*. The correct strategy is to track the dynamically updated anchor. Two viable approaches:

```typescript
// Option A: Track insertion depth (only works if OfficeCLI path is stable post-insert)
lastAnchor = `${repeaterSpec.insert_anchor.path}[${i + 1}]`;

// Option B: Reverse-clone (insert in reverse order, all using same original anchor)
const reversedItems = [...items].reverse();
for (const item of reversedItems) {
  ops.push({ kind: "clone", parent: "/body", from: repeaterSpec.clone_from,
             after: repeaterSpec.insert_anchor.path });
  // set fields on the newly cloned node using a stable relative reference
}
```

Option B is safer because it never requires tracking a moving target. The original anchor path never changes because you always insert at the same position (the new item slides *between* the anchor and the previous clone).

### 1.3 `setCell` Writes to Template Node, Not Cloned Node

Immediately after the clone op, the planner emits setCell ops:

```typescript
ops.push({
  kind: "setCell",
  path: `${lastAnchor}/${childPath}`,  // lastAnchor is already wrong here
  props: { text: String(val) },
});
```

Since `lastAnchor` points to the original template node (bug 1.2), all setCell ops write to the *template* paragraph. This is **destructive** — it corrupts the template block that will be cloned for subsequent items. The correct path requires referencing the clone's new position. With the reverse-clone strategy, the newly inserted node is always at `${repeaterSpec.insert_anchor.path}[^1]` (it was just inserted at position 1 relative to the anchor). With the forward strategy, it requires OfficeCLI to return the new path upon insert (not currently in the batch response).

**Short-term fix:** Use reverse-clone + hardcoded relative path. **Long-term fix:** OfficeCLI's `batch` command should return the resolved path of each newly created node — check if `--json` output includes this in `v1.0.64`.[^4]

### 1.4 `auditor.ts` CLI Side Effect on Import

The auditor file has a top-level CLI entry point that runs unconditionally:

```typescript
const docxPath = process.argv[^2];
if (docxPath) {
  auditTemplate(docxPath).then(...)  // runs on EVERY import if process has args
}
```

When `pipeline-core.ts` imports from `auditor.ts`, and the MCP server process was launched with arguments (e.g. `npx tsx src/mcp/office-auto-server.ts --some-arg`), this block fires and attempts to audit a random path. The fix is trivial:

```typescript
// Bun-native idiom:
if (import.meta.main) { ... }
// Node/tsx idiom:
if (process.argv[^1] && import.meta.url.endsWith(process.argv[^1])) { ... }
```

### 1.5 `officecli.ts` Response Parsing Inconsistency

The wrapper always appends `--json` and parses stdout:

```typescript
const parsed = JSON.parse(result.stdout || "{}");
return parsed;  // returns the raw parsed object, not normalized
```

The problem is that OfficeCLI commands return different top-level shapes depending on the command:
- `validate` → `{ ok: boolean, issues: [...] }`
- `query` → `{ results: [...] }`
- `batch` → `{ success: boolean, results: [...] }`

Callers then do ad-hoc access: `sdts.data?.results` in `auditor.ts`, `schema.success` in `validator.ts`, `q.data?.results?.length` in `validator.ts`. This is inconsistent and fragile — adding a new command requires auditing every caller. The `success` field is being read off a property that doesn't exist on `validate` output.

**Fix:** Create a normalizer:

```typescript
function parseOfficeCLI(result: SpawnSyncReturns<string>, command: string): OfficeCLIResult {
  if (result.status !== 0 && !result.stdout) {
    return { success: false, data: null, error: result.stderr?.slice(0, 500) };
  }
  try {
    const raw = JSON.parse(result.stdout || "{}");
    // Normalize: always expose { success, data, error }
    const success = raw.ok ?? raw.success ?? (result.status === 0);
    return { success, data: raw.results ?? raw.data ?? raw, error: raw.error };
  } catch {
    return { success: false, data: null, error: `Parse error: ${result.stdout?.slice(0,200)}` };
  }
}
```

### 1.6 Validator Runs 7 Serial Blocking `spawnSync` Calls

`validate()` calls `officecli` synchronously 7 times: 1x validate, 1x view issues, 5x query for placeholder patterns, plus N calls inside `checkInvariants` for each required section. Each `spawnSync` has a 120s timeout. On a large DOCX, total blocking time can exceed 15 minutes. This completely blocks the Node.js event loop for the duration.

The solution is to batch placeholder queries into one `query` call using OfficeCLI's boolean OR selector:

```typescript
// Instead of 5 separate queries:
const leftover = officecli(["query", file,
  ':contains("{{") or :contains("__") or :contains("Nội dung")'
]);
```

And to run validate + query in parallel via `Promise.all` using async `spawn` (not `spawnSync`).

### 1.7 `ContentSchema` `blocks` and `tables` Not Constrained Per-Template

`deriveContentSchema` generates strict `fields` constraints from the manifest, but leaves `blocks` and `tables` as `z.record(z.string(), z.array(z.any()))`. The LLM can generate any shape for block items and Zod will pass validation. However, `binding-planner.ts` accesses `item[fieldName]` where `fieldName` comes from `manifest.repeaters[name].item_fields`. If the LLM omits a field or uses a different key name, the planner silently skips the setCell op — the cloned block has empty fields with no error reported.

**Fix:** `deriveContentSchema` must also build per-repeater item schemas:

```typescript
for (const [repeaterName, repeaterSpec] of Object.entries(manifest.repeaters ?? {})) {
  const itemShape: Record<string, z.ZodTypeAny> = {};
  for (const fieldName of Object.keys(repeaterSpec.item_fields)) {
    itemShape[fieldName] = z.string();
  }
  blockShape[repeaterName] = z.array(z.object(itemShape));
}
```

***

## Part 2: Latent Architectural Risks

### 2.1 Manifest Schema Cannot Represent Rich Document Structures

The current `ManifestSchema` supports `fields` (scalar SDTs), `repeaters` (single-level clone blocks), and `tables`. This fails to represent common document patterns:

| Document Pattern | Required Manifest Support | Current Support |
|---|---|---|
| Nested tables (table inside a clause) | Hierarchical repeater with child table | ❌ Not supported |
| Multi-level numbered lists | Repeater with nested sub-repeater | ❌ Not supported |
| Conditional sections (show/hide based on data) | Conditional field with predicate | ❌ Not supported |
| Multi-section documents (different header/footer per section) | Section-scoped fields | ❌ Not supported |
| Rich text blocks (bold, italic, links within a paragraph) | Run-level content spec | ❌ Only plain `text` |
| Images inserted at runtime | Binary content field | ❌ Not modelled |

This is the primary scalability blocker. As you add document types (official memos, reports, contracts, meeting minutes), each will hit a manifest limitation.

**Design fix — extend `ManifestSchema` with a recursive structure:**

```typescript
// Allow repeaters to have nested repeaters and nested tables
export const RepeaterSpecSchema: z.ZodType<RepeaterSpec> = z.lazy(() => z.object({
  clone_from: z.string(),
  insert_anchor: z.object({ mode: z.enum(["after","before"]), path: z.string() }),
  item_fields: z.record(z.string(), z.string()),
  nested_repeaters: z.record(z.string(), RepeaterSpecSchema).optional(),
  nested_tables: z.record(z.string(), TableSpecSchema).optional(),
}));
```

### 2.2 Single Template Mode Detection is Brittle

`auditTemplate` assigns mode `strict-sdt` if any SDT exists, else `legacy-anchor`. Real-world administrative document templates often mix both: they have a few SDT fields for metadata (document number, date) but use heading+placeholder patterns for body sections. A template that is primarily `legacy-anchor` but has one incidental SDT will be misclassified as `strict-sdt`, causing all body section fields to be missed during audit.

**Fix:** Mode should be assigned per-field, not per-template:

```typescript
type FieldMode = "sdt" | "find-replace" | "heading-anchor";
```

The manifest records the mode on each `FieldSpec`, and the binding planner selects the appropriate OfficeCLI operation (direct `set` on resolved path vs. `set --find --replace`).

### 2.3 The `merge` Command Is Not Being Used

OfficeCLI v1.0.64 has a native `merge` command: `officecli merge <template> <output> <data.json>` that replaces all `{{key}}` placeholders with JSON values, working across paragraphs, runs, table cells, headers, footers, and chart titles. This is exactly what scalar field replacement does in the current pipeline (L3b), but implemented entirely in userland code across `binding-planner.ts` + `docx-renderer.ts` + `officecli.ts`.[^5]

**Risk:** The current approach requires resolving SDT paths (fragile, as shown in bugs 1.1–1.3), constructing batch operations, and handling OfficeCLI batch format correctly. Native `merge` eliminates this entire complexity for scalar fields. The only requirement is that templates use `{{fieldName}}` placeholders instead of SDT tags.

**Opportunity:** For most administrative document types (quyết định, công văn, biên bản), all scalar fields can be handled by `merge`. Only repeating blocks and tables require the full batch pipeline. This is a dramatic simplification.

### 2.4 No Idempotency — Template is Mutated In Place

`docx-renderer.ts` copies the template then applies the batch to the copy. But the copy is at a hardcoded output path (`template.out.docx`). If the pipeline fails halfway through the batch, the partially-mutated output file remains on disk. On the next run, the renderer will copy the (still valid) template again — but if there was a crash *after* the copy and *before* the batch, the output from the previous partial run may be used by subsequent validation calls.

More critically: the current `auditor.ts` writes manifests back to disk under `manifests/` but never checks if the template has changed since the manifest was cached. A stale manifest with outdated `resolved_path` values causes all subsequent `set` operations to target wrong document paths with no error.

**Fix:** Add a `template_sha` field to the manifest. On each pipeline run, compute the SHA-256 of the template file and compare against `manifest.template_sha`. If different, invalidate the manifest and re-audit.

### 2.5 Concurrent Requests on the Same Template

The MCP server is single-process. If two users request document generation from the same template simultaneously, both will copy to the same output path and execute `officecli open` + `batch` concurrently. OfficeCLI's resident mode holds a file lock, but two `open` calls on the same file will conflict.

**Fix:** Namespace output paths by request ID: `out/{templateId}_{uuid}.docx`. Use a per-template semaphore if resident mode is required.

### 2.6 sglang Backend Limitations for Grammar Enforcement

The config uses an sglang endpoint. Unlike llama-server (llama.cpp), sglang's `json_schema` / `response_format` support depends on the model and backend version. The master plan explicitly recommended llama-server for reliable GBNF/json_schema enforcement. With sglang, the `json_schema` is passed as `response_format` in the OpenAI-compatible path (`fetchOpenAICompletion` in `client.ts`), which *should* work — but sglang's grammar implementation is less battle-tested for complex nested schemas and Vietnamese Unicode patterns (character `Đ`, diacritics in regex patterns).

**Risk:** `document_number` pattern `^[0-9]+\/[A-ZĐ-]+$` contains `Đ` (U+0110). Many grammar generators only support ASCII character classes in regex constraints. The `deriveContentSchema` regex for date `^\d{4}-\d{2}-\d{2}$` should be fine, but the document number regex may silently fail to constrain the model output.

**Mitigation:** Test with `z.string().regex(/^[0-9]+\/[A-ZĐ-]+$/)` explicitly on the sglang endpoint and check if Zod-to-JSONSchema generates a valid `pattern` field. Add a post-Zod regex check as a fallback regardless of grammar enforcement.

### 2.7 No Document Version Control or Audit Trail

The pipeline writes `out/batch.json` as a log, but this file is overwritten on every run. There is no mechanism to replay a specific generation, diff two versions of the same document, or audit which content was injected by which request.

**Fix:** Name batch logs with timestamps: `out/{templateId}_{timestamp}.batch.json`. Use OfficeCLI's `dump` command (`officecli dump <output.docx>`) to generate a replayable batch from the final output — this is the round-trip regression testing mechanism described in the master plan.[^4]

***

## Part 3: OfficeCLI-First Strategy — What to Use Before Building Custom Tools

OfficeCLI v1.0.64 exposes an extensive set of native capabilities. The design principle should be: **exhaust OfficeCLI's native verbs before writing custom code**. Here is a capability map against pipeline needs:[^6][^7][^4]

### 3.1 What OfficeCLI Already Handles Natively

| Pipeline Need | OfficeCLI Native Command | Current Usage |
|---|---|---|
| Scalar field replacement | `merge <template> <output> <data.json>` with `{{key}}` syntax[^5] | ❌ Not used — using batch+set instead |
| Template audit (list structure) | `view <file> outline \| stats \| annotated --json` | ✅ Used partially |
| Query by style/tag/content | `query <file> <selector>` with `:contains`, `[@style=]`, `sdt[tag=]` | ✅ Used |
| Clone a block with its formatting | `add <file> <parent> --from <path> --after <anchor>` | ✅ Used (with anchor bug) |
| Validate output | `validate <file>` | ✅ Used |
| Check remaining placeholders | `query :contains("{{")` | ✅ Used |
| Atomic multi-operation apply | `batch <file> --input batch.json --stop-on-error` | ✅ Used |
| Regression/replay testing | `dump <file>` → replayable batch JSON | ❌ Not used |
| Resident mode (fast multi-step) | `open <file>` → commands → `close <file>` | ❌ Not used — each batch call opens/closes |
| Live preview during dev | `watch <file>` | ❌ Not used |
| Cross-format (xlsx, pptx) | Full command parity | ❌ Not planned |
| Plugin system for .doc, .hwpx, PDF export | `plugins install <name>` | ❌ Not used |
| Review/annotation workflow | `mark / unmark / get-marks` | ❌ Not needed yet |
| TOC/page number refresh | `refresh <file>` | ❌ Not used |

### 3.2 Recommended Architecture: `merge`-first Pipeline

For the majority of administrative document types (single-language, scalar fields, simple repeaters), the following pipeline eliminates most of the current complexity:

```
User NL request
     │
     ▼
L2: LLM → content.json (Zod-validated)
     │
     ├─ Scalar fields? ──→ officecli merge template.docx output.docx fields.json
     │                     (handles {{key}} replacement natively, including headers/footers)
     │
     ├─ Repeating blocks? → officecli batch (clone + set, anchor-tracked)
     │
     ├─ Tables? ──────────→ officecli batch (add tr + set tc)
     │
     ▼
L4: officecli validate + query :contains("{{") + view issues
```

This approach reduces L3 from 3 modules (`binding-planner`, `docx-renderer`, `officecli wrapper`) to 2 code paths: a direct `merge` call for scalar fields, and a batch call for structural changes.

### 3.3 What Requires Custom Tooling

Only a small set of use cases genuinely requires code beyond OfficeCLI calls:

| Capability Gap | Why OfficeCLI Can't | Custom Solution |
|---|---|---|
| Template SHA caching and staleness detection | OfficeCLI doesn't track template versions | TS utility in `manifest/cache.ts` |
| Dynamic `content.json` schema derivation from manifest | Schema derivation is application logic | `manifest/schema.ts` `deriveContentSchema()` |
| Zod validation + narrow self-repair loop for L2 | LLM backend-agnostic; OfficeCLI has no LLM | `llm/normalizer.ts` |
| Output path namespacing for concurrent requests | Process-level concern | Thin wrapper in `render/docx-renderer.ts` |
| `merge` data preparation (filter fields, handle date formatting, escape values) | Pre-processing step | Lightweight TS function |
| Multi-document type routing (which template to use) | Registry concern | `manifest/registry.ts` (new) |

### 3.4 TypeScript SDK vs. FastMCP for Custom MCP Tools

The project already uses `@modelcontextprotocol/sdk` in TypeScript. The question of switching to Python FastMCP is relevant if custom tooling is needed. The key trade-offs are:

| Dimension | TypeScript (`@modelcontextprotocol/sdk`) | Python FastMCP |
|---|---|---|
| Fit with existing codebase | ✅ Same language as pipeline core (Zod, types shared) | ❌ Requires language boundary, no type sharing |
| Schema validation | Zod (explicit, strict)[^8] | Pydantic (decorator-inferred, more implicit)[^9] |
| Boilerplate | Moderate — explicit `server.tool()` registration | Minimal — `@mcp.tool()` decorator[^9] |
| Async model | Node.js Promises (familiar) | asyncio (requires explicit coroutine awareness)[^10] |
| ML/data library access | Limited | Rich (numpy, pandas, sklearn for any ML post-processing) |
| Deployment | Same process as pipeline (Bun/Node) | Separate process, additional dependency |
| OfficeCLI interop | `spawnSync` / `spawn` directly | `subprocess` / `asyncio.create_subprocess_exec` |
| Long-term MCP feature parity | ✅ Official SDK, Anthropic-maintained | FastMCP 2.x/3.x adds features above the official SDK[^9] |

**Verdict: Stay with TypeScript for all custom MCP tools.** The existing codebase is already TypeScript, Zod schemas are the source of truth, and sharing types between `pipeline-core.ts` and the MCP server eliminates a whole class of serialization bugs. FastMCP Python would only be the right choice if the custom tools needed Python-native ML libraries (e.g., a document classifier, a layout model) — which is not the case here. If ergonomics are a concern, the TypeScript community package `punkpeye/fastmcp` (TypeScript FastMCP) provides the same decorator-style API as Python FastMCP while staying in the TypeScript ecosystem.[^11]

***

## Part 4: Flexible Multi-Document Architecture

### 4.1 The Core Problem with Current Single-Template Design

The current system is designed around one template (`format_template`) with four scalar `legacy-anchor` fields. Every document type requires a different manifest structure, and the `ContentSchema` is effectively hardcoded per template via `deriveContentSchema`. There is no mechanism for:
- Routing a user request to the correct template
- Supporting document types with fundamentally different structures (e.g., a contract vs. a decision notice vs. a meeting minutes)
- Evolving a template without invalidating existing manifests

### 4.2 Document Type Registry

The first extension needed is a **template registry** — a catalogue of available document types with their metadata, distinct from the manifest (which is a structural scan of one DOCX):

```typescript
// src/registry/document-types.ts
export interface DocumentType {
  id: string;                    // e.g. "quyet-dinh", "cong-van", "bien-ban"
  displayName: string;           // Human-readable name
  templateFile: string;          // path relative to templates/
  locale: string;
  description: string;           // For LLM routing context
  capabilities: DocumentCapability[]; // What this type supports
}

export type DocumentCapability =
  | "scalar_merge"        // simple {{key}} merge
  | "repeating_blocks"    // clone-block repeaters
  | "tables"              // dynamic table rows
  | "multi_section"       // section-scoped headers/footers
  | "conditional"         // show/hide sections
  | "rich_text";          // styled runs within paragraphs

// Registry loaded from templates/registry.json (version-controlled)
```

A routing agent (or a simple LLM call with a small schema) maps user intent to a `DocumentType.id`. This replaces the current hard `template_id` parameter in `generate_document`.

### 4.3 Per-Type Manifest with Capabilities

Each document type has its own manifest, extended with capabilities:

```json
{
  "template_id": "quyet-dinh-001",
  "capabilities": ["scalar_merge", "repeating_blocks"],
  "merge_fields": {
    "agency_name": "{{agency_name}}",
    "doc_number": "{{doc_number}}",
    "issue_date": "{{issue_date}}"
  },
  "repeaters": {
    "decision_items": {
      "clone_from": "/body/p[@style='DieuKhoan'][^1]",
      "insert_anchor": { "mode": "after", "path": "/body/p[@style='DieuKhoan'][last()]" },
      "item_fields": { "title": "run[^1]", "content": "run[^2]" },
      "item_schema": {
        "type": "object",
        "properties": {
          "title": { "type": "string", "maxLength": 200 },
          "content": { "type": "string" }
        },
        "required": ["title", "content"]
      }
    }
  },
  "template_sha": "abc123..."
}
```

The `item_schema` field allows `deriveContentSchema` to generate tight per-repeater Zod schemas, closing bug 1.7.

### 4.4 Capability-Driven Rendering Strategy

The `docx-renderer` selects its rendering strategy based on manifest capabilities:

```typescript
export async function render(ops: Op[], manifest: Manifest, templatePath: string, outputPath: string) {
  // Strategy 1: Use native `merge` for all scalar fields (no batch needed)
  if (manifest.capabilities.includes("scalar_merge") && manifest.merge_fields) {
    const mergeData = extractMergeData(ops);  // filter only scalar set ops
    await officecliMerge(templatePath, outputPath, mergeData);
    // Remove scalar set ops — already handled
    ops = ops.filter(op => op.kind !== "set");
  } else {
    // Fallback: copy template for batch
    fs.copyFileSync(templatePath, outputPath);
  }

  // Strategy 2: Batch for remaining structural ops (clone, setCell, etc.)
  if (ops.length > 0) {
    const batch = toBatch(ops);
    await officecliBatch(outputPath, batch, { stopOnError: true });
  }

  return outputPath;
}
```

This design means a simple document (only scalar fields) never needs to construct batch JSON at all — it uses `merge` directly, which is faster and simpler. Complex documents get the full batch pipeline only for the parts that need it.

### 4.5 OfficeCLI MCP as the Primary Agent Interface

Rather than the agent calling `office-auto_generate_document` as a black box, a more flexible design exposes OfficeCLI's MCP server directly to the orchestrator, with `office-auto` only providing the template registry and content normalization:

```
Orchestrator Agent
       │
       ├── office-auto_list_document_types()    → available types + capabilities
       ├── office-auto_audit_template(path)     → generate/refresh manifest
       ├── office-auto_normalize_content(req, template_id)  → content.json (L2 only)
       │
       ├── officecli_merge(template, output, data)          → scalar replacement
       ├── officecli_query(file, selector)                  → inspection/validation
       ├── officecli_batch(file, batch_json)                → structural ops
       └── officecli_validate(file)                         → output validation
```

This design gives the orchestrator **full transparency** over every step and allows it to adapt the pipeline per document type without changing any code. The agent can call `officecli_query` to inspect the template structure before deciding how to proceed, use `merge` for simple types, and fall back to `batch` for complex ones. This is aligned with OfficeCLI's design as an "AI-native CLI" where agents issue individual commands and observe results.[^12][^6]

### 4.6 Safe Agent Loop Design

Based on agentic system design principles, the orchestrator must include explicit stopping conditions:[^2][^3][^1]

```markdown
## LOOP GUARDRAILS (add to docgen-orchestrator.md)

### Iteration Budget
- Each pipeline run has a budget of MAX 8 tool calls total.
- Track tool calls. After 8 calls: STOP. Report partial state to user.

### No-Progress Detection
- If the same tool is called with the same arguments twice: STOP.
- If `generate_document` returns error twice in a row: STOP. Report error. Do not retry.

### Error Classification
- "Manifest not found" → call audit_template ONCE. If it fails → STOP.
- "Content normalization failed" → report LLM backend error. Do not retry more than 2 times.
- "Batch render failed" → report structural error to user. Do not self-repair.
- "Validation failed: leftover placeholders" → report which fields were not filled.
```

***

## Part 5: Priority Implementation Roadmap

| Priority | Change | Files Affected | Effort |
|---|---|---|---|
| **P0** | Fix `LLAMA_BASE_URL` to point to sglang endpoint | `.opencode/config.json` | 5 min |
| **P0** | Add loop guardrails to agent prompt | `.opencode/agents/docgen-orchestrator.md` | 15 min |
| **P0** | Fix repeater anchor drift (reverse-clone strategy) | `src/render/binding-planner.ts` | 30 min |
| **P0** | Fix `setCell` to reference cloned node path | `src/render/binding-planner.ts` | 15 min |
| **P1** | Remove CLI side-effect from `auditor.ts` | `src/manifest/auditor.ts` | 5 min |
| **P1** | Normalize OfficeCLI response parsing | `src/render/officecli.ts` | 30 min |
| **P1** | Add per-repeater item schema to `deriveContentSchema` | `src/manifest/schema.ts` | 30 min |
| **P1** | Add `template_sha` staleness check to manifest | `src/manifest/auditor.ts`, `cache.ts` | 45 min |
| **P2** | Implement `merge`-first rendering strategy | `src/render/docx-renderer.ts` | 2h |
| **P2** | Batch validator `officecli` calls (boolean OR query) | `src/validate/validator.ts` | 1h |
| **P2** | Add output path namespacing (concurrent safety) | `src/render/docx-renderer.ts` | 30 min |
| **P3** | Document type registry (`registry.json` + loader) | `src/registry/` (new) | 3h |
| **P3** | Capability-driven rendering strategy dispatch | `src/render/docx-renderer.ts` | 2h |
| **P3** | Extend `ManifestSchema` for nested repeaters | `src/manifest/schema.ts` | 3h |
| **P3** | Add `dump`-based regression testing | `test/` | 2h |

---

## References

1. [Execution Guardrails for Agentic Implementation](https://infohub.delltechnologies.com/en-us/p/execution-guardrails-for-agentic-implementation/) - Large Language Models (LLMs) have increasingly powerful capabilities when it comes to use cases such...

2. [Designing Safe Agent Loops: Avoiding Infinite Loops and ...](https://www.linkedin.com/posts/sathyavedu-rakesh_day20-30days-ai-activity-7413256928275038208-Y-n8) - 👉 Hello Guys!! We are #day20 of our #30days RAG and LangGraph Series ➡️ Day 20: Why Most Agent Loops...

3. [Build an Agent Tool Loop - Inngest Documentation](https://www.inngest.com/docs/ai-patterns/agent-tool-loops) - Build a fault-tolerant AI agent loop where every LLM call and tool execution is a checkpointed, retr...

4. [Home · iOfficeAI/OfficeCLI Wiki - GitHub](https://github.com/iOfficeAI/OfficeCLI/wiki) - OfficeCLI is the first and best Office suite purpose-built for AI agents to read, edit, and automate...

5. [command merge · iOfficeAI/OfficeCLI Wiki - GitHub](https://github.com/iOfficeAI/OfficeCLI/wiki/command-merge) - Copies the template to the output path, then replaces all {{key}} placeholders with values from the ...

6. [OfficeCLI — Single Binary CLI for AI Agents to Automate Word, Excel ...](https://powerpoint.md/skills/officecli.html) - OfficeCLI: Single binary CLI for AI agents to read, edit, and automate Word, Excel, and PowerPoint f...

7. [OfficeCLI — install, API, examples, gotchas | iOfficeAI/OfficeCLI](https://langlabs.io/iOfficeAI/OfficeCLI) - iOfficeAI/OfficeCLI packed for AI consumption — synthesized skill, file-tree token weights, and down...

8. [Building Your First MCP Server: TypeScript vs. Python - Ken W. Alger](https://www.kenwalger.com/blog/ai/mcp-quickstart-typescript-vs-python/) - TypeScript is the “native” language of the Model Context Protocol, Python SDK offers a beautifully d...

9. [FastMCP: building MCP servers in Python - Casys](https://casys.ai/blog/fastmcp-python-framework) - FastMCP is a widely used Python framework for MCP servers. Pythonic decorators, auto-generated schem...

10. [Python vs TypeScript MCP SDK: Key Differences | Skillful.sh Blog](https://skillful.sh/blog/python-vs-typescript-mcp-sdk-asyncio-patterns-fastmcp-and-when-to-choose-python) - Compare Python and TypeScript MCP SDKs: asyncio patterns, FastMCP shortcuts, Pydantic integration, a...

11. [Blog 11: FastMCP Showdown - Comparing Advanced TypeScript vs ...](https://cbruyndoncx.github.io/MCP-Learnings/6-Remaining/Blogs/blog-11) - Blog 11: FastMCP Showdown - Comparing Advanced TypeScript vs.

12. [OfficeCLI — Agent-friendly Office tools — Agent Skill | MCP App Store](https://mcpapp-store.com/skills/iofficeai-officecli/officecli) - A comprehensive CLI for reading, editing, validating, and automating .docx, .xlsx, and .pptx files —...

