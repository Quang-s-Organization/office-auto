# Kiến Trúc Workspace & Nhược Điểm Hiện Tại

---

## 1. Tổng Quan Workspace

`office-auto` là một hệ thống sinh tài liệu DOCX tự động sử dụng AI, vận hành dựa trên:

- **OpenCode framework**: nền tảng AI agent có khả năng load skill và gọi MCP tools
- **LLM**: Qwen3.6-35B-A3B-GGUF chạy qua sglang endpoint
- **OfficeCLI MCP**: bộ công cụ thao tác DOCX (query/set/batch/add/get/validate/view...)
- **Skill system**: các file markdown chứa hướng dẫn từng bước cho LLM
- **Triết lý Zero-Script**: mọi logic đều là markdown instructions, không có Python/JS

Kiến trúc tổng thể là một **pipeline 12 bước** do agent `docgen-orchestrator` điều phối, đọc nội dung từ `noidung.md` và đổ vào template `format_template.docx` thông qua SDT (Structured Document Tags).

---

## 2. Kiến Trúc Skills Agent Design

### 2.1. Agent Design Pattern

Agent được định nghĩa trong `.opencode/agents/docgen-orchestrator.md` với cấu trúc:

```
YAML front matter:
  - name, version, description
  - tools: officecli.*, bash
  - skills: danh sách skill cần load
---
Body:
  - Role description
  - Pipeline overview (12 bước)
  - Hard constraints
  - Key fixes learned từ thực tế
```

Agent hoạt động ở **chế độ primary** (single agent, không có sub-agents). Nó là "bộ não" duy nhất điều phối toàn bộ pipeline.

### 2.2. Skill Structure Pattern

Mỗi skill nằm trong `.opencode/skills/<skill-name>/` và tuân theo cấu trúc:

```
<skill-name>/
├── SKILL.md              # File chính: YAML frontmatter + instructions
├── assets/               # (Optional) Template JSON, examples
└── references/           # (Optional) Tài liệu tham khảo chi tiết, load JIT
```

**Nguyên lý Progressive Disclosure**: `SKILL.md` chỉ chứa procedure cốt lõi (<120 dòng), còn chi tiết nằm trong `references/` - chỉ được load vào context khi cần đến bước đó.

### 2.3. 5 Skills Hiện Có

| Skill | Vai trò | Version |
|-------|---------|---------|
| **docgen-workflow** | Pipeline chính 12 bước - trái tim của hệ thống | v3 |
| **officecli** | Syntax reference cho MCP tool officecli | v1 |
| **manifest** | Schema cho file manifest.json | v1 |
| **docx-template** | Hướng dẫn tạo template SDT | v1 |
| **sdt-migration** | Chuyển đổi template legacy-anchor sang strict-sdt | v2 |

### 2.4. Skill Loading Flow

```
opencode.json
  └── default_agent: "docgen-orchestrator"
        └── .opencode/config.json
              └── agent.docgen-orchestrator
                    ├── skills: [docgen-workflow, officecli, manifest]
                    ├── tools: [officecli.*, bash]
                    └── model: sglang/Qwen3.6-35B-A3B-GGUF
                          │
                          ▼
                    OpenCode framework
                    └── đọc agent MD → phát hiện skills list
                         └── load từng .opencode/skills/<name>/SKILL.md
                              └── inject vào system prompt của LLM
```

Skill `docx-template` và `sdt-migration` không nằm trong agent config mặc định, chỉ được load khi agent chủ động gọi (on-demand).

### 2.5. Skill Dependency Graph

```
docgen-orchestrator (agent)
├── docgen-workflow (skill)
│   ├── references/content-strategies.md   → chọn strategy A/B/C
│   ├── references/content-rules.md        → luật trích xuất verbatim
│   ├── references/validation-checks.md    → kiểm tra S1-S8
│   ├── references/audit-guide.md          → debug manifest rỗng
│   ├── references/normalize-guide.md      → format ngày/tháng/số
│   └── assets/batch-template.json         → mẫu batch JSON
│
├── officecli (skill)
│   ├── references/error-codes.md          → mã lỗi E_*/W_*
│   └── references/batch-template.json     → cấu trúc batch operation
│
└── manifest (skill)
    └── references/field-types.md          → field type reference

[On-demand]:
├── docx-template → references/section-registry.md
└── sdt-migration → (self-contained)
```

### 2.6. Pipeline 12 Bước Chi Tiết

**Pre-flight**: load `content-strategies.md` để biết cách phân loại section
**Bước 0**: Đọc manifest, xác định template mode (strict-sdt / legacy-anchor)
**Bước 1**: Audit template → sinh manifest (nếu chưa có)
**Bước 2**: Validate manifest
**Bước 3**: Với mỗi section, chọn Strategy A (SDT batch) / B (paragraph insert) / C (skip)
**Bước 4**: Trích xuất nội dung **verbatim** từ noidung.md (tuyệt đối không tóm tắt)
**Bước 5**: Xây dựng `batch.json` cho các section Strategy A
**Bước 6**: Chạy `officecli batch`
**Bước 7**: Insert section Strategy B bằng `officecli add --after`
**Bước 8**: **Verbatim self-check**: đọc lại nội dung, so sánh 80 ký tự đầu + word count
**Bước 9**: Post-process: `officecli refresh`
**Bước 10**: Validation (S1-S8 checks)
**Bước 11**: Copy output → `out/report.docx`
**Bước 12**: Report kết quả

### 2.7. Three Content Strategies (Cốt Lõi Của Hệ Thống)

```
Strategy A (SDT Batch Fill):
  ├── Điều kiện: heading trong noidung.md khớp chính xác với source_section trong manifest
  ├── Hành động: build batch.json → officecli batch
  └── Áp dụng cho: 8/10 SDTs (chuong1_heading, chuong1_tamquantrong_body, ...)

Strategy B (Paragraph Insert):
  ├── Điều kiện: không có SDT, nhưng template có heading chứa text tương ứng
  ├── Hành động: query heading → officecli add --after
  └── Áp dụng cho: các section phụ không có SDT

Strategy C (Skip):
  ├── Điều kiện: SDT tồn tại nhưng không có source section tương ứng
  ├── Hành động: không làm gì cả (để trống)
  └── Áp dụng cho: gioi_thieu_body, ketluan_body
```

### 2.8. Manifest System

Hai file manifest nằm trong `manifests/`:

- **format_template.manifest.json**: 10 field definitions với sdtId, tag, type, source_section, verbatim flag
- **format_template.struct-spec.json**: section registry với 14 entries, phân loại replace/insert, heading order invariants

---

## 3. OfficeCLI Tool Integration

### 3.1. Cấu Hình MCP

OfficeCLI được expose như MCP tool thông qua:

```json
// opencode.json
"mcp": {
  "officecli": {
    "type": "local",
    "command": ["officecli", "mcp"],
    "environment": { "OFFICECLI_NO_AUTO_RESIDENT": "0" }
  }
}
```

### 3.2. Các MCP Tools Có Sẵn

| Tool | Chức năng | Dùng trong pipeline |
|------|-----------|---------------------|
| `officecli query` | Truy vấn cấu trúc DOCX (SDT, heading, paragraph) | Bước 0, 3, 7 |
| `officecli set` | Set text cho SDT | Bước 6 (fallback) |
| `officecli batch` | Thực thi hàng loạt operation | Bước 6 |
| `officecli add` | Thêm paragraph mới | Bước 7 |
| `officecli get` | Đọc lại nội dung đã ghi | Bước 8 (self-check) |
| `officecli validate` | Validate DOCX structure | Bước 10 |
| `officecli view` | Xem document outline | Bước 10 |
| `officecli refresh` | Post-process document | Bước 9 |
| `officecli move` | Di chuyển paragraph | Agent notes |
| `officecli dump` | Dump raw structure | Debug |
| `officecli merge` | Merge documents | (chưa dùng) |
| `officecli remove` | Xóa elements | Agent notes (orphan removal) |

### 3.3. Path Syntax

OfficeCLI dùng XPath-like syntax để address elements:
- `/body/sdt[@sdtId=N]` → SDT by numeric ID (ưu tiên)
- `/body/sdt[@tag="name"]` → SDT by tag name
- `/body/p[N]` → paragraph by index
- `p[style=Heading2]` → heading by style

**Quy tắc quan trọng**: Luôn dùng `@sdtId` thay vì `@tag` hoặc positional index để tránh lỗi do thay đổi cấu trúc.

---

## 4. Nhược Điểm Của Workspace Hiện Tại

### 4.1. Về Kiến Trúc

| # | Nhược Điểm | Mô Tả | Severity |
|---|-----------|-------|----------|
| 1 | **Cấu hình trùng lặp giữa opencode.json và .opencode/config.json** | Cả 2 file đều định nghĩa MCP, agent config, model. Dễ gây desync khi sửa 1 file mà quên file kia. | **Cao** |
| 2 | **Thiếu versioning/schema validation cho manifest** | Manifest là JSON nhưng không có schema validation. LLM có thể tạo manifest sai cấu trúc mà không được cảnh báo sớm. | **Cao** |
| 3 | **Không có cơ chế retry tự động khi pipeline fail** | Nếu LLM hallucinate ở bước nào đó, pipeline fail hoàn toàn. Không có fallback strategy. | **Cao** |
| 4 | **Single agent, không có specialized sub-agents** | Agent hiện tại làm tất cả: audit, classify, extract, batch, insert, validate. Không có separation of concerns. | **Trung bình** |
| 5 | `.opencode/` và `.commandcode/` **cùng tồn tại không rõ ràng** | `.commandcode/` chứa plan cũ đã được thực thi, không còn giá trị. Gây confusion về cấu trúc workspace. | **Thấp** |

### 4.2. Về Skill System

| # | Nhược Điểm | Mô Tả | Severity |
|---|-----------|-------|----------|
| 6 | **Skill không được load mặc định đầy đủ** | Agent config chỉ load 3/5 skills. `docx-template` và `sdt-migration` phải được gọi thủ công, LLM có thể quên. | **Cao** |
| 7 | **Thiếu skill versioning mechanism** | Skill có version trong frontmatter nhưng không có cơ chế tự động kiểm tra/cập nhật. LLM có thể dùng skill cũ. | **Trung bình** |
| 8 | **Không có skill testing** | Không có cách nào test skill riêng lẻ. Phải chạy cả pipeline mới biết skill có hoạt động đúng không. | **Trung bình** |
| 9 | **Content-rules.md bị duplicate** | Verbatim rules xuất hiện cả trong SKILL.md (inline) và content-rules.md (reference). Dễ gây inconsistency. | **Thấp** |

### 4.3. Về Pipeline

| # | Nhược Điểm | Mô Tả | Severity |
|---|-----------|-------|----------|
| 10 | **Verbatim self-check dùng 80 ký tự đầu không đủ tin cậy** | So sánh 80 ký tự đầu có thể pass kể cả khi LLM hallucinate ở phần sau. Cần so sánh toàn bộ hoặc dùng tỷ lệ match cao hơn. | **Cao** |
| 11 | **Pipeline phụ thuộc hoàn toàn vào LLM** | Nếu LLM không follow instruction chính xác (vd: tóm tắt thay vì copy verbatim), pipeline sinh ra output sai. | **Cao** |
| 12 | **Không có rollback mechanism** | Nếu pipeline fail ở bước 10, file DOCX đã bị modify từ bước 6. Không có cách nào rollback về trạng thái ban đầu. | **Cao** |
| 13 | **Content planning ở bước 3 là LLM reasoning thuần túy** | Content plan không được lưu thành file JSON, chỉ tồn tại trong working memory của LLM. Nếu context bị reset, mất plan. | **Trung bình** |
| 14 | **Không có caching cho template đã audit** | Mỗi lần chạy pipeline đều audit lại template từ đầu, kể cả khi template không thay đổi. | **Trung bình** |
| 15 | **Strategy B (paragraph insert) dùng heading text matching không chính xác** | Chỉ dùng `contains` case-insensitive, có thể match nhầm heading. Cần dùng heading index hoặc paraId. | **Trung bình** |
| 16 | **Không có dry-run mode** | Không có cách nào xem pipeline sẽ làm gì trước khi thực sự chạy. | **Thấp** |

### 4.4. Về Testing

| # | Nhược Điểm | Mô Tả | Severity |
|---|-----------|-------|----------|
| 17 | **Test hoàn toàn thủ công** | tests/ chỉ có markdown hướng dẫn chạy tay. Không có automated test. | **Cao** |
| 18 | **Chỉ có 1 template test** | Format_template là template duy nhất. Không biết pipeline có hoạt động với template khác không. | **Cao** |
| 19 | **Thiếu integration test cho MCP tools** | Không có test nào verify rằng officecli MCP hoạt động đúng với các edge cases. | **Trung bình** |
| 20 | **Expected structure chỉ có 1 bộ invariants** | expected_structure.json cứng nhắc, không thể tái dùng cho template khác. | **Trung bình** |

### 4.5. Về Documentation & Maintenance

| # | Nhược Điểm | Mô Tả | Severity |
|---|-----------|-------|----------|
| 21 | **Thiếu architecture diagram dạng hình ảnh** | README.md có mô tả kiến trúc dạng text, không có diagram trực quan. | **Trung bình** |
| 22 | **Root directory có file lộn xộn** | `noidung.md`, `research-improve-pipeline.md`, `report.docx` nằm ở root. Cần tổ chức lại vào thư mục `sources/`, `docs/`, `outputs/`. | **Thấp** |
| 23 | **Thiếu changelog** | Không có file nào ghi lại lịch sử thay đổi của pipeline, skill, manifest. | **Thấp** |

### 4.6. Về Security & Reliability

| # | Nhược Điểm | Mô Tả | Severity |
|---|-----------|-------|----------|
| 24 | **Không có input validation cho noidung.md** | LLM có thể nhận file input sai format (không có heading, sai encoding) mà không được cảnh báo. | **Trung bình** |
| 25 | **Không có backup cho template gốc** | Pipeline modify template trực tiếp. Nếu lỗi, template gốc có thể bị hỏng. | **Trung bình** |
| 26 | **Không có permission boundary giữa agent và system** | Agent có bash:allow và edit:allow, có thể can thiệp vào file system ngoài pipeline. | **Trung bình** |
| 27 | **SDT batch dùng set --prop text= mất style** | Agent notes đã phát hiện lỗi này: set text làm mất style của heading. Phải manual restore style. | **Thấp** (đã có workaround) |

---

## 5. Tóm Tắt

### Điểm Mạnh

- **Zero-script philosophy**: giảm dependency, dễ maintain
- **Skill-based architecture**: modular, dễ mở rộng
- **Progressive disclosure**: tối ưu token consumption
- **Verbatim enforcement**: đảm bảo độ chính xác của nội dung
- **Three content strategies**: linh hoạt trong việc xử lý N→M mismatch

### Điểm Yếu Chính Cần Cải Thiện

1. **Pipeline quá phụ thuộc vào LLM reliability** - cần thêm validation layers và retry mechanisms
2. **Không có automated testing** - mọi thứ đều manual, khó phát hiện regression
3. **Single agent không scale** - cần tách thành specialized sub-agents
4. **Cấu hình trùng lặp** - opencode.json vs .opencode/config.json
5. **Thiếu rollback và caching** - pipeline không an toàn khi fail
6. **Chỉ 1 template test** - không đảm bảo pipeline generalized

---

*Document tạo ngày 2026-06-22 bởi architecture analysis.*
