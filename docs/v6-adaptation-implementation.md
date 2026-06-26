# v6 Adaptation — implementation (Phases 1–6)

> Hiện thực hoá [adaptation_research.md](../adaptation_research.md), **trừ trục A**
> (docx/html/pdf readers — vẫn markdown input). Mỗi phase giữ **parity tuyệt đối**:
> `batch_program.json` byte-identical với flow cũ; E2E S1–S8 xanh
> (docx build 3.3s, validator PASSED). Adaptation = **cặp nội dung↔template cùng
> chủ đề** (paper→journal, nghị định→hành chính), không phải nhồi nội dung lệch genre.

## Bất biến chống-bloat (anti-bloat invariant)
> Thêm biến thiên trên **một** trục (block kind / genre) KHÔNG tốn code trên trục kia.

| Trục | Trước | Sau |
|------|-------|-----|
| **B. Content-element** | thêm block kind = sửa parser + planner + count (3–4 chỗ) | thêm **1 BlockSpec** trong `block_specs.py` |
| **C. Genre** | profile phẳng, trùng ~70% role | `_base` ontology + overlay chỉ chứa delta |

## Các tệp mới
| Tệp | Vai trò |
|-----|---------|
| `schemas/content.ir.schema.json`, `schemas/profile.schema.json` | **Contract** (C1+A1) — fail-loud ở biên |
| `tools/contracts.py` | validate + `resolve_profile` (merge `extends` overlay chain) |
| `tools/inline.py` | inline→runs tokenizer (tách khỏi `markdown-parser.py` để import được) |
| `tools/block_specs.py` | **BlockSpec registry** (B2): parse+emit+count mỗi kind ở MỘT nơi; B3 escape hatch |
| `tools/role_matcher.py` | **offline char-ngram cosine** (S2) — đa ngữ, deterministic, 0 hallucinate, numpy-only |
| `tools/capabilities.py` | **capability negotiation** (§5) — degrade gracefully khi content↔template lệch |
| `profiles/_base.json` | **universal role ontology** (C3) — 9 role chung + placement |
| `profiles/vn-admin.json` | genre **văn bản hành chính** (standalone + `capabilities`) |

## Phase-by-phase

### P1 — Contracts (C1+A1)
JSON-Schema cho Content IR + Profile. Tools load qua `contracts.load_and_validate` /
`resolve_profile` → input sai gãy LOUD ngay, không lặng lẽ ra DOCX hỏng. Schema khớp
dữ liệu thật (artifact + 2 profile pass).

### P2 — BlockSpec registry (B2 + B3)
`block_specs.py` gom 3 operation mỗi block kind. `markdown-parser.parse_body_blocks`
và `planner.emit_blocks` giờ **iterate registry**, không if-elif. **Thêm element =
thêm 1 BlockSpec.** Unknown kind → degrade về paragraph nhất quán (emit==count), vá
luôn một latent bug cũ (unknown kind emit 1 para nhưng count 0).

### P3 — Profile ontology + layering (C3 + C2)
`_base.json` giữ 9 role chung + `role_to_logical` (byte-identical giá trị cũ).
`springer-paper`/`vn-thesis` thành overlay `extends:"_base"` chỉ chứa lexicon + role
đặc thù. `resolve_profile` merge: vocab union, keyword_rules replace/`_extra` prepend,
role_to_logical + `role_overrides`. Resolved → tái tạo 16/18 role, parity byte.

### P4 — Semantic router (S2 + S5), **opt-in**
`--backend router [--lazy]`. Tier-1 keyword (conf 0.9) → tier-2 char-ngram cosine tới
`role_descriptions` → tier-3 lazy đọc `first_paragraph` cho heading mơ hồ. Default
`keyword` giữ parity tuyệt đối. Đo trên content học thuật: generic 2→0.

### P5 — Capability negotiation (§5) + genre hành chính
Profile khai `capabilities` (template render được gì). `logical_mapper` so với feature
content dùng → ghi `capability_report` + cảnh báo + gate TOC. **Opt-in**: profile không
có `capabilities` ⇒ 0 đổi (parity). `vn-admin` minh chứng: QUYẾT ĐỊNH→doc_type,
"QUYẾT ĐỊNH:"→promulgation (disambiguation đúng), no-TOC. Chạy nội dung có equation qua
template `equation:false` → flag degraded, không gãy.

### P6 — Template onboarding (C4)
[template-onboarding.md](template-onboarding.md): quy trình LLM sinh profile MỘT LẦN
cho mỗi genre + checklist review. Profile = config LLM-gen, human-reviewed.

## Dùng nhanh
```bash
# genre mặc định (paper), parity flow:
python3 tools/markdown-parser.py noidung.md --out content.ir.json
python3 tools/semantic_classifier.py --content content.ir.json --profile profiles/springer-paper.json -o semantic.ir.json
python3 tools/logical_mapper.py --semantic semantic.ir.json --content content.ir.json --profile profiles/springer-paper.json -o logical.ir.json
python3 tools/planner.py --template-ir .cache/template.ir.json --content content.ir.json --logical logical.ir.json -o batch_program.json
python3 tools/doc_composer.py --template templates/format_template.docx --batch batch_program.json --output out/report.docx
python3 tools/validator.py out/report.docx --template-ir .cache/template.ir.json --content content.ir.json

# knobs mới:
#   --backend router --lazy   (semantic_classifier: phủ heading keyword không bắt được)
#   profiles/vn-admin.json     (genre hành chính, có capability negotiation)
#   python3 tools/contracts.py <file> content.ir|profile|profile-resolve   (validate thủ công)
```

## Chưa làm (ngoài scope đợt này)
- **Trục A** — docx/html/pdf readers (user chủ động hoãn).
- **P4 thị giác** — template phân biệt `logical_section`/`toc` (adaptation hiện chứng
  minh ở tầng logical; payoff thị giác cần template hành chính/journal riêng — đúng ghi
  chú trung thực trong [design-hierarchical-semantic-ir.md](design-hierarchical-semantic-ir.md)).
- **Sequential classification đầy đủ (S3)** — router hiện là per-node; khai thác thứ tự
  genre là bước nâng cấp tiếp.
- **LLM stage-2 thật** — `--backend router --lazy` là cầu nối offline; LLM pass vẫn ghi
  semantic.ir.json tay qua agent + `--check`.
