# DEPLOY — cài Trợ Lý AI cho một công ty (N máy)

Đối tượng đọc: đội triển khai / IT của khách. Không cần biết code,
không cần đọc repo — chỉ cần theo checklist.

## 0. Kiến trúc một máy (hiểu 30 giây)

```
Portal (trình duyệt, :8080)
    │  chat
    ▼
chat-bridge (:7682) ──► não (devin acp / claude / …)
    │                        │ đọc web qua
    │                        ▼
    │                   ext-bridge (:7684) ◄── Extension trong Chrome
    ▼                        │      (đang đăng nhập sẵn Zalo/Outlook)
launcher.py giám sát tất cả + beacon (báo về collector mỗi 15')
```

Mọi thứ chạy trên máy nhân viên, chỉ localhost. Dữ liệu nội dung không
rời máy; chỉ số đếm (lượt dùng, version, lỗi) đi lên collector.

## 1. Trước khi đi cài — chuẩn bị "bộ cài cty"

Zip một folder gồm:

- **Bộ cài**: toàn bộ repo `ai-assistant/` (bỏ `.git`).
- **`deploy/company/license.json`** — do vendor cấp (make-license.py),
  ghi org + số ghế + hạn.
- **`deploy/company/fleet.json`** — `{"url": "<collector-url>",
  "beacon_secret": "<mã org>"}` — vendor hoặc IT cty cấp.
- Link extension trên Chrome Web Store (unlisted) hoặc policy
  force-install (xem `force-install.md`).

### Yêu cầu máy nhân viên

- Windows 10+ (PowerShell admin lúc cài — không cần admin lúc chạy)
  hoặc macOS 12+.
- Chrome / Edge / Brave.
- Não đã cài sẵn trên máy (`devin` CLI) hoặc cài cùng lúc.

## 2. Cài collector trước (một lần mỗi cty)

Chọn 1 trong 3 tier — cùng một `tools/collector.py`:

| Tier | Collector ở đâu | Khi nào |
|---|---|---|
| **a) Customer-hosted** | `fleet.<domain-cty>` — VPS/CapRover của khách, cert thật | Khách có domain + nhân viên remote. **Khuyến nghị.** |
| **b) LAN self-hosted** | `http://<máy-IT>:8790` | Chỉ làm việc trong văn phòng, nhát public tuyệt đối |
| **c) Vendor-hosted** | `troly.hieuspace.com/fleet/` | Khách không có IT/hạ tầng (kèm điều khoản DPA) |

Cài (tier a/b): `python3 tools/collector.py --port 8790 --data DATA/`
+ cấu hình `DATA/config.json` `{"org","beacon_secret","admin_key"}`.
Sau đó mở `http://<collector>/` (nhập admin_key) để xem dashboard.

## 3. Từng máy nhân viên (~5 phút/máy)

### Windows

```powershell
# giải nén bộ cài, vào folder, chạy PowerShell ADMIN:
powershell -ExecutionPolicy Bypass -File deploy\install.ps1
```

Script làm: copy → `C:\TroLyAI`, cài ttyd qua winget, hỏi tạo user
sandbox, đặt license.json + fleet.json vào `.devin\`, shortcut Desktop.

### macOS

```sh
sh deploy/install.sh          # → ~/TroLyAI, brew install ttyd
```

### Extension — hai đường

- **Fleet (khuyến nghị)**: force-install qua policy → tự cài + tự
  update, nhân viên không bấm gì. Xem `force-install.md`.
- **Máy lẻ**: cho nhân viên link Web Store (unlisted) → bấm Cài.

### Lần chạy đầu

1. Mở "Trợ Lý AI" (shortcut / `start.sh`) → portal mở.
2. Onboarding: chọn não, đặt tên trợ lý.
3. Portal tự đẩy mã kết nối cho extension (`set-token`) — extension
   chấm xanh là xong.

## 4. Nghiệm thu mỗi máy (tick vào CHECKLIST.md)

- [ ] Portal `localhost:8080` mở được
- [ ] Chat trả lời được câu thử
- [ ] `chrome://extensions` thấy "Trợ Lý AI" (chấm xanh trên toolbar)
- [ ] `curl localhost:7682/api/health` → version đúng
- [ ] Sau ~15 phút: máy hiện trên dashboard collector
- [ ] license đúng org, ghế chưa vượt (dashboard `/api/license`)

## 5. Vận hành sau cài

| Việc | Cơ chế |
|---|---|
| Update code | Release ký ed25519 → collector mirror → máy tự kéo qua beacon, stage + apply khi khởi động lại. Rollback: `troly --rollback` |
| Workflow/rules mới | Đẩy pack mới lên collector (`POST /api/packs`) → máy tự apply |
| Nhân viên nghỉ | Revoke máy trên dashboard → máy bị đá khỏi fleet |
| Sự cố một máy | `web/admin.html` tại máy — lỗi, version, trạng thái |
| Xem hiệu suất | Dashboard collector — ai online, lượt dùng, lỗi, inj_suspect |

## 6. Viết workflow cho cty

Mỗi quy trình = một file `my-course/workflows/<id>.json` + liệt kê id
trong `index.json` (schema: title/desc/icon/dept i18n, `prompt` với
`{{input}}`, `inputs`, `requires`, `checklist`, `verify`). Nhân viên
thấy card trong portal → bấm Chạy → điền form → trợ lý làm → tick
checklist. Đẩy cho cả fleet qua `workflows/` trong config-pack
(plan 2) — máy tự áp trong 15'. `tools/test-packs.py` validate schema
mỗi release — viết xong chạy nó trước khi đẩy pack.

## 6.5. Gỡ / rollback

Xoá shortcut + folder `C:\TroLyAI` (hoặc `~/TroLyAI`). **Dữ liệu của
nhân viên nằm trong `my-course/`** — copy ra trước khi xoá nếu cần giữ.
Extension: gỡ trong `chrome://extensions` hoặc xoá policy.

## 7. Lỗi hay gặp (chi tiết: docs/troubleshooting-runbook.md)

- Policy chặn extension → force-install chưa áp đúng OU/registry.
- Proxy cty → beacon không tới collector; whitelist domain collector.
- `winget` thiếu → cài ttyd tay từ GitHub releases.
- Execution policy → chạy script với `-ExecutionPolicy Bypass`.
