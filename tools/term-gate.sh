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
exec "${BRAIN_TERM:-devin}"
