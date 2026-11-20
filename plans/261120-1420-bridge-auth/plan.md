---
title: "Siết bảo mật + đóng gói cho production (đợt 1+2)"
description: "Gắn khoá cho toàn bộ bridge bằng bridge.token + luật 'dữ liệu không phải lệnh' chống prompt injection + đóng gói troly single-binary/installer/extension-store — điều kiện để user thật dùng được và mở đường cho remote/mobile"
status: pending
priority: P1
effort: L
branch: main
tags: [security, auth, infra, packaging, critical]
created: 2026-11-20
---

# Siết bảo mật + đóng gói cho production (đợt 1+2)

## Bối cảnh — tại sao làm

Audit production phát hiện: mọi API bridge (`:7682`, `:7684`) không có auth —
process local bất kỳ gọi được `/api/secrets`, `/api/prompt`, `/api/save-page`,
và `/api/browser` (lái trình duyệt đã đăng nhập = confused deputy). Lỗ hổng
thật hiện hữu: `ext-bridge` WS `/ext` chỉ kiểm Origin khi header có mặt —
process local không gửi Origin chiếm được slot extension, nhận mọi lệnh agent.

Đồng thời chưa có phòng thủ prompt injection: agent đọc nội dung Zalo/web
rồi hành động — nội dung độc có thể ra lệnh giả.

Cả hai phải đóng TRƯỚC khi làm relay/mobile/installer.

## Thiết kế tổng thể

**Một "chìa khóa nhà" dùng chung**: `.devin/bridge.token`
- Dotfile → `serve.py` đã chặn serve ra web; thêm vào `.gitignore`
- Sinh MỘT LẦN trong `start.sh`/`start.bat` trước khi launch (tránh race giữa
  3 process); bridge fallback sinh bằng `O_CREAT|O_EXCL` atomic
- `chmod 600` trên unix
- Chấp nhận 2 cách trình: header `X-Bridge-Token` hoặc query `?token=`
- So token bằng `hmac.compare_digest` (chống timing)

**Phạm vi khoá:**

| Cửa | Khoá |
|---|---|
| `chat-bridge :7682` | mọi endpoint TRỪ `/api/health` + `OPTIONS` (preflight) |
| `ext-bridge :7684` | `/api/*` + WS `/ext?token=` (kiểm TRƯỚC origin check) |
| `serve.py :8080` | KHÔNG khoá — xem Trade-off #1 |

**CORS bắt buộc sửa**: cả 2 bridge thêm `X-Bridge-Token` vào
`Access-Control-Allow-Headers`, và `OPTIONS` phải miễn token — nếu không
preflight chết → mọi fetch portal chết kể cả khi có token.

**Ai lấy khoá ở đâu:**

| Consumer | Cách |
|---|---|
| Portal (`app.js`…) | `?t=` trong URL start mở → `localStorage` → header mọi fetch; iframe cùng origin đọc chung localStorage |
| Agent (skill) | CHÍNH: đọc file `.devin/bridge.token`. TẮT: env `$BRIDGE_TOKEN` (export trước spawn — chưa chứng minh exec tool kế thừa env, dùng làm fallback) |
| Extension | auto-pair qua `externally_connectable` từ onboarding; fallback ô dán trong options page |
| ttyd/terminal | export `BRIDGE_TOKEN` trước khi chạy ttyd |

## Trade-off đã quyết (ghi nhận, không sửa trong plan này)

1. **`serve.py` GET mở trên loopback**: `<img>` trong clone không gắn được
   token; process local đọc file trên disk được anyway → khoá HTTP loopback
   không thêm gì. `.devin/` đã bị chặn từ trước.
   **KHI CÓ RELAY (bắt buộc)**: GET `/my-course/` qua token, `/.shots/`
   (screenshot tab có thể chứa tin nhắn) chặn hoặc khoá riêng.
2. **`/api/health` mở**: chỉ trả `ok`+`brain`+`version`, không data; cần cho
   liveness/watchdog.
3. **Token trong `?t=` nằm trong history/bookmark**: chấp nhận trên loopback;
   ghi vào SECURITY.md.
4. **Cookie thay header**: bỏ — cookie theo port, `:8080` không phủ
   `:7682`/`:7684`, không giải quyết cross-port.

## Phases

| # | Phase | Nội dung | Link |
|---|-------|----------|------|
| 1 | Token infra + chat-bridge.py | sinh token, `_authed()`, CORS fix, env export | [phase-01](./phase-01-token-infra.md) |
| 2 | ext-bridge.py auth | `/api/*` + WS `/ext?token=`, vá lỗ hổng no-Origin | [phase-02](./phase-02-ext-bridge.md) |
| 3 | Portal/web plumbing | `?t=` bootstrap, fetch wrapper, Mã kết nối trong ⚙ | [phase-03](./phase-03-portal-web.md) |
| 4 | Extension pairing | manifest `key`+`externally_connectable`, auto-pair, options fallback | [phase-04](./phase-04-extension.md) |
| 5 | Windows parity | chat-bridge.ps1, start.bat, chat-terminal.ps1 | [phase-05](./phase-05-windows.md) |
| 6 | Agent rules + skills | AGENTS.md "dữ liệu ≠ lệnh", CLAUDE.md pointer, skills+packs | [phase-06](./phase-06-rules-skills.md) |
| 7 | Docs + VERSION + test | SECURITY, api-reference, runbook, decision-log, test matrix | [phase-07](./phase-07-docs-test.md) |
| 8 | `troly` single binary | PyInstaller 1-file: supervisor + bootstrap user dir + watchdog + update-đè-code | [phase-08](./phase-08-single-binary.md) |
| 9 | Distribution | extension lên Web Store + não tự cài trong onboarding + installer (tuỳ chọn) | [phase-09](./phase-09-distribution.md) |

## Rủi ro chính

- **R1**: quên OPTIONS/Allow-Headers → portal chết hoàn toàn (test case đầu)
- **R2**: exec tool của não không kế thừa env → `$BRIDGE_TOKEN` rỗng → skill
  fail → fallback đọc file là đường chính (đã thiết kế)
- **R3**: token race lúc start → sinh trong start script (đã thiết kế)
- **R4**: skill trong `skill-packs/` quên cập nhật → onboard máy mới cài bản
  cũ (phase 6 sửa CẢ packs)
- **R5**: não là Claude → đọc `CLAUDE.md` không phải `AGENTS.md` → luật an
  toàn biến mất → pointer file (phase 6)

## Out of scope (ghi rõ để không scope-creep)

- Relay/VPS, mobile — đợt sau (thiết kế đã chốt ở phiên trước)
- Khoá GET `my-course/` trên loopback (để đợt relay)
- Auto-update online (update = phát exe mới, phase 8 đủ cho giai đoạn này)
- `/api/report`, multi-tenant, rotation UI
- Ký code / notarization (cần khi scale — SmartScreen/Gatekeeper sẽ cảnh
  báo file lạ, chấp nhận trong pilot)

## Thứ tự thực thi

Auth (phase 1-7) và đóng gói (phase 8-9) độc lập — có thể làm song song,
nhưng khi release cho user thật thì BẮT BUỘC đợt auth xong trước (phát tán
bản chưa khoá = phát tán nhà không khoá).
