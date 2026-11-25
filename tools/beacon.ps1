# beacon.ps1 — bản Windows của tools/beacon.py (parity — đọc docstring
# file .py cho đầy đủ luồng pairing/backoff; contract snapshot giống hệt).
# Chỉ chạy khi có .devin\fleet.json; spawn bởi start.bat.
param([string]$WorkDir = "")
$ErrorActionPreference = "Stop"
if (-not $WorkDir) { $WorkDir = (Resolve-Path "$PSScriptRoot\..").Path }
$Devin   = Join-Path $WorkDir ".devin"
$FLEET_FP  = Join-Path $Devin "fleet.json"
$MID_FP    = Join-Path $Devin "machine.id"
$MKEY_FP   = Join-Path $Devin "machine.key"
$CURSOR_FP = Join-Path $Devin "beacon.cursor"
$INBOX_FP  = Join-Path $Devin "fleet-inbox.json"
$LIC_FP    = Join-Path $Devin "license.json"
$PACKV_FP  = Join-Path $Devin "pack-version"
$TOKEN_FP  = Join-Path $Devin "bridge.token"
$BRIDGE    = "http://127.0.0.1:7682"
$BEACON_VER = 1
$INTERVAL = [int]($env:TROLY_BEACON_INTERVAL ?? "900")
$PAIR_RETRY = [int]($env:TROLY_PAIR_RETRY ?? "300")   # chờ admin duyệt
$FAIL_SLEEPS = @(300, 900, 1800)      # backoff quay vòng 5'→15'→30'

function Read-File($fp) {
    if (Test-Path $fp) { return (Get-Content $fp -Raw -Encoding UTF8).Trim() }
    return ""
}
function Write-600($fp, $text) {
    # Windows không có chmod — file nằm trong profile user là đủ ranh
    # giới (parity .py ghi 0600); DPAPI user nếu cần cứng hơn là việc sau
    [IO.File]::WriteAllText($fp, $text)
}
function JLoad($fp) {
    try { return Get-Content $fp -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { return $null }
}
function Bridge-Get($path, $token) {
    return Invoke-RestMethod -Uri ($BRIDGE + $path) -TimeoutSec 4 `
        -Headers @{ "X-Bridge-Token" = $token }
}
function Collector-Post($path, $key, $payload, $base) {
    # trả @{code=..; obj=..} — HTTPError vẫn cần body (revoke/pending…)
    try {
        $r = Invoke-WebRequest -Uri ($base + $path) -Method Post `
            -TimeoutSec 5 -ContentType "application/json" `
            -Headers @{ "X-Beacon-Key" = $key } `
            -Body ($payload | ConvertTo-Json -Depth 8 -Compress)
        return @{ code = [int]$r.StatusCode
                  obj  = ($r.Content | ConvertFrom-Json) }
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            $code = [int]$resp.StatusCode
            try {
                $sr = New-Object IO.StreamReader($resp.GetResponseStream())
                return @{ code = $code
                          obj  = ($sr.ReadToEnd() | ConvertFrom-Json) }
            } catch { return @{ code = $code; obj = $null } }
        }
        throw   # lỗi mạng thật → caller xếp backoff
    }
}
function Machine-Id {
    $mid = Read-File $MID_FP
    if (-not $mid) {
        $mid = -join ((1..16) | ForEach-Object {
            [BitConverter]::ToString(
                [Security.Cryptography.RandomNumberGenerator]::GetBytes(1))
        }).Replace("-", "").ToLower()
        Write-600 $MID_FP $mid
    }
    return $mid
}
function Collect-Snapshot {
    # giống beacon.py: bridge chết vẫn trả snapshot tối thiểu
    $token = Read-File $TOKEN_FP
    $snap = [ordered]@{ bridge_up = $false }
    $counts = @{}
    try {
        $health = Bridge-Get "/api/health" $token
        $snap.bridge_up = [bool]$health.ok
        $snap.health = $health
        foreach ($kv in @{ brain = "/api/brain"; config = "/api/config"
                           bots = "/api/bots"; perms = "/api/permissions"
                           conns = "/api/connections" }.GetEnumerator()) {
            try { $snap[$kv.Key] = Bridge-Get $kv.Value $token } catch {}
        }
        $cur = [int]((Read-File $CURSOR_FP) -replace "\D", "" -replace "^$", "0")
        $poll = Bridge-Get "/api/poll?since=$cur&wait=0" $token
        if (-not $poll.reset) {
            foreach ($e in $poll.events) {
                $t = "$($e.t)"; if (-not $t) { $t = "?" }
                $counts[$t] = ($counts[$t] ?? 0) + 1
            }
        }
        Write-600 $CURSOR_FP "$($poll.next)"
    } catch {}
    return @{ snap = $snap; counts = $counts }
}

$fleet = JLoad $FLEET_FP
if (-not $fleet -or -not $fleet.collector -or -not $fleet.beacon_secret) {
    Write-Host "beacon: khong co .devin/fleet.json (hoac thieu truong) - ngu"
    exit 0
}
$base = $fleet.collector.TrimEnd("/")
$mid = Machine-Id
$fails = 0
while ($true) {
    $nap = $INTERVAL
    try {
        $mkey = Read-File $MKEY_FP
        if (-not $mkey) {
            $os = "$([Environment]::OSVersion.Platform) " +
                  "$([Environment]::OSVersion.Version)"
            $r = Collector-Post "/api/pair" $fleet.beacon_secret @{
                machine_id = $mid; hostname = $env:COMPUTERNAME; os = $os
                org = $fleet.org; license = (JLoad $LIC_FP)
            } $base
            if ($r.code -eq 200 -and $r.obj) {
                if ($r.obj.status -eq "approved" -and $r.obj.machine_key) {
                    Write-600 $MKEY_FP $r.obj.machine_key
                    Write-Host "beacon: admin da duyet - vao fleet"
                    $fails = 0
                } elseif ($r.obj.status -eq "revoked") {
                    Write-Host "beacon: may dang bi thu hoi - cho admin"
                } else {
                    Write-Host "beacon: cho admin duyet tren dashboard"
                    $nap = $PAIR_RETRY     # pending: thăm dò nhanh hơn
                }
            } else { $fails++ }
        } else {
            $got = Collect-Snapshot
            $os = "$([Environment]::OSVersion.Platform) " +
                  "$([Environment]::OSVersion.Version)"
            $payload = [ordered]@{
                beacon_ver = $BEACON_VER; machine_id = $mid
                hostname = $env:COMPUTERNAME; os = $os
                version = (Read-File (Join-Path $WorkDir "VERSION"))
                pack_version = ((Read-File $PACKV_FP) -replace "^$", $null)
                org = $fleet.org; ts = [int][DateTimeOffset]::Now.ToUnixTimeSeconds()
                license = (JLoad $LIC_FP); counts = $got.counts
                snapshot = $got.snap
            }
            $r = Collector-Post "/api/beacon" $mkey $payload $base
            if ($r.code -eq 200) {
                $fails = 0
                if ($r.obj -and ($r.obj.update -or $r.obj.pack)) {
                    $inbox = @{ ts = $payload.ts }
                    if ($r.obj.update) { $inbox.update = $r.obj.update }
                    if ($r.obj.pack)   { $inbox.pack   = $r.obj.pack }
                    Write-600 $INBOX_FP ($inbox | ConvertTo-Json -Depth 8)
                    # đá update/apply-pack chạy nền — source-mode Windows
                    # chạy .py qua python (có sẵn vì beacon.ps1 chạy cùng
                    # bộ cài source); frozen troly tự check lúc boot
                    foreach ($t in @("update", "apply-pack")) {
                        try {
                            Start-Process -WindowStyle Hidden python `
                                -ArgumentList "`"$PSScriptRoot\$t.py`"", "`"$WorkDir`"" `
                                -WorkingDirectory $WorkDir
                        } catch {}
                    }
                }
                if ($r.obj -and $r.obj.status -eq "revoked") {
                    Remove-Item $MKEY_FP -ErrorAction SilentlyContinue
                }
            } elseif ($r.code -in 401, 403) {
                if (($r.obj -and $r.obj.status -eq "revoked") `
                        -or $r.code -eq 403) {
                    Remove-Item $MKEY_FP -ErrorAction SilentlyContinue
                }
                $fails++
            } else { $fails++ }
        }
    } catch {
        $fails++
        Write-Host "beacon: loi vong lap — $($_.Exception.Message)"
    }
    if ($fails -gt 0) {
        Start-Sleep -Seconds $FAIL_SLEEPS[($fails - 1) % $FAIL_SLEEPS.Count]
    } else {
        Start-Sleep -Seconds $nap
    }
}
