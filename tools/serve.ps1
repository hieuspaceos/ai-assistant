# serve.ps1 — server web nhỏ cho portal, chạy bằng PowerShell thuần (không cần cài gì)
# Phục vụ folder ai-assistant/ tại http://localhost:8080
# Chặn dotfiles/folder ẩn (.devin, .git...) — secrets nằm đó, không được lộ ra web.

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

# CSP cho .html duoi my-course/intro/ (noi dung agent sinh) - script van
# chay nhung connect-src 'none' chan goi bridge :7682/:7684 va moi fetch/
# XHR/WS. KHONG ap cho /web/ - portal phai goi bridge duoc.
$csp = "default-src 'self'; script-src 'self' 'unsafe-inline' https:; " +
       "style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:; " +
       "font-src 'self' data: https:; media-src 'self' data:; " +
       "connect-src 'none'; form-action 'none'; base-uri 'none'; " +
       "object-src 'none'; frame-src 'self' https:; frame-ancestors 'self'"

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")
$listener.Prefixes.Add("http://127.0.0.1:$port/")
try { $listener.Start() } catch {
  Write-Host "Khong mo duoc cong $port. Co the da co mot server khac dang chay."
  Write-Host "Thu mo http://localhost:$port/web/ trong trinh duyet."
  exit 1
}

Write-Host "Portal dang chay tai http://localhost:$port/web/  (Ctrl+C de dung)"

while ($listener.IsListening) {
  try { $ctx = $listener.GetContext() } catch { break }
  try {
    $req = $ctx.Request; $res = $ctx.Response
    $path = [System.Uri]::UnescapeDataString($req.Url.LocalPath)
    if ($path -eq '/' -or $path -eq '/web' -or $path -eq '/web/') { $path = '/web/index.html' }

    # Chặn dotfile/dot-folder ở bất kỳ cấp nào của đường dẫn
    $segments = $path.TrimStart('/') -split '/'
    $hidden = $segments | Where-Object { $_.StartsWith('.') } | Select-Object -First 1

    $file = Join-Path $root ($path.TrimStart('/') -replace '/', [IO.Path]::DirectorySeparatorChar)
    $resolved = $null
    try { $resolved = (Resolve-Path $file -ErrorAction Stop).Path } catch {}

    if ($resolved -and -not $hidden -and $resolved.StartsWith($rootPrefix) -and (Test-Path $resolved -PathType Leaf)) {
      $bytes = [IO.File]::ReadAllBytes($resolved)
      $ext = [IO.Path]::GetExtension($resolved).ToLower()
      $res.ContentType = $mime[$ext]; if (-not $res.ContentType) { $res.ContentType = 'application/octet-stream' }
      # vendor khong doi theo request -> cache 1h; cho khac giu no-store
      $cc = if ($path.StartsWith('/web/vendor/')) { 'max-age=3600' } else { 'no-store' }
      $res.Headers.Add('Cache-Control', $cc)
      # ToLower BAT BUOC: FS Windows/macOS khong phan biet hoa-thuong nen
      # /MY-COURSE/x.html resolve ra cung file — so case-sensitive se lam
      # content doc thoat CSP qua alias viet hoa.
      if (($path.ToLower().StartsWith('/my-course/') -or $path.ToLower().StartsWith('/intro/')) -and
          ($ext -eq '.html' -or $ext -eq '.htm')) {
        $res.Headers.Add('Content-Security-Policy', $csp)
      }
      # Range cho video bai hoc — Chrome xin Range khi tua; chi single-range,
      # multi-range/chuoi la bo qua -> 200 tron file. HttpListener tu keep-alive.
      $range = [string]$req.Headers['Range']
      if ($range -match '^bytes=(\d*)-(\d*)$') {
        if ($Matches[1]) {
          $s = [long]$Matches[1]
          $e = if ($Matches[2]) { [long]$Matches[2] } else { [long]$bytes.Length - 1 }
        } else {
          # suffix: bytes=-500 = 500 byte cuoi (bytes=- → suf=0 → $s=size → 416)
          $suf = if ($Matches[2]) { [long]$Matches[2] } else { 0 }
          $s = [Math]::Max(0, [long]$bytes.Length - $suf)
          $e = [long]$bytes.Length - 1
        }
        if ($s -le $e -and $s -lt $bytes.Length) {
          $e = [Math]::Min($e, [long]$bytes.Length - 1)
          $res.StatusCode = 206
          $res.Headers.Add('Content-Range', "bytes $s-$e/$($bytes.Length)")
          $res.Headers.Add('Accept-Ranges', 'bytes')
          $res.ContentLength64 = $e - $s + 1
          $res.OutputStream.Write($bytes, [int]$s, [int]($e - $s + 1))
        } else {
          $res.StatusCode = 416
        }
      } else {
        $res.Headers.Add('Accept-Ranges', 'bytes')
        $res.ContentLength64 = $bytes.Length
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
      }
    } else {
      $res.StatusCode = 404
      $msg = [Text.Encoding]::UTF8.GetBytes('Khong tim thay file')
      $res.OutputStream.Write($msg, 0, $msg.Length)
    }
    $res.Close()
  } catch {
    # một request lỗi (client tắt tab giữa chừng...) không được làm chết server
    try { $ctx.Response.Abort() } catch {}
  }
}
