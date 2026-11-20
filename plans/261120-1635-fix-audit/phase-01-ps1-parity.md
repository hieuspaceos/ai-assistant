# Phase 1 — Port `/api/save-page` + `extVersion` vào chat-bridge.ps1

## Mục tiêu

Windows là nền tảng chính nhưng `chat-bridge.ps1` thiếu `POST /api/save-page`
→ `web/clone-view.html` bấm "Lưu lại trang" → 404. Port y chang logic
`.py` (sandbox `my-course/`, `.bak`, UTF-8 **không BOM**), và thêm
`extVersion` vào `/api/health` cho khớp bản `.py` đang commit.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/chat-bridge.ps1` | modify | thêm nhánh `POST /api/save-page` + `extVersion` trong health |
| `docs/api-reference.md` | check | đảm bảo save-page đã được ghi (ghi nếu thiếu) |

## Chi tiết

### 1a. Trước khi sửa — GIỮ UTF-8 BOM của file `.ps1`

`chat-bridge.ps1` hiện là UTF-8 **with BOM** (`ef bb bf`) — PowerShell
5.1 nhờ BOM mới parse đúng chuỗi tiếng Việt trong file. Editor/tool nào
ghi lại không BOM sẽ làm mojibake mọi thông báo lỗi trên Windows.
Kiểm sau khi sửa: `head -c 3 tools/chat-bridge.ps1 | xxd` = `efbb bf`.

### 1b. `POST /api/save-page` — chèn sau nhánh `delete-lesson`

Bám sát `chat-bridge.py:583-605`. PowerShell tương đương:

```powershell
elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/save-page") {
    $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
    $body = $reader.ReadToEnd() | ConvertFrom-Json
    $rel = ([string]$body.file).Trim().TrimStart("/")
    $html = [string]$body.html
    $course = (Resolve-Path (Join-Path $WorkDir "my-course")).Path
    $target = [IO.Path]::GetFullPath((Join-Path $WorkDir $rel))
    if (-not $rel.StartsWith("my-course/") -or $rel.Contains("..") -or
        -not $target.StartsWith($course + [IO.Path]::DirectorySeparatorChar) -or
        $target -notmatch '\.html?$') {
        Send-Json $ctx @{ err = "chỉ lưu file .html trong my-course/" } 400
    } elseif (-not $html) {
        Send-Json $ctx @{ err = "trang trống" } 400
    } else {
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
        # backup trước khi ghi đè — học viên sửa hỏng còn về được
        if (Test-Path $target) { Copy-Item $target "$target.bak" -Force }
        # UTF-8 KHÔNG BOM — Set-Content mặc định ghi BOM, viewer đọc file
        # trực tiếp sẽ thấy ký tự lạ đầu trang
        [IO.File]::WriteAllText($target, $html, (New-Object System.Text.UTF8Encoding $false))
        Send-Json $ctx @{ ok = $true }
    }
}
```

Lưu ý khác biệt `.py`: `realpath` giải symlink — PowerShell 5.1 không có
`realpath`; `GetFullPath` chuẩn hoá `..`/`.` là đủ cho threat model
(symlink attack trên máy học viên không nằm trong mô hình).

`Resolve-Path` trên `my-course` throw nếu folder chưa tồn tại
(`$ErrorActionPreference = "Stop"` đầu file) — my-course được seed sẵn
nên không xảy ra trong thực tế; giữ pattern giống nhánh `delete-lesson`,
không thêm guard riêng.

### 1c. Body size cap

`.py` giới hạn `save-page` 8MB, mọi POST khác 1MB (`cl > cap → 413`).
`ps1` đọc `InputStream` trực tiếp không có cap — thêm:

```powershell
$cap = if ($path -eq "/api/save-page") { 8000000 } else { 1000000 }
if ($ctx.Request.ContentLength64 -gt $cap) {
    Send-Json $ctx @{ err = "body quá lớn" } 413; continue
}
```

đặt ngay sau auth check, trước mọi đọc body POST.

### 1d. `extVersion` trong `/api/health`

Đọc `extension/manifest.json` → trường `version` (helper
`Get-ExtVersion`, bắt lỗi trả `$null`), thêm vào payload health — khớp
`ext_expected_version()` trong `.py` (đang nằm trong diff chưa commit).

### 1e. Diff endpoint toàn diện

`grep -o '"/api/[a-z-]*"'` trên cả 2 file, diff — xác nhận sau phase này
tập endpoint bằng nhau (phase 3 gắn test này để không trôi nữa).

## Acceptance

- `head -c 3 tools/chat-bridge.ps1 | xxd` = `efbb bf` sau khi sửa.
- `pwsh tools/chat-bridge.ps1` (hoặc máy Windows) → POST save-page file
  `my-course/test.html` → 200, file ghi đúng tiếng Việt không BOM;
  lần 2 → `.bak` xuất hiện.
- `{"file":"../evil.html"}` → 400; `{"file":"my-course/x.txt"}` → 400.
- `GET /api/health` có trường `extVersion`.
- Diff endpoint `.py` vs `.ps1` = rỗng.

## Rủi ro

- BOM (R1 trong plan) — dùng `WriteAllText` UTF8Encoding($false), không
  `Set-Content`.
- Không có máy Windows để chạy thật → kiểm cú pháp bằng `pwsh` trên macOS
  (`brew install powershell` nếu cần), verify hành vi thật ở phase 5.
