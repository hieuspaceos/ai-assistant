# Vendor infra — hạ tầng phía vendor trên troly.hieuspace.com

Tài liệu cho chính đội vận hành (không đưa khách). Một domain, một
cert, mọi thứ treo theo path.

## Sơ đồ

```
troly.hieuspace.com
├── /                → landing (site/index.html)
├── /privacy         → site/privacy.html — BẮT BUỘC cho Chrome Store
│                      (extension có quyền rộng phải khai privacy URL)
├── /releases/       → tĩnh: latest.json + troly-<ver>.zip đã ký
│                      ed25519 — update.py của máy/collector kéo từ đây
└── /fleet/          → hosted collector = Cloudflare Worker
                       (worker/src/index.js — port của collector.py)
    ├── /            → dashboard (login account 2-role master/cty-admin,
    │                  vẫn nhận admin_key qua tab "Dán key")
    ├── /api/pair    → máy xin vào
    ├── /api/beacon  → snapshot 15'
    └── /api/org-ping→ meta-telemetry cho vendor (1/ngày/collector)
```

## Hiện trạng (tháng 11/2026) — ĐÃ DEPLOY

Domain qua **Cloudflare proxy** → GitHub Pages (branch `gh-pages`) cho
site; **`/fleet/` đã live** qua Worker `troly-fleet` (đường A' — không
VPS nào cả):

- **Worker** `worker/src/index.js`: port nguyên semantics của
  `tools/collector.py` (endpoint/key/scope giống hệt). Route
  `troly.hieuspace.com/fleet*` trong `worker/wrangler.toml`.
- **D1** `troly-fleet-db`: schema giống `MIGRATIONS[1]` của py
  (`worker/schema.sql`).
- **R2** `troly-fleet-assets`: `releases/` + `packs/` — cùng key
  layout như `DATA/` của py.
- **Static Assets**: `collector-web/` (dashboard fetch `api/...`
  tương đối — chạy được dưới prefix lẫn trần `/`).
- **Cron**: `7 */6 * * *` mirror, `30 2 * * *` telemetry — đều
  early-return khi thiếu config (giống py).
- **Secrets** (Cloudflare secret store, không nằm trong repo):
  `ORGS_JSON` (orgs + beacon/license/admin_key), `VENDOR_KEY`,
  `TELEMETRY_KEY`. Bản sao lưu vendor nằm ở `collector.json` máy vendor
  (gitignored).
- `/fleet` (không slash) → worker normalize thẳng về `/`, không cần
  redirect; hint URL suy prefix từ request path nên `urljoin` phía máy
  đúng (`/fleet/releases/x`, `/fleet/packs/<org>/<v>.json`).

Ops:
```sh
cd worker && wrangler deploy                 # sau khi sửa index.js
wrangler secret put ORGS_JSON                # seed/fallback — org trong D1 ưu tiên hơn
wrangler d1 execute troly-fleet-db --remote --command "..."
wrangler r2 object delete troly-fleet-assets/<key>
```

Thêm org mới cho khách: **qua dashboard** (login master → tab Công ty →
tạo org → nhận `fleet.json` + `admin_key` + tài khoản cty-admin bàn
giao) hoặc `POST /api/orgs` — org ghi vào D1, không cần deploy/đổi
secret. Đường cũ `wrangler secret put ORGS_JSON` chỉ còn vai trò
seed/khôi phục. Xoay `beacon_secret`/`admin_key` của org:
`POST /api/orgs/<org>/rotate-secret` hoặc nút "Xoay khoá" trên
dashboard (có tuỳ chọn `kill_machines` đá máy về pending).

Tài khoản admin: `POST /api/bootstrap` (cần VENDOR_KEY) tạo master đầu
— chạy đúng 1 lần rồi tự khoá; sau đó master tạo/ khoá admin qua tab
Tài khoản. Khoá master cuối cùng bị chặn.

Còn lại chưa làm: `/releases/` trên Pages (kênh update cho máy CÁ
NHÂN — máy fleet lấy release qua collector R2, không qua đây) — vẫn
404; Always Use HTTPS trong dashboard Cloudflare.

## Lịch sử quyết định

Trước đây dự định: Worker chỉ proxy `/fleet/*` → VPS chạy collector.py.
Đã chuyển sang **Worker chạy thẳng** (không VPS): collector chủ yếu
CRUD+SQLite nên port sang Workers+D1+R2 gọn; free tier đủ cho pilot
(~96 req/ngày/máy); bỏ hẳn một server phải vá. Đánh đổi: collector có
2 implementation (`.py` self-host / Worker hosted) — mọi thay đổi
protocol endpoint phải patch cả hai, giống parity `.py`/`.ps1`.

## Đẩy release lên /releases/

```sh
# sau khi scripts/build-release.sh xanh:
scripts/sign-release.py --key ~/.troly/vendor.key dist/troly-<ver>.zip
# → dist/manifest-<ver>.json gồm {version,file,sha256,size,sig}
# ghép vào dist/latest.json rồi:
rsync -av dist/ troly:/var/www/troly.hieuspace.com/releases/
```

Server chỉ là bưu điện — máy khách verify sha256 + chữ ký ed25519 bằng
`tools/vendor-pubkey` nhúng sẵn; VPS bị deface không forge được release.

## Hosted collector per-cty

`tools/collector.py --config /srv/fleet/<slug>.json --data /srv/fleet/<slug>` —
một process + một file SQLite mỗi cty, không multi-tenant DB. Mỗi cty một `beacon_secret` +
`admin_key` riêng (cấp qua `make-license.py` cùng đợt license). Config
máy vendor thêm `vendor_read_key` (meta-dashboard đọc rollup — KHÔNG
ship trong config khách) và `release_key` (đẩy release; bản khách
không set → upload tắt, chỉ mirror từ vendor).

`/fleet/api/org-ping` — collector (kể cả bản self-hosted của khách)
gọi 1/ngày: `{org, machines_active, version_dist, license_expiry}`.
Vendor mù tịt sau bàn giao nếu thiếu lớp này — đây là "mắt" để support
và nhắc gia hạn. Opt-out: config `"org_ping": false` ở collector khách.

## Nguyên tắc

- Vendor thấy **org-level rollup**; chủ cty thấy **machine-level**;
  không ai thấy nội dung chat/file. Giữ vậy trong mọi feature mới.
- Không private key nào nằm trên VPS — khoá ký release ở máy vendor
  offline; machine_key cấp per-cty qua pairing.
