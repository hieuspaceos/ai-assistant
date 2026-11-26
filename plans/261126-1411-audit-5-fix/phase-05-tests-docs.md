# Phase 05 — Tests + docs + quyết định CSP top-navigation

## Test bổ sung

**`tools/test-distribution.py`** (phase-01 cases):
- pack `connections: [{"id":"x","open_url":"javascript:alert(1)"}]`
  → reject cả pack.
- pack `skills: {"s": {"C:/e.md":"x"}}`, `workflows: {"C:/w.json":{}}`,
  `mycourse_files: {"C:x.md":"x"}` → reject.
- pack `permissions_template: [{"path":"/","access":"read-write"}]`
  → reject (sensitive root).
- pack `exec_allowlist: ["pwsh *", "npx *"]` → reject.
- case hợp lệ cũ vẫn pass (regression).

**`tools/test-agent-spawn.ps1`** (phase-03): file `.devin\machine.key`
giả → spawn `type` → không đọc được. (Deny-Full trên file không tồn
tại lúc setup → chỉ verify được khi file có — test tạo file giả sau
setup rồi re-apply deny bằng icacls trực tiếp, hoặc setup chạy lại.)

**`tools/test-bridges.py`**: không đổi (save-page .py đã đúng). Nếu
thêm test ps1-side junction ở phase-02 thì nằm trong test-windows.

## Quyết định F14 — CSP `allow-top-navigation`

Residual từ audit-3 L5. Verify trước khi đổi:

- **Chrome**: `allow-top-navigation-by-user-activation` còn hỗ trợ
  → đổi trong `serve.py` + `serve.ps1`: clone links ngoài vẫn mở được
  khi user bấm (user-activation), script tự trồng top-navigate bị chặn.
- **Safari**: không hỗ trợ keyword → nếu app bắt buộc chạy Safari,
  `allow-top-navigation` phải giữ → ghi residual "trang clone có thể
  top-navigate khi mở trực tiếp; trong iframe portal thì…".
- Verify thực tế: trang test `<a href="https://example.com"
  target="_top">` + script `top.location=…` — bấm tay được, script
  tự động bị chặn.
- Nếu đổi: parity hai serve + cập nhật SECURITY.md (gỡ residual L5).
  Nếu không: SECURITY.md ghi rõ lý do giữ (Safari + clone links cần
  top-nav cho UX) + khuyến nghị học viên mở link bằng menu chuột phải.

## SECURITY.md cập nhật

- **F15 — `mcp_config.json` qua pack**: ghi rõ đây là kênh exec-theo-
  thiết-kế (org đẩy MCP server → lệnh chạy dưới agent user); khuyến
  nghị IT review pack trước khi phát; cân nhắc gating sau (hiện chưa
  vá — pack đã trusted-channel, nhưng transparency).
- **F10-note**: `permissions_template` giờ lint sensitive ở apply +
  ACL grant lọc lại ở setup-agent-user — enforcement-point recheck.
- **F3**: ghi parity note — ps1 chặn mọi reparse dưới my-course
  (chặt hơn .py `realpath`, fail-closed).
- **F1**: ghi nhận deploy constraint — Dest phải là nơi user thường
  ghi được (đã vá bằng icacls grant); môi trường multi-user cần
  `-ForUser` tương đương.
- Accepted-risk giữ nguyên: check-path/count-glob oracle, emit-event
  spoof, /api/prompt không rate-limit.

## Docs phụ

- `docs/api-reference.md`: nếu CSP đổi thì sửa chuỗi CSP ghi ở đó.
- `deploy/DEPLOY.md`: ghi chú ACL Dest + `-ForUser` cho multi-user.

## Done khi

- Toàn bộ test chạy xanh; CI test-windows xanh.
- SECURITY.md phản ánh đúng trạng thái sau vá.
