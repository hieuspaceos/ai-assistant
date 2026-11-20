#!/usr/bin/env bash
# ============================================================
#  TRO LY AI — mo khoa hoc cua ban (macOS/Linux)
#  Chay file nay de bat dau hoc:
#    bash start.sh
#  Mo 3 thu: trang web khoa hoc + chat bridge + cau noi extension.
# ============================================================
cd "$(dirname "$0")"
ROOT="$(pwd)"
# log để trong repo (đã gitignore) — cùng một chỗ với log Windows, dễ tìm
LOGDIR="$ROOT/.logs"
mkdir -p "$LOGDIR"

echo ""
echo "  Dang mo khoa hoc, cho mot chut nhe..."
echo ""

# --- Kiem tra devin CLI ---
if ! command -v devin >/dev/null 2>&1; then
  echo "  [X] Chua co Devin CLI. Ban can cai truoc - xem file SETUP.md"
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "  [X] Chua co python3 - can de chay bridge va portal"
  exit 1
fi

# --- 1. Portal tinh (cong 8080) — chan dotfiles (.devin chua secrets) ---
python3 tools/serve.py 8080 "$ROOT" >"$LOGDIR/portal.log" 2>&1 &
echo "  portal    : http://localhost:8080/web/"

# --- 2. chat-bridge (cong 7682): che do Chat kieu tin nhan ---
python3 tools/chat-bridge.py 7682 "$ROOT" >"$LOGDIR/chat-bridge.log" 2>&1 &

# --- 3. ext-bridge (cong 7684): cau noi extension trong trinh duyet ---
python3 tools/ext-bridge.py 7684 "$ROOT" >"$LOGDIR/ext-bridge.log" 2>&1 &

# --- 4. ttyd (cong 7681, tuy chon): che do Terminal nhung web ---
if command -v ttyd >/dev/null 2>&1; then
  ttyd -p 7681 -i 127.0.0.1 -W devin >"$LOGDIR/ttyd.log" 2>&1 &
else
  echo "  [!] Khong co ttyd - che do Terminal khong dung duoc (Chat van binh thuong)"
fi

sleep 2

# --- Bao loi ro rang neu dich vu nao khong len duoc ---
curl -sf -o /dev/null http://127.0.0.1:8080/web/ || \
  echo "  [!] Portal chua len - co the port 8080 dang bi chiem. Xem $LOGDIR/portal.log"
curl -sf -o /dev/null http://127.0.0.1:7682/api/health || \
  echo "  [!] Chat bridge chua len - che do Chat se trong. Xem $LOGDIR/chat-bridge.log"

# --- Mo trang web khoa hoc ---
URL="http://localhost:8080/web/"
if command -v open >/dev/null 2>&1; then
  open "$URL"          # macOS
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"      # Linux
else
  echo "  Mo tay: $URL"
fi

echo ""
echo "  Xong! Trang khoa hoc da mo trong trinh duyet."
echo "  Muon tat: Ctrl+C hoac dong cua so terminal nay."
echo ""

# Giu tien trinh cha + don dep khi thoat
trap 'kill 0' EXIT
wait
