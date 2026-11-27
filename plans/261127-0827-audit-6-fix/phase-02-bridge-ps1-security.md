# Phase 02 — `chat-bridge.ps1`: secrets wipe bug + parity + junction + emit-event (F2, F3, F8)

## F2 — `/api/secrets` ps1: wipe làm mất creds NGAY CẢ first save

Audit lại sau khi viết plan v1: bug nghiêm trọng hơn mô tả ban đầu.

Python (`chat-bridge.py:2407-2420`) coi `url`, `host`, `endpoint`
đều là "địa chỉ site" — đổi một trong ba → thay creds bằng TOÀN BỘ
fields vừa submit (`creds[app] = clean` — giữ cả user/password mới
nhập cùng lần đó).

PS1 (`chat-bridge.ps1:1547-1570`) có HAI vấn đề:

1. **Check lệch**: chỉ check `url`, không check `host`/`endpoint`
   như py.
2. **Bug mất dữ liệu (nghiêm trọng hơn)**: trong gate-apply, nhánh
   wipe gán `$entry = @{ url = $cleanFields.url }` — vứt TOÀN BỘ
   field khác kể cả field vừa submit cùng lần (`user`,
   `app_password`…). Mà `$oldUrl = $null` khi chưa có creds →
   `$cleanFields.url -ne $null` → **first save với url cũng rơi
   vào nhánh wipe** → secrets.local.json chỉ còn `{"url": ...}`,
   mất user/password.

Portal (`web/app.js:1139-1148`) gom TẤT CẢ input vào một POST —
form WP (url + user + app_password) submit một lần. Hệ quả: trên
Windows, học viên nhập đủ 3 ô → approve gate → file chỉ lưu url →
probe `check-connection` sau đó fail mãi → "không kết nối được"
không rõ lý do. Đây là bug functional sống trên nền chính, không
phải parity lý thuyết.

### Vá

Mirror đúng logic py — cả ở điểm tính `$wipe` (title card) lẫn trong
gate-apply:

```powershell
$endpointKeys = @('url','host','endpoint')
$wipe = $false
foreach ($k in $endpointKeys) {
    if ($cleanFields.ContainsKey($k) -and
        $cleanFields[$k] -ne [string]$creds0.$appId.$k) { $wipe = $true }
}
```

và trong gate — wipe phải giữ TOÀN BỘ clean fields vừa submit
(py: `creds[app] = clean`), không chỉ giữ url:

```powershell
$wiped = $false
foreach ($k in $endpointKeys) {
    if ($cleanFields.ContainsKey($k) -and
        $cleanFields[$k] -ne $old.$k) { $wiped = $true; break }
}
if ($wiped) { $entry = $cleanFields.Clone() }
```

Lưu ý `$entry` đã được build từ old-props + cleanFields ở trên — khi
`$wiped` ta thay bằng clone của cleanFields (bỏ mọi field cũ không
có trong submit). `$cleanFields` là hashtable nên `.Clone()` nông
đủ (value đều string).

## F3 — `Test-SensitivePath` không resolve junction

`chat-bridge.ps1:227` dùng `[IO.Path]::GetFullPath` — lexical, không
resolve reparse point. `path_guard.path_sensitive` dùng `realpath`.
Junction có sẵn trong folder được grant trỏ vào folder nhạy cảm →
lọt check. LOW (junction phải do ai đó tạo trước — quyền tạo
junction = quyền admin/developer mode, tức kẻ có thể tự làm đã
không cần lỗ hổng này), nhưng vá rẻ:

Trong `Test-SensitivePath` + `Test-RwGrantOk`, sau `GetFullPath`
thêm resolve target nếu path tồn tại:

```powershell
try {
    $item = Get-Item $rpl -ErrorAction Stop
    if ($item.LinkTarget) { $rpl = [IO.Path]::GetFullPath($item.LinkTarget).ToLower() }
} catch {}
```

`Get-Item.LinkTarget` resolve junction/symlink; path chưa tồn tại
(mới xin grant) thì giữ lexical — hành vi py tương đương
(`os.path.realpath` trả path khi không resolve được).

## F8 — `/api/emit-event`: `pack_applied`/`update_applied` không có caller nào

`chat-bridge.py:2649` whitelist gồm `pack_applied` + `update_applied`
— đây là tín hiệu admin dùng để biết rollout xong, không phải
"đếm thống kê" như comment. Agent cầm token emit giả → dashboard
báo rollout xong cho máy chưa update (độc khi ghép F11 — máy
Windows không-Python không tự update + có thể giả tín hiệu).

**Verify lại caller** (sửa sau khi viết plan v1): grep toàn repo —
`update.py`, `apply-pack.py`, `beacon.py`, `launcher.py`, `ext-bridge`
KHÔNG ai emit 2 type này. Chỉ `ext-bridge.py:120` gọi emit-event
với `inj_suspect`. Tức 2 entry whitelist này là mặt tấn công chết —
không có legitimate caller nào bị ảnh hưởng nếu xoá.

### Vá (đơn giản hơn plan v1 — cả .py lẫn .ps1)

XOÁ `pack_applied`/`update_applied` khỏi whitelist. Không cần cơ
chế internal-token/secret thứ 2 — không có caller nào để giữ
tương thích:

```python
# chat-bridge.py:2649 — whitelist chỉ còn 3 type có caller thật
if t not in ("inj_suspect", "perm:auto", "env_scrub"):
    self._json({"err": "event type không được phép"}, 400); return
```

```powershell
# chat-bridge.ps1:1665 — y hệt
if ($t -in @("inj_suspect","perm:auto","env_scrub")) { ... }
```

Nếu sau này update.py/apply-pack.py cần báo rollout lên dashboard:
đi kênh beacon (đã có trusted channel qua collector) hoặc thêm
internal-token lúc đó — không phòng thủ trước cho caller chưa có.

Cập nhật `test-content-guard.py:50-52` (đang assert whitelist gồm
2 type này) theo whitelist mới. `.ps1` nhớ BOM.

## Test

- `test-bridges.py`: thêm case secrets — (a) POST fields
  `{url, user, app_password}` lần đầu → file phải có ĐỦ 3 field
  (bắt đúng bug first-save mất creds); (b) POST `{host: "https://evil"}`
  với creds cũ có url khác → sau approve, file chứa đúng clean
  fields, không merge user/password cũ. Chạy được trên .py ngay;
  .ps1 verify tay trên Windows hoặc CI test-windows.
- `test-parity.py`: extract endpointKeys list từ cả hai file so bằng.
- `test-gates.py` / `test-content-guard.py`: emit-event
  `update_applied` → reject (400) kể cả khi có bridge.token.
