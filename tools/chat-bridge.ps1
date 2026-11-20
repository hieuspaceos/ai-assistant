# chat-bridge.ps1 — cầu nối giữa chat UI trong portal và "não" AI qua ACP.
#
# Chạy một agent CLI nói chuẩn ACP (JSON-RPC qua stdin/stdout) như process
# con — mặc định `devin acp`, đổi được sang não khác qua brain.json ở gốc
# project hoặc POST /api/brain. Nhận prompt từ browser qua HTTP,
# đẩy các event (text stream, tool call, xin phép) về browser bằng polling.
# Bản PowerShell này y hệt tools/chat-bridge.py (dùng cho macOS/Linux).
#
# Endpoints (mặc định port 7682, chỉ localhost):
#   GET  /api/poll?since=N -> {"events": [...], "next": M}
#   POST /api/prompt       -> {"text": "..."} gửi lời nhắn
#   POST /api/respond      -> {"id": N, "optionId": "..."} trả lời xin phép
#   GET  /api/health       -> {"ok": true, "sessionId": ...}
#   GET  /api/brain        -> não hiện tại + danh sách preset (kèm đã cài chưa)
#   POST /api/brain        -> {"id": <preset>} hoặc {"cmd","args"} đổi não

param(
    [int]$Port = 7682,
    [string]$WorkDir = (Split-Path -Parent $PSScriptRoot),
    [string]$Devin = "devin"
)

$ErrorActionPreference = "Stop"

# Chỉ trang local (host loopback, mọi port — portal có thể chạy port khác
# khi 8080 bận) được gọi API từ browser; request không có Origin
# (Invoke-RestMethod từ agent) vẫn cho qua — trang web lạ bị chặn 403.
function Test-LocalOrigin($origin) {
    if ([string]::IsNullOrEmpty($origin)) { return $false }
    try { $h = ([uri]$origin).Host } catch { return $false }
    return $h -eq "localhost" -or $h -eq "127.0.0.1" -or $h -eq "::1" -or $h.EndsWith(".localhost")
}

# ---------- não AI qua ACP ----------
$BrainFp = Join-Path $WorkDir "brain.json"
# Các não biết nói ACP mà onboarding gợi ý. requires = binary phải có trên
# PATH thì preset mới coi là "đã cài" (adapter qua npx vẫn cần CLI gốc để
# đăng nhập — vd codex-acp cần `codex`).
$BrainPresets = @(
    [pscustomobject]@{ id="devin";   label="Devin";                   cmd="devin";   args=@("acp","--process-model","in-process");        terminal="devin";   requires=@("devin");
        desc=@{ vi="Não mặc định — đi kèm bộ trợ lý này";                              en="Default brain — ships with this assistant" } }
    [pscustomobject]@{ id="gemini";  label="Gemini CLI (Google)";     cmd="gemini";  args=@("--acp");                                      terminal="gemini";  requires=@("gemini");
        desc=@{ vi="Nói ACP trực tiếp — cần cài Gemini CLI trước";                     en="Speaks ACP natively — needs Gemini CLI installed" } }
    [pscustomobject]@{ id="codex";   label="Codex CLI (OpenAI)";      cmd="npx";     args=@("-y","@agentclientprotocol/codex-acp");        terminal="codex";   requires=@("npx","codex");
        desc=@{ vi="Qua adapter codex-acp — cần cài + đăng nhập Codex CLI";            en="Via codex-acp adapter — needs Codex CLI installed and signed in" } }
    [pscustomobject]@{ id="claude";  label="Claude Code (Anthropic)"; cmd="npx";     args=@("-y","@agentclientprotocol/claude-agent-acp"); terminal="claude";  requires=@("npx","claude");
        desc=@{ vi="Qua adapter claude-agent-acp — cần cài + đăng nhập Claude Code";   en="Via claude-agent-acp adapter — needs Claude Code installed and signed in" } }
    [pscustomobject]@{ id="opencode"; label="OpenCode";               cmd="opencode"; args=@("acp");                                       terminal="opencode"; requires=@("opencode");
        desc=@{ vi="Nói ACP trực tiếp — cần cài OpenCode";                             en="Speaks ACP natively — needs OpenCode installed" } }
    [pscustomobject]@{ id="goose";   label="Goose (Block)";           cmd="goose";   args=@("acp");                                        terminal="goose";   requires=@("goose");
        desc=@{ vi="Nói ACP trực tiếp — cần cài Goose";                                en="Speaks ACP natively — needs Goose installed" } }
)

function Get-Brain {
    # brain.json → não đang dùng; id khớp preset thì lấy preset làm nền;
    # thiếu file/cmd → preset devin (tên binary vẫn override được bằng
    # tham số -Devin như trước). Y hệt load_brain() trong chat-bridge.py.
    try { $b = Get-Content $BrainFp -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $b = $null }
    if ($b -and -not $b.cmd -and $b.id) {
        $p = $BrainPresets | Where-Object { $_.id -eq $b.id } | Select-Object -First 1
        if ($p) { $b = $p }
    }
    if ($b -and $b.cmd) {
        if (-not $b.PSObject.Properties["args"]) { $b | Add-Member -NotePropertyName args -NotePropertyValue @() }
        if (-not $b.PSObject.Properties["terminal"] -or -not $b.terminal) { $b | Add-Member -NotePropertyName terminal -NotePropertyValue $b.cmd -Force }
        return $b
    }
    return [pscustomobject]@{ id="devin"; label="Devin"; cmd=$Devin; args=@("acp","--process-model","in-process"); terminal=$Devin }
}

$script:SessionId = $null
$script:NextId = 10
$script:AcpDead = $false
$script:AcpProc = $null
$script:AcpSub = $null
$script:EventStore = New-Object System.Collections.ArrayList
$script:EventBase = 0          # số event đã cắt khỏi đầu — cursor poll đếm tuyệt đối
$MaxEvents = 3000

# Dòng stdout của acp chạy qua event -> queue, main loop xử lý
$lineQueue = New-Object 'System.Collections.Concurrent.ConcurrentQueue[string]'

function Send-Acp($obj) {
    $json = ($obj | ConvertTo-Json -Depth 20 -Compress)
    # Ghi byte UTF-8 thẳng vào stream — không qua WriteLine vì WriteLine
    # dùng Console.InputEncoding (OEM codepage) làm hỏng tiếng Việt có dấu.
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json + "`n")
    $script:AcpProc.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
    $script:AcpProc.StandardInput.BaseStream.Flush()
}

function Call-Acp($method, $params) {
    $id = $script:NextId; $script:NextId += 1
    Send-Acp ([ordered]@{ jsonrpc = "2.0"; id = $id; method = $method; params = $params })
    return $id
}

function Push-Event($ev) {
    [void]$script:EventStore.Add($ev)
    if ($script:EventStore.Count -gt $MaxEvents) {
        $excess = $script:EventStore.Count - $MaxEvents
        $script:EventStore.RemoveRange(0, $excess)
        $script:EventBase += $excess
    }
}

function Start-Brain {
    # Bật (hoặc đổi) não: giết agent cũ nếu còn sống, spawn theo brain.json
    # rồi bắt tay ACP chuẩn (initialize + session/new).
    $brain = Get-Brain
    # HasExited ném lỗi trên process chưa start được (spawn fail lần trước)
    # → bọc try: giết được thì giết, không thì bỏ qua
    try { if ($script:AcpProc -and -not $script:AcpProc.HasExited) { $script:AcpProc.Kill() } } catch {}
    if ($script:AcpSub) {
        try { Unregister-Event -SourceIdentifier $script:AcpSub.SourceIdentifier } catch {}
        $script:AcpSub = $null
    }
    $script:SessionId = $null
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $brain.cmd
    $psi.Arguments = [string]::Join(" ", @($brain.args))
    $psi.WorkingDirectory = $WorkDir
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    # KHÔNG redirect stderr: buffer đầy mà không ai đọc → agent bị khóa chết.
    # (bản .py dùng stderr=DEVNULL tương đương)
    $psi.UseShellExecute = $false
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $script:AcpProc = New-Object System.Diagnostics.Process
    $script:AcpProc.StartInfo = $psi
    try { $null = $script:AcpProc.Start() } catch {
        # binary não chưa cài → báo UI, bridge vẫn sống để học viên đổi não
        $script:AcpDead = $true
        Push-Event ([ordered]@{ t = "err"; msg = "không chạy được '$($brain.cmd)' — não trợ lý chưa cài. Vào mục Cài đặt đổi sang não khác." })
        return
    }
    $script:AcpDead = $false
    $script:AcpProc.StandardInput.AutoFlush = $true
    $script:AcpSub = Register-ObjectEvent -InputObject $script:AcpProc -EventName OutputDataReceived -MessageData $lineQueue -Action {
        if ($null -ne $EventArgs.Data -and $EventArgs.Data.Trim()) {
            $Event.MessageData.Enqueue($EventArgs.Data.Trim())
        }
    }
    $script:AcpProc.BeginOutputReadLine()
    Call-Acp "initialize" @{
        protocolVersion = 1
        clientCapabilities = @{
            fs = @{ readTextFile = $false; writeTextFile = $false }
            terminal = $false
        }
    } | Out-Null
    Call-Acp "session/new" @{ cwd = $WorkDir; mcpServers = @() } | Out-Null
}

function Drain-Queue {
    $line = $null
    while ($lineQueue.TryDequeue([ref]$line)) {
        try { $m = $line | ConvertFrom-Json } catch { continue }
        # Kết quả của session/new (bất kể id nào)
        if ($null -eq $script:SessionId -and $m.result -and $m.result.sessionId) {
            $script:SessionId = $m.result.sessionId
            Push-Event ([ordered]@{ t = "ready"; sessionId = $script:SessionId })
            continue
        }
        if ($m.error) {
            Push-Event ([ordered]@{ t = "err"; msg = "$($m.error.message)" })
            continue
        }
        # Kết quả cuối của một lượt prompt
        if ($m.id -and $m.result -and ($m.result.PSObject.Properties.Name -contains "stopReason")) {
            Push-Event ([ordered]@{ t = "done" })
            continue
        }
        # Agent hỏi xin phép -> chuyển cho UI
        if ($m.method -eq "session/request_permission") {
            $p = $m.params; $tc = $p.toolCall
            $opts = @()
            foreach ($o in $p.options) {
                $opts += [ordered]@{ optionId = $o.optionId; name = $o.name; kind = $o.kind }
            }
            Push-Event ([ordered]@{
                t = "perm"; id = $m.id
                title = (if ($tc.title) { $tc.title } else { "Trợ lý muốn làm một việc" })
                options = $opts
            })
            continue
        }
        if ($m.method -ne "session/update") {
            # Request lạ từ agent (vd: fs/read_text_file, terminal/*) —
            # trả lời lỗi ngay, nếu không agent chờ vô hạn.
            if ($null -ne $m.id -and $m.method) {
                Send-Acp ([ordered]@{ jsonrpc = "2.0"; id = $m.id; error = @{ code = -32601; message = "client không hỗ trợ $($m.method)" } })
            }
            continue
        }
        $u = $m.params.update
        $su = $u.sessionUpdate
        if ($su -eq "agent_message_chunk" -and $u.content.text) {
            Push-Event ([ordered]@{ t = "text"; text = $u.content.text })
        } elseif ($su -eq "tool_call") {
            Push-Event ([ordered]@{ t = "tool"; title = (if ($u.title) { $u.title } else { "đang làm việc" }); status = "in_progress" })
        } elseif ($su -eq "tool_call_update" -and ($u.status -eq "completed" -or $u.status -eq "failed")) {
            Push-Event ([ordered]@{ t = "tool"; title = "$($u.title)"; status = $u.status })
        }
    }
}

# ---------- permissions.json + connections.json (Phase 0) ----------
$McDir = Join-Path $WorkDir "my-course"
$PermFp = Join-Path $McDir "permissions.json"
$ConnFp = Join-Path $McDir "connections.json"
$ConfigFp = Join-Path $McDir "config.json"
$SkillPacks = Join-Path $WorkDir ".devin\skill-packs"
$SkillsDir = Join-Path $WorkDir ".devin\skills"

function Load-Json($fp, $fallback) {
    try { return Get-Content $fp -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $fallback }
}
function Save-Json($fp, $obj) {
    # Ghi ra file tạm rồi đổi tên (atomic — crash giữa chừng không corrupt),
    # UTF8 KHÔNG BOM — file có BOM làm json.load() của Python/jq đọc hỏng.
    $json = $obj | ConvertTo-Json -Depth 20
    $tmp = "$fp.tmp"
    [IO.File]::WriteAllText($tmp, $json, [Text.UTF8Encoding]::new($false))
    Move-Item -Force $tmp $fp
}
function Expand-Path($p) {
    $p = [string]$p
    if ($p.StartsWith("~")) { $p = Join-Path $env:USERPROFILE $p.Substring(1).TrimStart('/','\') }
    return $p
}
function Run-Probe($probe) {
    # msg hiện thẳng dưới tên app trong panel Cài đặt của học viên —
    # viết bằng lời thường, không thuật ngữ (token/MCP/extension…)
    if (-not $probe) { return @{ ok = $false; msg = "chưa cài — cứ nhờ trợ lý trong chat, nó làm giúp" } }
    try {
        if ($probe.type -eq "http") {
            $d = Invoke-RestMethod -Uri $probe.url -TimeoutSec 4
            if (-not $probe.expect_key) {
                $ok = $true
            } else {
                $v = $d.($probe.expect_key)
                $ok = ("$v" -eq "$($probe.expect_val)")
            }
            return @{ ok = $ok; msg = $(if ($ok) { "đang hoạt động" } else { "chưa nối — mở trình duyệt rồi bật tiện ích Trợ Lý AI" }) }
        }
        if ($probe.type -eq "tabs") {
            # Có trang web đang mở khớp URL — vd: đã mở Zalo/Outlook trong browser
            $d = Invoke-RestMethod -Uri "http://127.0.0.1:7684/api/browser" -Method Post `
                 -ContentType "application/json" -Body '{"action":"tabs"}' -TimeoutSec 6
            if (-not $d.ok) {
                return @{ ok = $false; msg = "trình duyệt chưa nối — mở Chrome/Edge lên trước" }
            }
            $needle = ([string]$probe.url_contains).ToLower()
            $ok = ($needle.Length -gt 0) -and [bool](@($d.tabs) | Where-Object { ([string]$_.url).ToLower().Contains($needle) } | Select-Object -First 1)
            return @{ ok = $ok; msg = $(if ($ok) { "đang mở sẵn — nhờ được ngay" } else { "chưa mở — bấm nút Mở trang rồi đăng nhập" }) }
        }
        if ($probe.type -eq "zalo-oa") {
            $creds = Load-Json (Join-Path $WorkDir ".devin\secrets.local.json") @{}
            $tok = [string]($creds."zalo-oa".access_token)
            if (-not $tok) {
                return @{ ok = $false; msg = "chưa có mã kết nối — nhờ trợ lý trong chat cài giúp" }
            }
            try {
                $d = Invoke-RestMethod -Uri "https://openapi.zalo.me/v2.0/oa/getoa" -Headers @{ access_token = $tok } -TimeoutSec 8
                $ok = ($d.error -eq 0)
            } catch { $ok = $false }
            return @{ ok = $ok; msg = $(if ($ok) { "đang kết nối" } else { "mã kết nối sai hoặc hết hạn — nhờ trợ lý làm mới giúp" }) }
        }
        if ($probe.type -eq "path") {
            $ok = Test-Path (Expand-Path $probe.path)
            return @{ ok = $ok; msg = $(if ($ok) { "thấy folder" } else { "không thấy folder này" }) }
        }
        if ($probe.type -eq "mcp") {
            $cfg = Join-Path $WorkDir ".devin\mcp_config.local.json"
            $j = Load-Json $cfg @{}
            $servers = if ($j.mcpServers) { $j.mcpServers } elseif ($j.servers) { $j.servers } else { @{} }
            $ok = $null -ne $servers.($probe.name)
            return @{ ok = $ok; msg = $(if ($ok) { "đã cài sẵn" } else { "chưa cài — nhờ trợ lý trong chat cài giúp" }) }
        }
        if ($probe.type -eq "wp") {
            # WordPress REST: đọc credentials từ secrets.local.json (gitignored)
            $creds = Load-Json (Join-Path $WorkDir ".devin\secrets.local.json") @{}
            $wp = $creds.wordpress
            if (-not $wp -or -not $wp.url -or -not $wp.user -or -not $wp.app_password) {
                return @{ ok = $false; msg = "chưa có thông tin đăng nhập — nhờ trợ lý cài giúp" }
            }
            $pw = ([string]$wp.app_password) -replace ' ', ''
            $auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$($wp.user):$pw"))
            try {
                Invoke-RestMethod -Uri ($wp.url.TrimEnd('/') + "/wp-json/wp/v2/users/me") -Headers @{ Authorization = "Basic $auth" } -TimeoutSec 8 | Out-Null
                return @{ ok = $true; msg = "đang kết nối" }
            } catch {
                return @{ ok = $false; msg = "sai thông tin đăng nhập, hoặc không vào được site" }
            }
        }
    } catch {
        return @{ ok = $false; msg = "có lỗi khi kiểm tra — nhờ trợ lý xem giúp" }
    }
    return @{ ok = $false; msg = "kiểu kết nối lạ — nhờ trợ lý xem" }
}

# ---------- HTTP server ----------
function Send-Json($ctx, $obj, [int]$code = 200) {
    $body = [System.Text.Encoding]::UTF8.GetBytes(($obj | ConvertTo-Json -Depth 20 -Compress))
    $res = $ctx.Response
    $res.StatusCode = $code
    $res.ContentType = "application/json; charset=utf-8"
    $origin = $ctx.Request.Headers["Origin"]
    if (Test-LocalOrigin $origin) {
        $res.Headers.Add("Access-Control-Allow-Origin", $origin)
        $res.Headers.Add("Vary", "Origin")
    }
    $res.Headers.Add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    $res.Headers.Add("Access-Control-Allow-Headers", "Content-Type")
    $res.ContentLength64 = $body.Length
    $res.OutputStream.Write($body, 0, $body.Length)
    $res.OutputStream.Close()
}

Start-Brain

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://127.0.0.1:$Port/")
try { $listener.Start() } catch {
    Write-Host "Không mở được cổng $Port — có chương trình nào đang giữ nó rồi."
    exit 1
}
Write-Host "chat-bridge: http://localhost:$Port  (cwd=$WorkDir)"

try {
    while ($listener.IsListening) {
        $ctx = $null
        try { $ctx = $listener.GetContext() } catch { break }
        Drain-Queue
        try {
            $path = $ctx.Request.Url.AbsolutePath
            $origin = $ctx.Request.Headers["Origin"]
            if ($null -ne $origin -and -not (Test-LocalOrigin $origin)) {
                Send-Json $ctx @{ err = "origin không được phép" } 403
                continue
            }
            if ($ctx.Request.HttpMethod -eq "OPTIONS") {
                $ctx.Response.StatusCode = 204
                if (Test-LocalOrigin $origin) {
                    $ctx.Response.Headers.Add("Access-Control-Allow-Origin", $origin)
                    $ctx.Response.Headers.Add("Vary", "Origin")
                }
                $ctx.Response.Headers.Add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                $ctx.Response.Headers.Add("Access-Control-Allow-Headers", "Content-Type")
                $ctx.Response.OutputStream.Close()
                continue
            }
            if ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/health") {
                Send-Json $ctx @{ ok = $true; sessionId = $script:SessionId; brain = (Get-Brain).id }
            }
            elseif ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/brain") {
                $cur = Get-Brain
                $pres = @()
                foreach ($p in $BrainPresets) {
                    $inst = $true
                    foreach ($r in $p.requires) {
                        if (-not (Get-Command $r -ErrorAction SilentlyContinue)) { $inst = $false }
                    }
                    $pres += [ordered]@{
                        id = $p.id; label = $p.label; desc = $p.desc
                        cmd_display = ("$($p.cmd) $($p.args -join ' ')").Trim()
                        installed = $inst
                    }
                }
                Send-Json $ctx @{
                    current = @{ id = $cur.id; label = $cur.label; cmd = $cur.cmd; args = @($cur.args); terminal = $cur.terminal }
                    presets = $pres
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/poll") {
                $since = 0
                [void][int]::TryParse($ctx.Request.QueryString["since"], [ref]$since)
                $total = $script:EventBase + $script:EventStore.Count
                # reset: cursor client trỏ ngoài vùng event còn giữ —
                # thường là bridge vừa restart → replay toàn bộ cho client dựng lại
                $reset = ($since -lt 0) -or ($since -lt $script:EventBase) -or ($since -gt $total)
                if ($reset) {
                    $evs = @($script:EventStore)
                    Send-Json $ctx @{ events = $evs; next = $total; reset = $true }
                } else {
                    $idx = $since - $script:EventBase
                    $evs = @($script:EventStore.GetRange($idx, $script:EventStore.Count - $idx))
                    Send-Json $ctx @{ events = $evs; next = $total; reset = $false }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/permissions") {
                $q = Load-Json $PermFp @{ folders = @() }
                if (-not $q.PSObject.Properties["folders"]) { $q | Add-Member -NotePropertyName folders -NotePropertyValue @() }
                Send-Json $ctx $q
            }
            elseif ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/connections") {
                $k = Load-Json $ConnFp @{ apps = @() }
                if (-not $k.PSObject.Properties["apps"]) { $k | Add-Member -NotePropertyName apps -NotePropertyValue @() }
                Send-Json $ctx $k
            }
            elseif ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/config") {
                Send-Json $ctx (Load-Json $ConfigFp @{})
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/prompt") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                if ($script:AcpDead -or -not $script:AcpProc -or $script:AcpProc.HasExited) {
                    # não chết (process rớt hoặc chưa cài) → thử bật lại một lần
                    Start-Brain
                    Send-Json $ctx @{ err = "đang khởi động lại trợ lý — gửi lại sau vài giây" } 503
                } elseif (-not $script:SessionId) {
                    Send-Json $ctx @{ err = "chưa có session" } 503
                } else {
                    try {
                        Call-Acp "session/prompt" @{
                            sessionId = $script:SessionId
                            prompt = @(@{ type = "text"; text = $body.text })
                        } | Out-Null
                        Send-Json $ctx @{ ok = $true }
                    } catch {
                        Send-Json $ctx @{ err = "trợ lý đã dừng — chạy lại file start" } 503
                    }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/brain") {
                # Đổi não: {"id": <preset>} hoặc lệnh tự nhập {"cmd","args","terminal"}.
                # cmd chỉ cho phép tên lệnh trần (không path) — trang local bị
                # nhiễm vẫn không trỏ được vào script lạ trên máy.
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $bid = ([string]$body.id).Trim()
                $preset = $BrainPresets | Where-Object { $_.id -eq $bid } | Select-Object -First 1
                if ($preset) {
                    $b = [ordered]@{ id = $preset.id; label = $preset.label; cmd = $preset.cmd; args = @($preset.args); terminal = $preset.terminal }
                    $requires = @($preset.requires)
                } else {
                    $cmd = ([string]$body.cmd).Trim()
                    if ($cmd -notmatch '^[A-Za-z0-9_.-]+$') {
                        Send-Json $ctx @{ err = "lệnh não không hợp lệ — chỉ nhận tên lệnh" } 400
                        continue
                    }
                    $bArgs = @()
                    if ($body.args) {
                        $bArgs = @($body.args | Select-Object -First 20 | ForEach-Object {
                            $a = [string]$_
                            if ($a.Length -gt 200) { $a = $a.Substring(0, 200) }
                            $a
                        })
                    }
                    $label = if ($body.label) { [string]$body.label } else { $cmd }
                    if ($label.Length -gt 60) { $label = $label.Substring(0, 60) }
                    $term = if ($body.terminal) { [string]$body.terminal } else { $cmd }
                    if ($term.Length -gt 60) { $term = $term.Substring(0, 60) }
                    $b = [ordered]@{ id = $(if ($bid) { $bid } else { "custom" }); label = $label; cmd = $cmd; args = $bArgs; terminal = $term }
                    $requires = @($cmd)
                }
                $missing = @($requires | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
                if ($missing.Count -gt 0) {
                    Send-Json $ctx @{ err = "chưa cài trên máy: $($missing -join ', ')"; missing = $missing } 404
                } else {
                    Save-Json $BrainFp $b
                    Start-Brain
                    Send-Json $ctx @{ ok = $true; brain = $b }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/respond") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                if ($body.optionId -eq "__cancel__") {
                    # học viên từ chối / card không có nút nào → báo cancel cho agent
                    $payload = [ordered]@{
                        jsonrpc = "2.0"; id = $body.id
                        error = @{ code = -32800; message = "học viên không đồng ý" }
                    }
                } else {
                    $payload = [ordered]@{
                        jsonrpc = "2.0"; id = $body.id
                        result = @{ outcome = @{ outcome = "selected"; optionId = $body.optionId } }
                    }
                }
                try { if (-not $script:AcpDead -and $script:AcpProc -and -not $script:AcpProc.HasExited) { Send-Acp $payload } } catch {}
                Send-Json $ctx @{ ok = $true }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/delete-lesson") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $folder = [string]$body.folder
                if ($folder -notmatch '^[a-zA-Z0-9_-]+$') {
                    Send-Json $ctx @{ err = "tên folder lạ" } 400
                } else {
                    $course = (Resolve-Path (Join-Path $WorkDir "my-course")).Path
                    $target = Join-Path $course $folder
                    if ((Test-Path $target -PathType Container) -and
                        ((Resolve-Path $target).Path.StartsWith($course + [IO.Path]::DirectorySeparatorChar))) {
                        Remove-Item $target -Recurse -Force
                        $mf = Join-Path $course "manifest.json"
                        try {
                            $m = Get-Content $mf -Raw -Encoding UTF8 | ConvertFrom-Json
                            $m.lessons = @($m.lessons | Where-Object { $_.folder -ne $folder })
                            Save-Json $mf $m
                        } catch {}
                        Send-Json $ctx @{ ok = $true }
                    } else {
                        Send-Json $ctx @{ err = "không thấy folder bài" } 404
                    }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/permissions") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $p = Expand-Path ([string]$body.path).Trim()
                $lv = [string]$body.access
                if ($lv -ne "read" -and $lv -ne "read-write") {
                    Send-Json $ctx @{ err = "access phải là read hoặc read-write" } 400
                } elseif (-not (Test-Path $p -PathType Container)) {
                    Send-Json $ctx @{ err = "không thấy folder này trên máy" } 404
                } else {
                    $q = Load-Json $PermFp @{ folders = @() }
                    # so sánh sau Expand-Path — entry cũ ghi "~/Downloads" vẫn khớp được
                    $arr = @($q.folders | Where-Object { (Expand-Path $_.path) -ne $p })
                    $arr += @{ path = $p; access = $lv; note = ([string]$body.note).Substring(0, [Math]::Min(120, ([string]$body.note).Length)) }
                    $q.folders = $arr
                    Save-Json $PermFp $q
                    Send-Json $ctx @{ ok = $true }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/remove-permission") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $p = Expand-Path ([string]$body.path).Trim()
                $q = Load-Json $PermFp @{ folders = @() }
                $q.folders = @($q.folders | Where-Object { (Expand-Path $_.path) -ne $p })
                Save-Json $PermFp $q
                Send-Json $ctx @{ ok = $true }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/connections") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                if (-not $body.app.id) {
                    Send-Json $ctx @{ err = "thiếu app.id" } 400
                } else {
                    $k = Load-Json $ConnFp @{ apps = @() }
                    # thay tại chỗ để giữ thứ tự hiển thị trong panel Cài đặt
                    $idx = -1
                    for ($i = 0; $i -lt @($k.apps).Count; $i++) {
                        if ($k.apps[$i].id -eq $body.app.id) { $idx = $i; break }
                    }
                    if ($idx -ge 0) { $k.apps[$idx] = $body.app }
                    else { $k.apps = @($k.apps) + $body.app }
                    Save-Json $ConnFp $k
                    Send-Json $ctx @{ ok = $true }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/remove-connection") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $k = Load-Json $ConnFp @{ apps = @() }
                $k.apps = @($k.apps | Where-Object { $_.id -ne $body.id })
                Save-Json $ConnFp $k
                Send-Json $ctx @{ ok = $true }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/secrets") {
                # Form "Cài" trong panel Cài đặt: học viên dán app password WP /
                # mã OA… → ghi vào .devin\secrets.local.json (đã gitignore).
                # Chỉ GHI — không endpoint nào đọc secret ra ngoài.
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $appId = [string]$body.app
                if ($appId -notmatch '^[a-z0-9-]+$' -or -not $body.fields) {
                    Send-Json $ctx @{ err = "thiếu app hoặc fields" } 400
                } else {
                    $fp = Join-Path $WorkDir ".devin\secrets.local.json"
                    $creds = Load-Json $fp @{}
                    $entry = @{}
                    if ($creds.$appId) {
                        $creds.$appId.PSObject.Properties | ForEach-Object { $entry[$_.Name] = $_.Value }
                    }
                    $n = 0
                    foreach ($p in $body.fields.PSObject.Properties) {
                        if ($n -ge 10) { break }
                        $v = ([string]$p.Value).Trim()
                        if ($v) { $entry[[string]$p.Name] = $v.Substring(0, [Math]::Min(500, $v.Length)); $n++ }
                    }
                    if (-not $entry.Count) {
                        Send-Json $ctx @{ err = "chưa nhập gì" } 400
                    } else {
                        # Load-Json trả hashtable (file mới) hoặc PSCustomObject
                        # (file đã có) — ghi đúng cách cho từng kiểu
                        if ($creds -is [hashtable]) {
                            $creds[$appId] = $entry
                        } elseif ($creds.PSObject.Properties[$appId]) {
                            $creds.$appId = $entry
                        } else {
                            $creds | Add-Member -NotePropertyName $appId -NotePropertyValue $entry -Force
                        }
                        New-Item -ItemType Directory -Force -Path (Split-Path $fp) | Out-Null
                        Save-Json $fp $creds
                        Send-Json $ctx @{ ok = $true }
                    }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/setup") {
                # Onboarding lần đầu: ngôn ngữ + tên → config.json + skill pack đúng ngôn ngữ
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $lang = [string]$body.language
                $name = ([string]$body.learner_name).Trim()
                if ($name.Length -gt 80) { $name = $name.Substring(0, 80) }
                if ($lang -ne "vi" -and $lang -ne "en") {
                    Send-Json $ctx @{ err = "language phải là vi hoặc en" } 400
                } else {
                    New-Item -ItemType Directory -Force -Path $McDir | Out-Null
                    Save-Json $ConfigFp @{ language = $lang; learner_name = $name }
                    $mf = Join-Path $McDir "manifest.json"
                    try {
                        $m = Get-Content $mf -Raw -Encoding UTF8 | ConvertFrom-Json
                        if ($name) {
                            $m | Add-Member -NotePropertyName learner_name -NotePropertyValue $name -Force
                            Save-Json $mf $m
                        }
                    } catch {}
                    # Skill pack đè lên .devin\skills nhưng skill học viên TỰ
                    # TẠO (không có trong pack) phải giữ: dir cũ backup sang
                    # skills.bak rồi merge phần riêng về.
                    $pack = Join-Path $SkillPacks $lang
                    if (Test-Path $pack -PathType Container) {
                        $bak = "$SkillsDir.bak"
                        if (Test-Path $SkillsDir) {
                            if (Test-Path $bak) { Remove-Item $bak -Recurse -Force }
                            Move-Item $SkillsDir $bak
                        }
                        Copy-Item $pack $SkillsDir -Recurse
                        if (Test-Path $bak) {
                            Get-ChildItem $bak -Directory | ForEach-Object {
                                $dst = Join-Path $SkillsDir $_.Name
                                if (-not (Test-Path $dst)) { Copy-Item $_.FullName $dst -Recurse }
                            }
                        }
                    }
                    Send-Json $ctx @{ ok = $true }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/check-connection") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $k = Load-Json $ConnFp @{ apps = @() }
                $app = $k.apps | Where-Object { $_.id -eq $body.id } | Select-Object -First 1
                if (-not $app) {
                    Send-Json $ctx @{ err = "không thấy app" } 404
                } else {
                    $res = Run-Probe $app.probe
                    # sửa tại chỗ trên object trong mảng — giữ nguyên thứ tự
                    $app | Add-Member -NotePropertyName status -NotePropertyValue $(if ($res.ok) { "connected" } else { "not-connected" }) -Force
                    $app | Add-Member -NotePropertyName check_message -NotePropertyValue $res.msg -Force
                    Save-Json $ConnFp $k
                    Send-Json $ctx $res
                }
            }
            else {
                Send-Json $ctx @{ err = "not found" } 404
            }
        } catch {
            try { Send-Json $ctx @{ err = "$_" } 500 } catch {}
        }
    }
} finally {
    $listener.Stop()
    try { $script:AcpProc.Kill() } catch {}
}
