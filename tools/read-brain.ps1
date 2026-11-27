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
    'docker','podman','su','doas',
    # batch audit-3/audit-5 (trước sót — mirror cmd_deny.py):
    'brew','gh','java','jshell','dotnet','mono','lua','luajit',
    'r','rscript','tclsh','groovy','scala','kotlin','xcodebuild',
    'plutil','go','cargo','julia','ipython','pypy','micropython',
    'gjs','qjs','nodemon','tsx','ts-node','bunx','uv','uvx','pipx',
    'conda','poetry','pdm','jupyter','vitest','jest','mocha','clj',
    'clojure','lein','stack','cabal','mise','asdf'
)
# họ interpreter hậu tố version (python3.12…) — mirror _BRAIN_CMD_DENY_RE
$DenyRe = [regex]'(?x)^(?:
    (i?python|pypy|jython|micropython|pyspark)[\d.]*w? | py |
    perl[\d.]* | ruby[\d.]* | php[\d.]* | pip[\d.]* | node(js)?[\d.]* |
    (ba|z|fi|da|k|c|tc)?sh\d* | pwsh[\d.]* |
    lua(jit)?[\d.]* | tclsh[\d.]* | r(script)?[\d.]* |
    java\w* | jshell | groovy\w* | scala | kotlin[\w.]* | dotnet | mono |
    brew | gh | go | cargo | xcodebuild | plutil | shortcuts |
    bundle | irb | pry | julia[\w.]* | gjs | qjs | runghc | ghci
)$'
function Clean-Brain($v) {
    $t = [string]$v
    $tl = $t.ToLower()
    if ($t -match '^[A-Za-z0-9_.-]+$' -and $Deny -notcontains $tl -and
        $tl -notmatch $DenyRe) {
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
