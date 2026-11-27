# serve.ps1 — server web nhỏ cho portal, chạy bằng PowerShell thuần (không cần cài gì)
# Phục vụ folder ai-assistant/ tại http://localhost:8080
# Chặn dotfiles/folder ẩn (.devin, .git...) — secrets nằm đó, không được lộ ra web.
#
# Runspace pool 8 luồng + stream file từng chunk: bản cũ GetContext() đơn
# luồng serialize mọi request (portal ~20 assets tải tuần tự) và
# ReadAllBytes đọc FULL file vào RAM kể cả khi client chỉ xin Range —
# tua video 100MB tốn 100MB RAM mỗi lần.

$root = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path   # thư mục cha của tools/ = ai-assistant/
$rootPrefix = $root + [IO.Path]::DirectorySeparatorChar
$port = 8080

$mime = @{
  '.html'='text/html; charset=utf-8'; '.htm'='text/html; charset=utf-8'
  '.css'='text/css; charset=utf-8';   '.js'='application/javascript; charset=utf-8'
  '.json'='application/json; charset=utf-8'; '.md'='text/plain; charset=utf-8'
  '.png'='image/png'; '.jpg'='image/jpeg'; '.jpeg'='image/jpeg'
  '.gif'='image/gif'; '.svg'='image/svg+xml'; '.webp'='image/webp'
  '.mp4'='video/mp4'; '.mp3'='audio/mpeg'; '.wav'='audio/wav'
  '.pdf'='application/pdf'; '.zip'='application/zip'; '.csv'='text/csv; charset=utf-8'
  '.txt'='text/plain; charset=utf-8'; '.ico'='image/x-icon'
  '.woff'='font/woff'; '.woff2'='font/woff2'; '.ttf'='font/ttf'
}

# CSP cho .html duoi workspace/intro/ (noi dung agent sinh). Hai lop:
# sandbox -> OPAQUE ORIGIN (khong doc duoc localStorage/iframe portal/
# service worker; KHONG them allow-same-origin) + connect-src 'none' chan
# moi fetch/XHR/WS. KHONG ap cho /web/ - portal phai goi bridge duoc.
# Top-nav chi khi CO user activation (audit-5 F14).
$csp = "sandbox allow-scripts allow-top-navigation-by-user-activation " +
       "allow-popups allow-modals; " +
       "default-src 'self'; script-src 'self' 'unsafe-inline' https:; " +
       "style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:; " +
       "font-src 'self' data: https:; media-src 'self' data:; " +
       "connect-src 'none'; form-action 'none'; base-uri 'none'; " +
       "object-src 'none'; frame-src 'self' https:; frame-ancestors 'self'"

# Moi loai file render thanh document chay duoc script — parity CSP_SUFFIXES
# cua serve.py (audit-5 N4): .svg/.xml co <script>/XSLT chay trong origin
# :8080 doc duoc localStorage.bridge_token.
$cspSuffixes = @('.html','.htm','.svg','.xml','.xhtml','.xht',
                 '.shtml','.mhtml','.mht')

# JSON điều khiển quyền/cấu hình + persona bot: đọc qua API có token, không
# để GET trần trên :8080 (parity serve.py). So hoa-thường bắt buộc vì FS
# Windows không phân biệt case — /MY-COURSE/PERMISSIONS.JSON cùng một file.
$blockedJson = @('permissions.json', 'connections.json', 'config.json', 'bots.json', 'bot.md')

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")
$listener.Prefixes.Add("http://127.0.0.1:$port/")
try { $listener.Start() } catch {
  Write-Host "Khong mo duoc cong $port. Co the da co mot server khac dang chay."
  Write-Host "Thu mo http://localhost:$port/web/ trong trinh duyet."
  exit 1
}

Write-Host "Portal dang chay tai http://localhost:$port/web/  (Ctrl+C de dung)"

$handler = {
  param($ctx, $root, $rootPrefix, $mime, $csp, $cspSuffixes, $blockedJson)
  try {
    $req = $ctx.Request; $res = $ctx.Response
    $path = [System.Uri]::UnescapeDataString($req.Url.LocalPath)
    if ($path -eq '/' -or $path -eq '/web' -or $path -eq '/web/') { $path = '/web/index.html' }

    # Chặn dotfile/dot-folder ở bất kỳ cấp nào của đường dẫn
    $segments = $path.TrimStart('/') -split '/'
    $hidden = $segments | Where-Object { $_.StartsWith('.') } | Select-Object -First 1
    # JSON điều khiển — blocklist case-insensitive (xem $blockedJson)
    $low = @($segments | ForEach-Object { $_.ToLower() })
    $blocked = (($low.Count -eq 2 -and $low[0] -eq 'workspace' -and $blockedJson -contains $low[1]) -or
        ($low.Count -eq 1 -and $low[0] -eq 'brain.json'))

    $file = Join-Path $root ($path.TrimStart('/') -replace '/', [IO.Path]::DirectorySeparatorChar)
    $resolved = $null
    try { $resolved = (Resolve-Path $file -ErrorAction Stop).Path } catch {}

    if ($resolved -and -not $hidden -and -not $blocked -and
        $resolved.StartsWith($rootPrefix) -and (Test-Path $resolved -PathType Leaf)) {
      $ext = [IO.Path]::GetExtension($resolved).ToLower()
      $res.ContentType = $mime[$ext]; if (-not $res.ContentType) { $res.ContentType = 'application/octet-stream' }
      # vendor khong doi theo request -> cache 1h; cho khac giu no-store
      $cc = if ($path.StartsWith('/web/vendor/')) { 'max-age=3600' } else { 'no-store' }
      $res.Headers.Add('Cache-Control', $cc)
      $res.Headers.Add('X-Content-Type-Options', 'nosniff')
      # trang lạ iframe portal → clickjacking; SAMEORIGIN vẫn cho iframe
      # nội bộ (chat-frame, term-frame, clone-view) — parity serve.py
      $res.Headers.Add('X-Frame-Options', 'SAMEORIGIN')
      # ToLower BAT BUOC: FS Windows/macOS khong phan biet hoa-thuong nen
      # /MY-COURSE/x.html resolve ra cung file — so case-sensitive se lam
      # content doc thoat CSP qua alias viet hoa.
      if (($path.ToLower().StartsWith('/workspace/') -or $path.ToLower().StartsWith('/intro/')) -and
          ($cspSuffixes -contains $ext)) {
        $res.Headers.Add('Content-Security-Policy', $csp)
      }

      # Stream thay vi ReadAllBytes — request Range chỉ đọc đúng đoạn cần
      $fs = [IO.File]::Open($resolved, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
      $size = $fs.Length
      $s = 0; $e = $size - 1; $status = 200
      $range = [string]$req.Headers['Range']
      if ($range -match '^bytes=(\d*)-(\d*)$') {
        if ($Matches[1]) {
          $s = [long]$Matches[1]
          if ($Matches[2]) { $e = [Math]::Min([long]$Matches[2], $size - 1) }
        } else {
          # suffix: bytes=-500 = 500 byte cuoi (bytes=- → suf=0 → $s=size → 416)
          $suf = if ($Matches[2]) { [long]$Matches[2] } else { 0 }
          $s = [Math]::Max(0, $size - $suf)
        }
        if ($s -le $e -and $s -lt $size) {
          $status = 206
          $res.Headers.Add('Content-Range', "bytes $s-$e/$size")
        } else {
          $status = 416
        }
      }
      $res.Headers.Add('Accept-Ranges', 'bytes')
      if ($status -ne 416) {
        $res.StatusCode = $status
        $count = $e - $s + 1
        $res.ContentLength64 = $count
        if ($s -gt 0) { [void]$fs.Seek($s, [IO.SeekOrigin]::Begin) }
        $buf = New-Object byte[] 262144
        while ($count -gt 0) {
          $n = $fs.Read($buf, 0, [int][Math]::Min($buf.Length, $count))
          if ($n -le 0) { break }
          $res.OutputStream.Write($buf, 0, $n)
          $count -= $n
        }
      } else {
        $res.StatusCode = 416
      }
      $fs.Close()
    } else {
      # Trang loi em — parity send_error cua serve.py (ux-polish ph-07)
      $res.StatusCode = 404
      $page = "<!DOCTYPE html><html lang=vi><meta charset=utf-8>" +
        "<meta name=viewport content='width=device-width,initial-scale=1'>" +
        "<title>Um…</title><body style='font-family:system-ui,sans-serif;" +
        "max-width:34em;margin:4em auto;padding:0 1em;line-height:1.7;color:#333'>" +
        "<h2 style='font-weight:500'>Um, co gi do chua on</h2>" +
        "<p>Khong thay thu ban mo — co the no chua duoc tao. " +
        "Quay lai trang chinh roi chon trong danh sach nhe.</p>" +
        "<p><a href='/web/'>← Ve trang chinh</a></p></body></html>"
      $msg = [Text.Encoding]::UTF8.GetBytes($page)
      $res.ContentType = 'text/html; charset=utf-8'
      $res.ContentLength64 = $msg.Length
      $res.OutputStream.Write($msg, 0, $msg.Length)
    }
    $res.Close()
  } catch {
    # một request lỗi (client tắt tab giữa chừng...) không được làm chết server
    try { $ctx.Response.Abort() } catch {}
  }
}

$pool = [runspacefactory]::CreateRunspacePool(1, 8)
$pool.Open()
$jobs = New-Object System.Collections.ArrayList

while ($listener.IsListening) {
  try { $ctx = $listener.GetContextAsync().GetAwaiter().GetResult() } catch { break }
  try {
    $ps = [powershell]::Create()
    $ps.RunspacePool = $pool
    [void]$ps.AddScript($handler).AddArgument($ctx).AddArgument($root).AddArgument($rootPrefix).AddArgument($mime).AddArgument($csp).AddArgument($cspSuffixes).AddArgument($blockedJson)
    [void]$jobs.Add(@{ ps = $ps; h = $ps.BeginInvoke() })
    # dọn job đã xong để $jobs không phình theo số request
    for ($i = $jobs.Count - 1; $i -ge 0; $i--) {
      if ($jobs[$i].h.IsCompleted) {
        try { $jobs[$i].ps.EndInvoke($jobs[$i].h) } catch {}
        $jobs[$i].ps.Dispose()
        $jobs.RemoveAt($i)
      }
    }
  } catch {
    try { $ctx.Response.Abort() } catch {}
  }
}
