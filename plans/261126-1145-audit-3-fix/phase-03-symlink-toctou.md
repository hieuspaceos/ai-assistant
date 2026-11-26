# Phase 03 — CAO-2: grant folder → symlink swap → sandbox cấp quyền đích symlink

## Vá

**TOCTOU trên grant folder.** `/api/permissions` validate một lần lúc
request (`isdir` + `path_sensitive` + `rw_grant_ok`, ~1745–1757);
`_apply` (~1761–1771) chỉ ghi raw path vào `permissions.json`;
`gen-sandbox._emit_paths` resolve **realpath mỗi lần build profile**
(mỗi `spawn_brain`). Chuỗi:

1. Agent `mkdir my-course/x` → grant `read-write` — path trong vùng
   writable sẵn nên `rw_grant_ok` cho qua, card trông vô hại → duyệt.
2. Bất kỳ lúc nào sau đó: `rmdir x && ln -s ~/Library/LaunchAgents x`.
3. Spawn kế → profile emit `(allow file-read* file-write* (subpath
   "~/Library/LaunchAgents"))` → drop plist = code chạy NGOÀI Seatbelt
   lúc login. Symlink `~/.ssh` → đọc private key.

Cửa sổ tấn công = mọi spawn tương lai (không chỉ lúc chờ bấm) → vá ở
request-time không đủ, phải vá **tại enforcement point**.

## Lớp 1 — enforcement: `gen-sandbox.build_profile` (fix chính)

Trong vòng đọc `permissions.json` (~168–177), mỗi folder trước khi add
vào `rw`/`ro` phải qua **hai** check (check sensitive VÀ check symlink
divergence — thiếu cái nào cũng còn lỗ):

```python
from path_guard import path_sensitive, rw_grant_ok   # phase-01

def _grant_ok(p, access, cwd):
    """Grant chỉ emit khi path còn đúng như lúc học viên duyệt."""
    if path_sensitive(p):          # realpath bên trong — đích symlink
        return False               # vào sensitive đã bị chặn ở đây luôn
    # Divergence rule: realpath khác normpath = có symlink component.
    # Cho qua duy nhất canonicalization /private của macOS (/tmp,/var,
    # /etc → /private/*). So .lower(): APFS không phân biệt hoa-thường,
    # grant gõ "~/documents" không bị drop oan.
    np = os.path.normpath(os.path.abspath(os.path.expanduser(p)))
    rp = os.path.realpath(p)
    if rp.lower() != np.lower() and rp.lower() != ("/private" + np).lower():
        return False               # symlink đổi đích — kể cả đích KHÔNG
                                   # sensitive (~/Documents…) vẫn chặn
    if access == "read-write" and not rw_grant_ok(p, cwd):
        return False
    return True

for f in perm.get("folders", []):
    p = os.path.abspath(os.path.expanduser(str(f.get("path", ""))))
    if len(p) < 2:
        continue
    if not _grant_ok(p, str(f.get("access", "")), cwd):
        continue                   # bỏ grant — log/warn nếu muốn debug
    (rw if f.get("access") == "read-write" else ro).add(p)
```

Vì sao cần CẢ divergence rule: `path_sensitive` chỉ chặn đích thuộc
list. `ln -s ~/Documents x` — đích KHÔNG sensitive, `rw_grant_ok` cũng
cho qua (ngoài project = "bình thường") → chỉ có divergence rule chặn
được escalation "card hiện my-course/x nhưng sandbox được ~/Documents".
Trade-off đã cân: user cố ý symlink folder thật (Documents → ổ ngoài)
sẽ bị drop — hiếm, an toàn hơn, và `_apply` báo err thấy được.

Vì sao đủ: `_emit_paths` emit cả raw lẫn realpath — Seatbelt so
canonical path; grant divergent/sensitive bị bỏ **kể cả khi
permissions.json bị sửa tay**. Đây là lớp không phụ thuộc bridge —
file mồ côi/grant cũ/symlink swap đều bị chặn tại điểm phát quyền.

Edge đã nghĩ: `/tmp/x` → realpath `/private/tmp/x` → qua được nhờ nhánh
`/private` (canonicalization hợp lệ, không phải swap). Symlink nằm giữa
path (`my-course/link/inner`) cũng bị bắt vì realpath cả path khác
normpath.

## Lớp 2 — apply-time: `_apply` trong `/api/permissions`

`permissions.json` giữ raw path — `realpath` ghi lúc apply không giúp
gì sau swap, nhưng re-validate lúc apply vẫn đáng làm (bắt đúng thời
điểm "quyết định có hiệu lực", báo lỗi thấy được thay vì grant mồ côi
bị profile-build bỏ lặng lẽ):

```python
def _apply(paths=paths, access=access, note=note):
    ok, refused = [], []
    for p in paths:
        # path_sensitive đã realpath bên trong — KHÔNG gọi thêm lần
        # nữa trên realpath (thừa, không thêm gì)
        if (not os.path.isdir(p) or path_sensitive(p)
                or (access == "read-write" and not rw_grant_ok(p, CWD))):
            refused.append(p)
        else:
            ok.append(p)
    if ok:
        q = load_json(PERM_FP, {"folders": []})
        q["folders"] = [f for f in (q.get("folders") or [])
                        if os.path.expanduser(str(f.get("path", "")))
                        not in ok]
        for p in ok:
            q["folders"].append({"path": p, "access": access,
                                 "note": note})
        save_json(PERM_FP, q)
        gen_sandbox_profile()
    if refused:
        broadcast({"t": "err", "msg": "bỏ qua folder không còn hợp lệ: "
                   + ", ".join(refused)[:160]})
```

`isdir` lúc apply cũng follow symlink → symlink-tới-dir vẫn qua được
isdir nhưng bị `path_sensitive(realpath)` chặn nếu đích nhạy cảm; đích
vô hại (symlink trong my-course → /tmp) thì grant vào đích vô hại —
chấp nhận.

## Không làm

- **Không ghi realpath vào permissions.json** — raw path cần giữ cho UI
  hiển thị tên folder học viên thấy lúc duyệt; enforcement ở
  build_profile đã đủ chặn đích độc.
- **Windows**: không có Seatbelt → CAO-2 là lỗi macOS-only; ps1 không
  build profile. Ghi nhận.

## Test

- E2E macOS: grant `my-course/x` qua API → duyệt card → `rmdir x &&
  ln -s ~/Library/LaunchAgents x` → `gen_sandbox_profile()` → profile
  KHÔNG chứa `LaunchAgents`; `sandbox-exec -f .devin/agent.sb touch
  ~/Library/LaunchAgents/probe.plist` → Operation not permitted.
- Tương tự symlink `~/.ssh` → `sandbox-exec … cat ~/.ssh/id_rsa` → deny.
- **Đích KHÔNG sensitive**: `ln -s ~/Documents x` → profile KHÔNG chứa
  Documents (divergence rule bắt, không phải sensitive check).
- Ngoại lệ hợp lệ: grant `/tmp/x` (dir thật) → profile CÓ
  `/private/tmp/x` — không bị divergence rule drop oan.
- Request grant → swap symlink **trước khi bấm** → bấm Đồng ý → event
  `err` "bỏ qua folder không còn hợp lệ", permissions.json không có
  path đó.
- Grant hợp lệ bình thường (~/Documents/thu-muc) vẫn emit đúng — không
  over-block.

## Done khi

Không chuỗi nào — swap trước approve, swap sau approve, sửa tay
permissions.json — làm profile chứa subpath dưới `_SENSITIVE_DIRS`;
test trên PASS.
