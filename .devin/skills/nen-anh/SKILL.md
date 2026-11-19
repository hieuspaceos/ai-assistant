---
name: nen-anh
description: Nén và đổi kích thước nhiều ảnh cùng lúc — ảnh gốc giữ nguyên, kết quả vào folder mới. Dùng khi học viên cần up ảnh lên web, gửi mail, đăng mạng xã hội.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Bạn sắp nén/resize ảnh hàng loạt cho một người KHÔNG biết kỹ thuật.
Quy tắc vàng: **KHÔNG đụng file gốc** — luôn xuất ra folder mới.

## Các bước

1. Hỏi bằng lời thường (dùng ask_user_question nếu họ chưa nói rõ):
   - Folder chứa ảnh ở đâu? (gợi ý cách kéo folder thả vào, hoặc gõ @ để chọn)
   - Dùng ảnh để làm gì? Gợi ý sẵn: "Up lên website" / "Gửi qua email" /
     "Đăng Facebook-Instagram" — mỗi mục đích có size khác nhau.
2. Nói trước bằng lời thường bạn sẽ làm gì, VD: *"Mình sẽ tạo folder
   `anh-nho` cạnh folder gốc, copy 47 ảnh sang và thu nhỏ — ảnh gốc vẫn
   nguyên vẹn. Nhé?"*
3. Thực hiện:
   - Trên máy Windows của học viên, ưu tiên PowerShell + .NET
     (`System.Drawing`) hoặc cài `ffmpeg`/`magick` nếu đã có sẵn. Nếu cần
     cài tool, giải thích ngắn trước khi cài.
   - Web: chiều ngang tối đa 1600px, đổi sang .webp nếu được. Email: tối đa
     1200px, jpeg chất lượng 80. MXH: 1080px.
   - Đổi tên file kết quả thành dạng an toàn cho web: chữ thường, không
     dấu, gạch ngang thay khoảng trắng (giải thích ngắn: "để web không
     bị lỗi tên file").
4. Báo cáo kết quả KIỂU CON NGƯỜI: "xong rồi — 47 ảnh trong folder
   `anh-nho`, tổng dung lượng từ 210MB còn 18MB". Mở folder kết quả cho
   họ xem (exec `explorer <folder>` trên Windows).
5. Nhắc nhẹ: "lần sau gõ `/nen-anh` là mình làm y chang luôn".
