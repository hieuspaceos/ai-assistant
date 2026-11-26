# Plan 1/5 — Fleet console: beacon + collector + license + dashboard trung tâm

Ngày: 2026-11-25. Mục tiêu: cho một người quản trị (IT/chủ doanh nghiệp)
xem được **toàn bộ máy** đã cài ai-assistant — ai đang dùng, dùng nhiều
không, bot nào, lỗi gì — mà **không mở bridge ra mạng** (giữ nguyên
threat model loopback).

## Ngữ cảnh đã chốt

- `web/admin.html` (đã có) = màn hình **từng máy**, đọc 6 GET endpoint của
  bridge :7682. Fleet console tái dùng đúng shape JSON đó.
- Mô hình **push, không pull**: mỗi máy chủ động POST snapshot lên
  collector của công ty. Không endpoint nào trên máy nhân viên bị expose.
- License = "đếm và báo", gentle enforcement — flag chứ không khoá app
  (khoá cứng = cả phòng nghỉ việc một sáng thứ hai).
- Constraint stdlib-only giữ nguyên trên máy nhân viên. Collector là
  server-side → được phép phong phú hơn nhưng vẫn ưu tiên stdlib để
  "single-file chạy được ngay" cho công ty không có hệ thống.

## Kiến trúc

```
Máy NV 1 ─┐   tools/beacon.py (spawn bởi launcher.py)
Máy NV 2 ─┼─ POST snapshot + license + fingerprint mỗi 15'
Máy NV n ─┘            │
                       ▼
              ┌─────────────────────┐
              │ collector (cty)     │  nhận → lưu → phát
              │ tools/collector.py  │  releases + config-pack
              │  :8790 loopback/LAN │  (plan 2 dùng lại)
              └─────────┬───────────┘
                        ▼
              tools/collector-web/  dashboard đọc collector API
              (static, giống admin.html nhưng n máy)
```

## Hai tier triển khai — CÙNG một collector.py

Quyết sau phân tích VPS (audit round 7): collector chạy ở hai chỗ,
code giống hệt nhau, khác chỗ đứng:

| Tier | Collector ở đâu | Cho ai | HTTPS | Remote |
|---|---|---|---|---|
| **LAN self-hosted** | Máy IT trong LAN cty | Cty không có infra public | ✗ HTTP | ✗ |
| **Customer-hosted** | VPS/domain CỦA KHÁCH — `fleet.<domain-cty>` | Cty có domain/hạ tầng (IMA: `*.imagetraveldmc.com` + CapRover) | ✓ cert thật | ✓ |
| **Vendor-hosted** | `troly.hieuspace.com/fleet/` | Cty nhỏ không IT/domain | ✓ | ✓ |

**Customer-hosted là tier tốt nhất khi khách có domain**: reachability
của hosted (nhân viên remote beacon được) + data ownership của
self-hosted (metadata ở trên hạ tầng của CHÍNH khách — câu chuyện
riêng tư đẹp nhất). `fleet.json` nhận URL bất kỳ — code không đổi,
chỉ khác nơi deploy collector và cert. Với IMA: collector gần như
là một app thêm trong CapRover của họ, cùng hạ tầng
`mcp.imagetraveldmc.com` (plan 5).

Tasks thêm cho hosted tier:
- [x] `collector.py --org <org>` — mỗi cty một file SQLite riêng
      trong `data/<org>.db` (isolation bằng file, không build
      multi-tenant DB — đủ và đơn giản). Một process serve nhiều org
      qua `--org-dir` hoặc mỗi org một process+port.
- [x] HTTPS: vendor-hosted đi qua path `troly.hieuspace.com/fleet/`
      (nginx `location /fleet/` → proxy_pass) — dùng chung cert +
      domain với site, không cần subdomain/cert mới. Customer-hosted:
      cert thật theo hạ tầng của khách (LE qua CapRover/nginx của
      họ). Beacon verify cert thật cả hai (stdlib urllib tự làm);
      KHÔNG hỗ trợ self-signed — hoặc có flag `insecure` ghi rõ rủi
      ro trong log, chỉ để dev.
- [x] `X-Admin-Key` per-org — IT cty A không đọc được fleet cty B
      (key gắn với org trong request).
- [x] **Meta-telemetry lên vendor** (role B): collector định kỳ
      (1/ngày) POST rollup `{org, machines_active, version_dist,
      license_expiry, ts}` về `troly.hieuspace.com/fleet/api/org-ping`
      (key vendor cấp) → vendor dashboard "IMA 18/20 v1.4, Acme
      5/10 v1.3". Chỉ org-level, không machine-level — vendor thấy
      khách sống/khoẻ để support + nhắc gia hạn; cty vẫn giữ
      machine-level. Opt-out bằng `COLLECTOR_NO_TELEMETRY=1`.
- [x] Hợp đồng triển khai có điều khoản DPA (PDPD) cho tier hosted:
      vendor xử lý metadata thay khách — ghi trong `deploy/DEPLOY.md`.

## Tasks

### Phase 01 — Machine identity + license format

- [x] `.devin/machine.id` — uuid4 sinh lần chạy đầu (trong launcher hoặc
      beacon), KHÔNG rotate. Fingerprint = machine.id + hostname — đủ để
      đếm ghế, không thu thập gì thêm.
- [x] `.devin/license.json` — do vendor (mình) cấp lúc triển khai:
      ```json
      {"org": "IMA", "seats": 20, "expiry": "2027-01-01",
       "issued": "2026-11-25", "sig": "<hmac-sha256 hex>"}
      ```
      `sig = HMAC(vendor_secret, "org|seats|expiry|issued")` — secret chỉ
      nằm ở script cấp phía vendor + collector của đó. Client KHÔNG verify
      crypto (stdlib không có verify chữ ký) — client chỉ đọc `expiry` để
      hiện banner vàng "gần hạn"; enforcement thật nằm ở collector.
- [x] `tools/make-license.py` — script phía vendor sinh license (nhập
      org/seats/expiry + secret từ env `TROLY_LICENSE_SECRET`). Chạy một
      lần lúc gói bộ cài cho khách.
- [x] Cấu hình collector per máy: `.devin/fleet.json`
      ```json
      {"collector": "http://<ip-máy-IT>:8790", "org": "IMA",
       "beacon_secret": "<chuỗi do vendor cấp, chung cả org>"}
      ```
      `beacon_secret` = shared key để collector tin request — đặt trong
      header `X-Beacon-Key`. Không có file → beacon không chạy (single
      machine mode hiện tại giữ nguyên, không ảnh hưởng ai chưa deploy).
- [x] **Device pairing** (học `gateway/methods/pairing.go` của GoClaw —
      audit round 6): shared secret cả org là mắt yếu — một máy lộ là
      kẻ trong LAN spam được mọi máy. Nâng cấp: beacon lần đầu gửi
      `pair` request (machine.id + hostname + license) bằng
      beacon_secret → hiện "pending" trên dashboard → admin approve →
      collector phát `machine_key` riêng (ghi `.devin/machine.key`) →
      mọi beacon sau dùng machine_key. Revoke được từng máy (nhân
      viên nghỉ việc, máy mất) mà không ảnh hưởng fleet. beacon_secret
      giữ vai trò "vé vào cửa" thôi.
- [x] Collector DB: bảng `schema_version` + hàm migrate tuần tự
      (học `internal/upgrade` của họ — SQLite cũng cần migration
      vì collector sẽ sống lâu ở máy khách).

### Phase 02 — `tools/beacon.py` (+ `beacon.ps1` parity)

- [x] Vòng lặp mỗi `TROLY_BEACON_INTERVAL` giây (default 900):
      GET nội bộ `http://localhost:7682/api/health|brain|config|bots|
      permissions|connections|poll` (kèm `X-Bridge-Token` từ
      `.devin/bridge.token`) → gói thành snapshot.
- [x] `poll` dùng cursor: `.devin/beacon.cursor` lưu `next` từ lần
      trước → `poll?since=<cursor>` chỉ kéo event mới (since=0 mỗi
      15' kéo lại cả event store — audit round 5). `reset:true` →
      reset cursor, đếm từ đầu.
- [x] Snapshot thêm: `machine_id`, `hostname`, `os`, `version` (app —
      collector cần để quyết `update` response), `pack_version` (đọc
      `.devin/pack-version` — collector quyết `pack` response),
      `license` (bản đầy đủ để collector verify sig), `ts`,
      `beacon_ver`.
      Thống kê event: đếm `done/err/perm/perm:auto/tool/inj_suspect`
      từ `poll` — chỉ gửi **đếm theo loại + window**, KHÔNG gửi text
      nội dung (privacy của nhân viên — dashboard chủ thấy "dùng
      nhiều không", không thấy "nói gì"). `inj_suspect`/`perm:auto`
      từ plan 6 — dashboard flag máy hay gặp nội dung độc / gate bị
      bypass nhiều bởi allowlist.
- [x] POST `collector/api/beacon` với `X-Beacon-Key`; timeout 5s; lỗi
      mạng → retry backoff (5', 15', 30' rồi quay vòng). Offline thì máy
      vẫn chạy bình thường — beacon là phụ.
- [x] Nhận response: collector có thể trả `{update: ver, pack: n}` —
      beacon chỉ GHI vào `.devin/fleet-inbox.json`, việc áp dụng là của
      plan 2 (update.py) — beacon không tự vá code.
- [x] `launcher.py`: spawn beacon cùng các con khác nếu `fleet.json`
      tồn tại. `launcher.ps1` tương đương.
- [x] `beacon.ps1`: cùng contract (đọc token, GET 7 endpoint, POST
      snapshot, ghi inbox). Parity test: cùng field set.

### Phase 03 — `tools/collector.py` (single-file, stdlib)

Chạy trên MỘT máy trong cty (máy IT hoặc VPS nội bộ). SQLite stdlib lưu
snapshot — không cần Postgres.

- [x] Endpoints:
  - `POST /api/beacon` — xác thực `X-Beacon-Key` → upsert
    `machines(machine_id, org, hostname, os, last_seen, snapshot_json,
    license_json, ev_stats)`; trả `{update, pack}` khi có.
  - `GET /api/fleet` — list máy: machine_id, hostname, last_seen,
    brain, version, ext_version, ev_stats 24h, license_status
    (ok/expiring/exceeded/invalid), bot đang active.
  - `GET /api/fleet/<machine_id>` — snapshot đầy đủ của một máy
    (cho trang chi tiết — tái dùng render của admin.html).
  - `GET /api/license` — đếm unique machine_id active 30 ngày vs
    `seats` → trạng thái license.
  - `POST/GET /api/releases` + `/api/packs` — chỗ plan 2 cắm vào.
- [x] Bind: mặc định `0.0.0.0:8790` (LAN cty cần tới được — KHÔNG
      loopback vì máy NV phải push tới). Auth = beacon_secret cho POST;
      GET dashboard sau `/api/fleet*` đòi `X-Admin-Key` riêng (khác
      beacon_secret — máy NV không đọc được data máy khác).
- [x] License check tại `POST /api/beacon`: verify `sig` bằng secret
      của org đó; sai/hết hạn → vẫn lưu snapshot nhưng đánh dấu
      `license_status` → dashboard flag. Không reject — gentle.
- [x] Rate limit + body cap giống pattern bridge (máy cty bị flood vẫn
      là máy cty).

### Phase 04 — `collector-web/` dashboard trung tâm

- [x] `index.html` — danh sách máy dạng bảng: hostname / nhân viên
      (learner_name từ config) / não / version / ext / last_seen (xám
      khi >1h không beacon = máy tắt hoặc mất mạng) / lượt dùng hôm
      nay / lỗi / bot. Sort + filter theo phòng ban (tag từ config-pack).
- [x] Click máy → trang chi tiết render giống `admin.html` (tách phần
      render của admin.html thành `adm-render.js` dùng chung — DRY,
      không copy).
- [x] Header: tổng ghế "18/20 đang dùng" + cảnh báo license.
- [x] Serve static bởi chính collector (`GET /` → index.html) — khỏi
      server phụ. Dashboard cầm `X-Admin-Key` theo pattern portal:
      mở `http://collector:8790/?key=<admin_key>` → JS nhét key vào
      header mọi fetch `/api/fleet*` (giống bridge-token.js).

### Phase 05 — Parity + tests + docs

- [x] `test-fleet.py` mới (pattern test-gates): snapshot shape beacon
      gửi khớp schema collector nhận; license sig verify đúng/sai;
      config thiếu → beacon im lặng không crash launcher.
- [x] Test parity beacon .py/.ps1 — cùng field set snapshot.
- [x] `docs/fleet.md` — kiến trúc push, port, hai secret
      (beacon vs admin), cách đổi collector URL, privacy: cái gì
      được gửi / cái gì không.
- [x] `SECURITY.md` bổ sung dòng: collector là biên mới (mạng cty,
      không phải loopback) — threat model mới: máy NV giả → spam
      snapshot (mitigate: beacon_secret + upsert theo machine_id);
      admin_key lộ → đọc được metadata toàn cty (không có nội dung).

## GATE

- Beacon chạy trên máy dev → collector nhận snapshot đúng schema →
  dashboard hiện 1 máy.
- Sai beacon_secret → 401; license giả/hết hạn → flag trên dashboard,
  app máy NV vẫn chạy.
- Tắt collector → máy NV hoạt động bình thường, beacon retry không
  crash.

## Rủi ro / mở

- `beacon_secret` lộ (copy từ máy NV) → kẻ trong LAN spam được snapshot
  giả — chấp nhận (gentle), ghi residual.
- Beacon → collector đi HTTP trần trong LAN — snapshot chứa
  hostname/license (không nội dung chat). Chấp nhận trong LAN cty;
  tier hosted đi HTTPS cert thật → residual chỉ còn ở self-hosted.
- Collector trên Windows cty: `collector.py` là .py → máy IT cần Python.
  Phương án: đóng gói chung bộ cài `TroLyAI.exe` có sẵn python —
  collector chạy bằng binary đó (`troly --collector`). Quyết khi build.
- Biên lai pháp lý VN (Luật TTDNC/PDPD): dashboard cho chủ xem usage
  nhân viên — cần dòng trong hợp đồng triển khai + thông báo nhân viên.
  KHÔNG gửi nội dung chat/file là đúng hướng rồi — giữ nguyên.

## Kết quả triển khai (2026-11-25)

Đã code xong, `tools/test-fleet.py` xanh (36 check — static contract +
integration collector thật: pair 401 → pending → approve → beacon 200 →
license ok/invalid → usage gộp → revoke → 403 revoked). GATE đạt qua
e2e tay: beacon pair → pending trên dashboard → approve → machine.key
→ snapshot lên `/api/fleet`.

**Khác spec đã ghi (quyết khi code):**

- Multi-org: thay vì `--org` file SQLite riêng, dùng MỘT DB có cột
  `org` + `admin_key → org` scope mọi GET (IT org A không đọc được
  org B). Hosted multi-tenant vẫn khuyến nghị một process per org
  (isolation mạnh hơn query filter) — code không cần đổi.
- Revoke GIỮ `machine_key` (không NULL) — máy bị revoke tra ra được
  row → trả `status:"revoked"` rõ ràng, beacon biết xoá key + re-pair
  hiện pending. Spec gốc trả lỗi chung → máy không biết mình bị revoke.
- `/api/license` chỉ đếm `seats` từ license **sig hợp lệ** — license
  bị sửa mà vẫn đếm ghế thì kẻ gian tự nâng ghế lên vô hạn.
- `pending` không tính là lỗi backoff — có nhịp riêng `PAIR_RETRY`
  (300s): admin duyệt xong máy vào fleet nhanh, không kẹt 30'.
- Release/pack hint: `POST/GET /api/releases|packs` thành file-based
  `collector-data/releases.json`/`packs.json` đọc mỗi beacon — đủ cho
  plan 2 cắm vào, không cần endpoint quản trị riêng.
- `adm-render.js`: canonical ở `web/`, `collector.py find_static`
  fallback sang `web/` khi chạy từ repo → không copy file trong repo;
  deploy độc lập copy `collector-web/` + file đó.
- Windows: không có `launcher.ps1` — `start.bat` spawn `beacon.ps1`
  (đã viết, parity contract snapshot qua test-fleet).
- stdout beacon `flush=True` — log `.logs/beacon.log` không bị buffer
  (bắt được khi e2e).

**Còn lại (ops/deploy — không code):**

- HTTPS cert thật cho tier hosted — việc của nginx/CapRover lúc deploy;
  code đã nhận path prefix `/fleet/` và beacon verify cert qua stdlib.
- Điều khoản DPA trong hợp đồng → viết trong `deploy/DEPLOY.md` (plan 4).
- `troly --collector` đóng gói Windows không-Python → quyết khi build
  binary (plan 4).
