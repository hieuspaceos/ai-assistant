---
title: "Vá findings audit đợt 6 (2 vòng + re-audit plan) — serve.ps1 CSP suffix, endpoint ps1 thiếu, org-ping worker↔collector, secrets wipe mất creds first-save, walkthrough open-url scheme, node Linux không pin sha256, emit-event giả tín hiệu rollout"
description: "Audit đợt 6 hai vòng chấm 4 trục (đồng bộ/bảo mật/hiệu năng/scale) toàn app: serve+bridge+ext-bridge+collector+worker+beacon+guards+portal+extension+deploy. Nền tiếp tục tốt — không lỗ hổng mới CAO độc lập; các CAO đều là drift parity .py↔.ps1/.js hoặc bug sót trên bản Windows. Nặng nhất: serve.ps1 chỉ CSP .html/.htm → .svg độc dưới workspace trên Windows XSS origin portal trộm bridge_token (đúng audit-5 N4 đã vá trên .py); chat-bridge.ps1 thiếu 5 endpoint portal gọi (bot gallery + cài não 1-click chết ngầm, onboarding first-run vỡ); chat-bridge.ps1 secrets wipe chỉ giữ url → first-save mất user/password (creds Windows không bao giờ lưu được đủ — bug functional sống); worker /api/org-ping đòi master thay vì telemetry key → rollup fleet từ collector tự-host về hosted tier 403 mãi. Kèm: walkthrough open-url không scheme-check (cùng class audit-5 F2 đã vá ở connections), install-brain Linux x64 sha256=None, emit-event whitelist 2 type rollout không-caller (agent emit giả tín hiệu), collector q() mở conn mới mỗi query, _merged_bank O(machines)/pull không cache. Re-audit plan sửa 5 lỗi kỹ thuật trong draft v1 (xem từng phase)."
status: draft
priority: P1
effort: L
branch: main
tags: [security, parity, windows, worker, fleet, perf, audit-fix]
created: 2026-11-27
depends-on: 261126-1411-audit-5-fix (đã xong)
---

# Vá findings audit đợt 6

## Bối cảnh

Audit 2 vòng (báo cáo trong conversation) bao phủ `serve.py`/`serve.ps1`,
`chat-bridge.py` (2728 dòng) /`chat-bridge.ps1` (1687 dòng),
`ext-bridge.py`, `collector.py`, `worker/src/index.js`,
`beacon.py`/`beacon.ps1`, `update.py`, `apply-pack.py`,
`install-brain.py`, `path_guard`/`cmd_deny`/`content_guard`/`gen-sandbox`,
`term-gate.*`, `read-brain.ps1`, `setup-agent-user.ps1`,
`web/app.js`/`chat.html`/`bridge-token.js`, `extension/` toàn bộ,
`collector-web/`, `start.sh`/`start.bat`, `troly.spec`, `.gitignore`.

Mô-típ lỗi đợt này: **drift parity — vá một bên, sót bên kia**, đúng
điểm yếu code đã tự ghi ("nhân bản = drift chắc chắn" trong path_guard
/header). 3 CAO đều là dạng này: audit-5 N4 vá CSP trên .py sót .ps1;
endpoint mới thêm .py sau "đóng băng" .ps1 nhưng portal gọi vô điều
kiện; org-ping thêm khi collector.py là canonical rồi port worker thiếu
đường telemetry key. Khác đợt 5 ("đường tắt chưa qua lưới"), đợt này
là "lưới đã đúng nhưng chỉ ở một bản song ngữ".

## Bản đồ finding → phase

| # | Finding (mức) | Phase |
|---|---|---|
| F1 | `serve.ps1` chỉ áp CSP sandbox cho `.html`/`.htm` — thiếu `.svg .xml .xhtml .xht .shtml .mhtml .mht` mà serve.py:43-44 cover; `.svg` độc dưới `/workspace/`/`/intro/` mở trực tiếp trên Windows → script trong origin :8080 → đọc `localStorage.bridge_token` → mọi API bridge (CAO — regression audit-5 N4 trên nền chính) | 01 |
| F2 | `chat-bridge.ps1` `/api/secrets` nhánh wipe gán `$entry = @{ url = ... }` — vứt mọi field khác, và `$oldUrl=$null` ở first-save cũng kích wipe → **save creds trên Windows chỉ giữ url, mất user/password** → probe kết nối fail mãi (CAO functional — bug sống trên nền chính, không chỉ parity; kèm check lệch `url` vs `url\|host\|endpoint` py:2412) | 02 |
| F3 | `Test-SensitivePath` ps1 dùng `GetFullPath` lexical không resolve junction — parity gap với `path_guard.realpath`; junction sẵn có trỏ vào folder nhạy cảm lọt check (LOW — cần junction tạo trước) | 02 |
| F4 | `worker` `/api/org-ping` đòi `role === "master"` (index.js:1062) — collector.py:847 nhận `X-Admin-Key` = `PING_KEY`/telemetry; collector tự-host ping về hosted tier → 403 mãi → `org_pings` hosted trống, dashboard vendor mất rollup org self-host; `telemetry.key` vô dụng trên worker (CAO parity) | 04 |
| F5 | `chat-bridge.ps1` thiếu **5** endpoint portal gọi: `/api/bots`, `/api/bot`, `/api/bot-import`, `/api/bot-import-confirm`, `/api/install-brain` — onboarding.html:368+ gọi install-brain ở first-run → "cài não 1-click" chết ngầm ngay lần mở đầu trên Windows. (Re-audit: `pick-folder`/`reveal` py là darwin-only → không phải regression; `/api/config` ps1 đã có → PY_ONLY_OK stale.) Cần quyết định: port hay feature-gate portal (CAO) | 05 |
| F6 | Walkthrough `open-url`: `window.open(sub(s.url))` không check scheme (app.js:761) — `javascript:` kế thừa origin portal → đọc token + UI redress; cùng class audit-5 F2 đã vá ở connections.open_url; `test-walkthrough.py:41` chỉ check field tồn tại (MED — não đã cầm token nên escalation hạn chế, nhưng chạy code trong browser context học viên) | 03 |
| F7 | `install-brain.py` `NODE_DIST[("Linux","x86_64")]` sha256=None → fetch bỏ check (`want_sha` falsy short-circuit) — binary thành não gemini trên Linux chỉ qua HTTPS trần, mọi nền khác pin cứng (MED-LOW) | 03 |
| F8 | `/api/emit-event` whitelist gồm `pack_applied`/`update_applied` (chat-bridge.py:2649) — agent tự emit → dashboard báo "đã update" cho máy chưa update. (Re-audit: KHÔNG caller nào emit 2 type này → vá = xoá khỏi whitelist, không cần internal-token) (MED-LOW) | 02 |
| F9 | `collector.py` `q()` → `db()` mở conn mới MỖI query + chạy `CREATE TABLE IF NOT EXISTS meta` (DDL write trên mọi read) + SELECT schema_version + vòng migrate — beacon ~10 queries = ~10 connects + 10 schema-check, thuần lãng phí dưới `_db_lock` global (MED perf) | 05 |
| F10 | `_merged_bank` O(machines×size)/pull không cache (collector.py:1060); worker N R2 GET **tuần tự** (index.js:454-473) — mỗi máy kéo bank = quét toàn fleet (MED perf/scale) | 05 |
| F11 | `beacon.ps1` đá `python update.py`/`apply-pack.py` trong `catch {}` — máy fleet Windows không-Python nhận hint nhưng im lặng không áp, collector không biết (TRUNG — đã báo nhưng cần kênh báo ngược, không chỉ vá yên lặng) | 04 |
| F12 | Deny-list `BRAIN_CMD_DENY` nhân bản 4 nơi (cmd_deny.py ↔ term-gate.sh ↔ term-gate.ps1 ↔ read-brain.ps1) — đã so: hiện khớp, nhưng không test nào bắt drift (LOW nợ kỹ thuật) | 06 |
| F13 | `onMessageExternal` cứng port `:8080` (background.js:86) — đổi port portal thì auto-pair chết ngầm (LOW) | 06 (note) |

## Nguyên tắc vá

1. **Parity .py ↔ .ps1 ↔ .js.** Mọi vá ở một bên phải so hai bên kia
   trong cùng commit — đợt này F1/F2/F3/F4 đều là "vá đúng một bên".
   Sửa `.ps1` PHẢI ghi file kèm BOM (bài học audit đợt 1).
2. **F5 là quyết định, không phải vá thuần.** `PY_ONLY_OK` trong
   test-parity.py là sự đóng băng có khai báo — trước khi port phải
   chọn: (a) port đủ 5 endpoint (nặng, ~300-400 dòng ps1 mới), hay
   (b) feature-gate portal (ẩn bot gallery/install nút khi bridge báo
   không hỗ trợ) + giữ PY_ONLY_OK. Đề xuất (b) cho bot cluster; riêng
   `install-brain` cân nhắc vì onboarding Windows là first-run của đa
   số học viên — nếu gate thì phải có fallback hướng dẫn cài tay.
   `pick-folder`/`reveal` không cần port (darwin-only cả ở py) — chỉ
   đánh dấu DARWIN_ONLY hoặc stub "không hỗ trợ" cho parity-list sạch.
3. **Security fix ở cả điểm enforce lẫn điểm lint** — F6 vá
   `window.open` renderer VÀ `test-walkthrough.py` validator, giống
   pattern audit-5 (connections vá ở `_h_connections` + `apply-pack`).
4. **Key mới = nguồn mới, không phải role mới.** F4 thêm PING_KEY
   env vào worker — và phải HOIST `/api/org-ping` lên TRƯỚC admin
   gate chung ở `doPost` (index.js:822): request chỉ mang PING_KEY
   không phải admin credential, sẽ chết 401 trước khi tới handler —
   handler phải tự xác thực (PING_KEY hoặc master), y py.
5. **Perf vá điểm nghẽn đo được, không tối ưu mò.** F9/F10 vá bằng
   conn-reuse + cache-keyed-version — giữ `_db_lock` (đúng cho
   SQLite single-writer), không chuyển pool.
6. **Test trước docs sau.** Mỗi vá có test trong test-parity /
   test-bridges / test-worker / test-fleet; SECURITY.md cập nhật
   residual ở phase cuối.
7. **Không phá tuyên bố "đóng băng" khi chưa quyết.** Mọi endpoint
   mới đẩy vào .ps1 phải đồng thời xoá khỏi `PY_ONLY_OK` — list đó
   là nguồn sự thật về trạng thái đóng băng.

## Done khi

- `python3 tools/test-parity.py tools/test-bridges.py
  tools/test-distribution.py tools/test-packs.py tools/test-gates.py
  tools/test-fleet.py tools/test-worker.py tools/test-walkthrough.py
  tools/test-content-guard.py` PASS.
- CI `test-windows` xanh (F1/F2/F3 cần test trên Windows thật).
- SECURITY.md ghi đủ residual: emit-event tách quyền, F11 accepted-
  risk nếu chọn không port, F12 nợ parity deny-list.
- F5 có quyết định ghi lại (kể cả khi chọn "không port" — update
  PY_ONLY_OK comment + portal degrade có chủ đích, không silent).
