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
#   GET  /api/health       -> {"ok": true, "brain": ..., "version": ...}
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

# "Chìa khoá nhà" dùng chung cho mọi bridge — start.bat sinh trước; đây
# chỉ là fallback (ghi atomic bằng .NET để không race với bridge khác)
$TokenFp = Join-Path $WorkDir ".devin\bridge.token"
function Get-BridgeToken {
    if (Test-Path $TokenFp) {
        $t = (Get-Content $TokenFp -Raw -Encoding UTF8).Trim()
        if ($t) { return $t }
    }
    # CSPRNG — Get-Random là System.Random (seed ~32bit, đoán được theo
    # thời điểm process); đây là chìa khoá cho mọi API đặc quyền
    $t = ([BitConverter]::ToString(
        [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(24)
    )).Replace('-', '').ToLower()
    New-Item -ItemType Directory -Force -Path (Split-Path $TokenFp) | Out-Null
    try {
        $fs = [IO.File]::Open($TokenFp, [IO.FileMode]::CreateNew)
        $b = [Text.Encoding]::UTF8.GetBytes($t)
        $fs.Write($b, 0, $b.Length); $fs.Close()
        return $t
    } catch [IO.IOException] {
        # Thua race → chờ thằng thắng ghi xong rồi đọc; file tồn tại mà
        # rỗng (ai đó tạo file trống) → ghi thẳng, không có gì để mất.
        Start-Sleep -Milliseconds 50
        $t2 = (Get-Content $TokenFp -Raw -Encoding UTF8).Trim()
        if ($t2) { return $t2 }
        [IO.File]::WriteAllText($TokenFp, $t)
        return $t
    }
}
$BridgeToken = Get-BridgeToken
$env:BRIDGE_TOKEN = $BridgeToken   # não + ttyd kế thừa khi spawn

function Test-Authed($req) {
    # Mọi API ngoại trừ /api/health + OPTIONS phải trình "chìa khoá nhà":
    # header X-Bridge-Token (fetch/curl) hoặc ?token= (một dòng lệnh)
    $tok = $req.Headers["X-Bridge-Token"]
    if (-not $tok) { $tok = $req.QueryString["token"] }
    # constant-time — '-ceq' thoát sớm theo byte đầu khác (timing oracle)
    $a = [Text.Encoding]::UTF8.GetBytes([string]$tok)
    $b = [Text.Encoding]::UTF8.GetBytes($BridgeToken)
    if ($a.Length -ne $b.Length) { return $false }
    $d = 0
    for ($i = 0; $i -lt $a.Length; $i++) { $d = $d -bor ($a[$i] -bxor $b[$i]) }
    return ($d -eq 0)
}
function Get-AppVersion {
    $vf = Join-Path $WorkDir "VERSION"
    if (Test-Path $vf) { $v = (Get-Content $vf -Raw -Encoding UTF8).Trim(); if ($v) { return $v } }
    return "0"
}
function Get-ExtVersion {
    # version extension "đúng" = version trong payload đang chạy
    try { $m = Get-Content (Join-Path $WorkDir "extension\manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json; return $m.version } catch { return $null }
}
# Các não biết nói ACP mà onboarding gợi ý. requires = binary phải có trên
# PATH thì preset mới coi là "đã cài" (adapter qua npx vẫn cần CLI gốc để
# đăng nhập — vd codex-acp cần `codex`).
$BrainPresets = @(
    [pscustomobject]@{ id="devin";   label="Devin";                   cmd="devin";   args=@("acp","--process-model","in-process");        terminal="devin";   requires=@("devin");   cost="paid";
        desc=@{ vi="Não mặc định — đi kèm bộ trợ lý này";                              en="Default brain — ships with this assistant" } }
    [pscustomobject]@{ id="gemini";  label="Gemini CLI (Google)";     cmd="gemini";  args=@("--acp");                                      terminal="gemini";  requires=@("gemini");  cost="free";
        desc=@{ vi="Miễn phí với tài khoản Google cá nhân — não gợi ý cho người mới";  en="Free with a personal Google account — suggested brain for new users" } }
    [pscustomobject]@{ id="codex";   label="Codex CLI (OpenAI)";      cmd="npx";     args=@("-y","@agentclientprotocol/codex-acp");        terminal="codex";   requires=@("npx","codex"); cost="paid";
        desc=@{ vi="Qua adapter codex-acp — cần cài + đăng nhập Codex CLI";            en="Via codex-acp adapter — needs Codex CLI installed and signed in" } }
    [pscustomobject]@{ id="claude";  label="Claude Code (Anthropic)"; cmd="npx";     args=@("-y","@agentclientprotocol/claude-agent-acp"); terminal="claude";  requires=@("npx","claude"); cost="paid";
        desc=@{ vi="Qua adapter claude-agent-acp — cần cài + đăng nhập Claude Code";   en="Via claude-agent-acp adapter — needs Claude Code installed and signed in" } }
    [pscustomobject]@{ id="opencode"; label="OpenCode";               cmd="opencode"; args=@("acp");                                       terminal="opencode"; requires=@("opencode"); cost="byok";
        desc=@{ vi="App miễn phí — cần tự nối model (API key) của bạn";                en="Free app — needs your own model (API key) connected" } }
    [pscustomobject]@{ id="goose";   label="Goose (Block)";           cmd="goose";   args=@("acp");                                        terminal="goose";   requires=@("goose");   cost="byok";
        desc=@{ vi="App miễn phí — cần tự nối model (API key) của bạn";                en="Free app — needs your own model (API key) connected" } }
)

# Interpreter/exec helper không được làm "não" tự nhập — args của chúng
# là code-exec trần (parity BRAIN_CMD_DENY trong cmd_deny.py — file này
# là bản mirror tay, cập nhật khi cmd_deny đổi).
$BrainCmdDeny = @("python3","python","py","sh","bash","zsh","fish","dash",
    "osascript","node","deno","bun","ruby","perl","php","pwsh",
    "powershell","cmd","env","nice","xargs","find","make","rake",
    "npm","npx","yarn","pnpm","gem","pip","pip3","curl","wget",
    "nc","ncat","socat","busybox","open","rundll32","regsvr32",
    "mshta","wscript","cscript","wmic","certutil","bitsadmin",
    "eval","exec","launchctl",
    "ssh","scp","sftp","rsync","ftp","telnet","rlogin","rsh",
    "tmux","screen","script","expect","lldb","gdb","dtrace",
    "automator","swift","sudo","crontab","at","atq","atrm",
    "sandbox-exec","sqlite3","mysql","psql","redis-cli","mongosh",
    "mongo","qlmanage","spctl","codesign",
    "security","pbcopy","pbpaste","screencapture",
    "git","awk","gawk","nawk","mawk","tar","vim","vi","nvim",
    "nano","emacs","less","more","most","man","nohup","setsid",
    "timeout","flock","watch","parallel","shortcuts","xcrun",
    "docker","podman","su","doas",
    # batch audit-3/audit-5 (trước sót — mirror cmd_deny.py):
    "brew","gh","java","jshell","dotnet","mono","lua","luajit",
    "r","rscript","tclsh","groovy","scala","kotlin","xcodebuild",
    "plutil","go","cargo","julia","ipython","pypy","micropython",
    "gjs","qjs","nodemon","tsx","ts-node","bunx","uv","uvx","pipx",
    "conda","poetry","pdm","jupyter","vitest","jest","mocha","clj",
    "clojure","lein","stack","cabal","mise","asdf")
# Họ interpreter hậu tố VERSION (python3.12, perl5.40…) — exact-match
# không bắt được; mirror _BRAIN_CMD_DENY_RE (cmd_deny.py).
$BrainCmdDenyRe = [regex]'(?x)^(?:
    (i?python|pypy|jython|micropython|pyspark)[\d.]*w? | py |
    perl[\d.]* | ruby[\d.]* | php[\d.]* | pip[\d.]* | node(js)?[\d.]* |
    (ba|z|fi|da|k|c|tc)?sh\d* |
    lua(jit)?[\d.]* | tclsh[\d.]* | r(script)?[\d.]* |
    java\w* | jshell | groovy\w* | scala | kotlin\w* | dotnet | mono |
    brew | gh | go | cargo | xcodebuild | plutil | shortcuts |
    bundle | irb | pry | julia | gjs | qjs | runghc | ghci
)$'
function Test-BrainDenied([string]$name) {
    $n = $name.ToLower()
    return ($BrainCmdDeny -contains $n) -or ($n -match $BrainCmdDenyRe)
}

function Get-Brain {
    # brain.json → não đang dùng; id khớp preset thì lấy preset làm nền;
    # thiếu file/cmd → preset devin (tên binary vẫn override được bằng
    # tham số -Devin như trước). Y hệt load_brain() trong chat-bridge.py.
    try { $b = Get-Content $BrainFp -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $b = $null }
    $fromPreset = $false
    if ($b -and -not $b.cmd -and $b.id) {
        $p = $BrainPresets | Where-Object { $_.id -eq $b.id } | Select-Object -First 1
        if ($p) { $b = $p; $fromPreset = $true }
    }
    # cmd/terminal phải là tên lệnh trần; cmd do FILE tự khai nằm trong
    # deny-list cũng rơi về devin — trước đây chỉ check ở POST /api/brain,
    # còn brain.json sửa tay ("/bin/evil", "powershell") vẫn spawn thẳng.
    if ($b -and $b.cmd -and ([string]$b.cmd -match '^[A-Za-z0-9_.-]+$') -and
        ($fromPreset -or -not (Test-BrainDenied ([string]$b.cmd)))) {
        if (-not $b.PSObject.Properties["args"]) { $b | Add-Member -NotePropertyName args -NotePropertyValue @() }
        # terminal cũng qua deny-list: file sửa tay terminal:"powershell"
        # → term-gate.cmd exec shell trần trong ttyd (parity load_brain py).
        if (-not $b.PSObject.Properties["terminal"] -or -not $b.terminal -or
            ([string]$b.terminal -notmatch '^[A-Za-z0-9_.-]+$') -or
            (Test-BrainDenied ([string]$b.terminal))) {
            $b | Add-Member -NotePropertyName terminal -NotePropertyValue $b.cmd -Force
        }
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

# Card xin phép chỉ được trả lời khi đang pending — giống chat-bridge.py:
# /api/respond trước đây nhận id/optionId tuỳ ý → tự duyệt thay học viên.
$script:PermPending = @{}      # id -> @{ options = @(optionId); ts = epoch }
$script:PromptBusy = $false    # serialize /api/prompt — 2 prompt đồng thời → 409
$script:PromptSince = $null    # mốc bắt đầu lượt — cho watchdog tick dưới main loop
$PermTtl = 600                 # perm treo >10 phút coi như chết
$PermMax = 200                 # trần chống phình

# Não treo giữa lượt quá lâu → watchdog giết + mở prompt (parity
# TURN_TIMEOUT bên .py). TROLY_TURN_TIMEOUT giây — override cho test.
$TurnTimeout = 1200
try { if ($env:TROLY_TURN_TIMEOUT) { $TurnTimeout = [int]$env:TROLY_TURN_TIMEOUT } } catch {}

# Consent gate (parity với chat-bridge.py): write đặc quyền qua card do
# bridge tự phát. RESIDUAL: agent cũng gọi /api/respond được — card chặn
# im lặng + bắt nghi thức, respond card nội bộ đòi Origin trình duyệt.
$script:LocalPending = @{}     # "local-<hex>" -> @{ apply = [scriptblock]; ts = epoch }

function New-Gate($title, [scriptblock]$applyFn) {
    if ($script:LocalPending.Count -ge $PermMax) {
        $script:LocalPending.Clear()
    }
    $rid = "local-" + ([BitConverter]::ToString(
        [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(8)
    )).Replace('-', '').ToLower()
    $script:LocalPending[$rid] = @{ apply = $applyFn; ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
    Push-Event ([ordered]@{
        t = "perm"; id = $rid; title = $title
        options = @(
            @{ optionId = "ok"; name = "Đồng ý" },
            @{ optionId = "__cancel__"; name = "Không" })
    })
    return $rid
}

# Folder NHẠY CẢM không được cấp quyền dù request hợp lệ — card xác nhận
# không bảo vệ được người bấm đại "Đồng ý" (parity path_sensitive() py).
function Test-SensitivePath($p) {
    $rpl = [IO.Path]::GetFullPath([string]$p).TrimEnd('\', '/').ToLower()
    $home = [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\', '/')
    if ($rpl -match '^[a-z]:$' -or $rpl -eq $home.ToLower()) { return $true }
    $sens = @("$home\.ssh", "$home\.gnupg", "$home\.aws", "$home\.kube",
        "$home\.config\gh", "$home\.claude", "$home\.codex", "$home\.gemini",
        "$home\.opencode", "$home\.config\opencode", "$home\.config\devin",
        "$home\AppData\Local\devin",
        "$env:LOCALAPPDATA\Google\Chrome\User Data",
        "$env:LOCALAPPDATA\Microsoft\Edge\User Data",
        "$env:APPDATA\Mozilla\Firefox",
        "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data",
        "$env:LOCALAPPDATA\Arc\User Data",
        "$env:LOCALAPPDATA\Vivaldi\User Data",
        "$env:APPDATA\Opera Software",
        "$env:APPDATA\Microsoft\Credentials",
        "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup",
        "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp",
        # binary chạy ngoài mọi hàng rào — ghi được = code thoát sandbox
        "$env:WINDIR", "$env:ProgramFiles", "${env:ProgramFiles(x86)}",
        "$env:LOCALAPPDATA\Programs")
    foreach ($s in $sens) {
        if (-not $s) { continue }
        $sl = $s.TrimEnd('\', '/').ToLower()
        # Hai chiều: path NẰM TRONG folder nhạy cảm hoặc CHỨA folder nhạy
        # cảm — grant "AppData\Local" mà chỉ so một chiều sẽ đọc hết Chrome
        # User Data (vô hiệu toàn bộ deny-list con).
        if ($rpl -eq $sl -or $rpl.StartsWith($sl + '\') -or
            $sl.StartsWith($rpl + '\')) { return $true }
    }
    return $false
}

# read-write trong/trùm folder mã nguồn = ghi được tools\*.ps1 → code chạy
# ngoài mọi hàng rào (parity rw_grant_ok trong chat-bridge.py). Path nằm
# trong vùng writable sẵn (my-course…) thì cho qua — thừa nhưng vô hại.
function Test-RwGrantOk($p) {
    $rpl = [IO.Path]::GetFullPath([string]$p).TrimEnd('\', '/').ToLower()
    $cwdl = [IO.Path]::GetFullPath($WorkDir).TrimEnd('\', '/').ToLower()
    if ($rpl -ne $cwdl -and -not $rpl.StartsWith($cwdl + '\') -and
        -not $cwdl.StartsWith($rpl + '\')) { return $true }
    foreach ($d in @("my-course", ".devin\skills", ".logs")) {
        $w = [IO.Path]::GetFullPath((Join-Path $WorkDir $d)).TrimEnd('\', '/').ToLower()
        if ($rpl -eq $w -or $rpl.StartsWith($w + '\')) { return $true }
    }
    return $false
}

# Dòng stdout của acp chạy qua event -> queue, main loop xử lý
$lineQueue = New-Object 'System.Collections.Concurrent.ConcurrentQueue[string]'

# ---------- sandbox: spawn não dưới user hạn chế "troly-agent" ----------
# Khi .devin\agent-user.cred tồn tại (setup-agent-user.ps1 đã chạy), não
# được spawn bằng CreateProcessWithLogonW dưới user kém quyền — stdio ACP
# đi qua anonymous pipe (handles kernel object, inherit cross-user được).
# Bridge kill bằng Job Object handle của chính nó tạo (KHÔNG phải
# OpenProcess/TerminateProcess — non-admin không mở được process user khác).
# Job tạo kèm KILL_ON_JOB_CLOSE-ish: TerminateJobObject giết cả cây con.
$script:AcpIn = $null      # FileStream ghi vào stdin não (chỉ sandbox)
$script:AcpOut = $null     # stdout reader của não (chỉ sandbox)
$script:AcpHandle = [IntPtr]::Zero   # process handle (creator = full access)
$script:AcpJob = [IntPtr]::Zero      # Job Object → kill tree
$script:AcpTask = $null    # ReadLineAsync đang chờ (chỉ sandbox)

$AgentCredFp = Join-Path $WorkDir ".devin\agent-user.cred"

function Get-AgentCred {
    # @{user, password} hoặc $null. Cred là DPAPI blob — chỉ đúng Windows
    # user của học viên giải mã được (troly-agent đọc file cũng vô dụng).
    if ($env:TROLY_NO_SANDBOX -eq "1" -or -not (Test-Path $AgentCredFp)) {
        return $null
    }
    try {
        $sec = ConvertTo-SecureString (Get-Content $AgentCredFp -Raw).Trim()
        $pw = [Net.NetworkCredential]::new("x", $sec).Password
        if (-not $pw) { return $null }
        return @{ user = "troly-agent"; password = $pw }
    } catch { return $null }
}

# C# spawn helper — CreateProcessWithLogonW + anonymous pipes + Job Object.
# Add-Type compile một lần khi script chạy (cached theo type name).
if (-not ([System.Management.Automation.PSTypeName]"TroLy.AgentSpawn").Type) {
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace TroLy {
public static class AgentSpawn {
    [StructLayout(LayoutKind.Sequential)]
    struct SA { public int n; public IntPtr sd; public bool inherit; }
    [StructLayout(LayoutKind.Sequential)]
    struct PI { public IntPtr proc, thread; public int pid, tid; }
    [StructLayout(LayoutKind.Sequential)]
    struct SI {
        public int cb; public string reserved, desktop, title;
        public int x, y, xSize, ySize, xCnt, yCnt, fill, flags;
        public short show, res2; public IntPtr res2p;
        public IntPtr inH, outH, errH;
    }
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CreatePipe(out IntPtr r, out IntPtr w, ref SA sa, uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool DuplicateHandle(IntPtr srcP, IntPtr src, IntPtr dstP,
        out IntPtr dst, uint access, bool inherit, uint options);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateProcessWithLogonW(string user, string domain,
        string password, int logonFlags, string app, string cmdline,
        int flags, IntPtr env, string cwd, ref SI si, out PI pi);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr attr, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr proc);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateJobObject(IntPtr job, uint exitCode);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateProcess(IntPtr proc, uint exitCode);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetExitCodeProcess(IntPtr proc, out int code);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFileW(string name, uint access, uint share,
        ref SA sa, uint disp, uint flags, IntPtr tmpl);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(IntPtr job, int cls,
        IntPtr info, uint len);

    [StructLayout(LayoutKind.Sequential)]
    struct JOBBASIC {
        public long pTime, jTime;
        public uint flags, minWS, maxWS, active, affinity, prio, sched;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct IOC { public ulong a, b, c, d, e, f; }
    [StructLayout(LayoutKind.Sequential)]
    struct JOBEXT {
        public JOBBASIC basic; public IOC io;
        public UIntPtr pMem, jMem, pPeak, jPeak;
    }

    const int STILL_ACTIVE = 259;

    public sealed class Result {
        public int Pid;
        public IntPtr Process;      // handle con — creator có full access
        public IntPtr Job;          // Job Object → TerminateJobObject kill tree
        public SafeFileHandle StdinWrite;
        public SafeFileHandle StdoutRead;
        public string Error;
    }

    static IntPtr InheritableDup(IntPtr h) {
        // đầu pipe phía child cần inherit; đầu phía bridge giữ không-inherit
        IntPtr d;
        if (!DuplicateHandle(GetCurrentProcess(), h, GetCurrentProcess(),
                             out d, 0, true, 2))  // DUPLICATE_SAME_ACCESS
            throw new Win32Exception(Marshal.GetLastWin32Error());
        return d;
    }

    static IntPtr NulWrite() {
        var sa = new SA { n = Marshal.SizeOf<SA>(), inherit = false };
        return CreateFileW("NUL", 0x40000000, 3, ref sa, 3, 0, IntPtr.Zero);
    }

    // envBlock: "K=V\0K=V\0\0" — Marshal.StringToHGlobalUni giữ \0 trong
    // chuỗi + thêm \0 cuối → block unicode double-null đúng chuẩn.
    public static Result Start(string user, string password, string cmdline,
                               string workdir, string envBlock) {
        var r = new Result();
        var sa = new SA { n = Marshal.SizeOf<SA>(), inherit = false };
        IntPtr inR, inW, outR, outW;
        if (!CreatePipe(out inR, out inW, ref sa, 0) ||
            !CreatePipe(out outR, out outW, ref sa, 0)) {
            r.Error = "CreatePipe: " + Marshal.GetLastWin32Error();
            return r;
        }
        IntPtr cIn, cOut, cErr;
        try {
            cIn = InheritableDup(inR);
            cOut = InheritableDup(outW);
            cErr = InheritableDup(NulWrite());   // stderr → NUL (như .py DEVNULL)
        } catch (Exception e) {
            r.Error = "dup: " + e.Message; return r;
        }
        var si = new SI { cb = Marshal.SizeOf<SI>() };
        si.flags = 0x100;                       // STARTF_USESTDHANDLES
        si.inH = cIn; si.outH = cOut; si.errH = cErr;
        IntPtr env = Marshal.StringToHGlobalUni(envBlock);
        PI pi;
        try {
            bool ok = CreateProcessWithLogonW(user, ".", password, 1,
                null, cmdline,
                0x400 | 0x08000000,              // UNICODE_ENV | NO_WINDOW
                env, workdir, ref si, out pi);
            if (!ok) {
                r.Error = "CreateProcessWithLogonW: " +
                          Marshal.GetLastWin32Error();
                CloseHandle(cIn); CloseHandle(cOut); CloseHandle(cErr);
                CloseHandle(inR); CloseHandle(inW);
                CloseHandle(outR); CloseHandle(outW);
                return r;
            }
        } finally { Marshal.FreeHGlobal(env); }
        CloseHandle(cIn); CloseHandle(cOut); CloseHandle(cErr);
        CloseHandle(inR); CloseHandle(outW);    // bridge chỉ giữ đầu của mình
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job != IntPtr.Zero) {
            // KILL_ON_JOB_CLOSE (0x2000): het handle job -> kernel giet ca
            // cay. Bridge chet dot ngot / bi force-kill thi con van khong
            // thanh process mo coi.
            var ext = new JOBEXT();
            ext.basic.flags = 0x2000;
            IntPtr p = Marshal.AllocHGlobal(Marshal.SizeOf<JOBEXT>());
            try {
                Marshal.StructureToPtr(ext, p, false);
                SetInformationJobObject(job, 9, p,
                    (uint)Marshal.SizeOf<JOBEXT>());
            } finally { Marshal.FreeHGlobal(p); }
            AssignProcessToJobObject(job, pi.proc);
        }
        CloseHandle(pi.thread);
        r.Pid = pi.pid; r.Process = pi.proc; r.Job = job;
        r.StdinWrite = new SafeFileHandle(inW, true);
        r.StdoutRead = new SafeFileHandle(outR, true);
        return r;
    }

    public static bool IsAlive(IntPtr hProcess) {
        int code;
        if (!GetExitCodeProcess(hProcess, out code)) return false;
        return code == STILL_ACTIVE;
    }

    // Kill tree qua Job — không cần quyền trên từng process (non-admin
    // không TerminateProcess được process user khác; Job Object thì được
    // vì bridge là owner của job). Fallback giết process chính.
    public static void Kill(IntPtr hJob, IntPtr hProcess) {
        if (hJob != IntPtr.Zero) {
            TerminateJobObject(hJob, 1);
            CloseHandle(hJob);
        } else if (hProcess != IntPtr.Zero) {
            TerminateProcess(hProcess, 1);
        }
    }
}
}
'@ -ReferencedAssemblies System.IO.FileSystem, System.Runtime.InteropServices, Microsoft.Win32.Primitives, System.ComponentModel.Primitives
}

function Test-BrainAlive {
    if ($script:AcpHandle -ne [IntPtr]::Zero) {
        return [TroLy.AgentSpawn]::IsAlive($script:AcpHandle)
    }
    return ($script:AcpProc -and -not $script:AcpProc.HasExited)
}

function Stop-Brain {
    # Sandbox: giết cả cây qua Job Object (non-admin không Kill được
    # process user khác — handle Job của chính bridge mới là đường đi).
    if ($script:AcpHandle -ne [IntPtr]::Zero) {
        try { [TroLy.AgentSpawn]::Kill($script:AcpJob, $script:AcpHandle) } catch {}
        $script:AcpHandle = [IntPtr]::Zero; $script:AcpJob = [IntPtr]::Zero
        return
    }
    try { if ($script:AcpProc -and -not $script:AcpProc.HasExited) { $script:AcpProc.Kill($true) } } catch {}
}

function Send-Acp($obj) {
    $json = ($obj | ConvertTo-Json -Depth 20 -Compress)
    # Ghi byte UTF-8 thẳng vào stream — không qua WriteLine vì WriteLine
    # dùng Console.InputEncoding (OEM codepage) làm hỏng tiếng Việt có dấu.
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json + "`n")
    $w = if ($script:AcpIn) { $script:AcpIn } else { $script:AcpProc.StandardInput.BaseStream }
    $w.Write($bytes, 0, $bytes.Length)
    $w.Flush()
}

function Call-Acp($method, $params) {
    $id = $script:NextId; $script:NextId += 1
    Send-Acp ([ordered]@{ jsonrpc = "2.0"; id = $id; method = $method; params = $params })
    return $id
}

$script:AcpReplies = @{}   # parity .py — reply của não theo id, Drain-Queue ghi

function Wait-AcpReply($mid, $timeoutSec) {
    # Chờ não trả lời call `$mid` — handshake ACP bắt buộc tuần tự
    # (initialize xong mới được session/new — não từ chối "Invalid
    # request" nếu session/new đi trước). Bơm Drain-Queue vì reader
    # là event-driven (queue đổ trong Drain-Queue).
    $end = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $end) {
        Drain-Queue
        $k = [string]$mid
        if ($script:AcpReplies.ContainsKey($k)) {
            $r = $script:AcpReplies[$k]
            $script:AcpReplies.Remove($k)
            return $r
        }
        if ($script:AcpDead) { return $null }
        Start-Sleep -Milliseconds 50
    }
    return $null
}

$script:RunId = 0        # parity .py — bump ở /api/prompt, event kèm run_id

function Push-Event($ev) {
    if (-not $ev.Contains("run_id")) { $ev["run_id"] = $script:RunId }
    [void]$script:EventStore.Add($ev)
    if ($ev.t -in @("ready", "done", "err")) {
        $script:PermPending.Clear()   # lượt mới/kết thúc/lỗi → perm cũ hết hạn
        $script:PromptBusy = $false   # kết lượt (kể cả não chết → err) → mở prompt
    }
    if ($script:EventStore.Count -gt $MaxEvents) {
        $excess = $script:EventStore.Count - $MaxEvents
        $script:EventStore.RemoveRange(0, $excess)
        $script:EventBase += $excess
    }
}

function Start-BrainSandboxed($brain, $cred) {
    # Spawn não dưới user "troly-agent" kém quyền (setup-agent-user đã cấp
    # ACL). Trả $true khi spawn + handshake được đẩy đi; $false → caller
    # rơi về spawn thường (vẫn hơn kẹt chết, kèm event cảnh báo).
    # Resolve cmd -> full path: PATH-search của child có thể fail khi
    # troly-agent không enumerate được dir chứa binary (deny-read chỉ
    # cho traverse) — full path bỏ qua search, chỉ cần exec trên file.
    $cmdPath = $brain.cmd
    try { $cmdPath = (Get-Command $brain.cmd -ErrorAction Stop).Source } catch {}
    $cmdline = '"' + $cmdPath + '"'
    foreach ($a in @($brain.args)) { $cmdline += ' "' + $a + '"' }
    $home2 = "C:\Users\$($cred.user)"
    $envPairs = [ordered]@{
        SystemRoot = $env:SystemRoot; windir = $env:windir
        SystemDrive = $env:SystemDrive; ComSpec = $env:ComSpec
        PATHEXT = $env:PATHEXT; PATH = $env:PATH
        TEMP = "C:\Windows\Temp"; TMP = "C:\Windows\Temp"
        USERPROFILE = $home2; HOMEDRIVE = "C:"; HOMEPATH = "\Users\$($cred.user)"
        APPDATA = "$home2\AppData\Roaming"; LOCALAPPDATA = "$home2\AppData\Local"
        USERNAME = $cred.user; USERDOMAIN = $env:COMPUTERNAME
        COMPUTERNAME = $env:COMPUTERNAME
        # npx adapter: cache RIENG trong profile troly-agent — nếu xài
        # chung ~/.npm của chủ thì agent ghi được package vào cache chủ
        # → chủ npx exec code agent đặt = thoát sandbox.
        NPM_CONFIG_CACHE = "$home2\.npm-cache"
        BRIDGE_TOKEN = $script:BridgeToken
    }
    $envBlock = (($envPairs.GetEnumerator() |
                  ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "`0") + "`0"
    $res = [TroLy.AgentSpawn]::Start($cred.user, $cred.password,
                                   $cmdline, $WorkDir, $envBlock)
    if (-not $res -or $res.Error) {
        Push-Event ([ordered]@{ t = "err"; msg = "không sandbox được não ($($res.Error)) — trợ lý đang chạy quyền đầy đủ" })
        return $false
    }
    $script:AcpHandle = $res.Process
    $script:AcpJob = $res.Job
    # ::new() resolve overload theo kiểu thật — New-Object sẽ coerce
    # SafeFileHandle thành string rồi chọn ctor (string path, FileMode)
    # và đi tìm file "Microsoft.Win32.SafeHandles.SafeFileHandle".
    $script:AcpIn = [IO.FileStream]::new($res.StdinWrite, [IO.FileAccess]::Write)
    $script:AcpOut = [IO.StreamReader]::new(
        [IO.FileStream]::new($res.StdoutRead, [IO.FileAccess]::Read),
        [Text.Encoding]::UTF8)
    # Đọc stdout bằng ReadLineAsync — KHÔNG dùng thread: scriptblock PS
    # trên raw Thread không có runspace → crash. Task hoàn thành được
    # drain trong Drain-Queue (vốn đã chạy mỗi request, đơn luồng).
    $script:AcpTask = $script:AcpOut.ReadLineAsync()
    $script:AcpDead = $false
    # initialize PHẢI có result trước khi session/new — bắn liền nhau
    # thì não trả "Invalid request" và SessionId mãi rỗng → prompt kẹt
    $mid = Call-Acp "initialize" @{
        protocolVersion = 1
        clientCapabilities = @{
            fs = @{ readTextFile = $false; writeTextFile = $false }
            terminal = $false
        }
    }
    $r = Wait-AcpReply $mid 30
    if ($r -and $r.result) {
        $mid2 = Call-Acp "session/new" @{ cwd = $WorkDir; mcpServers = @() }
        Wait-AcpReply $mid2 30 | Out-Null
    }
    return $true
}

function Start-Brain {
    # Bật (hoặc đổi) não: giết agent cũ nếu còn sống, spawn theo brain.json
    # rồi bắt tay ACP chuẩn (initialize + session/new).
    $brain = Get-Brain
    Stop-Brain   # giết não cũ — cả hai đường (Process.Kill / Job Object)
    if ($script:AcpSub) {
        try { Unregister-Event -SourceIdentifier $script:AcpSub.SourceIdentifier } catch {}
        $script:AcpSub = $null
    }
    foreach ($s in @($script:AcpIn, $script:AcpOut)) {
        try { if ($s) { $s.Dispose() } } catch {}
    }
    $script:AcpIn = $null; $script:AcpOut = $null; $script:AcpTask = $null
    $script:AcpProc = $null
    $script:SessionId = $null
    # Có cred user hạn chế → spawn trong sandbox (S4); lỗi → về đường
    # thường kèm cảnh báo (degrade về policy-only chứ không kẹt chết)
    $cred = Get-AgentCred
    if ($cred -and (Start-BrainSandboxed $brain $cred)) { return }
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
    # env scrub (parity content_guard.scrub_env): não kế thừa TOÀN BỘ env
    # user — `printenv` trong sandbox đọc được OPENAI_API_KEY/AWS đang
    # set. Spawn bằng allowlist; cty truyền thêm qua env-allowlist.json.
    $keep = @("PATH","HOME","USER","USERNAME","LOGNAME","LANG","LC_ALL",
        "LC_CTYPE","TZ","TMPDIR","TEMP","TMP","SHELL","TERM",
        "BRIDGE_TOKEN","BRAIN_TERM","TROLY_DATA",
        "SystemRoot","SystemDrive","WINDIR","APPDATA","LOCALAPPDATA",
        "USERPROFILE","HOMEDRIVE","HOMEPATH","COMSPEC","PATHEXT",
        "ProgramData","ProgramFiles","ProgramFiles(x86)","PSModulePath",
        "NUMBER_OF_PROCESSORS","OS","PROCESSOR_ARCHITECTURE",
        "XDG_CONFIG_HOME","XDG_DATA_HOME","XDG_CACHE_HOME",
        "XDG_RUNTIME_DIR","DISPLAY","SSH_AUTH_SOCK",
        "DBUS_SESSION_BUS_ADDRESS",
        # proxy vars — cấu hình mạng, máy sau proxy cty cần não lên net
        "HTTP_PROXY","HTTPS_PROXY","NO_PROXY","ALL_PROXY",
        "http_proxy","https_proxy","no_proxy","all_proxy")
    try {
        $exf = Join-Path $WorkDir ".devin\env-allowlist.json"
        if (Test-Path $exf) {
            $exd = Get-Content $exf -Raw | ConvertFrom-Json
            foreach ($k in @($exd.extra)) { $keep += [string]$k }
        }
    } catch {}
    $psi.EnvironmentVariables.Clear()
    $dropped = 0
    foreach ($kv in [System.Environment]::GetEnvironmentVariables().GetEnumerator()) {
        if ($keep -contains $kv.Key -or $kv.Key.StartsWith("TROLY_")) {
            $psi.EnvironmentVariables[$kv.Key] = [string]$kv.Value
        } else { $dropped++ }
    }
    if ($dropped -gt 0) {
        Push-Event ([ordered]@{ t = "env_scrub"; dropped = $dropped })
    }
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
    $mid = Call-Acp "initialize" @{
        protocolVersion = 1
        clientCapabilities = @{
            fs = @{ readTextFile = $false; writeTextFile = $false }
            terminal = $false
        }
    }
    $r = Wait-AcpReply $mid 30
    if ($r -and $r.result) {
        $mid2 = Call-Acp "session/new" @{ cwd = $WorkDir; mcpServers = @() }
        Wait-AcpReply $mid2 30 | Out-Null
    }
}

function Drain-Queue {
    # Đường sandbox: đã có task ReadLineAsync xong chưa → đổ vào queue.
    # EOF (Result=null) hoặc pipe gãy → không đặt task mới; IsAlive trong
    # Test-BrainAlive lo phần phát hiện não chết.
    if ($script:AcpTask -and $script:AcpTask.IsCompleted) {
        try { $l = $script:AcpTask.Result } catch { $l = $null }
        if ($null -ne $l -and $l.Trim()) { $lineQueue.Enqueue($l.Trim()) }
        $script:AcpTask = if ($null -ne $l) {
            $script:AcpOut.ReadLineAsync()
        } else { $null }
    }
    $line = $null
    while ($lineQueue.TryDequeue([ref]$line)) {
        try { $m = $line | ConvertFrom-Json } catch { continue }
        # Reply của một call đang chờ — ghi trước, vẫn cho các nhánh
        # dưới xử lý tiếp (sessionId, err, done) như thường
        if ($null -ne $m.id -and `
            ($m.PSObject.Properties.Name -contains "result" -or `
             $m.PSObject.Properties.Name -contains "error")) {
            $script:AcpReplies[[string]$m.id] = $m
        }
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
            # id do CHÍNH não tự khai: (1) không scalar → hashtable key rác
            # + JSON-RPC reply không khớp; (2) trùng card đang mở → che card
            # local (đọc id qua /api/poll) — bấm "Đồng ý" của học viên thành
            # approval cho tool call của não. Từ chối + báo lỗi cả hai.
            $badId = ($null -eq $m.id) -or `
                ($m.id -isnot [string] -and $m.id -isnot [int] -and $m.id -isnot [long]) -or `
                $script:PermPending.ContainsKey([string]$m.id) -or `
                $script:LocalPending.ContainsKey([string]$m.id)
            if ($badId) {
                try { Send-Acp ([ordered]@{ jsonrpc = "2.0"; id = $m.id
                    error = @{ code = -32602; message = "id không hợp lệ" } }) } catch {}
                continue
            }
            $p = $m.params; $tc = $p.toolCall
            $opts = @()
            $optIds = @()
            foreach ($o in $p.options) {
                $opts += [ordered]@{ optionId = $o.optionId; name = $o.name; kind = $o.kind }
                $optIds += [string]$o.optionId
            }
            # kẹp độ dài title do não gửi — phình thì lọt thẳng vào store
            $ttl = if ($tc.title) { [string]$tc.title } else { "Trợ lý muốn làm một việc" }
            if ($ttl.Length -gt 200) { $ttl = $ttl.Substring(0, 200) }
            # exec allowlist (parity content_guard): lệnh khớp glob trong
            # .devin/exec-allowlist.json → auto-duyệt không card. Denylist
            # metachar lọc pattern độc (file bị sửa tay).
            $alMatched = $null
            try {
                $alf = Join-Path $WorkDir ".devin\exec-allowlist.json"
                if (Test-Path $alf) {
                    $alPats = @((Get-Content $alf -Raw | ConvertFrom-Json).patterns)
                    # parity .py — ưu tiên field LỆNH (cmd/command); text/
                    # input chứa văn bản bất kỳ, não đặt chuỗi hiền vào
                    # đó mà toolCall làm việc khác thì auto-duyệt bừa.
                    $cands = @()
                    if ($tc.rawInput) {
                        foreach ($k in @("cmd","command")) {
                            if ($tc.rawInput.$k -is [string] -and
                                $tc.rawInput.$k.Trim()) {
                                $cands += $tc.rawInput.$k
                            }
                        }
                    }
                    if (-not $cands.Count) { $cands = @($ttl) }
                    foreach ($pat in $alPats) {
                        $pl = ([string]$pat).Trim()
                        if (-not $pl -or $pl.ToLower() -match '[|<>;&`]|(\$\()|sudo|rm |curl|wget|certutil|powershell|bash|python|node |sh |eval') { continue }
                        # pattern phải bắt đầu bằng tên lệnh — `*`/`?` trần
                        # khớp mọi lệnh = tắt gate (parity .py)
                        if ($pl[0] -notmatch '[a-zA-Z0-9._-]') { continue }
                        foreach ($c in $cands) {
                            $cn = ($c -replace '\s+', ' ').Trim()
                            # parity .py — lệnh chứa metachar (chain/
                            # redirect) không auto-duyệt dù khớp glob:
                            # "git status *" cũng nuốt "&& rm -rf ~"
                            if ($cn -match '[|<>;&`]|(\$\()') { continue }
                            if ($cn -like $pl -or $cn -like "$pl *") {
                                $alMatched = $pl; break
                            }
                        }
                        if ($alMatched) { break }
                    }
                }
            } catch {}
            if ($alMatched) {
                $allow = $null
                foreach ($o in $opts) {
                    if ([string]$o.kind -match '^(?i)allow') { $allow = $o; break }
                }
                $pick = if ($allow) { $allow.optionId } elseif ($opts.Count) { $opts[0].optionId } else { $null }
                Push-Event ([ordered]@{ t = "perm:auto"; title = $ttl; pattern = $alMatched })
                try {
                    if ($null -ne $pick) {
                        Send-Acp ([ordered]@{ jsonrpc = "2.0"; id = $m.id
                            result = @{ outcome = @{ outcome = "selected"; optionId = $pick } } })
                    } else {
                        Send-Acp ([ordered]@{ jsonrpc = "2.0"; id = $m.id
                            error = @{ code = -32602; message = "không có option duyệt" } })
                    }
                } catch {}
                continue
            }
            if ($script:PermPending.Count -ge $PermMax) { $script:PermPending.Clear() }
            $script:PermPending[[string]$m.id] = @{
                options = $optIds
                ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            }
            Push-Event ([ordered]@{
                t = "perm"; id = $m.id
                title = $ttl
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
function Test-Probe($probe) {
    # probe phải khớp schema cố định (parity validate_probe bên .py):
    # probe tuỳ ý = oracle đọc file ngoài sandbox / kênh exfil creds.
    # Chặn 2 đầu — upsert /api/connections từ chối + Run-Probe kiểm lại.
    if (-not $probe -or -not $probe.type) { return $false }
    $t = [string]$probe.type
    if ($t -eq "http") {
        try { $u = [uri]([string]$probe.url) } catch { return $false }
        $h = $u.Host
        return ($u.Scheme -eq "http" -or $u.Scheme -eq "https") -and `
            ($h -eq "localhost" -or $h -eq "127.0.0.1" -or $h -eq "::1" -or $h.EndsWith(".localhost"))
    }
    if ($t -eq "tabs") {
        return ($probe.url_contains -is [string]) -and ([string]$probe.url_contains).Length -le 120
    }
    if ($t -eq "path") {
        # chỉ probe dưới ~ và KHÔNG đụng .devin — nếu không thành oracle
        # tồn-tại-file cho secrets.local.json & cả
        $p = [IO.Path]::GetFullPath((Expand-Path ([string]$probe.path)))
        $home2 = [IO.Path]::GetFullPath($env:USERPROFILE)
        $dev = [IO.Path]::GetFullPath((Join-Path $WorkDir ".devin"))
        return $p.StartsWith($home2 + [IO.Path]::DirectorySeparatorChar) -and `
            -not ($p -eq $dev -or $p.StartsWith($dev + [IO.Path]::DirectorySeparatorChar)) -and `
            -not (Test-SensitivePath $p)
    }
    if ($t -eq "mcp") {
        return ($probe.name -is [string]) -and ([string]$probe.name).Length -le 40
    }
    return ($t -eq "wp" -or $t -eq "zalo-oa")
}

function Run-Probe($probe) {
    # msg hiện thẳng dưới tên app trong panel Cài đặt của học viên —
    # viết bằng lời thường, không thuật ngữ (token/MCP/extension…)
    if (-not $probe) { return @{ ok = $false; msg = "chưa cài — cứ nhờ trợ lý trong chat, nó làm giúp" } }
    if (-not (Test-Probe $probe)) {
        return @{ ok = $false; msg = "kiểu kết nối lạ — nhờ trợ lý xem" }
    }
    try {
        if ($probe.type -eq "http") {
            # CHỈ đính mã kết nối khi probe chính 2 bridge — đính cho URL
            # loopback khác là rò token sang server local lạ (parity .py;
            # cùng lý do BRIDGE_PORTS trong bridge-token.js)
            $hdr = @{}
            try {
                if (([uri]$probe.url).Port -in @(7682, 7684)) {
                    $hdr["X-Bridge-Token"] = $BridgeToken
                }
            } catch {}
            $d = Invoke-RestMethod -Uri $probe.url -TimeoutSec 4 -Headers $hdr
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
                 -ContentType "application/json" -Headers @{ "X-Bridge-Token" = $BridgeToken } `
                 -Body '{"action":"tabs"}' -TimeoutSec 6
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
            $wpu = ([string]$wp.url).TrimEnd('/')
            if (-not $wpu.StartsWith('https://')) {
                # Basic auth qua http = gửi mật khẩu plaintext — parity chat-bridge.py
                return @{ ok = $false; msg = "địa chỉ site phải bắt đầu bằng https:// — nhờ trợ lý sửa giúp" }
            }
            $pw = ([string]$wp.app_password) -replace ' ', ''
            $auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$($wp.user):$pw"))
            try {
                Invoke-RestMethod -Uri ($wpu + "/wp-json/wp/v2/users/me") -Headers @{ Authorization = "Basic $auth" } -TimeoutSec 8 | Out-Null
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
    $res.Headers.Add("Access-Control-Allow-Headers", "Content-Type, X-Bridge-Token")
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
# Chống slow-drip: loop đơn luồng nên một client rỏ header/body từng
# giọt là nghẽn cả bridge (parity với settimeout(45) bên chat-bridge.py —
# ở đây timeout ngắn hơn vì ps1 không có long-poll nào cần giữ request).
$listener.TimeoutManager.HeaderWait = [timespan]::FromSeconds(15)
$listener.TimeoutManager.EntityBody = [timespan]::FromSeconds(30)
$listener.TimeoutManager.RequestQueue = [timespan]::FromSeconds(30)
$listener.TimeoutManager.IdleConnection = [timespan]::FromSeconds(60)
Write-Host "chat-bridge: http://localhost:$Port  (cwd=$WorkDir)"

try {
    while ($listener.IsListening) {
        $ctx = $null
        try { $ctx = $listener.GetContext() } catch { break }
        Drain-Queue
        # Watchdog lượt treo (parity _turn_watchdog bên .py): não sống nhưng
        # không trả done/err quá $TurnTimeout → PromptBusy kẹt 409 vĩnh viễn.
        # Loop đơn luồng không có Timer nên mỗi request là một nhịp — portal
        # poll ~1s nên tick đủ dày; Push-Event err tự clear PromptBusy.
        if ($script:PromptBusy -and $script:PromptSince -and
            ((Get-Date) - $script:PromptSince).TotalSeconds -gt $TurnTimeout) {
            Push-Event ([ordered]@{ t = "err"; msg = "trợ lý bị kẹt quá lâu — mình đang khởi động lại não" })
            Stop-Brain
            $script:AcpDead = $true   # prompt tiếp theo đi đường Start-Brain self-heal
        }
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
                $ctx.Response.Headers.Add("Access-Control-Allow-Headers", "Content-Type, X-Bridge-Token")
                $ctx.Response.OutputStream.Close()
                continue
            }
            # Mọi endpoint trừ /api/health phải có mã kết nối — process
            # local lạ không ra lệnh được cho trợ lý nữa.
            if (-not ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/health") -and
                -not (Test-Authed $ctx.Request)) {
                Send-Json $ctx @{ err = "thiếu hoặc sai mã kết nối" } 401
                continue
            }
            # body quá lớn → chặn trước khi đọc (save-page cho tới 8MB vì
            # trang clone nhúng ảnh base64; mọi POST khác 1MB)
            if ($ctx.Request.HttpMethod -eq "POST") {
                $cap = if ($path -eq "/api/save-page") { 8000000 } else { 1000000 }
                if ($ctx.Request.ContentLength64 -gt $cap) {
                    Send-Json $ctx @{ err = "body quá lớn" } 413
                    continue
                }
            }
            if ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/health") {
                Send-Json $ctx @{ ok = $true; brain = (Get-Brain).id; version = (Get-AppVersion); extVersion = (Get-ExtVersion) }
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
                        cost = $p.cost
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
            elseif ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/check-path") {
                # onboarding hỏi "folder này có tồn tại không" trước khi thêm —
                # POST /api/permissions tạo card nên không dùng để kiểm được.
                # Chỉ trả isdir, không lộ metadata; vẫn đòi token.
                $p0 = Expand-Path ([string]$ctx.Request.QueryString["path"]).Trim()
                # parity .py: path nhạy cảm → false luôn (oracle dò file)
                Send-Json $ctx @{ ok = $true; isdir = ($p0 -and
                    -not (Test-SensitivePath $p0) -and
                    (Test-Path $p0 -PathType Container)) }
            }
            elseif ($ctx.Request.HttpMethod -eq "GET" -and $path -eq "/api/count-glob") {
                # parity .py — verify workflow hỏi số file khớp glob;
                # trả SỐ không trả tên. Pattern chỉ trong dir (không ../).
                $d0 = Expand-Path ([string]$ctx.Request.QueryString["path"]).Trim()
                $pat = [string]$ctx.Request.QueryString["pattern"]
                if (-not $pat) { $pat = "*" }
                if ($pat.Length -gt 100) { $pat = $pat.Substring(0,100) }
                if ($pat -match '\.\.|/|\\') { $pat = "*" }
                $cnt = 0
                if ($d0 -and -not (Test-SensitivePath $d0) -and
                    (Test-Path $d0 -PathType Container)) {
                    $cnt = @((Get-ChildItem -Path $d0 -Filter $pat -Force |
                              Select-Object -First 2001)).Count
                }
                Send-Json $ctx @{ ok = $true; count = [Math]::Min($cnt,2000);
                                  capped = ($cnt -gt 2000) }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/prompt") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                if ($script:AcpDead -or -not (Test-BrainAlive)) {
                    # não chết (process rớt hoặc chưa cài) → thử bật lại một lần
                    Start-Brain
                    Send-Json $ctx @{ err = "đang khởi động lại trợ lý — gửi lại sau vài giây" } 503
                } elseif (-not $script:SessionId) {
                    Send-Json $ctx @{ err = "chưa có session" } 503
                } elseif ($script:PromptBusy) {
                    # loop single-threaded nên cờ này không cần lock — chỉ
                    # được set bởi chính handler này, clear ở Push-Event
                    Send-Json $ctx @{ err = "trợ lý đang xử lý câu trước" } 409
                } else {
                    try {
                        $script:PromptBusy = $true
                        $script:PromptSince = Get-Date
                        $script:RunId += 1   # parity .py — đếm lượt thật cho beacon
                        Call-Acp "session/prompt" @{
                            sessionId = $script:SessionId
                            prompt = @(@{ type = "text"; text = $body.text })
                        } | Out-Null
                        Send-Json $ctx @{ ok = $true }
                    } catch {
                        $script:PromptBusy = $false   # gửi hỏng → không kẹt busy
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
                    # Interpreter/exec helper không được làm "não" tự nhập —
                    # args của chúng là code-exec trần (python -c, find -exec)
                    if (Test-BrainDenied $cmd) {
                        Send-Json $ctx @{ err = "lệnh này chạy code tuỳ ý — không dùng làm não được" } 400
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
                    if ($term -notmatch '^[A-Za-z0-9_.-]+$') { $term = $cmd }
                    if (Test-BrainDenied $term) {
                        Send-Json $ctx @{ err = "lệnh terminal này chạy code tuỳ ý — không dùng được" } 400
                        continue
                    }
                    $b = [ordered]@{ id = $(if ($bid) { $bid } else { "custom" }); label = $label; cmd = $cmd; args = $bArgs; terminal = $term }
                    $requires = @($cmd)
                }
                $missing = @($requires | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
                if ($missing.Count -gt 0) {
                    Send-Json $ctx @{ err = "chưa cài trên máy: $($missing -join ', ')"; missing = $missing } 404
                } elseif (-not $preset) {
                    # Não tự nhập → consent gate (preset vẫn đổi thẳng)
                    $disp = "$cmd $($bArgs -join ' ')"
                    if ($disp.Length -gt 80) { $disp = $disp.Substring(0, 80) }
                    $rid = New-Gate "Đổi não sang lệnh tự nhập `"$disp`"?" ({
                        Save-Json $BrainFp $b
                        Start-Brain
                    }.GetNewClosure())
                    Send-Json $ctx @{ pending = $rid; msg = "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để đổi não" } 202
                } else {
                    Save-Json $BrainFp $b
                    Start-Brain
                    Send-Json $ctx @{ ok = $true; brain = $b }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/respond") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                # id PHẢI đang pending cho cả hai đường — __cancel__ chỉ miễn
                # check optionId, không miễn check id (chặn bơm id rác).
                # Chỉ Remove khi hợp lệ — request optionId lạ không được giết
                # card (kẻ xấu sẽ DoS được nút bấm của học viên).
                $key = [string]$body.id
                $oid = [string]$body.optionId
                # Card nội bộ (consent gate): phải kèm Origin trình duyệt —
                # chỉ pop khi đủ điều kiện (request rác không DoS được nút
                # xác nhận của học viên). Check trước PermPending.
                $lrec = $script:LocalPending[$key]
                if ($null -ne $lrec) {
                    $lage = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $lrec.ts
                    if ($lage -gt $PermTtl) {
                        $script:LocalPending.Remove($key)
                        Send-Json $ctx @{ err = "yêu cầu không còn hiệu lực" } 404
                    } elseif ($oid -ne "ok" -and $oid -ne "__cancel__") {
                        Send-Json $ctx @{ err = "lựa chọn không hợp lệ" } 400
                    } elseif (-not (Test-LocalOrigin $ctx.Request.Headers["Origin"])) {
                        Send-Json $ctx @{ err = "thiếu Origin trình duyệt" } 403
                    } else {
                        $script:LocalPending.Remove($key)   # one-shot sau check
                        $failed = $null
                        if ($oid -eq "ok") {
                            try { & $lrec.apply } catch { $failed = "$($_.Exception.Message)" }
                        }
                        if ($failed) {
                            if ($failed.Length -gt 120) { $failed = $failed.Substring(0, 120) }
                            Send-Json $ctx @{ err = "làm không được — $failed" } 500
                        } else {
                            Send-Json $ctx @{ ok = $true }
                        }
                    }
                    continue
                }
                $rec = $script:PermPending[$key]
                $age = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $(if ($rec) { $rec.ts } else { 0 })
                if ($null -eq $rec -or $age -gt $PermTtl) {
                    Send-Json $ctx @{ err = "yêu cầu không còn hiệu lực" } 404
                } elseif (-not (Test-LocalOrigin $ctx.Request.Headers["Origin"])) {
                    # Card não (ACP): id do chính não tự khai + nó có sẵn
                    # token → phải đòi Origin trình duyệt y như card nội
                    # bộ, kẻo não/script nhiễm tự duyệt tool call của mình
                    Send-Json $ctx @{ err = "thiếu Origin trình duyệt" } 403
                } elseif ($body.optionId -ne "__cancel__" -and
                          $rec.options -notcontains [string]$body.optionId) {
                    Send-Json $ctx @{ err = "lựa chọn không hợp lệ" } 400
                } else {
                    $script:PermPending.Remove($key)     # one-shot, không replay
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
                    try { if (-not $script:AcpDead -and (Test-BrainAlive)) { Send-Acp $payload } } catch {}
                    Push-Event ([ordered]@{ t = "perm_done"; id = $body.id })
                    Send-Json $ctx @{ ok = $true }
                }
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
                        $rid = New-Gate "Xoá bài học $folder? (vào thùng rác — khôi phục được)" ({
                            # không xoá hẳn — move vào .trash/ để khôi phục
                            # được; tên kèm timestamp + hex tránh đụng tên
                            $trash = Join-Path $course ".trash"
                            New-Item -ItemType Directory -Force -Path $trash | Out-Null
                            $dst = Join-Path $trash ($folder + "-" + (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + ([guid]::NewGuid().ToString("N").Substring(0,6)))
                            Move-Item $target $dst
                            $mf = Join-Path $course "manifest.json"
                            try {
                                $m = Get-Content $mf -Raw -Encoding UTF8 | ConvertFrom-Json
                                $m.lessons = @($m.lessons | Where-Object { $_.folder -ne $folder })
                                Save-Json $mf $m
                            } catch {}
                        }.GetNewClosure())
                        Send-Json $ctx @{ pending = $rid; msg = "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để xoá (bài giữ trong thùng rác)" } 202
                    } else {
                        Send-Json $ctx @{ err = "không thấy folder bài" } 404
                    }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/save-page") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $rel = ([string]$body.file).Trim().TrimStart("/")
                $html = [string]$body.html
                $course = (Resolve-Path (Join-Path $WorkDir "my-course")).Path
                $target = [IO.Path]::GetFullPath((Join-Path $WorkDir $rel))
                if (-not $rel.StartsWith("my-course/") -or $rel.Contains("..") -or
                    $rel.Contains("\") -or
                    -not $target.StartsWith($course + [IO.Path]::DirectorySeparatorChar) -or
                    $target -notmatch '\.html?$') {
                    Send-Json $ctx @{ err = "chỉ lưu file .html trong my-course/" } 400
                } elseif (-not $html) {
                    Send-Json $ctx @{ err = "trang trống" } 400
                } else {
                    # GetFullPath chỉ lexical — junction/symlink dưới
                    # my-course\ lách containment (audit-5 F3; bản .py
                    # dùng realpath nên không lỗi). Check từng segment
                    # kể cả leaf: ReparsePoint → từ chối. Segment chưa
                    # tồn tại (subdir mới) → Get-Item trả $null → bỏ qua.
                    $rp = $course; $reparse = $false
                    $segs = $rel -split '/'
                    foreach ($seg in $segs[1..($segs.Count-1)]) {
                        $rp = Join-Path $rp $seg
                        $it = Get-Item $rp -Force -ErrorAction SilentlyContinue
                        if ($it -and ($it.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                            $reparse = $true; break
                        }
                    }
                    if ($reparse) {
                        Send-Json $ctx @{ err = "không lưu qua link/junction" } 400
                        continue
                    }
                    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
                    # backup trước khi ghi đè — học viên sửa hỏng còn về được
                    if (Test-Path $target) { Copy-Item $target "$target.bak" -Force }
                    # UTF-8 KHÔNG BOM — Set-Content mặc định ghi BOM, viewer đọc
                    # file trực tiếp sẽ thấy ký tự lạ đầu trang
                    [IO.File]::WriteAllText($target, $html, (New-Object System.Text.UTF8Encoding $false))
                    Send-Json $ctx @{ ok = $true }
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/permissions") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $lv = [string]$body.access
                # Batch {"paths":[...]} = MỘT card — onboarding thêm nhiều
                # folder không spam card (parity chat-bridge.py)
                $raw = @()
                if ($body.paths) { $raw = @($body.paths) } else { $raw = @($body.path) }
                if ($raw.Count -gt 20) {
                    Send-Json $ctx @{ err = "quá nhiều folder một lần" } 400
                    continue
                }
                $paths = @(); $bad = @(); $sensitive = $null; $rwbad = $null
                foreach ($r0 in $raw) {
                    $p0 = Expand-Path ([string]$r0).Trim()
                    if (-not $p0 -or -not (Test-Path $p0 -PathType Container)) {
                        $bad += [string]$r0; continue
                    }
                    if (Test-SensitivePath $p0) { $sensitive = $p0; break }
                    if ($lv -eq "read-write" -and -not (Test-RwGrantOk $p0)) { $rwbad = $p0; break }
                    $paths += $p0
                }
                if ($lv -ne "read" -and $lv -ne "read-write") {
                    Send-Json $ctx @{ err = "access phải là read hoặc read-write" } 400
                } elseif ($sensitive) {
                    Send-Json $ctx @{ err = "folder chứa dữ liệu nhạy cảm — không cấp quyền được: $sensitive" } 400
                } elseif ($rwbad) {
                    Send-Json $ctx @{ err = "không cấp ghi trong folder mã nguồn của trợ lý — ghi được là code chạy ngoài mọi hàng rào: $rwbad" } 400
                } elseif (-not $paths.Count) {
                    Send-Json $ctx @{ err = "không thấy folder này trên máy" } 404
                } else {
                    # Consent gate — permissions.json là "đồ chìa khoá": agent
                    # tự cấp quyền được nếu endpoint này ghi thẳng
                    $note2 = ([string]$body.note)
                    $note2 = $note2.Substring(0, [Math]::Min(120, $note2.Length))
                    $disp = if ($paths.Count -eq 1) { $paths[0] } else { "$($paths.Count) folder" }
                    $rid = New-Gate "Thêm quyền $lv cho $disp`?" ({
                        $q = Load-Json $PermFp @{ folders = @() }
                        # so sánh sau Expand-Path — entry cũ ghi "~/Downloads" vẫn khớp được
                        $arr = @($q.folders | Where-Object { $paths -notcontains (Expand-Path $_.path) })
                        foreach ($p0 in $paths) {
                            $arr += @{ path = $p0; access = $lv; note = $note2 }
                        }
                        $q.folders = $arr
                        Save-Json $PermFp $q
                    }.GetNewClosure())
                    $resp = @{ pending = $rid; msg = "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để có hiệu lực" }
                    if ($bad.Count) { $resp.skipped = $bad }
                    Send-Json $ctx $resp 202
                }
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/remove-permission") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $p = Expand-Path ([string]$body.path).Trim()
                $rid = New-Gate "Gỡ quyền folder $p?" ({
                    $q = Load-Json $PermFp @{ folders = @() }
                    $q.folders = @($q.folders | Where-Object { (Expand-Path $_.path) -ne $p })
                    Save-Json $PermFp $q
                }.GetNewClosure())
                Send-Json $ctx @{ pending = $rid; msg = "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để có hiệu lực" } 202
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/connections") {
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                if (-not $body.app.id) {
                    Send-Json $ctx @{ err = "thiếu app.id" } 400
                } elseif ($body.app.probe -and -not (Test-Probe $body.app.probe)) {
                    # client ghi probe tuỳ ý = oracle/exfil — chỉ nhận schema cố định
                    Send-Json $ctx @{ err = "kiểu kết nối không hỗ trợ" } 400
                } elseif ($body.app.open_url -and ([string]$body.app.open_url -notmatch '^https?://')) {
                    # open_url là link nút "Mở trang" trong portal — javascript:/
                    # data: chạy được script trong origin portal → chỉ nhận http(s)
                    Send-Json $ctx @{ err = "open_url chỉ nhận link http(s)" } 400
                } else {
                    $k = Load-Json $ConnFp @{ apps = @() }
                    $ou = [string]$body.app.open_url
                    $oldOu = ""
                    foreach ($a in @($k.apps)) {
                        if ($a.id -eq $body.app.id) { $oldOu = [string]$a.open_url; break }
                    }
                    if ($ou -and $ou -ne $oldOu) {
                        # open_url MỚI/ĐỔI → nút "Mở trang" quen-thuộc trỏ
                        # site lạ → card cho học viên thấy đích (audit v6,
                        # parity py). Upsert status/name chạy thẳng.
                        $appObj = $body.app
                        $rid = New-Gate "Đặt link `"Mở trang`" của $($appObj.id) → $ou`?" ({
                            $kk = Load-Json $ConnFp @{ apps = @() }
                            $idx = -1
                            for ($i = 0; $i -lt @($kk.apps).Count; $i++) {
                                if ($kk.apps[$i].id -eq $appObj.id) { $idx = $i; break }
                            }
                            if ($idx -ge 0) { $kk.apps[$idx] = $appObj }
                            else { $kk.apps = @($kk.apps) + $appObj }
                            Save-Json $ConnFp $kk
                        }.GetNewClosure())
                        Send-Json $ctx @{ pending = $rid; msg = "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để đặt link" } 202
                    } else {
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
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/remove-connection") {
                # Agent tự gỡ kết nối = mất nút âm thầm → gate (audit v6,
                # parity py). Không UI nào gọi nên card không thêm ma sát.
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $aid = [string]$body.id
                $rid = New-Gate "Gỡ kết nối $aid`?" ({
                    $k = Load-Json $ConnFp @{ apps = @() }
                    $k.apps = @($k.apps | Where-Object { $_.id -ne $aid })
                    Save-Json $ConnFp $k
                }.GetNewClosure())
                Send-Json $ctx @{ pending = $rid; msg = "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để gỡ" } 202
            }
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/secrets") {
                # Form "Cài" trong panel Cài đặt: học viên dán app password WP /
                # mã OA… → ghi vào .devin\secrets.local.json (đã gitignore).
                # Chỉ GHI — không endpoint nào đọc secret ra ngoài.
                # Ghi credential là đặc quyền → consent gate (audit v6):
                # agent tự gọi url mới = xoá creds thật / exfil host lạ.
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $appId = [string]$body.app
                if ($appId -notmatch '^[a-z0-9-]+$' -or -not $body.fields -or $body.fields -isnot [PSCustomObject]) {
                    Send-Json $ctx @{ err = "thiếu app hoặc fields" } 400
                } else {
                    $cleanFields = @{}
                    $n = 0
                    foreach ($p in $body.fields.PSObject.Properties) {
                        if ($n -ge 10) { break }
                        $v = ([string]$p.Value).Trim()
                        if ($v) { $cleanFields[[string]$p.Name] = $v.Substring(0, [Math]::Min(500, $v.Length)); $n++ }
                    }
                    if (-not $cleanFields.Count) {
                        Send-Json $ctx @{ err = "chưa nhập gì" } 400
                    } else {
                        $fp = Join-Path $WorkDir ".devin\secrets.local.json"
                        # Card báo trước wipe — đổi url là xoá hết thông tin cũ.
                        $creds0 = Load-Json $fp @{}
                        $oldUrl0 = if ($creds0.$appId) { [string]$creds0.$appId.url } else { $null }
                        $wipe = ($cleanFields.ContainsKey("url") -and $cleanFields.url -ne $oldUrl0)
                        $gateTitle = "Lưu thông tin đăng nhập cho $appId`?"
                        if ($wipe) { $gateTitle = "Lưu thông tin đăng nhập cho $appId — đổi địa chỉ site sẽ XOÁ thông tin cũ`?" }
                        $rid = New-Gate $gateTitle ({
                            $creds = Load-Json $fp @{}
                            $oldUrl = if ($creds.$appId) { [string]$creds.$appId.url } else { $null }
                            $entry = @{}
                            if ($creds.$appId) {
                                $creds.$appId.PSObject.Properties | ForEach-Object { $entry[$_.Name] = $_.Value }
                            }
                            foreach ($kn in @($cleanFields.Keys)) { $entry[$kn] = $cleanFields[$kn] }
                            # Đổi url → xoá toàn bộ creds còn lại: giữ user/app_password
                            # qua URL mới là kênh gửi credential thật tới host attacker
                            if ($cleanFields.ContainsKey("url") -and $cleanFields.url -ne $oldUrl) {
                                $entry = @{ url = $cleanFields.url }
                            }
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
                        }.GetNewClosure())
                        Send-Json $ctx @{ pending = $rid; msg = "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để lưu" } 202
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
                    $applySetup = {
                        New-Item -ItemType Directory -Force -Path $McDir | Out-Null
                        Save-Json $ConfigFp @{ language = $lang; learner_name = $name }
                        # Đồng bộ tên + recipes (công thức nhanh) vào manifest —
                        # recipes đi kèm pack ngôn ngữ nên sidebar đúng lệnh, đúng tiếng
                        $mf = Join-Path $McDir "manifest.json"
                        try {
                            $m = Get-Content $mf -Raw -Encoding UTF8 | ConvertFrom-Json
                            if ($name) {
                                $m | Add-Member -NotePropertyName learner_name -NotePropertyValue $name -Force
                            }
                            $rec = Load-Json (Join-Path $SkillPacks "recipes\$lang.json") @{}
                            if ($rec -and $rec.recipes) {
                                $m | Add-Member -NotePropertyName recipes -NotePropertyValue $rec.recipes -Force
                            }
                            Save-Json $mf $m
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
                    }.GetNewClosure()
                    # Setup đã chạy rồi (config có language) mà bị gọi lại → agent
                    # có thể đang cố đè skills/config — qua card xác nhận. Lần đầu
                    # thật (onboarding) thì chạy luôn, không cần card.
                    $cfg = Load-Json $ConfigFp @{}
                    if ($cfg -and $cfg.language) {
                        $rid = New-Gate "Chạy lại thiết lập ban đầu — sẽ cài đè bộ skill?" $applySetup
                        Send-Json $ctx @{ pending = $rid; msg = "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để chạy lại" } 202
                    } else {
                        & $applySetup
                        Send-Json $ctx @{ ok = $true }
                    }
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
            elseif ($ctx.Request.HttpMethod -eq "POST" -and $path -eq "/api/emit-event") {
                # Endpoint nội bộ: ext-bridge/tools phát event phụ (inj_suspect,
                # perm:auto, env_scrub, pack_applied, update_applied) vào event
                # stream để beacon đếm. Whitelist type — không nhận gì lạ.
                $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                $body = $reader.ReadToEnd() | ConvertFrom-Json
                $t = [string]$body.t
                if ($t -in @("inj_suspect","perm:auto","env_scrub","pack_applied","update_applied")) {
                    # parity .py — giữ đủ field để beacon/dashboard đọc
                    $ev = [ordered]@{ t = $t }
                    foreach ($k in @("action","patterns","dropped","title","pattern","msg")) {
                        if ($null -ne $body.$k) { $ev[$k] = $body.$k }
                    }
                    Push-Event $ev
                    Send-Json $ctx @{ ok = $true }
                } else {
                    Send-Json $ctx @{ err = "type không nhận" } 400
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
    Stop-Brain   # Job Object cũng đóng → cả cây process của não chết sạch
}
