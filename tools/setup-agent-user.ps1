# setup-agent-user.ps1 — Windows: tao user han che "troly-agent" + cap
# NTFS ACL + luu credential DPAPI cho chat-bridge.ps1 spawn nao duoi
# user do (CreateProcessWithLogonW). Chay MOT LAN, can admin.
#
#   powershell -ExecutionPolicy Bypass -File tools\setup-agent-user.ps1
#
# Mo hinh tuong duong Seatbelt tren macOS:
#   - project: READ+EXECUTE toan cay (agent doc AGENTS.md, skills…)
#   - GHI duoc: my-course\, .devin\skills\, .logs\
#   - DENY-W: tools\, web\, extension\, .git\, brain.json, 4 file JSON
#     dieu khien trong my-course\, bot.md — agent ghi duoc = tu leo
#     quyen (tools\*.ps1 chay duoi quyen CHU).
#   - DENY het: secrets.local.json, mcp_config.local.json,
#     agent-user.cred (DPAPI scope chu nhung chan doc van sach hon).
#   - bridge.token: doc duoc (can goi bridge), deny-W.
#   - brain binary dir + brain config dir: RX/R — CLI nao can config
#     cua CHU de chay (~/.config/devin…); y nhu macOS noi agent la
#     cung user nen doc san. KHONG grant config nao khac.
#   - permissions.json folders: theo access (read→RX, read-write→M).
# Chay lai: password reset -> cred file viet lai, ACL grant lai.
#
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

# --- tao/reset user han che + password ngau nhien ---
# Luon reset password moi lan chay -> cred file luon dong bo, va chay
# lai nhieu lan khong vo tinh dung password cu da lo.
$pwd = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 |
              ForEach-Object {[char]$_})
$sec = ConvertTo-SecureString $pwd -AsPlainText -Force
if (-not (Get-LocalUser -Name $AgentUser -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $AgentUser -Password $sec `
        -FullName "TroLy AI Agent" -Description "User han che cho nao tro ly - chi doc/ghi folder duoc cap" `
        -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    Write-Host "Da tao user '$AgentUser'."
} else {
    Set-LocalUser -Name $AgentUser -Password $sec
    Write-Host "User '$AgentUser' da co — reset password."
}

# --- luu cred DPAPI: chi Windows user CHU giai ma duoc ---
# troly-agent doc file nay cung vo dung (DPAPI gan voi user da ma hoa)
# nhung van deny doc cho sach.
$CredFp = Join-Path $Root ".devin\agent-user.cred"
New-Item -ItemType Directory -Force (Split-Path $CredFp) | Out-Null
($sec | ConvertFrom-SecureString) | Set-Content $CredFp -Encoding UTF8 -NoNewline
icacls $CredFp /inheritance:r /grant "${env:USERNAME}:(F)" `
       /deny "${AgentUser}:(F)" /Q | Out-Null
Write-Host "  cred -> $CredFp (DPAPI, chi ban giai ma)"

# --- cap ACL ---
function Grant-Item($path, $rights) {
    if (-not (Test-Path $path)) { return }
    icacls $path /grant "${AgentUser}:(OI)(CI)$rights" /T /Q | Out-Null
    Write-Host "  $rights  $path"
}
function Deny-Write($path) {
    if (-not (Test-Path $path)) { return }
    icacls $path /deny "${AgentUser}:(OI)(CI)(W)" /T /Q | Out-Null
    Write-Host "  DENY-W $path"
}
function Deny-Full($path) {
    if (-not (Test-Path $path)) { return }
    icacls $path /deny "${AgentUser}:(OI)(CI)(F)" /T /Q | Out-Null
    Write-Host "  DENY   $path"
}

Write-Host "Cap ACL project:"
Grant-Item $Root "RX"                                   # doc toan cay
Grant-Item (Join-Path $Root "my-course") "M"            # ghi bai hoc, files
Grant-Item (Join-Path $Root ".devin\skills") "M"        # agent tu viet skill
Grant-Item (Join-Path $Root ".logs") "M"                # log

# File dieu khien + ma nguon bridge: doc duoc, KHONG ghi.
foreach ($p in @(
    (Join-Path $Root "tools"), (Join-Path $Root "web"),
    (Join-Path $Root "extension"), (Join-Path $Root ".git"),
    (Join-Path $Root "brain.json"),
    (Join-Path $Root "my-course\permissions.json"),
    (Join-Path $Root "my-course\connections.json"),
    (Join-Path $Root "my-course\config.json"),
    (Join-Path $Root "my-course\bots.json"),
    (Join-Path $Root "my-course\bot.md"))) { Deny-Write $p }

# bridge.token: nao DOC duoc (can de goi bridge) nhung khong GHI —
# agent bi lua khong doi duoc chia khoa.
Deny-Write (Join-Path $Root ".devin\bridge.token")

# Secrets: khoa han — agent doc duoc la lo het credential ra ngoai.
foreach ($fp in @($CredFp,
                 (Join-Path $Root ".devin\secrets.local.json"),
                 (Join-Path $Root ".devin\mcp_config.local.json"))) {
    Deny-Full $fp
}

# --- brain CLI: binary dir + config dir cua chu ---
# Agent chay duoi troly-agent KHONG tu doc duoc file trong profile cua
# chu — phai grant ro rang thu muc cai CLI nao va thu muc config cua nao
# do (~/.config/devin, ~/.claude…), y nhu macOS noi agent la cung user
# nen doc san. Chi grant dung brain dang chon trong brain.json.
$BrainFp = Join-Path $Root "brain.json"
if (Test-Path $BrainFp) {
    try {
        $b = Get-Content $BrainFp -Raw -Encoding UTF8 | ConvertFrom-Json
        # brain.json flat; khi chi co id (preset) thi map id -> cmd
        $PresetCmd = @{ devin="devin"; gemini="gemini"; codex="npx"
            claude="npx"; opencode="opencode"; goose="goose" }
        $brainId = if ($b.id) { [string]$b.id } else { "devin" }
        $brainCmd = if ($b.cmd) { [string]$b.cmd } else { $PresetCmd[$brainId] }
        if ($brainCmd) {
            $cmdSrc = (Get-Command $brainCmd -ErrorAction SilentlyContinue).Source
            if ($cmdSrc) {
                $cmdDir = Split-Path -Parent (Resolve-Path $cmdSrc)
                Grant-Item $cmdDir "RX"
            }
            # KHONG grant ~/.npm: npx cache cua chu ma agent ghi duoc
            # = agent dat package doc -> chu npx exec code do (escape).
            # Agent dung cache rieng qua NPM_CONFIG_CACHE trong
            # Start-BrainSandboxed (env NPM_CONFIG_CACHE=$HOME\.npm-cache).
            # map id nao -> thu muc config trong profile chu
            $cfgDirs = switch -Wildcard ($brainId) {
                "devin"    { @("$env:USERPROFILE\.config\devin",
                               "$env:LOCALAPPDATA\devin") }
                "claude"   { @("$env:USERPROFILE\.claude") }
                "codex"    { @("$env:USERPROFILE\.codex") }
                "gemini"   { @("$env:USERPROFILE\.gemini") }
                "opencode" { @("$env:USERPROFILE\.opencode",
                               "$env:USERPROFILE\.config\opencode") }
                "copilot"  { @("$env:USERPROFILE\.copilot") }
                "goose"    { @("$env:USERPROFILE\.config\goose") }
                default    { @() }
            }
            foreach ($d in $cfgDirs) { Grant-Item $d "RX" }
        }
    } catch { Write-Host "  bo qua brain grant: $_" -ForegroundColor Yellow }
}

# --- permissions.json: grant theo access ---
Write-Host "Cap ACL permissions.json:"
if (Test-Path $PermFp) {
    $perm = Get-Content $PermFp -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($f in $perm.folders) {
        $p = [Environment]::ExpandEnvironmentVariables(
                 ($f.path -replace "^~", $env:USERPROFILE))
        Grant-Item $p ($(if ($f.access -eq "read-write") { "M" } else { "RX" }))
    }
} else {
    Write-Host "  khong thay permissions.json — chi cap project."
}

Write-Host ""
Write-Host "Xong. Tu lan khoi dong chat-bridge.ps1 toi, nao se chay" -ForegroundColor Green
Write-Host "duoi user han che '$AgentUser' (vung cat that, khong chi loi hua)." -ForegroundColor Green
Write-Host "Chay lai script nay sau khi DOI NAO hoac them quyen moi de cap nhat ACL." -ForegroundColor Yellow
