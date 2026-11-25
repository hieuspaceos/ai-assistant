# test-agent-spawn.ps1 — smoke test S4 (Windows sandbox). CAN ADMIN.
#
#   powershell -ExecutionPolicy Bypass -File tools\test-agent-spawn.ps1
#
# Gia dinh setup-agent-user.ps1 da chay (CI chay truoc). Khong co cred thi
# test tu tao user de van chay duoc phan unit-test AgentSpawn.
#
#   1. compile C# AgentSpawn nhung trong chat-bridge.ps1 (code that)
#   2. spawn cross-user: whoami = troly-agent
#   3. deny-read file bi chan, doc duoc file cho phep
#   4. deny-ghi tools\, ghi duoc my-course\  (ACL do setup-agent-user cap)
#   5. stdio 2 chieu qua anonymous pipe (stdin -> stdout)
#   6. IsAlive + kill ca cay qua Job Object
#   7. sai mat khau -> Error ro rang (khong throw)
#   8. e2e: chat-bridge.ps1 that + fakebrain.exe -> ready/pong:troly-agent
#
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script:pass = 0; $script:fail = 0
function Check($name, [bool]$cond) {
    if ($cond) { $script:pass++; Write-Host "  ok   $name" -ForegroundColor Green }
    else { $script:fail++; Write-Host "  FAIL $name" -ForegroundColor Red }
}

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "can chay voi quyen admin" -ForegroundColor Red; exit 2
}

# fakebrain.exe (dotnet build o step CI truoc) phai nam tren PATH de
# CreateProcessWithLogonW resolve duoc — ca trong env test lan env child.
$FakeBin = Join-Path $Root "tools\fakebrain\bin\Release\net8.0"
$env:PATH = "$FakeBin;$env:PATH"

# --- 1. compile C# AgentSpawn nhung trong chat-bridge.ps1 (code that) ---
$src = Get-Content (Join-Path $Root "tools\chat-bridge.ps1") -Raw -Encoding UTF8
$mark = "Add-Type -TypeDefinition @'"
$i0 = $src.IndexOf($mark) + $mark.Length
$i1 = $src.IndexOf("'@ -ReferencedAssemblies")
if ($i0 -lt $mark.Length -or $i1 -le $i0) {
    Write-Host "khong tach duoc C# block" -ForegroundColor Red; exit 2
}
Add-Type -TypeDefinition $src.Substring($i0, $i1 - $i0) `
    -ReferencedAssemblies System.IO.FileSystem, System.Runtime.InteropServices, Microsoft.Win32.Primitives, System.ComponentModel.Primitives
Check "AgentSpawn compile" $true

# --- user + password: tu cred file (setup da chay) hoac tu tao ---
$AgentUser = "troly-agent"
$CredFp = Join-Path $Root ".devin\agent-user.cred"
if (Test-Path $CredFp) {
    $pw = [Net.NetworkCredential]::new("x",
        (ConvertTo-SecureString (Get-Content $CredFp -Raw).Trim())).Password
} else {
    Write-Host "(khong co cred — tu tao user cho unit test)" -ForegroundColor Yellow
    $pw = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 |
                  ForEach-Object {[char]$_})
    $sec = ConvertTo-SecureString $pw -AsPlainText -Force
    if (Get-LocalUser -Name $AgentUser -ErrorAction SilentlyContinue) {
        Set-LocalUser -Name $AgentUser -Password $sec
    } else {
        New-LocalUser -Name $AgentUser -Password $sec `
            -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    }
}

# env block toi thieu — cwd + TEMP phai la cho world-accessible
# (C:\Windows\Temp), KHONG phai temp rieng cua admin.
$home2 = "C:\Users\$AgentUser"
$envPairs = [ordered]@{
    SystemRoot = $env:SystemRoot; windir = $env:windir
    ComSpec = $env:ComSpec; PATHEXT = $env:PATHEXT; PATH = $env:PATH
    TEMP = "C:\Windows\Temp"; TMP = "C:\Windows\Temp"
    USERPROFILE = $home2; APPDATA = "$home2\AppData\Roaming"
    LOCALAPPDATA = "$home2\AppData\Local"; USERNAME = $AgentUser
}
$envBlock = (($envPairs.GetEnumerator() |
              ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "`0") + "`0"
$work = "C:\Windows\Temp"

# --- fixture file: 1 bi deny-full, 1 cho doc ---
$tmp = "C:\Windows\Temp\troly-s4-test"
New-Item -ItemType Directory -Force $tmp | Out-Null
$secretFp = Join-Path $tmp "secret.txt"; "TOP-SECRET-123" | Set-Content $secretFp
icacls $secretFp /inheritance:r /grant "${env:USERNAME}:(F)" `
       /deny "${AgentUser}:(F)" /Q | Out-Null
$allowFp = Join-Path $tmp "allow.txt"; "HELLO-OK" | Set-Content $allowFp
icacls $allowFp /grant "${AgentUser}:(RX)" /Q | Out-Null

function Spawn-ReadAll($cmdline) {
    # spawn -> doc het stdout toi khi con exit -> kill -> tra @{out|err}
    $r = [TroLy.AgentSpawn]::Start($AgentUser, $pw, $cmdline, $work, $envBlock)
    if ($r.Error) { return @{ err = $r.Error } }
    $out = ([IO.StreamReader]::new(
        [IO.FileStream]::new($r.StdoutRead, [IO.FileAccess]::Read),
        [Text.Encoding]::UTF8)).ReadToEnd()
    [TroLy.AgentSpawn]::Kill($r.Job, $r.Process)
    return @{ out = $out }
}

# --- 2. spawn cross-user ---
$r = Spawn-ReadAll 'cmd.exe /c whoami'
Check "spawn cross-user" (-not $r.err)
Check "whoami = troly-agent" ($r.out -match "troly-agent")

# --- 3. ACL doc ---
$r = Spawn-ReadAll "cmd.exe /c type `"$secretFp`""
Check "deny-read secret" (-not $r.err -and $r.out -notmatch "TOP-SECRET-123")
$r = Spawn-ReadAll "cmd.exe /c type `"$allowFp`""
Check "read file cho phep" ($r.out -match "HELLO-OK")

# --- 4. ACL ghi (do setup-agent-user cap tren checkout that) ---
$wf = Join-Path $Root "tools\poc-write.txt"
Spawn-ReadAll "cmd.exe /c echo hacked> `"$wf`"" | Out-Null
Start-Sleep -Milliseconds 300
Check "deny-write tools\" (-not (Test-Path $wf))
Remove-Item $wf -Force -ErrorAction SilentlyContinue

$okf = Join-Path $Root "my-course\poc-write.txt"
Spawn-ReadAll "cmd.exe /c echo wrote> `"$okf`"" | Out-Null
Start-Sleep -Milliseconds 300
Check "write my-course\" ((Test-Path $okf) -and
    ((Get-Content $okf -Raw -ErrorAction SilentlyContinue) -match "wrote"))
Remove-Item $okf -Force -ErrorAction SilentlyContinue

# --- 5. stdio 2 chieu + 6. IsAlive/Kill qua Job ---
# Diag truoc: troly-agent nhin thay + chay duoc fakebrain khong?
# (stderr cua con di vao NUL nen bat "2>&1" trong cmd de loi lo ra stdout)
$r2 = Spawn-ReadAll "cmd.exe /c `"dir `"$FakeBin`" 2>&1`""
Write-Host "  dir bin: $((($r2.out -split "`n") | Select-Object -Last 4) -join ' | ')"
$r3 = Spawn-ReadAll 'cmd.exe /c "fakebrain <NUL 2>&1"'
Write-Host "  fakebrain via cmd: $(($r3.out -replace '\s+',' ').Trim())"
$r = [TroLy.AgentSpawn]::Start($AgentUser, $pw, '"fakebrain"', $work, $envBlock)
if ($r.Error) { Write-Host "    (err: $($r.Error))" -ForegroundColor Yellow }
Check "spawn fakebrain" (-not $r.Error)
if (-not $r.Error) {
    $w = [IO.FileStream]::new($r.StdinWrite, [IO.FileAccess]::Write)
    $rr = [IO.StreamReader]::new(
        [IO.FileStream]::new($r.StdoutRead, [IO.FileAccess]::Read),
        [Text.Encoding]::UTF8)
    $b = [Text.Encoding]::UTF8.GetBytes(
        '{"jsonrpc":"2.0","id":42,"method":"initialize","params":{}}' + "`n")
    $w.Write($b, 0, $b.Length); $w.Flush()
    $task = $rr.ReadLineAsync()
    $line = if ($task.Wait(15000)) { $task.Result } else { $null }
    Check "stdio roundtrip (id=42)" ($line -match '"id":42')
    Check "IsAlive" ([TroLy.AgentSpawn]::IsAlive($r.Process))
    [TroLy.AgentSpawn]::Kill($r.Job, $r.Process)
    Start-Sleep -Milliseconds 500
    Check "chet sau kill qua Job" (-not [TroLy.AgentSpawn]::IsAlive($r.Process))
}

# --- 7. sai mat khau -> Error ro rang ---
$r = [TroLy.AgentSpawn]::Start($AgentUser, "Sai-Mat-Khau-123!",
                             'cmd.exe /c echo x', $work, $envBlock)
Check "sai mat khau -> Error" (-not [string]::IsNullOrEmpty($r.Error))

# --- 8. e2e: chat-bridge.ps1 that spawn fakebrain trong vung cat ---
$bp = $null
try {
    @{ id = "fake"; cmd = "fakebrain"; args = @() } |
        ConvertTo-Json -Compress |
        Set-Content (Join-Path $Root "brain.json") -Encoding UTF8
    $brOut = Join-Path $tmp "bridge.out"; $brErr = Join-Path $tmp "bridge.err"
    $bp = Start-Process pwsh -PassThru -WindowStyle Hidden `
        -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass",
            "-File","tools\chat-bridge.ps1","-Port","7699" `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $brOut -RedirectStandardError $brErr
    # token do bridge tu sinh luc khoi dong — cho file xuat hien
    $tokFp = Join-Path $Root ".devin\bridge.token"
    for ($i = 0; $i -lt 40 -and -not (Test-Path $tokFp); $i++) {
        Start-Sleep -Milliseconds 250
    }
    $tok = (Get-Content $tokFp -Raw -ErrorAction SilentlyContinue).Trim()
    $ready = $false
    for ($i = 0; $i -lt 90 -and -not $ready; $i++) {
        try {
            $h = Invoke-RestMethod "http://127.0.0.1:7699/api/health" -TimeoutSec 2
            if ($h.ok -and $h.sessionId) { $ready = $true }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    Check "bridge + sandboxed brain ready" $ready
    if (-not $ready) {
        foreach ($f in @($brOut, $brErr)) {
            if (Test-Path $f) {
                Write-Host "---- $f ----"
                Get-Content $f -Tail 20 -ErrorAction SilentlyContinue
            }
        }
    }
    if ($ready) {
        $evs = (Invoke-RestMethod `
            "http://127.0.0.1:7699/api/poll?since=0&token=$tok" `
            -TimeoutSec 5).events
        # co event "khong sandbox duoc" = da roi ve duong thuong -> fail
        Check "khong roi ve spawn thuong" (
            -not ($evs | Where-Object {
                $_.t -eq "err" -and $_.msg -match "sandbox" }))
        Invoke-RestMethod "http://127.0.0.1:7699/api/prompt?token=$tok" `
            -Method Post -ContentType "application/json" `
            -Body '{"text":"hi"}' -TimeoutSec 5 | Out-Null
        $done = $false; $evs = @()
        for ($i = 0; $i -lt 60 -and -not $done; $i++) {
            $evs = (Invoke-RestMethod `
                "http://127.0.0.1:7699/api/poll?since=0&token=$tok" `
                -TimeoutSec 5).events
            if ($evs | Where-Object { $_.t -eq "done" }) { $done = $true }
            else { Start-Sleep -Milliseconds 500 }
        }
        Check "prompt -> done" $done
        # fake brain stream "pong:<username>" — chung minh nao chay duoi
        # troly-agent that chu khong phai user chu
        $pong = $evs | Where-Object { $_.t -eq "text" -and $_.text -match "pong" } |
                Select-Object -First 1
        Check "nao chay duoi troly-agent" ($pong.text -match "troly-agent")
    }
} finally {
    if ($bp) { Stop-Process -Id $bp.Id -Force -ErrorAction SilentlyContinue }
}

Write-Host ""
Write-Host "== $script:pass pass / $script:fail fail =="
exit ($(if ($script:fail -gt 0) { 1 } else { 0 }))
