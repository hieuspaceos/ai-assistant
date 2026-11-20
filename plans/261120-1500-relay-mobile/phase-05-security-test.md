# Phase 5 — Security review + test matrix cho relay

Đây là cánh cửa MỞ RA INTERNET đầu tiên của sản phẩm — không merge nếu
chưa qua checklist này. Test trên lab: relay chạy local cổng khác, hosts
file trỏ domain giả.

## 1. Threat model — ghi vào `docs/SECURITY.md` (cập nhật từ đợt 1)

| Mối đe | Đã chặn bằng |
|---|---|
| Ai đó nối WS giả desktop | `X-Relay-Auth` = `mid:ts:HMAC(mid:ts, relay.secret)` — không có secret thì close; ts hết hạn 5' chặn replay |
| Đoán mã pair 6 số | TTL 5' + dùng 1 lần + rate-limit 5 lần/phút/IP |
| Phone session bị đánh cắp | Cookie HttpOnly+Secure; TTL 30 ngày; không có cách nào đọc cookie qua JS |
| Relay bị chiếm | Không lưu dữ liệu; token chỉ trong RAM; traffic MITM được (ghi rõ là giới hạn v1) |
| Bridge local bị gọi xấu | `X-Bridge-Token` đi xuyên suốt — auth đợt 1 vẫn đứng sau relay |
| Đọc file nhạy cảm qua proxy | Relay chặn `/.devin`, `/.git`, `/my-course/.shots` ở mép |
| Desktop offline | 503 rõ ràng — không queue, không retry âm thầm |

## 2. Test matrix bắt buộc

**Auth:**
- WS `/ws/desktop` không `X-Relay-Auth` / sai hmac / ts quá 5 phút → close
  ngay, không vào DESKS
- `POST /pair` sai mã → 401; đúng mã đã dùng lần 2 → 401 (one-time)
- Request API không cookie → 401/redirect; cookie hết hạn → về form
- 6 lần sai mã trong 1 phút **cùng một XFF** → 429; XFF khác nhau vẫn vào
  được (verify rate-limit đọc X-Forwarded-For chứ không phải
  client_address — sau Caddy mọi request đều từ 127.0.0.1)
- Access log Caddy/relay không chứa `s=`/hmac (auth nằm ở header)

**Đường đi:**
- `GET /` qua relay (desktop offline) → portal + form vẫn load (static từ VPS)
- `GET /api/health` offline → 503 "đang nghỉ"; online → 200 từ bridge thật
- `POST /api/prompt` → xuống bridge, session chat thật trả về qua relay
- `GET /my-course/trang.html` (clone) → load được; `/.devin/x` → 403
- `GET /ext-api/browser/status` → connector rewrite thành
  `/api/browser/status` trên :7684 → 200 (KHÔNG phải `/browser/status`)
- Header `X-Bridge-Token` sai từ phone → bridge local 401 (relay không nuốt)
- Request same-origin từ phone CÓ kèm `X-Bridge-Token` (verify luật mới
  trong `bridge-token.js`: same-origin được gắn token — chỗ dễ sót nhất
  vì code cũ cố tình chỉ gắn cho loopback)
- `GET /web` (không slash) → redirect Location KHÔNG chứa `127.0.0.1:8080`
  (connector rewrite Location nội bộ thành path tương đối)
- Pair xong → relay redirect `/?t=<token>` → portal phone lưu được token
  (verify message `hello` connector→relay đã mang bridge_token)

**Bền bỉ:**
- Kill connector giữa chừng → troly restart, WS mới thay thế WS cũ ở relay
- `remote.json` `enabled:false` → connector KHÔNG thoát (idle loop),
  supervisor không đếm crash; bật lại `true` → tự nối WS mà không cần
  restart troly
- Port 7685 bị chiếm sẵn → connector vẫn chạy phần WS, log lỗi rõ,
  `/api/remote/pair-code` trả lỗi có nghĩa chứ không treo
- Rút mạng desktop 60s → reconnect, chat tiếp được
- Hai connector cùng mid → đường mới thắng, đường cũ close (test bằng
  connector giả)

**Mobile:**
- iPhone Safari + Android Chrome thật: pair → chat → nhận reply →
  A2HS → mở từ icon → session còn
- Desktop sleep/tắt → phone thấy "đang nghỉ" trong ≤30s
- Remote (hostname không phải localhost): nút/iframe **Terminal không
  xuất hiện** (ttyd không qua relay); chỉ Chat mode hoạt động

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

- [ ] Đợt bridge-auth merge xong hết (9 phases — `261120-1420`)
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
