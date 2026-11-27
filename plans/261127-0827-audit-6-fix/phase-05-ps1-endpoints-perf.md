# Phase 05 — quyết định 7 endpoint ps1 + perf collector (F5, F9, F10)

## F5 — endpoint `.ps1` thiếu mà portal đang gọi (gap thật = 5, không phải 7)

`test-parity.py` khai `PY_ONLY_OK`:

```python
PY_ONLY_OK = {"/api/bot", "/api/bots", "/api/bot-import",
              "/api/bot-import-confirm", "/api/install-brain",
              "/api/pick-folder", "/api/reveal", "/api/config"}
```

với comment ".ps1 đã đóng băng (ship-learner ph-5)". Nhưng ps1 thực
tế vẫn được update sau đó (`/api/config`, `/api/secrets`,
`/api/setup`, `/api/emit-event` đều có) → "đóng băng" là trạng thái
nợ, không phải quyết định kiến trúc. `/api/config` nằm trong
PY_ONLY_OK nhưng ps1 ĐÃ có — list này đã stale tự thân.

**Verify lại** (sửa sau khi viết plan v1 — v1 nói "7 endpoint, cả
pick-folder/reveal kẹt walkthrough", KHÔNG đúng):

- `/api/pick-folder` + `/api/reveal` trong `.py` là **darwin-only**:
  `_g_pick_folder_probe` trả `supported:false` trên non-mac
  (`chat-bridge.py:1709-1714`), `_h_pick_folder`/`_h_reveal` trả
  `{"ok":false,"err":"không hỗ trợ"}` (`1716`, `1747`). Trên Windows
  kể cả chạy `.py` cũng "không hỗ trợ" → ps1 thiếu 2 endpoint này
  KHÔNG phải regression. Portal cũng degrade êm: app.js probe fail →
  ẩn nút duyệt; reveal step `.catch(()=>{})` → bỏ qua.
- `/api/config`: ps1 ĐÃ có → xoá khỏi PY_ONLY_OK.

Gap thật trên Windows = **5 endpoint**: `/api/bots`, `/api/bot`,
`/api/bot-import`, `/api/bot-import-confirm`, `/api/install-brain`.
Portal gọi vô điều kiện: `web/app.js:1227` (bots), `1274/1329/1339`
(bot), `1368` (bot-import), `1397` (bot-import-confirm);
`web/chat.html:213` (bots); `web/onboarding.html:368,377,391`
(install-brain — onboarding poll + POST). `bfetch` catch → UI
rỗng/ngầm → học viên Windows: **onboarding "cài não 1-click" chết
ngay ở first-run** (visible nhất), bot gallery trống, không import
bot được.

### Quyết định cần chốt TRƯỚC khi vá (ghi trong phase này)

**Phương án A — port đủ:** viết 5 handler ps1 (~300-400 dòng, mirror
logic py: `_g_bots`/`_h_bot` đọc-ghi `workspace/bots.json` + gate;
`bot-import` 2 bước stage→confirm; `install-brain` spawn process +
poll state file). Rủi ro: thêm mặt code ps1 phải duy trì; import zip
trong PS phức tạp hơn py (`Expand-Archive` + lint path).

**Phương án B — feature-gate portal:** ps1 `/api/health` trả
`features: {bots: false, installBrain: false}`; app.js/chat.html/
onboarding.html đọc và ẨN control + tooltip "tính năng này chưa có
trên bản Windows". Giữ PY_ONLY_OK cho 5 endpoint này với comment
quyết định có chủ đích.

**Đề xuất:** B cho cụm bots/bot-import (lớn, defer được); nhưng
`/api/install-brain` cần đánh giá riêng — onboarding Windows là
first-run của đa số học viên, "cài não 1-click" chết ngay lần đầu
mở app là UX tệ. Nếu chọn B cho install-brain thì onboarding phải
có fallback rõ (hướng dẫn cài tay qua install.ps1/verify).

Với pick-folder/reveal: không cần port. Để parity list sạch, thêm
2 stub trả `{"ok":false,"err":"không hỗ trợ"}` (và probe trả
`supported:false`) hoặc đánh dấu `DARWIN_ONLY` trong test-parity —
không để chúng nằm chung bucket "endpoint thiếu" gây nhiễu lần
audit sau.

Cập nhật `PY_ONLY_OK` theo quyết định cuối (xoá `/api/config` bất
kể phương án nào).

## F9 — `collector.py` mở SQLite conn mới mỗi query

`q()` → `db()` (`tools/collector.py:181-193`): mỗi query =
connect + `CREATE TABLE IF NOT EXISTS meta` (DDL *write* trên mọi
read) + SELECT schema_version + vòng migrate-check. Một POST beacon
~8-10 queries → ~10 connects. Dưới `_db_lock` global đã serialize,
đây là overhead thuần.

### Vá

Tách `db()` thành `db()` (open + migrate — chỉ boot) và
`_conn()` (open nhẹ, không migrate). `q()` dùng `_conn()`; boot giữ
`db()` migrate 1 lần. An toàn hơn nữa: giữ flag module `_schema_ok`
sau `db()` boot — `_conn` assert flag, tránh path nào gọi q() trước
migrate (test import thẳng q() mà không boot → flag off → fallback
chạy db() đầy đủ một lần).

```python
_schema_ok = False
def _conn():
    if not _schema_ok:
        return db()
    conn = sqlite3.connect(DB_FP)
    conn.row_factory = sqlite3.Row
    return conn
```

và `db()` set `global _schema_ok = True` cuối hàm.

## F10 — `bank.json` merge O(machines) mỗi pull

`collector.py:1060` `_merged_bank` đọc+parse mọi JSON của org mỗi
GET; worker `index.js:454-473` N R2 GET tuần tự.

### Vá

**collector.py:** cache module-level `{org: (ver, payload_bytes)}` —
`ver` từ `_bank_version` (mtime — rẻ). GET bank.json: tính ver, hit
cache thì trả luôn, miss thì merge + cache. Invalidate tự nhiên khi
có upload mới (mtime đổi → ver đổi → miss). `_db_lock`-style lock
nhỏ cho cache dict (hoặc tái dùng `_db_lock` — đã serialize).

```python
_bank_cache = {}
def _merged_bank(org):
    v = _bank_version(org)
    hit = _bank_cache.get(org)
    if hit and hit[0] == v:
        return hit[1]
    ... merge y cũ ...
    _bank_cache[org] = (v, merged); return merged
```

**worker:** `Promise.all` batch R2 gets (D1 đã list machine_ids):

```js
const objs = await Promise.all(rows.map(r2 =>
  env.BUCKET.get(`skills/${row.org}/${r2.machine_id}.json`)));
for (const o of objs) { if (!o) continue; ... }
```

Cache R2-level optional (put `skills/<org>/_merged.json` khi
upload) — bỏ nếu muốn vá nhỏ; `Promise.all` đã đủ cắt latency
tuần tự.

## Test

- `test-fleet.py`: đo hoặc chỉ functional — POST skills → GET
  bank.json 2 lần → nội dung khớp; upload thêm → GET lại thấy skill
  mới (cache invalidate đúng).
- `test-worker.py`: y hệt cho R2 path.
