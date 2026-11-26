# install.ps1 — cài Trợ Lý AI lên máy Windows (chạy PowerShell ADMIN).
#
# Chạy:  powershell -ExecutionPolicy Bypass -File install.ps1 [-Dest C:\TroLyAI]
#        [-ForUser <user>] [-Quiet] [-NoSandbox]
#
#   -Quiet     cài im lặng (GPO/Intune) — không hỏi gì, mặc định làm
#              mọi bước; chạy dưới SYSTEM thì NÊN kèm -ForUser để đặt
#              shortcut + ACL cho đúng chủ máy.
#   -NoSandbox bỏ tạo user sandbox troly-agent (não chạy chung user —
#              chỉ policy bảo vệ, máy không ép được).
#
# Làm gì:
#   1. Copy bộ trợ lý vào -Dest (mặc định C:\TroLyAI)
#   2. winget install ttyd nếu thiếu (terminal cho não)
#   3. Hỏi có setup user sandbox troly-agent không (khuyến nghị)
#   4. Copy license.json + fleet.json từ folder "company" cạnh script (nếu có)
#   5. Shortcut Desktop "TroLy AI" → start.bat
#   6. Hướng dẫn bước còn lại (extension + lần chạy đầu)
param([string]$Dest = "C:\TroLyAI", [string]$ForUser = "",
      [switch]$Quiet, [switch]$NoSandbox)
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
function Rc($srcDir, $dstDir, [string[]]$extra) {
    robocopy $srcDir $dstDir @extra /NFL /NDL /NJH /NJS | Out-Null
    # robocopy exit >=8 = loi copy thuc — <8 la thanh cong (copy/skip)
    if ($LASTEXITCODE -ge 8) {
        Write-Host "  !! copy $dstDir loi (robocopy exit $LASTEXITCODE)" -ForegroundColor Red
        exit 1
    }
}
$dirs = @("tools","web","extension","templates","docs","collector-web")
foreach ($d in $dirs) {
    Rc (Join-Path $src $d) (Join-Path $Dest $d) `
        @("/E","/XD","__pycache__",".shots","clone-work")
}
Rc (Join-Path $src ".devin\skill-packs") (Join-Path $Dest ".devin\skill-packs") @("/E")
# my-course: 6 file state la du lieu hoc vien — reinstall KHONG de
# (mat learner_name → may thanh "moi" → pack re-ap exec_allowlist +
# permissions_template; mat bots/consent da duyet). Seed con lai di
# qua /XO: ghi de chi khi goi cai moi hon — chinh sua cua hoc vien
# trong bai hoc khong bi ban cu de len. (audit-5 F7)
$stateFiles = @("config.json","manifest.json","bots.json","permissions.json",
    "connections.json","bot.md")
$mcDest = Join-Path $Dest "my-course"
if (Test-Path $mcDest) {
    Rc (Join-Path $src "my-course") $mcDest `
        @("/E","/XO","/XD","__pycache__",".shots","clone-work",".trash") `
        + @("/XF") + $stateFiles
    foreach ($sf in $stateFiles) {
        $sfSrc = Join-Path (Join-Path $src "my-course") $sf
        $sfDst = Join-Path $mcDest $sf
        if ((Test-Path $sfSrc) -and -not (Test-Path $sfDst)) {
            Copy-Item $sfSrc $sfDst
        }
    }
} else {
    Rc (Join-Path $src "my-course") $mcDest `
        @("/E","/XD","__pycache__",".shots","clone-work",".trash")
}
$files = @("AGENTS.md","CLAUDE.md","SETUP.md","README.md","requirements.txt",
    "VERSION","CHANGELOG.md","start.sh","start.bat","brain.json",".gitignore")
foreach ($f in $files) {
    robocopy $src $Dest $f /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host "  !! copy $f loi (robocopy exit $LASTEXITCODE)" -ForegroundColor Red
        exit 1
    }
}
# user thuong chay app can GHI .devin\ (token/key/state), my-course\,
# .logs\ — C:\<dir> mac dinh chi cho BUILTIN\Users RX nen app chet khi
# non-elevated (audit-5 F1). Grant M cho user local (-ForUser khi can
# chi dinh dung chu nhan thay vi moi Users); troly-agent cung thuoc
# Users nen setup-agent-user.ps1 RE-SEAL lai (deny-W tren root + mo
# dung 3 dir writable) — thieu buoc do la sandbox escape.
$grantTo = if ($ForUser) { $ForUser } else { "BUILTIN\Users" }
icacls $Dest /grant "${grantTo}:(OI)(CI)M" /T /Q | Out-Null
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

# 3. sandbox user (tuỳ chọn, khuyến nghị — Quiet mặc định CÓ trừ khi
# -NoSandbox; Intune/GPO chạy dưới SYSTEM vẫn tạo user được vì đã admin)
$ans = if ($Quiet) { "" } else {
    Read-Host "Tao user sandbox troly-agent (giam quyen cho agent)? [Y/n]"
}
if (-not $NoSandbox -and $ans -ne "n" -and $ans -ne "N") {
    & powershell -ExecutionPolicy Bypass -File "$Dest\tools\setup-agent-user.ps1"
} elseif ($NoSandbox) {
    Write-Host "  bo qua sandbox user (-NoSandbox) — nao chay chung user, chi policy bao ve"
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

# 5. shortcut Desktop — cài tay = Desktop user đang chạy; -Quiet + -ForUser
# = Desktop user đích; -Quiet không -ForUser (SYSTEM) = Public Desktop
$desktop = if ($ForUser) { "C:\Users\$ForUser\Desktop" }
           elseif ($Quiet) { "$env:PUBLIC\Desktop" }
           else { "$env:USERPROFILE\Desktop" }
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut("$desktop\TroLy AI.lnk")
$lnk.TargetPath = "$Dest\start.bat"
$lnk.WorkingDirectory = $Dest
$lnk.Description = "Mo Tro Ly AI"
$lnk.Save()
Write-Host "  ok — shortcut Desktop ($desktop)"

Write-Host ""
Write-Host "== Xong. Con lai: =="
Write-Host "  1. Extension: cai tu Chrome Web Store (link IT cap) HOAC force-install policy"
Write-Host "  2. Chay 'TroLy AI' tren Desktop -> portal mo -> lam theo onboarding"
Write-Host "  3. Kiem tra: chrome://extensions thay 'Tro Ly AI', portal chat tra loi"
