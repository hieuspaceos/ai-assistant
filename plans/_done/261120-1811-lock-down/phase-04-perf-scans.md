# Phase 4 — Hiệu năng: scan DOM một pass + render stream theo frame

## Mục tiêu

Hai điểm đo được là đau (không tối ưu mò): content.js ép reflow hàng
chục nghìn lần mỗi action trên trang nặng (Zalo/Sheets), và chat.html
`marked.parse` toàn văn mỗi chunk → O(n²) khi stream dài.

## File động

| File | Action | Việc |
|---|---|---|
| `extension/content.js` | modify | actClick/scrollableEls/assets — 1 pass, cap số node |
| `web/chat.html` | modify | `addText` batch render bằng rAF + gom render khi replay |
| `tools/serve.py` + `serve.ps1` | modify | `/web/vendor/` được cache (xóa no-store đại trà chỗ đó) |
| `tools/serve.py` | modify | `protocol_version = "HTTP/1.1"` (keep-alive) + hỗ trợ `Range` |
| `tools/serve.ps1` | modify | parity Range (HttpListener keep-alive sẵn) — **giữ BOM** |

## Chi tiết

### 4a. `actClick` — thu thập text một lần

Hiện tại `innerText` (ép reflow) được đọc trong `filter` rồi lại trong
`sort` — tới 2–3 reflow/ứng viên × nghìn ứng viên.

```js
const cands = [...document.querySelectorAll('a,button,div,span,li,[role]')]
  .slice(0, 6000)                       // trần chống trang khổng lồ
  .filter(visible)
  .map(e => ({ e, t: (e.innerText || '').toLowerCase() }));
// một layout flush duy nhất, sau đó filter/sort trên t đã cache —
// giữ NGUYÊN thứ tự ưu tiên: exact (children<=3, chuỗi ngắn nhất)
// → contains (chuỗi ngắn nhất). Không đổi semantics (R5).
```

### 4b. `scrollableEls()` — giảm fan-out layout

`querySelectorAll('body *')` là scan toàn cây. Giữ API, giới hạn:

```js
const els = [...document.querySelectorAll(
  'main,section,article,aside,nav,div,ul')]
  .slice(0, 4000)
  .filter(el => el.scrollHeight - el.clientHeight > 50 && el.clientHeight > 60);
```

Loại trừ leaf tags (span/a/img…) không bao giờ là vùng cuộn — bỏ bớt
~70% phần tử mà không mất vùng cuộn thật (vùng cuộn hầu như luôn là
container). Rủi ro: vùng cuộn là `ul`/container đã liệt kê — an toàn.

### 4c. `assets()` — cap scan nền

`document.querySelectorAll('body *')` + `getComputedStyle` đến khi đủ
40 bg — trang xấu nhất vẫn quét hết. Thêm `.slice(0, 5000)` trước khi
loop: bg ngoài 5000 node đầu gần như không phải tài nguyên chủ đạo.

### 4d. chat.html — render theo frame, không theo chunk

```js
let pendingRaw = null, rafId = 0;
function addText(t) {
  if (!curBubble) agentBubble();
  curBubble.dataset.raw = (curBubble.dataset.raw || '') + t;
  const b = curBubble;              // BẮT BUỘC capture: 'done'/'tool'/
  if (!rafId) rafId = requestAnimationFrame(() => {  // 'err'/'addUser'
    rafId = 0;                      // set curBubble=null GIỮA chừng rAF
    b.innerHTML = md(b.dataset.raw);// — đọc curBubble trong callback sẽ
    msgs.scrollTop = msgs.scrollHeight;  // crash "innerHTML of null"
  });                               // hoặc render nhầm bubble mới
}
```

Parse tối đa 1 lần/frame (~60 lần/s) thay vì mỗi chunk; câu dài giảm
~90% công parse mà mắt người không thấy khác gì. `done`/`perm`/`err`/
`tool`/`addUser` flush ngay (`cancelAnimationFrame` + render đúng bubble
đang dở) để không trễ bubble cuối và không rơi mất chunk cuối.

### 4e. Cache vendor

`serve.py` đang `no-store` cho mọi thứ — vendor fonts/marked/purify
không đổi theo request nào:

```python
# end_headers — phải tính giá trị TRƯỚC rồi gửi MỘT header duy nhất;
# gửi thêm header thứ hai là response có 2 Cache-Control (browser lấy
# cái nào là tuỳ — bug tinh trong draft).
cc = "max-age=3600" if self.path.startswith("/web/vendor/") else "no-store"
self.send_header("Cache-Control", cc)
```

`serve.ps1` parity. (manifest/guide đã cache-bust bằng `?_=Date.now()`
nên giữ no-store chỗ khác là đúng.)

### 4f. serve.py — keep-alive (HTTP/1.1)

`protocol_version` mặc định `"HTTP/1.0"` (BaseHTTPRequestHandler) →
**mọi asset** (font, marked.js, purify, app.js, manifest...) là một
TCP connection + một thread mới; một lần mở portal ~15 connection. Fix
một dòng:

```python
class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
```

Điều kiện đã có sẵn: `send_head` gửi `Content-Length` cho mọi response
file, `send_error` cũng gửi — giữ-alive hợp lệ. ThreadingHTTPServer giữ
1 thread/conn idle keep-alive — ở 1 client không đáng kể (trình duyệt
tự đóng sau vài giây). `serve.ps1` dùng HttpListener — HTTP.SYS tự
keep-alive, **không cần sửa**, chỉ ghi nhận parity.

### 4g. chat.html — replay gom theo bubble (không render từng chunk)

Khi `data.reset`, client xoá DOM và replay tới 3000 event — nếu đi đúng
đường `addText` thì rơi lại O(n²) của 4d, chỉ khác là đau lúc reconnect
thay vì lúc stream. Trong chế độ replay: **chỉ tích raw vào
`dataset.raw`, KHÔNG gọi `md()`**; render một lần khi bubble đóng (event
`done`/`err`/`perm` hoặc hết replay) → mỗi bubble parse đúng 1 lần bất
kể bao nhiêu chunk.

```js
let replaying = false;
// trong nhánh data.reset: replaying = true;
// addText: if (replaying) { append raw; return; }  // không rAF
// khi bubble hoàn tất / hết replay: render lần cuối + replaying = false;
```

### 4h. serve.py — hỗ trợ `Range` cho video bài học

Không có Range, `video.mp4` trong `my-course/lesson-*/` **không tua
được** — browser phải tải hết mới seek (Chrome mặc định xin Range).
Với học viên xem video vài chục MB đây là UX thật.

```python
# trong send_head, sau khi mở f và lấy size:
rng = self.headers.get("Range")
if rng and rng.startswith("bytes="):
    try:
        s, _, e = rng[6:].partition("-")
        if "," in s + e: raise ValueError     # multi-range → bỏ qua, 200
        start = int(s) if s else 0
        end = int(e) if e else size - 1
        if start > end or start >= size: raise ValueError
        end = min(end, size - 1)
    except ValueError:
        f.close()                             # tránh leak fd mỗi request
        self.send_error(416); return None
    self.send_response(206)
    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    self.send_header("Accept-Ranges", "bytes")
    self.send_header("Content-Length", str(end - start + 1))
    self.end_headers()
    # CẠM BẪY LỚN: KHÔNG được `return f` — copyfile() của base class sẽ
    # gửi từ start TỚI EOF, nhiều hơn Content-Length → vỡ keep-alive
    # HTTP/1.1 (client đọc thừa byte, connection desync). Phải tự ghi
    # đúng đoạn rồi return None:
    f.seek(start)
    remaining = end - start + 1
    while remaining > 0:
        chunk = f.read(min(remaining, 262144))
        if not chunk: break
        self.wfile.write(chunk)
        remaining -= len(chunk)
    f.close()
    return None
```

Chỉ xử lý single-range (`bytes=a-b,c-d` → rơi vào nhánh trả 200 trọn
file, hợp lệ theo spec). Luôn gửi `Accept-Ranges: bytes` kể cả response
200 — khai báo đó là opt-in mềm, Chrome sẽ dùng Range khi seek.
`serve.ps1`: HttpListener không tự xử lý Range → parse tay tương tự,
set `StatusCode=206` + header `Content-Range`/`Accept-Ranges`, ghi
`$bytes[$start..$end]` — **giữ BOM**. (ReadAllBytes hiện đã đọc trọn
file vào RAM — giữ nguyên, video bài học không quá lớn; nếu sau này
đau thì chuyển FileStream seek.)

## Verify (tay)

- `/doc-zalo` chạy snapshot/click-by-text trên Zalo Web thật — so sánh
  tốc độ cảm nhận trước/sau; quan trọng nhất: **bấm đúng phần tử cũ**
  (R5: regression khớp text).
- Chat: prompt trả lời dài ~2000 chữ → quan sát CPU tab không spike
  liên tục như trước; chữ vẫn chảy mượt.
- `curl -H "Range: bytes=0-99" http://127.0.0.1:8080/my-course/lesson-XX/video.mp4`
  → `206` + `Content-Range`; video tua được trong trình duyệt.
- `curl -v http://127.0.0.1:8080/web/bridge-token.js` → `HTTP/1.1` và
  connection tái dùng (`Keep-Alive`/`Connection` behavior đúng).
- Mở portal → đóng → mở lại: reconnect replay lịch sử chat dài không
  giật; bubble render đúng nội dung cuối.
