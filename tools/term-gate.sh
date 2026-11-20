#!/bin/sh
# term-gate.sh — "lễ tân" trước não trong chế độ Terminal (ttyd).
# ttyd không tự xác thực được (flag -O chỉ so hostname, bỏ port) nên mỗi
# kết nối spawn script này: đòi mã kết nối đúng mới exec não.
# $1 = ?arg= từ URL (ttyd -a append CUỐI argv). Não lấy từ env BRAIN_TERM.
t="$1"
if [ -z "$t" ]; then
  printf "Ma ket noi (xem trong portal > Cai dat): "
  read -r -t 90 t || exit 1
fi
[ "$t" = "$BRIDGE_TOKEN" ] || { echo "Sai ma ket noi."; sleep 2; exit 1; }

# Terminal mode cũng chịu sandbox như Chat mode — não qua cửa nào cũng
# bị Seatbelt khoá theo permissions.json. Profile do launcher/start.sh
# sinh lúc boot (chat-bridge regen mỗi spawn); chưa có file → chạy
# thường, không kẹt lối vào.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SB="$ROOT/.devin/agent.sb"
if [ "$(uname -s)" = "Darwin" ] && [ -f "$SB" ] \
   && command -v sandbox-exec >/dev/null 2>&1 \
   && [ "$TROLY_NO_SANDBOX" != "1" ]; then
  exec sandbox-exec -f "$SB" "${BRAIN_TERM:-devin}"
fi
exec "${BRAIN_TERM:-devin}"
