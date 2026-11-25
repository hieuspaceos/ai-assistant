# ai-assistant — Codebase Summary

Bản đồ file theo vai trò. Inventory thật: `git ls-files`.

## Root

| File | Vai trò |
|---|---|
| `AGENTS.md` | Persona "giáo viên ELI10" + quy tắc an toàn — áp cho mọi session agent |
| `README.md` | Giới thiệu + cấu trúc folder |
| `SETUP.md` | Hướng dẫn cài cho học viên (Windows Terminal, Devin CLI, ttyd) |
| `start.bat` / `start.sh` | Launcher: serve :8080 + chat-bridge :7682 + ext-bridge :7684 + ttyd :7681 + mở browser |
| `brain.json` | "Não" agent đang dùng — `{id,label,cmd,args,terminal}`; mặc định devin, đổi trong onboarding/panel Cài đặt hoặc `POST /api/brain` |

## tools/ — các bridge và tiện ích

| File | Vai trò |
|---|---|
| `serve.py` / `serve.ps1` | Static server: chặn dotfiles, Host check chống rebinding, CSP `sandbox` opaque-origin `/my-course/`+`/intro/`, Range, keep-alive |
| `chat-bridge.py` / `.ps1` | Chat portal ↔ não ACP (`brain.json` chọn não, `/api/brain` đổi nóng); API config/permissions/connections/secrets/save-page; long-poll + prompt_lock + respond-gate; spawn não qua Seatbelt (macOS) |
| `term-gate.sh` / `.cmd` | Cửa gác giữa ttyd và não — đòi mã kết nối (từ `?arg=`) trước khi exec não; macOS bọc sandbox-exec |
| `gen-sandbox.py` | Sinh `.devin/agent.sb` từ `permissions.json` — whitelist write + deny-enumerate read + deny exec binary thoát-sandbox |
| `setup-agent-user.ps1` | Windows sandbox (admin một lần): tạo user hạn chế `troly-agent`, ACL icacls tương đương Seatbelt, credential DPAPI → `.devin/agent-user.cred`; `chat-bridge.ps1` spawn não cross-user qua `CreateProcessWithLogonW` (`TroLy.AgentSpawn` + Job Object) — verify trên CI `test-windows` |
| `launcher.py` | Supervisor của bản đóng gói (`troly`/`TroLyAI.exe`) — tự dựng `~/TroLyAI`, spawn 4 process |
| `build.sh` | Đóng gói binary một file (PyInstaller) |
| `chat-terminal.ps1` | Chạy ttyd theme sáng font lớn (Windows), qua term-gate |
| `ext-bridge.py` | HTTP `/api/browser` ↔ WS extension — lái trình duyệt thật; WS auth trước handshake, cap 64MB |
| `clone-compare.py` | So clone vs nguồn: `harvest`/`styles`/`shot` — pha 4 của /clone-trang |
| `scene-player.html` | Player cho `scene.json` của bài học (demo có điều khiển) |
| `test-bridges.py` | Smoke test endpoint: auth 401, save-page sandbox, brain whitelist — spawn bridge thật trên port động |
| `test-parity.py` | Diff tập endpoint `/api/*` giữa chat-bridge `.py` ↔ `.ps1` — bắt drift |
| `test-packs.py` | Diff `.devin/skills/` ↔ `skill-packs/` + kiểm recipes trỏ đúng skill — bắt "quên đồng bộ pack" |

## extension/ — MV3 "Trợ Lý AI"

| File | Vai trò |
|---|---|
| `manifest.json` | Quyền: tabs, debugger (CDP cho nhóm t*), scripting, storage |
| `background.js` | WS client tới ext-bridge; dispatch action; tab/debugger control |
| `content.js` | Snapshot cây, click/type/scroll, trích dom/styles/assets/css trong trang |

## web/ — portal

| File | Vai trò |
|---|---|
| `index.html` + `app.js` + `styles.css` | Portal chính: danh sách bài học từ manifest, tab Chat/Terminal |
| `chat.html` | Giao diện chat bong bóng (markdown) ↔ chat-bridge |
| `clone-view.html` | Viewer trang clone: toàn màn hình, thanh sửa nội dung tại chỗ, Lưu/Tải về |
| `onboarding.html` | Wizard lần đầu: ngôn ngữ, tên, folder, app kết nối |
| `vendor/` | Thư viện đóng gói sẵn cho trang tĩnh |

## .devin/

| Đường | Vai trò |
|---|---|
| `skills/<tên>/SKILL.md` | Skill đang active — onboarding copy từ skill-packs |
| `skill-packs/vi/` | 20 skill tiếng Việt (/phong-van /hoc-bai /doc-zalo /clone-trang …) |
| `skill-packs/en/` | 20 skill English tương ứng (/interview /tutor /read-zalo /clone-page …) |
| `skill-packs/recipes/` | `<lang>.json` — recipes sidebar theo ngôn ngữ, `/api/setup` ghi vào manifest |
| `agents/slide-builder.md` | Subagent dựng `slides.html` từ nội dung bài |
| `agents/video-builder.md` | Subagent: `video-script.md` (luôn) + `video.mp4` (bonus) |

## templates/

Khung bài học: `lesson.md`, `exercise.md`, `video-script` template,
`slide-deck.html` (slide-builder nhân bản rồi đổ nội dung).

## my-course/ — dữ liệu của học viên

| Đường | Vai trò |
|---|---|
| `config.json` | `language`, `learner_name` — onboarding ghi |
| `permissions.json` | Folder agent được đọc/ghi ngoài my-course |
| `connections.json` | Trạng thái kết nối app/web + field bí mật (`secret:true`) |
| `manifest.json` | Danh sách bài học — portal đọc để render |
| `lesson-XX-<slug>/` | Một bài: guide.md, exercise.md, video-script.md, slides.html, video.mp4, scene.json, sample-files/ |
| `clone-work/<site>/` | Số liệu đo mỗi site clone: ref-dom, ref-styles, ref-css/, ref-assets, ref-shot-*, ref-states.md, tokens.md |
| `trang-*.html` | File clone thành phẩm (mở trong clone-view hoặc trực tiếp) |

## intro/

`slides.html` — deck giới thiệu tĩnh (Bài 0) trước khi có khoá học riêng.

## site/ — landing page troly.hieuspace.com

HTML/CSS/JS thuần (`index.html`, `privacy.html`, `*.css`, `assets/` —
video demo + poster). Deploy = copy ra branch `gh-pages` (+ `CNAME`),
GitHub Pages phục vụ. `.hallmark/` giữ ảnh chụp review, không deploy.

## plans/

Kế hoạch nhiều phase đã/thực thi — mỗi folder `YYMMDD-HHMM-<tên>/` có
`plan.md` + `phase-NN-*.md`.
