---
name: doc-outlook
description: Đọc Outlook Web (outlook.office.com) trên trình duyệt thật — liệt kê mail chưa đọc, đọc nội dung mail, tải file đính kèm. KHÔNG tự gửi/reply mail.
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

Đọc Outlook Web qua extension Trợ Lý AI — cùng API `/mo-web`, pattern
giống `/doc-zalo`. Học viên đã đăng nhập sẵn trên browser.

## Chuẩn bị

1. `curl -s http://localhost:7684/api/browser/status` → `connected: true`.
2. `{"action":"tabs"}` → tìm tab `outlook.office.com` /
   `outlook.live.com`. Chưa có → `open` URL.
3. Trang đòi đăng nhập → nhờ học viên đăng nhập tay, đợi báo xong.

## Liệt kê mail chưa đọc

1. `snapshot` → tìm nút filter/Unread (Outlook có nút "Filter" trên danh
   sách mail → mục "Unread"). `click` theo chữ nếu không có ref.
2. `query` vùng danh sách mail (thử `div[role=option]`,
   `[class*=mailList]`, `[aria-label*=message]`).
3. Cuộn vùng danh sách (`scrollables` tìm pane trái) để nạp thêm.
4. Báo tên người gửi + tiêu đề + giờ — KHÔNG đọc nội dung khi chưa được
   nhờ.

## Đọc một mail

1. `click` theo chữ (tiêu đề/người gửi) → mail mở ở pane đọc.
2. `query`/`read` vùng nội dung (`[aria-label*=message body]` hoặc pane
   phải) → tóm tắt cho học viên.
3. File đính kèm: thấy tên file + nút Download → `click` để browser lưu
   về Downloads, báo học viên.

## Soạn/reply mail

Soạn được: `click` "New mail" hoặc "Reply" → `type` vào ô To/CC/nội dung.
**Luật cứng**: trước khi `click` nút Send phải hỏi: *"mình sắp gửi mail
này tới <người nhận>, bạn đồng ý không?"* — đồng ý mới bấm.

## Luật

- Không đọc mail ngoài yêu cầu; không xoá/di chuyển mail khi chưa hỏi.
- Outlook hay đổi class → selector không ra gì thì `screenshot` + dò lại
  `scrollables`/`query` rộng hơn, báo học viên "Outlook vừa đổi giao
  diện, mình đang dò lại".
- Mail chứa link/xác nhận bảo mật (đổi mật khẩu, OTP): chỉ đọc tóm tắt,
  không bấm link thay học viên.
