# Phase 04 — worker↔collector parity + beacon fail-back (F4, F11)

## F4 — `/api/org-ping` worker đòi master, collector nhận telemetry key

`tools/collector.py:847-852`:

```python
if not (PING_KEY and _eq(self.headers.get("X-Admin-Key"), PING_KEY)):
    return self._json({"err": "thiếu hoặc sai key"}, 401)
```

`worker/src/index.js:1062-1066`:

```js
if (actor.role !== "master")
  return j({ err: "chỉ master" }, 403);
```

`PING_KEY` (telemetry.key trong collector.json) là credential
OUTBOUND-only — thiết kế để collector cty tự host ping rollup lên
vendor mà không cấp master. Worker không có khái niệm key này →
hosted tier (worker) nhận ping từ collector tự host = 403 mãi →
bảng `org_pings` trên hosted trống → dashboard vendor mất rollup.

Cùng gốc: worker `telemetry()` gửi `X-Admin-Key: env.TELEMETRY_KEY`
(index.js:1169-1190) — outbound đã có env, chỉ thiếu inbound.

### Vá

**Lưu ý kiến trúc worker**: `doPost` có admin gate CHUNG ở
`index.js:822-823` (`const actor = await authAdmin(...); if (!actor)
return 401`) — request chỉ mang PING_KEY bị chặn ở đây TRƯỚC KHI tới
handler `/api/org-ping` ở dòng 1062. Vá đúng phải **hoist org-ping
lên trước admin gate** — handler tự xác thực (y py, chỗ auth của nó
không phụ thuộc admin gate):

```js
  // --- trước "const actor = await authAdmin(req, env, orgs)" ---
  if (path === "/api/org-ping") {
    // tự xác thực: PING_KEY (telemetry outbound-only, y
    // collector.py:847) hoặc master — không qua admin gate vì
    // key này không phải admin credential
    const pk = req.headers.get("X-Admin-Key") || "";
    const isPing = env.PING_KEY && eq(pk, env.PING_KEY);
    if (!isPing) {
      const actor0 = await authAdmin(req, env, orgs);
      if (!actor0 || actor0.role !== "master")
        return j({ err: "chỉ master" }, 403);
    }
    const [b, err] = await body(req);
    // … giữ nguyên phần insert/prune hiện có từ dòng 1065 …
  }
```

tức là DI CHUYỂN block `/api/org-ping` hiện có (1062-1080) lên trước
dòng 822, thay điều kiện master bằng `isPing || master`. `eq()` đã có
sẵn. Không tạo role mới — key này chỉ mở đúng endpoint này.

Cách vá sai cần tránh: thêm `env.PING_KEY` check ở dòng 1064 như
sketch trước — request PING_KEY chết ở 401 gate dòng 823, code sửa
không bao giờ chạy tới.

Deploy kèm: `wrangler secret put PING_KEY` trên hosted tier, và ghi
vào `deploy/vendor-infra.md` rằng `telemetry.url` trỏ hosted thì
`telemetry.key` = PING_KEY đó.

### Test

`test-worker.py` thêm case: POST `/api/org-ping` với
`X-Admin-Key: <PING_KEY test>` → 200; key sai → 403; không key → 403.
`.dev.vars` test thêm `PING_KEY=test-ping-key`.

## F11 — máy Windows không-Python: update/pack im lặng không chạy

`beacon.ps1:224-229`:

```powershell
foreach ($t in @("update", "apply-pack")) {
    try {
        Start-Process -WindowStyle Hidden python `
            -ArgumentList "`"$PSScriptRoot\$t.py`"", "`"$WorkDir`"" ...
    } catch {}
}
```

Python là optional trên Windows (`start.bat` chỉ warn cho
ext-bridge). Máy fleet không-Python → `Start-Process` throw → catch
nuốt → inbox đã ghi update/pack nhưng không bao giờ áp — dashboard
thấy máy "sống" version cũ vô hạn, không tín hiệu nào ngược.

### Vá — 2 lớp

**Lớp 1 — không nuốt:** ghi trạng thái vào snapshot beacon để
collector thấy. `beacon.ps1` snapshot đã gom `pack_version`/
`bank_version`; thêm `tool_fail`:

```powershell
foreach ($t in @("update", "apply-pack")) {
    try {
        Start-Process ... (y hiện tại)
    } catch {
        # báo ngược trong snapshot lần beacon sau — collector phải
        # thấy máy "không tự vá được" thay vì tưởng đang update
        $toolFail = $t + ":no-python"
    }
}
```

đưa `$toolFail` vào payload snapshot (field mới, collector bỏ qua
field lạ — backward compatible). Phía collector.py `_beacon` lưu
`snapshot_json` nguyên trạng sẵn — `adm-render` hiện field mới không
cần schema change; hiển thị ở dashboard (badge "cần cài Python").

**Lớp 2 — tương lai (note, không bắt buộc vá):** port `update.py` +
`apply-pack.py` sang .ps1 là việc lớn — frozen `troly.exe` đã tự
check lúc boot nên chỉ máy source-mode-Windows-không-Python bị ảnh
hưởng. Ghi nhận trong SECURITY.md/known-limitations thay vì vá.

### Test

`test-fleet.py` (nếu có path snapshot): gửi snapshot có
`tool_fail` → dashboard data chứa field. Phần ps1 verify tay trên
Windows không-Python: đặt fleet.json, chạy beacon.ps1 một vòng →
snapshot gửi lên có `tool_fail`.
