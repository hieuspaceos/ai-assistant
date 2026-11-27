"""cmd_deny.py — deny-list lệnh interpreter/exec-helper dùng CHUNG cho
chat-bridge (não tự nhập + term-gate), apply-pack (lint exec_allowlist)
và content_guard.exec_allowed (enforcement).

Lý do tách (audit-5 F9): cùng một "danh sách lệnh = code-exec trần" sống
ở 3 điểm — lint pack, check brain.json, match allowlist lúc chạy.
Nhân bản = drift chắc chắn, drift ở đây là kênh chạy code tuỳ ý sau
consent. Module thuần hàm, không state, chỉ import re + fnmatch.

Tên underscore bắt buộc: file gạch ngang (apply-pack.py…) không import
được — module dùng chung phải import được bình thường."""
import fnmatch
import re

# Interpreter/exec helper không được làm "não" tự nhập — args của chúng
# là code-exec trần (python3 -c, find -exec, npm run). Preset npx đã cover
# adapter hợp lệ nên deny npx/npm ở custom cũng không mất gì.
BRAIN_CMD_DENY = {
    "python3", "python", "py", "sh", "bash", "zsh", "fish", "dash",
    "osascript", "node", "deno", "bun", "ruby", "perl", "php", "pwsh",
    "powershell", "cmd", "env", "nice", "xargs", "find", "make", "rake",
    "npm", "npx", "yarn", "pnpm", "gem", "pip", "pip3", "curl", "wget",
    "nc", "ncat", "socat", "busybox", "open", "rundll32", "regsvr32",
    "mshta", "wscript", "cscript", "wmic", "certutil", "bitsadmin",
    "eval", "exec", "launchctl",
    # đọc credential/clipboard/màn hình
    "security", "pbcopy", "pbpaste", "screencapture",
    # exfil kênh mạng + shell bọc (pty → chạy lệnh tự do)
    "ssh", "scp", "sftp", "rsync", "ftp", "telnet", "rlogin", "rsh",
    "tmux", "screen", "script", "expect",
    # debug/inject + runtime + cơ chế chạy ngoài/lách sandbox
    "lldb", "gdb", "dtrace", "automator", "swift", "sudo",
    "crontab", "at", "atq", "atrm", "sandbox-exec",
    # DB client — lệnh "não" không bao giờ là shell database
    "sqlite3", "mysql", "psql", "redis-cli", "mongosh", "mongo",
    "qlmanage", "spctl", "codesign",
    # code-exec qua args/config: git -c core.pager=sh, awk 'BEGIN{system()}',
    # tar --checkpoint-action, editor/pager shell-escape (vim :!, less !cmd),
    # wrapper bọc lệnh tuỳ ý, container mount host
    "git", "awk", "gawk", "nawk", "mawk", "tar", "vim", "vi", "nvim",
    "nano", "emacs", "less", "more", "most", "man", "nohup", "setsid",
    "timeout", "flock", "watch", "parallel", "shortcuts", "xcrun",
    "docker", "podman", "su", "doas",
    # exec-qua-args hoặc build+run còn sót (audit-3 M3): brew ruby -e,
    # gh extension exec, jshell/java, dotnet/mono script, R -e, go run…
    "brew", "gh", "java", "jshell", "dotnet", "mono", "lua", "luajit",
    "r", "rscript", "tclsh", "groovy", "scala", "kotlin", "xcodebuild",
    "plutil", "go", "cargo", "julia", "ipython", "pypy", "micropython",
    "gjs", "qjs",
    # runner đời mới còn sót (audit-lại): nodemon/tsx/ts-node chạy JS,
    # uv/uvx/pipx/conda/poetry bọc python, jupyter/vitest/jest/mocha exec
    # file test/notebook, clj/lein/stack/cabal chạy Clojure/Haskell —
    # tất cả đều là exec-via-args y hệt python3.12 bị chặn.
    "nodemon", "tsx", "ts-node", "bunx", "uv", "uvx", "pipx", "conda",
    "poetry", "pdm", "jupyter", "vitest", "jest", "mocha", "clj",
    "clojure", "lein", "stack", "cabal", "mise", "asdf",
}

# Interpreter/compiler có hậu tố VERSION (python3.12, perl5.40, php8.2,
# pip3.11, ruby3.3) hay clone (ipython, pypy, jython, micropython, luajit)
# lọt exact-match — deny thêm bằng regex. Denylist không bao giờ đầy đủ:
# custom brain vẫn = chạy lệnh tuỳ ý sau consent, list chỉ chặn tên
# hiển nhiên — text card phải nói đúng bản chất đó.
_BRAIN_CMD_DENY_RE = re.compile(r"""^(?:
    (i?python|pypy|jython|micropython|pyspark)[\d.]*w? | py |
    perl[\d.]* | ruby[\d.]* | php[\d.]* | pip[\d.]* | node(js)?[\d.]* |
    (ba|z|fi|da|k|c|tc)?sh\d* | pwsh[\d.]* |
    lua(jit)?[\d.]* | tclsh[\d.]* | r(script)?[\d.]* |
    java\w* | jshell | groovy\w* | scala | kotlin[\w.]* | dotnet | mono |
    brew | gh | go | cargo | xcodebuild | plutil | shortcuts |
    bundle | irb | pry | julia[\w.]* | gjs | qjs | runghc | ghci
)$""", re.X | re.I)


def brain_cmd_denied(name):
    """Deny exact-set HOẶC regex (interpreter hậu tố version lọt
    exact-match — audit-3 M3)."""
    return name in BRAIN_CMD_DENY or bool(_BRAIN_CMD_DENY_RE.match(name))


def first_token(cmdline):
    """Token đầu của một pattern/lệnh dạng string ("pwsh -File x" →
    "pwsh"; "./tool.sh" → "tool.sh") — dùng cho lint exec_allowlist và
    exec_allowed: so deny-set trên TÊN LỆNH thay vì substring (deny-set
    có tên ngắn r/at/go/env — substring khớp mọi pattern)."""
    tok = (str(cmdline).split() or [""])[0].lower()
    # bóc path: "./x", "C:\x", "/usr/bin/x" → tên lệnh
    tok = tok.replace("\\", "/").rsplit("/", 1)[-1]
    # bóc hậu tố Windows: pwsh.exe → pwsh
    return re.sub(r"\.(exe|bat|cmd|com|ps1)$", "", tok)


# Glob meta + quote — token pattern có thể dấu tên lệnh trong glob mà
# exec-match vẫn khớp: "git*" khớp "git -c …", "g[i]t"/"g[!x]t" khớp
# git, '"git"' shell bóc quote ra git (audit-lại-3: brain_cmd_denied
# so thẳng token thô → hết mấy kiểu này đều lọt).
_GLOB_QUOTE = re.compile(r"[\*\?\[\]\!\"'`]")


def pattern_cmd_denied(pat_tok):
    """Token đầu của một PATTERN allowlist (đã qua first_token) có thể
    khớp một lệnh bị deny không — so 3 lớp:
    1. bóc glob-meta/quote rồi so thẳng: git*→git, [p]wsh→pwsh, "git"→git
    2. bóc thêm digit/dot cho họ version: python3.1?→python
    3. reverse fnmatch: token-glob khớp tên nào trong deny-set
       (g[!x]t khớp git — class negation strip không bóc được)
    """
    t = str(pat_tok)
    plain = _GLOB_QUOTE.sub("", t)
    if brain_cmd_denied(plain):
        return True
    if brain_cmd_denied(re.sub(r"[\d.]", "", plain)):
        return True
    return any(fnmatch.fnmatchcase(n, t) for n in BRAIN_CMD_DENY)
