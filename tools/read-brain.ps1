# read-brain.ps1 — đọc brain.json, in "cmd|terminal" ĐÃ VALIDATE.
#
# Dùng chung cho start.bat + chat-terminal.ps1. Giá trị thô từ brain.json
# đi thẳng vào %BRAIN_CMD%/%BRAIN_TERM% rồi được mở rộng trong batch
# (where %BRAIN_CMD%, "%BRAIN_TERM%" trong term-gate.cmd) — ký tự &, |, "
# trở thành command injection TRƯỚC KHI deny-list kịp so tên lệnh, nên
# phải lọc charset ở đây (parity check trong load_brain() của bridge).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Deny = @(
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
function Clean-Brain($v) {
    $t = [string]$v
    if ($t -match '^[A-Za-z0-9_.-]+$' -and $Deny -notcontains $t.ToLower()) {
        return $t
    }
    return 'devin'
}
$cmd = 'devin'; $term = 'devin'
try {
    $b = Get-Content (Join-Path $Root 'brain.json') -Raw -Encoding UTF8 |
         ConvertFrom-Json
    if ($b.cmd) { $cmd = Clean-Brain $b.cmd }
    if ($b.terminal) { $term = Clean-Brain $b.terminal }
} catch {}
Write-Output "$cmd|$term"
