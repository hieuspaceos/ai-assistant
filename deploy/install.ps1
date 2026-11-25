# install.ps1 — cài Trợ Lý AI lên máy Windows (chạy PowerShell ADMIN).
#
# Chạy:  powershell -ExecutionPolicy Bypass -File install.ps1 [-Dest C:\TroLyAI]
#
# Làm gì:
#   1. Copy bộ trợ lý vào -Dest (mặc định C:\TroLyAI)
#   2. winget install ttyd nếu thiếu (terminal cho não)
#   3. Hỏi có setup user sandbox troly-agent không (khuyến nghị)
#   4. Copy license.json + fleet.json từ folder "company" cạnh script (nếu có)
#   5. Shortcut Desktop "TroLy AI" → start.bat
#   6. Hướng dẫn bước còn lại (extension + lần chạy đầu)
param([string]$Dest = "C:\TroLyAI")
$ErrorActionPreference = "Stop"
$src = Split-Path -Parent $PSScriptRoot   # folder repo chứa deploy/

Write-Host "== Cai Tro Ly AI =="
Write-Host "Nguon : $src"
Write-Host "Dich  : $Dest"

# 1. copy theo INCLUDE-list = whitelist update.py (CODE_DIRS/FILES +
# SEED + .devin/skill-packs). Exclude-list từng lọt secrets/state máy
# dev (secrets.local.json, machine.id, collector-data, .logs, .shots…)
# vào bộ cài NV — include thì artefact mới tự nhiên không đi theo.
if (Test-Path $Dest) { Write-Host "$Dest da ton tai — cap nhat de len" }
$dirs = @("tools","web","extension","templates","docs","collector-web","my-course")
foreach ($d in $dirs) {
    robocopy (Join-Path $src $d) (Join-Path $Dest $d) /E /NFL /NDL /NJH /NJS `
        /XD __pycache__ .shots clone-work | Out-Null
}
robocopy (Join-Path $src ".devin\skill-packs") (Join-Path $Dest ".devin\skill-packs") `
    /E /NFL /NDL /NJH /NJS | Out-Null
$files = @("AGENTS.md","CLAUDE.md","SETUP.md","README.md","requirements.txt",
    "VERSION","CHANGELOG.md","start.sh","start.bat","brain.json",".gitignore")
foreach ($f in $files) {
    robocopy $src $Dest $f /NFL /NDL /NJH /NJS | Out-Null
}
Write-Host "  ok — copy xong"

# cạm bẫy: learner_name khác rỗng trong bộ cài = mọi máy NV bị coi là
# "máy cũ" → mycourse_files của pack cty không bao giờ áp
try {
    $cfg = Get-Content "$Dest\my-course\config.json" -Raw | ConvertFrom-Json
    if ($cfg.learner_name) {
        Write-Host "  !! my-course/config.json có learner_name — mycourse_files"
        Write-Host "     của pack sẽ KHÔNG áp trên máy NV. Để trống trước khi cài."
    }
} catch {}

# 2. ttyd
if (-not (Get-Command ttyd -ErrorAction SilentlyContinue)) {
    Write-Host "  ttyd chua co — cai qua winget..."
    try { winget install --id tsl0922.ttyd -e --accept-source-agreements --accept-package-agreements }
    catch { Write-Host "  !! winget loi — cai tay ttyd tu https://github.com/tsl0922/ttyd/releases" }
} else { Write-Host "  ok — ttyd da co" }

# 3. sandbox user (tuỳ chọn, khuyến nghị)
$ans = Read-Host "Tao user sandbox troly-agent (giam quyen cho agent)? [Y/n]"
if ($ans -ne "n" -and $ans -ne "N") {
    & powershell -ExecutionPolicy Bypass -File "$Dest\tools\setup-agent-user.ps1"
}

# 4. license + fleet từ folder company/ cạnh installer
$comp = Join-Path $PSScriptRoot "company"
New-Item -ItemType Directory -Force -Path "$Dest\.devin" | Out-Null
foreach ($f in @("license.json", "fleet.json")) {
    $p = Join-Path $comp $f
    if (Test-Path $p) {
        Copy-Item $p "$Dest\.devin\$f" -Force
        Write-Host "  ok — $f da dat vao .devin\"
    }
}

# 5. shortcut Desktop
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut("$env:USERPROFILE\Desktop\TroLy AI.lnk")
$lnk.TargetPath = "$Dest\start.bat"
$lnk.WorkingDirectory = $Dest
$lnk.Description = "Mo Tro Ly AI"
$lnk.Save()
Write-Host "  ok — shortcut Desktop"

Write-Host ""
Write-Host "== Xong. Con lai: =="
Write-Host "  1. Extension: cai tu Chrome Web Store (link IT cap) HOAC force-install policy"
Write-Host "  2. Chay 'TroLy AI' tren Desktop -> portal mo -> lam theo onboarding"
Write-Host "  3. Kiem tra: chrome://extensions thay 'Tro Ly AI', portal chat tra loi"
