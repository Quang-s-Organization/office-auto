# Template onboarding (C4) — sinh profile cho một genre mới

> Trả lời câu hỏi *"ai tạo profile cho document type mới?"* trong
> [hardcoded_suspend.md](../hardcoded_suspend.md). Quy trình: **LLM sinh profile
> MỘT LẦN cho mỗi họ template, người review, rồi pipeline chạy deterministic mãi.**
> Profile là *config do LLM sinh, người duyệt* — không phải code, không phải gánh
> nặng viết tay từng cái.

Aim của hệ thống là **cặp nội dung↔template cùng chủ đề** (nghiên cứu→journal
paper; nghị quyết/nghị định→văn bản hành chính). Onboarding một genre = thêm
**một** file `profiles/<id>.json` thoả [profile schema](../schemas/profile.schema.json).
Không sửa tool nào.

## Khi nào cần onboarding

Khi xuất hiện một **cặp (loại nội dung, template) mới** mà chưa có profile khớp —
ví dụ: báo cáo tài chính, đơn từ, hợp đồng, giáo án, biên bản họp.

## Quy trình 4 bước

### Bước 1 — Discover template
```bash
python3 tools/template_inspector.py templates/<new>.docx --out .cache/template.ir.json
```
Cho ra styles/prototypes/body_sequence đã discover (không hardcode).

### Bước 2 — Thu heading-tree của vài sample cùng genre
```bash
python3 tools/markdown-parser.py samples/<genre>-1.md --out /tmp/s1.json
# document_tree = danh sách heading + level + word_count (KHÔNG cần body)
```

### Bước 3 — LLM sinh profile (một lần)
Đưa cho agent (Qwen/OpenCode) **chỉ** heading-tree của các sample + danh sách
logical-section mà template hỗ trợ. Yêu cầu emit một profile JSON. Prompt mẫu:

> Bạn đang onboard một genre tài liệu mới cho một compiler deterministic.
> ĐẦU VÀO: (a) heading-tree của N tài liệu mẫu cùng loại; (b) các style/section
> mà template đích hỗ trợ.
> NHIỆM VỤ: sinh một file profile JSON gồm:
> - `id`, `description`, `strategy:"clone"`, `default_role:"generic"`.
> - `role_vocabulary`: tập role NGỮ NGHĨA (cái-này-LÀ-GÌ), độc lập style. Nếu
>   genre này chia sẻ ontology học thuật, đặt `"extends":"_base"` và chỉ thêm role
>   đặc thù.
> - `role_descriptions`: một dòng gloss mỗi role (đây là menu đóng cho lần phân
>   loại sau).
> - `keyword_rules`: surface-form hay gặp cho mỗi role (uppercase, giữ dấu), xếp
>   theo ĐỘ ƯU TIÊN (đặc thù trước tổng quát; rule có dấu hai chấm như
>   `"QUYẾT ĐỊNH:"` phải đứng trước `"QUYẾT ĐỊNH"`).
> - `front_matter_roles`: role mà template ĐÃ có sẵn (sẽ `preserve`, không in lại).
> - `capabilities`: template render được gì (`toc`, `equation`, `table`, `code`…).
>   `false` ở cái nào template không có.
> - `role_to_logical`: mỗi role → `{section, intent, toc, presentation, outline_level}`.
>   Dùng `"FROM_LEVEL"` cho presentation/outline để giữ heading-style theo markdown.
> RÀNG BUỘC: KHÔNG sinh style/font/paraId. Role phải là tên ngữ nghĩa, không phải
> tên style. Chỉ emit JSON.

### Bước 4 — Validate + review
```bash
python3 tools/contracts.py profiles/<id>.json profile-resolve   # schema + layering OK?
```
Người review:
- Mỗi `role_to_logical[role].section` có tồn tại trong template không?
- Thứ tự `keyword_rules` đúng ưu tiên (disambiguation) chưa?
- `front_matter_roles` có đúng phần template tự lo (tránh in trùng bìa) không?
- `capabilities` phản ánh đúng template (không khai khống) chưa?

Xong là chạy pipeline bình thường — không gọi LLM nữa cho mọi tài liệu cùng genre.

## Kiểm chứng nhanh genre mới
```bash
python3 tools/markdown-parser.py noidung.md --out content.ir.json
python3 tools/semantic_classifier.py --content content.ir.json --profile profiles/<id>.json --output semantic.ir.json
#   thêm --backend router --lazy nếu keyword chưa phủ hết (offline, đa ngữ)
python3 tools/logical_mapper.py --semantic semantic.ir.json --content content.ir.json --profile profiles/<id>.json --output logical.ir.json
#   stderr in [logical] CAPABILITY: … nếu nội dung dùng feature template không có
python3 tools/planner.py --template-ir .cache/template.ir.json --content content.ir.json --logical logical.ir.json -o batch_program.json
```

## Ví dụ tham chiếu
- [profiles/springer-paper.json](../profiles/springer-paper.json) — overlay học thuật (extends `_base`).
- [profiles/vn-thesis.json](../profiles/vn-thesis.json) — overlay đề cương/luận văn VN.
- [profiles/vn-admin.json](../profiles/vn-admin.json) — **standalone** (ontology riêng) + `capabilities` (no TOC/equation) cho văn bản hành chính.
