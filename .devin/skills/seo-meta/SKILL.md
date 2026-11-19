---
name: seo-meta
description: Sửa SEO meta (title, description, alt ảnh) của bài WordPress qua REST API — hỗ trợ Yoast và RankMath. Sửa từng bài hoặc hàng loạt theo danh sách.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Sửa meta SEO của bài WordPress qua REST — việc vốn phải mở từng bài trong
wp-admin sửa tay. Kiểm tra kết nối giống `/dang-bai` (app `wordpress` trong
`connections.json`, credentials ở `.devin/secrets.local.json`).

## Dò plugin SEO trước

Plugin nào thì field đó:

| Plugin | Meta keys |
|---|---|
| Yoast | `_yoast_wpseo_title`, `_yoast_wpseo_metadesc` |
| RankMath | `rank_math_title`, `rank_math_description` |

Dò bằng cách `GET {base}/wp-json/wp/v2/posts/{id}` → xem trường `meta`
có key nào. **Lưu ý**: field meta chỉ đọc/ghi được qua REST khi plugin
đã `register_meta` với `show_in_rest: true` — Yoast/RankMath mặc định có.
Nếu `meta` trả rỗng → báo học viên site cần bật REST meta (plugin mới /
cấu hình), không đoán bừa.

## Sửa một bài

1. Hỏi: bài nào (id/slug/link), sửa field nào (title/description/cả hai/
   alt ảnh), nội dung mới là gì — hoặc nhờ mình gợi ý từ nội dung bài.
2. `GET {base}/wp-json/wp/v2/posts/{id}` → đọc title hiện tại + meta.
3. Đưa học viên xem bản sửa đề xuất trước (title mới, description mới) —
   đồng ý mới ghi.
4. `POST {base}/wp-json/wp/v2/posts/{id}` —
   `{"meta": {"_yoast_wpseo_title": "...", "_yoast_wpseo_metadesc": "..."}}`.
5. Đọc lại post xác nhận meta đã ghi → báo học viên.

## Sửa hàng loạt

1. Lấy danh sách: `GET {base}/wp-json/wp/v2/posts?per_page=100&page=N`
   lặp tới hết (header `X-WP-TotalPages`).
2. Cho học viên xem bảng TÓM TẮT: id, tiêu đề, meta hiện tại trống/đã có —
   không in cả nội dung.
3. Hỏi luật sửa: "bài nào thiếu description thì tự sinh từ 160 ký tự đầu"
   / "sửa theo danh sách mình đưa (file)".
4. Chạy từng bài, báo tiến độ gọn (vd "xong 12/47"), lỗi tập hợp cuối.
5. **Alt ảnh**: `POST /wp-json/wp/v2/media/{id}` `{"alt_text": "..."}` —
   dùng khi sửa alt cho ảnh đại diện/trong bài.

## Luật an toàn

- Sửa meta thay nội dung thật của site — luôn cho xem trước danh sách sẽ
  sửa + nội dung mới, được đồng ý mới ghi hàng loạt.
- Không sửa trường ngoài meta SEO (nội dung, slug, ngày đăng) trừ khi
  được nhờ rõ.
