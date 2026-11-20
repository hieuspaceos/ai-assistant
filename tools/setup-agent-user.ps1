# setup-agent-user.ps1 — Windows: tao user han che "troly-agent" + cap
# NTFS ACL theo my-course/permissions.json. Chay MOT LAN, can admin.
#
#   powershell -ExecutionPolicy Bypass -File tools\setup-agent-user.ps1
#
# TRANG THAI: KHUNG — moi lam duoc nua dau (user + ACL). Nua sau (spawn
# nao duoi user do) BI TAC KY THUAT, chua verify tren may that:
#   runas / Start-Process -Credential KHONG redirect duoc stdin/stdout —
#   ma ACP song nho stdio pipe. Huong nghien cuu truoc khi hoan thien:
#     - CreateProcessWithLogonW qua Add-Type (P/Invoke) voi pipe handles
#     - PsExec -u troly-agent (Sysinternals, can cai ngoai + EULA)
#   Den khi chua spawn duoc → Windows = policy-only (khong enforcement).
#   KHONG tuyen bo sandbox tren Windows khi chua verify.
# Xem: plans/261120-1811-lock-down/phase-06-os-sandbox.md

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PermFp = Join-Path $Root "my-course\permissions.json"
$AgentUser = "troly-agent"

# --- can admin ---
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Can chay PowerShell quyen Administrator." -ForegroundColor Red
    exit 1
}

# --- tao user han che neu chua co ---
if (-not (Get-LocalUser -Name $AgentUser -ErrorAction SilentlyContinue)) {
    $pwd = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 |
                  ForEach-Object {[char]$_})
    $sec = ConvertTo-SecureString $pwd -AsPlainText -Force
    New-LocalUser -Name $AgentUser -Password $sec `
        -FullName "TroLy AI Agent" -Description "User han che cho nao tro ly - chi doc/ghi folder duoc cap" `
        -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    Write-Host "Da tao user '$AgentUser'."
} else {
    Write-Host "User '$AgentUser' da co san."
}

# --- cap ACL: project luon full, permissions.json theo access ---
function Grant-Folder($path, $rights) {
    if (-not (Test-Path $path)) {
        Write-Host "  bo qua (khong ton tai): $path" -ForegroundColor Yellow
        return
    }
    icacls $path /grant "${AgentUser}:(OI)(CI)$rights" /T /Q | Out-Null
    Write-Host "  $rights  $path"
}

Write-Host "Cap ACL:"
Grant-Folder $Root "F"          # project: skills, lessons, history…

if (Test-Path $PermFp) {
    $perm = Get-Content $PermFp -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($f in $perm.folders) {
        $p = [Environment]::ExpandEnvironmentVariables(
                 ($f.path -replace "^~", $env:USERPROFILE))
        Grant-Folder $p ($(if ($f.access -eq "read-write") { "M" } else { "R" }))
    }
} else {
    Write-Host "  khong thay permissions.json — chi cap project."
}

# --- carve-out: secrets khoa han, bridge.token chi cam GHI ---
# bridge.token: nao DOC duoc (can de goi bridge) nhung khong GHI —
# agent bi lua khong doi duoc chia khoa.
$tokFp = Join-Path $Root ".devin\bridge.token"
if (Test-Path $tokFp) {
    icacls $tokFp /deny "${AgentUser}:(W)" /Q | Out-Null
    Write-Host "  DENY-W $tokFp"
}
foreach ($fp in @((Join-Path $Root ".devin\secrets.local.json"),
                 (Join-Path $Root ".devin\mcp_config.local.json"))) {
    if (Test-Path $fp) {
        icacls $fp /deny "${AgentUser}:(F)" /Q | Out-Null
        Write-Host "  DENY   $fp"
    }
}

Write-Host ""
Write-Host "Xong nua dau (user + ACL). Nua sau — spawn nao duoi" -ForegroundColor Yellow
Write-Host "'$AgentUser' — CHUA implement: stdio pipe cross-user can" -ForegroundColor Yellow
Write-Host "CreateProcessWithLogonW/PsExec. Xem phase-06-os-sandbox.md." -ForegroundColor Yellow
