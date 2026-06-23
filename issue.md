# Issues with report.docx

## 1. Content Placement — Sai vị trí (Critical)

**Vấn đề**: Toàn bộ nội dung từ `noidung.md` bị **chèn vào cuối template**, sau cả mục SUPERVISOR'S COMMENTS. Kết quả là một tài liệu có:

- Các phần template cũ: ACKNOWLEDGEMENTS, ABSTRACT, TABLE OF CONTENTS, CHAPTER 1–5, REFERENCES, APPENDIX, SUPERVISOR'S COMMENTS
- Rồi mới đến nội dung thật: CƠ SỞ LÝ THUYẾT, ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI, TÀI LIỆU THAM KHẢO

**Hậu quả**: Nội dung chính trở thành phụ lục. Template có CHAPTER 2. LITERATURE REVIEW nhưng không được dùng — lẽ ra nội dung này phải thay thế hoặc được đặt trong CHAPTER 2.

## 2. Document Outline Hierarchy — Sai cấu trúc phân cấp (Critical)

**Vấn đề**: Tất cả các heading H2 bị lồng sai cấp cha. Cấu trúc outline hiện tại:

```
TÀI LIỆU THAM KHẢO (H1)
  ├── Retrieval-Augmented Generation... (H2)    ← sai, phải nằm dưới "ỨNG DỤNG..."
  ├── Tối ưu hóa hiệu năng... (H2)               ← sai
  │   ├── Tăng cường dữ liệu ảnh (H3)             ← sai, phải nằm dưới "CƠ SỞ..."
  │   └── Thu thập dữ liệu ảnh thủ công (H3)      ← sai
  ├── Các phương pháp sinh dữ liệu... (H2)         ← sai
  ├── Các lĩnh vực ứng dụng chính (H2)            ← sai
  ├── Các thách thức phổ biến... (H2)              ← sai
  └── Tầm quan trọng dữ liệu ảnh... (H2)          ← sai (phải là H2 đầu tiên)
```

**Nguyên nhân**: Chèn tuần tự bằng anchor chaining (`--after`) vào cuối document mà không thiết lập cấu trúc heading hierarchy đúng trong OOXML. Outline level của heading không được đồng bộ với document-level TOC/outline XML.

## 3. First-Line Indent — Thiếu thụt đầu dòng (High)

**Vấn đề**: 54/54 body paragraphs (100%) thiếu `first-line indent`. Đây là yêu cầu định dạng chuẩn cho văn bản học thuật tiếng Việt (thường thụt 1.27cm hoặc 2 ký tự).

**Phạm vi**: Tất cả body paragraphs từ `7FF22229` đến `7FF222A1`.

## 4. Font Size Heading1 — Không đồng nhất (High)

**Vấn đề**: Các heading "CHAPTER..." trong template dùng **16pt Calibri** (với explicit `markRPr.size=16pt`), nhưng các heading mới chèn vào dùng **24pt** (effective từ default Heading1 style). Cụ thể:

| Heading | Font Size | Font eastAsia |
|---------|-----------|---------------|
| CHAPTER 1 | 16pt | Calibri |
| CƠ SỞ LÝ THUYẾT | 24pt | Times New Roman |
| CHAPTER 2 | 16pt | Calibri |

**Nguyên nhân**: Clone prototype là heading "ACKNOWLEDGEMENTS" (14pt), nhưng effective style lại là 24pt từ `/styles/Heading1`. Template CHAPTER headings có explicit run properties (`markRPr`) override xuống 16pt nhưng không được sao chép.

## 5. Font Face Heading2 — Sai font (Medium)

**Vấn đề**: Template Heading2 prototype dùng **Calibri** (eastAsia), nhưng các H2 mới dùng **Times New Roman** cho cả ASCII và eastAsia. Gây mất nhất quán font chữ trong toàn bộ tài liệu.

## 6. Heading3 Formatting — Không có prototype trong template (Medium)

**Vấn đề**: Template không có sẵn Heading3 prototype. Script tạo H3 bằng cách clone H2_PROTO rồi gán `style=Heading3`. Tuy nhiên, việc này không đảm bảo:

- Font size H3 đúng chuẩn (thường 12-13pt)
- Run properties (bold, spacing) được kế thừa từ style định nghĩa
- Không có bookmark/outline-level tương ứng

## 7. Không xử lý được các thành phần Markdown đặc biệt (Medium)

**Vấn đề**: `noidung.md` chứa:

- **Hình ảnh**: `[Hình 1.1. Các bước xây dựng mô hình...]` → được xử lý như body text thông thường, không phải hình ảnh
- **Công thức LaTeX**: `$\tilde{x} = \lambda x_i + (1 - \lambda)x_j$` → giữ nguyên chuỗi text, không được render
- **Bold/Italic**: Markdown formatting (`**bold**`) mất trong quá trình chuyển đổi

## 8. Tham chiếu bị đảo thứ tự trong document (Medium)

**Vấn đề**: Dù content.ir.json có tham chiếu theo thứ tự [1], [2], ..., [13], nhưng trong output document, thứ tự xuất hiện trong outline vẫn có dấu hiệu bất thường về thứ tự sắp xếp do anchor chaining ngược.

## 9. Template sections trống — Giữ nguyên section không có nội dung (Low)

**Vấn đề**: Template chứa các section như "ACKNOWLEDGEMENTS", "ABSTRACT", "CHAPTER 1", "CHAPTER 3–5", "APPENDIX", "SUPERVISOR'S COMMENTS" vẫn giữ nguyên. Không có nội dung tương ứng trong `noidung.md`, tạo ấn tượng tài liệu chưa hoàn chỉnh.

## 10. Thiếu cập nhật Table of Contents (Low)

**Vấn đề**: Template có TABLE OF CONTENTS section, nhưng nội dung mới không được cập nhật vào TOC fields. Khi mở trong Word, TOC sẽ hiển thị sai hoặc không hiển thị nội dung mới.

---

## Tóm tắt Root Cause

1. **Thiếu analysis template structure trước khi insert** → không xác định được vị trí chèn phù hợp (CHAPTER 2)
2. **Anchor chaining sai** → chèn `--after` cuối document thay vì chèn vào đúng vị trí
3. **Không clone đúng prototype** → mất explicit font/size properties
4. **Không xử lý được heading hierarchy trong OOXML** → outline bị hỏng
5. **Markdown parser quá đơn giản** → mất thông tin về ảnh, công thức, định dạng inline
