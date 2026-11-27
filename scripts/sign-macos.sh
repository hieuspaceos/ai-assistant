#!/bin/bash
# sign-macos.sh — ký + notarize + verify dist/troly (macOS)
#
# Dùng: bash scripts/sign-macos.sh [đường-dẫn-binary]   (mặc định dist/troly)
#
# Yêu cầu 1 lần:
#   1. Cert "Developer ID Application" trong keychain (tạo ở developer.apple.com)
#   2. API key App Store Connect (.p8) + Issuer ID → lưu profile:
#        xcrun notarytool store-credentials troly-notary \
#            --key <AuthKey_XXX.p8> --key-id <KEYID> --issuer <UUID>
# Sau đó script này tự chạy hết: sign → zip → notarize --wait → verify.
# Staple KHÔNG bắt buộc cho binary trần (stapler chỉ nhét ticket vào
# bundle .app/.dmg/.pkg; Mach-O lẻ vẫn qua Gatekeeper bằng tra ticket
# online — máy cần mạng lần chạy đầu).
set -euo pipefail

BIN="${1:-dist/troly}"
IDENTITY="${TROLY_SIGN_IDENTITY:-Developer ID Application: Hieu Phan Trong (KHZWP95P4J)}"
PROFILE="${TROLY_NOTARY_PROFILE:-troly-notary}"
ENT="$(dirname "$0")/entitlements.plist"

[ -f "$BIN" ] || { echo "không thấy $BIN — build trước (pyinstaller)" >&2; exit 1; }
[ -f "$ENT" ] || { echo "thiếu $ENT" >&2; exit 1; }

echo "== 1. codesign (hardened runtime + entitlements)"
codesign --force --options runtime --timestamp --entitlements "$ENT" \
    --sign "$IDENTITY" "$BIN"

echo "== 2. zip nộp Apple"
ZIP="$(mktemp /tmp/troly-notary-XXXX.zip)"
ditto -c -k --keepParent "$BIN" "$ZIP"

echo "== 3. notarize (chờ kết quả)"
xcrun notarytool submit "$ZIP" --keychain-profile "$PROFILE" --wait
rm -f "$ZIP"

echo "== 4. verify — mô phỏng máy user: quarantine rồi chạy thật"
QBIN="$(mktemp /tmp/troly-quar-XXXX)"
cp "$BIN" "$QBIN"
chmod +x "$QBIN"   # mktemp tạo mode 600 — cp đè vẫn thiếu exec bit
xattr -w com.apple.quarantine "0083;00000000;Safari;" "$QBIN"
"$QBIN" --help >/dev/null 2>&1; rc=$?
# troly detect "đang chạy sẵn" cũng trả 0 — mọi exit ≠126/127 nghĩa là
# Gatekeeper đã cho chạy (127=not found, 126=permission/quarantine chặn)
if [ "$rc" -le 1 ]; then
    echo "OK — binary qua Gatekeeper (quarantined vẫn chạy được)"
else
    rm -f "$QBIN"
    echo "FAIL — binary quarantined không chạy (exit $rc)" >&2
    exit 1
fi
rm -f "$QBIN"
echo "Xong — $BIN đã sign + notarized, sẵn sàng phát."
