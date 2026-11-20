# Phase 8 — `troly` single binary (đóng gói backend)

## Mục tiêu

Gói toàn bộ backend Python (stdlib-only) thành **một file chạy duy nhất**
`TroLyAI.exe` (Windows) / `troly` (macOS) — user không cần Python, không
cần start.bat, double-click là chạy.

Quyết định thiết kế then chốt: **một binary nhiều vai** — cùng file đóng vai
supervisor lẫn từng bridge, phân vai qua argv. Self-install: lần chạy đầu
tự giải nén payload (web/, skills packs, templates, extension/, AGENTS.md)
vào folder user `~/TroLyAI` — CWD agent = folder đó, layout giữ nguyên như
project hiện tại → **không phải đổi một dòng code bridge nào**.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/launcher.py` | create | entry point: `troly run/serve/chat-bridge/ext-bridge` + bootstrap + supervisor |
| `tools/build.sh` | create | script PyInstaller → dist/troly (kèm payload data) |
| `.gitignore` | modify | `build/`, `dist/`, `*.spec` |

## Chi tiết

### launcher.py (~200 dòng)

```
troly run          → bootstrap user dir → spawn 3 child: serve/chat-bridge/
                     ext-bridge (cùng binary, argv khác) → watchdog restart
                     → mở portal ?t=<token> → nằm chờ (tray icon để sau)
troly serve        → exec tương đương tools/serve.py
troly chat-bridge  → exec tương đương tools/chat-bridge.py
troly ext-bridge   → exec tương đương tools/ext-bridge.py
```

- Khi đóng bằng PyInstaller: `sys.argv` dispatch; các file tool import được
  vì đều stdlib → `import serve/chat_bridge/ext_bridge` và gọi main — hoặc
  đơn giản hơn: để các tool giữ nguyên `if __name__ == "__main__"`, launcher
  `runpy.run_path` hoặc gọi trực tiếp hàm sau khi gán sys.argv.
- **Bootstrap user dir**: `DATA = ~/TroLyAI` (Win: `%USERPROFILE%\TroLyAI`)
  → nếu thiếu `my-course/`, copy payload mặc định (web/, .devin/skill-packs/,
  templates/, extension/, AGENTS.md, README, VERSION, clone-compare.py…)
  từ resource trong binary ra. KHÔNG ghi đè nếu đã có.
- **Supervisor**: spawn `sys.executable`-style subprocess = `[exe, "chat-bridge"]`
  ×3; child chết → log + restart (backoff 2s, tối đa ~10 lần rồi báo trên
  portal khi mở). Đây luôn là "watchdog" đã bàn — process này không chết được
  trừ khi user tắt.
- CWD của mọi child = `DATA` → mọi path hiện tại (`.devin/`, `my-course/`,
  `brain.json`) đúng y hệt.
- `BRIDGE_TOKEN` sinh trong bootstrap (trước khi spawn child — vẫn đúng
  thiết kế "một điểm sinh").
- **Update cơ chế sau này**: `troly run` thấy `~/TroLyAI/VERSION` cũ hơn
  version trong binary → copy đè CHỈ phần code (web/, tools, skills packs,
  templates) — KHÔNG đụng `my-course/`, `brain.json`, `.devin/skills/`,
  secrets. Đây là đường update rẻ: phát hành = thay exe, user chạy lại.

### build.sh

```bash
pyinstaller --onefile --name troly \
  --add-data "web:web" --add-data ".devin/skill-packs:.devin/skill-packs" \
  --add-data "templates:templates" --add-data "extension:extension" \
  --add-data "AGENTS.md:." --add-data "VERSION:." \
  tools/launcher.py
```

(PyInstaller ~vài MB, không dep ngoài. macOS build trước; Windows build
trên máy Windows/CI — PyInstaller không cross-compile.)

### Startup tự chạy (tuỳ chọn trong ⚙)

`troly run --register-startup` → Win: registry `Run` key; macOS:
`~/Library/LaunchAgents` plist. Toggle trong settings panel.

## Acceptance

- `troly run` trên máy sạch → tạo `~/TroLyAI` đầy đủ → 3 port lên → mở
  portal có token → chat được (não đã cài)
- Kill một child → supervisor tự bật lại
- Chạy lại `troly run` → không ghi đè my-course/brain/secrets
- `dist/troly` chạy được trên máy KHÔNG cài Python

## Rủi ro

- PyInstaller bị antivirus Windows đánh dấu (false positive phổ biến) →
  cần ký code sau (ghi roadmap; giai đoạn pilot chấp nhận)
- Payload trong binary cũ → nhờ cơ chế update-đè-code ở trên
