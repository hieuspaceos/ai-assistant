# ai-assistant — API Reference

Ba endpoint group trên máy học viên, tất cả bind `127.0.0.1`, JSON
thuần. API của collector/worker (fleet — bind public, model khoá
khác) nằm ở `docs/fleet.md`, không lặp lại ở đây.

## Auth — bắt buộc từ v1.0

Mọi call phải kèm "mã kết nối" `.devin/bridge.token`:

- Header `X-Bridge-Token: <mã>` — hoặc
- Query `?token=<mã>` — tiện cho lệnh một dòng / WebSocket.

```bash
TOKEN=$(cat .devin/bridge.token)
curl -s "http://localhost:7682/api/poll?since=0&token=$TOKEN"
curl -s -H "X-Bridge-Token: $TOKEN" http://localhost:7684/api/browser/status
```

Thiếu/sai → `401 {"err":"thiếu hoặc sai mã kết nối"}`. Miễn:
`GET /api/health` (liveness) và `OPTIONS` (preflight CORS). Chi tiết mô
hình khoá: `SECURITY.md`.

---

## 1. ext-bridge :7684 — lái trình duyệt (`tools/ext-bridge.py`)

```
POST http://localhost:7684/api/browser?token=<mã>
{"action": "<action>", "tabId": <id>, ...params}
→ {"ok": true, ...} | {"ok": false, "err": "..."}
```

Extension kết nối `ws://localhost:7684/ext?token=<mã>&v=<version>`
— `connected:false` nghĩa là extension chưa mở/chưa nạp/chưa pair.
WS auth check **trước** handshake (sai/thiếu token → HTTP 401, không
phải 101 rồi đóng); một message WS tích luỹ quá 64 MB → cắt kết nối.
`extVersion` trong response status là version extension tự báo; portal
so với `extVersion` của `/api/health` (manifest trong payload) để hiện
pill "Extension bản cũ" khi lệch.

| action | params | Trả về |
|---|---|---|
| `status` | — | `{connected, extVersion}` — extension có nối không + bản của nó |
| `tabs` | — | danh sách tab `{id, url, title}` |
| `open` | `url` | `tabId` tab mới |
| `activate` | `tabId` | focus tab |
| `close` | `tabId` | đóng tab |
| `snapshot` | `tabId?` | cây phần tử có `ref` e1,e2… để bấm |
| `click` | `tabId?, ref\|text` | bấm theo ref hoặc chữ hiển thị |
| `type` | `tabId?, ref, text` | gõ vào ô |
| `scroll` | `tabId?, dy, sel?` | cuộn trang/vùng (`dy:-99999` về đầu) |
| `scrollables` | `tabId?` | vùng cuộn s1,s2… cho `scroll sel=` |
| `query` | `tabId?, sel, attr?` | text/attr của phần tử khớp selector |
| `read` | `tabId?, sel?` | toàn văn trang đã lọc gọn |
| `fetch` | `tabId?, url` | tải URL bằng phiên của tab (đọc được sheet private) |
| `key` | `tabId?, sel?, ref?, key` | Enter/Tab/Escape/Delete/mũi tên |
| `paste` | `tabId?, sel?, text` | dán text/TSV qua clipboard |
| `rect` | `tabId?, sel\|ref` | toạ độ tâm phần tử |
| `dom` | `tabId?, sel?` | HTML sống đã render (toàn trang hoặc vùng) |
| `styles` | `tabId?, sel, deep?, depth?` | computed style + box (~120 phần tử đầu khi deep) |
| `assets` | `tabId?` | ảnh, SVG, font, link CSS, background-image |
| `css` | `tabId?` | nội dung stylesheet (rule đầy đủ; `blocked` → fetch href) |
| `screenshot` | `tabId?` | chụp tab → đường dẫn file `.shots/` |
| `wait` | `tabId?, ms` | chờ (tối đa 5s) |
| `reload` | — | nạp lại extension sau khi sửa code |

**Nhóm t* — input THẬT qua CDP** (app chặn event giả như Zalo #richInput,
grid Google Sheets):

| action | Dùng khi |
|---|---|
| `tclick` `sel\|ref\|x,y` | click giả không ăn |
| `tright` | mở context menu |
| `tmove` | hover lộ nút/menu ẩn |
| `ttype` `sel\|ref, text` | gõ vào editor phức tạp |
| `tinsert` `text, mode?` | chèn tại con trỏ; `mode=char` ghi vào grid Sheets |
| `tkey` `key, modifiers?` | phím thật (`modifiers:4` = Cmd/Ctrl) |
| `tdetach` | tháo debugger, tắt banner "đang gỡ lỗi" |

Lưu ý: `screenshot` dính `MAX_CAPTURE_..._PER_SECOND` của Chrome — đợi
vài giây chụp lại, đừng bỏ ảnh (ảnh là chuẩn so của clone-pipeline).

---

## 2. chat-bridge :7682 — portal chat + quản trị (`tools/chat-bridge.py`)

Body limit: 1 MB mặc định, **8 MB riêng `/api/save-page`** (trang clone
có ảnh base64).

### GET

| Path | Trả về |
|---|---|
| `/api/health` | `{"ok":true, "brain":"<id não>", "version":"<VERSION>", "extVersion":"<version extension kỳ vọng>"}` — **miễn token** |
| `/api/brain` | não hiện tại + danh sách preset (kèm cờ `installed`) |
| `/api/poll` | output mới từ session não ACP. `?since=<n>` con trỏ; `since<0` = reset (replay toàn bộ + `reset:true`). `?wait=<ms>` = long-poll: chờ tới khi có event mới hoặc hết `wait` (cap 30s) — chỉ `.py`, `.ps1` bỏ qua `wait` (HttpListener tuần tự, giữ request sẽ kẹt mọi call khác) |
| `/api/permissions` | nội dung `permissions.json` |
| `/api/connections` | nội dung `connections.json` |
| `/api/config` | nội dung `config.json` |
| `/api/check-path` | `?path=<đường dẫn>` → `{ok, isdir}` — onboarding kiểm folder tồn tại trước khi xin quyền; chỉ trả isdir, không metadata |
| `/api/bots` | `{active, bots, templates}` — bot đã tạo + template nghề từ `skill-packs/roles/` |

### POST

| Path | Body | Tác dụng |
|---|---|---|
| `/api/prompt` | `{text}` | gửi prompt vào não ACP. Não đang bận một lượt khác → `409 {"err":"đang bận"}`. Não chết → bridge tự bật lại, trả 503 "gửi lại sau" |
| `/api/brain` | `{id}` hoặc `{cmd, args?, terminal?, label?}` | đổi não: ghi `brain.json` + restart agent; preset không đủ `requires` → 404 kèm `missing`; `cmd` chỉ nhận tên lệnh trần `[A-Za-z0-9_.-]+` và ngoài denylist interpreter/exec (exact-match + `_BRAIN_CMD_DENY_RE` cho hậu tố version như `python3.12`; so **case-insensitive**); `terminal` cũng phải tên trần và qua cùng denylist, sai → về `cmd`/preset. **Mọi đổi não → consent gate `202 {pending, msg}`** — kể cả preset (agent tự gọi được endpoint qua token nên preset đổi thẳng = tự kill session); card custom ghi "chạy lệnh tuỳ ý" vì denylist không đầy đủ |
| `/api/respond` | `{id, optionId}` | hai loại card, CẢ HAI đều **bắt buộc `Origin` loopback** (card ACP: id do não tự khai + não có sẵn token → thiếu Origin là não tự duyệt) — thiếu/khác → `403` và card KHÔNG bị consume: (a) card ACP — `id` phải đang pending (ghi khi bridge dispatch `session/request_permission`, TTL 600s; `id` non-scalar hoặc trùng card đang mở — kể cả `local-*` — bị từ chối ngay lúc đăng ký + báo `-32602` cho agent): không khớp/hết hạn/đã trả → `404`; `optionId` lạ → `400` (không huỷ card). (b) card nội bộ `local-*` (consent gate): nhận `ok`/`__cancel__`; hợp lệ → apply một lần. `optionId:"__cancel__"` = huỷ. **macOS (NATIVE_GATE):** cả hai loại card duyệt qua hộp thoại native (`osascript`) do bridge spawn — option duyệt qua HTTP → `403` dù đủ token+Origin (proof-of-human; card ACP approve pick theo `_pick_allow` — ưu tiên `allow_once` trước `allow_always`, không phải `allow*` đầu tiên); `__cancel__` vẫn nhận qua HTTP và giết dialog đang mở; quyết định phát `perm_done` để UI đóng card. Dialog native KHÔNG có nút cancel — bấm "Không"/hết hạn = declined → đóng card hẳn, không phát lại card đường HTTP. `NATIVE_MAX=2`: đạt trần dialog đang mở thì gate từ chối (`409` cho endpoint, `-32602` cho não ACP) — không queue, không downgrade card |
| `/api/delete-lesson` | `{folder}` | consent gate → `202 {pending, msg}`; bấm Đồng ý mới xoá — thực ra **move** vào `my-course/.trash/<folder>-<ts>-<hex>` + gỡ manifest (khôi phục được), không xoá hẳn |
| `/api/save-page` | `{file, html}` | ghi `.html` **chỉ dưới `my-course/`**; tự tạo `<file>.bak` trước khi ghi đè; chặn `..` |
| `/api/permissions` | `{path, access, note?}` hoặc `{paths:[...], access, note?}` | consent gate → `202 {pending, msg}`; batch `paths` (≤20) = **một** card, folder không tồn tại đi vào `skipped`; folder nhạy cảm (root, home, `~/.ssh`, keychain, profile trình duyệt, `LaunchAgents`/`Startup`…) → `400` ngay, không card — so **hai chiều**: path nằm dưới HOẶC chứa folder nhạy cảm đều chặn (`~/Library` chứa Keychains); `access:"read-write"` trên folder chứa/trong mã nguồn trợ lý (ngoài `my-course`/`.devin/skills`/`.logs` vốn writable sẵn) → `400` — ghi được `tools/*.py` là code chạy ngoài sandbox; lúc bấm Đồng ý (`_apply`) mọi path **re-validate lại** — folder đã mất/đổi thành symlink nhạy cảm sau request bị bỏ qua kèm event `err`, không ghi grant độc; sau khi duyệt: thêm folder + regen `.devin/agent.sb` (macOS — build profile còn kiểm lại từng grant bằng `_grant_ok`: realpath đụng sensitive hoặc diverge khỏi normpath → bỏ emit, chặn symlink swap sau approve) |
| `/api/remove-permission` | `{path}` | consent gate → `202 {pending, msg}`; sau khi duyệt: gỡ quyền + regen `.devin/agent.sb` (macOS) |
| `/api/connections` | `{app, ...}` | cập nhật trạng thái kết nối app; `app.probe` phải khớp schema cố định (`http` chỉ URL loopback, `tabs`/`mcp`/`path`/`wp`/`zalo-oa` theo từng kiểu) — probe tuỳ ý → 400; `app.open_url` chỉ nhận `http(s)://` (`javascript:`/`data:` → 400); `open_url` **mới hoặc đổi** → **consent gate** `202` (card hiện đích link — nút "Mở trang" quen-thuộc trỏ site lạ là phishing); upsert status/name giữ nguyên `open_url` → chạy thẳng |
| `/api/remove-connection` | `{id}` | gỡ kết nối — **consent gate** `202` (agent tự gỡ = mất nút âm thầm) |
| `/api/secrets` | `{app, fields}` | lưu field bí mật (ô `secret:true` trong connections) — **consent gate** `202` (ghi credential là đặc quyền); đổi `url`/`host`/`endpoint` → **xoá toàn bộ field còn lại** sau khi duyệt — giữ creds cũ qua host mới là kênh exfil; card báo trước "sẽ XOÁ thông tin cũ" |
| `/api/setup` | `{language, learner_name, ...}` | onboarding: ghi config, cài skill pack đúng ngôn ngữ. Config đã có `language` (re-setup) → **consent gate** `202 {pending, msg}` — agent gọi lại không đè được skill/config |
| `/api/check-connection` | `{id}` | probe trạng thái app (http/tabs/wp/…) — `run_probe` tự kiểm lại schema trước khi chạy (probe cũ lọt vào file từ trước khi có check) |
| `/api/bot` | `{action, ...}` | `create`/`activate`/`delete`/`rename` bot; `create` kẹp `instructions` ≤500 chữ + `recipes` chuẩn hoá `{command, meaning}` (≤20×~120) + cap 50 bot; activate/delete → **consent gate** `202` — card activate **preview trích `instructions`** (payload nạp mọi session) chứ không chỉ hiện tên; activate → cài skill thiếu + ghi `my-course/bot.md`; `id:null` → bỏ chọn |
| `/api/bot-import` | `{file: "<base64 zip>"}` | bung bundle bot vào temp → trả `{preview:{stage,name,avatar,instructions,skills,needs,bundled}}`; chống zip-slip; body cap 8MB |
| `/api/bot-import-confirm` | `{stage}` | ghi thật: cài skill (không đè) + thêm bot vào `bots.json`; KHÔNG tự activate; stage dùng một lần |

---

## 3. serve :8080 — static file server (`tools/serve.py`)

Không có API — chỉ GET file tĩnh. Đặc điểm:

- **Host check**: chỉ nhận `Host:` thuộc `localhost`/`127.0.0.1`/`[::1]`
  (mọi port) — chống DNS rebinding; Host khác/thiếu → 403. `serve.ps1`
  miễn lo (http.sys chỉ bind prefix localhost).
- Chặn đường dẫn chứa dotfiles (`.devin`, `.git`) — secrets của học viên
  nằm trong `.devin/`, không được lộ ra HTTP.
- **CSP** trên mọi `.html` dưới `/my-course/` và `/intro/` (so path
  đã-unquote + lower-case — `%6dy-course`/`/MY-COURSE` không bypass;
  gắn kể cả response 206): **`sandbox allow-scripts
  allow-top-navigation allow-popups allow-modals`** — trang rơi vào
  opaque origin (không `allow-same-origin`): không đọc được
  `localStorage.bridge_token`, không DOM-đọc portal qua
  iframe/`window.open`, không register service worker — kèm
  `connect-src 'none'` chặn mọi fetch/XHR/WS. Clone-view sửa trang qua
  `srcdoc` đã lọc script vì trang giờ opaque (không đọc DOM được nữa).
- HTTP/1.1 keep-alive; `/web/vendor/*` cache `max-age=3600`, còn lại
  `no-store`; `Range` single-range → `206` + `Content-Range`
  (`bytes=-N` = suffix), vượt biên → `416`, multi-range → `200` trọn.
- `GET /web/` → portal · `/my-course/trang-*.html` → file clone ·
  `/web/clone-view.html?src=/my-course/<file>.html` → viewer sửa trang.

## 4. ttyd :7681 — terminal (tuỳ chọn)

Không spawn não trần — mọi đường đều qua **term-gate**
(`tools/term-gate.sh` / `.ps1`, áp ở `start.sh`, `chat-terminal.ps1`,
`tools/launcher.py`; `term-gate.cmd` chỉ còn là forwarder không-kèm-arg
— `.cmd` không thể đọc `%1` an toàn, expansion re-parse → injection):

```
ttyd -p 7681 -i 127.0.0.1 -W -a <gate>
```

`-a` cho ttyd append `?arg=` của URL iframe vào cuối lệnh gate; portal
(`app.js`) tự gắn `?arg=<BRIDGE_TOKEN>`. Gate đòi nhập đúng mã kết nối
trong shell (sai 3 lần → thoát; `.sh` timeout 90s mỗi lần đọc — `.cmd`
không có timeout được do `set /p`) rồi mới `exec <não>` —
macOS bọc thêm `sandbox-exec -f .devin/agent.sb`. `TROLY_TERM_STRICT=1`
bỏ qua `?arg=` luôn hỏi tay — token qua argv lộ trong `ps` của máy
multi-user. Trang web lạ mở được
WS ttyd nhưng chỉ gặp prompt mã, không chạm được shell.
