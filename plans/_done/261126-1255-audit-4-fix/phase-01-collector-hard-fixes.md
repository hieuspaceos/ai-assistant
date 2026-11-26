# Phase 01 — collector.py: vá cứng không phụ thuộc quyết định (~30 dòng)

## Vá

Bảy finding nhỏ gộp một commit vì cùng file, cùng kiểu "thiếu check một
dòng". Không đổi contract với beacon/dashboard.

## 1.1 — `porg` traversal (`collector.py:655-676`)

Chặt nhất: `porg` phải là org đã khai trong config — pack cho org không
tồn tại vốn vô nghĩa, và giết luôn crash `latest-{porg}.json` (tên chứa
`/` → FileNotFoundError → handler chết). Thêm `type(ver) is int` thay
`isinstance` (chặn `True` → `True.json`) và `ver >= 0`.

```python
# trước (dòng 655-659)
porg = str(b.get("org") or "")
ver = b.get("pack_version")
if not porg or not isinstance(ver, int):
    ...

# sau
porg = str(b.get("org") or "")
ver = b.get("pack_version")
if porg not in ORGS or type(ver) is not int or ver < 0:
    return self._json({"err": "pack cần org trong config + "
                              "pack_version int >= 0"}, 400)
```

Check `org != "*" and porg != org` (dòng 660) giữ nguyên phía dưới.

## 1.4 — `_body` non-dict (`collector.py:249-262`)

`json.loads("[1,2,3]")` qua được parse rồi `b.get(...)` → AttributeError.
Mọi caller đã check `b is None` nên chỉ cần trả None sau 400:

```python
try:
    b = json.loads(self.rfile.read(cl) or b"{}")
except Exception:
    self._json({"err": "json không hợp lệ"}, 400)
    return None
if not isinstance(b, dict):
    self._json({"err": "body phải là json object"}, 400)
    return None
return b
```

**1.4b — crash cấp hai trong `_beacon` (phát hiện khi audit lại plan).**
Check dict top-level chưa đủ: `_beacon` đọc nested `snap.get("config")`
(dòng 318-321), `counts.items()` (dòng 347) — body hợp lệ
`{"snapshot":[1],"counts":[1]}` vẫn AttributeError → connection rớt.
Helper một dòng dùng cho mọi nested dict:

```python
def _as_dict(x):
    return x if isinstance(x, dict) else {}
```

rồi bọc `snap`, `cfg`, `brain`, `health`, `counts` (và `ev_stats` khi
dumps `b.get("counts")`). Các endpoint khác an toàn: `_pair` chỉ
`b.get`/`str()`/`json.dumps`; `license_status` đã isinstance(lic, dict).

## 1.5a — upload `latest.json` + ghi atomic (`collector.py:607-625, 645`)

Hai vá trong route `POST /api/releases/<file>`:

```python
fn = os.path.basename(path[len("/api/releases/"):])
# latest.json là manifest do POST /api/releases quản — upload đè trực
# tiếp = fleet đọc rác tới khi manifest đúng được đẩy lại.
# GIỮ check ("." , "..") — class [._-] của regex cho ".." qua; bắt đầu
# bằng alnum cũng chặn dotfile.
if not fn or fn in (".", "..") or fn == "latest.json" or \
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", fn):
    return self._json({"err": "tên file lạ"}, 400)
```

(cần `import re` — file hiện chưa import).

Ghi manifest atomic ở cả hai nơi (`/api/releases` POST dòng 645 và
`mirror_loop` dòng 776-778) — pattern tmp + `os.replace`:

```python
tmp = os.path.join(REL_DIR, ".latest.json.tmp")
with open(tmp, "w") as f:
    json.dump(man, f, indent=2)
os.replace(tmp, os.path.join(REL_DIR, "latest.json"))
```

## 1.8 — lost-update race `usage` (`collector.py:88, 341-355`)

`_db_lock` đổi `threading.Lock()` → `threading.RLock()` (một từ —
`q()` tự acquire lock, Lock thường sẽ deadlock khi bọc ngoài). Rồi bọc
read-merge-write trong một `with _db_lock:`:

```python
if counts:
    day = datetime.date.today().isoformat()
    with _db_lock:
        old = q("SELECT counts FROM usage WHERE machine_id=? AND day=?",
                (row["machine_id"], day), one=True)
        merged = dict(json.loads(old[0])) if old else {}
        ...
        q("INSERT INTO usage ... ON CONFLICT ...", write=True)
```

## 1.7 — rate limit sau reverse proxy (`collector.py:385-387, 552-554`)

Config mới `trust_proxy` (bool, mặc định false). Helper trong Handler:

```python
def _client_ip(self):
    if CFG.get("trust_proxy"):
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return self.client_address[0]
```

`rate_ok(self._client_ip(), ...)`. Cấu hình sai (bật khi không có proxy
→ client tự forge XFF né rate limit) là lỗi deploy — comment rõ trong
docstring config.

## S1 — `license_status` tin `lic["org"]` (`collector.py:157`)

Máy khai org nào thì verify bằng secret org đó → license org B hợp lệ
được trên máy org A. Ép org theo ROW máy:

```python
if not isinstance(lic, dict):
    return "missing"
if lic.get("org") != org_name:          # license org khác = invalid
    return "invalid"
sec = (ORGS.get(org_name) or {}).get("license_secret")
```

(Đã verify: `make-license.py` bắt buộc `--org` — license thật luôn có
field `org`; license forged thiếu `org` → `None != org_name` → invalid,
fail-closed đúng hướng. Check strict là an toàn.)

## S2 — `org_pings` không trần (`collector.py:599`)

Mỗi insert kèm prune (rẻ, chạy trong cùng write):

```python
q("INSERT INTO org_pings(org,ts,payload) VALUES(?,?,?)", ...)
q("DELETE FROM org_pings WHERE ts<?",
  (int(time.time()) - 90 * 86400,), write=True)
```

(90 ngày đủ cho "LIMIT 500" đọc; chỉnh nếu muốn giữ lâu hơn.)

## Test

Thêm vào `test-fleet.py` (đã có harness dựng collector thật):

- `POST /api/packs {"org":"../../esc2","pack_version":9}` với vendor key
  → 400, `assert not os.path.exists(<tmp>/esc2)` và không có dir lạ
  ngoài DATA.
- `POST /api/beacon` (và `/api/pair`) body `[1,2,3]` → 400 JSON,
  connection còn sống (request tiếp theo OK).
- `POST /api/beacon` body `{"snapshot":[1],"counts":[1]}` (dict nhưng
  nested sai kiểu) → 200/`{"ok":true}` hoặc 400 — KHÔNG traceback,
  connection sống.
- `POST /api/releases/latest.json` (admin key) → 400; upload
  `foo-1.0.zip` vẫn 200.
- `POST /api/packs {"org":"<org thật>","pack_version":true}` → 400
  (`type(ver) is not int`).
- Beacon hai lần nhanh cùng `counts` → tổng không mất nhánh (khó ép
  race — ít nhất check merge đúng sau 2 beacon).

## Done khi

Hai PoC audit trả 400 có response; `test-fleet.py` PASS gồm case mới;
`latest.json` chỉ đổi qua `POST /api/releases` manifest.
