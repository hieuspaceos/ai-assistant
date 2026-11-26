# Phase 03 — `setup-agent-user.ps1`: khóa fleet creds + siết grant loop

## Vá

**F6 — agent đọc được fleet credentials.** `Grant-Item $Root "RX" /T`
cho troly-agent đọc TOÀN cây — kể `.devin\machine.key`,
`.devin\fleet.json` (chứa `beacon_secret` = secret pairing org),
`.devin\license.json`. Agent chỉ cần `bridge.token` để gọi bridge —
đọc được beacon_secret = pair được máy lạ vào fleet / giả máy.

Thêm vào cụm Deny-Full sẵn có (~line 119):

```powershell
foreach ($fp in @($CredFp,
                 (Join-Path $Root ".devin\secrets.local.json"),
                 (Join-Path $Root ".devin\mcp_config.local.json"),
                 (Join-Path $Root ".devin\machine.key"),
                 (Join-Path $Root ".devin\fleet.json"),
                 (Join-Path $Root ".devin\license.json"),
                 (Join-Path $Root ".devin\env-allowlist.json"))) {
    Deny-Full $fp
}
```

(`env-allowlist.json` thêm vào cho sạch — không phải secret nhưng là
config mở lại env-scrub, agent đọc cũng không cần; Deny-Full nó cho
đồng nhất "config mở còng = khoá".)

Cân nhắc thêm `.devin\pack-version`, `.devin\update-pending.json` —
agent đọc được cũng vô hại (metadata version), bỏ qua.

**F11 — grant loop không check sensitive.** Trên macOS
`gen-sandbox._grant_ok` re-check sensitive+divergence ở enforcement
point; bên Windows `setup-agent-user.ps1` grant trần theo
permissions.json. Chain nguy hiểm: pack `permissions_template`
(F10 — không lint trước đây) hoặc file sửa tay → `{"path":"C:\\",
"access":"read-write"}` → icacls M cho agent trên C:\.

Thêm guard trong vòng `foreach ($f in $perm.folders)`:

```powershell
foreach ($f in $perm.folders) {
    $p = [Environment]::ExpandEnvironmentVariables(
             ($f.path -replace "^~", $env:USERPROFILE))
    # bỏ qua grant nguy hiểm — parity ý đồ _grant_ok bên macOS:
    # root ổ / home gốc / path không tồn tại không cấp
    $rp = try { (Resolve-Path $p -ErrorAction Stop).Path } catch { $null }
    if (-not $rp) { Write-Host "  bo qua (khong ton tai): $p"; continue }
    if ($rp -match "^[A-Za-z]:\\?$" -or
        $rp -ieq $env:USERPROFILE -or
        $rp -ieq "$env:WINDIR" -or
        $rp.StartsWith(($env:WINDIR -replace '\\$','') + '\')) {
        Write-Host "  bo qua (nhay cam): $p" -ForegroundColor Yellow; continue
    }
    Grant-Item $p ($(if ($f.access -eq "read-write") { "M" } else { "RX" }))
}
```

Mở rộng hơn: reuse list sensitive Windows trong `path_guard.py`
(browser profiles, `~\AppData\Roaming\1Password`…) — copy subset
Windows-relevant vào ps1 (không import cross-language được). Không
cần đủ hết — blocker chính là drive-root + home + Windows dir +
`$env:ProgramData`/`Program Files` (chứa creds app khác); browser
profile paths là second-order (agent đã RX-đọc từ $Root không tới
đó — vấn đề chỉ khi GRANT mới).

**F6b — `manifest.json` + re-seal sau grant Users:M (phase-04).**
Hai việc liên quan:

- `my-course\manifest.json` hiện KHÔNG nằm trong Deny-Write — agent có
  M trên my-course nên sửa manifest được ngay hôm nay → thêm vào list
  Deny-Write (line 104-112).
- **Bắt buộc khi phase-04 grant `BUILTIN\Users:M` trên `$Dest`**: agent
  cũng thuộc Users → được M toàn cây, gồm `.devin` state
  (`exec-allowlist.json` → tự duyệt exec vì `exec_allowed` chỉ lọc
  metachar; `update-stage` + `update-pending.json` → RCE quyền owner
  lúc boot; `start.bat`, `AGENTS.md`, `collector-web/` chưa deny).
  Re-seal trong script này, ĐẶT TRƯỚC các Deny-Write/Deny-Full lẻ:

```powershell
# agent ∈ BUILTIN\Users — grant M toàn cây của installer cho owner
# cũng trao cho agent → khoá lại: deny W toàn cây (kế thừa cho file
# tạo sau này: update-stage, backup-code-*…), rồi gỡ deny trong đúng
# 3 dir agent được ghi. /remove:d phải chạy TRƯỚC Deny-Write lẻ bên
# dưới vì nó gỡ cả deny sẵn có trong my-course.
icacls $Root /deny "${AgentUser}:(OI)(CI)W" /Q | Out-Null
foreach ($d in @("my-course", ".devin\skills", ".logs")) {
    icacls (Join-Path $Root $d) /remove:d "${AgentUser}" /T /Q | Out-Null
}
```

  Verify trên Windows thật: `/remove:d /T` gỡ được ACE deny kế thừa
  trên cây con; nếu không, fallback `/inheritance:r` + grant lại
  (`troly-agent:M`, `Users:M`, `SYSTEM/Administrators:F` — đừng quên
  giữ admin). Lưu ý `.devin\skills` phải tồn tại trước khi gỡ deny —
  `New-Item -Force` nếu chưa có, vì deny-W trên `.devin` khiến agent
  không tự tạo được (bridge-owner vẫn tạo được, nhưng dir tạo sau sẽ
  kế thừa deny → pre-create ở đây cho chắc).

**Cập nhật SECURITY.md** — ghi rõ: pack `permissions_template` được
lint sensitive ở apply (phase-01) + ACL grant cũng lọc lại lần nữa
ở đây (enforcement-point recheck, đúng pattern audit-3).

## File

| File | Việc |
|---|---|
| `tools/setup-agent-user.ps1` | F6 deny-full creds; F11 sensitive skip trong grant loop; F6b deny-write `manifest.json` + re-seal agent sau Users:M (đặt sau Grant-Item, trước Deny-Write lẻ) (+BOM khi ghi lại) |

## Verify

- CI `test-windows` chạy sẵn script này — sau sửa vẫn pass
  (test-agent-spawn check deny-read secret / deny-write tools /
  write my-course).
- Thêm vào `test-agent-spawn.ps1`: tạo file `.devin\machine.key` giả
  → spawn `type` → không đọc được nội dung.
- **Verify re-seal** (cần khi phase-04 áp): grant Users:M giả lập trên
  cây test → spawn agent → `echo > .devin\exec-allowlist.json` bị
  Access Denied; `echo > my-course\x.txt` vẫn ghi được; `echo >
  my-course\config.json` vẫn denied.
