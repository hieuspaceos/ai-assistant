#!/usr/bin/env python3
"""backup.py — snapshot dữ liệu máy trước khi update/pack-apply đè lên.

Học `internal/backup` của GoClaw: kiểm đĩa trống TRƯỚC khi copy —
thiếu chỗ thì abort rõ ràng chứ không nén nửa chừng rồi để lại đống rác.

Sao chép: `workspace/` toàn bộ + các file state trong `.devin/` mà
update/pack có thể chạm (skills/, rules.local.md, bots-related…).
KHÔNG sao chép code (tools/web/extension) — code rollback đi đường
`.devin/backup-code-*` của launcher, là mốc khác.

Đích: `.devin/backup-<timestamp>/` + file manifest.json ghi nguồn gốc.
Giữ tối đa KEEP bản gần nhất — xoá bản cũ hơn (máy NV đĩa nhỏ).

  python3 tools/backup.py [DATA_DIR] [--why update|pack]
"""
import json, os, shutil, sys, time

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.environ.get("TROLY_DATA") or os.getcwd())
WHY = "manual"
if "--why" in sys.argv:
    WHY = sys.argv[sys.argv.index("--why") + 1]
DEVIN = os.path.join(ROOT, ".devin")
KEEP = 5                          # giữ 5 snapshot gần nhất

# state máy cần bảo toàn qua update/pack — code không nằm trong list
# này; mỗi entry là file HOẶC dir con của .devin/
STATE = [
    "skills", "rules.local.md", "exec-allowlist.json", "fleet.json",
    "fleet-inbox.json", "machine.id", "machine.key", "license.json",
    "pack-version", "beacon.cursor", "secrets.local.json",
    "mcp_config.json", "mcp_config.local.json", "bridge.token",
]
SEED = ["workspace"]              # dir ở ROOT


def dir_size(fp):
    total = 0
    for r, _, fs in os.walk(fp):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return total


def main():
    dest = os.path.join(
        DEVIN, "backup-" + time.strftime("%Y%m%d-%H%M%S"))
    # preflight: đo trước dung lượng rồi so với đĩa trống — copy vào
    # .devin/ tức cùng ổ với ROOT
    need = 0
    for name in SEED:
        fp = os.path.join(ROOT, name)
        if os.path.isdir(fp):
            need += dir_size(fp)
    for name in STATE:
        fp = os.path.join(DEVIN, name)
        if os.path.isdir(fp):
            need += dir_size(fp)
        elif os.path.isfile(fp):
            need += os.path.getsize(fp)
    free = shutil.disk_usage(ROOT).free
    if need > free * 0.9:
        sys.exit(f"backup: cần ~{need // 1_048_576}MB nhưng đĩa chỉ "
                 f"còn {free // 1_048_576}MB — abort, chưa đụng gì")
    os.makedirs(dest, exist_ok=True)
    copied = []
    for name in SEED:
        src = os.path.join(ROOT, name)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(dest, name)
        # clone-work = DOM site bên thứ 3, phình và tái tạo được — bỏ
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            "clone-work", ".shots", "__pycache__"))
        copied.append(name)
    dev_dst = os.path.join(dest, ".devin")
    os.makedirs(dev_dst, exist_ok=True)
    for name in STATE:
        src = os.path.join(DEVIN, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dev_dst, name))
            copied.append(".devin/" + name)
        elif os.path.isfile(src):
            shutil.copy2(src, os.path.join(dev_dst, name))
            copied.append(".devin/" + name)
    with open(os.path.join(dest, "manifest.json"), "w") as f:
        json.dump({"ts": int(time.time()), "why": WHY,
                   "items": copied}, f, indent=2)
    # dọn bản cũ — giữ KEEP bản mới nhất
    backs = sorted(d for d in os.listdir(DEVIN)
                   if d.startswith("backup-")
                   and os.path.isdir(os.path.join(DEVIN, d)))
    for old in backs[:-KEEP]:
        shutil.rmtree(os.path.join(DEVIN, old), ignore_errors=True)
    print(f"backup: {len(copied)} mục → {dest}")


if __name__ == "__main__":
    main()
