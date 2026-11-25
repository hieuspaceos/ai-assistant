# Changelog

Format theo [Keep a Changelog](https://keepachangelog.com/). Mỗi release
phải có mục riêng — `tools/build-release.sh` fail nếu thiếu.

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
