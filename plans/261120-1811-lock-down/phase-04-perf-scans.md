# Phase 4 — Hiệu năng: scan DOM một pass + render stream theo frame

## Mục tiêu

Hai điểm đo được là đau (không tối ưu mò): content.js ép reflow hàng
chục nghìn lần mỗi action trên trang nặng (Zalo/Sheets), và chat.html
`marked.parse` toàn văn mỗi chunk → O(n²) khi stream dài.

## File động

| File | Action | Việc |
|---|---|---|
| `extension/content.js` | modify | actClick/scrollableEls/assets — 1 pass, cap số node |
| `web/chat.html` | modify | `addText` batch render bằng rAF |
| `tools/serve.py` + `serve.ps1` | modify | `/web/vendor/` được cache (xóa no-store đại trà chỗ đó) |

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
  if (!rafId) rafId = requestAnimationFrame(() => {
    rafId = 0;
    curBubble.innerHTML = md(curBubble.dataset.raw);
    msgs.scrollTop = msgs.scrollHeight;
  });
}
```

Parse tối đa 1 lần/frame (~60 lần/s) thay vì mỗi chunk; câu dài giảm
~90% công parse mà mắt người không thấy khác gì. `done`/`perm` flush
ngay (`cancelAnimationFrame` + render) để không trễ bubble cuối.

### 4e. Cache vendor

`serve.py` đang `no-store` cho mọi thứ — vendor fonts/marked/purify
không đổi theo request nào:

```python
# end_headers: no-store mặc định; ngoại lệ
if self.path.startswith("/web/vendor/"):
    self.send_header("Cache-Control", "max-age=3600")  # thay no-store
```

`serve.ps1` parity. (manifest/guide đã cache-bust bằng `?_=Date.now()`
nên giữ no-store chỗ khác là đúng.)

## Verify (tay)

- `/doc-zalo` chạy snapshot/click-by-text trên Zalo Web thật — so sánh
  tốc độ cảm nhận trước/sau; quan trọng nhất: **bấm đúng phần tử cũ**
  (R5: regression khớp text).
- Chat: prompt trả lời dài ~2000 chữ → quan sát CPU tab không spike
  liên tục như trước; chữ vẫn chảy mượt.
