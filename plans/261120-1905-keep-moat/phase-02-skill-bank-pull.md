# Phase 2 — Skill bank hai chiều: pack `community/` chảy về máy học viên

## Mục tiêu

Đóng vòng skill bank: `/gom-skill` gom skill học viên tự tạo về kho
chung → kho được curate → **phát lại** cho mọi học viên qua bản `troly`
mới. Học viên B được hưởng công thức học viên A nảy ra.

## File động

| File | Action | Việc |
|---|---|---|
| `.devin/skill-packs/community/` | create | pack thứ ba — skill cộng đồng đã curate, không theo ngôn ngữ |
| `tools/launcher.py` | modify | `CODE_DIRS` đã gồm `.devin/skill-packs` → `community/` tự đi theo; verify `_copy_tree` không bỏ sót |
| `tools/chat-bridge.py` | modify | `/api/setup` sau khi copy pack ngôn ngữ → merge thêm `community/` theo cùng luật "không đè skill tự tạo" |
| `.devin/skill-packs/recipes/community.json` | create | recipes cho skill cộng đồng (append vào manifest, không đè pack ngôn ngữ) |
| `tools/test-packs.py` | modify | tính cả pack `community/` trong kiểm đồng bộ |
| `docs/skills-system.md` | modify | cập nhật sơ đồ vòng đời: 3 pack + luật merge community |
| `docs/api-reference.md` | modify | ghi endpoint `POST /api/skills-sync` |
| `.devin/skills/gom-skill/SKILL.md` | modify | hướng dẫn gói skill gửi kho chung → quy trình curate (PR vào `skill-packs/community/`) |

## Chi tiết

### Pack `community/`

- Skill ở đây = skill do học viên/agent tự sinh trong thực tế, đã qua
  review của chủ kho. Ngôn ngữ theo skill gốc (phần lớn vi).
- `name` trong frontmatter phải trùng tên folder; tránh trùng tên với
  pack vi/en — trùng thì đổi tên khi curate (skill chung sống cùng
  `.devin/skills/` nên tên là namespace duy nhất).

### Merge trong `/api/setup` (`chat-bridge.py`)

Sau block copy pack ngôn ngữ hiện có, thêm:

```python
# pack cộng đồng — merge thêm, không đè skill đã có (kể cả tự tạo)
com = os.path.join(SKILL_PACKS, "community")
if os.path.isdir(com):
    for name in os.listdir(com):
        src = os.path.join(com, name)
        dst = os.path.join(SKILLS_DIR, name)
        if os.path.isdir(src) and not os.path.exists(dst):
            shutil.copytree(src, dst)
    # recipes cộng đồng append vào manifest (không đè recipes pack ngôn ngữ)
    rec = load_json(os.path.join(SKILL_PACKS, "recipes", "community.json"), {})
    if rec.get("recipes"):
        try:
            m = json.load(open(mf, encoding="utf-8"))
            have = {r.get("command") for r in m.get("recipes", [])}
            m.setdefault("recipes", [])
            m["recipes"] += [r for r in rec["recipes"]
                             if r.get("command") not in have]
            json.dump(m, open(mf, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        except Exception:
            pass
```

### Khi nào community pack mới tới máy học viên

- Update `troly` (VERSION đổi) → `skill-packs/` bị đè → nhưng
  `.devin/skills/` (active) KHÔNG bị đè — đúng thiết kế hiện tại.
- Vậy skill cộng đồng mới chỉ tới máy cũ qua một cơ chế "nạp bổ sung":
  tái dùng chính hàm merge trên — tách nó thành helper
  `merge_pack(pack_dir)` rồi gọi từ `/api/setup` VÀ từ một endpoint nhỏ
  `POST /api/skills-sync` (hoặc gọi lại setup khi có bản mới — portal
  banner "Có bản mới" có thể gợi ý chạy). Chọn `POST /api/skills-sync`
  cho rõ: agent cũng gọi được sau khi update.

### Quy trình curate (ghi trong gom-skill + docs)

1. Học viên chạy `/gom-skill` → file nén gửi chủ kho.
2. Chủ kho review (không secret, không lệnh phá hoại, đúng format) →
   vào `skill-packs/community/<ten>/`.
3. Release mới → mọi máy nhận được khi update + `skills-sync`.

## Acceptance

- Máy mới onboard → `.devin/skills/` có cả skill pack ngôn ngữ lẫn
  `community/`; manifest có recipes cả hai nguồn, không trùng
- Skill học viên tự tạo trước đó không bị đè khi sync
- `POST /api/skills-sync` trên máy cũ kéo skill cộng đồng mới về sau
  update `troly`
- `test-packs.py` pass với 3 pack

## Rủi ro

- Skill cộng đồng kém chất lượng/xấu → curate thủ công, không nhận PR
  tự động; mỗi skill vào kho kèm người review trong git log.
- Namespace đụng nhau giữa 3 pack → luật "không đè" + đổi tên khi
  curate; `test-packs.py` kiểm trùng tên folder giữa các pack.
