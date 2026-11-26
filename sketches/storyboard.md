# Storyboard — "Sáng hôm sau, nó tự chạy" (~22s, play-once)

Kể theo logic NGƯỜI XEM, không theo trình tự vận hành của sản phẩm.
Nhịp cảm xúc: **việc dồn dập tới, lặp lại mãi → trợ lý giải dồn dập
→ nó nhớ nhà mình → hôm sau tự chạy.**

Không thuật ngữ trong thoại. Dùng được cho cả CSS/JS animation lẫn
shot list video/Lottie sau này. Có bản cắt 6s (chỉ Scene 2, loop)
cho hero.

> ⚠ **Phụ thuộc feature:** S4 "tự chạy" cần scheduler — `schedule`
> cron trong workflow-layer (phase sau, `plans/261125-1632`) +
> scheduler/launcher tick. Kịch bản giữ payoff này vì feature nằm
> trong lộ trình đã chốt; deploy landing trước feature xong thì S4
> phải đổi thành "một câu thay cả buổi".

## Khung chung — mọi vai đều theo 4 nhịp này

| Nhịp | Giây | Việc của scene |
|---|---|---|
| 1 · Việc dồn, lặp mãi | 0–4 | 3 việc chồng lên + MỘT hệ quả cụ thể có giá; lịch lật, đống hiện lại |
| 2 · Giải dồn | 4–11 | 3 câu nhờ → 3 kết quả, nhịp stamp ~2s/việc; cuối là 1 beat "lần sau gõ vầy" |
| 3 · Nó nhớ | 11–15 | Gõ câu ngắn → stamp xong tức thì (không quay chuỗi) → thoại chứng minh trí nhớ → stamp gài sổ |
| 4 · Tự chạy, mỗi ngày | 15–19 | Lịch lật — mỗi sáng kết quả đã sẵn; silhouette + counter tiết kiệm |
| Kết | 19–22 | "Càng dùng — càng của riêng bạn." DỪNG ở đây + replay/CTA — không autoplay vô hạn |

Nguyên tắc:
1. **Nỗi đau là một ĐỐNG, NÓ LẶP LẠI, VÀ NÓ CÓ GIÁ** — MỘT hệ quả cụ
   thể (một người chờ, một deadline, một con số mất). Bừa thì quen,
   mất thì đau.
2. **S2: 3 task là đủ dồn** — mỗi task ~2s cho câu nhờ + kết quả đọc
   được. Hơn 3 task là danh sách tính năng, không phải câu chuyện.
3. **Trí nhớ chứng minh bằng thoại** — một câu "lần trước bạn…".
   KHÔNG quay lại chuỗi task (nhàm); stamp tức thì đủ.
4. **S4 có người** — silhouette bàn sáng, cà phê, màn hình đã xong +
   counter. Payoff phải chạm, không chỉ thấy.
5. **Trụ "dạy" = beat cuối S2** — "lần sau bạn gõ vầy là được";
   và S3 gõ đúng câu đó. Beat dạy nối beat nhớ.
6. **Play-once, không loop** — phim có mạch nên dừng ở frame payoff;
   chỉ bản cắt 6s loop. Tổng ≤22s.

---

## Vai 1 — Minh · marketing (bản gốc)

- **S1 Việc dồn, mỗi ngày:** Zalo chấm đỏ + Sheet báo giá chưa cập
  nhật + 300 ảnh Canva chờ nén. Lịch lật: Thứ 2 → Thứ 3 → Thứ 4 —
  đống y hệt. Thẻ nổi: *"khách A chờ báo giá từ 8h"*. Chữ: "Sáng
  nào cũng thế này."
- **S2 Giải dồn (~2s/việc):**
  - "đọc hộ tin Zalo" → bot quét, chấm đỏ tắt → "6 hội thoại ·
    3 người đang chờ bạn" ✓
  - "cập nhật sheet theo file này" → bảng đối chiếu hiện ✓
  - "nén mấy ảnh kia" → folder mới gọn → "300 ảnh · gốc nguyên" ✓
  - Beat cuối: bong bóng nhỏ — "lần sau bạn chỉ cần gõ 'việc sáng'
    là được."
- **S3 Nó nhớ:** Minh gõ "việc sáng" → stamp xong tức thì. Trợ lý:
  "mình cập nhật theo mẫu báo giá của công ty bạn như lần trước nhé."
  Thẻ `/viec-sang` đóng dấu gài vào sổ — cầu nối sang tự chạy.
- **S4 Tự chạy, mỗi ngày:** lịch lật y như S1 — mỗi sáng hiện ra kết
  quả: Zalo tóm tắt, sheet xong. Silhouette người + cà phê mở máy.
  Counter: "tiết kiệm ~45 phút." Chữ: "Không cần nhờ — nó tự chạy,
  mỗi sáng."

## Vai 2 — Lan · sales

- **S1 Việc dồn, mỗi tuần:** Excel 3.000 dòng khách, cột tỉnh gõ mỗi
  kiểu + nhóm Zalo "gửi chị list tỉnh em gấp". Lịch lật: tuần 44 →
  45 → 46 — đống y hệt. Thẻ nổi: *"3 khách chờ báo giá từ sáng"*.
  Chữ: "Thứ hai nào cũng thế này."
- **S2 Giải dồn:**
  - "tách theo tỉnh, mỗi tỉnh một file" → "47 file · gốc nguyên" ✓
  - "soạn báo giá cho khách A theo mẫu" → nháp báo giá hiện ✓
  - "lọc ai chưa follow trong sheet này" → list khách cũ trượt ra ✓
  - Beat: "lần sau gõ 'list tuần' là được."
- **S3 Nó nhớ:** "list tuần" → stamp xong. Trợ lý: "mình chia theo
  tỉnh, báo giá theo mẫu công ty bạn như mọi tuần." Thẻ `/list-tuan`
  gài sổ.
- **S4 Tự chạy, mỗi tuần:** lịch lật — mỗi thứ hai folder đã tách sẵn
  + list follow-up chờ. Silhouette + counter "tiết kiệm ~3 giờ."
  "Thứ hai không còn là cơn ác mộng."

## Vai 3 — Hoa · văn phòng / kế toán

- **S1 Việc dồn, mỗi ngày:** hoá đơn rải Downloads + mẫu báo cáo Word
  trống + Outlook 14 mail chưa đọc. Lịch lật — đống y hệt. Thẻ nổi:
  *"sếp cần báo cáo trước 5h"*. Chữ: "Chiều nào cũng thế này."
- **S2 Giải dồn:**
  - "điền file Excel này vào mẫu báo cáo tuần" → bảng Word tự đầy ✓
  - "gom hoá đơn theo tháng" → folder Tháng-10, Tháng-11 xếp hàng ✓
  - "tóm tắt mail chưa đọc" → "14 mail · 3 mail cần trả lời hôm nay" ✓
  - Beat: "lần sau gõ 'việc chiều' là được."
- **S3 Nó nhớ:** "việc chiều" → stamp xong. Trợ lý: "mình điền đúng
  mẫu của công ty bạn như mọi tuần nhé." Thẻ `/viec-chieu` gài sổ.
- **S4 Tự chạy, mỗi ngày:** lịch lật — mỗi chiều nháp điền sẵn + mail
  tóm tắt. Silhouette + counter "tiết kiệm ~1.5 giờ." "Bạn chỉ còn
  một việc: duyệt."

## Vai 4 — Trang · content / SEO

- **S1 Việc dồn, mỗi bài:** 5 bài WP nháp chờ + meta trống đỏ cả cột
  + ảnh thiếu alt. Lịch lật: bài 12 → 13 → 14 — đống y hệt. Thẻ nổi:
  *"bài hôm qua vẫn thiếu meta"*. Chữ: "Bài nào cũng thế này."
- **S2 Giải dồn:**
  - "đăng 5 bài này, nhớ điền meta" → nháp lên, meta/alt đầy —
    "duyệt rồi mới xuất bản" ✓
  - "sửa alt cho cả loạt ảnh cũ" → từng ảnh được gán mô tả ✓
  - "kiểm lại meta mấy bài cũ" → list lỗi trượt ra ✓
  - Beat: "lần sau gõ 'bài mới' là được."
- **S3 Nó nhớ:** "bài mới" → stamp xong, đúng format đúng chuyên mục.
  Trợ lý: "mình điền meta theo cách site bạn vẫn làm nhé." Thẻ
  `/bai-moi` gài sổ.
- **S4 Tự chạy, mỗi bài:** lịch lật — mỗi bài mới checklist meta tự
  xong. Silhouette + counter "tiết kiệm ~30 phút/bài." "Checklist tự
  chạy — bạn chỉ viết."

## Vai 5 — Tuấn · design / Canva

- **S1 Việc dồn, mỗi ngày:** 500 ảnh `design (137).png` rải Downloads
  + web đòi ảnh <200KB + team nhắn "ảnh đâu rồi". Lịch lật — đống y
  hệt. Thẻ nổi: *"sếp hỏi ảnh lúc 3h"*. Chữ: "Cuối ngày nào cũng
  thế này."
- **S2 Giải dồn:**
  - "nén và đổi tên theo tour" → folder sạch, tên thành hàng ✓
  - "ảnh nào còn quá lớn cho web" → list đỏ → nén nốt ✓
  - "gom hết vào folder theo ngày" → Downloads sạch ✓
  - Beat: "lần sau gõ 'ảnh mới' là được."
- **S3 Nó nhớ:** "ảnh mới" → stamp xong. Trợ lý: "mình nén webp 80%,
  tên theo tour, gốc không đụng như mọi lần." Thẻ `/anh-moi` gài sổ.
- **S4 Tự chạy, mỗi ngày:** lịch lật — mỗi chiều export xong là folder
  sạch hiện. Silhouette + counter "việc 40 phút → vài phút."
  "Mỗi chiều."

---

> B2B có người xem và nỗi đau riêng — xem `storyboard-b2b.md`.

---

## Ghi chú thực thi

- **Một engine, nhiều kịch bản:** mỗi vai = config {pains[], stake,
  tasks[], teachWord, memoryLine, recipe, payoffText, timeSaved}.
  `.story` render scene từ config → đổi vai là đổi data.
- **Hai bản:** loop 6s chỉ Scene 2 cho hero; bản ~22s play-once ở
  section `#vong-quay`, dừng ở frame kết + nút replay + CTA.
- **Nhịp S2:** mỗi task ~2s (nhờ → stamp); tick âm thanh nếu có.
- **Nút chọn vai** ("Bạn làm nghề gì?"): marketing / sales / văn
  phòng / content / design. Mặc định marketing (Minh).
- Khi JS off: hiển thị tĩnh Scene 2 của vai mặc định.
- **Asset cần ngoài CSS thuần:** silhouette + cà phê (S4) — duy nhất
  chỗ đáng một Lottie/SVG ngoài; còn lại (đống việc, lịch lật, bot
  quét, stamp) vẽ được bằng CSS.
