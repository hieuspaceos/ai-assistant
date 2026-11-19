---
name: dang-bai
description: Đăng bài lên WordPress qua REST API — tạo bản nháp, upload ảnh, gắn ảnh đại diện, gán chuyên mục/tag. Luôn tạo nháp trước, chỉ xuất bản khi học viên đồng ý.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Đăng bài WordPress qua REST API (`/wp-json/wp/v2/`) cho người không biết
kỹ thuật. Kết hợp tốt với `/anh-web`: ảnh web-ready → upload làm ảnh đại
diện.

## Kiểm tra kết nối (bắt buộc)

1. Đọc `my-course/connections.json` → app `wordpress`.
2. `POST /api/check-connection` `{"id":"wordpress"}` → `ok: true` mới tiếp.
3. `ok: false` / thiếu credentials → hướng dẫn setup:
   - Bảo học viên mở ⚙ **Cài đặt** → nút **Cài** cạnh WordPress → làm
     theo hướng dẫn trong form (tạo Application Password trong wp-admin)
     → dán rồi bấm **Lưu & kiểm tra**. Form ghi vào
     `.devin/secrets.local.json` (gitignored) đúng schema
     `{"url","user","app_password"}`.
   - Nếu học viên thích tự ghi file: cùng schema trên, vào
     `.devin/secrets.local.json` — file đã gitignore.
   - **Không bao giờ** bảo học viên dán app password vào khung chat, vào
     manifest, hay in ra terminal.
   - Chạy lại `check-connection` xác nhận `ok: true`.

## Đọc credentials (không in ra)

```python
import json
creds = json.load(open(".devin/secrets.local.json"))
wp = creds["wordpress"]; base = wp["url"].rstrip("/")
auth = (wp["user"], wp["app_password"].replace(" ", ""))
```

Dùng Python `urllib` hoặc `requests` (nếu có) + Basic auth. Không echo
`app_password` dưới bất kỳ dạng nào.

## Đăng bài

1. Hỏi học viên nếu chưa rõ: nội dung bài (file .md/.docx hay dán thẳng),
   tiêu đề, chuyên mục (category), tag, ảnh đại diện (folder nào).
2. **Chuyên mục/tag**: `GET {base}/wp-json/wp/v2/categories?search=<tên>`
   lấy id; tên mới thì `POST` tạo. Tag tương tự với `/tags`.
3. **Upload ảnh**: `POST {base}/wp-json/wp/v2/media` —
   header `Content-Type: image/webp` (hoặc jpeg/png theo file),
   `Content-Disposition: attachment; filename="<tên-file>"`, body = bytes.
   Trả `id` media → dùng làm `featured_media`.
4. **Tạo bài — LUÔN nháp trước**:
   `POST {base}/wp-json/wp/v2/posts` —
   `{"title": ..., "content": <html>, "status": "draft", "categories":[id],
   "tags":[id], "featured_media": <media id>}`.
   Nội dung markdown → chuyển HTML (đoạn `<p>`, ảnh `<img src=media url>`).
5. Báo học viên: *"đã tạo nháp <tiêu đề>, link xem trước: {preview link}"*.
   Hỏi: *"xem nháp ổn chưa, đăng thật không?"*
6. Chỉ khi đồng ý: `POST {base}/wp-json/wp/v2/posts/{id}` `{"status":"publish"}`.

## Luật an toàn

- **Không publish khi chưa hỏi** — mặc định `status:"draft"`, xuất bản phải
  có đồng ý rõ ràng.
- Không sửa/xoá bài đã có trừ khi học viên chỉ rõ bài nào.
- Không in/log app password; lỗi 401/403 → bảo học viên kiểm tra lại app
  password, không đoán.
- Lỗi upload ảnh do size → báo học viên, gợi ý `/nen-anh` giảm size trước.
