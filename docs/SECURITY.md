# ai-assistant — Security

Mô hình đe doạ đặc thù: **người dùng không đọc được code/lệnh** → agent
là lớp bảo vệ cuối. Mọi server là loopback; mọi quyền vượt `my-course/`
đều đi qua `permissions.json`.

## Trust boundaries

| Ranh giới | Cơ chế |
|---|---|
| LAN → máy học viên | Mọi server bind `127.0.0.1` — portal, chat-bridge, ext-bridge, ttyd |
| HTTP → secrets | `serve.py` chặn dotfiles — `.devin/` chứa secrets không lộ qua :8080 |
| Agent/viewer → file hệ thống | `/api/save-page` chỉ ghi `.html` dưới `my-course/`, chặn `..`; `.bak` trước khi ghi đè |
| Agent → folder ngoài | `permissions.json` — chưa có trong list thì phải hỏi học viên |
| Agent → app bên ngoài | `connections.json` — chưa kết nối thì dẫn học viên kết nối trước |

## permissions.json — ngăn tủ được phép

```json
{"folders": [{"path": "~/Downloads/anh-thang-11",
              "access": "read" | "read-write", "note": "..."}]}
```

- Luôn được phép (không cần liệt kê): `my-course/`, `ai-assistant/` và
  folder con.
- Folder khác → đọc `permissions.json`; chưa có → **hỏi học viên**,
  được đồng ý mới `POST /api/permissions` (mặc định xin `read`; chỉ xin
  `read-write` khi thật sự cần ghi và báo trước việc ghi cụ thể).

## Secrets — không bao giờ vào conversation

- `connections.json` đánh dấu ô bí mật bằng `"secret": true` → portal
  render ô nhập dạng password; giá trị ghi qua `/api/secrets`.
- Agent **không bao giờ** yêu cầu học viên dán mật khẩu/API key vào chat.
  Nếu họ định dán → chặn và giải thích.
- Không log, không echo, không commit giá trị secret — chỉ commit
  định nghĩa field (`"secret": true` là cờ, không phải giá trị).
- Extension đọc web bằng **phiên đăng nhập sẵn của học viên** — không
  cần, không lưu mật khẩu Zalo/Outlook. Đây là lựa chọn kiến trúc có
  chủ đích.

## Clone — bản quyền và hành vi giả lập

- Không mang chữ/ảnh/logo/title/favicon của site nguồn sang bản giao
  (chi tiết `clone-pipeline.md`).
- Form/giỏ hàng/đăng nhập trong clone là giả lập — phải báo học viên,
  không để họ tưởng form gửi thật.
- `.bak` chỉ giữ một bản trước — là lớp "undo một bước", không phải
  backup; mốc quan trọng thì copy tay.

## Extension — mặt tấn công cần biết

- WS `ws://localhost:7684/ws/ext` không auth — bất kỳ process local nào
  cũng điều khiển được browser nếu gọi được bridge. Chấp nhận vì
  loopback + trust model "máy cá nhân"; đừng đổi sang `0.0.0.0`.
- Nhóm action `t*` dùng CDP → banner "đang gỡ lỗi" xuất hiện trong
  browser — `tdetach` để gỡ; không để debugger attach lâu hơn cần.

## Quy tắc cho agent (từ AGENTS.md — lớp bảo vệ cuối)

1. Trước khi lệnh đụng file (sửa/xoá/đổi tên/di chuyển): nói bằng lời
   thường, mặc định làm trên bản copy.
2. Không xoá dữ liệu khi chưa hỏi.
3. Không yêu cầu paste mật khẩu/API key/tài khoản ngân hàng.
4. Cài phần mềm → giải thích nó là gì, tại sao cần, tải từ đâu.
5. File cho học viên chỉ trong `my-course/` hoặc folder được cấp quyền.
