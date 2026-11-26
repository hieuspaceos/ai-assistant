# install-brain.ps1 — IT cài "não" cho máy nhân viên (PowerShell ADMIN).
#
# Chạy:  powershell -ExecutionPolicy Bypass -File install-brain.ps1 [-Brain gemini|devin]
#
#   -Brain gemini   Node.js (winget) + npm i -g @google/gemini-cli — FREE,
#                   nhân viên đăng nhập bằng Google CÁ NHÂN lần đầu chạy.
#   -Brain devin    Devin CLI (irm cli.devin.ai/install.ps1) — cần seat
#                   Devin trả phí, nhân viên đăng nhập lần đầu chạy.
#
# Script chỉ cài binary + đặt brain.json vào DEST. ĐĂNG NHẬP vẫn là của
# nhân viên lần đầu mở trợ lý (OAuth cá nhân — không provision được).
# Chạy SAU install.ps1 (cần folder đích tồn tại).
param([string]$Dest = "C:\TroLyAI",
      [ValidateSet("gemini","devin")][string]$Brain = "gemini")
$ErrorActionPreference = "Stop"

Write-Host "== Cai nao '$Brain' cho Tro Ly AI =="

if ($Brain -eq "gemini") {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Write-Host "  cai Node.js qua winget..."
        winget install --id OpenJS.NodeJS -e `
            --accept-source-agreements --accept-package-agreements
        # PATH của session này chưa nạp lại — bổ sung chỗ node mới cài
        $env:PATH = "$env:ProgramFiles\nodejs;$env:PATH"
    } else { Write-Host "  ok — node da co" }
    Write-Host "  npm i -g @google/gemini-cli..."
    npm install -g "@google/gemini-cli"
    if (-not (Get-Command gemini -ErrorAction SilentlyContinue)) {
        Write-Host "  !! npm xong nhung khong thay 'gemini' — kiem tra lai"
        exit 1
    }
    $bj = @{ id="gemini"; label="Gemini CLI (Google)"; cmd="gemini";
             args=@("--acp"); terminal="gemini" }
} else {
    Write-Host "  cai Devin CLI..."
    powershell -NoProfile -Command "irm https://cli.devin.ai/install.ps1 | iex"
    if (-not (Get-Command devin -ErrorAction SilentlyContinue)) {
        Write-Host "  !! khong thay 'devin' — installer co the can PATH moi"
        exit 1
    }
    $bj = @{ id="devin"; label="Devin"; cmd="devin";
             args=@("acp","--process-model","in-process"); terminal="devin" }
}

# Không đè brain.json nếu máy đã onboard (learner_name có rồi = não là
# lựa chọn của user). Máy mới → ghi sẵn để onboarding auto-chọn.
$cfg = Join-Path $Dest "my-course\config.json"
$onboarded = $false
try {
    $onboarded = [bool]((Get-Content $cfg -Raw | ConvertFrom-Json).learner_name)
} catch {}
$bf = Join-Path $Dest "brain.json"
if ($onboarded -and (Test-Path $bf)) {
    Write-Host "  may da onboard — giu nguyen brain.json hien co"
} else {
    $bj | ConvertTo-Json | Set-Content $bf -Encoding UTF8
    Write-Host "  ok — brain.json -> $Brain"
}

Write-Host ""
Write-Host "== Xong. Nhan vien lan dau mo tro ly se duoc hoi dang nhap nao =="
Write-Host "   (gemini: Google ca nhan | devin: tai khoan Devin cua nguoi do)"
