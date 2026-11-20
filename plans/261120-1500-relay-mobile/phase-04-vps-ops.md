# Phase 4 — Deploy relay lên VPS (ops)

Mục tiêu: một VPS $4-6 (1 CPU/1GB đủ — relay chỉ bơm byte) chạy relay
vĩnh viễn, TLS tự gia hạn, tự bật lại khi crash/reboot.

## 1. Chuẩn bị VPS

- Ubuntu 22.04/24.04 bất kỳ (Hetzner/DigitalOcean/Vultr — hoặc VPS VN nếu
  muốn latency thấp cho user VN; latency ~30-50ms chấp nhận được vì
  workload là text).
- Domain: một subdomain `relay.<domain>.com` (hoặc domain rẻ riêng
  `troly-connect.vn`) trỏ A record → IP VPS. **Bắt buộc có domain** —
  Let's Encrypt không cấp cho IP trần, và cookie `Secure` cần HTTPS.
- Firewall: `ufw allow 22, 80, 443` — chỉ 3 port mở ra ngoài.

## 2. TLS — Caddy (khuyến nghị)

```bash
apt install caddy
# /etc/caddy/Caddyfile:
relay.example.com {
    reverse_proxy 127.0.0.1:4443
}
systemctl reload caddy
```

Caddy tự xin + gia hạn cert Let's Encrypt, tự xử lý WS upgrade. Không
cần certbot, không cần nginx config dài.

**Phương án B** (không muốn cài Caddy): relay.py tự wrap
`ssl.SSLContext` + certbot `--standalone` với hook renew → copy cert.
Phức tạp hơn đáng kể — chỉ dùng nếu VPS đã có web server khác chiếm 443.

## 3. Deploy relay.py

```bash
useradd -r -d /opt/troly-relay troly          # system user, không shell login
mkdir -p /opt/troly-relay && chown troly:troly /opt/troly-relay
scp deploy/relay.py root@vps:/opt/troly-relay/   # scp bằng root/SSH key của
scp -r web/ root@vps:/opt/troly-relay/           # mình — user 'troly' mới tạo
ssh root@vps 'chown -R troly:troly /opt/troly-relay && \
    sudo -u troly python3 -c "import secrets;print(secrets.token_hex(32))" \
    > /opt/troly-relay/relay.secret && chmod 600 /opt/troly-relay/relay.secret'
```

(Lệnh gốc `scp ... troly@vps` chết ngay: user `troly` vừa tạo không có
SSH key/password — scp bằng tài khoản đăng nhập được rồi `chown`.)

**`web/` là bản copy tĩnh — phải sync theo release**: mỗi lần desktop
lên VERSION mới mà portal đổi, re-scp `web/` lên VPS, kẻo phone thấy
bản cũ (lệch với `/api/health` trả về). Ghi bước này vào runbook +
nhắc trong quy trình release của ship-learner phase 1.

`relay.secret` = chìa khoá chung desktop↔relay → copy giá trị này vào
`.devin/remote.json` `secret` phía desktop (phase 2).

## 4. systemd — tự sống

`/etc/systemd/system/troly-relay.service`:

```ini
[Unit]
Description=TroLy relay
After=network.target

[Service]
User=troly
WorkingDirectory=/opt/troly-relay
ExecStart=/usr/bin/python3 relay.py --port 4443 --secret-file relay.secret
Restart=always
RestartSec=3
StandardOutput=append:/opt/troly-relay/relay.log

[Install]
WantedBy=multi-user.target
```

`systemctl enable --now troly-relay` → done. Log rotate: logrotate config
đơn giản (hoặc `append` + journald — chọn một, ghi runbook).

## 5. Kiểm tra sau deploy

```bash
curl https://relay.example.com/health        # {"ok":true,"desktops_online":0}
curl https://relay.example.com/api/health    # 503 "đang nghỉ" (chưa có desktop)
curl https://relay.example.com/              # portal HTML + pair form nếu chưa login
```

Mở trên điện thoại 4G (không wifi) → thấy form nhập mã = relay sống.

## 6. Tài liệu hoá

- `docs/remote-access-runbook.md` mới: sơ đồ, lệnh deploy, rotate secret,
  restore VPS mới (5 bước), các ca sự cố (desktop offline, mã không nhận,
  cookie mất, VPS đổi IP).
- `docs/decision-log.md`: ghi quyết định "self-host relay thay vì
  Cloudflare Tunnel/Tailscale" — lý do: không phụ thuộc bên thứ ba, chi
  phí ~$5/tháng, relay không lưu dữ liệu nên rủi ro VPS bị xâm nhập
  giới hạn ở traffic đang chạy (và token chỉ trong RAM).

## Acceptance criteria

- Reboot VPS → relay + TLS tự lên lại, phone pair session còn dùng được
  (session trong RAM mất → user nhập lại mã — chấp nhận, ghi runbook).
- `ss -tlnp` trên VPS: chỉ 22/80/443 + 4443 trên 127.0.0.1.
- Fail2ban hoặc ufw rate-limit SSH (không bắt buộc nhưng ghi runbook).

## Rủi ro

- VPS bị chiếm → attacker MITM được traffic (không E2E v1) — giảm thiểu:
  relay không lưu gì, secret chỉ cho auth chứ không giải mã; nâng cấp E2E
  ở đợt sau nếu cần.
- Domain hết hạn/quên gia hạn → mất hết remote. Ghi runbook auto-renew
  domain.
