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
MANIFEST = os.path.join(ROOT, "my-course", "manifest.json")

# skill vi -> skill en: ánh xạ TƯỜNG MINH (tên lệnh theo ngôn ngữ).
# Thêm một dòng khi có skill mới — thiếu dòng = test fail, đúng chủ đích.
VI_TO_EN = {
    "anh-web": "web-images",
    "cap-nhat-sheet": "update-sheet",
    "clone-trang": "clone-page",
    "dang-bai": "publish-post",
    "doc-outlook": "read-outlook",
    "doc-zalo": "read-zalo",
    "gom-file": "gather-files",
    "gom-skill": "pack-skill",
    "hoc-bai": "tutor",
    "lam-excel": "work-excel",
    "lam-word": "work-word",
    "loc-khach": "split-customers",
    "mo-web": "open-web",
    "nen-anh": "compress-images",
    "phong-van": "interview",
    "seo-meta": "seo-meta",
    "tom-tat-file": "summarize-file",
    "trang-moi": "new-page",
    "xuat-canva": "export-canva",
    "zalo-oa": "zalo-oa",
}

def skill_dirs(base):
    return {d for d in os.listdir(base)
            if os.path.isdir(os.path.join(base, d))} if os.path.isdir(base) else set()

fails = []

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

if fails:
    print(f"FAIL — {len(fails)} lỗi:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"PASS — {len(vi)} skill vi, {len(en)} skill en, "
      f"{len(active)} active đồng bộ")
