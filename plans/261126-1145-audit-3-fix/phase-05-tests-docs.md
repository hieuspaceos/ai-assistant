# Phase 05 — Tests + SECURITY.md + kiểm ps1

## Vá

Đợt vá này đụng vào đúng vùng "đã từng bị audit bắt" → phải để lại test
chặn regression, không chỉ vá rồi đi.

## `tools/test-bridges.py` — thêm case

File đã `import importlib.util` sẵn → unit-test internal function qua
`spec_from_file_location` (load được file gạch ngang), không cần spawn
bridge cho các case thuần hàm:

- `_pick_allow`: opts `[allow_always, allow_once]` → trả `allow_once`;
  opts `[reject_once, allow_always]` → trả `allow_always` (không nhầm
  reject); opts chỉ reject → fallback `opts[0]`... (quyết semantics:
  không có allow → trả option đầu, caller quyết — giữ y hành vi cũ).
- `_BRAIN_CMD_DENY_RE`: `python3.12`, `ipython`, `ksh`, `brew`, `gh`,
  `Rscript`, `luajit` → deny; `mycli`, `br3w`, `restic` → không match.
- `path_sensitive`/`rw_grant_ok`/`_grant_ok` (gen-sandbox — import qua
  runpy dict như `gen_sandbox_profile` đang làm): `~/.ssh`, `~/Library`,
  `/`, home → sensitive; symlink divergence → False; `/tmp` → qua.

HTTP-level (spawn bridge thật như hiện nay):

- `/api/brain` preset → 202 pending (không 200 trực tiếp);
  `{"cmd":"python3.12"}` → 400 reject (deny chạy TRƯỚC gate — verify
  không tạo card).
- `/api/permissions` flow: POST → 202 → respond ok → verify `_apply`
  re-validate: tạo dir, request, `rmdir` trước khi respond → apply →
  folder không được ghi + event `err`.
- `POST` gated spam → NATIVE_MAX: headless không spawn osascript được
  → test cap ở `local_pending` (request thứ 3 → 409 khi 2 card
  native-pending — trên macOS; trên platform khác native=False → cap
  không áp — test chỉ chạy darwin).

## `tools/test-gates.py`

- `GATED["/api/brain"]` comment đổi: `"cmd tự nhập (preset đổi thẳng)"`
  → `"mọi lần — kể cả preset (agent tự kill session/spawn churn)"`.
- Nếu `/api/bot create` vẫn ungated → khai rõ trong GATED comment của
  `/api/bot` hoặc thêm ghi chú OPEN_OK kèm lý do (không kích hoạt gì,
  instructions preview ở activate).

## `tools/test-parity.py`

Không endpoint mới → PASS như cũ. Nếu phase-04 đổi hành vi
`/api/brain` mà ps1 không theo (frozen) → đó là drift HÀNH VI không
phải drift endpoint — test-parity không bắt được; ghi nhận.

## `docs/SECURITY.md` — ghi nhận accepted-risk + invariant

Thêm mục cho audit đợt này:

- **probe `type:path` = oracle tồn-tại-file**: bridge `exists()` hộ cho
  agent — leak 1-bit cho mọi path dưới `~` trừ sensitive/.devin. Probe
  upsert không gate là chủ đích (chỉ open_url gate). Accepted.
- **`/api/check-path`, `/api/count-glob`**: cùng loại oracle — chủ đích
  cho verify engine.
- **`/api/emit-event`, `/api/connections` upsert**: agent fake được
  `perm:auto`/`env_scrub`/`status:"connected"` → integrity của dashboard
  là best-effort, không phải audit trail.
- **`/api/prompt` không rate-limit**: prompt_lock serialize nhưng não
  bị nhiễm spam được → billing DoS. Accepted tạm — throttle để sau.
- **urllib forward `X-Bridge-Token` theo redirect**: hiện không endpoint
  nào 3xx nên an toàn — nếu thêm endpoint trả redirect phải re-check
  (hoặc vá rẻ luôn: strip token header trong `redirect_request` khi
  host đổi — nếu patch ≤5 dòng thì làm luôn trong phase này).
- **CSP serve.py**: cân nhắc `allow-top-navigation-by-user-activation`
  nếu Chrome/Safari còn hỗ trợ — verify trước khi đổi; nếu không thì
  ghi nhận residual (trang clone trồng được top-navigate ra ngoài).
- **`bot.md` deny-write**: deferred — cần endpoint ghi-bot trước.
- **ps1 divergence**: liệt kê các fix .py-only của đợt này.

## `chat-bridge.ps1` — ĐÃ KIỂM (kết quả: không có bug tương đương)

- `New-Gate` (~184) là Origin-based thuần — không native dialog, không
  fallback path → CAO-1 không tồn tại trên ps1. Ghi nhận trong
  SECURITY.md: các fix đợt này là .py-only, Windows đã accepted mở hơn
  (không Seatbelt enforcement).
- Đọng một việc nhỏ: list deny interpreter trong ps1 (nếu có — grep
  `BrainCmdDeny|deny` lúc implement để ghi chính xác vào SECURITY.md).

## Test

- `python3 tools/test-gates.py tools/test-parity.py
  tools/test-bridges.py` PASS.
- Đọc lại SECURITY.md — mọi accepted-risk trong audit có mặt.

## Done khi

Mọi finding "ghi nhận" của audit hoặc đã vá, hoặc nằm trong SECURITY.md
kèm lý do; test mới chặn được đúng các regression CAO-1/CAO-2/M1/M3/M5
ở mức test được không cần GUI.
