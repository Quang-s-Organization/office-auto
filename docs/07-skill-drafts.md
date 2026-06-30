# 07 — Bản nháp 2 Skill (thuần markdown)

> Hiện thực hoá [02](02-system-design.md) + [06](06-self-discovery-and-induction.md) thành `SKILL.md` **thuần markdown** (đúng yêu cầu của thầy: skill dạy agent *cách dùng lệnh* pandoc/officecli, **không** đóng gói script). Đây là *bộ khung khởi điểm* — tinh chỉnh bằng eval ([01 §7](01-skill-design-methodology.md)).

Hai nguyên tắc xuyên suốt cả hai skill:
- **Self-describing tools:** dạy agent **hỏi** công cụ (`pandoc --list-extensions`, `officecli help docx <el>`) thay vì nhồi mọi cờ vào skill → tổng quát + không lỗi thời.
- **Determinism nằm ở CLI, không ở token:** skill mô tả **recipe lệnh** (low-freedom cho thao tác giòn); phán đoán (induct cấp/loại) để cho LLM (high-freedom). Đây là cách dung hoà "thuần markdown" với khuyến nghị "ưu tiên xác định" của Anthropic.

Đặt tại `.opencode/skills/<name>/SKILL.md` hoặc `.claude/skills/<name>/SKILL.md` (OpenCode đọc cả hai).

---

## A. Skill 1 — `inducing-doc-structure`

```markdown
---
name: inducing-doc-structure
description: >
  Induces the structural grammar of any hierarchical document (legal documents,
  contracts, standards, reports) from a .docx and writes it to a Markdown +
  JSON structure spec. Discovers heading levels, numbering schemes (roman/decimal/
  alpha, delimiters), auto-vs-manual numbering, and formatting BY PROBING the file,
  not by assuming a fixed template. Use when converting .docx to a structure
  outline, extracting a document skeleton/format, or when the user mentions
  Thông tư/Nghị định/Quyết định/Nghị quyết/Hướng dẫn, "bóc khung", "định dạng đầu mục".
---

# Inducing Document Structure

You DISCOVER the document's rules; you do NOT assume them. Output is evidence-backed.
Tools: pandoc only (read), plus your own ad-hoc Lua/jq you generate at runtime.

## Tool-probe rule
Tools are self-describing — query them, don't guess:
`pandoc --list-extensions=docx` · `pandoc --help`. If a behavior is uncertain, test on the file.

## Workflow (copy this checklist; tick as you go)
```
- [ ] 1 PROBE   : dump AST + evidence, build inventories (NO judgement yet)
- [ ] 2 INDUCE  : propose >=1 Structure Grammar hypotheses
- [ ] 3 VERIFY  : re-sequence from each rule, score coverage & fit, pick/iterate
- [ ] 4 EMIT    : write structure-spec.md + structure-spec.json with confidence + anomalies
```

### 1 PROBE  (deterministic; run exactly)
```bash
F="$1"
pandoc -f docx+styles -t json "$F" > ast.json        # source of truth
pandoc -f docx+styles -t markdown "$F" > human.md      # for your reading/QA
pandoc -f docx+styles "$F" -L probe.lua -t native >/dev/null 2> evidence.tsv
```
Generate `probe.lua` from the template in references/probing.md (emits one row per
structural block: kind, style, header-level, leading-ordinal, indent).
Build three inventories from ast.json + evidence.tsv — see references/inventories.md:
**style inventory**, **numbering inventory** (ListAttributes + ordinal-text patterns),
**ordered sequence**. Do not label levels yet.

### 2 INDUCE  (your judgement; propose, don't commit)
Select applicable primitives from references/primitives.md (detect-style-clusters,
detect-ordinal-patterns, detect-auto-vs-manual, infer-nesting-from-order-and-indent,
infer-reset-rule, cluster-by-format-signature, propose-level-labels). Compose them into
one or more candidate **Structure Grammars** (schema in references/grammar-schema.md).
You MAY use references/priors.md (common patterns incl. Vietnamese legal) as STARTING
hypotheses — but they are priors, not rules; verification decides.

### 3 VERIFY  (deterministic check against THIS document)
For each hypothesis: regenerate the expected ordinal sequence from its rules and compare
to the observed sequence. Compute **coverage** (% structural blocks classified) and
**sequence-fit** (% ordinals matching). Keep the best; if coverage<~0.95 or fit is low,
return to step 2 and revise (loop, max 3 rounds). See references/verify.md.

### 4 EMIT
Write `structure-spec.md` (human outline) and `structure-spec.json` (machine, for the
building skill). Include detected_type (or "unknown"), per-level signal+numbering+format
+examples, a confidence score, and an explicit anomalies list. Never hide low confidence.

## Anti-assumptions
- A "heading" may appear as Header, as Div{custom-style}, OR as a plain Para with the
  ordinal as literal text — check all three (see references/probing.md).
- Numbering may be auto (ListAttributes) or manual (text). Record numbering.source; a
  wrong guess makes the build skill double-number.
- Flush boundary: if the .docx was just written by officecli, it must have been saved
  first or pandoc reads it empty.

## References (loaded on demand)
- references/probing.md      — probe.lua template, the 3 AST shapes of a heading
- references/inventories.md  — how to build the 3 inventories from ast.json
- references/primitives.md   — the structural reasoning primitives (atomic modules)
- references/grammar-schema.md — Structure Grammar schema (the IR contract)
- references/verify.md       — re-sequencing & scoring
- references/priors.md       — common patterns (VN legal + generic) as PRIORS only
```

**Vì sao bố cục này:** `SKILL.md` < 500 dòng, đóng vai *mục lục*; chi tiết nặng (probe.lua, priors, schema) ở `references/` nạp khi cần ([01 progressive disclosure](01-skill-design-methodology.md)). Workflow + checklist + feedback loop theo best-practices. Phán đoán (Pha 2) high-freedom; probe/verify (Pha 1,3) low-freedom.

---

## B. Skill 2 — `building-docx-from-structure`

```markdown
---
name: building-docx-from-structure
description: >
  Builds a .docx from a structure spec (the output of inducing-doc-structure),
  reproducing FORMAT not content: heading levels, numbering schemes/delimiters,
  bold/caps/alignment/indent. Fills bodies with placeholder text. Uses officecli
  only. Verifies via round-trip parity. Use when generating a Word file from an
  extracted structure/skeleton, or recreating a document's format.
---

# Building DOCX from Structure

You reproduce FORMAT, not content. Content may be placeholder ("Nội dung Điều N...").
Tool: officecli only. Build base: the bundled officecli-docx skill conventions.

## Help-first rule
officecli is self-describing and version-pinned: `officecli help docx <element>`
(paragraph, style, numbering, abstractnum, num, table, section). When unsure of a prop
name/enum, consult help — help is authoritative over this skill.

## Workflow (copy checklist)
```
- [ ] 1 LOAD+VALIDATE : read structure-spec.json; reject if malformed
- [ ] 2 SEED FORMAT   : styles + numbering definitions (Path C dump-template if available, else define)
- [ ] 3 COMPILE       : spec -> one officecli `batch` array (the plan artifact)
- [ ] 4 BUILD         : run batch; placeholder bodies
- [ ] 5 FLUSH+VERIFY  : save; re-probe with the inducing skill; diff grammar (format-only)
- [ ] 6 ITERATE       : fix batch for any parity mismatch; repeat 3-5
```

### Choose a build path (see references/paths.md)
- **Path C (preferred when a reference .docx exists):** `officecli dump ref.docx /styles`
  and `dump ref.docx /numbering` -> replay into the new doc to seed REAL style+numbering
  definitions, then add the body. Most faithful, least error-prone.
- **Path B (default):** define styles + abstractNum/num, then compile the whole body into
  ONE `batch` array.
- **Path D:** if a {{placeholder}} template exists and only content varies, use `merge`.

### Numbering (match what was induced)
- numbering.source=auto -> use listStyle=ordered / numId+ilvl so Word renders the ordinal;
  set scheme via abstractNum format (decimal/upperRoman/lowerLetter...) and the reset rule.
- numbering.source=manual -> write the ordinal as literal text exactly; do NOT also auto-number.
Recipe (verified): `add /numbering --type abstractnum --prop format=decimal` ->
`add /numbering --type num --prop abstractNumId=0` -> `add /body --type paragraph
--prop numId=1 --prop ilvl=0 ...`. See references/numbering.md and `help docx abstractnum`.

### Format per level
Map each level's induced format to props: bold/all_caps(->uppercase text)/align/size/indent.
Use paragraph style when available (`--prop style=...`), else direct props.
Heading styles: name them "Heading 1".. and set outline level so a re-probe sees Headers
(critical for parity — see references/parity.md).

### 5 FLUSH+VERIFY  (round-trip parity = evaluator-optimizer)
```bash
officecli save "$OUT"      # MANDATORY before pandoc reads it (resident/flush trap)
```
Run inducing-doc-structure on "$OUT" -> grammar_out. Diff grammar_out vs the input spec on
FORMAT fields only (level, scheme, delim, bold, caps, align, indent) — ignore content.
Report a parity table (per level: match/mismatch). Any mismatch -> fix batch, loop.

## Discipline (from officecli-docx)
- Quote paths with `[]`; single-quote values with `$`. listStyle is a paragraph prop.
- numId must exist before use. Build with `batch`, not 50 loose calls.
- `save`/`close` before any non-officecli read. Assume there are problems; do one
  fix-and-verify cycle that finds zero issues before declaring done.

## References (on demand)
- references/paths.md      — the 4 build paths + when each is optimal
- references/numbering.md  — abstractNum/num recipes per scheme & reset
- references/parity.md     — round-trip diff procedure & parity scoring
- references/spec-schema.md — the structure-spec.json contract (mirror of skill 1)
```

---

## C. Cây thư mục đề xuất
```
.opencode/skills/
├── inducing-doc-structure/
│   ├── SKILL.md
│   └── references/  (probing.md, inventories.md, primitives.md,
│                     grammar-schema.md, verify.md, priors.md)
└── building-docx-from-structure/
    ├── SKILL.md
    └── references/  (paths.md, numbering.md, parity.md, spec-schema.md)
```
- **Hợp đồng dùng chung:** `grammar-schema.md` (skill 1) ≡ `spec-schema.md` (skill 2) — giữ đồng bộ; đây là Format IR ([02 §2](02-system-design.md)).
- **Thuần markdown:** mọi `references/*.md` là văn bản; `probe.lua`/`batch.json`/`jq` là thứ **agent sinh ra lúc chạy** từ mẫu trong references, **không** ship sẵn dưới dạng script — tôn trọng ràng buộc của thầy đồng thời vẫn đẩy được tính xác định xuống pandoc/officecli.
- **Khởi điểm Skill 2:** copy `~/.opencode/skills/officecli-docx/SKILL.md` làm nền, thêm phần "build theo structure-spec" + parity.

## D. Việc cần làm để biến nháp thành thật
1. Thu thập mẫu: 5 loại VN + ≥3 ngoài miền (hợp đồng, TCVN, tài liệu EN) vào `samples/`.
2. Viết `references/grammar-schema.md` (chốt IR) trước tiên — xem [02 §2](02-system-design.md).
3. Viết `probe.lua` mẫu + `primitives.md`; chạy Pha 1–3 trên samples, chỉnh tới coverage/fit cao.
4. Skill 2: ưu tiên Path C với 1 docx mẫu/loại; nếu không, Path B.
5. Round-trip parity tới ngưỡng; chạy **zero-prior test** ([06 §7](06-self-discovery-and-induction.md#7-generalization)) để đo độ tổng quát thật.
