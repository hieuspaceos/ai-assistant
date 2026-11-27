#!/usr/bin/env python3
"""test-deny-parity.py — BRAIN_CMD_DENY sống ở 5 file (audit-6 F12):

  cmd_deny.py      canonical (import được)
  term-gate.sh     case-glob (tên exact + glob python*/?sh…)
  term-gate.ps1    $deny + $denyRe (mirror tay)
  read-brain.ps1   $Deny + $DenyRe (mirror tay)
  chat-bridge.ps1  $BrainCmdDeny + $BrainCmdDenyRe (mirror tay)

Drift ở đây = kênh code-exec: một PR thêm interpreter vào cmd_deny.py
mà quên mirror = não "python3.13" lọt qua trên một nền. Test FAIL khi
tên trong canonical thiếu ở một file, tên lạ xuất hiện ở mirror, hoặc
regex mirror lệch token với _BRAIN_CMD_DENY_RE.

Chạy: python3 tools/test-deny-parity.py"""
import fnmatch
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from cmd_deny import BRAIN_CMD_DENY, _BRAIN_CMD_DENY_RE  # canonical

FAILS = []

def fail(msg):
    FAILS.append(msg)
    print("FAIL —", msg)

def read(fp):
    return open(os.path.join(ROOT, fp), encoding="utf-8-sig").read()

# ---------- exact-name sets ----------

def ps_array(fp, varname):
    # array kết thúc bằng ")" đứng đầu dòng riêng — không được non-greedy
    # tới ")" đầu tiên vì comment trong array chứa "(...)"
    m = re.search(r"\$" + varname + r"\s*=\s*@\((.*?)\n\)", read(fp), re.S)
    if not m:
        return None
    return set(re.findall(r"""['"]([^'"]+)['"]""", m.group(1)))

def sh_patterns(fp):
    """Toàn bộ alternative trong `case "$_bt" in` — gồm exact name và
    glob (python*, ?sh, *sh[0-9]*). Giữ nguyên glob để fnmatch."""
    src = read(fp)
    m = re.search(r'case "\$_bt" in(.*?)\)\s*\n\s*echo', src, re.S)
    if not m:
        return None
    body = m.group(1).replace("\\\n", "").replace("\n", "")
    pats = [p.strip().strip('"') for p in body.split("|")]
    pats[-1] = pats[-1].rstrip(")").strip()   # alternative cuối đóng )
    return [p for p in pats
            if p and p != "" and "[!" not in p]   # bỏ charset guard

SETS = {
    "term-gate.ps1":   ps_array("tools/term-gate.ps1", "deny"),
    "read-brain.ps1":  ps_array("tools/read-brain.ps1", "Deny"),
    "chat-bridge.ps1": ps_array("tools/chat-bridge.ps1", "BrainCmdDeny"),
}
for name, s in SETS.items():
    if s is None:
        fail(f"{name}: không extract được deny array")
        continue
    missing = BRAIN_CMD_DENY - s
    extra = s - BRAIN_CMD_DENY
    if missing:
        fail(f"{name} thiếu {len(missing)} tên: {sorted(missing)[:8]}")
    if extra:
        fail(f"{name} có tên lạ (không trong canonical): {sorted(extra)[:8]}")

# term-gate.sh: canonical name phải bị bắt bởi ÍT NHẤT một pattern
# (exact hoặc glob) — glob là nhánh tương đương của regex phía py.
pats = sh_patterns("tools/term-gate.sh")
if pats is None:
    fail("term-gate.sh: không extract được case patterns")
else:
    missed = [n for n in sorted(BRAIN_CMD_DENY)
              if not any(fnmatch.fnmatchcase(n, p) for p in pats)]
    if missed:
        fail(f"term-gate.sh không bắt {len(missed)} tên: {missed[:8]}")

# ---------- regex mirrors (ps1) ↔ _BRAIN_CMD_DENY_RE ----------
# re.X/?x bỏ whitespace — so sánh sau khi xoá ws + prefix (?x).
canon_re = re.sub(r"\s+", "", _BRAIN_CMD_DENY_RE.pattern)

def ps_regex(fp, varname):
    m = re.search(r"\$" + varname + r"\s*=\s*\[regex\]'(.*?)'",
                  read(fp), re.S)
    if not m:
        return None
    return re.sub(r"\s+", "", m.group(1)).replace("(?x)", "")

RES = {
    "term-gate.ps1":   ps_regex("tools/term-gate.ps1", "denyRe"),
    "read-brain.ps1":  ps_regex("tools/read-brain.ps1", "DenyRe"),
    "chat-bridge.ps1": ps_regex("tools/chat-bridge.ps1", "BrainCmdDenyRe"),
}
for name, rx in RES.items():
    if rx is None:
        fail(f"{name}: không extract được deny regex")
    elif rx != canon_re:
        fail(f"{name}: deny regex lệch canonical "
             f"(canonical {len(canon_re)} chars vs {len(rx)})")

# ---------- glob coverage: họ versioned phải bị bắt ở mọi nền ----------
# mẫu interpreter có hậu tố version/clone — exact-set không đủ, phải
# qua regex (py/ps1) hoặc glob (sh).
SAMPLES = ["python3.12", "python3.13", "perl5.40", "php8.2", "pip3.11",
           "ruby3.3", "node18", "nodejs20", "lua5.4", "luajit2",
           "tclsh8.6", "rscript4.3", "r4.3", "java17", "javac",
           "julia1.9", "groovy4", "kotlin1.9", "ipython", "pypy",
           "jython", "micropython", "pyspark", "pwsh7", "zsh5",
           "ksh93", "dash0", "bash5", "runghc", "ghci"]

py_re = _BRAIN_CMD_DENY_RE
for s in SAMPLES:
    hit_py = (s in BRAIN_CMD_DENY) or bool(py_re.match(s))
    hit_sh = pats and any(fnmatch.fnmatchcase(s, p) for p in pats)
    misses = []
    if not hit_py:
        misses.append("cmd_deny.py")
    if not hit_sh:
        misses.append("term-gate.sh")
    for name, rx in RES.items():
        if rx is not None:
            try:
                if not re.match(rx, s, re.I):
                    misses.append(name)
            except re.error:
                misses.append(name + "(regex lỗi)")
    if misses:
        fail(f"'{s}' lọt qua: {', '.join(misses)}")

if FAILS:
    print(f"\n{len(FAILS)} lỗi parity deny-list")
    sys.exit(1)
n = len(BRAIN_CMD_DENY)
print(f"PASS — {n} tên deny khớp 4 file mirror + regex mirror đồng nhất"
      f" + {len(SAMPLES)} mẫu versioned bị bắt ở mọi nền")
