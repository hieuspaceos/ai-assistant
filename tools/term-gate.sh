#!/bin/bash
# term-gate.sh — "lễ tân" trước não trong chế độ Terminal (ttyd).
# ttyd không tự xác thực được (flag -O chỉ so hostname, bỏ port) nên mỗi
# kết nối spawn script này: đòi mã kết nối đúng mới exec não.
# $1 = ?arg= từ URL (ttyd -a append CUỐI argv). Não lấy từ env BRAIN_TERM.
# Shebang bash bắt buộc — `read -t` không phải POSIX, sh=dash (Linux) chết.
#
# TROLY_TERM_STRICT=1: bỏ qua $1, luôn hỏi tay — token qua argv hiện trong
# `ps` của máy multi-user. Chậm hơn (không autofill) nhưng token không lộ.
t="$1"
if [ "$TROLY_TERM_STRICT" = "1" ]; then t=""; fi

tries=0
while [ "$t" != "$BRIDGE_TOKEN" ]; do
  tries=$((tries+1))
  if [ "$tries" -gt 3 ]; then echo "Sai ma ket noi qua nhieu lan."; sleep 2; exit 1; fi
  if [ -n "$t" ]; then echo "Sai ma ket noi, thu lai."; fi
  printf "Ma ket noi (xem trong portal > Cai dat): "
  read -r -t 90 t || exit 1
done

# Não terminal-mode: sandbox-exec chỉ có trên macOS; Windows đi nhánh .cmd
# của ttyd; Linux chạy thẳng. BRAIN_TERM exec TRỰC TIẾP, KHÔNG qua `sh -c`
# để không có eval path — và phải kiểm lại ở đây: start.sh đọc brain.json
# thô, nên file sửa tay (terminal:"sh") mở shell trần cho ai có mã kết
# nối. Giữ đồng bộ với BRAIN_CMD_DENY trong cmd_deny.py.
# Hạ chữ thường trước khi so: FS macOS/Windows không phân biệt hoa-thường
# → "Python3" exec vẫn ra python3 dù pattern "python3" không khớp.
_bt="$(printf '%s' "$BRAIN_TERM" | tr '[:upper:]' '[:lower:]')"
case "$_bt" in
  ""|*[!a-z0-9_.-]*|\
  py|python|python3|sh|bash|zsh|fish|dash|env|nice|xargs|find|make|rake|\
  osascript|node|deno|bun|ruby|perl|php|pwsh|powershell|cmd|\
  git|awk|gawk|nawk|mawk|tar|vim|vi|nvim|nano|emacs|less|more|most|man|\
  nohup|setsid|timeout|flock|watch|parallel|shortcuts|xcrun|docker|podman|su|doas|\
  npm|npx|yarn|pnpm|gem|pip|pip3|curl|wget|nc|ncat|socat|busybox|open|\
  rundll32|regsvr32|mshta|wscript|cscript|wmic|certutil|bitsadmin|eval|exec|\
  launchctl|security|pbcopy|pbpaste|screencapture|\
  ssh|scp|sftp|rsync|ftp|telnet|rlogin|rsh|tmux|screen|script|expect|\
  lldb|gdb|dtrace|automator|swift|sudo|crontab|at|atq|atrm|sandbox-exec|\
  sqlite3|mysql|psql|redis-cli|mongosh|mongo|qlmanage|spctl|codesign|\
  brew|gh|java|jshell|dotnet|mono|lua|luajit|r|rscript|tclsh|groovy|\
  scala|kotlin|xcodebuild|plutil|go|cargo|julia|ipython|pypy|\
  micropython|gjs|qjs|nodemon|tsx|ts-node|bunx|uv|uvx|pipx|conda|\
  poetry|pdm|jupyter|vitest|jest|mocha|clj|clojure|lein|stack|cabal|\
  mise|asdf|\
  python*|perl*|php*|pip*|ruby*|node*|lua*|tclsh*|rscript*|java*|\
  julia*|groovy*|kotlin*|ipython*|pypy*|jython*|micropython*|pyspark*|\
  ?sh|??sh|*sh[0-9]*|bundle|irb|pry|runghc|ghci)
    echo "Lenh terminal khong hop le - chay devin."; BRAIN_TERM=devin ;;
esac
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SB="$ROOT/.devin/agent.sb"
if [ "$(uname -s)" = "Darwin" ] && [ -f "$SB" ] \
   && command -v sandbox-exec >/dev/null 2>&1 \
   && [ "$TROLY_NO_SANDBOX" != "1" ]; then
  exec sandbox-exec -f "$SB" "${BRAIN_TERM:-devin}"
fi
exec "${BRAIN_TERM:-devin}"
