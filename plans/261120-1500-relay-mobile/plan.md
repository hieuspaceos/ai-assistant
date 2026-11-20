---
title: "Relay VPS + mobile remote access (đợt 3)"
description: "Điện thoại dùng trợ lý qua relay tự host trên VPS — desktop giữ não/tay chân ở nhà, điện thoại là màn hình + bàn phím từ xa, không phụ thuộc bên thứ ba"
status: pending
priority: P2
effort: L
branch: main
tags: [relay, mobile, remote, security, infra]
created: 2026-11-20
depends-on: 261120-1420-bridge-auth (đợt 1+2)
---

# Relay VPS + mobile remote access

## Bối cảnh — thiết kế đã chốt từ phiên thảo luận

Điện thoại **không chạy được** não CLI/extension/filesystem → mô hình duy
nhất giữ nguyên sản phẩm: **điện thoại = màn hình + bàn phím ở xa**, desktop
ở nhà làm hết. Hai đầu đều sau NAT → cần "điểm hẹn" — user không muốn phụ
thuộc Tailscale/Cloudflare/Telegram → **tự host relay trên VPS của mình**.

```
[Điện thoại] ──HTTPS──> [VPS relay.py] <──WSS outbound── [Desktop connector]
   mở URL, gõ lệnh        điểm hẹn + bơm lệnh              giữ đường dây mở,
                                                           forward về localhost
```

Desktop chủ động nối RA → NAT nào cũng qua. Relay chỉ là bảng ghép đôi
`machine-id → đường dây`, không lưu dữ liệu, không biết nghĩ.

**Prerequisite (đợt 1+2 phải xong trước):** `bridge.token` auth đã có trên
mọi API; `troly` supervisor để connector chạy như một child; portal `?t=`
bootstrap đã có sẵn pattern.

## Quyết định thiết kế

1. **Relay viết tay Python stdlib** — tái dùng mẫu WS server đã prove trong
   `ext-bridge.py` (ws_handshake/ws_recv/ws_send). Một file `relay.py`,
   `scp` lên VPS là chạy — đúng triết lý zero-dep.
2. **Phone = chính portal hiện tại** — `BRIDGE_URL` đổi thành same-origin
   khi không chạy localhost; relay proxy `/api/*` → connector → `:7682`,
   còn lại → `:8080`. Portal không cần bản "mobile" riêng.
3. **Pairing mã ngắn một lần** — desktop xin mã từ relay, hiện trong ⚙;
   điện thoại nhập 6 số → relay cấp cookie session dài hạn. Không password,
   không tài khoản.
4. **TLS**: Caddy reverse proxy (auto-cert Let's Encrypt, 1 binary cài ở
   VPS) → relay.py chỉ nghe `127.0.0.1:4443`. Đơn giản hơn tự quản cert.
5. **Desktop offline → 503 rõ ràng** "trợ lý ở nhà đang nghỉ" — không
   queue lệnh v1 (queue = nghiệp vụ phức tạp, để sau).

## Phases

| # | Phase | Nội dung | Link |
|---|-------|----------|------|
| 1 | relay.py core | WS registry + pairing code + HTTP proxy routing | [phase-01](./phase-01-relay-core.md) |
| 2 | connector.py | child trong troly, forward path→port, reconnect | [phase-02](./phase-02-connector.md) |
| 3 | Portal remote | BRIDGE_URL same-origin, UI pairing, PWA manifest | [phase-03](./phase-03-portal-remote.md) |
| 4 | VPS ops | deploy: Caddy TLS, systemd, firewall, domain | [phase-04](./phase-04-vps-ops.md) |
| 5 | Security + test | auth matrix, offline, rate-limit, E2E test | [phase-05](./phase-05-security-test.md) |

## Rủi ro chính

- **R1**: pairing code brute-force → 6 số + TTL 5 phút + rate-limit per IP
- **R2**: relay là SPOF — chấp nhận (vps của mình, document restore)
- **R3**: WS frame code tái dùng từ ext-bridge — phải port cẩn thận, test
  kỹ fragmentation/mask (đã có code mẫu chạy thật)
- **R4**: `BRIDGE_URL` hardcode nhiều chỗ — phase 3 phải grep sạch
- **R5**: `.shots/` — relay TUYỆT ĐỐI không proxy đường đó (đã ghi trong
  SECURITY yêu cầu relay)

## Out of scope

- Multi-tenant nhiều user/VPS (v1: một user một máy một relay)
- Não/MCP trên VPS (hybrid — plan riêng nếu cần)
- E2E encryption qua relay (v1 tin VPS của mình; nâng cấp sau)
- Native app (PWA đủ)
- Queue lệnh khi desktop offline
