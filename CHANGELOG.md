# Changelog

Format theo [Keep a Changelog](https://keepachangelog.com/). Mỗi release
phải có mục riêng — `tools/build-release.sh` fail nếu thiếu.

## [Unreleased]

### Thêm
- Quản trị 2 tầng trên collector Workers: tài khoản thật trong D1
  (bảng `admins` + `sessions`, PBKDF2-HMAC-SHA256, Bearer token 7 ngày)
  thay cho một key chung cả org. `master` (vendor) tạo org + cấp license
  (ký HMAC đúng format make-license.py) + quản tài khoản cty-admin ngay
  trên dashboard; `admin` (IT cty) chỉ thấy/duyệt máy org mình.
  Bảng `orgs` trong D1 ghi đè ORGS_JSON; bảng `audit` ghi ai-duyệt-gì.
  Endpoint mới: login/logout/whoami/password/bootstrap (1 lần, cần
  vendor_key), orgs CRUD, `orgs/<org>/license`, admins CRUD, audit.
  Link `?key=` + X-Admin-Key vẫn sống cho collector.py self-host.
- `collector-web/index.html` viết lại: màn login 2 cửa (tài khoản /
  dán key) + dashboard theo vai trò — tab Máy (pending + drawer chi
  tiết, cột kết nối/app + tổng hợp fleet + lọc), Công ty, Tài khoản,
  Nhật ký, Pack. Design theo tokens của site.
- `POST /api/orgs/<org>/rotate-secret` (master): xoay beacon_secret +
  admin_key — fleet.json/admin_key cũ chết ngay; `kill_machines` đá
  toàn bộ máy về pending buộc re-pair. Org env-only → migrate sang D1.
  Nút "Xoay khoá" trên tab Công ty.
- `tools/test-worker.py`: integration test worker qua wrangler dev +
  D1 local — đủ vòng đời 2-tầng (37 check). `test-fleet.py` thêm
  parity collector.py ↔ worker/index.js (endpoint set, worker-only
  khai trong WORKER_ONLY).
- Upload release giờ chỉ master (trước đây admin_key org cũng đẩy được).

### Sửa
- `.devin/bridge.token` giờ rotate mỗi lần start (launcher.py,
  start.sh, start.bat) — trước đây persist mãi làm gốc tin cậy duy
  nhất của mặt phẳng local. Session extension đang sống chết cùng
  restart (vốn đã reset state). Health-check chạy TRƯỚC rotate:
  double-launch khi đang mở chỉ mở lại portal bằng token cũ — ghi đè
  file ở đây làm portal/beacon lệch token với bridge đang sống.
- Worker: chặn khoá master cuối cùng (`/api/admins/<id>` 400 — mất
  hết master = lockout vĩnh viễn vì bootstrap đã tự khoá); audit
  redact pass chứa `"` không còn lộ phần đuôi.
- `tools/beacon.py`, `tools/update.py`, `tools/apply-pack.py`: thêm
  User-Agent riêng — Cloudflare chặn UA mặc định "Python-urllib"
  (error 1010 → 403) nên beacon/update không tới được collector host
  trên Workers (phát hiện khi test E2E trên Windows thật).
- `tools/beacon.py`: stdout/stderr `reconfigure(errors="backslashreplace")`
  — console/log Windows là cp1252, print tiếng Việt raise
  UnicodeEncodeError giết cả vòng beacon ngay tại chỗ in lỗi.

## [1.0.3] — 2025-11-25

### Thêm
- `worker/` — port collector.py sang Cloudflare Workers + D1 + R2;
  hosted fleet ĐÃ LIVE tại `https://troly.hieuspace.com/fleet/` (route,
  secrets qua wrangler; org đầu tiên IMA). Ops: deploy/vendor-infra.md.

## [1.0.2] — 2025-11

### Thêm
- Fleet console: beacon trên máy nhân viên + collector cho IT/cty —
  dashboard thấy N máy, version, license, lượt dùng; pairing per-máy
  với approve/revoke; license ký HMAC, đếm ghế kiểu "flag chứ không
  khoá".
- Kênh phân phối: release zip ký ed25519 (public key nhúng trên máy,
  private key offline phía vendor); update.py kéo→verify→stage, launcher
  áp khi mở app, rollback bằng `troly --rollback`; config-pack per-cty
  (skills/bots/connections/workflows/rules/allowlist) qua apply-pack.py —
  "một code base, khác biệt là pack".
- `tools/backup.py`: snapshot my-course + state .devin trước update/pack.
- `tools/sync-fork.sh`: trích khác biệt từ fork cũ sang `packs/<org>/`.
- `build-release.sh`: cổng phát hành — git sạch, test suite, CHANGELOG,
  secret-scan zip, ký, xuất manifest.

### Sửa
- AGENTS.md đọc thêm `.devin/rules.local.md` (luật cty) — đứng trên lời
  dặn thường, dưới luật an toàn lõi.

## [1.0.0] — 2025-10

Bản đầu: portal + 3 bridge loopback + extension lái trình duyệt thật +
não ngoài qua ACP + sandbox/consent gate.
