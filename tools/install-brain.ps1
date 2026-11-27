# install-brain.ps1 — cài "não" bằng một nút bấm trên Windows.
# Bản mirror của install-brain.py (máy học viên Windows thường KHÔNG có
# Python nên không spawn được script .py). Giữ nguyên contract file trạng
# thái .devin\install-brain.json để chat-bridge.ps1 /api/install-brain
# poll được — sống qua cả restart bridge.
#
# Chạy: install-brain.ps1 <brain-id> <DATA>
#   gemini — tải Node portable về DATA\node (không cần admin/winget)
#            rồi npm install -g @google/gemini-cli
#   devin  — installer chính thức (irm | iex), cài về ~\.local\bin
#
# Cài xong não vẫn cần ĐĂNG NHẬP (OAuth) — onboarding mở terminal qua
# POST /api/install-brain {"login":1}.
param(
    [Parameter(Mandatory=$true)][string]$Brain,
    [Parameter(Mandatory=$true)][string]$Data
)
$ErrorActionPreference = "Stop"
$NodeVer = "v26.13.1"
$NodeBase = "https://nodejs.org/dist/$NodeVer/"
# chỉ hỗ trợ Windows x64 — mirror NODE_DIST[("Windows","AMD64")] bên .py
$NodeZip = "node-$NodeVer-win-x64.zip"
$NodeSha = "e2edda75bfb089654705cf65a13b58933bfd5f57148e8ebda916f58a2474f1f7"
$Data = [IO.Path]::GetFullPath($Data)
$StateFp = Join-Path $Data ".devin\install-brain.json"
$script:Log = New-Object System.Collections.ArrayList

function Write-State($st, $step="") {
    New-Item -ItemType Directory -Force -Path (Split-Path $StateFp) | Out-Null
    $lg = @($script:Log)
    if ($lg.Count -gt 30) { $lg = $lg[($lg.Count-30)..($lg.Count-1)] }
    $o = [ordered]@{ id = $Brain; state = $st; step = $step; log = $lg;
                     ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
    [IO.File]::WriteAllText($StateFp, ($o | ConvertTo-Json -Depth 6 -Compress),
                          [Text.UTF8Encoding]::new($false))
}
function Say($msg, $step="") {
    [void]$script:Log.Add([string]$msg)
    Write-Output (@{ step = $step; msg = [string]$msg } | ConvertTo-Json -Compress)
    Write-State "running" $step
}
function Fail($msg) {
    Say ("!! " + $msg) "error"
    Write-State "error"
    exit 1
}

# Chỗ não cài lén nằm — bridge prepend cùng list này vào PATH (parity
# bin_dirs() bên .py: node\bin cho layout unix, node\ cho zip Windows).
function Get-BinDirs {
    @((Join-Path $Data "node\bin"), (Join-Path $Data "node"),
      (Join-Path $env:USERPROFILE ".local\bin")) |
        Where-Object { Test-Path $_ -PathType Container }
}
function Add-BinDirs {
    foreach ($d in (Get-BinDirs)) {
        if (($env:PATH -split ';') -notcontains $d) { $env:PATH = "$d;$env:PATH" }
    }
}
function Find-Cmd($c) {
    foreach ($d in (Get-BinDirs)) {
        foreach ($ext in @("", ".exe", ".cmd", ".bat")) {
            $p = Join-Path $d ($c + $ext)
            if (Test-Path $p) { return $p }
        }
    }
    $g = Get-Command $c -ErrorAction SilentlyContinue
    if ($g) { return $g.Source }
    return $null
}

function Run($cmdline, $step) {
    # Chạy lệnh cài qua cmd /c (npm/devin là .cmd/.ps1 installer), stream
    # từng dòng output về state file y như bản .py. stderr gộp vào stdout
    # ở tầng cmd (2>&1) — tránh buffer stderr đầy khóa chết process.
    Say ("`$ " + $cmdline) $step
    Add-BinDirs
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = "cmd.exe"
    $pinfo.Arguments = "/c " + $cmdline + " 2>&1"
    $pinfo.WorkingDirectory = $Data
    $pinfo.UseShellExecute = $false
    $pinfo.RedirectStandardOutput = $true
    $pinfo.EnvironmentVariables["PATH"] = $env:PATH
    $p = [System.Diagnostics.Process]::Start($pinfo)
    while ($true) {
        $line = $p.StandardOutput.ReadLine()
        if ($null -eq $line) { break }
        $line = $line.Trim()
        if ($line) {
            if ($line.Length -gt 200) { $line = $line.Substring(0, 200) }
            Say ("   " + $line) $step
        }
    }
    $p.WaitForExit()
    if ($p.ExitCode -ne 0) {
        Fail ("lệnh chạy sai (code " + $p.ExitCode + ") — xem log phía trên")
    }
}

function Ensure-Node {
    # node+npm sẵn trên PATH (kể cả bundle cũ) → bỏ qua; không thì tải
    # bản portable về DATA\node — không cần admin/winget (parity .py,
    # kèm kiểm sha256 cứng).
    if ((Find-Cmd "node") -and (Find-Cmd "npm")) { Say "node đã có sẵn" "node"; return }
    Say ("tải " + $NodeBase + $NodeZip) "node"
    $tmpd = Join-Path ([IO.Path]::GetTempPath()) ("troly-node-" + [guid]::NewGuid().ToString("N").Substring(0,8))
    New-Item -ItemType Directory -Force -Path $tmpd | Out-Null
    try {
        $arc = Join-Path $tmpd $NodeZip
        Invoke-WebRequest -Uri ($NodeBase + $NodeZip) -OutFile $arc -UseBasicParsing
        if ((Get-FileHash $arc -Algorithm SHA256).Hash.ToLower() -ne $NodeSha) {
            Fail "file tải lệch chữ ký sha256 — hủy cài"
        }
        Say "giải nén node…" "node"
        $exd = Join-Path $tmpd "x"
        Expand-Archive $arc $exd
        $inner = Join-Path $exd ("node-" + $NodeVer + "-win-x64")
        $dst = Join-Path $Data "node"
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        Move-Item $inner $dst
    } finally {
        Remove-Item $tmpd -Recurse -Force -ErrorAction SilentlyContinue
    }
    Add-BinDirs
    if (-not ((Find-Cmd "node") -and (Find-Cmd "npm"))) {
        Fail ("giải nén xong nhưng không thấy node/npm trong " + (Join-Path $Data "node"))
    }
    Say ("node " + $NodeVer + " cài xong vào " + (Join-Path $Data "node")) "node"
}

function Install-Gemini {
    Ensure-Node
    $npm = Find-Cmd "npm"
    # --prefix cố định DATA\node: gemini luôn rơi vào chỗ bridge đã biết
    $prefix = Join-Path $Data "node"
    New-Item -ItemType Directory -Force -Path $prefix | Out-Null
    Run ('"' + $npm + '" install -g --prefix "' + $prefix + '" @google/gemini-cli') "gemini"
    Add-BinDirs
    if (-not (Find-Cmd "gemini")) { Fail "npm xong nhưng không thấy lệnh gemini — thử lại" }
    Say "gemini CLI cài xong — còn bước đăng nhập Google" "gemini"
}

function Install-Devin {
    Run 'powershell -NoProfile -Command "irm https://cli.devin.ai/install.ps1 | iex"' "devin"
    Add-BinDirs
    if (-not (Find-Cmd "devin")) { Fail "installer xong nhưng không thấy lệnh devin — mở lại app rồi kiểm tra" }
    Say "devin CLI cài xong — còn bước đăng nhập" "devin"
}

$installers = @{ gemini = { Install-Gemini }; devin = { Install-Devin } }
if (-not $installers.ContainsKey($Brain)) {
    Fail ("không có installer cho '" + $Brain + "' — cài tay theo trang hãng")
}
Write-State "running"
Say ("bắt đầu cài não '" + $Brain + "'…")
try {
    & $installers[$Brain]
} catch {
    Fail $_.Exception.Message
}
Write-State "done"
Write-Output (@{ step = "done"; msg = "xong" } | ConvertTo-Json -Compress)
