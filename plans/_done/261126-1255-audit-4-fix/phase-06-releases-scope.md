# Phase 06 ⏸ — Releases scope: ai được upload release (QUYẾT ĐỊNH TRƯỚC)

## Vá

Finding 1.5b — `REL_DIR` global cho mọi org (`collector.py:690`). Trên
collector multi-org (LAN tier một process nhiều org), admin org A
`POST /api/releases` → manifest global → máy org B nhận update hint.
Máy NV vẫn verify sha256 + ed25519 bằng vendor-pubkey nên không chạy
được file xấu — worst case là stale/denied — nhưng org admin đáng lẽ
không có quyền đẩy release xuống fleet org khác.

(Phần `latest.json` overwrite + atomic đã vá ở phase-01; phase này chỉ
quyết "ai được upload".)

## Option A — `release_key` riêng trong config (KHUYẾN NGHỊ)

Release là artifact của VENDOR (đã ký ed25519 bởi vendor) — người upload
phải là vendor/IT giữ key ký, không phải org admin bất kỳ. Config:

```json
"release_key": "khoá-đẩy-release"     // top-level, tuỳ chọn
```

```python
RELEASE_KEY = CFG.get("release_key") or ""
```

Cả hai route upload (`/api/releases/<file>` và `/api/releases`) thay
`_scope()` bằng:

```python
if not (RELEASE_KEY and
        _eq(self.headers.get("X-Admin-Key"), RELEASE_KEY)):
    return self._json({"err": "thiếu hoặc sai release_key"}, 401)
```

Chưa set `release_key` → upload tắt hoàn toàn, release chỉ lên bằng
mirror_loop/copy tay (đúng cho collector khách nhận từ vendor).
`/api/releases` manifest check giữ nguyên (file phải tồn tại trước).

**Chi phí:** một field config + hai gate. **Được:** org admin mất quyền
upload luôn — khỏi bài toán per-org; global REL_DIR hợp lý vì release
thật ra là của vendor.

## Option B — per-org releases

Layout giống packs: `REL_DIR/<org>/` + `latest-<org>.json`; upload vào
dir org mình; `_release_hint(b, row["org"])` đọc manifest của org;
GET `/api/releases/latest` + `/releases/<f>` resolve theo org của row.

**Chi phí:** đổi path máy tải + migrate file hiện có + nhiều chỗ đụng
(`_release_hint`, upload, download path check, mirror_loop cũng phải
ghi vào org nào). **Được:** quyền nhất quán với pack. **Không:** release
vendor-signed mà phát theo org → cùng file zip nhiều bản copy, mirror
loop phức tạp.

## Option C — giữ global

Chỉ phase-01 (chặn `latest.json` + atomic); chấp nhận org admin đẩy
release ảnh hưởng org khác — trên deployment process-per-org
(vendor-infra) là moot.

## Cạnh tranh cần quyết

- Ai đẩy release trong thực tế: vendor pipeline (`sign-release.py` +
  upload) hay IT khách? Nếu IT khách cần đẩy → phải cấp họ
  `release_key` — vẫn tách được khỏi admin_key dashboard.
- Multi-org LAN tier có thật sự chạy không, hay luôn process-per-org?
  Nếu luôn một-org → Option C đủ.

## Test (sau khi chọn)

- Option A: admin key hợp lệ → 401 trên cả hai route; `release_key` →
  200; không set key → 401; máy NV `GET /api/releases/latest` vẫn
  bằng machine_key.
- Option B: admin A upload → chỉ máy org A thấy hint; máy B không.

## Done khi

Credential dashboard org không đủ quyền đẩy release xuống máy org khác
(A), hoặc release scope theo org (B), hoặc quyết định ghi nhận (C).
