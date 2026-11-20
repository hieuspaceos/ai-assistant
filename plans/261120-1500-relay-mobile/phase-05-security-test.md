# Phase 5 — Security review + test matrix cho relay

Đây là cánh cửa MỞ RA INTERNET đầu tiên của sản phẩm — không merge nếu
chưa qua checklist này. Test trên lab: relay chạy local cổng khác, hosts
file trỏ domain giả.

## 1. Threat model — ghi vào `docs/SECURITY.md` (cập nhật từ đợt 1)

| Mối đe | Đã chặn bằng |
|---|---|
| Ai đó nối WS giả desktop | `s` = HMAC(mid, relay.secret) — không có secret thì close |
| Đoán mã pair 6 số | TTL 5' + dùng 1 lần + rate-limit 5 lần/phút/IP |
| Phone session bị đánh cắp | Cookie HttpOnly+Secure; TTL 30 ngày; không có cách nào đọc cookie qua JS |
| Relay bị chiếm | Không lưu dữ liệu; token chỉ trong RAM; traffic MITM được (ghi rõ là giới hạn v1) |
| Bridge local bị gọi xấu | `X-Bridge-Token` đi xuyên suốt — auth đợt 1 vẫn đứng sau relay |
| Đọc file nhạy cảm qua proxy | Relay chặn `/.devin`, `/.git`, `/my-course/.shots` ở mép |
| Desktop offline | 503 rõ ràng — không queue, không retry âm thầm |

## 2. Test matrix bắt buộc

**Auth:**
- WS `/ws/desktop` không `s` / sai `s` → close ngay, không vào DESKS
- `POST /pair` sai mã → 401; đúng mã đã dùng lần 2 → 401 (one-time)
- Request API không cookie → 401/redirect; cookie hết hạn → về form
- 6 lần sai mã trong 1 phút → 429

**Đường đi:**
- `GET /` qua relay (desktop offline) → portal + form vẫn load (static từ VPS)
- `GET /api/health` offline → 503 "đang nghỉ"; online → 200 từ bridge thật
- `POST /api/prompt` → xuống bridge, session chat thật trả về qua relay
- `GET /my-course/trang.html` (clone) → load được; `/.devin/x` → 403
- Header `X-Bridge-Token` sai từ phone → bridge local 401 (relay không nuốt)

**Bền bỉ:**
- Kill connector giữa chừng → troly restart, WS mới thay thế WS cũ ở relay
- Rút mạng desktop 60s → reconnect, chat tiếp được
- Hai connector cùng mid → đường mới thắng, đường cũ close (test bằng
  connector giả)

**Mobile:**
- iPhone Safari + Android Chrome thật: pair → chat → nhận reply →
  A2HS → mở từ icon → session còn
- Desktop sleep/tắt → phone thấy "đang nghỉ" trong ≤30s

## 3. Prompt-injection — lớp relay không nới lỏng

Luật "dữ liệu ≠ lệnh" của đợt 1 áp nguyên: prompt từ phone vẫn là prompt
user (có cookie + token hợp lệ). Nhưng ghi thêm vào `docs/SECURITY.md`:
**kênh remote có thêm 1 bề mặt** — nếu cookie session bị leak, attacker có
thể gửi prompt thay user. Giảm thiểu đã có: hành động nguy hiểm (gửi tin,
xoá, chuyển tiền) luôn hỏi — và câu hỏi xác nhận đó **đi về cùng kênh đã
pair**, nên attacker vẫn phải tự xác nhận. Đợt sau (nếu cần): danh sách
hành động chỉ cho phép khi request đến từ localhost, không qua relay
(VD: đọc `.devin/secrets.local.json`).

## 4. Checklist trước khi mở cho user thật

- [ ] Đợt 1 auth xong hết (7 phases kia merge trước)
- [ ] `remote.json` không nằm trong git, chmod 600
- [ ] `relay.secret` chỉ tồn tại 2 nơi: VPS + remote.json
- [ ] Pairing flow e2e chạy trên điện thoại thật qua domain thật
- [ ] Runbook `remote-access-runbook.md` hoàn chỉnh
- [ ] Portal trên viewport mobile dùng được (không chỉ load được)

## Rủi ro còn lại (chấp nhận, ghi rõ)

- Không E2E: relay đọc được traffic đi qua (v1 tin VPS của mình — đúng
  quyết định đã chốt; E2E = đợt sau)
- Một user/relay — multi-tenant là plan khác (hybrid/hosted)
- Session RAM mất khi relay restart → user nhập mã lại (ux nhỏ, an toàn)
