# Phase 3 — Portal chạy được cả local lẫn qua relay

Portal hiện hardcode `BRIDGE_URL = http://127.0.0.1:7682`. Khi mở qua
`https://relay.example.com` thì điện thoại **không có** localhost:7682 —
phải gọi same-origin để relay bơm xuống. Đây là phase chạm nhiều file web
nhất.

## 1. `BRIDGE_URL` — same-origin khi không phải localhost

`web/app.js` (và các trang gọi trực tiếp):

```js
const IS_LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname);
const BRIDGE_URL = IS_LOCAL ? "http://127.0.0.1:7682" : "";   // same-origin
// bfetch(path) đã tồn tại (đợt 1) → đổi thành:
async function bfetch(path, opt = {}) {
  const r = await fetch(BRIDGE_URL + path, {
    ...opt,
    headers: { ...opt.headers, "X-Bridge-Token": bridgeToken() },
  });
  ...
}
```

Khi remote: `BRIDGE_URL=""` → fetch `/api/prompt` → relay nhận → bơm xuống
connector → `:7682`. **Token vẫn đi kèm** — relay chỉ là đường ống.

Grep toàn bộ `127.0.0.1:7682`, `127.0.0.1:7684`, `localhost:8080` trong
`web/` — mọi chỗ phải qua `bfetch`/`BRIDGE_URL`. Riêng ext-bridge (`:7684`)
chỉ có `/api/browser/status` — đổi path thành `/ext-api/browser/status`
(prefix do connector map, phase 2) → chỉ làm việc khi local (remote thì
`/ext-api` connector trả từ :7684 — vẫn được nếu cần).

## 2. Pairing UI — hai phía

**Desktop (portal ⚙):** mục mới "Truy cập từ điện thoại":
- Toggle bật/tắt → `POST /api/remote/config {"enabled": bool}` (endpoint
  mới trong chat-bridge — ghi `.devin/remote.json`, restart connector qua
  supervisor).
- Khi bật: nút "Lấy mã ghép đôi" → `GET /api/remote/pair-code` → hiện
  **6 số lớn + đếm ngược 5:00** + chữ "nhập mã này trên điện thoại".
- Khi chưa có `remote.json`: hiện hướng dẫn một dòng (setup bởi người cài
  đặt — phase 4), nút "Tạo cấu hình" cho trường hợp đã có VPS sẵn.

**Điện thoại:** mở `https://relay.example.com` → chưa có cookie → relay
serve `web/pair.html` (file mới, ~50 dòng): logo + ô nhập 6 số + nút.
`POST /pair` đúng → cookie → redirect `/` → portal load bình thường.
Session hết hạn 30 ngày → tự về lại form nhập mã (desktop phải lấy mã mới —
cố tình: mã sống ngắn là tính năng).

**Nhận mã lần đầu trên phone:** user nhập số → cần **cả bridge.token**.
Đợt 1: token trong `?t=` / localStorage. Phone không có → sau khi pair
thành công, relay redirect `/?t=<bridge-token>` — **relay phải biết token**.
Giải pháp: connector gửi `{"type": "hello", "bridge_token": "<token>"}`
khi đăng ký WS → relay giữ trong `DESKS[mid]["token"]` → khi pair OK thì
redirect kèm. Token chỉ sống trong RAM relay, không ghi đĩa.

## 3. PWA — để "Add to Home Screen" có icon, mở full-screen

- `web/manifest.json` mới: name "Trợ Lý AI", `display: standalone`, icon
  192/512 (dùng icon có sẵn hoặc tạo PNG đơn giản), `start_url: /`.
- `<link rel="manifest">` thêm vào `web/index.html` (và các trang con).
- Service worker: **KHÔNG làm** — SW cache sẽ bắt request API, rủi ro lớn
  hơn lợi ích (portal phải luôn online để dùng anyway — desktop mà tắt thì
  cache cũng vô nghĩa). Chỉ manifest đủ cho A2HS.
- `<meta name="viewport">` — kiểm tra đã có trong các trang.

## 4. Mobile CSS — chỉ chỗ thật sự vỡ

Không redesign. Audit nhanh các trang trên viewport 390px, sửa tối thiểu:
- `web/styles.css`: chat input dính đáy, font ≥16px (chống iOS zoom khi
  focus), nút ≥44px.
- `chat.html`: khung chat `100dvh`, sidebar collapse thành drawer.
- Bảng/danh sách lesson: `overflow-x: auto` nếu tràn.

## 5. Trạng thái kết nối cho phone

Khi remote, header portal hiện chấm trạng thái: xanh "đã kết nối máy nhà" /
xám "máy nhà đang nghỉ" — nguồn: `GET /api/health` qua relay trả 503 → UI
đổi. Poll 15s chỉ khi tab visible.

## Acceptance criteria

- Mở portal qua URL giả remote (test bằng hosts/proxy) → `bfetch` gọi
  same-origin, `curl /api/health` qua relay đúng bridge.
- Toàn bộ hardcode `127.0.0.1:7xxx` trong `web/` = 0 (grep verify).
- Pair e2e (một máy, relay chạy local port khác): lấy mã trên desktop →
  nhập trên trình duyệt khác → cookie → chat gửi prompt được.
- Viewport 390px: không scroll ngang, gõ chat không bị zoom.

## Rủi ro

- Sót chỗ hardcode → test bằng cách chạy portal qua relay thật (không
  được phép chỉ đọc code).
- `?t=` trong redirect `/pair` → URL có token, nằm trong history phone —
  chấp nhận (đã ghi trade-off đợt 1).
