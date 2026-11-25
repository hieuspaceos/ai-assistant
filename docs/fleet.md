# Fleet — beacon + collector (quản trị nhiều máy)

Kiến trúc cho doanh nghiệp: mỗi máy nhân viên **chủ động đẩy** snapshot
định kỳ lên một collector trong công ty; IT/chủ xem dashboard tổng —
không port nào trên máy nhân viên mở ra mạng, threat model loopback của
các bridge giữ nguyên.

```
Máy NV ── tools/beacon.py ──POST 15'──▶ tools/collector.py :8790
   (.devin/fleet.json)                     (SQLite, dashboard /)
```

## Cài một máy vào fleet

Bộ cài cty đặt sẵn `.devin/fleet.json` + `.devin/license.json`:

```json
// .devin/fleet.json — do vendor cấp khi gói bộ cài
{"collector": "https://fleet.cty.vn",      // hoặc http://may-IT:8790
 "org": "IMA",
 "beacon_secret": "vé-vào-cửa chung cả org"}
```

`launcher.py`/`start.sh`/`start.bat` chỉ spawn beacon khi file này tồn
tại — máy cá nhân không có → không chạy, không log lỗi.

## Pairing — từ shared secret tới khoá riêng từng máy

`beacon_secret` chung cả org chỉ là **vé vào cửa**, không phải chìa
khoá:

1. Máy mới → `POST /api/pair` (machine.id + hostname + license, header
   `X-Beacon-Key: beacon_secret`) → hiện **pending** trên dashboard.
2. Admin bấm Duyệt → collector cấp `machine_key` riêng → máy ghi
   `.devin/machine.key` (0600).
3. Beacon sau đó dùng `machine_key` — **revoke từng máy** (nghỉ việc,
   mất máy) mà không ảnh hưởng fleet. Máy bị revoke → 403 `revoked` →
   xoá key local → re-pair hiện pending lần nữa (admin thấy, quyết).
4. `machine.id` (hex 32) sinh lần đầu, KHÔNG rotate — định danh đếm ghế.

Vì sao không dùng thẳng beacon_secret làm khoá beacon: một máy lộ
secret → kẻ trong LAN giả mạo được mọi máy. Với pairing, revoke một
máy chỉ mất máy đó.

## Hai lớp khoá — giữ riêng

| Khoá | Ai cầm | Mở được gì |
|---|---|---|
| `beacon_secret` → `machine_key` | máy NV | POST pair + beacon (ghi state chính mình) |
| `admin_key` | IT cty | GET dashboard + `/api/fleet*` + duyệt/revoke máy |
| `license_secret` | vendor + collector config | verify chữ ký license (không nằm trên máy NV) |
| vendor key (`telemetry.key`) | vendor | nhận `/api/org-ping`, đọc `/api/org-pings` |

`admin_key` map về org trong `collector.json` → IT cty A không đọc
được fleet cty B khi collector host nhiều org.

## Collector — `tools/collector.py`

```bash
python3 tools/collector.py --config collector.json \
    --port 8790 --bind 0.0.0.0 --data collector-data --web collector-web
```

```json
// collector.json — KHÔNG commit
{"orgs": {"IMA": {"beacon_secret": "…", "license_secret": "…",
                  "admin_key": "…"}},
 "telemetry": {"url": "https://troly.hieuspace.com/fleet/api/org-ping",
               "key": "vendor-key"}}
```

- Bind `0.0.0.0` là **chủ đích** — máy NV trong LAN phải push tới được
  (khác bridge loopback). Dashboard: `http://collector:8790/?key=<admin_key>`.
- SQLite `collector-data/fleet.db`, bảng `meta.schema_version` + migrate
  tuần tự (`MIGRATIONS` trong file — collector sống lâu ở máy khách).
- Release/pack hint: đặt `collector-data/releases.json`
  `{"version","url","sha256"}` và/hoặc `packs.json` `{"<org>":{…}}` →
  beacon được báo qua response `{update, pack}` → ghi
  `.devin/fleet-inbox.json` (update.py ở plan 2 kéo về — beacon không
  tự vá code).
- Rate limit 240 GET / 60 POST mỗi phút/IP + body cap 1MB + 64 thread
  slot — cùng pattern bridge.

### Ba tier triển khai — cùng code, khác chỗ đứng

| Tier | Collector ở đâu | HTTPS | Remote | Cho ai |
|---|---|---|---|---|
| LAN self-hosted | máy IT trong LAN | ✗ | ✗ | cty nhát public |
| Customer-hosted | VPS/domain khách `fleet.<cty>` | ✓ | ✓ | cty có hạ tầng (IMA: CapRover) |
| Vendor-hosted | `troly.hieuspace.com/fleet/` | ✓ | ✓ | cty nhỏ không IT |

**Vendor-hosted = `worker/` — port của collector.py sang Cloudflare
Workers + D1 + R2** (đã deploy): route `troly.hieuspace.com/fleet*`,
DB `troly-fleet-db`, bucket `troly-fleet-assets`, secrets `ORGS_JSON`/
`VENDOR_KEY` trong secret store. Cùng endpoint/scope/response với
collector.py — khác biệt: multi-tenant theo cột `org` (không phải
process-per-org), prefix `/fleet` suy từ request path (hint URL trả
`/fleet/...` để `urljoin` phía máy đúng), mirror/telemetry chạy bằng
Cron thay thread. Ops: `deploy/vendor-infra.md`. Mọi thay đổi protocol
endpoint phải patch CẢ `collector.py` lẫn `worker/src/index.js` —
parity giống `.py`/`.ps1`.

Customer-hosted là tier tốt nhất khi khách có domain: remote được +
metadata nằm trên hạ tầng CHÍNH khách.

### Meta-telemetry (vendor nhìn khách)

`telemetry` trong config → collector POST rollup **org-level** 1 lần/ngày
`{org, machines_active, version_dist, license_expiry, ts}` về vendor —
vendor thấy "IMA 18/20 v1.4" để support + nhắc gia hạn. KHÔNG gửi
machine-level. Tắt: `COLLECTOR_NO_TELEMETRY=1` hoặc bỏ mục telemetry.

## Snapshot gửi gì — và KHÔNG gửi gì

**Gửi**: machine.id, hostname, OS, version app + pack, license đầy đủ
(collector verify sig), trạng thái bridge/brain/config/bots/
permissions/connections, và **đếm event theo loại** (`done`, `err`,
`perm`, `perm:auto`, `tool`, `inj_suspect`…) kể từ cursor lần trước
(`.devin/beacon.cursor` — `poll?since=<cursor>` chỉ kéo event mới).

**KHÔNG gửi**: nội dung chat, tin nhắn, file, prompt, text sự kiện.
Dashboard thấy "dùng nhiều không, lỗi gì" — không thấy "nói gì".
Đây là cam kết privacy của sản phẩm với nhân viên — đừng "tiện tay"
thêm field text vào snapshot.

## License — "đếm và báo"

`tools/make-license.py` (chỉ chạy phía vendor):

```bash
TROLY_LICENSE_SECRET=<org-secret> python3 tools/make-license.py \
    --org IMA --seats 20 --expiry 2027-01-01 --out .devin/license.json
```

`sig = HMAC-SHA256(secret, "org|seats|expiry|issued")` — verify ở
collector. Gentle enforcement: license sai/hết hạn → flag trên
dashboard, **máy NV vẫn chạy** (khoá cứng = cả phòng nghỉ việc một sáng
thứ hai). `/api/license` đếm máy active 30 ngày vs `seats` →
`exceeded`; seats chỉ tin license sig hợp lệ (license bị sửa mà vẫn
đếm ghế thì kẻ gian tự nâng ghế).

## API tóm tắt

| Method + path | Khoá | Việc |
|---|---|---|
| `POST /api/pair` | beacon_secret | xin vào fleet → pending/approved+key/revoked |
| `POST /api/beacon` | machine_key | upsert snapshot + counts, trả `{update,pack}` |
| `POST /api/pair-approve` | admin_key | cấp machine_key |
| `POST /api/pair-revoke` | admin_key | thu hồi máy (giữ key để trả revoked rõ ràng) |
| `GET /api/pending` | admin_key | máy chờ duyệt |
| `GET /api/fleet` | admin_key | bảng máy + usage hôm nay + license_status |
| `GET /api/fleet/<id>` | admin_key | snapshot đầy đủ + usage 14 ngày |
| `GET /api/license` | admin_key | seats vs active30 + status |
| `POST /api/org-ping` | vendor key | nhận rollup org-level |
| `GET /api/org-pings` | vendor key | meta-dashboard vendor |
| `GET /` + static | — | dashboard (data vẫn đòi admin key) |
| `GET /api/releases/latest` | machine_key | manifest release mới nhất |
| `GET /releases/<file>` | machine_key | tải zip release đã ký |
| `GET /packs/<org>/<ver>.json` | machine_key | tải pack — CHỈ cùng org |
| `POST /api/releases/<file>` | admin_key | upload zip (bước 1) |
| `POST /api/releases` | admin_key | upload manifest (bước 2) |
| `GET /api/packs` | admin_key | pack latest đang phát per org |
| `POST /api/packs` | admin_key | đẩy pack mới (admin_key scope org) |

## File máy NV liên quan

`.devin/` — `fleet.json` (cấu hình), `machine.id`, `machine.key`,
`license.json`, `beacon.cursor`, `fleet-inbox.json`, `pack-version`.
Tất cả là machine state → đã gitignore, KHÔNG đi vào release.

## Test

`python3 tools/test-fleet.py` — static contract (snapshot keys parity
.py/.ps1, chuỗi ký license khớp hai phía, adm-render.js dùng chung,
launcher/start spawn đúng điều kiện) + integration dựng collector thật:
pair sai key 401 → pending → approve → beacon 200 → license ok/invalid
→ usage gộp → revoke → 403 revoked.
