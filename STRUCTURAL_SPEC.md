# Document Structural Specification

## Target Document: format_template.docx

### Chapter Structure
| Chapter | Heading Text | SDT Heading Tag | Sections |
|---------|-------------|-----------------|---------|
| Giới thiệu | GIỚI THIỆU | (no heading SDT) | Body content |
| Chương 1 | CƠ SỞ LÝ THUYẾT | chuong1_heading | Tầm quan trọng, Thu thập dữ liệu |
| Chương 2 | ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI | chuong2_heading | SLM, RAG, Responsible AI |
| Kết luận | KẾT LUẬN | (no heading SDT) | Body content |
| Tài liệu tham khảo | TÀI LIỆU THAM KHẢO | (no heading SDT) | References list |

### Source Mapping (noidung.md → template SDT)
| noidung.md H1/H2 | Template SDT Tag |
|-----------------|-----------------|
| GIỚI THIỆU | gioi_thieu_body |
| # CƠ SỞ LÝ THUYẾT | chuong1_heading |
| ## Tầm quan trọng dữ liệu ảnh huấn luyện... | chuong1_tamquantrong_body |
| ## Thu thập dữ liệu ảnh thủ công | chuong1_thuchap_body |
| # ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI | chuong2_heading |
| ## Small Language Models / Edge AI | chuong2_slm_body |
| ## RAG + Knowledge Management | chuong2_rag_body |
| ## Responsible AI | chuong2_responsibleai_body |
| KẾT LUẬN | ketluan_body |
| TÀI LIỆU THAM KHẢO | tlthamkhao_list |

### Full SDT List
| # | Tag | Type | Source Chapter |
|---|-----|------|----------------|
| 1 | gioi_thieu_body | body_text | Giới thiệu |
| 2 | chuong1_heading | heading1 | Chương 1 |
| 3 | chuong1_tamquantrong_body | body_text | Chương 1 |
| 4 | chuong1_thuchap_body | body_text | Chương 1 |
| 5 | chuong2_heading | heading1 | Chương 2 |
| 6 | chuong2_slm_body | body_text | Chương 2 |
| 7 | chuong2_rag_body | body_text | Chương 2 |
| 8 | chuong2_responsibleai_body | body_text | Chương 2 |
| 9 | ketluan_body | body_text | Kết luận |
| 10 | tlthamkhao_list | body_text | Tài liệu tham khảo |

### Invariants (MUST NEVER BE VIOLATED)
- Total H1 headings in output: exactly 5 (GIỚI THIỆU, CƠ SỞ LÝ THUYẾT,
  ỨNG DỤNG..., KẾT LUẬN, TÀI LIỆU THAM KHẢO)
- Figure captions ([Hình X.X...]) MUST have style=Caption/Bảng biểu - title, NOT Heading
- Heading text MUST NOT include numeric prefix "1." — template uses unnumbered Heading 1
- All body content: verbatim from noidung.md, no summarization
