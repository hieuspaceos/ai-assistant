---
name: gom-file
description: Gom file lộn xộn vào các folder theo loại hoặc ngày tháng — dọn Downloads, Desktop. Luôn hỏi trước, luôn có thể hoàn tác.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Dọn folder bừa bộn cho người không biết kỹ thuật. Họ sợ nhất là **mất
file** — nên quy trình phải: xem trước → đồng ý → mới dọn, và di chuyển
chứ không xoá.

## Các bước

1. Hỏi: dọn folder nào (thường là Downloads/Desktop)? Gom theo kiểu gì —
   gợi ý sẵn: "theo loại file" (ảnh vào Anh/, pdf vào Tai-lieu/...) hoặc
   "theo tháng tải về".
2. **Liệt kê trước khi làm**: cho họ xem bảng TÓM TẮT theo loại —
   KHÔNG từng file (VD: "23 ảnh → Anh/, 8 pdf → Tai-lieu/, 4 file lạ
   để nguyên"). Hỏi đồng ý.
3. Di chuyển bằng `mv`/PowerShell `Move-Item` — tuyệt đối không xoá gì.
   File trùng tên thì thêm hậu tố, không ghi đè.
4. Báo cáo: "xong — Downloads từ 89 file loạn còn 6 folder gọn gàng".
   Mở folder cho họ xem.
5. Dạy cách hoàn tác: "muốn trả lại như cũ thì bảo mình 'gom lại hết về
   Downloads' là được".
