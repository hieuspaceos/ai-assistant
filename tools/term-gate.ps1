# term-gate.ps1 — bản Windows của term-gate.sh (THAY term-gate.cmd).
#
# Tại sao không dùng .cmd: mọi expansion của %1/%t% trong batch được
# re-parse — payload ?arg= chứa " phá vòng nháy của `if "%t%"==...` →
# & <lệnh> chạy trực tiếp = RCE qua link http://localhost:7681/?arg=%22%26<cmd>
# mở trong trình duyệt học viên (trang web NGOÀI nhúng iframe/redirect —
# ttyd -O chỉ so Origin của WS, không chặn GET trang). PowerShell nhận
# argv không re-lex nên toàn bộ gate sống ở đây.
#
# -GateArg = ?arg= từ URL (ttyd -a append CUỐI argv). Não lấy từ env
# BRAIN_TERM. TROLY_TERM_STRICT=1: bỏ qua arg, luôn hỏi tay — token qua
# argv/URL hiện trong `ps`/history của máy multi-user.
param([string]$GateArg = "")

$t = $GateArg
if ($env:TROLY_TERM_STRICT -eq "1") { $t = "" }

# Mã kết nối sai → hỏi lại, tối đa 3 lần. So sánh ordinal (case-sensitive)
# — token là hex nên tương đương compare_digest cho input này.
# Read-Host không có timeout được như "read -t" trên Unix — hạn chế đã
# ghi trong docs/SECURITY.md.
$tries = 0
while (-not [string]::Equals($t, $env:BRIDGE_TOKEN, [StringComparison]::Ordinal)) {
    $tries += 1
    if ($tries -gt 3) {
        Write-Host "Sai ma ket noi qua nhieu lan."
        exit 1
    }
    if ($t) { Write-Host "Sai ma ket noi, thu lai." }
    $t = Read-Host "Ma ket noi (xem trong portal > Cai dat)"
}

# BRAIN_TERM exec trực tiếp — brain.json sửa tay (terminal:"powershell")
# mở shell trần trong ttyd cho ai có mã kết nối. Charset + deny-list giữ
# đồng bộ BRAIN_CMD_DENY (chat-bridge.py) / term-gate.sh / read-brain.ps1.
# Ký tự &, |, " phải chặn bằng charset — `& $brain` của PowerShell cũng
# chạy được lệnh nếu giá trị lạ lọt qua.
$brain = [string]$env:BRAIN_TERM
$deny = @(
    'sh','bash','zsh','fish','dash','cmd','powershell','pwsh',
    'python','python3','py','node','deno','bun','ruby','perl','php',
    'wscript','cscript','mshta','rundll32','regsvr32','wmic','certutil',
    'bitsadmin','npm','npx','yarn','pnpm','gem','pip','pip3','curl','wget',
    'nc','ncat','socat','busybox','ssh','scp','sftp','rsync','ftp','telnet',
    'rlogin','rsh','tmux','screen','script','expect','osascript','security',
    'sudo','launchctl','env','nice','xargs','find','make','rake','open',
    'pbcopy','pbpaste','screencapture','lldb','gdb','dtrace','automator',
    'swift','eval','exec','crontab','at','atq','atrm','sandbox-exec',
    'sqlite3','mysql','psql','redis-cli','mongosh','mongo',
    'qlmanage','spctl','codesign',
    'git','awk','gawk','nawk','mawk','tar','vim','vi','nvim',
    'nano','emacs','less','more','most','man','nohup','setsid',
    'timeout','flock','watch','parallel','shortcuts','xcrun',
    'docker','podman','su','doas'
)
if ($brain -notmatch '^[A-Za-z0-9_.-]+$' -or $deny -contains $brain.ToLower()) {
    Write-Host "Lenh terminal khong hop le - chay devin."
    $brain = "devin"
}
& $brain
