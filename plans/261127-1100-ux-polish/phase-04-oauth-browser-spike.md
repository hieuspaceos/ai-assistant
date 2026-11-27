# Phase 04 — Spike: đăng nhập não qua trình duyệt thay vì mở terminal

## Lý do

Onboarding hiện có bước `brainLogin`: "Mở terminal đăng nhập não" —
một cửa sổ dòng lệnh pop lên, học viên phải tự đăng nhập trong đó rồi
quay lại bấm "kiểm tra lại". Đây là chỗ duy nhất trong onboarding buộc
người không biết code chạm vào màn hình đen.

Nhưng **không phải não nào cũng hỗ trợ** đăng nhập trình duyệt gọn —
mỗi CLI một kiểu (OAuth device flow, mở browser rồi bắt callback
localhost, chỉ có TUI login...). Phase này là **spike khảo sát**, ra
bảng sự thật rồi mới quyết làm gì. Không code trước.

## Bảng khảo sát (điền vào `findings.md`)

Với mỗi não trong `BRAIN_PRESETS` của `chat-bridge.py`:

| Não | Lệnh login | Kiểu auth | Tự đóng được không | Ghi chú |
|---|---|---|---|---|
| devin | `devin login`? | ? | ? | |
| gemini | `gemini` (login trong TUI) / `gemini auth`? | ? | ? | |
| codex-acp | `codex login` | ? | ? | |
| claude-acp | `claude` | ? | ? | |
| goose | `goose configure`? | ? | ? | |
| opencode | `opencode auth`? | ? | ? | |

Câu hỏi cần trả lời cho từng não:

1. Login có mở browser được không (URL OAuth + callback localhost)?
2. Callback xong tab có tự đóng / hiện "you may close this tab" không,
   hay phải paste code ngược vào terminal?
3. CLI có subcommand headless để check trạng thái đăng nhập không
   (`whoami`, `auth status`)? — cần cho nút "kiểm tra lại".
4. Non-interactive được không (env var, `--no-browser` + URL riêng)?

## Hai kịch bản đích (chọn theo kết quả spike)

### Kịch bản A — não hỗ trợ browser auth

- Onboarding bấm "Đăng nhập não" → bridge mở URL OAuth trong tab mới
  → não tự xử callback → portal poll `auth status` → xanh thì sang
  bước, không terminal nào hiện.
- Cần thêm: endpoint `/api/brain/login` spawn lệnh login của não với
  cờ browser-mode (nếu CLI hỗ trợ), bắt stderr (phase 03 đã có) để
  lấy URL nếu CLI không tự mở.

### Kịch bản B — não chỉ có TUI login

- Giữ "mở terminal đăng nhập" nhưng **đóng khung cho đỡ sợ**: cửa sổ
  đó mở kèm dòng hướng dẫn in sẵn + tự đóng khi login xong (script
  wrapper `login-<não>.sh/.ps1` chờ exit code), portal poll trạng
  thái và tự sang bước — học viên không phải bấm "kiểm tra lại".
- Card stderr từ phase 03 báo lỗi login rõ ràng hơn.

## Deliverable

`findings.md` trong plan folder này: bảng trên điền đủ + quyết định
A/B từng não + diff nhỏ áp cho não nào được A (đổi `BRAINS[].desc`/
thêm field `login: {type: "browser"|"tui", cmd: ...}` vào brain.json
schema).

## Ra ngoài phạm vi

- Không tự viết OAuth flow riêng cho não nào — chỉ điều phối thứ CLI
  sẵn có.
- Không lưu credential — não tự giữ phiên trong keychain/profile của
  nó như hiện tại.
