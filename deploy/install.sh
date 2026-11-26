#!/bin/sh
# install.sh — cài Trợ Lý AI lên macOS (không cần root).
#
# Chạy: sh install.sh [--quiet] [--no-autostart] [~/TroLyAI]
#   --quiet        cài im lặng (MDM) — không hỏi, mặc định tạo LaunchAgent
#   --no-autostart bỏ LaunchAgent (kể cả trong --quiet)
set -e
QUIET=0; NO_AUTOSTART=0
for a in "$@"; do
    case "$a" in
        --quiet) QUIET=1 ;;
        --no-autostart) NO_AUTOSTART=1 ;;
        --*) echo "flag la: $a" >&2; exit 2 ;;
        *) DEST="$a" ;;
    esac
done
DEST="${DEST:-$HOME/TroLyAI}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Cai Tro Ly AI =="
echo "Nguon : $SRC"
echo "Dich  : $DEST"

mkdir -p "$DEST"
# copy theo INCLUDE-list = whitelist của update.py (CODE_DIRS/FILES +
# SEED + .devin/skill-packs). Exclude-list từng lọt secrets/state máy
# dev (secrets.local.json, machine.id, collector-data, .logs, .shots…)
# vào bộ cài NV — include thì artefact mới tự nhiên không đi theo.
# Reinstall: 6 file state của học viên không được đè (mất learner_name
# → máy thành "mới" → pack re-áp exec_allowlist/permissions_template).
# Bài học còn lại cứ đè — seed cập nhật theo gói mới là chủ đích.
STATE="config.json manifest.json bots.json permissions.json connections.json bot.md"
XTRA=""
if [ -d "$DEST/workspace" ]; then
    for f in $STATE; do XTRA="$XTRA --exclude=workspace/$f"; done
fi
TMPF="$(mktemp /tmp/troly-install-XXXXXX)"
tar cf "$TMPF" -C "$SRC" --exclude=__pycache__ \
    --exclude='workspace/.shots' --exclude='workspace/clone-work' \
    --exclude='workspace/.trash' $XTRA \
    tools web extension templates docs collector-web \
    .devin/skill-packs workspace \
    AGENTS.md CLAUDE.md SETUP.md README.md requirements.txt VERSION \
    CHANGELOG.md start.sh start.bat brain.json .gitignore \
    || { echo "  !! loi doc goi nguon — huy cai"; rm -f "$TMPF"; exit 1; }
tar xf "$TMPF" -C "$DEST" \
    || { echo "  !! loi ghi vao $DEST — cai dat do dang"; rm -f "$TMPF"; exit 1; }
rm -f "$TMPF"
echo "  ok — copy xong"

# cạm bẫy: learner_name khác rỗng trong bộ cài = mọi máy NV bị coi là
# "máy cũ" → mycourse_files của pack cty không bao giờ áp
if grep -q '"learner_name"[[:space:]]*:[[:space:]]*"[^"]' \
        "$DEST/workspace/config.json" 2>/dev/null; then
    echo "  !! workspace/config.json có learner_name — mycourse_files"
    echo "     của pack sẽ KHÔNG áp trên máy NV. Để trống trước khi cài."
fi

# ttyd qua brew (không brew → cảnh báo, terminal não sẽ không có)
if ! command -v ttyd >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        echo "  ttyd chua co — brew install ttyd..."
        brew install ttyd || echo "  !! brew loi — cai ttyd tay sau"
    else
        echo "  !! khong co brew — terminal cua nao se khong mo duoc."
        echo "     Cai brew (brew.sh) roi: brew install ttyd"
    fi
else
    echo "  ok — ttyd da co"
fi

# license + fleet từ folder company/ cạnh installer
mkdir -p "$DEST/.devin"
for f in license.json fleet.json; do
    if [ -f "$(dirname "$0")/company/$f" ]; then
        cp "$(dirname "$0")/company/$f" "$DEST/.devin/$f"
        echo "  ok — $f da dat vao .devin/"
    fi
done

# LaunchAgent tuỳ chọn — tự mở khi login. --quiet mặc định CÓ (MDM
# muốn autostart), --no-autostart tắt; cài tay vẫn hỏi như cũ.
ans=""
if [ "$NO_AUTOSTART" -eq 0 ]; then
    if [ "$QUIET" -eq 1 ]; then
        ans="y"
    else
        printf "Tao LaunchAgent tu chay khi dang nhap? [y/N] "
        read -r ans
    fi
fi
if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    PLIST="$HOME/Library/LaunchAgents/com.troly.start.plist"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.troly.start</string>
  <key>ProgramArguments</key>
  <array><string>/bin/sh</string><string>$DEST/start.sh</string></array>
  <key>WorkingDirectory</key><string>$DEST</string>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DEST/.devin/troly.log</string>
  <key>StandardErrorPath</key><string>$DEST/.devin/troly.log</string>
</dict></plist>
EOF
    launchctl load "$PLIST" 2>/dev/null || true
    echo "  ok — LaunchAgent $PLIST"
fi

echo ""
echo "== Xong. Con lai: =="
echo "  1. Extension: cai tu Chrome Web Store (link IT cap) HOAC unpacked"
echo "  2. Chay: sh $DEST/start.sh  -> portal mo -> lam theo onboarding"
echo "  3. Kiem tra: chrome://extensions thay 'Tro Ly AI', portal chat tra loi"
