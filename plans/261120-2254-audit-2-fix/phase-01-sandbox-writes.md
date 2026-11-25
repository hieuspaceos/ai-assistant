# Phase 01 — Sandbox write-model: đổi "cwd allow + carve-out" thành allowlist

## Vá

**S2** (ghi được code bridge → RCE ngoài sandbox) và **phần file của S1**
(ghi được `permissions.json`/`brain.json`).

## Vấn đề hiện tại

`build_profile()` cho `rw = {cwd} | tmps | sysw` — agent trong Seatbelt ghi
được mọi thứ trong `ai-assistant/` trừ vài literal deny (bridge.token,
secrets, mcp_config). Kéo theo:

- `tools/chat-bridge.py` + payload → restart = exec ngoài sandbox.
- `brain.json {"cmd": "/tmp/evil"}` → respawn tự nhiên = exec (validate
  chỉ ở POST handler, `load_brain()` đọc file trần).
- `my-course/permissions.json` thêm `"/": read-write` → regen ở spawn
  kế = profile phình toàn ổ.
- `AGENTS.md` / `.devin/skills/` mã độc → gỡ luật an toàn cho phiên sau.
- `extension/`, `web/` — ghi mã nguồn portal/extension.

## Thiết kế mới — `tools/gen-sandbox.py`

Write-allowlist thay vì write cả cwd. Tập `rw` mới:

```python
rw = tmps | sysw(caches) | {
    mc_dir,                          # my-course/ — bài học, clone, manifest
    os.path.join(cwd, ".devin", "skills"),   # agent tạo skill mới
    os.path.join(cwd, ".logs"),      # log/history
}
```

Đọc giữ nguyên (deny-enumeration hiện tại + sysr).

**Deny-write literals trong vùng allow** (deny thắng allow — emit raw +
realpath như pattern `_emit_paths`):

- `my-course/permissions.json`, `connections.json`, `bots.json`,
  `config.json`, `bot.md` — chỉ bridge (ngoài sandbox) được ghi.
- Giữ nguyên deny hiện có: `.devin/bridge.token` (write),
  `secrets.local.json`, `mcp_config.local.json` (read+write).
- `.devin/agent.sb` — profile tự nó (regen ở bridge sẽ ghi đè nhưng deny
  vẫn đáng có cho rõ ý đồ).

Vì `.devin` không còn trong rw ngoài `skills/` → các file khác trong
`.devin` tự động deny-write. `brain.json`/`AGENTS.md`/`tools/`/`web/`/
`extension/`/`site/`/`templates/`/`docs/`/`intro/`/`plans/` tất cả
deny-write theo default.

**Rủi ro hồi quy:** agent hiện có thể ghi `plans/` hoặc file lạc ở root —
AGENTS.md đã quy định "file cho học viên chỉ trong `my-course/` hoặc
folder được cấp quyền" nên allowlist ĐÚNG với luật đang khai. Kiểm kỹ
skill nào trong `.devin/skills/` ghi ngoài 3 vùng trên — nếu có thì điều
chỉnh skill, không nới sandbox.

## Thêm trong gen-sandbox.py

- `(deny process-exec (literal "/usr/bin/osascript"))` — chặn kênh
  AppleEvents vượt mặt file-sandbox (agent lái app khác qua osascript).
  Verify não preset (devin/gemini…) không cần osascript trước khi merge —
  nếu có thì bỏ rule này khỏi scope.

## Validate load-time trong `chat-bridge.py`

`load_brain()` thêm: `cmd`/`terminal` không khớp `^[A-Za-z0-9_.-]+$` →
rơi về preset devin (file bị sửa tay không spawn được lệnh lạ). Đây là
defense-in-depth — với S2 vá xong agent không còn ghi file được, nhưng
rẻ nên làm.

## Test

- Test mới (test-bridges.py, nhóm sandbox — chỉ chạy trên Darwin):
  - spawn process trong `sandbox-exec -f agent.sb`: ghi
    `tools/probe-w.txt` → EPERM; ghi `my-course/probe-w.txt` → OK;
    ghi `my-course/permissions.json` → EPERM; ghi `.devin/skills/x/y` →
    OK; ghi `brain.json` → EPERM.
  - `build_profile` output chứa subpath allow đúng 3 vùng + literals deny.
- Test `load_brain` với brain.json cmd chứa `/` → fallback devin.
- Đổi `PY_ONLY_OK` không cần (không đổi endpoint).

## Done khi

Trên macOS: `sandbox-exec -f .devin/agent.sb sh -c 'echo x > tools/t.txt'`
fail, `'echo x > my-course/t.txt'` ok. Profile regenerate giữ nguyên các
deny sẵn có.
