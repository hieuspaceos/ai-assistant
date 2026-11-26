---
title: "Viết lại copy landing page bằng lời người dùng — bỏ jargon, trả lời câu hỏi thực dụng"
description: "Rà soát toàn bộ từ ngữ trên site/index.html + story.js: thay 'não AI' và jargon kỹ sư (MCP, connector, ed25519, pack, fleet console...) bằng lời người văn phòng và chủ doanh nghiệp thật sự dùng; thêm các câu trả lời còn thiếu (não AI tốn tiền không, trợ lý luôn hỏi trước khi gửi/đăng/xoá, kênh liên hệ B2B)."
status: in-progress
priority: P1
effort: S
branch: main
tags: [site, landing, copy, positioning]
created: 2026-11-26
depends-on: review 4 góc nhìn (marketing / content / chủ DN / NVVP) — đã chốt với user
---

# Plain-copy sweep cho landing page

## Bối cảnh

Review 4 góc nhìn (2026-11-26) kết luận: story animation đã chạm cảm
xúc tốt, nhưng trang còn nhiều chỗ viết cho kỹ sư thay vì người đọc —
nặng nhất là section `#cho-cty` (B2B) và các điểm chạm "não AI".
Người dùng văn phòng không hiểu "não AI" là gì; chủ doanh nghiệp lạc
hoàn toàn ở 4 thẻ B2B. Ngoài ra 3 câu hỏi thực dụng chưa được trả lời:
não AI có tốn tiền không, trợ lý có gửi nhầm tin không, liên hệ cty
ở đâu (GitHub là rào cản với chủ DN Việt).

Nguyên tắc viết lại: **mọi câu phải vượt qua bài test "nhân viên
văn phòng đọc to có hiểu không"** — không thuật ngữ Anh trừ tên app
thật; khái niệm kỹ thuật phải quy về kết quả người dùng thấy.

## Danh mục đổi từ ngữ (đề xuất — user duyệt/chỉnh khi làm)

### Hero + sơ đồ hệ thống (`index.html` ~dòng 42–100)

| Hiện tại | Đề xuất |
|---|---|
| Tagline "làm việc thật · dạy bạn làm chủ trợ lý" | "làm việc thật · dạy bạn tự làm" |
| Box "Não AI bạn chọn" / sub "Devin, Gemini, Codex, Claude, OpenCode, Goose" | "AI bạn chọn" / sub "Claude, ChatGPT, Gemini… — dùng tài khoản bạn đã có" (xem Quyết định 1) |
| Figcaption "Não bên dưới, app bạn dùng xung quanh." | "Trợ lý ở giữa — app bạn dùng xung quanh, AI bạn chọn bên dưới." |
| aria-label sơ đồ "não AI nối vào…" | đổi đồng bộ "AI bạn chọn nối vào…" |
| Thêm 1 dòng dưới cụm nút hero | "Phần mềm miễn phí, mã nguồn mở — cần tài khoản AI bạn đã có (Claude, ChatGPT…)." (xem Quyết định 2) |

### Vòng quay (`index.html` lead + `.loop-cap`; `story.js`)

| Hiện tại | Đề xuất |
|---|---|
| "trợ lý sinh thêm trợ lý con chuyên việc" | "trợ lý tạo thêm trợ lý riêng cho từng việc" |
| "gói thành skill; gộp vài skill thành một trợ lý con chuyên một việc" | "gói thành một công thức; gộp vài công thức thành trợ lý riêng cho một việc" (khớp metaphor "công thức" + `/viec-sang` trên màn hình) |
| "nháp báo giá sẵn duyệt" (Lan) | "bản nháp báo giá chờ duyệt" |
| "nháp lên · meta đầy · chờ duyệt" (Trang) | "đăng nháp xong · meta đầy · chờ duyệt" |
| "list khách cần gọi lại", "list follow-up chờ", "list lỗi trượt ra", "list đỏ" | "danh sách khách cần gọi lại", "danh sách cần gọi lại", "danh sách lỗi đã lọc", "ảnh quá nặng" |
| Payoff Tuấn "Mỗi chiều." | "Mỗi chiều folder tự sạch — bạn về đúng giờ." |

### Đấu nối `#noi` + câu an toàn mới

| Hiện tại | Đề xuất |
|---|---|
| dt "MCP / API" | "Hệ thống riêng của công ty" |
| dd "CRM, sheet nội bộ của công ty: cắm connector khi cần" | "CRM, sheet nội bộ — cần nối thêm thì IT cấu hình một lần" |
| dd "Relay tự host: máy nhà làm, điện thoại nhắn từ xa" | "Máy ở nhà/công ty làm việc — bạn nhắn việc từ điện thoại" |
| **Thêm plug mới hoặc dòng trong statement** | "Gửi tin, đăng bài, xoá file — trợ lý luôn hỏi bạn trước." (bán cơ chế confirm-gate có sẵn trong AGENTS.md — trả lời nỗi sợ "gửi nhầm") |

### Section chủ doanh nghiệp `#cho-cty` — viết lại toàn bộ

- H2 giữ: "Cùng vòng quay đó — nhân lên cho cả đội" (tốt).
- Lead: "Mỗi nhân viên một trợ lý trên máy mình. Công ty gói quy trình
  riêng thành pack, đẩy xuống theo phòng ban — không fork code."
  → "Mỗi nhân viên một trợ lý trên máy mình. Quy trình riêng của công
  ty gói sẵn một lần, cài xuống từng phòng ban — không cần đội kỹ thuật."
- 4 thẻ đổi:
  - "Fleet console" → **"Màn hình quản lý"**: "Biết máy nào đang dùng,
    bản nào, có lỗi không — chỉ thấy con số, không đọc chat của nhân viên."
    (giữ insight "không soi nội dung" — đây là điểm bán mạnh nhất)
  - "Pack cấu hình" → **"Gói quy trình công ty"**: "Công thức, quy trình,
    luật riêng của công ty — cài xuống từng phòng ban một lần."
  - "Cập nhật có chữ ký" → **"Cập nhật an toàn"**: "Máy tự cập nhật bản
    mới đã kiểm chứng; có lỗi thì quay lại bản cũ ngay."
  - "Tự host hoặc hosted" → **"Dữ liệu ở đâu, bạn chọn"**: "Chạy trên máy
    của công ty hoặc thuê sẵn — máy nhân viên chỉ gửi báo cáo ra ngoài."
- CTA "Nhắn qua GitHub" → đổi kênh (xem Quyết định 3).

### Statement riêng tư

| Hiện tại | Đề xuất |
|---|---|
| "não không thừa hưởng secret trên máy" | "AI không đọc được mật khẩu hay khoá đăng nhập trên máy" |

### Nav

- "Vòng quay" → "Cách trợ lý học" (người mới biết click vào xem gì).

### Thêm mới (nếu duyệt)

- **FAQ ngắn** cuối trang hoặc gộp trong `#tai`: 3 câu — "Có tốn tiền
  không?", "Tôi có cần biết code không?", "Máy công ty chặn cài phần
  mềm thì sao?" (xem Quyết định 4).

## Quyết định — đã chốt với user (2026-11-26)

1. **Danh sách não AI**: ghi tên quen "Claude, ChatGPT, Gemini…" —
   chấp nhận hơi sai sự thật để đổi lấy quen thuộc.
2. **Tiền não AI**: cả hai — một dòng ngắn dưới nút hero + giải thích
   kỹ trong FAQ.
3. **Liên hệ B2B**: form ngay trên trang, gửi về
   `phantronghieu1@gmail.com`. Triển khai tạm bằng **formsubmit.co**
   (POST form thẳng, không cần backend; MailChannels của Cloudflare
   đã ngừng 2024 nên Worker + send-mail chưa khả thi miễn phí).
   Lần submit đầu sẽ có mail kích hoạt tới hộp thư — cần bấm xác nhận.
   Sau này có thể đổi sang Cloudflare Worker + Resend/Mailgun.
4. **FAQ**: thêm section riêng trước `#tai`, 4 câu: tốn tiền không /
   cần biết code không / máy cty chặn cài thì sao / dữ liệu có bị gửi
   đi không.

## Phases

| # | Phase | Nội dung |
|---|-------|----------|
| 1 | Chốt quyết định | User trả lời 4 quyết định trên → fix bảng copy cuối |
| 2 | Sweep index.html | Hero, sơ đồ, tagline, `#noi`, `#cho-cty` viết lại, statement, nav, CTA liên hệ; thêm dòng "luôn hỏi trước khi gửi/đăng/xoá" |
| 3 | Sweep story.js | nháp→bản nháp, list→danh sách, payoff Tuấn; kiểm không câu nào vượt quá khung layout (chuỗi dài hơn có thể tràn `.task__res`) |
| 4 | FAQ (nếu duyệt) | Section FAQ 3 câu hoặc lồng vào `#tai` |
| 5 | Deploy + verify | Bump `?v=9` story.js (+style nếu đổi), commit main → gh-pages, curl xác nhận, nhắc user hard-refresh |

## Không làm ở đợt này

- Social proof / testimonial / con số người dùng (cần dữ liệu thật, không có)
- Pricing page đầy đủ (chưa có mô hình giá)
- B2B storyboard riêng (`sketches/storyboard-b2b.md` — phase sau)
- SEO schema, A/B test
