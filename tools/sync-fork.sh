#!/bin/bash
# sync-fork.sh — INTERIM: hút khác biệt của fork ima-assistant sang
# packs/ima/pack.json trong repo này. "NO FORK, only pack": fork chết
# dần, mọi khác biệt của cty sống trong pack — một code base duy nhất.
#
#   bash tools/sync-fork.sh [đường-tới-ima-assistant]
#
# Quy tắc tách:
#   - skill có trong fork mà KHÔNG có trong .devin/skill-packs/vi/
#     → skill riêng của org → vào pack (kèm mọi file trong skill dir)
#   - my-course/{connections,bots,permissions}.json của fork → pack
#   - AGENTS.md của fork → rules_local_md (luật cty đọc kèm AGENTS lõi)
#   - phần code (tools/web/extension) khác biệt → CHỈ BÁO, không đưa
#     vào pack — code khác biệt phải merge về repo hoặc bỏ, không pack
set -euo pipefail
cd "$(dirname "$0")/.."
FORK="${1:-../ima-assistant}"
[ -d "$FORK" ] || { echo "không thấy fork ở $FORK"; exit 1; }

python3 - "$FORK" <<'PY'
import json, os, sys

fork, root = sys.argv[1], os.getcwd()
base_skills = set()
for lang in ("vi", "en"):
    d = os.path.join(root, ".devin", "skill-packs", lang)
    if os.path.isdir(d):
        base_skills |= set(os.listdir(d))

# merge trên pack HIỆN CÓ — phần tay dựng (workflows, bots persona,
# devin_files, mycourse_files, rules_local_md đã chắt) không bị xoá
# khi re-sync. Fork chỉ cập nhật các khoá nó thật sự cung cấp.
out = os.path.join(root, "packs", "IMA", "pack.json")
try:
    pack = json.load(open(out, encoding="utf-8"))
except Exception:
    pack = {}
pack.setdefault("org", "IMA")
pack.setdefault("skills", {})
pack.setdefault("bots", [])
pack.setdefault("connections", [])
pack.setdefault("workflows", {})
pack.setdefault("permissions_template", [])
pack.setdefault("exec_allowlist", [])

# skills riêng của fork → vào pack (đọc mọi file trong skill dir)
sk_dir = os.path.join(fork, ".devin", "skills")
only = []
if os.path.isdir(sk_dir):
    for sid in sorted(os.listdir(sk_dir)):
        sd = os.path.join(sk_dir, sid)
        if not os.path.isdir(sd) or sid in base_skills:
            continue
        files = {}
        for r, _, fs in os.walk(sd):
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), sd)
                files[rel] = open(os.path.join(r, f),
                                  encoding="utf-8").read()
        pack["skills"][sid] = files
        only.append(sid)

# state org trong my-course → pack
myc = os.path.join(fork, "my-course")
for name, key in (("bots.json", "bots"),
                  ("connections.json", "connections"),
                  ("permissions.json", "permissions_template")):
    fp = os.path.join(myc, name)
    if os.path.isfile(fp):
        data = json.load(open(fp, encoding="utf-8"))
        pack[key] = data.get("bots") if key == "bots" else \
            data.get("apps") if key == "connections" else \
            data.get("folders") if key == "permissions_template" \
            else data
        pack[key] = pack[key] or []

# AGENTS.md của fork = luật cty — chỉ hút LẦN ĐẦU; pack đã có
# rules_local_md đã chắt (persona tách sang bot) thì giữ bản đó
ag = os.path.join(fork, "AGENTS.md")
if os.path.isfile(ag) and not pack.get("rules_local_md"):
    pack["rules_local_md"] = open(ag, encoding="utf-8").read()

# .devin/mcp_config.json của fork → devin_files nếu pack chưa có
mc = os.path.join(fork, ".devin", "mcp_config.json")
if os.path.isfile(mc):
    pack.setdefault("devin_files", {})
    if "mcp_config.json" not in pack["devin_files"]:
        pack["devin_files"]["mcp_config.json"] = \
            open(mc, encoding="utf-8").read()

pack["pack_version"] = int(pack.get("pack_version") or 0) + 1
with open(out, "w", encoding="utf-8") as f:
    json.dump(pack, f, ensure_ascii=False, indent=2)
print(f"pack → {out} (v{pack['pack_version']})")
print(f"  skills IMA riêng: {len(only)} — {', '.join(only[:8])}"
      + ("…" if len(only) > 8 else ""))
PY

# báo code khác biệt — người merge tay về repo, pack không mang code
echo "--- code khác biệt giữa fork và repo (merge tay nếu cần):"
for d in tools web extension templates; do
    diff -rq "$FORK/$d" "$d" 2>/dev/null | grep -v __pycache__ || true
done | head -30
