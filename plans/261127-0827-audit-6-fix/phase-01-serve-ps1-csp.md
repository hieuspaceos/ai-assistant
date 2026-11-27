# Phase 01 — `serve.ps1`: CSP suffixes parity (F1)

## Finding

`serve.py` áp `Content-Security-Policy: sandbox …` cho mọi suffix
render-thành-document (`tools/serve.py:43-44`):

```python
CSP_SUFFIXES = (".html", ".htm", ".svg", ".xml", ".xhtml", ".xht",
                ".shtml", ".mhtml", ".mht")
```

`serve.ps1:86-90` chỉ check `.html`/`.htm`:

```powershell
if (($path.ToLower().StartsWith('/workspace/') -or $path.ToLower().StartsWith('/intro/')) -and
    ($ext -eq '.html' -or $ext -eq '.htm')) {
  $res.Headers.Add('Content-Security-Policy', $csp)
}
```

Mime table ps1 (`tools/serve.ps1:14-24`) phục vụ `.svg` →
`image/svg+xml` — browser render thành document có `<script>` chạy
được. Agent ghi `workspace/` — file `.svg` độc do não (hoặc pack/bank
sau này) sinh, học viên mở trực tiếp → script chạy trong origin
`:8080` → `localStorage.bridge_token` → full bridge API (kể cả
endpoint có gate — respond với Origin localhost hợp lệ). Đây là
**chính xác audit-5 N4** đã vá trên `.py` — regression parity trên
nền chính.

Phạm vi thật (verify lại mime table): `.xml`, `.xhtml`, `.xht`,
`.shtml`, `.mhtml`, `.mht` KHÔNG có trong `$mime` → fallback
`application/octet-stream` → browser tải về chứ không render →
**hôm nay chỉ `.svg` exploit được**. Vá đầy đủ suffixes vẫn đúng:
mime table có thể mở rộng sau, và parity với `CSP_SUFFIXES` giữ 2
file khỏi drift tiếp.

## Vá

Đồng bộ suffix list với `serve.py`. Trong `$handler`:

```powershell
# mọi loại file render thành document chạy được script — parity
# CSP_SUFFIXES của serve.py (audit-5 N4): .svg/.xml có <script>/XSLT.
$cspSuffixes = @('.html','.htm','.svg','.xml','.xhtml','.xht',
                 '.shtml','.mhtml','.mht')
if (($path.ToLower().StartsWith('/workspace/') -or
     $path.ToLower().StartsWith('/intro/')) -and
    ($cspSuffixes -contains $ext)) {
  $res.Headers.Add('Content-Security-Policy', $csp)
}
```

`$csp` giữ nguyên (sandbox allow-scripts
allow-top-navigation-by-user-activation allow-popups allow-modals +
default-src 'self' …) — string này parity với serve.py rồi, chỉ
điều kiện áp lệch.

**Nhớ BOM** khi ghi `serve.ps1` (bài học audit-1: file thiếu BOM
làm PowerShell 5.1 parse lệch → nội dung ghi ra đĩa sai).

## Test

`tools/test-parity.py` hiện chỉ so endpoint — CSP suffix là drift
đúng kiểu nó không bắt được. Thêm check nhẹ vào test-parity (hoặc
test-bridges): extract `CSP_SUFFIXES` tuple từ serve.py và
`$cspSuffixes` từ serve.ps1 bằng regex, so 2 set bằng nhau — FAIL
khi một bên thêm suffix mà bên kia quên.

Test thủ công trên Windows thật (CI test-windows): tạo
`workspace/t/x.svg` chứa `<script>alert(1)</script>`, GET
`http://localhost:8080/workspace/t/x.svg` → header phải có
`Content-Security-Policy: sandbox`.
