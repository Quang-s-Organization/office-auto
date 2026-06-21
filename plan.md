Đã đọc xong toàn bộ. Bây giờ tổng hợp tất cả risks và implementation plan.

***

## Risk Audit — Hiện Trạng Repo

Trước khi vào plan, đây là toàn bộ vấn đề phát hiện được:

### 🔴 Risk Nghiêm Trọng

**R1 — `bash: "deny"` trong config.json làm chết toàn bộ workflow**

Agent bị cấm bash hoàn toàn.  Nhưng `sdt-migration/SKILL.md` yêu cầu agent chạy `officecli add`, `officecli move` — đây là CLI commands, không phải MCP calls.  Nếu agent không thể bash, migration không chạy được. Ngoài ra Step 1 của `docgen-workflow` viết manifest qua bash cũng bị block. 

**R2 — Step 0 và Step 1 trong `docgen-workflow` conflict logic**

Step 0 nói: nếu `manifest.mode == "legacy-anchor"` AND `fields` empty → load sdt-migration. 
Step 1 nói: nếu manifest tồn tại AND `fields` non-empty → skip. Nếu không có manifest → query SDT rồi write.

Vấn đề: **Không có branch xử lý trường hợp manifest chưa tồn tại ở Step 0**. Agent gặp template mới không có manifest sẽ vào Step 0 → fail vì không đọc được file → behavior undefined.

**R3 — `officecli` skill dùng `"op"` key, `docgen-workflow` skill dùng `"command"` key trong batch.json**

`officecli/SKILL.md` viết: `{ "op": "set", ... }` 
`docgen-workflow/SKILL.md` viết: `{ "command": "set", ... }` 

Hai skill dạy agent hai schema khác nhau cho cùng một JSON. Agent sẽ dùng cái nào tùy context → batch fail không đoán được.

### 🟡 Risk Trung Bình

**R4 — `sdt-migration/SKILL.md` thiếu Phase 4 (write manifest)**

Skill kết thúc ở Phase 3 "Re-audit", chỉ nói "Write all tag → path mappings into the manifest JSON" nhưng không có lệnh cụ thể.  Agent sẽ không biết dùng bash hay tool gì để write.

**R5 — `docgen-workflow` Step 0 branch cho "manifest không tồn tại" bị thiếu**

Chỉ có 2 cases: manifest exists+empty → migrate, manifest exists+non-empty → skip. Không có case: manifest file không tồn tại. 

**R6 — `validate-guide.md` thiếu structural invariant checks**

Pass criteria chỉ check `ok: true` + view issues empty + leftover placeholder.  Không check heading order, content deduplication, image presence — đây chính là lý do pipeline báo success dù output sai (từ investigation report).

**R7 — `manifest/SKILL.md` khai báo `repeaters` và `tables` nhưng manifest thực tế không có**

Manifest hiện tại chỉ có `fields`.   Agent đọc skill thấy có `repeaters`/`tables` spec nhưng template không dùng → confusion khi interpret manifest.

### 🟢 Đã Tốt

- `docgen-orchestrator.md` ngắn gọn, hard constraints rõ ràng 
- `officecli/SKILL.md` có DOM restructuring commands đúng syntax 
- `config.json` đã loại bỏ `manifest-server`, chỉ còn `officecli` MCP 
- `sdt-migration` skill tồn tại và đúng procedure 

***

## Implementation Plan

### Phase 1 — Fix Critical Blockers (làm trước, không test được nếu thiếu)

**Task 1.1 — Sửa `bash` permission trong `config.json`**

```json
// THAY ĐỔI:
"permission": {
  "edit": "allow",
  "bash": "allow"   // ← từ "deny" → "allow"
}
```

Lý do: Agent cần bash để chạy `officecli` CLI (migration), write manifest JSON, và write `batch.json` ra disk. 

**Task 1.2 — Thống nhất batch.json schema về `"op"` key**

Trong `docgen-workflow/SKILL.md` Step 4, đổi tất cả `"command"` → `"op"` để khớp với `officecli/SKILL.md`:  

```json
// ĐÚNG (theo officecli skill):
{ "op": "set", "path": "/body/sdt[@tag=\"full_name\"]", "props": { "text": "..." } }
```

**Task 1.3 — Fix Step 0 logic trong `docgen-workflow/SKILL.md`**

Thêm case "manifest không tồn tại":

```markdown
## Step 0 — Classify Template

CASE A: manifests/<id>.manifest.json EXISTS + fields non-empty
  → Skip to Step 3

CASE B: manifests/<id>.manifest.json EXISTS + fields empty
  → Load skill: sdt-migration → run migration → rewrite manifest → back to Step 0

CASE C: manifests/<id>.manifest.json DOES NOT EXIST
  → Run: officecli query <template> /body/sdt --props tag,path,type
  → If SDT tags found → construct and write manifest (see Step 1 format) → go to Step 3
  → If no SDTs found → Load skill: sdt-migration → run migration → go to Step 0
```

***

### Phase 2 — Bổ Sung Missing Content

**Task 2.1 — Thêm Phase 4 vào `sdt-migration/SKILL.md`**

```markdown
## Phase 4: Write Manifest File

After Phase 3 re-audit, get all tags:
```bash
officecli query <file> /body/sdt --props tag,path
```

Write manifest using bash heredoc:
```bash
cat > manifests/<template_id>.manifest.json << 'EOF'
{
  "template_id": "<template_id>",
  "mode": "strict-sdt",
  "locale": "vi-VN",
  "fields": {
    "<tag>": {
      "sdt_tag": "<tag>",
      "resolved_path": "/body/sdt[@tag=\"<tag>\"]",
      "type": "scalar",
      "required": false
    }
  }
}
EOF
```
Rules:
- template_id = filename without .docx
- One entry per tag from query output
- DO NOT invent tags not found in query
- Verify after write: cat manifests/<template_id>.manifest.json
```

**Task 2.2 — Thêm structural validation vào `validate-guide.md`**

Thêm section mới sau "Pass Criteria":

```markdown
## Structural Invariant Checks (academic documents)

After basic validation passes, run heading order check:
```bash
officecli query <output> /body/p --props style,text | grep -i "heading"
```

Expected order for format_template:
1. Heading 1: GIỚI THIỆU
2. Heading 1: CƠ SỞ LÝ THUYẾT
3. Heading 1: ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI
4. Heading 1: KẾT LUẬN
5. Heading 1: TÀI LIỆU THAM KHẢO

FAIL if: any Heading 1 appears after TÀI LIỆU THAM KHẢO.

Content deduplication check:
```bash
officecli query <output> /body/p[@style="Normal"] --props paraId,text
```
If body paragraphs exist OUTSIDE SDTs: flag as W_DUPLICATE. Do not deliver.
```

**Task 2.3 — Trim `manifest/SKILL.md` bỏ repeater/table spec**

Remove hoặc comment out `Repeater` và `Table fill` sections vì template hiện tại không dùng.  Giữ lại để tham khảo nhưng đánh dấu rõ `(not used in current templates)` để agent không bị confused.

***

### Phase 3 — Rebuild Template + Test

**Task 3.1 — Rebuild template sạch từ template thầy**

```
1. Copy template_thay.docx → templates/format_template_clean.docx
2. Run: officecli query templates/format_template_clean.docx /body/p --props paraId,text,style
3. Identify heading paraIds theo đúng thứ tự: GIỚI THIỆU → CƠ SỞ → ỨNG DỤNG → KẾT LUẬN → TÀI LIỆU
4. Run sdt-migration Phase 1-4 để wrap từng section
5. Verify: officecli query /body/sdt --props tag,path → phải có đủ 13 tags
6. Write manifests/format_template_clean.manifest.json
```

**Task 3.2 — Test end-to-end**

```
Input:  templates/format_template_clean.docx
        manifests/format_template_clean.manifest.json  
        noidung.md (content source)

Run:    docgen-workflow Step 3-7
        → batch.json constructed
        → officecli batch execute
        → officecli validate
        → structural invariant check (Phase 2.2)

Expected: report_v2.docx với heading đúng thứ tự, không có extra paragraphs
```

***

### Thứ Tự Thực Hiện

```
[Ngay bây giờ]
Task 1.1 → config.json bash:allow          (5 phút)
Task 1.2 → fix "command" → "op"            (5 phút)
Task 1.3 → fix Step 0 logic                (15 phút)

[Tiếp theo]
Task 2.1 → sdt-migration Phase 4           (10 phút)
Task 2.2 → validate-guide structural check (15 phút)
Task 2.3 → trim manifest skill             (5 phút)

[Sau khi markdown xong]
Task 3.1 → rebuild template sạch          (30-60 phút tùy template thầy)
Task 3.2 → test end-to-end                (verify)
```
