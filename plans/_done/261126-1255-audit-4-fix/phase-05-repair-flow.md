# Phase 05 ⏸ — Re-pair trả `machine_key`: repair flow hay ghi tài liệu

## Vá

Finding 1.3 — `collector.py:284-287`: máy đã approved re-pair (mất
file `machine.key`) → server trả lại `machine_key` chỉ với
`beacon_secret` + `machine_id`. `beacon_secret` là shared secret toàn
org trên mọi máy NV ("vé vào cửa") → đủ để impersonate máy đã duyệt:
gửi snapshot giả, tải release/pack. `machine_id` random 16 byte nên
không đoán được — nhưng LAN tier chạy HTTP plaintext nên sniffer LAN
thấy hết `beacon_secret` + `machine_id` + `machine_key` + `admin_key`.

## Option A — repair flow: re-pair cần admin duyệt lại (KHUYẾN NGHỊ cho vendor-hosted/multi-tenant)

Re-pair trên máy approved → KHÔNG trả key; đánh dấu "máy xin cấp lại",
admin approve → cấp key MỚI (rotate miễn phí). Migration v2:

```python
MIGRATIONS[2] = [
    "ALTER TABLE machines ADD COLUMN repair INTEGER DEFAULT 0",
    "ALTER TABLE machines ADD COLUMN pending_key TEXT",
]
```

Trong `_pair` (thay dòng 284-287):

```python
if row and row["approved"] and not row["revoked"]:
    if row["repair"] and row["pending_key"]:
        # admin đã duyệt cấp lại → trả key mới, rotate: key cũ chết
        mk = row["pending_key"]
        q("UPDATE machines SET machine_key=?, repair=0, "
          "pending_key=NULL WHERE machine_id=?",
          (mk, mid), write=True)
        return self._json({"status": "approved", "machine_key": mk})
    # máy mất key xin cấp lại — không trả key chỉ vì biết beacon_secret
    if not row["repair"]:
        q("UPDATE machines SET repair=1 WHERE machine_id=?",
          (mid,), write=True)
    return self._json({"status": "pending"})
```

(`/api/beacon` vẫn chạy bằng key cũ trong lúc chờ — máy thật không chết;
máy đã mất key thì pending, đúng ý.)

`/api/pair-approve` chia hai nhánh (dòng 574-583). ⚠ Hai chỗ SELECT
phải sửa kèm — code hiện `SELECT org FROM machines` KHÔNG trả `repair`:

```python
# dòng 574: phải lấy cả repair — sqlite3.Row trả IndexError khi
# đọc cột không có trong SELECT
r = q("SELECT org,repair FROM machines WHERE machine_id=?", (mid,),
      one=True)
...
mk = secrets.token_hex(24)
if r["repair"]:
    # cấp lại: vào pending_key, máy nhận ở lần pair kế — key cũ sống
    # tới lúc đó nên máy thật không downtime
    q("UPDATE machines SET pending_key=? WHERE machine_id=?",
      (mk, mid), write=True)
else:
    q("UPDATE machines SET approved=1, revoked=0, machine_key=? "
      "WHERE machine_id=?", (mk, mid), write=True)
return self._json({"ok": True, "machine_key": mk})
```

Dashboard thấy repair: query `/api/pending` (dòng 471-475) đổi WHERE
thành `(approved=0 OR repair=1) AND revoked=0` — VÀ thêm `repair` vào
SELECT list (hiện `SELECT machine_id,org,hostname,os,first_seen,
last_seen,license_status` — cột liệt kê tường minh, quên thêm là
`dict(r)` thiếu field) → adm-render.js hiện badge "cấp lại key".

Cạnh:

- Spam pair của máy approved chỉ set flag idempotent — không flood.
- Revoke giữ nguyên — máy revoked vẫn trả `{"status":"revoked"}`.
- Máy thật mất key → pending tới khi admin bấm — UX mất một bước duyệt
  nhưng đúng security (chính là giá của vá).

## Option B — giữ trả key, ghi rõ vào DEPLOY.md

Chấp nhận: LAN tier là HTTP plaintext nên `beacon_secret`,
`machine_id`, `machine_key`, `admin_key` đều sniffable sẵn — vá re-pair
không cứu được gì nếu LAN không tin. Ghi DEPLOY.md: "LAN tier yêu cầu
LAN tin cậy vật lý; org nhạy cảm → customer-hosted HTTPS".

**Hợp khi:** fleet chỉ chạy LAN nhỏ tin cậy; không hợp khi
vendor-hosted/multi-tenant nơi beacon_secret của org A không được quyền
lật máy org A (mà vẫn là shared secret).

## Cạnh tranh cần quyết

- Re-pair bao lâu xảy ra một lần trong thực tế? (Máy mất `machine.key`
  = user xoá file hoặc reset profile — hiếm → Option A rẻ về UX.)
- Dashboard adm-render.js có sẵn chỗ hiện pending với field thêm không
  — Option A cần vài dòng render.

## Test (sau khi chọn Option A)

- e2e: pair → approve → re-pair → `pending` (không key) + `repair=1`;
  admin approve → re-pair → `approved` + key MỚI ≠ key cũ; beacon key
  mới 200, beacon key cũ 403.
- Re-pair máy không repair → dashboard pending hiện row.
- Migration: DB cũ mở lên có 2 cột mới, dữ liệu nguyên.

## Done khi

`beacon_secret` một mình không lấy được `machine_key` của máy đã duyệt
(A), hoặc DEPLOY.md ghi rõ LAN trust requirement (B).
