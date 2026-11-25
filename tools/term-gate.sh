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
# của ttyd; Linux chạy thẳng. BRAIN_TERM được validate tên-trần lúc load
# brain.json — exec trực tiếp, KHÔNG qua `sh -c` để không có eval path.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SB="$ROOT/.devin/agent.sb"
if [ "$(uname -s)" = "Darwin" ] && [ -f "$SB" ] \
   && command -v sandbox-exec >/dev/null 2>&1 \
   && [ "$TROLY_NO_SANDBOX" != "1" ]; then
  exec sandbox-exec -f "$SB" "${BRAIN_TERM:-devin}"
fi
exec "${BRAIN_TERM:-devin}"
