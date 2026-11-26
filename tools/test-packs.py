#!/usr/bin/env python3
"""test-packs.py — parity giữa .devin/skills/ (active) và
.devin/skill-packs/ (kho mẫu phát cho học viên qua launcher/onboarding).

Bắt các drift:
  - skill active có nhưng thiếu trong pack vi  → bản đóng gói mất skill
  - skill trong pack vi thiếu bản en          → học viên en mất skill
  - skill có ở cả hai nhưng nội dung lệch     → pack là bản cũ
  - SKILL.md thiếu frontmatter name/description
  - recipes manifest trỏ tới skill không có trong pack vi

Chạy: python3 tools/test-packs.py"""
import filecmp, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, ".devin", "skills")
PACKS = os.path.join(ROOT, ".devin", "skill-packs")
PACK_VI = os.path.join(PACKS, "vi")
PACK_EN = os.path.join(PACKS, "en")
MANIFEST = os.path.join(ROOT, "workspace", "manifest.json")

# skill vi -> skill en: ánh xạ TƯỜNG MINH (tên lệnh theo ngôn ngữ).
# Nguồn chung: skill-packs/skill-map.json — chat-bridge cũng đọc file này
# khi activate bot cho học viên en. Thêm skill mới → thêm một dòng vào
# file đó — thiếu dòng = test fail, đúng chủ đích.
try:
    VI_TO_EN = json.load(open(os.path.join(PACKS, "skill-map.json"),
                              encoding="utf-8"))
except Exception as e:
    VI_TO_EN = {}
    _map_err = e

def skill_dirs(base):
    return {d for d in os.listdir(base)
            if os.path.isdir(os.path.join(base, d))} if os.path.isdir(base) else set()

fails = []
if not VI_TO_EN:
    fails.append(f"skill-map.json không đọc được: {_map_err}")

def check(ok, msg):
    if not ok:
        fails.append(msg)

# 1. Frontmatter name + description không rỗng trong mọi SKILL.md
def check_frontmatter(base, tag):
    for d in sorted(skill_dirs(base)):
        fp = os.path.join(base, d, "SKILL.md")
        if not os.path.isfile(fp):
            fails.append(f"{tag}: {d} thiếu SKILL.md")
            continue
        head = open(fp, encoding="utf-8").read(3000)
        m = re.search(r"^name:\s*(\S+)", head, re.M)
        check(m and m.group(1) == d,
              f"{tag}/{d}: name frontmatter != tên folder")
        check(re.search(r"^description:\s*\S", head, re.M) is not None,
              f"{tag}/{d}: thiếu description")

check_frontmatter(SKILLS, "skills")
check_frontmatter(PACK_VI, "pack-vi")
check_frontmatter(PACK_EN, "pack-en")

# 2. Skill active (hoặc được recipes nhắc) → phải có trong pack vi
active = skill_dirs(SKILLS)
vi = skill_dirs(PACK_VI)
en = skill_dirs(PACK_EN)
for s in sorted(active - vi):
    fails.append(f"skill active '{s}' thiếu trong skill-packs/vi "
                 f"→ bản đóng gói sẽ không có")

try:
    recipes = json.load(open(MANIFEST, encoding="utf-8")).get("recipes", [])
except Exception:
    recipes = []
for r in recipes:
    name = str(r.get("command", "")).lstrip("/")
    if name and name not in vi:
        fails.append(f"recipes manifest trỏ /{name} nhưng pack vi không có")

# 3. Nội dung active ↔ pack vi phải giống nhau (chống "sửa active quên pack")
for s in sorted(active & vi):
    a, b = os.path.join(SKILLS, s), os.path.join(PACK_VI, s)
    cmp = filecmp.dircmp(a, b)
    diff = list(cmp.diff_files) + list(cmp.left_only) + list(cmp.right_only)
    check(not diff, f"skill '{s}': nội dung lệch giữa skills/ và pack vi "
                    f"({', '.join(diff[:3])})")

# 4. Mọi skill pack vi phải có bản en (theo map); skill en mồ côi = thiếu map
for s in sorted(vi):
    en_name = VI_TO_EN.get(s)
    check(en_name is not None, f"skill vi '{s}' chưa khai trong VI_TO_EN")
    if en_name:
        check(en_name in en, f"bản en của '{s}' (= '{en_name}') thiếu trong pack en")
mapped = set(VI_TO_EN.values())
for s in sorted(en - mapped):
    fails.append(f"skill en '{s}' không có bản vi trong VI_TO_EN")

# 5. recipes.json phải có cho cả 2 ngôn ngữ, command tồn tại trong pack
for lang, pack in (("vi", vi), ("en", en)):
    fp = os.path.join(PACKS, "recipes", lang + ".json")
    try:
        rs = json.load(open(fp, encoding="utf-8"))["recipes"]
        for r in rs:
            n = str(r.get("command", "")).lstrip("/")
            check(n in pack, f"recipes/{lang}.json trỏ /{n} — không có trong pack")
    except Exception as e:
        fails.append(f"recipes/{lang}.json không đọc được: {e}")

# 6. roles/*.json — mọi skill tham chiếu phải tồn tại (trong pack vi, hoặc
#    map được sang en); mọi need phải khớp id app trong connections.json
ROLES = os.path.join(PACKS, "roles")
try:
    conn = json.load(open(os.path.join(ROOT, "workspace", "connections.json"),
                          encoding="utf-8"))
    conn_ids = {a.get("id") for a in conn.get("apps", [])}
except Exception as e:
    conn_ids = set()
    fails.append(f"connections.json không đọc được: {e}")
if os.path.isdir(ROLES):
    for f in sorted(os.listdir(ROLES)):
        if not f.endswith(".json"):
            continue
        try:
            t = json.load(open(os.path.join(ROLES, f), encoding="utf-8"))
        except Exception as e:
            fails.append(f"roles/{f} không đọc được: {e}")
            continue
        for s in t.get("skills") or []:
            ok = s in vi or s in en or VI_TO_EN.get(s) in en
            check(ok, f"roles/{f}: skill '{s}' không có trong pack nào")
        for n in t.get("needs") or []:
            check(n in conn_ids,
                  f"roles/{f}: need '{n}' không khớp id nào trong connections.json")

# 7. workspace/workflows/ — schema workflow: id khớp tên file, prompt
#    không rỗng, checklist ≥1 mục, requires.connections trỏ id app thật,
#    inputs key dùng trong prompt ({{key}} phải khai báo input)
WF_DIR = os.path.join(ROOT, "workspace", "workflows")
if os.path.isdir(WF_DIR):
    try:
        idx = json.load(open(os.path.join(WF_DIR, "index.json"),
                             encoding="utf-8"))
        ids = idx.get("workflows") or []
    except Exception as e:
        ids = []
        fails.append(f"workflows/index.json không đọc được: {e}")
    for wid in ids:
        fp = os.path.join(WF_DIR, wid + ".json")
        if not os.path.exists(fp):
            fails.append(f"workflows/index.json trỏ '{wid}' — file thiếu")
            continue
        try:
            w = json.load(open(fp, encoding="utf-8"))
        except Exception as e:
            fails.append(f"workflows/{wid}.json không đọc được: {e}")
            continue
        check(w.get("id") == wid,
              f"workflows/{wid}.json: id '{w.get('id')}' ≠ tên file")
        check(bool(str(w.get("prompt") or "").strip()),
              f"workflows/{wid}.json: prompt rỗng")
        check(len(w.get("checklist") or []) >= 1,
              f"workflows/{wid}.json: checklist < 1 mục")
        for cid in (w.get("requires") or {}).get("connections") or []:
            check(cid in conn_ids,
                  f"workflows/{wid}.json: requires.connections '{cid}' "
                  f"không khớp id trong connections.json")
        # mọi {{key}} trong prompt phải có input tương ứng
        declared = {i.get("key") for i in w.get("inputs") or []}
        for k in re.findall(r"\{\{(\w+)\}\}", str(w.get("prompt"))):
            check(k in declared,
                  f"workflows/{wid}.json: prompt dùng {{{{{k}}}}} "
                  f"nhưng không khai trong inputs")
        # title phải có ít nhất bản vi
        ti = w.get("title")
        check(isinstance(ti, dict) and bool(ti.get("vi")),
              f"workflows/{wid}.json: title thiếu bản vi")
        # verify: dir + glob hợp lệ nếu khai
        v = w.get("verify")
        if v:
            check(bool(v.get("dir")),
                  f"workflows/{wid}.json: verify thiếu dir")
            check(".." not in str(v.get("glob") or ""),
                  f"workflows/{wid}.json: verify.glob chứa ..")

if fails:
    print(f"FAIL — {len(fails)} lỗi:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"PASS — {len(vi)} skill vi, {len(en)} skill en, "
      f"{len(active)} active đồng bộ")
