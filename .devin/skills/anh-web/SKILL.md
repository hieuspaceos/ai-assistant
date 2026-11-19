---
name: anh-web
description: Đổi tên + nén hàng loạt ảnh export từ Canva thành ảnh sẵn sàng đăng web — ảnh gốc giữ nguyên, kết quả vào folder mới. Dùng khi học viên vừa export một đống ảnh từ Canva và phải chuẩn bị để up lên website, WordPress, hoặc gửi team.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Bạn sắp xử lý một mẻ ảnh export từ Canva cho một người KHÔNG biết kỹ thuật.
Họ thường có một folder đầy file tên kiểu `Thiết kế chưa có tên.png`,
`post facebook (1).png` — nặng, tên lộn xộn, chưa dùng cho web được.

Quy tắc vàng: **KHÔNG đụng file gốc** — luôn copy sang folder mới rồi mới
đổi tên + nén.

## Các bước

1. Hỏi bằng lời thường (dùng ask_user_question nếu họ chưa nói rõ):
   - Folder chứa ảnh ở đâu? (gợi ý: kéo folder thả vào khung chat, hoặc
     gõ @ để chọn)
   - Muốn đặt tên file mới kiểu gì? Gợi ý sẵn 2-3 kiểu dễ chọn:
     "theo tên chiến dịch, VD `sale-tet-01`" / "theo tên bài đăng" /
     "giữ nguyên ý gốc, chỉ sửa cho sạch".
   - Ảnh để làm gì? Gợi ý: "Up website/WordPress" / "Đăng mạng xã hội" /
     "Gửi email" — mỗi mục đích một size.
2. Nói trước bằng lời thường bạn sẽ làm gì, VD: *"Mình sẽ tạo folder
   `anh-web` cạnh folder gốc, copy 23 ảnh sang, đổi tên thành
   `sale-tet-01.webp` tới `sale-tet-23.webp` và nén nhẹ — ảnh gốc vẫn
   nguyên vẹn. Nhé?"*
3. Thực hiện:
   - Trên máy Windows của học viên, ưu tiên PowerShell + .NET
     (`System.Drawing`) hoặc `ffmpeg`/`magick` nếu đã có sẵn. Trên macOS
     dùng `sips` có sẵn. Nếu cần cài tool, giải thích ngắn trước khi cài.
   - Đổi tên chuẩn web: chữ thường, không dấu, gạch ngang thay khoảng
     trắng, đánh số 2 chữ số (`ten-01`, `ten-02`...). Giải thích ngắn:
     "để web không bị lỗi tên file, và ảnh xếp đúng thứ tự".
   - Size theo mục đích: website → ngang tối đa 1600px, đổi sang .webp
     nếu được; MXH → 1080px; email → 1200px, jpeg chất lượng 80.
4. Báo cáo kết quả KIỂU CON NGƯỜI: "xong rồi — 23 ảnh trong folder
   `anh-web`, tổng dung lượng từ 95MB còn 4MB, tên đã đẹp hết". Mở
   folder kết quả cho họ xem.
5. Nhắc nhẹ: "lần sau export Canva xong, gõ `/anh-web` là mình làm y
   chang luôn".
