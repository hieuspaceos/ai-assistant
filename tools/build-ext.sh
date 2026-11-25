#!/bin/sh
# build-ext.sh — đóng gói extension/ thành zip upload Chrome Web Store.
#
# GIỮ trường `key` trong manifest.json: EXT_ID được derive từ key —
# bỏ key là đổi ID → phải sửa EXT_ID trong web/app.js + mọi policy
# force-install đã cài. Zip phải chứa file ở ROOT (không bọc folder)
# và không kèm file rác (.DS_Store, *.pem chữ ký tạm...).
#
# Chạy: sh tools/build-ext.sh   →  dist/troly-ext-<ver>.zip
set -e
cd "$(dirname "$0")/.."

VER=$(python3 -c "import json;print(json.load(open('extension/manifest.json'))['version'])")
OUT="dist/troly-ext-$VER.zip"
mkdir -p dist
rm -f "$OUT"

# lint nhanh trước khi gói
python3 - <<'EOF'
import json, sys
m = json.load(open('extension/manifest.json'))
assert m.get('key'), 'manifest thiếu key — EXT_ID sẽ đổi!'
assert m['manifest_version'] == 3
ec = m.get('externally_connectable', {}).get('matches', [])
assert all('localhost' in u or '127.0.0.1' in u for u in ec), \
    'externally_connectable mở ra ngoài localhost!'
need = {'icon16.png','icon48.png','icon128.png'}
import os
miss = [f for f in need if not os.path.exists('extension/'+f)]
assert not miss, f'thiếu icon: {miss}'
print('manifest ok — key giữ nguyên, connectable chỉ localhost')
EOF

# zip: cd vào extension/ để file nằm ở root của zip
( cd extension && zip -q -r "../$OUT" . \
    -x '.DS_Store' '*/.DS_Store' '*.pem' '*.crx' '*.zip' '__MACOSX*' )

echo "== $OUT"
unzip -l "$OUT" | head -20
python3 -c "import zipfile;z=zipfile.ZipFile('$OUT');print('files:',len(z.namelist()));assert 'manifest.json' in z.namelist(),'manifest không ở root'"
echo "OK — upload file này lên Chrome Web Store (unlisted)"
