#!/usr/bin/env python3
"""test-parity.py — chat-bridge.py và chat-bridge.ps1 phải cùng tập
endpoint /api/*. Drift đã từng làm mất /api/save-page trên Windows.

Chạy: python3 tests/test-parity.py"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def endpoints(fp):
    # chỉ khớp literal "/api/..." có nháy kép ngay trước — chuỗi URL dài
    # ("http://127.0.0.1:7684/api/browser") không match, không nhiễu
    return set(re.findall(r'"(/api/[a-z-]+)"',
                          open(fp, encoding="utf-8-sig").read()))

# Endpoint chỉ có trong .py mà CHỦ ĐÍCH không port — khai TƯỜNG MINH ở
# đây: warn, không fail. Endpoint trong list này mà lại có trong .ps1
# thì tự động ra khỏi warn. (audit-6 F5: 5 endpoint bots/bot-import/
# install-brain đã port sang ps1; /api/config ps1 đã có từ trước.)
PY_ONLY_OK = set()
# ux-polish ph-06: pick-folder/reveal đã port cả .ps1 (WinForms dialog +
# explorer /select,) — không còn darwin-only. Giữ set rỗng để khai sau.
DARWIN_ONLY = set()

py = endpoints(os.path.join(ROOT, "tools", "chat-bridge.py"))
ps = endpoints(os.path.join(ROOT, "tools", "chat-bridge.ps1"))
only_py, only_ps = sorted(py - ps), sorted(ps - py)
known = sorted(set(only_py) & (PY_ONLY_OK | DARWIN_ONLY))
only_py = [e for e in only_py if e not in (PY_ONLY_OK | DARWIN_ONLY)]
if only_py or only_ps:
    print("FAIL — endpoint drift giữa hai bridge:")
    for e in only_py:
        print("  chỉ chat-bridge.py :", e)
    for e in only_ps:
        print("  chỉ chat-bridge.ps1:", e)
    sys.exit(1)
for e in known:
    tag = "darwin-only" if e in DARWIN_ONLY else "khai PY_ONLY_OK"
    print(f"  warn — {e} chỉ có .py ({tag})")
print(f"PASS — {len(py & ps)} endpoint /api/* khớp nhau giữa .py và .ps1"
      + (f" (+{len(known)} chỉ-.py đã khai)" if known else ""))

# CSP suffixes parity serve.py ↔ serve.ps1 (audit-6 F1) — một bên thêm
# suffix render-document mà bên kia quên = XSS chạy trong origin portal.
def _suffix_set(pattern, fp):
    m = re.search(pattern, open(fp, encoding="utf-8-sig").read())
    if not m:
        return None
    return set(re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)))

py_csp = _suffix_set(r"CSP_SUFFIXES\s*=\s*\(([^)]*)\)",
                     os.path.join(ROOT, "tools", "serve.py"))
ps_csp = _suffix_set(r"\$cspSuffixes\s*=\s*@\(([^)]*)\)",
                     os.path.join(ROOT, "tools", "serve.ps1"))
if not py_csp or not ps_csp or py_csp != ps_csp:
    print("FAIL — CSP suffix drift serve.py vs serve.ps1:",
          sorted((py_csp or set()) ^ (ps_csp or set())))
    sys.exit(1)
print(f"PASS — {len(py_csp)} CSP suffixes khớp serve.py ↔ serve.ps1")

# Endpoint-keys parity /api/secrets (audit-6 F2) — "địa chỉ site" gồm
# url|host|endpoint; một bên so thiếu key = merge creds cũ qua host mới.
py_sec = re.search(r'for k in \("url", "host", "endpoint"\)',
                   open(os.path.join(ROOT, "tools", "chat-bridge.py"),
                        encoding="utf-8").read())
ps_sec = re.search(r"\$endpointKeys\s*=\s*@\('url','host','endpoint'\)",
                   open(os.path.join(ROOT, "tools", "chat-bridge.ps1"),
                        encoding="utf-8-sig").read())
if not (py_sec and ps_sec):
    print("FAIL — secrets endpoint-keys drift: py dùng url|host|endpoint,"
          " ps1 phải có $endpointKeys cùng 3 key")
    sys.exit(1)
print("PASS — secrets endpoint-keys url|host|endpoint khớp .py ↔ .ps1")
