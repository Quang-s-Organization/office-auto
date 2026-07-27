# Cấu trúc document: format_template.docx

> Tự động rút trích ngày 2026-07-20 —置信度 (confidence): **0.95**

---

## 1. Thông tin trang

| Thuộc tính | Giá trị |
|---|---|
| Kích thước giấy | A4 (21 × 29.7 cm) |
| Lề trái/phải | 3.5 cm / 1.5 cm |
| Lề trên/dưới | 2.49 cm / 2.01 cm |
| Phông mặc định | Times New Roman 14pt |
| Theme | Office |
| Trang bìa không số | Có (`titlePage=true`) |
| Đoạn văn | 57 (18 đoạn trống dùng làm khoảng trắng) |

## 2. Header / Footer

| Vị trí | Nội dung |
|---|---|
| Header | Style `header`; chứa nội dung ngắn (có thể là merge-field / content control) |
| Footer | Trống — **không** có trường PAGE động |

## 3. Bảng phông & style

### Style dùng cho heading (đánh số tự động via abstractNum 11, numId=1)

| Level | Style | Định dạng số | In đậm | In nghiêng | Căn chỉnh |
|---|---|---|---|---|---|
| 0 | `heading 1` | `CHƯƠNG <n>.` | ✅ | ❌ | center |
| 1 | `heading 2` | `<n>.<n>.` | ✅ | ❌ | both (thả hàng) |
| 2 | `heading 3` | `<n>.<n>.<n>.` | ✅ | ✅ | both (thả hàng) |

Tất cả heading dùng `spaceBefore=6pt`, `lineSpacing=1.5x`.

### Style nội dung

| Style | Vai trò | Đặc điểm |
|---|---|---|
| `Normal` | Base, trang bìa, tiêu đề mục lục | 14pt, có thể bold |
| `Normal_style` | Đoạn thân văn bản | 14pt, căn `both`, thụt đầu dòng 28.35pt, dãn dòng 1.5x |
| `toc 1` | Mục lục cấp 1 (tĩnh) | bold, tab leader dot @ 9072 twips |
| `toc 2` | Mục lục cấp 2 (tĩnh) | indent 13.9pt, tab leader dot @ 9072 |
| `toc 3` | Mục lục cấp 3 (tĩnh) | firstLineIndent 28.35pt, tab leader dot @ 9072 |
| `table of figures` | Danh mục hình (tĩnh) | italic bold, hangingIndent, tab leader dot |
| `Bảng biểu - title` | Chú thích hình/bảng | 11pt, italic, center, dãn 1.2x |
| `List Paragraph` | Tài liệu tham khảo | Arial 11pt, căn both, indent 54pt |

## 4. Cấu trúc tài liệu (trình tự các section)

```
┌── Trang bìa
│   ├── 11 đoạn trống (push content xuống)
│   ├── "BÁO CÁO CHUYÊN ĐỀ"          [Normal, bold, 14pt]
│   ├── 1 đoạn trống
│   └── "NGHIÊN CỨU ..."             [Normal, bold, 15pt]
│
├── Mục lục (TĨNH — không phải trường TOC)
│   ├── "MỤC LỤC"                    [Normal, bold]
│   ├── "Trang"                      [Normal]
│   ├── toc 1: DANH MỤC CÁC KÝ HIỆU  [→ iii]
│   ├── toc 1: DANH MỤC CÁC HÌNH VẼ  [→ iv]
│   ├── toc 1: GIỚI THIỆU            [→ 1]
│   ├── toc 1: CHƯƠNG 1. CƠ SỞ ...   [→ 4]
│   ├── toc 2: 1.1. Tầm quan trọng.. [→ 4]
│   ├── toc 2: 1.2. Các thách thức.. [→ 5]
│   ├── toc 2: 1.3. Các lĩnh vực...  [→ 9]
│   ├── toc 2: 1.4. Các phương pháp..[→ 11]
│   ├── toc 3: 1.4.1. Thu thập...    [→ 11]
│   ├── toc 3: 1.4.2. Tăng cường...  [→ 12]
│   ├── toc 1: KẾT LUẬN              [→ 15]
│   └── toc 1: TÀI LIỆU THAM KHẢO    [→ 15]
│
├── Danh mục ký hiệu, chữ viết tắt
│   ├── "DANH MỤC CÁC KÝ HIỆU..."    [Normal, bold]
│   ├── đoạn trống
│   └── Bảng 11 hàng × 2 cột (ký hiệu ↔ giải nghĩa)
│
├── Danh mục hình vẽ (TĨNH)
│   ├── "DANH MỤC CÁC HÌNH VẼ"      [Normal, bold]
│   ├── "Trang"                      [Normal]
│   └── 3 entry (table of figures)
│
├── NỘI DUNG CHÍNH
│   ├── heading 1: "GIỚI THIỆU"
│   │   └── Normal_style: thân văn bản
│   │
│   ├── heading 1: "CHƯƠNG 1. CƠ SỞ LÝ THUYẾT"
│   │   ├── heading 2: "1.1. Tầm quan trọng..."
│   │   │   ├── Normal: thân
│   │   │   ├── đoạn trống
│   │   │   ├── Hình ảnh
│   │   │   ├── Bảng biểu - title: "Hình 1.1. Các bước..."
│   │   │   ├── heading 3: "1.1.1. Thu thập dữ liệu..."
│   │   │   │   └── Normal_style: thân
│   │   │   │       └── đoạn trống
│   │   │   └── (cấu trúc lặp)
│   │
│   ├── heading 1: "KẾT LUẬN"
│   │   └── Normal_style: thân
│   │
│   └── heading 1: "TÀI LIỆU THAM KHẢO"
│       └── List Paragraph: "[1]. ..."
│
└── (Footer trống — không số trang)
```

## 5. Ngữ pháp khối nội dung (body block grammar)

Mỗi chương tuân theo quy tắc này:

```
heading 1 ("CHƯƠNG <n>. <TIÊU ĐỀ>")
  heading 2 ("<n>.<n>. <tiêu đề>")
    text (Normal_style, thụt đầu dòng)
    text (Normal)
    heading 3 ("<n>.<n>.<n>. <tiêu đề>")
      text (Normal_style)
    [optional] hình ảnh
    [optional] caption (Bảng biểu - title, italic)
```

## 6. Anomalies (lưu ý)

1. **Mục lục tĩnh**: TOC được gõ tay, không phải trường TOC động — phải cập nhật thủ công khi thêm/bớt mục.
2. **Không số trang động**: Footer trống; số trang trong TOC là số tĩnh.
3. **Khoảng trắng bằng đoạn trống**: 18 đoạn rỗng thay vì dùng `spaceBefore`/`spaceAfter`.
4. **Header placeholder**: Header mặc định chứa "51", header khác "v" — có thể là merge-field chưa điền.
5. **Phông 14pt mặc định**: Cao hơn tiêu chuẩn học thuật (12pt) một số trường yêu cầu.
