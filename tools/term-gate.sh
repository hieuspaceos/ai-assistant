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
  python*|perl*|php*|pip*|ruby*|node*|lua*|tclsh*|rscript*|r[0-9]*|java*|\
  julia*|groovy*|kotlin*|ipython*|pypy*|jython*|micropython*|pyspark*|\
  pwsh*|?sh|??sh|*sh[0-9]*|bundle|irb|pry|runghc|ghci)
    echo "Lenh terminal khong hop le - chay devin."; BRAIN_TERM=devin ;;
esac
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Env allowlist y content_guard.scrub_env — não terminal-mode trước
# thừa hưởng TOÀN BỘ env của launcher (API key của user lọt vào não —
# audit-5 N7). Giữ nhóm base + proxy + TROLY_* động + extras của
# .devin/env-allowlist.json (parity load_env_extra); unset phần còn lại
# trước khi exec não. `env -i` không gọn được nhóm động nên unset.
_tg_keep=" PATH HOME USER USERNAME LOGNAME LANG LC_ALL LC_CTYPE TZ \
TMPDIR TEMP TMP SHELL TERM BRIDGE_TOKEN BRAIN_TERM TROLY_DATA \
XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_RUNTIME_DIR \
HTTP_PROXY HTTPS_PROXY NO_PROXY ALL_PROXY \
http_proxy https_proxy no_proxy all_proxy "
# extras — python3 parse JSON đúng mọi format (parity load_env_extra;
# sed chỉ bắt được "extra" trên 1 dòng), sed làm fallback khi thiếu py
_tg_extras=$(python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(" ".join(str(k) for k in (d.get("extra") or [])
                   if str(k).isidentifier()))
except Exception:
    pass' "$ROOT/.devin/env-allowlist.json" 2>/dev/null \
|| sed -n 's/.*"extra"[[:space:]]*:[[:space:]]*\[\([^]]*\)\].*/\1/p' \
     "$ROOT/.devin/env-allowlist.json" 2>/dev/null \
     | tr ',' ' ' | tr -d "\"'[:blank:]")
for _v in $_tg_extras; do
  case "$_v" in
    *[!A-Za-z0-9_]*|[0-9]*|"") ;;              # tên lạ → bỏ
    *) _tg_keep="$_tg_keep$_v " ;;
  esac
done
for _v in $(env | sed 's/=.*//'); do
  case "$_v" in TROLY_*) continue ;; esac
  # 2>/dev/null: SHELLOPTS/BASHOPTS readonly do bash export — unset
  # fail nhưng không hại, im lỗi khỏi rác terminal
  case "$_tg_keep" in *" $_v "*) ;; *) unset "$_v" 2>/dev/null ;; esac
done
unset _tg_keep _tg_extras _v

SB="$ROOT/.devin/agent.sb"
if [ "$(uname -s)" = "Darwin" ] && [ -f "$SB" ] \
   && command -v sandbox-exec >/dev/null 2>&1 \
   && [ "$TROLY_NO_SANDBOX" != "1" ]; then
  exec sandbox-exec -f "$SB" "${BRAIN_TERM:-devin}"
fi
exec "${BRAIN_TERM:-devin}"
