# ai-assistant — Codebase Summary

Bản đồ file theo vai trò. Inventory thật: `git ls-files`.

## Root

| File | Vai trò |
|---|---|
| `AGENTS.md` | Persona "giáo viên ELI10" + quy tắc an toàn — áp cho mọi session agent |
| `README.md` | Giới thiệu + cấu trúc folder |
| `SETUP.md` | Hướng dẫn cài cho học viên (Windows Terminal, Devin CLI, ttyd) |
| `start.bat` / `start.sh` | Launcher: serve :8080 + chat-bridge :7682 + ext-bridge :7684 + ttyd :7681 (chỉ khi `config.terminal` — mặc định TẮT, tiết RAM) + mở browser |
| `brain.json` | "Não" agent đang dùng — `{id,label,cmd,args,terminal}`; mặc định devin, đổi trong onboarding/panel Cài đặt hoặc `POST /api/brain` |

## tools/ — các bridge và tiện ích

| File | Vai trò |
|---|---|
| `serve.py` / `serve.ps1` | Static server: chặn dotfiles, Host check chống rebinding, CSP `sandbox` opaque-origin `/workspace/`+`/intro/`, Range, keep-alive |
| `chat-bridge.py` / `.ps1` | Chat portal ↔ não ACP (`brain.json` chọn não, `/api/brain` đổi nóng); API config/permissions/connections/secrets/save-page; long-poll + prompt_lock + respond-gate; spawn não qua Seatbelt (macOS) |
| `term-gate.sh` / `.ps1` | Cửa gác giữa ttyd và não — đòi mã kết nối (từ `?arg=`) trước khi exec não; macOS bọc sandbox-exec. `.cmd` chỉ là forwarder không-arg (batch không đọc argv an toàn) |
| `read-brain.ps1` | Đọc `brain.json` → in `cmd|terminal` ĐÃ validate (charset + deny-list) — `start.bat`/`chat-terminal.ps1` dùng chung, tránh expansion injection trong batch |
| `gen-sandbox.py` | Sinh `.devin/agent.sb` từ `permissions.json` — whitelist write + deny-enumerate read + deny exec binary thoát-sandbox; `_grant_ok` re-validate từng grant lúc build (path_sensitive trên realpath + symlink-divergence) — enforcement point chặn TOCTOU |
| `path_guard.py` | Policy đường dẫn nhạy cảm dùng CHUNG: `_SENSITIVE_DIRS`/`_SENSITIVE_ROOTS`, `path_sensitive` (two-way, case-insensitive, realpath), `rw_grant_ok` — chat-bridge kiểm lúc request/apply, gen-sandbox kiểm lúc phát quyền. Tên underscore bắt buộc (script gạch ngang import được); lọc `isabs` sau expanduser — entry không resolve được trên nền đó bị loại (Windows `~\…` trên POSIX và ngược lại) |
| `setup-agent-user.ps1` | Windows sandbox (admin một lần): tạo user hạn chế `troly-agent`, ACL icacls tương đương Seatbelt, credential DPAPI → `.devin/agent-user.cred`; `chat-bridge.ps1` spawn não cross-user qua `CreateProcessWithLogonW` (`TroLy.AgentSpawn` + Job Object) — verify trên CI `test-windows` |
| `launcher.py` | Supervisor của bản đóng gói (`troly`/`TroLyAI.exe`) — tự dựng `~/TroLyAI`, spawn 4 process |
| `build.sh` | Đóng gói binary một file (PyInstaller) |
| `chat-terminal.ps1` | Chạy ttyd theme sáng font lớn (Windows), qua term-gate |
| `ext-bridge.py` | HTTP `/api/browser` ↔ WS extension — lái trình duyệt thật; WS auth trước handshake, cap 64MB |
| `clone-compare.py` | So clone vs nguồn: `harvest`/`styles`/`shot` — pha 4 của /clone-trang |
| `scene-player.html` | Player cho `scene.json` của bài (demo có điều khiển) |
| `render-video.py` / `tts-vieneu.py` | Render `video.mp4` từ `scene.json`: chụp frame scene-player bằng trình duyệt headless + ghép ffmpeg, xuất kèm `.vtt` theo timing; giọng đọc ưu tiên VieNeu-TTS local (Apache-2.0, env `TTS_PY`/`TTS_VOICE`), fallback `say`/SAPI |
| `test-bridges.py` | Smoke test endpoint: auth 401, save-page sandbox, brain whitelist — spawn bridge thật trên port động |
| `test-parity.py` | Diff tập endpoint `/api/*` giữa chat-bridge `.py` ↔ `.ps1` — bắt drift |
| `test-packs.py` | Diff `.devin/skills/` ↔ `skill-packs/` + kiểm recipes trỏ đúng skill — bắt "quên đồng bộ pack" |
| `test-gates.py` | Mọi endpoint POST `/api/*` phải khai `GATED` (handler gọi `gate_local`/`New-Gate`) hoặc `OPEN_OK` — bắt "write đặc quyền quên consent gate"; `.py` enumerate `POST_ROUTES` dict rồi quét source method đích (`.ps1` vẫn regex-parse) |
| `beacon.py` / `.ps1` | Máy nhân viên → collector: pair (pending → approve ghi `pending_key` → pair sau nhận `machine_key`) rồi snapshot 15' (đếm lượt/version/license — không nội dung); pending poll 60s, fail backoff 300s×3 |
| `collector.py` | Trung tâm fleet (3 tier cùng code): pairing + approve/revoke + repair (re-pair máy approved → cờ `repair`, cấp lại key qua `pending_key` — migration v2), license check, dashboard, store `releases/` + `packs/` phát xuống, mirror upstream 6h. Khoá 3 tầng: `beacon_secret`/`admin_key` per-org, `telemetry.key` chỉ org-ping, `vendor_read_key` rollup-only + `release_key` upload release |
| `worker/` | **Port của collector.py** sang Cloudflare Workers + D1 + R2 — tier vendor-hosted ĐANG CHẠY tại `troly.hieuspace.com/fleet/`; `wrangler.toml` (route/cron/binding), `src/index.js`, `schema.sql`; thêm tầng tài khoản admin 2-role (admins/sessions/audit trong D1) |
| `update.py` | Máy kéo release: manifest no-redirect → sha256 + ed25519 (`ed25519.py` vendored, `vendor-pubkey`) → stage `.devin/update-stage/` → launcher apply + rollback |
| `apply-pack.py` | Áp config-pack cty vào `.devin/` — lint exec_allowlist, permissions/exec_allowlist chỉ máy mới, rules.local.md |
| `make-license.py` | Vendor: cấp license.json ký HMAC theo org/seats/expiry |
| `sign-release.py` + `ed25519.py` | Vendor: ký release offline (`--gen-key` sinh cặp khoá, privkey KHÔNG vào repo) |
| `sign-macos.sh` + `entitlements.plist` | macOS: codesign Developer ID + notarize (`notarytool --wait`) + verify quarantine — CI gọi cùng chuỗi qua secrets, local qua keychain profile `troly-notary` |
| `build-release.sh` | Release-readiness gate: test suite + secret-scan zip + changelog + git sạch |
| `sync-fork.sh` | Hút phần IMA-only từ `../ima-assistant` → `packs/ima/pack.json` (skill diff, config, workflows, rules) |
| `content_guard.py` | Lớp ranh giới: wrap UNTRUSTED (sanitize marker + NFKC fold + id hash), detect_injection advisory, scrub_env allowlist spawn, exec_allowed glob |
| `backup.py` | Snapshot `.devin/`+`workspace/` trước update/pack-apply — giữ 5 bản |
| `build-ext.sh` | Zip `extension/` → `dist/troly-ext-<ver>.zip` upload Web Store — lint giữ `key` (EXT_ID), connectable localhost-only |
| `test-fleet.py` | GATE plan 1: collector thật, đủ vòng đời pair→approve→beacon→revoke + parity endpoint-set collector↔worker (`WORKER_ONLY` khai rõ) |
| `test-worker.py` | Integration worker: `wrangler dev` + D1 local — bootstrap lock, login/session, orgs+license HMAC, cross-org 403/404, rotate-secret, audit, last-master lock |
| `test-distribution.py` | GATE plan 2: ký→verify→stage→apply pack→rollback hermetic |
| `test-content-guard.py` | GATE plan 6: wrap byte-shape, sanitize, fold+detect, allowlist, scrub, live /api/emit-event |

## deploy/ — bộ cài cho đội triển khai

| File | Vai trò |
|---|---|
| `DEPLOY.md` | Hướng dẫn cài N máy: kiến trúc 30s, bộ cài cty, 3 tier collector, nghiệm thu, vận hành, rollback |
| `install.ps1` / `install.sh` | Cài 1 máy: copy code (loại state/machine-local), ttyd, license+fleet vào `.devin/`, shortcut/LaunchAgent |
| `force-install.md` | Extension qua policy: Registry/GPO/plist `ExtensionInstallForcelist` — tự cài + tự update |
| `CHECKLIST.md` | Bản in 1 trang tick từng máy |
| `vendor-infra.md` | Hạ tầng vendor trên troly.hieuspace.com: site, /releases/, /fleet/ hosted collector, org-ping |
| `company/` | Người cài tự tạo — đặt `license.json` + `fleet.json` của cty trước khi zip bộ cài |

## extension/ — MV3 "Trợ Lý AI"

| File | Vai trò |
|---|---|
| `manifest.json` | Quyền: tabs, debugger (CDP cho nhóm t*), scripting, storage |
| `background.js` | WS client tới ext-bridge; dispatch action; tab/debugger control |
| `content.js` | Snapshot cây, click/type/scroll, trích dom/styles/assets/css trong trang |

## web/ — portal

| File | Vai trò |
|---|---|
| `index.html` + `app.js` + `styles.css` | Portal chính: danh sách công cụ từ manifest, tab Chat/Terminal, section Quy trình (workflow cards) |
| `chat.html` | Giao diện chat bong bóng (markdown) ↔ chat-bridge |
| `clone-view.html` | Viewer trang clone: toàn màn hình, thanh sửa nội dung tại chỗ, Lưu/Tải về |
| `onboarding.html` | Wizard lần đầu: ngôn ngữ, tên, folder, app kết nối |
| `vendor/` | Thư viện đóng gói sẵn cho trang tĩnh |

## .devin/

| Đường | Vai trò |
|---|---|
| `skills/<tên>/SKILL.md` | Skill đang active — onboarding copy từ skill-packs |
| `skill-packs/vi/` | 21 skill tiếng Việt (/phong-van /huong-dan /doc-zalo /tao-cong-cu …) |
| `skill-packs/en/` | 21 skill English tương ứng (/interview /guide /read-zalo /make-tool …) |
| `skill-packs/recipes/` | `<lang>.json` — recipes sidebar theo ngôn ngữ, `/api/setup` ghi vào manifest |
| `agents/slide-builder.md` | Subagent dựng `slides.html` — GIỮ LẠI cho sau này, luồng phỏng vấn không gọi |
| `agents/video-builder.md` | Subagent `video-script.md` + `video.mp4` — GIỮ LẠI, luồng không gọi |

## templates/

`walkthrough.json` — schema màn hướng dẫn tương tác (15 step kinds:
say/prompt/input/choice/pick-file/open-url/wait-perm/wait-run/auto/
spotlight/open/watch/download/check/copy/done + cond/optional/
then_probe/media). `lesson.md` — khung guide.md (bản đọc của
walkthrough). `exercise.md`/`video-script`/`slide-deck.html` giữ lại
cho slide-builder/video-builder — luồng mặc định không dùng.

## Walkthrough (portal)

`web/app.js` render walkthrough.json thành modal từng-bước (overlay +
spotlight + widget theo kind): `prompt` POST `/api/prompt`, `wait-*`/
`auto` poll `/api/poll` tự qua bước, `open` gọi `/api/reveal` mở
Finder, `cond` probe `/api/check-connection`+`/api/check-path`,
`optional` nút Bỏ qua, tiến trình lưu localStorage. Validator
`tools/test-walkthrough.py`. Runner là renderer câm — trí tuệ sinh
nội dung nằm trong skill `/tao-cong-cu` (en: `/make-tool`), kèm pattern
prompt-optional + wait-run lặp gánh lượt hỏi lẻ giữa run.

## workspace/ — dữ liệu của học viên

| Đường | Vai trò |
|---|---|
| `config.json` | `language`, `learner_name` — onboarding ghi |
| `permissions.json` | Folder agent được đọc/ghi ngoài workspace |
| `connections.json` | Trạng thái kết nối app/web + field bí mật (`secret:true`) |
| `manifest.json` | Danh sách công cụ — portal đọc để render |
| `tool-XX-<slug>/` | Một công cụ: walkthrough.json + guide.md — công cụ sinh trước đợt rework có thể kèm slides.html/video.mp4/exercise.md |
| `clone-work/<site>/` | Số liệu đo mỗi site clone: ref-dom, ref-styles, ref-css/, ref-assets, ref-shot-*, ref-states.md, tokens.md |
| `trang-*.html` | File clone thành phẩm (mở trong clone-view hoặc trực tiếp) |

## intro/

`slides.html` — deck giới thiệu tĩnh (phần giới thiệu) trước khi có bộ công cụ riêng.

## site/ — landing page troly.hieuspace.com

HTML/CSS/JS thuần (`index.html`, `privacy.html`, `tokens/base/style/
story.css`, `story.js`, `assets/` — video demo + poster). Deploy =
copy ra branch `gh-pages` (+ `CNAME`), GitHub Pages phục vụ.
`.hallmark/` giữ ảnh chụp review, không deploy.

Bố cục hiện tại: masthead (wordmark giữa, nav tách 2 cánh) → hero +
sơ đồ app (icon brand simple-icons inline SVG) → `#vong-quay`
storyband xanh đậm full-bleed (animation nhờ→làm→nhớ→tự chạy trong
`story.js`) → `#xem` switcher video → `#cho-cty` ctyband xanh nhạt:
5 tab màn hình giả render bằng HTML (fleet dashboard, máy nhân viên,
gói quy trình, người mới vào việc, người nghỉ việc) + 4 thẻ outcome +
một dòng "Cho bạn IT" + form card → formsubmit.co → `#hoi` FAQ +
bot SVG nhảy → `#tai` → footer căn giữa.

Gotcha deploy: Cloudflare cache CSS theo query string — mọi thay đổi
CSS phải bump `style.css?v=N` / `story.js?v=N` trong index.html, và
kiểm lại giá trị `?v` bằng grep sau khi sed (sed trong lệnh lỗi
syntax hoặc pattern không khớp sẽ âm thầm không chạy).

## plans/

Kế hoạch nhiều phase đã/thực thi — mỗi folder `YYMMDD-HHMM-<tên>/` có
`plan.md` + `phase-NN-*.md`.

## Phân phối & vận hành (đã có)

- `tools/beacon.py` (+`.ps1`) — báo danh 15' lên collector, kèm trigger
  update/apply-pack khi inbox có việc.
- `tools/collector.py` — collector một code cho 3 tier; endpoints
  /api/pair, /api/beacon, /api/license, /api/releases|packs, dashboard
  `collector-web/index.html`; `fleet-<org>.json` per-org.
- `worker/` — port collector.py → Cloudflare Workers+D1+R2, ĐANG LIVE
  tại `troly.hieuspace.com/fleet/` (tier vendor-hosted); secrets qua
  `wrangler secret` (backup `collector.json` gitignored); tài khoản
  admin 2 tầng master/cty-admin + orgs/audit trong D1 — tạo org qua
  dashboard không cần `wrangler secret put`.
- `tools/update.py` — kéo release ký ed25519 (pubkey trong `vendor-pubkey`,
  override `TROLY_VENDOR_PUBKEY` cho test), sha256 + verify + stage + rollback
  qua `tools/backup.py`; `tools/make-license.py` cấp license.
- `tools/apply-pack.py` — áp pack cty: skills/bots/connections/workflows/
  rules/permissions + `devin_files` (whitelist mcp_config*.json —
  env-allowlist cố ý ngoài whitelist vì nó un-scrub env) +
  `mycourse_files` (chỉ máy mới).
- `tools/content_guard.py` — bọc UNTRUSTED cho nội dung ngoài, sanitize,
  detect_injection, scrub_env; exec allowlist đọc `.devin/exec-allowlist.json`.
- `tools/build-release.sh`, `sign-release.py`, `build-ext.sh`,
  `sync-fork.sh` (merge khác-biệt fork → pack), `ed25519.py` vendored.
- `packs/IMA/pack.json` v3 — pack đầu đời thật (IMA Travel DMC).
- `deploy/` — install.ps1/sh, DEPLOY.md, force-install.md, CHECKLIST.md,
  vendor-infra.md. `site/` — landing + privacy (Chrome Store).
- Docs: docs/fleet.md, docs/distribution.md, docs/SECURITY.md,
  docs/case-study-ima.md (skeleton), docs/troubleshooting-runbook.md.
- Test: test-fleet, test-worker, test-distribution, test-content-guard,
  test-packs, test-gates, test-parity, test-bridges.
