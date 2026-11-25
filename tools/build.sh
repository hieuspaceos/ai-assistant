#!/usr/bin/env bash
# Đóng gói Trợ Lý AI thành một file chạy duy nhất (PyInstaller onefile).
# Chạy trên HĐH muốn build — PyInstaller không cross-compile:
#   macOS   → dist/troly
#   Windows → dist\troly.exe (build trên máy Windows/CI)
set -euo pipefail
cd "$(dirname "$0")/.."

command -v pyinstaller >/dev/null || {
  echo "Chưa có pyinstaller: python3 -m pip install pyinstaller"; exit 1; }

# Payload "bung" ra ~/TroLyAI lần chạy đầu — toàn bộ phần mềm + seed
# my-course/brain.json. KHÔNG bundle secrets, token, skills active,
# plans, git. clone-work/ bị loại: DOM site thật của bên thứ 3 — phình
# binary + rủi ro IP/privacy khi phân phối.
SEP=":"; [ "$(uname -s)" = "MINGW64_NT"* ] && SEP=";"   # win dùng ;
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
cp -R my-course "$STAGE/my-course"
# clone-work: DOM site thật của bên thứ 3 (IP/privacy). .shots: screenshot
# tab của máy build — có thể chứa tin nhắn học viên. .bak: bản nháp undo.
# .trash: bài học viên vừa xoá — là dữ liệu làm việc, không seed.
# bot.md: trợ lý đang active của máy build — không seed cho học viên mới.
# (troly.spec _collect lọc y hệt — giữ 2 đường build đồng nhất.)
rm -rf "$STAGE/my-course/clone-work" "$STAGE/my-course/.shots" \
       "$STAGE/my-course/.trash"
rm -f "$STAGE/my-course/bot.md"
find "$STAGE/my-course" -name '*.bak' -delete
# hidden-import: child "vai" chạy qua runpy TRONG cùng frozen interpreter —
# PyInstaller chỉ thấy import tĩnh của launcher nên phải khai tay module
# mà tools/*.py cần, không thì child chết ModuleNotFoundError
pyinstaller --onefile --name troly --clean \
  --hidden-import http.server \
  --hidden-import urllib.parse \
  --hidden-import urllib.request \
  --hidden-import urllib.error \
  --hidden-import socket \
  --hidden-import struct \
  --hidden-import hashlib \
  --hidden-import base64 \
  --hidden-import hmac \
  --hidden-import secrets \
  --hidden-import threading \
  --hidden-import shutil \
  --hidden-import subprocess \
  --hidden-import tempfile \
  --hidden-import signal \
  --hidden-import platform \
  --hidden-import runpy \
  --hidden-import webbrowser \
  --hidden-import queue \
  --hidden-import concurrent.futures \
  --hidden-import functools \
  --hidden-import winreg \
  --add-data "web${SEP}web" \
  --add-data "tools${SEP}tools" \
  --add-data "extension${SEP}extension" \
  --add-data "templates${SEP}templates" \
  --add-data "docs${SEP}docs" \
  --add-data ".devin/skill-packs${SEP}.devin/skill-packs" \
  --add-data "$STAGE/my-course${SEP}my-course" \
  --add-data "AGENTS.md${SEP}." \
  --add-data "CLAUDE.md${SEP}." \
  --add-data "SETUP.md${SEP}." \
  --add-data "README.md${SEP}." \
  --add-data "requirements.txt${SEP}." \
  --add-data "VERSION${SEP}." \
  --add-data "brain.json${SEP}." \
  --exclude-module tkinter \
  tools/launcher.py

OUT="$(ls dist/troly* 2>/dev/null | head -1)"
echo "Xong → ${OUT:-dist/troly} — copy file này cho học viên là xong."
