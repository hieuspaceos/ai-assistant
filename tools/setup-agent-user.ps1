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
#     LUU Y: deny-write tren file .exe cung chan EXECUTE (quirk Windows,
#     khac macOS) — day la TINH NANG: agent khong chay duoc PE dat trong
#     tools\. Script (.ps1/.py) van chay vi interpreter nam o Program
#     Files chi co RX. Nao that (devin, npx…) ngoai deny-tree nen exec OK.
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
# CSPRNG — Get-Random là System.Random (~32bit seed, đoán được theo thời
# điểm chạy) nên không dùng cho password; sinh hex như bridge.token.
# Dùng instance Create()+GetBytes(byte[]) thay vì static GetBytes(int):
# overload static chỉ có trên .NET Core/5+ (pwsh 7), .NET Framework
# (Windows PowerShell 5.1 — thứ start.bat gọi) không có.
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $rb = New-Object byte[] 24
    $rng.GetBytes($rb)
} finally {
    $rng.Dispose()
}
# suffix "A9!" đảm bảo đủ 4 nhóm ký tự (hoa+thường+số+ký hiệu) — policy
# complexity của Windows Server (runner CI, máy cty bật policy) reject
# password hex-thường-trần dù entropy đủ. Entropy vẫn nằm ở 48 hex ngẫu
# nhiên; suffix cố định không làm yếu đáng kể cho local account.
$pwd = ([BitConverter]::ToString($rb)).Replace('-', '').ToLower() + 'A9!'
$sec = ConvertTo-SecureString $pwd -AsPlainText -Force
if (-not (Get-LocalUser -Name $AgentUser -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $AgentUser -Password $sec `
        -FullName "TroLy AI Agent" -Description "Nao tro ly - quyen han che" `
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
# .devin\skills phai ton tai TRUOC khi re-seal — deny-W ke thua tren
# .devin khien agent khong tu tao duoc dir nay neu chua co.
New-Item -ItemType Directory -Force (Join-Path $Root ".devin\skills") | Out-Null
Grant-Item $Root "RX"                                   # doc toan cay
Grant-Item (Join-Path $Root "my-course") "M"            # ghi bai hoc, files
Grant-Item (Join-Path $Root ".devin\skills") "M"        # agent tu viet skill
Grant-Item (Join-Path $Root ".logs") "M"                # log

# RE-SEAL (audit-5 F6b): install.ps1 grant "BUILTIN\Users:M" tren $Dest
# cho user thuong chay app — troly-agent cung thuoc Users nen duoc M
# toan cay neu khong khoa lai (.devin\exec-allowlist.json = tu duyet
# exec; update-stage+update-pending = RCE quyen chu; start.bat…).
# Deny W ke thua toan cay (file state tao SAU NAY cung bi chan), roi
# go deny trong dung 3 dir agent duoc ghi. /remove:d PHAI chay truoc
# Deny-Write le ben duoi vi no go ca deny san co trong my-course.
icacls $Root /deny "${AgentUser}:(OI)(CI)W" /Q | Out-Null
foreach ($d in @("my-course", ".devin\skills", ".logs")) {
    icacls (Join-Path $Root $d) /remove:d "${AgentUser}" /T /Q | Out-Null
}

# File dieu khien + ma nguon bridge: doc duoc, KHONG ghi.
foreach ($p in @(
    (Join-Path $Root "tools"), (Join-Path $Root "web"),
    (Join-Path $Root "extension"), (Join-Path $Root ".git"),
    (Join-Path $Root "brain.json"),
    (Join-Path $Root "my-course\permissions.json"),
    (Join-Path $Root "my-course\connections.json"),
    (Join-Path $Root "my-course\config.json"),
    (Join-Path $Root "my-course\bots.json"),
    (Join-Path $Root "my-course\manifest.json"),
    (Join-Path $Root "my-course\bot.md"))) { Deny-Write $p }

# bridge.token: nao DOC duoc (can de goi bridge) nhung khong GHI —
# agent bi lua khong doi duoc chia khoa.
Deny-Write (Join-Path $Root ".devin\bridge.token")

# Secrets: khoa han — agent doc duoc la lo het credential ra ngoai.
# machine.key/fleet.json (beacon_secret ca org)/license.json cung vay
# (audit-5 F6) — agent chi can bridge.token de goi bridge.
foreach ($fp in @($CredFp,
                 (Join-Path $Root ".devin\secrets.local.json"),
                 (Join-Path $Root ".devin\mcp_config.local.json"),
                 (Join-Path $Root ".devin\machine.key"),
                 (Join-Path $Root ".devin\fleet.json"),
                 (Join-Path $Root ".devin\license.json"),
                 (Join-Path $Root ".devin\env-allowlist.json"))) {
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
# Enforcement-point recheck (audit-5 F11, parity path_sensitive/_grant_ok
# tren macOS): drive-root / home / Windows / Program* = "mo toan may";
# .ssh, browser profile, DPAPI… = credential store. So HAI chieu nhu
# path_sensitive: path trong sensitive HOAC path chua sensitive (grant
# C:\Users doc het profile moi user). Pack permissions_template hay
# file sua tay khong duoc bien thanh ACL cho agent.
Write-Host "Cap ACL permissions.json:"
if (Test-Path $PermFp) {
    $perm = Get-Content $PermFp -Raw -Encoding UTF8 | ConvertFrom-Json
    # Hai nhom theo dung path_guard: ROOTS = chan exact-match (~,
    # WINDIR…) — con cua chung van grant duoc nhu macOS; DIRS = so
    # hai chieu (trong sensitive / chua sensitive) nhu _SENSITIVE_DIRS.
    $skipExact = @($env:USERPROFILE, $env:WINDIR, $env:ProgramFiles,
                   ${env:ProgramFiles(x86)}, $env:ProgramData) |
                 Where-Object { $_ } |
                 ForEach-Object { $_.TrimEnd('\') }
    $la = $env:LOCALAPPDATA; $ra = $env:APPDATA
    $skipDirs = @((Join-Path $env:USERPROFILE ".ssh"),
                  (Join-Path $env:USERPROFILE ".aws"),
                  (Join-Path $env:USERPROFILE ".kube"),
                  (Join-Path $env:USERPROFILE ".docker"),
                  (Join-Path $env:USERPROFILE ".azure"),
                  $(if ($la) { Join-Path $la "Google\Chrome" }),
                  $(if ($la) { Join-Path $la "Microsoft\Edge" }),
                  $(if ($la) { Join-Path $la "BraveSoftware" }),
                  $(if ($ra) { Join-Path $ra "Mozilla" }),
                  $(if ($ra) { Join-Path $ra "1Password" }),
                  $(if ($ra) { Join-Path $ra "Microsoft\Credentials" }),
                  $(if ($ra) { Join-Path $ra "Microsoft\Protect" }),
                  $(if ($ra) { Join-Path $ra "Microsoft\Crypto" })) |
                 Where-Object { $_ } |
                 ForEach-Object { $_.TrimEnd('\') }
    foreach ($f in $perm.folders) {
        $p = [Environment]::ExpandEnvironmentVariables(
                 ($f.path -replace "^~", $env:USERPROFILE))
        if (-not [IO.Path]::IsPathRooted($p)) {
            Write-Host "  bo qua (khong tuyet doi): $p"; continue
        }
        # ProviderPath: .Path cua UNC mang prefix FileSystem:: lam so
        # khop StartsWith sai; ProviderPath tra path FS tho.
        $rp = try { (Resolve-Path $p -ErrorAction Stop).ProviderPath.
                    TrimEnd('\') } catch { $null }
        if (-not $rp) { Write-Host "  bo qua (khong ton tai): $p"; continue }
        $bad = ($rp -match "^[A-Za-z]:$") -or ($skipExact -contains $rp)
        foreach ($s in $skipDirs) {
            if ($rp -ieq $s `
                -or $rp.StartsWith($s + '\', 'OrdinalIgnoreCase') `
                -or $s.StartsWith($rp + '\', 'OrdinalIgnoreCase')) {
                $bad = $true; break
            }
        }
        if ($bad) {
            Write-Host "  bo qua (nhay cam): $p" -ForegroundColor Yellow
            continue
        }
        Grant-Item $p ($(if ($f.access -eq "read-write") { "M" } else { "RX" }))
    }
} else {
    Write-Host "  khong thay permissions.json — chi cap project."
}

Write-Host ""
Write-Host "Xong. Tu lan khoi dong chat-bridge.ps1 toi, nao se chay" -ForegroundColor Green
Write-Host "duoi user han che '$AgentUser' (vung cat that, khong chi loi hua)." -ForegroundColor Green
Write-Host "Chay lai script nay sau khi DOI NAO hoac them quyen moi de cap nhat ACL." -ForegroundColor Yellow
