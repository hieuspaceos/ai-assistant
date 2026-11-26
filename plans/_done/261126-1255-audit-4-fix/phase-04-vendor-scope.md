# Phase 04 ⏸ — Vendor key: tách key hay chỉ siết scope (QUYẾT ĐỊNH TRƯỚC)

## Vá

Finding 1.2 — `VENDOR_KEY` trả `"*"` trong `_admin_org`
(`collector.py:233-240`) qua được MỌI check scope: approve/revoke máy,
đẩy pack, upload release, đọc full snapshot từng máy (`/api/fleet/<mid>`
chứa `perms` — đường dẫn learner, PII). Nặng hơn: đây là cùng key nằm
plaintext trong `collector.json` của mọi khách self-host (dùng auth
outbound `telemetry_loop`) → ai đọc được config đó có god-mode inbound
trên collector đó.

Docstring dòng 76-78 hứa "chỉ rollup org-level, không machine-level" —
code không làm điều đó.

## Option A — tách hai key (KHUYẾN NGHỊ)

Nhận ra: key trong config khách là credential OUTBOUND (để ghi
org-ping lên collector vendor) — nó không nên có quyền inbound trên
chính collector khách. Tách:

```python
# config vendor-hosted collector:
#   "telemetry": {"key": "<ping-key>"}     # credential ghi org-ping
#   "vendor_read_key": "<read-key>"        # đọc rollup dashboard
VENDOR_READ = CFG.get("vendor_read_key") or ""
PING_KEY = TELE.get("key") or ""           # đổi tên VENDOR_KEY → rõ vai
```

- `_admin_org`: `VENDOR_READ` → `"*"`; admin keys → org.
- `POST /api/org-ping` (dòng 593-595): check `_eq(header, PING_KEY)` —
  semantics giữ nguyên, chỉ đổi tên biến.
- `"*"` thành **read-rollup-only**, bắt ở route. ⚠ Đã audit lại — cần
  quyết `*` được đọc NHỮNG GÌ, vì `/api/fleet` (list) trả **machine-level**
  (hostname, learner name — PII) chứ không phải rollup org:
  - Chặt theo docstring ("không machine-level"): `*` chỉ được
    `GET /api/org-pings` + `GET /api/license` (aggregate) + `GET /api/packs`
    (danh sách pack, không PII). `/api/fleet`, `/api/pending`,
    `/api/fleet/<mid>` đều 403 cho `*`.
  - Nới nếu meta-dashboard cần list máy: thêm `/api/fleet` + `/api/pending`
    vào whitelist `*` — chấp nhận vendor thấy hostname/learner (cân nhắc
    PII), nhưng `/api/fleet/<mid>` (full snapshot, `perms` = đường dẫn
    folder) vẫn 403.
  - mọi POST admin (`pair-approve`, `pair-revoke`, `/api/releases`,
    `/api/releases/<f>`, `/api/packs`) → `org == "*"` → 403 — chắc chắn,
    không có ngoại lệ.
- Config khách self-host: KHÔNG cần `vendor_read_key` → key lộ chỉ ghi
  được org-ping, gần như vô hại. Vendor-hosted collector thêm
  `vendor_read_key` cho meta-dashboard.
- Docstring đầu file + template `collector.json` cập nhật.

**Chi phí:** thêm một field config; vendor infra phải phát read-key.
**Được:** key trên máy khách mất quyền inbound hoàn toàn.

## Option B — giữ một key, chỉ siết scope `"*"`

Vẫn `VENDOR_KEY` → `"*"` nhưng áp các gate `org == "*"` → 403 ở write
+ machine-level GET như trên.

**Chi phí:** vài dòng.
**Được/không:** đơn giản, nhưng key lộ trong config khách VẪN đọc được
rollup mọi org của collector đó (`/api/fleet` list, license, pending) —
giảm từ god-mode xuống read-only, chưa triệt để.

## Cạnh tranh cần quyết

- Meta-dashboard vendor hiện dùng key nào? Nếu đang dùng `telemetry.key`
  để đọc `/api/fleet` thì Option A đổi credential phía vendor —
  `vendor-infra.md` cập nhật theo.
- Customer-hosted tier (VPS khách): họ tự cấu hình — không có
  `vendor_read_key` thì vendor không đọc được gì (đúng: riêng tư).

## Test (sau khi chọn)

- Option A: request với `telemetry.key` → mọi GET/POST trừ org-ping →
  401; `vendor_read_key` → GET rollup 200, GET `/api/fleet/<mid>` 403,
  POST approve 403.
- Option B: vendor key → GET rollup 200, machine-level + write 403;
  admin key org A → vẫn full quyền org A.

## Done khi

Không một credential nào trong `collector.json` của khách có quyền
admin inbound; `"*"` không đụng được write endpoint và machine detail.
