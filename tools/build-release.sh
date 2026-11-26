#!/bin/bash
# build-release.sh — cổng phát hành của vendor. Chạy ở máy dev trước khi
# đẩy release; MỌI bước fail → dừng, không phát bản lởm.
#
#   bash tools/build-release.sh <version>
#
# Cổng (theo thứ tự):
#   1. git sạch (uncommitted = release không truy được nguồn)
#   2. VERSION file khớp tham số
#   3. CHANGELOG.md có mục cho version đó — khách/máy nhìn thấy gì mới
#   4. chạy cả test suite (test-bridges, test-gates, test-parity,
#      test-fleet, test-packs, test-distribution nếu có)
#   5. zip → secret-scan nội dung zip (API key/token lọt vào release =
#      leak cho mọi máy khách) — học release gate của GoClaw
#   6. ký ed25519 (private key ~/.troly-release-key hoặc $TROLY_RELEASE_KEY)
#   7. xuất releases/<ver>/ : troly-<ver>.zip + manifest.json
#
# .devin/ bị TÁCH: chỉ .devin/skill-packs/ đi theo release — token,
# machine.key, license, fleet.json, skills cài sẵn là state máy khách.
set -euo pipefail
cd "$(dirname "$0")/.."
VER="${1:?cần version — bash tools/build-release.sh 1.0.3}"
KEY_FP="${TROLY_RELEASE_KEY:-$HOME/.troly-release-key}"

die() { echo "GATE FAIL: $1" >&2; exit 1; }

# --- 1. git sạch ---
[ -d .git ] && [ -n "$(git status --porcelain 2>/dev/null)" ] \
    && die "working tree chưa sạch — commit/stash trước khi phát"

# --- 2. VERSION khớp ---
[ "$(cat VERSION)" = "$VER" ] \
    || die "VERSION file=$(cat VERSION) ≠ tham số $VER — sửa VERSION trước"

# --- 3. CHANGELOG ---
[ -f CHANGELOG.md ] || die "thiếu CHANGELOG.md"
grep -q "^## \[$VER\]\|^## $VER" CHANGELOG.md \
    || die "CHANGELOG.md chưa có mục cho $VER"

# --- 4. test suite ---
for t in tools/test-*.py; do
    echo "== $t"
    python3 "$t" || die "$t FAIL — sửa trước khi phát"
done

# --- 5. zip ---
OUT="releases/$VER"
mkdir -p "$OUT"
ZIP="$OUT/troly-$VER.zip"
rm -f "$ZIP"
zip -qr "$ZIP" \
    tools web extension templates collector-web docs \
    .devin/skill-packs \
    AGENTS.md CLAUDE.md SETUP.md README.md requirements.txt \
    VERSION start.sh start.bat \
    -x "*/__pycache__/*" "*.pyc" "tools/beacon.ps1.bak" \
    -x "collector.json" "collector-data/*"

# --- 6. secret-scan nội dung zip ---
python3 - "$ZIP" <<'PY'
import re, sys, zipfile
PAT = re.compile(
    rb"(sk-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9-]{20,}"
    rb"|AIza[0-9A-Za-z_-]{30,}|ghp_[0-9A-Za-z]{30,}"
    rb"|AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,}"
    rb"|-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"
    rb"|bridge\.token.*[0-9a-f]{32,})")
hits = []
with zipfile.ZipFile(sys.argv[1]) as z:
    for n in z.namelist():
        if n.endswith("/") or n.endswith((".png", ".jpg", ".ico",
                                          ".zip", ".mp4")):
            continue
        m = PAT.search(z.read(n))
        if m:
            hits.append((n, m.group(0)[:40].decode("utf-8", "replace")))
if hits:
    for n, s in hits:
        print(f"SECRET-SCAN FAIL: {n}: {s}…", file=sys.stderr)
    sys.exit("release zip chứa thứ trông giống secret — dọn trước khi phát")
print("secret-scan: sạch")
PY

# --- 7. ký ---
[ -f "$KEY_FP" ] || die "thiếu private key — đặt ở $KEY_FP hoặc \$TROLY_RELEASE_KEY"
python3 tools/sign-release.py --key "$KEY_FP" --zip "$ZIP" \
    --version "$VER" --out "$OUT/manifest.json"

echo
echo "RELEASE OK: $ZIP"
cat "$OUT/manifest.json"
echo
echo "Đẩy lên origin:  scp -r $OUT/* <vps>:<site>/releases/"
echo "Hoặc collector:  POST /api/releases/<file> + /api/releases" \
     "(header X-Admin-Key: <release_key> trong collector.json)"
