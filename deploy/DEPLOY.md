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
- **`deploy/company/fleet.json`** — `{"collector": "<collector-url>",
  "org": "<ORG>", "beacon_secret": "<mã org>"}` — vendor hoặc IT cty
  cấp (hosted tier: dashboard trả sẵn file này khi tạo org).
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

> ⚠ **Tier b đi HTTP trần** — `beacon_secret`, `machine_key`, `admin_key`
> đều cleartext trên dây LAN. Chỉ dùng trên LAN tin cậy vật lý (switch/
> wifi của cty — không guest-wifi, không VLAN lẫn máy lạ). Org nhạy cảm
> hoặc có nhân viên remote → tier a (HTTPS cert thật). Khi collector đứng
> sau nginx/proxy, bật `"trust_proxy": true` trong config để rate limit
> theo IP thật (X-Forwarded-For) — đừng bật nếu client kết nối trực tiếp.
Tier c không cần cài gì — vendor tạo org trên dashboard
`troly.hieuspace.com/fleet/` và bàn giao `fleet.json` + tài khoản
cty-admin (login bằng account, admin_key cũ vẫn nhận qua "Dán key").

## 3. Từng máy nhân viên (~5 phút/máy)

### Windows

```powershell
# giải nén bộ cài, vào folder, chạy PowerShell ADMIN:
powershell -ExecutionPolicy Bypass -File deploy\install.ps1
```

Script làm: copy → `C:\TroLyAI`, cài ttyd qua winget, hỏi tạo user
sandbox, đặt license.json + fleet.json vào `.devin\`, shortcut Desktop.
Script cũng `icacls` grant Modify cho `BUILTIN\Users` trên thư mục cài
(ACL mặc định của `C:\` chỉ cho user thường quyền đọc — không grant thì
app chạy non-elevated không ghi được `.devin\`, `.logs\`, `workspace\`);
`setup-agent-user.ps1` chạy ngay sau đó seal lại quyền của user sandbox
`troly-agent`. Máy đa-user có thể truyền `-ForUser` để chỉ định đúng chủ
nhân. Re-install giữ nguyên file state trong `workspace\` (config,
manifest, bots, permissions, connections, bot.md) — seed lessons vẫn
được cập nhật.

### macOS

```sh
sh deploy/install.sh          # → ~/TroLyAI, brew install ttyd
```

### Cài không ngồi máy (GPO / Intune / MDM)

Hai installer đều có chế độ im lặng — không hỏi gì:

```powershell
# Windows — GPO startup script hoặc Intune win32 app (chạy dưới SYSTEM):
powershell -ExecutionPolicy Bypass -File deploy\install.ps1 -Quiet -ForUser ngoc.nguyen
# -Quiet: không Read-Host; -ForUser: shortcut + ACL đặt cho đúng chủ máy
#        (không -ForUser thì shortcut rơi vào Public Desktop)
# -NoSandbox: bỏ tạo troly-agent — KHÔNG khuyến nghị, chỉ khi AD cấm
#        tạo local user
```

```sh
# macOS — MDM (Jamf/Kandji) script:
sh deploy/install.sh --quiet          # tự tạo LaunchAgent
sh deploy/install.sh --quiet --no-autostart   # không tự mở khi login
```

Lưu ý Intune win32 app: đóng gói `.intunewin` từ bộ cài cty,
`install command` = dòng PowerShell trên, `install behavior` = System,
rules = file `C:\TroLyAI\start.bat` tồn tại. Extension phải áp
force-install policy TRƯỚC hoặc ngay sau — xem `force-install.md`.

### Extension — hai đường

- **Fleet (khuyến nghị)**: force-install qua policy → tự cài + tự
  update, nhân viên không bấm gì. Xem `force-install.md`.
- **Máy lẻ**: cho nhân viên link Web Store (unlisted) → bấm Cài.

### Não AI cho máy nhân viên — hai đường

- **IT cài sẵn (khuyến nghị cho fleet)**: `deploy/install-brain.ps1`
  (PowerShell admin) cài Node + `gemini-cli` machine-wide qua winget —
  chạy cùng đợt `install.ps1`, kể cả trong GPO/Intune. Hoặc đẩy pack
  có field `brain` → máy **chưa onboard** tự ghi `brain.json` chọn sẵn
  não (không đè lựa chọn của máy đã chạy).
- **Nhân viên tự cài**: nút "Cài não này" trong onboarding tự cài
  (không cần admin — node portable trong `~/TroLyAI/node`).

Dù đường nào, nhân viên vẫn **đăng nhập não lần đầu** bằng tài khoản
riêng (Google cá nhân cho Gemini) — không có credential cty nào để IT
quản.

### Lần chạy đầu

1. Mở "Trợ Lý AI" (shortcut / `start.sh`) → portal mở.
2. Onboarding: chọn não (đã cài sẵn thì tick ngay), đặt tên trợ lý.
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
| Nhân viên nghỉ | Revoke máy trên dashboard → máy bị đá khỏi fleet (chi tiết mục 5.1) |
| Gán tên NV vào máy | Mở drawer máy trên dashboard → ô "gán tên nhân viên" → Lưu. Xuất báo cáo ghế: nút "Xuất CSV" |
| Sự cố một máy | `web/admin.html` tại máy — lỗi, version, trạng thái |
| Xem hiệu suất | Dashboard collector — ai online, lượt dùng, lỗi, inj_suspect |

### 5.1. Nhân viên nghỉ việc — thu hồi seat đầy đủ

1. **Gom công thức trước** (drawer máy → "Gom công thức") — máy
   upload `.devin/skills` về kho công thức của org ở lần beacon kế;
   máy mới của người thay việc sẽ tự kéo kho về. Nếu máy đã offline
   hẳn thì bỏ qua bước này.
2. **Revoke máy** trên dashboard (drawer máy → "Thu hồi máy này") —
   máy bị đá khỏi fleet ngay, beacon sau đó trả `revoked`, máy tự xoá
   `machine.key` và về pending. Ghế `active30` giảm sau 30 ngày.
3. **Dữ liệu trên máy**: `workspace/` chứa toàn bộ bài làm của NV —
   copy ra nếu cty cần giữ, rồi xoá folder `C:\TroLyAI` / `~/TroLyAI`
   (hoặc re-image máy theo quy trình IT).
4. **Extension**: gỡ thủ công trong `chrome://extensions`, hoặc nếu
   cài qua force-install policy thì máy trả về domain chung sẽ tự gỡ
   khi policy không còn áp cho user/máy đó.
5. **Tài khoản não**: NV đăng nhập Gemini/Devin bằng tài khoản riêng
   — không có creds cty nào nằm trên máy để thu hồi. Nếu từng cấp key
   chung (Phase 05-B), rotate key đó ở phía provider.

## 6. Viết workflow cho cty

Mỗi quy trình = một file `workspace/workflows/<id>.json` + liệt kê id
trong `index.json` (schema: title/desc/icon/dept i18n, `prompt` với
`{{input}}`, `inputs`, `requires`, `checklist`, `verify`). Nhân viên
thấy card trong portal → bấm Chạy → điền form → trợ lý làm → tick
checklist. Đẩy cho cả fleet qua `workflows/` trong config-pack
(plan 2) — máy tự áp trong 15'. `tests/test-packs.py` validate schema
mỗi release — viết xong chạy nó trước khi đẩy pack.

## 6.5. Gỡ / rollback

Xoá shortcut + folder `C:\TroLyAI` (hoặc `~/TroLyAI`). **Dữ liệu của
nhân viên nằm trong `workspace/`** — copy ra trước khi xoá nếu cần giữ.
Extension: gỡ trong `chrome://extensions` hoặc xoá policy.

## 7. Lỗi hay gặp (chi tiết: docs/troubleshooting-runbook.md)

- Policy chặn extension → force-install chưa áp đúng OU/registry.
- Proxy cty → beacon không tới collector; whitelist domain collector.
- `winget` thiếu → cài ttyd tay từ GitHub releases.
- Execution policy → chạy script với `-ExecutionPolicy Bypass`.
