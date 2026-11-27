# Findings — spike đăng nhập não qua trình duyệt (phase 04)

Nguồn: docs chính thức của từng CLI + đọc `BRAIN_PRESETS` trong
`tools/chat-bridge.py`. Ô đánh **(cần verify)** là chưa chạy thật trên
máy đích — lệnh verify ghi kèm cuối bảng. Điền ngày 2026-01.

## Bảng khảo sát

| Não | Lệnh login | Kiểu auth | Tự đóng được không | Ghi chú |
|---|---|---|---|---|
| devin | `devin auth login` | OAuth browser → callback localhost **(cần verify)** | Có thể — `devin auth status` check được **(cần verify)** | Não mặc định, trả phí. API-key path: env/`devin auth login --api-key` nếu có. |
| gemini | `gemini` → chọn "Login with Google" trong TUI | OAuth browser → callback localhost, trang "may close this tab" | Không — login nằm TRONG TUI, không có lệnh `auth login` riêng **(cần verify bản mới — vài bản có `gemini auth`)** | Miễn phí — não gợi ý cho người mới. Headless: `GEMINI_API_KEY` env. |
| codex | `codex login` | OAuth browser → callback localhost; có `codex login --device-auth` (device code) cho máy không mở browser được | `codex login status` check headless được | Qua adapter npx codex-acp. **Ứng viên A mạnh nhất**: login rời TUI, check trạng thái sạch. API-key: `codex login --api-key` / `OPENAI_API_KEY`. |
| claude | `/login` trong TUI; `claude setup-token` headless | OAuth browser → **paste code ngược lại terminal** (setup-token), hoặc OAuth trong TUI | `claude setup-token` in URL + chờ paste → wrapper chờ exit được | Qua adapter npx claude-agent-acp. Không callback tự đóng sạch — nửa A nửa B. `ANTHROPIC_API_KEY` env. |
| opencode | `opencode auth login` | Menu provider trong TUI → OAuth (browser + paste code) hoặc nhập API key tuỳ provider | `opencode auth list` check được — nhưng bước chọn provider là TUI | BYOK — flow nhiều nhánh theo provider, khó đóng khung một kiểu. |
| goose | `goose configure` | TUI wizard → chọn provider → nhập API key (vài provider OAuth) | `goose configure` là wizard tương tác — không non-interactive | BYOK — gần như chắc B. |

## Quyết định A/B từng não

- **codex → A**. `codex login` tự mở browser, callback tự đóng tab,
  `codex login status` làm nút "kiểm tra lại" không cần hỏi. Endpoint
  `/api/brain/login` spawn `codex login` với env bình thường là đủ.
- **devin → A nếu verify đúng** `devin auth login` mở browser +
  `devin auth status` đọc được. Verify bằng cách chạy trên máy đã cài.
- **gemini → B** (trừ khi verify thấy `gemini auth` rời TUI). Wrapper
  `login-gemini.sh/.ps1`: mở terminal chạy `gemini`, in sẵn dòng dẫn
  "bấm số 1 để đăng nhập Google", watch cho `~/.gemini/oauth_creds.json`
  xuất hiện → tự đóng + portal sang bước.
- **claude → B** qua `claude setup-token`: wrapper in URL cho học viên
  mở browser, paste code vào, xong tự đóng (exit code). Không cần portal
  poll vì wrapper tự kết thúc.
- **opencode → B**, **goose → B**: flow BYOK nhiều nhánh TUI, đóng khung
  bằng wrapper in dẫn + chờ exit. Card stderr phase 03 bắt lỗi login.

## Diff nhỏ áp khi làm (ngoài phase này)

Thêm field `login` vào schema brain preset (cả `chat-bridge.py` lẫn
`.ps1` — parity):

```python
"login": {"type": "browser",          # → nút "Đăng nhập" mở browser
          "cmd": ["codex", "login"],
          "check": ["codex", "login", "status"]}
# hoặc
"login": {"type": "tui",              # → wrapper script có dẫn sẵn
          "script": "login-gemini"}
```

Onboarding `brainLogin`: não `type:"browser"` → gọi endpoint spawn
login + poll `check`; `type:"tui"` → giữ đường terminal nhưng chạy
wrapper script thay vì lệnh trần.

## Việc verify còn lại (khi có máy thật)

- `devin auth login --help` → cờ browser/api-key; `devin auth status`.
- `gemini --version` mới nhất có `gemini auth` chưa; file creds
  `~/.gemini/oauth_creds.json` có đúng tên không.
- `claude auth status` / `claude /status` headless được không.
