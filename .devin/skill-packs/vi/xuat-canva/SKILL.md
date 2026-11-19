---
name: xuat-canva
description: Lấy file export từ Canva về máy rồi xử lý — hướng dẫn học viên export đúng, gom ảnh/file về folder, chuyển tiếp cho nén/đổi tên/đăng web. Trợ lý KHÔNG bấm trong Canva editor.
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

Canva không có đường automation bền trong editor — quy trình đúng là:
**học viên export → trợ lý xử lý file**. Skill này chuẩn hoá khâu bắt
đầu: export về đâu, đặt tên gì, sau đó làm gì tiếp.

## Bước 1 — Export

Hướng dẫn học viên trên Canva (họ tự bấm, mình chỉ chỉ):

1. Nút **Chia sẻ** (góc trên phải) → **Tải xuống**.
2. Loại file: PNG (ảnh thường) / JPG (ảnh nền trắng, nhẹ) / PDF (in).
   Nhiều trang → Canva tải về **file .zip**.
3. File về `~/Downloads` mặc định.

## Bước 2 — Gom về folder làm việc

- Nếu `.zip`: giải nén ra folder `<tên-thiết-kế>` trong Downloads hoặc
  folder được phép (kiểm tra `permissions.json` trước).
- Nếu nhiều file rời: gom vào một folder.

## Bước 3 — Xử lý tiếp theo nhu cầu

| Nhu cầu | Chuyển cho |
|---|---|
| Ảnh đăng web/WordPress | `/anh-web` (đổi tên + nén → webp) |
| Ảnh gửi mail/ MXH | `/nen-anh` |
| Đăng lên WordPress | `/dang-bai` (upload ảnh đã xử lý) |
| Xem có gì trong đống file | `/tom-tat-file` |

## Lưu ý

- Canva Pro export `.svg`/`.pdf print`: xử lý ảnh thì convert sang
  png/jpg trước (sips/ImageMagick).
- Học viên hay quên export nhiều trang → zip: nhắc "nếu thiết kế nhiều
  trang, tick chọn trang hoặc tải cả zip rồi mình giải nén".
- Không dùng extension bấm trong Canva editor (layout phức tạp, dễ hỏng
  bài đang làm) — editor chỉ để học viên tự thiết kế.
