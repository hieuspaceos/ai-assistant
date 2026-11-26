# Phase 02 — Bridge hardening: confused-deputy + input validation (chat-bridge.py, serve.py)

## Vá

**S3a, S3b, S7-denylist, S11, S12, S13** — tất cả nằm trong
`tools/chat-bridge.py` (+ `serve.py` cho S12, `ext-bridge.py` cho WS mask).

## 2.1 — Probe schema cố định (`/api/connections` + `run_probe`)

Hiện `POST /api/connections` upsert `app` dict nguyên trạng → `probe`
tuỳ ý. Thêm `validate_probe(probe)` whitelist:

| type | field cho phép | ràng buộc |
|---|---|---|
| `http` | `url`, `expect_key`, `expect_val` | scheme `https?` + hostname ∈ {localhost, 127.0.0.1, ::1, *.localhost} — builtin duy nhất đang dùng là `:7684/api/browser/status` |
| `tabs` | `url_contains` | str ≤120 |
| `path` | `path` | expanduser xong phải nằm dưới `~` và KHÔNG nằm trong `<cwd>/.devin` — chặn oracle file secrets |
| `mcp` | `name` | str ≤40 |
| `wp`, `zalo-oa` | — | không field |

`POST /api/connections` reject probe sai → 400. `run_probe` thêm lớp
phòng thủ thứ hai: `http` vẫn kiểm scheme+host ngay trước `urlopen`
(chặn cả probe đã lọt vào file từ trước), `r.read(1_048_576)` kẹp body.

## 2.2 — `/api/secrets`: đổi `url` thì xoá field còn lại

Chain hiện tại: agent ghi `{app:"wordpress", fields:{url:"http://evil"}}`
→ merge giữ `user`+`app_password` → check-connection gửi Basic creds tới
host mới.

Fix: khi merge, nếu field tên `url` (hoặc `endpoint`, `host` — bộ khoá
endpoint biết trước) **đổi giá trị so với stored** → xoá toàn bộ field
khác của app đó (bắt buộc nhập lại). Trả `{ok, note:"đổi địa chỉ — cần
nhập lại thông tin đăng nhập"}`. Portal `app.js` hiện note này.

Thêm: `run_probe` wp — pin scheme `https` (WP app-password qua http đã
là plaintext leak sẵn — giờ bắt https luôn).

## 2.3 — `/api/brain`: cmd denylist + `terminal` regex

`cmd` custom regex tên trần đã có nhưng args tuỳ ý (`python3 -c`,
`find -exec`, `npx -e`…) = exec code cho mọi token-holder.

- `BRAIN_CMD_DENY` = interpreter/exec helpers:
  `python3, python, py, sh, bash, zsh, fish, dash, osascript, node,
  deno, bun, ruby, perl, php, pwsh, powershell, cmd, env, nice, xargs,
  find, make, rake, npm, npx, gem, pip, pip3, curl, wget, nc, ncat,
  socat, busybox, open, rundll32, regsvr32, mshta, wscript, cscript,
  wmic, certutil, bitsadmin, eval, exec, launchctl`
  (`npx`/`npm` deny vì preset codex/claude đã cover adapter).
- `terminal` field phải khớp `^[A-Za-z0-9_.-]+$` — hiện chỉ cắt [:60],
  nó chạy vào `%BRAIN_TERM%` unquoted trong `term-gate.cmd` = cmd
  injection. `.cmd` cũng sửa quote ở phase-04.
- `load_brain()` cũng kiểm (phase-01 đã spec — giữ một chỗ logic).

## 2.4 — S11: `instructions` dict kẹp độ dài

`confirm_bot_bundle`: `isinstance(instructions, dict)` → kẹp từng value
2000 chars (và key ∈ {vi, en}).

## 2.5 — S12: blocklist JSON nhạy trên `:8080`

`serve.py` `send_head`: chặn `my-course/{permissions,connections,config,
bots}.json` + `my-course/bot.md` (404). `manifest.json` vẫn mở — portal
cần. `serve.ps1` làm tương đương ở phase-04.

## 2.6 — S13 nhỏ

- `ext-bridge.py` `ws_recv`: frame từ client không mask → đóng kết nối
  (RFC bắt client mask).
- `chat-bridge.py` boot: dọn `tempfile.gettempdir()/troly-bot-*` cũ >1h
  (stage leak khi crash).

## Test (test-bridges.py mở rộng)

- `/api/connections` probe `file:///etc/passwd` → 400; probe http tới
  `evil.com` → 400; probe hợp lệ → 200.
- secrets: ghi `{url,user,app_password}` → ghi `{url: "http://khac"}` →
  đọc file (test-side) thấy chỉ còn `url` mới.
- `/api/brain` `{cmd:"python3"}` → 400 denylist; `{terminal:"a&b"}` → 400.
- bot-import instructions dict value 5000 chars → file ghi ≤2000.
- serve.py: `GET /my-course/permissions.json` → 404; `manifest.json` → 200.

## Done khi

Toàn bộ check trên xanh; không endpoint nào đổi chữ ký → parity test vẫn
pass.
