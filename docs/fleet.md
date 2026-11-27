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
2. Admin bấm Duyệt → collector ghi `pending_key`; máy nhận
   `machine_key` ở lần pair sau → ghi `.devin/machine.key` (0600).
3. Beacon sau đó dùng `machine_key` — **revoke từng máy** (nghỉ việc,
   mất máy) mà không ảnh hưởng fleet. Máy bị revoke → 403 `revoked`
   và cứ thế báo revoked mỗi lần pair (KHÔNG tự về pending — máy
   revoked cũng ẩn khỏi list Pending vì list lọc `revoked=0`).
   Un-revoke = admin `POST /api/pair-approve` qua API → máy nhận key
   mới ở pair kế.
4. `machine.id` (hex 32) sinh lần đầu, KHÔNG rotate — định danh đếm ghế.
   Collector validate charset `[A-Za-z0-9][A-Za-z0-9._-]*` ≤200 ký tự
   ngay ở pair — mid đi vào path `skills/<org>/<mid>.json`, không cho
   slash nên `..` cũng vô hại.
5. **Re-pair máy đã duyệt** (mất `machine.key`): KHÔNG trả lại key chỉ
   vì biết `beacon_secret` — máy về pending với cờ `repair`, admin
   duyệt → cấp key MỚI (key cũ chết sau rotate — tự động rotate khi
   cấp lại). `beacon_secret` một mình không đủ lấy key máy đã duyệt.

Vì sao không dùng thẳng beacon_secret làm khoá beacon: một máy lộ
secret → kẻ trong LAN giả mạo được mọi máy. Với pairing, revoke một
máy chỉ mất máy đó.

## Mô hình khoá — tách theo vai trò

| Khoá | Ai cầm | Mở được gì |
|---|---|---|
| `beacon_secret` → `machine_key` | máy NV | POST pair + beacon (ghi state chính mình) |
| `admin_key` | IT cty | GET dashboard + `/api/fleet*` + duyệt/revoke máy + đẩy pack org mình |
| **session token** (Bearer 7 ngày) | admin đã login | giống `admin_key`, kèm role + org scope (hosted tier) |
| `license_secret` | vendor + collector config | verify chữ ký license (không nằm trên máy NV) |
| `telemetry.key` | máy khách → vendor | CHỈ ghi `POST /api/org-ping` — không quyền admin inbound |
| `vendor_read_key` | vendor | đọc rollup org-level (`/api/org-pings`, `/api/license`, `/api/packs`) — chỉ đặt trên collector vendor |
| `release_key` | vendor/maintainer | `POST /api/releases*` — không set = upload tắt (chỉ mirror/copy tay) |

`admin_key` map về org trong `collector.json` → IT cty A không đọc
được fleet cty B khi collector host nhiều org.

### Tài khoản admin (collector Workers — hosted tier)

Tier hosted (`worker/` trên Cloudflare) nâng `admin_key`/`vendor_key`
thành **tài khoản thật** trong D1: bảng `admins` (user/pass hash
PBKDF2, role `master`|`admin`, org), `sessions` (Bearer 7 ngày),
`orgs` (ghi đè ORGS_JSON), `audit` (ai-duyệt-gì).

- **master** (vendor): tab Công ty trên dashboard tạo org → nhận về
  `fleet.json` + `admin_key` + tài khoản cty-admin đầu tiên để bàn
  giao; cấp license (`orgs/<org>/license` ký đúng format
  make-license.py); tab Tài khoản quản mọi admin; tab Nhật ký xem audit.
- **cty-admin**: chỉ thấy máy/audit org mình; tab Pack đẩy pack cho
  org mình; duyệt/revoke máy.
- `POST /api/bootstrap` (cần vendor_key, chạy được đúng 1 lần) tạo
  master đầu tiên — sau đó endpoint tự khoá.
- X-Admin-Key / link `?key=` vẫn hoạt động — collector.py self-host
  không có bảng accounts nên dashboard giữ cửa "Dán key". `POST
  /api/releases*` giờ chỉ master.
- Đổi pass / disable / reset pass đều **xoá hết session** của account
  đó → thay đổi có hiệu lực ngay. Khoá **master cuối cùng** bị chặn
  (400) — không thể tự lockout.
- `POST /api/orgs/<org>/rotate-secret` (master): sinh `beacon_secret` +
  `admin_key` mới — key cũ chết ngay, session tài khoản vẫn sống. Opt-in
  `kill_machines: true` đá toàn bộ máy về pending buộc re-pair (dùng
  khi secret lộ). Org còn trong ORGS_JSON (env-only) được migrate sang
  D1 luôn. Nút "Xoay khoá" trên tab Công ty.

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
               "key": "vendor-key"},
 "release_key": "…"}        // tuỳ chọn: bật POST /api/releases*;
                            // vendor_read_key CHỈ đặt ở collector vendor
```

- Bind `0.0.0.0` là **chủ đích** — máy NV trong LAN phải push tới được
  (khác bridge loopback). Dashboard: `http://collector:8790/` → ô
  "Dán key" nhập `admin_key` (không dán key vào URL — rơi vào
  history/proxy log).
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

**Gửi**: machine.id, hostname, OS, version app + pack + bank
(`pack-version`, `bank-version` trong `.devin/`), license đầy đủ
(collector verify sig), trạng thái bridge/brain/config/bots/
permissions/connections, **danh mục skill** trong `.devin/skills/`
(metadata `id` + `name` + `desc` từ front-matter — KHÔNG phải nội
dung), và **đếm event theo loại** (`done`, `err`, `perm`,
`perm:auto`, `tool`, `inj_suspect`…) kể từ cursor lần trước
(`.devin/beacon.cursor` — `poll?since=<cursor>` chỉ kéo event mới).

**KHÔNG gửi**: nội dung chat, tin nhắn, file, prompt, text sự kiện,
**nội dung skill** (skill chỉ đi lên khi admin xin — xem mục Kho công
thức). Dashboard thấy "dùng nhiều không, lỗi gì" — không thấy "nói
gì". Đây là cam kết privacy của sản phẩm với nhân viên — đừng "tiện
tay" thêm field text vào snapshot.

## Kho công thức (skill bank) — bàn giao khi nhân viên nghỉ

Vấn đề: skill nhân viên tự sinh nằm chết trong `.devin/skills/` của
máy đó — revoke máy là mất luôn. Skill bank giữ công thức ở lại org:

1. Beacon luôn báo **danh mục** skill (metadata) trong snapshot →
   dashboard hiện cột "Công thức" + list trong drawer máy.
2. Admin bấm **"Gom công thức"** trong drawer → `POST /api/harvest`
   → cờ `harvest=1` → beacon resp `{harvest:true}` → máy mới upload
   **nội dung** `.devin/skills/` qua `POST /api/skills` (endpoint này
   403 nếu cờ chưa bật — giữ cam kết privacy; `off:true` huỷ xin).
3. Collector lưu `DATA/skills/<org>/<machine_id>.json` (worker: R2
   `skills/<org>/<machine_id>.json` + index `skill_bank` trong D1).
   Dashboard tab Pack → card "Kho công thức" hiện từng entry: ai
   (label/learner/hostname), bao nhiêu công thức, gom lúc nào.
4. Máy nào có `bank-version` cũ hơn kho → beacon resp `{bank:
   {version, url}}` → `apply-pack.py` kéo `GET /packs/<org>/bank.json`
   (merge mọi entry, ts mới thắng id trùng) → cài theo luật sở hữu:
   skill chưa có → tạo + đánh dấu **bank-owned**
   (`.devin/bank-skills.json`); bank-owned → ghi đè; dir của pack/user
   → bỏ qua (bank không đè pack, pack là sự thật cấp org; khi pack
   áp một id đang bank-owned thì pack chiếm sở hữu lại).
   → Máy mới của người thay việc beacon lần đầu là nhận đủ công thức.

Giới hạn upload (lint cả hai phía): ≤60 skill, ≤20 file/skill, file
text ≤200KB, path tương đối sạch (chặn absolute/`..`/backslash/
drive/`.`/rỗng). Beacon tự skip filename xấu ngay tại nguồn — một
tên lạ không làm reject cả batch (cờ `harvest` khỏi kẹt).

## License — "đếm và báo"

`scripts/make-license.py` (chỉ chạy phía vendor):

```bash
TROLY_LICENSE_SECRET=<org-secret> python3 scripts/make-license.py \
    --org IMA --seats 20 --expiry 2027-01-01 --out .devin/license.json
```

`sig = HMAC-SHA256(secret, "org|seats|expiry|issued")` — verify ở
collector. Gentle enforcement: license sai/hết hạn → flag trên
dashboard, **máy NV vẫn chạy** (khoá cứng = cả phòng nghỉ việc một sáng
thứ hai). `/api/license` đếm máy active 30 ngày vs `seats` →
`exceeded`; seats chỉ tin license sig hợp lệ (license bị sửa mà vẫn
đếm ghế thì kẻ gian tự nâng ghế).

## API tóm tắt

Endpoint chung cả hai bản (`collector.py` ↔ `worker/` — parity check
trong `test-fleet.py` khoá set này):

| Method + path | Khoá | Việc |
|---|---|---|
| `POST /api/pair` | beacon_secret | xin vào fleet → pending/approved+key/revoked |
| `POST /api/beacon` | machine_key | upsert snapshot + counts, trả `{update,pack,harvest,bank}` |
| `POST /api/pair-approve` | admin_key | ghi `pending_key` — máy nhận `machine_key` ở lần pair sau (cấp mới lẫn cấp lại một đường) |
| `POST /api/pair-revoke` | admin_key | thu hồi máy (giữ key để trả revoked rõ ràng) |
| `GET /api/pending` | admin_key | máy chờ duyệt + máy `repair=1` chờ cấp lại key |
| `GET /api/fleet` | admin_key | bảng máy + usage hôm nay + license_status + `conns` (app connections, chip tổng hợp) |
| `GET /api/fleet/<id>` | admin_key | snapshot đầy đủ + usage 14 ngày + `label` |
| `POST /api/machine/<id>/label` | admin_key | gán tên nhân viên vào máy (≤80 chữ; vendor_read_key → 403, máy org khác → 404; worker ghi audit `machine-label`) |
| `GET /api/seats/export` | admin_key | CSV báo cáo ghế (UTF-8 BOM — Excel mở đúng dấu): org, machine_id, hostname, label, learner, version, pack_version, last_seen, license_status |
| `GET /api/license` | admin_key | seats vs active30 + status |
| `POST /api/org-ping` | telemetry.key | nhận rollup org-level |
| `GET /api/org-pings` | vendor_read_key | meta-dashboard vendor |
| `GET /` + static | — | dashboard (data vẫn đòi admin key/session) |
| `GET /api/releases/latest` | machine_key | manifest release mới nhất |
| `GET /releases/<file>` | machine_key | tải zip release đã ký |
| `GET /packs/<org>/<ver>.json` | machine_key | tải pack — CHỈ cùng org |
| `GET /packs/<org>/bank.json` | machine_key | kho công thức merged của org — CHỈ cùng org |
| `POST /api/skills` | machine_key | upload nội dung `.devin/skills` — CHỈ khi `harvest=1` (admin đã xin) |
| `POST /api/harvest` | admin_key | bật/tắt cờ xin gom công thức (`off:true` huỷ; worker ghi audit) |
| `GET /api/skills-bank` | admin_key | list entry kho công thức (label/learner/hostname + N skills; vendor_read_key → 403) |
| `POST /api/releases/<file>` | release_key (master ở hosted) | upload zip (bước 1) |
| `POST /api/releases` | release_key (master ở hosted) | upload manifest (bước 2) |
| `GET /api/packs` | admin_key | pack latest đang phát per org |
| `POST /api/packs` | admin_key | đẩy pack mới (admin_key scope org) |

Endpoint **chỉ có trên worker** (tài khoản admin 2 tầng — set
`WORKER_ONLY` trong `test-fleet.py`):

| Method + path | Ai | Việc |
|---|---|---|
| `POST /api/bootstrap` | vendor_key | tạo master đầu tiên — tự khoá sau lần đầu |
| `POST /api/login` | — | user/pass → session Bearer 7 ngày |
| `POST /api/logout` | session | xoá session |
| `GET /api/whoami` | session | role + org của caller |
| `POST /api/password` | session | đổi pass mình (xoá hết session) |
| `GET`/`POST /api/orgs` | master | list / tạo org (trả secrets + tài khoản cty-admin đầu) |
| `POST /api/orgs/<org>/license` | master | ký license.json (HMAC khớp make-license.py) |
| `POST /api/orgs/<org>/rotate-secret` | master | sinh beacon_secret + admin_key mới; opt-in `kill_machines` đá máy về pending |
| `GET`/`POST`/`PATCH`/`DELETE /api/admins[/<id>]` | master | CRUD tài khoản admin, disable/reset pass — khoá master cuối cùng bị chặn |
| `GET /api/audit` | session | nhật ký ai-duyệt-gì (cty-admin: chỉ org mình) |

## File máy NV liên quan

`.devin/` — `fleet.json` (cấu hình), `machine.id`, `machine.key`,
`license.json`, `beacon.cursor`, `fleet-inbox.json`, `pack-version`,
`bank-version`, `bank-skills.json` (id skill do kho sở hữu).
Tất cả là machine state → đã gitignore, KHÔNG đi vào release.

## Test

`python3 tests/test-fleet.py` — static contract (snapshot keys parity
.py/.ps1, chuỗi ký license khớp hai phía, adm-render.js dùng chung,
launcher/start spawn đúng điều kiện, **endpoint set collector.py ↔
worker** với `WORKER_ONLY` khai tường minh) + integration dựng
collector thật: pair sai key 401 → pending → approve → beacon 200 →
license ok/invalid → usage gộp → revoke → 403 revoked.

`python3 tests/test-worker.py` — integration cho hosted tier: spawn
`wrangler dev` + D1 local (cần `worker/.dev.vars`), phủ toàn bộ vòng
đời 2 tầng: bootstrap self-lock, legacy X-Admin-Key, login session,
tạo org, license HMAC khớp `make-license.py`, phân quyền cross-org
403/404, audit actor, rotate-secret + `kill_machines`, chặn khoá
master cuối, redact pass chứa quote. Chạy trong CI (`build.yml`).
