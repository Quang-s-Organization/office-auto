Scope thay đổi căn bản: đây là **văn bản hành chính** (quyết định, nghị quyết) theo thể thức chuẩn — format gần như cố định, chỉ thay nội dung/field. Điều này đổi hẳn thiết kế tối ưu, nên tôi research kỹ thể thức văn bản hành chính (Nghị định 30/2020/NĐ-CP) và cách đánh số Điều/Khoản/Điểm để plan khớp đúng, rồi mới deliver file markdown.

Research xong. Scope mới làm rõ một điều quan trọng: đây là **văn bản hành chính theo thể thức chuẩn** (Nghị định 30/2020/NĐ-CP) — format gần như cố định, chỉ thay nội dung/field. Điều này lật lại một giả định lớn trong pipeline hiện tại: **cách splice toàn bộ `<w:body>` thực ra LÀM HỎNG thể thức** (khối chữ ký, nơi nhận, quốc hiệu nằm trong body sẽ bị xóa). Bài toán đúng của bạn là **điền field vào template (mail-merge / region replacement)**, không phải render markdown tự do.

Dưới đây là file markdown đầy đủ, viết lại hoàn toàn theo scope văn bản hành chính. Copy nguyên khối (outer fence dùng `~~~~`):

markdown

# Office-Auto — Administrative-Document Pipeline Plan (v3.1 → v4-AD)

> **Scope (locked):** Vietnamese **administrative documents** (văn bản hành chính) —
> 

> quyết định, nghị quyết, công văn, tờ trình, thông báo, etc. — produced for a
> 

> government/agency office. The document **format is fixed by the template** and
> 

> follows the national standard **Nghị định 30/2020/NĐ-CP** ("thể thức và kỹ thuật
> 

> trình bày văn bản hành chính"). The pipeline's job is to **update content/fields**
> 

> (decision name, resolution body, số/ký hiệu, ngày tháng, căn cứ, điều khoản, nơi
> 

> nhận, người ký…) into that template **without disturbing the official layout**.
> 

> 
> 

> This plan is written for a coding agent to implement. It supersedes the prior
> 

> "general md→docx hardening" plan because the scope is now narrower and more
> 

> deterministic.
> 

---

## 0. TL;DR for the implementer

1. **Stop replacing the whole `<w:body>`.** For administrative documents this is
    
    actively wrong: the thể thức components (Quốc hiệu/Tiêu ngữ, khối chữ ký, Nơi
    
    nhận, dấu) live *inside* the body. Full-body splice silently destroys them.
    
2. **Adopt a template-as-form model.** The template is the authoritative document.
    
    Mark the variable regions (fields + the nội dung region) and replace *only*
    
    those regions. Everything else is preserved byte-for-byte.
    
3. **Two replacement units:**
    - **Field merge** (single-value tokens: số, ký hiệu, ngày, tên loại, trích yếu,
        
        người ký, chức vụ, nơi nhận…). 90% of real edits are here.
        
    - **Body region rendering** (the "Nội dung" block: Điều / Khoản / Điểm with
        
        Vietnamese legal numbering, paragraphs, căn cứ list, optional simple table).
        
4. **Shrink the IR.** No general tables/images/code as first-class. Admin docs need:
    
    headings/Điều, legal-numbered clauses, paragraphs, inline bold/italic/underline,
    
    centered lines, simple "danh sách" tables, page breaks. Everything else →
    
    `unsupported` with a loud error.
    
5. **LLM is an extractor/mapper, not a renderer.** It converts the user's source
    
    into a typed, validated *FieldSet + BodyPlan* JSON. It never emits XML, never
    
    decides styling, never touches the template chrome.
    
6. **Fail loud + thể thức compliance gate.** Validate: all required fields filled,
    
    no leftover tokens, chrome unchanged outside replaced regions, and the 9 ND-30
    
    components still present.
    

---

## 1. Current architecture (grounding)

Confirmed from the repo (`Quang-s-Organization/office-auto`, MCP server `v3.1.0`):

- Phase graph: `CREATED → SOURCE_PARSED → MAPPED → COMPILED → VALIDATED →
    
    APPLIED → VERIFIED → COMPLETED`, supervised by handlers
    
    `phaseInspect/phaseSourceParse/phaseMap/phaseCompile/phaseValidate/phaseApply/
    
    phaseVerify/phaseFinalGate`.
    
- Apply step (`apply_splice.ts › spliceDocxBody`): copy template → `AdmZip` →
    
    replace the entire `word/document.xml` body → write zip.
    
- Chrome handling (`docx-xml.ts`): `extractChrome` keeps **front-matter** (blocks
    
    before the first heading) + the **first `sectPr`**. Body rendering
    
    (`buildParagraphXml`) emits **one `<w:r>` per paragraph**, no inline runs, no
    
    `<w:br/>`.
    
- Style resolution (`resolveStyleMap`, `findFirstHeadingParagraph`): hardcoded
    
    candidate lists of styleIds/names; unmapped role → paragraph **silently skipped**.
    
- Validation (`validate_output.ts`): currently rubber-stamps (`validated:true`).

### Why this breaks on administrative documents specifically

| Thể thức component (ND-30) | Where it sits in OOXML | Current pipeline result |
| --- | --- | --- |
| Quốc hiệu + Tiêu ngữ (header table) | top of `<w:body>`, before content | Kept *only if* it's "front-matter" before first heading — fragile |
| Số, ký hiệu / Địa danh, ngày tháng | in the header table cells | Not a "field" → cannot be updated; survives by luck |
| Nội dung (Điều/Khoản/Điểm) | middle of body | Flattened to single runs; legal numbering lost |
| **Chức vụ + chữ ký người có thẩm quyền** | **after** the content | **Destroyed** — it's after the last heading, inside the replaced range |
| **Nơi nhận** | **after/below** content | **Destroyed** for the same reason |
| Dấu / chữ ký số | overlay near signature | Lost / misplaced |

**Conclusion:** the splice model preserves the *top* of the thể thức by accident and

deletes the *bottom* (signature block + nơi nhận) by design. For this scope, the

fix is not "render the body better" — it's "stop regenerating the body; replace

only marked regions."

---

## 2. Research basis (what the standard actually requires)

Vietnamese administrative documents follow a **fixed, legally-specified structure**

(ND 30/2020/NĐ-CP, Phụ lục I). The main thể thức components are:[[1]](https://storage-edu.vnpt.vn/edu-lci/8398/Vanban/12_trich-tt-30.pdf)

1. Quốc hiệu và Tiêu ngữ
2. Tên cơ quan, tổ chức ban hành văn bản
3. Số, ký hiệu của văn bản
4. Địa danh và thời gian ban hành văn bản
5. Tên loại và trích yếu nội dung văn bản
6. Nội dung văn bản
7. Chức vụ, họ tên và chữ ký của người có thẩm quyền
8. Dấu, chữ ký số của cơ quan, tổ chức
9. Nơi nhận

Optional components: phụ lục, dấu chỉ độ mật/khẩn, ký hiệu người soạn thảo, etc.

Technical presentation rules (Phụ lục I):[[2]](http://thptvantao.edu.vn/tin-tuc-thong-bao/thong-bao/diem-moi-trong-nghi-dinh-30-2020-nd-cp-ve-ky-thuat-trinh-bay.html)[[3]](https://thptphunghung.hcm.edu.vn/tai-nguyen/the-thuc-va-ky-thuat-trinh-bay-van-ban-theo-nghi-dinh-so-302020nd-cp-cua-chinh/ctmb/14161/449348)

- Paper: **A4 (210 × 297 mm)**, portrait (landscape only for wide tables).
- Font: **Times New Roman**, Unicode (TCVN 6909:2001), black, size typically 13–14.
- Component positions fixed by Mục IV Phần I Phụ lục I.

Body numbering hierarchy (Phần/Chương/Mục/Tiểu mục/Điều/Khoản/Điểm):[[4]](http://thcskimchung.pgd-donganh.edu.vn/van-ban-cong-van/so-do-the-thuc-van-ban-hanh-chinh-theo-nghi-dinh-30-2020-nd-cp-nhu-the-nao-cach-trinh-bay-the-thuc-van-ban-hanh-chinh-.html)

- **Điều**: `Điều 1.`, `Điều 2.` … (bold label).
- **Khoản**: `1.`, `2.` …
- **Điểm**: `a)`, `b)`, `c)` …
- Căn cứ lines are in *italics* and end with `;` (last one ends with `.`).
- Signature block uses authority prefixes such as `TM.`, `KT.`, `Q.`, `TL.`,
    
    `TUQ.` (e.g. "TM. ỦY BAN NHÂN DÂN").[[5]](https://cadn.com.vn/van-ban-hanh-chinh-cua-co-quan-va-nguoi-dung-dau-co-quan-post236264.html)
    

**Design implication:** the value space is *small and closed*. We can enumerate the

constructs exhaustively. This is the opposite of "general markdown," and it justifies

a deterministic, template-locked pipeline with the LLM used only for extraction.

> Official text of the decree is published at [chinhphu.vn](http://chinhphu.vn) for citation in code
> 

> comments / tests.[[6]](https://vanban.chinhphu.vn/default.aspx?pageid=27160&docid=199378)
> 

---

## 3. Problem statement (v3.1 risks, re-scoped to admin docs)

| ID | Problem | Code location | Admin-doc impact |
| --- | --- | --- | --- |
| **P1** | Signature block + Nơi nhận after content are deleted by full-body splice | `apply_splice.ts`, `extractChrome` | **Critical** — invalid văn bản, missing thẩm quyền/chữ ký |
| **P2** | No field-level update (số, ký hiệu, ngày, trích yếu, người ký) | no field model exists | Core use-case ("update đồng bộ") impossible without regenerating whole body |
| **P3** | Inline formatting flattened to one run; markdown markers (`**`,`*`) leak as literal text | `buildParagraphXml` | Bold trích yếu / "QUYẾT ĐỊNH:" / căn cứ italics lost |
| **P4** | Vietnamese legal numbering (Điều/Khoản/Điểm) not modeled | `build_render_list.roleForSourceBlock` returns Normal for everything | Clause numbering wrong/missing |
| **P5** | Line breaks `\n` collapse | single `<w:t>` | Multi-line căn cứ / nơi nhận lists merge |
| **P6** | Style role hardcoded; unmapped → silently skipped | `resolveStyleMap`, `buildRenderList` (`if(!styleId) continue`) | Content silently disappears |
| **P7** | `extractChrome` grabs first `sectPr` only; `generateParaId` may collide with retained paraIds | `docx-xml.ts` | Multi-section docs + duplicate paraId corruption |
| **P8** | Validation rubber-stamps; no thể thức compliance check | `validate_output.ts`, final gate | Invalid documents pass as "ok" |

---

## 4. Design principles (v4-AD)

1. **Template is sacred.** Default behavior = preserve 100% of the template; mutate
    
    only explicitly-marked regions. No region marked → no change (and a warning).
    
2. **Deterministic core, LLM advisor at the edges.** All XML generation is pure code.
    
    LLM only produces a typed `FieldSet`/`BodyPlan` from the source and is fully
    
    schema-validated before use.
    
3. **Closed construct set.** Enumerate every admin-doc construct. Anything outside →
    
    `unsupported` with a hard error and a precise message (no silent skip).
    
4. **Fail loud.** Missing required field, leftover token, unmapped construct, chrome
    
    drift → error with a `repair_handoff`, never a silent pass.
    
5. **Reproducible & auditable.** Same input ⇒ byte-identical output. Persist the
    
    `FieldSet`, `BodyPlan`, and a region-diff report in the run state dir.
    

---

## 5. Target architecture (v4-AD)

```
INSPECT_TEMPLATE → BIND_FIELDS → PARSE_SOURCE → BUILD_PLAN → COMPILE_REGIONS
   → APPLY_REGIONS → VALIDATE → COMPLIANCE_GATE → VERIFY → COMPLETED
```

| Phase | Module (new/changed) | Responsibility |
| --- | --- | --- |
| INSPECT_TEMPLATE | `lib/template-introspect.ts` | Discover variable regions (content controls / bookmarks / `{{tokens}}`), read style table, locate the "Nội dung" body region, detect sections |
| BIND_FIELDS | `lib/field-binding.ts` | Build the `FieldSet` schema from the template's discovered fields |
| PARSE_SOURCE | `lib/source-parse/*` (mdast-based) | Parse the source markdown into a structured tree |
| BUILD_PLAN | `tools/build_plan.ts` (+ optional `lib/llm-advisor.ts`) | Map source → `FieldSet` values + `BodyPlan` (Điều/Khoản/Điểm tree) |
| COMPILE_REGIONS | `lib/ooxml/{runs,paragraph,clause,table,numbering}.ts` | Render *only* the replacement OOXML fragments |
| APPLY_REGIONS | `tools/apply_regions.ts` | Splice fragments into the marked regions; rest untouched |
| VALIDATE | `tools/validate_body.ts` | Real structural/XML validation |
| COMPLIANCE_GATE | `lib/thethuc-check.ts` | ND-30 component presence + no leftover tokens + chrome diff |
| VERIFY | existing officecli `view`/`validate` | Final document sanity |

> Keep the existing supervisor/run-state/artifact-store machinery. Retire
> 

> `compile_ops.ts` (dead) and the full-body path in `apply_splice.ts`.
> 

### 5.1 Region-marking mechanism (pick one; recommend A)

The template must tell the pipeline *what is variable*. Three options:

- **A. Word content controls (`<w:sdt>`) — RECOMMENDED.** Each variable region is a
    
    content control with a stable `<w:tag w:val="so_ky_hieu">`. Pros: tag-addressable,
    
    survive reformatting, native Word UX, can't be accidentally split. Cons: template
    
    authors must insert them (one-time setup per template).
    
- **B. Bookmarks.** `<w:bookmarkStart w:name="...">…</w:bookmarkEnd>`. Pros: simple.
    
    Cons: easy to break, ranges fragile across edits.
    
- **C. Text tokens `{{so_ky_hieu}}`.** Pros: zero template tooling. Cons: tokens can
    
    be split across runs by Word; need run-merge normalization; fragile in tables.
    

**Recommendation:** implement **A as primary**, with **C as a fallback** (token

normalizer that merges split runs) so existing un-instrumented templates still work.

Document a short "how to mark a template" guide for the office.

---

## 6. Data model

### 6.1 FieldSet (single-value merges — the common case)

```tsx
// schemas/field-set.ts
export type FieldValue =
  | { kind: "text"; runs: InlineRun[] }      // supports bold/italic/underline
  | { kind: "date"; iso: string; display: string } // "Hà Nội, ngày 05 tháng 3 năm 2026"
  | { kind: "lines"; lines: InlineRun[][] }; // e.g. Nơi nhận list

export type FieldSet = Record<string /* tag */, FieldValue>;

// Typical tags for a Quyết định:
//   ten_co_quan, so_ky_hieu, dia_danh_ngay, ten_loai, trich_yeu,
//   can_cu[], noi_dung (-> BodyPlan), chuc_vu_ky, ho_ten_ky, noi_nhan[]
```

### 6.2 InlineRun (closed inline set)

```tsx
export type InlineRun = {
  text: string;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  // no colors/strike/links by default — add only if a real template needs them
};
```

### 6.3 BodyPlan (the "Nội dung" region)

```tsx
export type BodyNode =
  | { type: "dieu"; num: number; title: InlineRun[]; children: BodyNode[] }
  | { type: "khoan"; num: number; content: InlineRun[]; children: BodyNode[] }
  | { type: "diem"; label: string /* a,b,c */; content: InlineRun[] }
  | { type: "para"; align?: "left"|"center"|"justify"; content: InlineRun[] }
  | { type: "cancu"; content: InlineRun[] }      // italic, ends ';' or '.'
  | { type: "table"; rows: InlineRun[][][] }     // simple "danh sách kèm theo"
  | { type: "pagebreak" }
  | { type: "unsupported"; reason: string; raw: string };

export type BodyPlan = { nodes: BodyNode[] };
```

> **Legal numbering is rendered deterministically** from `num`/`label`, never copied
> 

> from the source text. The parser/LLM only identifies *which* node type a line is.
> 

### 6.4 Style binding

```tsx
// resolved from the template's own style table, with confidence + fallback
export type StyleBinding = {
  role: "dieu" | "khoan" | "diem" | "para" | "cancu" | "table" | "tieude";
  styleId: string;
  source: "content_control" | "exact_match" | "heuristic" | "llm" | "default";
  confidence: number; // 0..1
};
```

---

## 7. Component implementation checklist

### 7.1 `lib/template-introspect.ts`

- [ ]  Parse `word/document.xml` + `styles.xml` with a real XML parser (keep
    
    `adm-zip` for the package).
    
- [ ]  Enumerate variable regions: `<w:sdt>` tags (mode A), bookmarks (B), `{{token}}`
    
    scan with split-run merge (C).
    
- [ ]  Locate the **Nội dung region** (between the trích yếu/QUYẾT ĐỊNH line and the
    
    signature block) as an addressable range.
    
- [ ]  Read all `sectPr` (not just the first); record section boundaries.
- [ ]  Emit a `TemplateProfile { fields[], bodyRegion, styleBindings[], sections[] }`.

### 7.2 `lib/field-binding.ts`

- [ ]  Build the expected `FieldSet` schema from `TemplateProfile.fields`.
- [ ]  Mark required vs optional (required: số/ký hiệu, ngày, tên loại, trích yếu,
    
    nội dung, người ký, nơi nhận — configurable per doc type).
    

### 7.3 `lib/source-parse/*`

- [ ]  Use an mdast parser (e.g. `remark`/`micromark`) — drop the line-merge parser.
- [ ]  Produce a structured tree with inline marks intact.

### 7.4 `tools/build_plan.ts` (+ `lib/llm-advisor.ts`)

- [ ]  Deterministic mapping first: map known source sections → field tags by
    
    label/anchor.
    
- [ ]  Detect clause structure (Điều/Khoản/Điểm) by regex + position; renumber
    
    deterministically.
    
- [ ]  **LLM advisor** (bounded) for: (a) free-form source → field tag mapping when
    
    labels are ambiguous; (b) clause-type classification when regex is uncertain;
    
    (c) căn cứ vs nội dung disambiguation. Output is `FieldSet`+`BodyPlan` JSON,
    
    **schema-validated (Zod)**; invalid → reject + fail.
    
- [ ]  LLM never emits XML and never chooses styleIds.

### 7.5 `lib/ooxml/*`

- [ ]  `runs.ts`: `InlineRun[] → <w:r><w:rPr>…</w:rPr><w:t xml:space="preserve">`
    
    with `<w:b/> <w:i/> <w:u w:val="single"/>`; `\n → <w:br/>`.
    
- [ ]  `clause.ts`: render Điều/Khoản/Điểm with correct labels and indentation;
    
    bold "Điều N." label; `a) b) c)` for điểm.
    
- [ ]  `numbering.ts`: only if a template uses real list numbering; otherwise render
    
    labels as literal text (admin docs usually do literal labels — verify per
    
    template).
    
- [ ]  `paragraph.ts`: alignment + style mapping; `table.ts`: simple grid for
    
    "danh sách kèm theo".
    

### 7.6 `tools/apply_regions.ts`

- [ ]  Replace **only** marked regions in `word/document.xml`. Never touch the rest.
- [ ]  Always `copyFileSync` template → output first (template never mutated — keep
    
    the existing invariant from `.opencode/memory/project.md`).
    
- [ ]  Re-pack with `adm-zip`, preserving all other parts byte-identical.

### 7.7 `tools/validate_body.ts` (replace rubber-stamp)

- [ ]  XML well-formedness of `document.xml`.
- [ ]  All required `FieldSet` tags filled.
- [ ]  **No leftover tokens / empty content controls.**
- [ ]  paraId uniqueness; no duplicate IDs introduced.

### 7.8 `lib/thethuc-check.ts` (COMPLIANCE_GATE)

- [ ]  Assert presence of ND-30 components 1–9 (by tag/anchor) in the **output**.
- [ ]  Chrome diff: every part *except* replaced regions must be byte-identical to the
    
    copied template. Any drift → fail.
    
- [ ]  Optional: font/size check (Times New Roman) on rendered runs.
- [ ]  Emit a human-readable compliance report into the run state dir.

---

## 8. LLM usage map (precise)

| Decision point | Deterministic? | LLM role | Output | Guardrail |
| --- | --- | --- | --- | --- |
| Inline bold/italic/underline | ✅ parser | none | — | grammar is exact |
| Điều/Khoản/Điểm detection | ✅ regex + position | fallback only | node type | confidence gate |
| Renumbering | ✅ code | none | — | deterministic |
| Source section → field tag | ⚠️ partial | **primary when ambiguous** | tag mapping JSON | Zod + required-field check |
| Căn cứ vs nội dung split | ⚠️ | fallback | classification | validated |
| Unrepresentable content | ✅ detect | triage message | `unsupported` reason | hard error |
| StyleId / XML | ✅ code | **never** | — | LLM output is text/JSON only |

LLM is "advisor": typed, validated, replaceable by rules. The document is correct

even if the LLM is removed (it just handles fewer ambiguous inputs).

---

## 9. Case-coverage matrix

Two axes (from the redesign): **Syntactic vs Semantic** × **Closed vs Open**.

|  | Closed (enumerable) | Open (needs judgment) |
| --- | --- | --- |
| **Syntactic** | inline marks, line breaks, clause labels, tables → **pure code** | — |
| **Semantic** | known field tags, known doc types → **rules** | ambiguous source→field mapping, clause classification → **LLM advisor** |

Input dimensions to test:

1. Doc type: quyết định / nghị quyết / công văn / tờ trình / thông báo.
2. Region mode: content control / bookmark / token.
3. Edit type: field-only update vs body re-author vs both.
4. Clause depth: Điều→Khoản→Điểm; nested vs flat.
5. Căn cứ list length 0..N.
6. Nơi nhận list length 1..N.
7. Signature authority prefix: TM./KT./Q./TL./TUQ./none.
8. Multi-section / landscape table page.
9. Inline formatting density (bold trích yếu, italic căn cứ).

Anything outside the matrix → `unsupported` with a clear message (e.g. images,

embedded charts, complex merged tables) — **degrade loudly, never silently**.

---

## 10. Test & verification strategy

- **Golden corpus:** 8–12 real (anonymized) office templates + their filled outputs.
    
    Store `template.docx`, `source.md`, `expected.docx`.
    
- **Region-diff test:** assert output == template except inside marked regions.
- **Compliance test:** all 9 ND-30 components present; no leftover tokens.
- **Fidelity metric:** structural match score on rendered runs/clauses (target ≥0.98)
    
    in addition to "coverage 100%". Coverage alone is not correctness (P8).
    
- **Round-trip determinism:** run twice → byte-identical output.
- **Negative tests:** missing required field, unmarked region, unsupported construct
    
    → must fail with the right error code.
    

---

## 11. Rollout

- **M1 (correctness foundation):** template-introspect (mode A + token fallback),
    
    FieldSet model, `apply_regions.ts` (region-only splice), `validate_body.ts`,
    
    compliance gate. **Fixes P1, P2, P6, P8.** Field-only updates work end-to-end.
    
- **M2 (body rendering):** mdast parse, `runs.ts` (inline marks, `<w:br/>`),
    
    `clause.ts` (Điều/Khoản/Điểm), căn cứ italics. **Fixes P3, P4, P5.**
    
- **M3 (structure):** multi-section/sectPr handling, paraId-collision-safe IDs,
    
    simple "danh sách" tables. **Fixes P7.**
    
- **M4 (robust mapping):** style-binding with confidence + LLM advisor sidecar for
    
    ambiguous source→field mapping.
    
- **M5 (hardening):** golden corpus, fidelity metrics, determinism + negative tests.

---

## 12. Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Office templates aren't instrumented with content controls | Ship token-mode fallback + a 1-page "how to mark a template" guide |
| Authority/signature rules vary by org (TM./KT./…) | Keep signature as fields; never auto-generate authority prefix |
| LLM mis-maps a field | Required-field check + compliance gate catch it; fail loud |
| Numbering schemes differ (Điều vs Mục vs số thứ tự) | Per-doc-type numbering config |
| Template uses real list numbering vs literal labels | Detect at introspect; render to match the template, not assumed |

---

## 13. Decision needed before M1

Pick the **region-marking mode** the office can realistically maintain:

- **A (recommended):** we add content controls to each template once. Most robust.
- **C (zero-tooling):** rely on `{{token}}` text in templates. Faster to start,
    
    more fragile.
    

Default assumption for M1 if unanswered: **implement A + C together** (content

controls primary, token fallback), so both instrumented and plain templates work.

---

### Appendix A — Reference sources

- ND 30/2020/NĐ-CP official text — [chinhphu.vn](http://chinhphu.vn)
- Thể thức components (9 main parts) — trích TT-30 summary
- Presentation rules (A4, Times New Roman, Unicode) — Phụ lục I summaries
- Phần/Chương/Mục/Điều/Khoản/Điểm layout — sơ đồ thể thức
- Signature authority prefixes (TM./KT./…) — Điều 13 ND-30 commentary

Vài lưu ý quan trọng về thay đổi tư duy so với plan trước:

1. **Đảo ngược kiến trúc cốt lõi:** với văn bản hành chính, splice toàn bộ body là *sai về bản chất* — nó xóa khối chữ ký + nơi nhận (nằm sau nội dung trong body). Plan mới chuyển sang **chỉ thay vùng được đánh dấu** (content control / bookmark / token), giữ nguyên 100% thể thức.[[1]](https://storage-edu.vnpt.vn/edu-lci/8398/Vanban/12_trich-tt-30.pdf)
2. **IR thu nhỏ mạnh:** không cần general tables/images/code. Chỉ cần Điều/Khoản/Điểm (đánh số theo ND-30), inline bold/italic/underline, line break, danh sách đơn giản.[[4]](http://thcskimchung.pgd-donganh.edu.vn/van-ban-cong-van/so-do-the-thuc-van-ban-hanh-chinh-theo-nghi-dinh-30-2020-nd-cp-nhu-the-nao-cach-trinh-bay-the-thuc-van-ban-hanh-chinh-.html)
3. **LLM lùi về vai trò extractor/mapper** (source → FieldSet/BodyPlan typed JSON), không render XML, không chọn style.
4. Thêm **COMPLIANCE_GATE** kiểm tra 9 thành phần thể thức + không còn token thừa + chrome không đổi ngoài vùng thay.

Một điểm cần bạn quyết trước khi code agent bắt M1 (mục §13): **template của cơ quan sẽ đánh dấu vùng biến đổi bằng cách nào** — dùng *content control* (bền nhất, cần chèn 1 lần) hay chỉ `{{token}}` text (không cần công cụ, nhưng dễ vỡ)? Nếu bạn cho biết, tôi sẽ chốt M1 và có thể phác code khung `template-introspect.ts` + `apply_regions.ts` + `field-set.ts` cho bạn.

Lưu ý: tôi chỉ đọc repo (read-only) — không push, không chạy pipeline, không tạo report.docx hộ được.