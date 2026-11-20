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

py = endpoints(os.path.join(ROOT, "tools", "chat-bridge.py"))
ps = endpoints(os.path.join(ROOT, "tools", "chat-bridge.ps1"))
only_py, only_ps = sorted(py - ps), sorted(ps - py)
if only_py or only_ps:
    print("FAIL — endpoint drift giữa hai bridge:")
    for e in only_py:
        print("  chỉ chat-bridge.py :", e)
    for e in only_ps:
        print("  chỉ chat-bridge.ps1:", e)
    sys.exit(1)
print(f"PASS — {len(py)} endpoint /api/* khớp nhau giữa .py và .ps1")
