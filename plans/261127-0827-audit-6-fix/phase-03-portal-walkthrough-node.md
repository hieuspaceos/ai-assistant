# Phase 03 — portal walkthrough `open-url` + node sha256 Linux (F6, F7)

## F6 — `open-url` step không scheme-check

`web/app.js:761`:

```js
if (a === 'openurl') { window.open(sub(s.url), '_blank'); ...
```

`s.url` từ `walkthrough.json` — file do não viết trong bài học, hoặc
(mạt khả năng) đến từ pack/bank sau này. `window.open("javascript:…")`
mở document kế thừa origin opener → script chạy trong origin portal
→ đọc `localStorage.bridge_token`, render UI giả trong portal.

Đây là **cùng class với audit-5 F2** đã vá ở `connections.open_url`
(lint `^https?://` trong `apply-pack.py:155-163` + check
`chat-bridge.py:2298-2302`) — vá surface thứ nhất, sót surface thứ hai.

Giới hạn thiệt hại (ghi trong plan để không đánh giá quá tay): não
sandbox đọc được `.devin/bridge.token` sẵn — XSS không cho token mới.
Giá trị còn lại của lỗ hổng: chạy JS trong **browser context của
học viên** (đọc DOM portal, tương tác UI, persist qua
localStorage/service-worker nếu có), và nếu walkthrough đi qua kênh
pack/bank thì là XSS remote-từ-vendor — mức MED là hợp lý, không phải
CAO.

### Vá — 2 điểm (enforce + lint, pattern audit-5)

**Renderer** (`web/app.js`, ngay trước `window.open`):

```js
if (a === 'openurl') {
  const u = sub(s.url);
  if (!/^https?:\/\//i.test(u)) { uiAlert(t('gateTitle'), t('wtBadUrl')); return; }
  window.open(u, '_blank'); ...
}
```

(thêm key `wtBadUrl` vào cả 2 i18n table vi/en — check `t()` fallback
nếu thiếu key trước khi dùng.)

**Validator** (`tools/test-walkthrough.py`): trong `check_file`,
step `open-url` có `url` thì reject nếu sau khi bỏ `{{var}}` (biến
chưa resolve lúc lint — chỉ check literal prefix) mà prefix không
phải `http(s)`:

```python
if k == "open-url":
    u = str(s.get("url") or "")
    # biến {{x}} chưa resolve — chỉ lint literal không-chứa-biến;
    # renderer app.js check scheme lại lúc chạy (defense 2 lớp)
    if u and "{{" not in u and not re.match(r"^https?://", u, re.I):
        fail(errs, w, "open-url url chỉ nhận http(s): %s" % u[:60])
```

URL chứa biến (`{{s.endpoint}}`) không lint được tĩnh → renderer
check là lưới cuối — đúng mô hình 2 lớp.

## F7 — `install-brain.py` node Linux x64 không pin sha256

`tools/install-brain.py:31`:

```python
("Linux", "x86_64"):   (f"node-{NODE_VER}-linux-x64.tar.gz", None),
```

`fetch()` short-circuit `if want_sha and sha256(dst) != want_sha` →
`None` bỏ qua check. Binary tải về trở thành não gemini — chuỗi
supply-chain duy nhất không pin (Win + 2 macOS đều pin cứng).

### Vá

Lấy sha256 từ `https://nodejs.org/dist/v26.13.1/SHASUMS256.txt`
(official, HTTPS) điền vào tuple — giữ pattern pin-cứng, không đổi
code fetch. Nếu muốn tiện bump version sau này: có thể đổi `fetch`
thành fetch-SHASUMS + verify động cho cả 4 nền — nhưng đó là refactor
ngoài scope; pin tay khớp convention hiện có.

## Test

- `tools/test-walkthrough.py`: thêm fixture walkthrough chứa
  `open-url` với `url: "javascript:alert(1)"` → validator phải FAIL;
  `url: "{{app.url}}"` → PASS (biến lint sau); `url: "https://…"` →
  PASS.
- F7 verify tay: `python3 -c "from tools... "` — thực ra chỉ cần check
  tuple trong test: test-distribution thêm assert `all(sha for
  (_,(f,sha)) in NODE_DIST.items())`.
