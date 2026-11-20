#!/usr/bin/env python3
"""test-parity.py — chat-bridge.py và chat-bridge.ps1 phải cùng tập
endpoint /api/*. Drift đã từng làm mất /api/save-page trên Windows.

Chạy: python3 tools/test-parity.py"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def endpoints(fp):
    # chỉ khớp literal "/api/..." có nháy kép ngay trước — chuỗi URL dài
    # ("http://127.0.0.1:7684/api/browser") không match, không nhiễu
    return set(re.findall(r'"(/api/[a-z-]+)"',
                          open(fp, encoding="utf-8-sig").read()))

# .ps1 đã đóng băng (ship-learner ph-5) — endpoint mới chỉ thêm vào .py.
# Khai TƯỜNG MINH ở đây: warn, không fail. Endpoint trong list này mà lại
# có trong .ps1 thì tự động ra khỏi warn.
PY_ONLY_OK = {"/api/bot", "/api/bots"}

py = endpoints(os.path.join(ROOT, "tools", "chat-bridge.py"))
ps = endpoints(os.path.join(ROOT, "tools", "chat-bridge.ps1"))
only_py, only_ps = sorted(py - ps), sorted(ps - py)
known = sorted(set(only_py) & PY_ONLY_OK)
only_py = [e for e in only_py if e not in PY_ONLY_OK]
if only_py or only_ps:
    print("FAIL — endpoint drift giữa hai bridge:")
    for e in only_py:
        print("  chỉ chat-bridge.py :", e)
    for e in only_ps:
        print("  chỉ chat-bridge.ps1:", e)
    sys.exit(1)
for e in known:
    print(f"  warn — {e} chỉ có .py (.ps1 đã frozen, khai trong PY_ONLY_OK)")
print(f"PASS — {len(py & ps)} endpoint /api/* khớp nhau giữa .py và .ps1"
      + (f" (+{len(known)} chỉ-.py đã khai)" if known else ""))
