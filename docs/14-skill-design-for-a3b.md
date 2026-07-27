# 14 — Thiết kế Skill cho Qwen3.6-A3B (trả lời câu hỏi của thầy)

> **Câu hỏi gốc của thầy (qua bạn):** *"Skill dài, chi tiết mấy nghìn dòng có tốt không? Model nhỏ như Qwen3.6-35B-A3B dùng được skill dài không? — Thầy có những bộ skill siêu dài, cứ nghiên cứu đi."* File này trả lời **dứt điểm, có bằng chứng tier cao**, và rút ra **luật thiết kế cụ thể** cho model 3B-active. Bổ sung [01](01-skill-design-methodology.md) (phương pháp luận) + [09](09-model-qwen3.6-a3b.md) (model) + [10](10-context-and-time-management.md) (context).

## Mục lục
- [1. Câu hỏi đặt SAI — đặt lại cho đúng](#1-đặt-lại)
- [2. Bằng chứng: mật độ chỉ dẫn giết model, không phải độ dài file](#2-bằng-chứng)
- [3. Vì sao A3B ở đầu dễ vỡ của phổ](#3-a3b)
- [4. Nghịch lý & lời giải: scaffold NHIỀU, density ÍT](#4-nghịch-lý)
- [5. "Skill mấy nghìn dòng của thầy" thực ra là gì](#5-skill-thầy)
- [6. 10 luật thiết kế cho A3B](#6-mười-luật)
- [7. Ngân sách chỉ dẫn (đo được)](#7-ngân-sách)
- [8. Checklist áp cho 3 skill của ta](#8-checklist)

---

## 1. Đặt lại
Câu "skill dài có hại model nhỏ không?" trộn lẫn hai thứ khác nhau:
- **Độ dài TỔNG của skill** (SKILL.md + mọi reference/script) — thứ **nằm trên đĩa**.
- **Mật độ chỉ dẫn ĐỒNG THỜI** trong cửa sổ context *tại một bước* — thứ model **thực sự phải xử lý cùng lúc**.

Bằng chứng (§2) chỉ đúng một điều: **cái giết hiệu năng là (2), không phải (1).** Một skill 3000 dòng mà mỗi lúc chỉ nạp ~200 dòng liên quan **an toàn hơn** một skill 400 dòng nhồi 40 chỉ dẫn phải thoả **cùng lúc**. ⇒ Câu hỏi đúng: *"Làm sao để, tại mỗi bước, model A3B chỉ đối mặt số chỉ dẫn tối thiểu?"* Trả lời: **progressive disclosure + phân rã bước** (§4, §6).

> Nói cách khác: **thầy đúng** (skill có thể siêu dài & chi tiết) **và bạn đúng** (A3B không nuốt nổi một prompt dài, dày đặc) — hai điều này **không mâu thuẫn**; chúng được hoà giải bằng *kiến trúc thông tin*, không bằng "viết ngắn lại".

## 2. Bằng chứng
Tier cao, mới, và **đo trên cả model nhỏ** (link [08](08-sources.md) + dưới):

- **IFScale — "How Many Instructions Can LLMs Follow at Once?"** ([arXiv 2507.11538](https://arxiv.org/abs/2507.11538)): benchmark 500 chỉ dẫn đồng thời. Kết quả chốt hạ:
  - **Ngay cả model frontier tốt nhất chỉ đạt ~68%** ở mật độ 500 chỉ dẫn. Không model nào miễn nhiễm.
  - **Ba dạng suy giảm:** *threshold decay* (model reasoning mạnh: gần hoàn hảo tới ngưỡng rồi rơi), *linear decay* (gpt-4.1, claude-sonnet-4), ***exponential decay* (gpt-4o, llama-4-scout — nhóm YẾU HƠN)**. Model càng yếu, đường cong càng dốc.
  - **Universal primacy effect:** chỉ dẫn ở **đầu** được tuân thủ tốt hơn ở giữa/cuối → giới hạn attention.
  - **Lỗi dịch từ "sửa sai" sang "BỎ QUÊN"** khi tải nặng: model *lặng lẽ bỏ* chỉ dẫn, không báo.
- **"Through the Valley"** ([arXiv 2506.07712](https://arxiv.org/abs/2506.07712)): huấn/đẩy long-CoT vào **model nhỏ** làm **tụt mạnh** (Gemma3-1B rớt ~25% baseline); **model nhỏ hồi phục kém/không hồi phục**, model lớn hồi nhanh. → Tải nhận thức nặng phạt model nhỏ **không đối xứng**.
- **Lost-in-the-Middle / Context Rot / NoLiMa / RULER** ([10 §2](10-context-and-time-management.md#2-độ-chính-xác)): độ chính xác rơi theo độ dài **dù model "đủ chỗ"**; hình chữ U theo vị trí; distractor giống-nghĩa hại nhất. Đúng cho **cả** Qwen/GPT/Claude/Gemini.
- **Anthropic Agent Skills** ([best-practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)): *"context window là tài sản chung"*, giữ SKILL.md **< 500 dòng**, đẩy chi tiết ra file con nạp-khi-cần; **progressive disclosure** là nguyên lý lõi.

> Tổng hợp: **số chỉ dẫn đồng thời ↑ ⇒ độ tuân thủ ↓ (exponential với model yếu), và lỗi thành "bỏ quên lặng lẽ".** Đây chính xác là chế độ hỏng ta phải tránh cho A3B.

## 3. A3B
Qwen3.6-35B-A3B: **35B tổng, ~3B active/token** ([09](09-model-qwen3.6-a3b.md)). Hệ quả:
- **Suy luận một-bước ≈ tầm model 3–4B** — yếu hơn frontier nhiều. Nó **không** "hiểu ngầm" một khối chỉ dẫn dài, nhiều nhánh, mơ hồ.
- Theo IFScale, A3B thuộc **nhóm đường cong dốc** (gần *exponential decay*): thêm vài chỉ dẫn đồng thời là rớt nhanh.
- Theo "Through the Valley", A3B **hồi phục kém** khi bị quá tải → một khi lạc, khó tự gỡ.
- Chạy **local trong OpenCode**: mỗi lượt **re-prefill toàn history** ([10 §3](10-context-and-time-management.md#3-thời-gian-bộ-nhớ)) → context dày còn phạt **tốc độ** mỗi lượt.

⇒ A3B cần **nhiều scaffolding cấu trúc** (để bù suy luận yếu) nhưng **rất ít chỉ dẫn đồng thời** (để không vượt ngưỡng). Đó là nghịch lý §4.

## 4. Nghịch lý
**Nghịch lý:** model yếu cần *hướng dẫn kỹ hơn* (nhiều chi tiết) **nhưng** lại *chịu tải kém hơn* (ít chỉ dẫn đồng thời). Giải bằng cách **tách hai trục**:

| Trục | A3B cần | Cơ chế |
|---|---|---|
| **Độ chi tiết TỔNG** (trên đĩa) | **CAO** (recipe cụ thể, ví dụ đã kiểm chứng, ít mơ hồ) | reference/*.md, script agent sinh khi chạy |
| **Mật độ ĐỒNG THỜI** (trong context/bước) | **THẤP** (mỗi bước 1 việc, ít lựa chọn) | progressive disclosure + phân rã checklist |

**SELF-DISCOVER** ([06 §2](06-self-discovery-and-induction.md#2-nền-tảng-học-thuật)) khớp đúng: *scaffolding tường minh giúp model YẾU nhiều nhất*. Nhưng scaffolding phải là **chuỗi bước gọn**, không phải một đống luật phẳng. Tức: **cấu trúc hoá kiến thức để tại mỗi thời điểm chỉ một lát mỏng, tín-hiệu-cao, ít chỉ dẫn được kích hoạt.**

## 5. Skill thầy
"Skill mấy nghìn dòng" của thầy **không** phải mấy nghìn dòng chỉ dẫn *đồng thời*. Gần như chắc chắn nó là:
- **`SKILL.md` mỏng** (vài trăm dòng) — vai trò *mục lục + router + workflow*.
- **Nhiều `reference/*.md`, `EXAMPLES.md`, `scripts/*`** — **chỉ nạp khi nhánh đó được chạm** (progressive disclosure — [01 §1](01-skill-design-methodology.md#1-progressive-disclosure)). Ví dụ chính chủ: skill `pdf/` của Anthropic = SKILL.md ngắn + FORMS.md + reference.md + examples.md + scripts.
- Model chỉ **trả token cho nhánh nó dùng**. "Mấy nghìn dòng" là **tổng thư viện**, không phải **cửa sổ làm việc**.

⇒ **Thầy không sai.** Bài học: **bắt chước *kiến trúc* (mỏng + phân tầng), đừng bắt chước *độ dài phẳng*.** Nếu bê nguyên "mấy nghìn dòng" vào một `SKILL.md` để A3B nuốt cùng lúc → rơi vào chế độ hỏng §2. Cùng nội dung, tách tầng → an toàn.

> Kiểm chứng nhanh với thầy: mở một skill "siêu dài" của thầy ra — đếm **`SKILL.md` bao nhiêu dòng** vs **tổng reference**. Gần như chắc SKILL.md < 500, phần còn lại là file con nạp-khi-cần. Đó là bằng chứng trực quan cho cả lớp.

## 6. Mười luật
Luật thiết kế skill cho A3B (áp cho cả 3 skill — [12](12-two-flows-and-routing.md)):

1. **`SKILL.md` = mục lục + router + workflow, < 500 dòng.** Mọi chi tiết nặng → `references/` nạp khi cần.
2. **Một bước = một hành động.** Checklist tuần tự (PROBE→…, CONVERT→…), mỗi ô **một việc kiểm được**. Không gộp 5 quyết định vào một đoạn văn.
3. **Một reference active tại một thời điểm.** Tham chiếu **sâu 1 cấp** ([01 §8](01-skill-design-methodology.md#8-đặc-tả-kỹ-thuật-skillmd)); tránh A→B→C. Nhánh loại trừ nhau → tách file (mục lục §2 IFScale: bớt chỉ dẫn đồng thời).
4. **Ít lựa chọn: 1 default + 1 lối thoát.** Không "dùng pandoc HOẶC officecli HOẶC…". Nêu đường tối ưu, ghi escape hatch ở cuối (chống *decision overload* của A3B).
5. **Đặt chỉ dẫn tối quan trọng ở ĐẦU và CUỐI mỗi khối** (primacy+recency — IFScale/Lost-in-Middle). Đừng chôn "phải `save` trước pandoc" ở giữa.
6. **Đẩy trạng thái ra ĐĨA, không giữ trong đầu model.** IR/inventory/`body.docx` là bộ nhớ ngoài; nạp lát cắt JIT ([10 §4](10-context-and-time-management.md#4-chín-kỹ-thuật)). A3B giữ ít state.
7. **Verify bằng CLI/logic xác định, KHÔNG tin model "tự đúng".** Vì lỗi A3B là *bỏ quên lặng lẽ* (§2) → phải có bước máy-kiểm (coverage/parity/checklist nhị phân).
8. **Recipe giòn = freedom thấp; phán đoán = freedom cao** ([01 §4](01-skill-design-methodology.md#4-degrees-of-freedom)). Lệnh pandoc/officecli: chép đúng từng dòng. Chọn loại/nhãn cấp: để model, có verify.
9. **Thuật ngữ nhất quán, không thông tin gắn-mốc-thời-gian trong luồng chính** ([01 §9](01-skill-design-methodology.md#9-anti-patterns)). A3B dễ lẫn từ đồng nghĩa (field/box/element).
10. **Đúng 3 skill, description tách bạch + "When NOT to use"** (chống *phase transition* — [01 §10](01-skill-design-methodology.md#10-góc-nhìn-học-thuật)): quá nhiều skill chồng lấn ⇒ A3B **chọn sai skill**.

**Bổ sung vận hành (từ [09](09-model-qwen3.6-a3b.md)):** `--jinja` cho tool-calling; **thinking BẬT** ở bước phán đoán (induce/verify), **TẮT** ở bước cơ học (convert/build) để tiết kiệm context; `-c` ~32–48K, **không** 262K; tool/skill ít tham số.

## 7. Ngân sách
Gợi ý **đo được** cho A3B (tinh chỉnh bằng test thật — con số là điểm khởi đầu, không phải chân lý):

| Đại lượng | Ngân sách A3B | Vì sao |
|---|---|---|
| Chỉ dẫn **đồng thời** phải thoả / 1 bước | **≤ 5–7** | IFScale: model yếu rớt nhanh khi vượt; giữ dưới "khuỷu" đường cong |
| Số bước trong 1 workflow | **4–6** (checklist) | mỗi bước 1 việc; dài hơn → tách sub-flow |
| Lựa chọn / 1 quyết định | **1 default + 1 escape** | tránh decision overload |
| `SKILL.md` | **< 500 dòng** (thực tế nhắm 150–300) | Anthropic; đủ cho mục lục+router+workflow |
| Reference nạp / 1 bước | **1 file, ≤ 1–2K token** | progressive disclosure; 1 active tại 1 thời điểm |
| `-c` context làm việc | **32–48K** | effective < claimed; re-prefill mỗi lượt ([10 §7](10-context-and-time-management.md#7-ngân-sách)) |

> **Cách kiểm "quá tải":** nếu một bước bắt A3B thoả > ~7 ràng buộc cùng lúc, **tách bước**. Nếu nó bắt đầu **bỏ quên** ràng buộc (không báo lỗi mà lặng lẽ thiếu) → đúng triệu chứng §2 → giảm mật độ, đừng thêm lời.

## 8. Checklist áp cho 3 skill
Rà 3 skill ([12 §6](12-two-flows-and-routing.md#6-kiến-trúc)) theo §6:
- [ ] Mỗi `SKILL.md` < 500 dòng, là **mục lục+router+workflow**; chi tiết ở `references/`.
- [ ] Workflow **4–6 bước**, mỗi bước **1 hành động** kiểm được (checklist copy-in).
- [ ] Tham chiếu **1 cấp**; nhánh loại trừ ⇒ tách file; **1 reference active/bước**.
- [ ] Mỗi quyết định **1 default + 1 escape**; không liệt kê nhiều lựa chọn.
- [ ] Chỉ dẫn "must" (save-trước-pandoc, đừng-số-đúp) đặt **đầu/cuối** khối, không giữa.
- [ ] Mọi bước giòn có **verify bằng CLI** (coverage/parity/checklist), không tin tự-đúng.
- [ ] 3 description **tách bạch** input đặc trưng + có **"When NOT to use"**.
- [ ] **Test trên Qwen3.6-A3B thật** (Claude A viết / A3B chạy — [01 §7](01-skill-design-methodology.md#7-evaluation-driven-development)); nếu A3B *bỏ quên bước* → giảm mật độ bước đó.

---
### Nguồn chính (mới, ngoài [08](08-sources.md))
- IFScale — How Many Instructions Can LLMs Follow at Once?: https://arxiv.org/abs/2507.11538
- Through the Valley — Long CoT for Small Language Models: https://arxiv.org/abs/2506.07712
- Anthropic — Skill authoring best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- (Nền context: Lost-in-Middle / Context Rot / RULER — [10 §2](10-context-and-time-management.md#2-độ-chính-xác))
