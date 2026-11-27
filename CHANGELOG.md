# Changelog

Format theo [Keep a Changelog](https://keepachangelog.com/). Mỗi release
phải có mục riêng — `scripts/build-release.sh` fail nếu thiếu.

## [Unreleased]

### Thêm
- **Interactive walkthrough** — sản phẩm mới của `/phong-van`: mỗi công
  cụ sinh ra kèm `walkthrough.json` trong folder bài → portal hiện nút
  **"▶ Dùng ngay"** mở modal hướng dẫn từng-bước làm thật (gõ lệnh gửi
  thẳng vào chat, chờ quyền/run tự qua bước, spotlight sáng đúng chỗ
  bấm, mở kết quả trong Finder). 15 step kinds (say/prompt/input/
  choice/pick-file/open-url/wait-perm/wait-run/auto/spotlight/open/
  watch/download/check/copy/done) + flow (cond/optional/then_probe/
  media) + resume localStorage. Schema: `templates/walkthrough.json`;
  runner: `web/app.js`; validator: `tests/test-walkthrough.py`.
- Skill **`/tao-cong-cu`** (en: `/make-tool`) — gói một việc lặp lại
  thành skill `/command` + walkthrough + guide; `/phong-van` gọi lại
  nó, học viên cũng gọi trực tiếp được.
- `POST /api/reveal` (chat-bridge) — `open <path>` cho nút "Mở trong
  Finder"; chống-oracle giống check-path.
- Guide có `### Bước N` tự render thành wizard đọc (Bước N/M + Xem
  hết/Xem từng bước); tab portal hiện/ẩn theo cờ manifest
  (`has_slides/has_video/has_exercise`).

- **Kho công thức (skill bank)** — bàn giao skill khi nhân viên nghỉ
  việc, đúng màn "Người nghỉ việc" trên landing: beacon báo danh mục
  skill metadata trong snapshot → dashboard hiện cột "Công thức";
  admin bấm "Gom công thức" trong drawer máy → `POST /api/harvest`
  → cờ đi qua beacon resp → máy upload `.devin/skills` qua
  `POST /api/skills` (403 nếu admin chưa xin — giữ cam kết privacy);
  kho lưu `DATA/skills/<org>/<mid>.json` (worker: R2 + index D1
  `skill_bank`); beacon resp hint `bank` → máy kéo
  `GET /packs/<org>/bank.json` về áp theo luật sở hữu (bank-owned ghi
  đè, không đè pack/user). Card "Kho công thức" ở tab Pack.
- Rate limit tách counter GET/POST (240/60 mỗi phút/IP) — trước đây
  chung counter nên GET dashboard đủ nhiều là đói POST (parity
  collector.py ↔ worker).
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
- `tests/test-worker.py`: integration test worker qua wrangler dev +
  D1 local — đủ vòng đời 2-tầng (37 check). `test-fleet.py` thêm
  parity collector.py ↔ worker/index.js (endpoint set, worker-only
  khai trong WORKER_ONLY).
- Upload release giờ chỉ master (trước đây admin_key org cũng đẩy được).

### Sửa
- **Audit skill bank** (sau khi kho công thức lên):
  - `machine_id` giờ validate `[A-Za-z0-9][A-Za-z0-9._-]*` ngay ở
    `/api/pair` + chặn lần nữa trước khi ghi `skills/<org>/<mid>.json`
    — trước đây mid `../../x` ghi trốn ra ngoài DATA (py + worker).
  - Mid >200 ký tự bị cắt TRƯỚC khi check → DB lưu bản cắt còn máy
    beacon bản dài → lookup trượt mãi; giờ reject thay vì cắt.
  - `harvest_skills` skip filename xấu (`\`, `..`, drive, dotfile) —
    trước đây một tên xấu (POSIX cho phép) làm lint reject cả body →
    cờ `harvest` kẹt vĩnh viễn, dashboard "đang chờ" vô hạn.
  - `_bad_rel`/`badRel`/`_bad_relpath` chặn thêm filename `.`/rỗng —
    qua được lưới `..` nhưng `open(dir/.)` crash, kéo bank chết dở.
  - Worker parity: `lintSkills` chặn array (`typeof []==="object"`),
    `n_skills` đếm key khi skills là dict (không rớt field).
  - `apply_bank` tự guard `files` dict + `content` str (pack có
    `lint()` bảo vệ, bank trước đây tin collector lint).
- **Audit đợt 4 — collector.py + extension** (plan
  `plans/261126-1255-audit-4-fix`, 3 vòng audit-lại):
  - Tách vendor key god-mode thành 3 tầng: `telemetry.key` chỉ còn
    `POST /api/org-ping`; `vendor_read_key` (chỉ collector vendor) =
    read-rollup-only — `/api/fleet`, `/api/pending`, `/api/fleet/<mid>`
    403 (machine-level PII), mọi write 403; `release_key` riêng cho
    `POST /api/releases*` (admin_key org mất quyền đẩy release).
  - Re-pair máy approved không còn trả `machine_key` chỉ vì biết
    `beacon_secret`: set `repair=1` + pending; mọi approve ghi key vào
    `pending_key`, máy chỉ nhận key qua pair (migration v2) — rotate
    miễn phí, key cũ chết khi key mới phát.
  - Chống crash: `porg in ORGS` + pack_version int (traversal PoC),
    `_body`/`_as_dict` non-dict cả nested, org-ping payload cắt JSON
    → DoS dashboard, manifest `latest.json` upload + atomic write,
    RLock merge counts, `trust_proxy`+XFF, license org-match,
    prune `org_pings` 90 ngày.
  - Extension: ref `data-tlai` → `refMap` isolated world (trang không
    gắn ref giả được), snapshot bỏ `el.value`, `dom` strip CSRF token,
    `Object.hasOwn` + `{ok:false}`, `{...params, action}`, debugger
    idle-detach ~2 phút, `expectUrl` + `url` trong response, token
    restore sau 3×401, `externally_connectable` siết `:8080`.
  - Regression tự gây đã vá: first-approve không phát key (approve
    ghi `machine_key` trực tiếp → mọi máy phải duyệt 2 lần); revoke
    kẹt cờ repair; `badTokenFails` đếm x2 (onerror+onclose cùng
    handler).
  - Còn mở: `worker/src/index.js` chưa port repair flow (re-pair vẫn
    trả key cũ) — port D1 riêng, đợt sau.
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
- `tools/backup.py`: snapshot workspace + state .devin trước update/pack.
- `scripts/sync-fork.sh`: trích khác biệt từ fork cũ sang `packs/<org>/`.
- `build-release.sh`: cổng phát hành — git sạch, test suite, CHANGELOG,
  secret-scan zip, ký, xuất manifest.

### Sửa
- AGENTS.md đọc thêm `.devin/rules.local.md` (luật cty) — đứng trên lời
  dặn thường, dưới luật an toàn lõi.

## [1.0.0] — 2025-10

Bản đầu: portal + 3 bridge loopback + extension lái trình duyệt thật +
não ngoài qua ACP + sandbox/consent gate.
