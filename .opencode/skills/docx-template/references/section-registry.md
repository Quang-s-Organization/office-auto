# Section Registry — Document Section Classification

Classify every template section BEFORE running the generation pipeline.
Each section belongs to exactly one mode: PRESERVE, SYNC, or REPLACE.

> **Note**: This classification system was originally designed for SDT-based templates.
> In the v2 refined pipeline (Clone DOM Builder), SYNC mode is rarely needed because
> content is built from scratch via `add --from + set`. REPLACE mode is the default.
> PRESERVE rules still apply to front matter, TOC, headers/footers.

## Classification Decision Tree

```
CÂU HỎI 1: Section có chứa nội dung academic/chương không?
  → YES → REPLACE (clone từ prototype + set text)

CÂU HỎI 2: Section chứa metadata tự động (TOC, danh mục hình)?
  → YES → PRESERVE + `refresh` sau cùng

CÂU HỎI 3: Section chứa bảng/danh sách cần đồng bộ với nội dung mới?
  → YES → SYNC (query → diff → patch)

CÂU HỎI 4: Section là cấu trúc trang (bìa, header, footer, watermark)?
  → YES → PRESERVE tuyệt đối

Default (không rõ): PRESERVE. Không suy luận — tra content.ir.json section list.
