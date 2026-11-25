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

# --- Kiem tra python3 truoc (can de doc brain.json va chay bridge) ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "  [X] Chua co python3 - can de chay bridge va portal"
  exit 1
fi

# --- Doc "nao" tu brain.json (mac dinh devin, doi duoc trong onboarding) ---
BRAIN_CMD="devin"; BRAIN_TERM="devin"
if [ -f "$ROOT/brain.json" ]; then
  BRAIN_CMD="$(python3 -c "import json;print(json.load(open('$ROOT/brain.json')).get('cmd','devin'))" 2>/dev/null || echo devin)"
  BRAIN_TERM="$(python3 -c "import json;print(json.load(open('$ROOT/brain.json')).get('terminal','devin'))" 2>/dev/null || echo devin)"
fi
if ! command -v "$BRAIN_CMD" >/dev/null 2>&1; then
  echo "  [!] Chua co '$BRAIN_CMD' (nao tro ly) - che do Chat se khong chay."
  echo "      Cai no, hoac mo portal roi doi sang nao khac trong muc thiet lap."
fi

# --- "Chia khoa nha" dung chung cho cac bridge — sinh 1 lan truoc khi
# launch (tranh race giua cac process), export de ttyd/nao ke thua ---
TOKEN_FILE="$ROOT/.devin/bridge.token"
mkdir -p "$ROOT/.devin"
if [ ! -s "$TOKEN_FILE" ]; then
  (umask 077; python3 -c "import secrets;print(secrets.token_hex(24))" > "$TOKEN_FILE")
fi
BRIDGE_TOKEN="$(cat "$TOKEN_FILE")"
export BRIDGE_TOKEN
export BRAIN_TERM          # term-gate.sh lay nao tu env, khong qua argv

# --- Seatbelt profile (macOS): sinh san de term-gate/nao sandbox ngay
# spawn dau tien; chat-bridge cung regen moi spawn nen day la phong bi
# cho ca Terminal mode. Loi → bo qua, khong ket boot ---
if [ "$(uname -s)" = "Darwin" ]; then
  python3 tools/gen-sandbox.py "$ROOT" >/dev/null 2>&1 || true
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
  # ttyd KHONG tu xac thuc → moi ket noi phai qua term-gate: doi ma ket
  # noi roi moi exec nao. -a cho phep portal tu dien ma qua ?arg= (append
  # cuoi argv). -O so hostname Origin voi Host → chan trang web NGOAI
  # mo ws://127.0.0.1:7681 bom process term-gate (WS khong chiu same-
  # origin); portal localhost:* van qua vi chi so hostname, bo port.
  ttyd -p 7681 -i 127.0.0.1 -W -a -O sh tools/term-gate.sh >"$LOGDIR/ttyd.log" 2>&1 &
else
  echo "  [!] Khong co ttyd - che do Terminal khong dung duoc (Chat van binh thuong)"
fi

sleep 2

# --- Bao loi ro rang neu dich vu nao khong len duoc ---
curl -sf -o /dev/null http://127.0.0.1:8080/web/ || \
  echo "  [!] Portal chua len - co the port 8080 dang bi chiem. Xem $LOGDIR/portal.log"
curl -sf -o /dev/null http://127.0.0.1:7682/api/health || \
  echo "  [!] Chat bridge chua len - che do Chat se trong. Xem $LOGDIR/chat-bridge.log"

# --- Mo trang web khoa hoc (kem ma ket noi de portal goi duoc bridge) ---
URL="http://localhost:8080/web/?t=$BRIDGE_TOKEN"
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
