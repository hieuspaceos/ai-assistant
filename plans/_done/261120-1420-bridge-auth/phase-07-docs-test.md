# Phase 7 — Docs + VERSION + test

## Mục tiêu

Docs khớp với thực tế mới; `/api/health` có `version`; test ma trận đầy đủ.

## File động

| File | Action | Việc |
|---|---|---|
| `VERSION` | create | `1.0.0` — health trả ra |
| `docs/SECURITY.md` | modify | viết lại mô hình auth + threat model + yêu cầu relay |
| `docs/api-reference.md` | modify | mục auth + cập nhật mọi ví dụ curl kèm token |
| `docs/troubleshooting-runbook.md` | modify | curl examples kèm token + mục rotation |
| `docs/decision-log.md` | modify | entry: tại sao token loopback, tại sao GET :8080 mở |
| `SETUP.md` | modify | nhắc: extension ID mới → cài lại; mã kết nối ở ⚙ |
| `docs/INDEX.md` | modify | nếu cần cập nhật map |

## SECURITY.md — nội dung cần có

- Mô hình khoá: `.devin/bridge.token`, 2 cách trình, scope từng port
- Threat model ghi rõ: loopback token chống "process local gọi API đặc
  quyền" (confused deputy) + drive-by; GET :8080 mở vì local đọc file được
  anyway — **KHÔNG áp cho non-loopback**
- **Yêu cầu relay (khi có)**: mọi request vào bridge phải qua token;
  GET `/my-course/` khoá; `/.shots/` chặn (screenshot = dữ liệu nhạy cảm)
- Token trong URL `?t=` nằm history — chấp nhận loopback, relay dùng
  cơ chế riêng
- Rotation: `rm .devin/bridge.token` + restart = khoá mới, mọi phía cũ
  mất hiệu lực
- Prompt injection: trỏ mục "Dữ liệu không phải lệnh" trong AGENTS.md

## Test matrix — chạy trên thư mục tạm + port tạm

| # | Kiểm | Mong đợi |
|---|---|---|
| 1 | `curl :PORT/api/poll` không token | 401 |
| 2 | `?token=sai` | 401 |
| 3 | `?token=<đúng>` + `X-Bridge-Token` đúng | 200 |
| 4 | `OPTIONS` không token | 204, Allow-Headers có `X-Bridge-Token` |
| 5 | `GET /api/health` không token | 200 + `version` |
| 6 | WS `/ext` không token | 401/từ chối, không chiếm slot |
| 7 | WS `/ext?token=<đúng>` | handshake OK (client giả) |
| 8 | Não spawn → `env` có `BRIDGE_TOKEN` (best-effort) | có hoặc ghi nhận fallback |
| 9 | Portal `?t=` → fetch có header, 401 không còn | portal dùng được |
| 10 | Endpoint cũ (`save-page`, `brain`, `secrets`…) | không regression |

## Acceptance tổng

- Mọi test case xanh trên macOS (py); ps1 review tay + note cần verify Win
- `git status` sạch secrets: `bridge.token` trong `.gitignore`
- Docs khớp code

## Việc sau plan (để lại cho đợt tới)

- Port toàn bộ sang ima-assistant (sau khi verify ở ai-assistant)
- Relay: yêu cầu đã ghi sẵn trong SECURITY.md
- Installer/auto-update/`/api/report`
