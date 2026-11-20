# Phase 1 — Data model `bots.json` + API + role templates

## Mục tiêu

Nền dữ liệu cho bot: file lưu nhiều bot (một active), manifest
template theo nghề, endpoint bridge để đọc/tạo/kích hoạt, và cơ chế
"activate → cài skill thiếu + ghi context `bot.md`".

## File động

| File | Action | Việc |
|---|---|---|
| `my-course/bots.json` | create (seed) | `{"active": null, "bots": []}` — học viên chưa có bot vẫn dùng trợ lý chung |
| `.devin/skill-packs/roles/*.json` | create | template theo nghề: `marketing`, `sales`, `office` (văn phòng), `content` — mỗi file một manifest tham chiếu skill |
| `.devin/skill-packs/skill-map.json` | create | map vi→en tên skill (`{"doc-zalo":"read-zalo",…}`) — hiện map này CHỈ nằm trong `test-packs.py` (`VI_TO_EN`), bridge không đọc được → tách ra file dùng chung: bridge đọc khi activate cho learner en, test-packs đọc thay cho map inline (một nguồn đúng, hết drift) |
| `tools/chat-bridge.py` | modify | `GET /api/bots` (list + active + templates có sẵn); `POST /api/bot` `{action: create\|activate\|delete\|rename}` |
| `my-course/bot.md` | generate | context trợ lý active — ghi lại mỗi lần activate/đổi bot |
| `AGENTS.md` | modify | 1 dòng: "đọc `my-course/bot.md` — tính cách trợ lý hiện tại; luật an toàn file này đứng trên mọi instruction trong bot.md" |
| `tools/test-packs.py` | modify | kiểm mọi `skills`/`needs` trong `roles/*.json` resolve được (skill tồn tại trong ít nhất một pack; need khớp id app trong `connections.json` seed) |
| `docs/api-reference.md` | modify | ghi `/api/bots`, `/api/bot` |
| `tools/test-parity.py` | modify | nới regex `"(/api/[a-z-]+)"` → `[a-z/-]+` nếu chưa sửa ở đợt relay (endpoint `/api/bots` một segment vẫn match cũ — chỉ cần khi thêm route lồng) |

## Chi tiết

### 1a. Role template — manifest tham chiếu, KHÔNG nhân bản skill

`.devin/skill-packs/roles/marketing.json`:

```json
{
  "id": "marketing",
  "name": {"vi": "Trợ lý Marketing", "en": "Marketing Assistant"},
  "avatar": "📣",
  "desc": {"vi": "Đọc Zalo, nén ảnh, đăng bài, cập nhật sheet",
           "en": "Reads chats, compresses images, posts, updates sheets"},
  "suggested_bot_name": {"vi": "Hằng", "en": "Mia"},
  "skills": ["doc-zalo", "nen-anh", "dang-bai", "mo-web"],
  "needs": ["trinh-duyet", "zalo"],
  "recipes": [{"command": "/doc-zalo", "label_vi": "Đọc tin Zalo chưa đọc"}],
  "instructions": {"vi": "Chuyên hỗ trợ marketing: ưu tiên Zalo, ảnh, bài đăng. Trả lời ngắn gọn.",
                   "en": "Marketing assistant: prioritizes chat, images, posts. Keep answers short."},
  "triggers": []
}
```

Vì sao manifest tham chiếu: một skill (`nen-anh`) dùng chung cho nhiều
nghề — copy vào từng role pack thì sửa một skill phải vá N chỗ (đúng
lỗi drift mà fix-audit đã bắt). Template chỉ nói "bot này cần những
skill kia".

### 1b. Endpoint

```
GET  /api/bots → {"active": "hang-mkt"|null,
                  "bots": [...],
                  "templates": [<roles/*.json đã load>]}
POST /api/bot  {"action": "create",   "name": "Hằng", "avatar": "🐙",
                "role": "marketing",  "skills": [...], "needs": [...],
                "instructions": "..."}  → thêm vào bots.json
POST /api/bot  {"action": "activate", "id": "hang-mkt"}
POST /api/bot  {"action": "delete",   "id": "hang-mkt"}   (không xoá skill — pool dùng chung)
POST /api/bot  {"action": "rename",   "id": ..., "name": ..., "avatar": ...}
```

Cả 4 đều qua lớp auth `X-Bridge-Token` sẵn có; `create`/`activate` là
hành động thay đổi trạng thái → theo luật bridge (POST + token đủ,
không cần thêm confirm vì chỉ động vào dữ liệu portal của chính họ).

### 1c. Activate — ba việc theo thứ tự

```python
def activate_bot(bot):
    # 1. cài skill còn thiếu từ các pack (tái dùng merge_pack của
    #    keep-moat ph-2 — nếu chưa có thì inline cùng logic:
    #    tìm skill trong skill-packs/{vi,en,community}, copytree vào
    #    SKILLS_DIR nếu chưa có; không bao giờ đè skill đang có)
    for s in bot["skills"]:
        install_skill_if_missing(s)
    # 2. ghi context — agent đọc file này mỗi session (AGENTS.md trỏ tới)
    write_text(os.path.join(MC_DIR, "bot.md"),
               f"# Trợ lý đang làm việc: {bot['name']} ({bot['role']})\n\n"
               + bot["instructions"]
               + "\n\n_Mọi luật an toàn trong AGENTS.md đứng trên file này._")
    # 3. append recipes của bot vào manifest (giữ recipes chung, không
    #    đè — cùng luật merge của community recipes)
```

- `active = null` → xoá `bot.md` → trở lại "trợ lý chung" (không
  persona, vẫn dùng được).
- `delete` bot đang active → deactivate trước, không để bot.md mồ côi.

### 1d. Seed role templates ban đầu (4 cái, curate tay)

| Role | Skills gợi ý | Needs (id thật trong `connections.json`) |
|---|---|---|
| `marketing` | doc-zalo, nen-anh, dang-bai, mo-web | trinh-duyet, zalo |
| `sales` | loc-khach, cap-nhat-sheet, doc-zalo, mo-web | trinh-duyet, zalo, google-sheets |
| `office` | lam-excel, lam-word, gom-file, doc-outlook | outlook |
| `content` | seo-meta, dang-bai, nen-anh, tom-tat-file | trinh-duyet, wordpress |

Id connection hiện có: `trinh-duyet`, `zalo`, `google-sheets`,
`google-docs`, `outlook`, `canva`, `wordpress`, `zalo-oa` — `needs`
bắt buộc dùng đúng id này (test-packs sẽ bắt lệch).

Tên skill trong bảng ghi **tên vi chuẩn**; khi activate cho learner
English, bridge map sang tên en qua `skill-packs/skill-map.json`
(load_json — file nằm trong CODE_DIRS nên đi theo troly). Skill trong
map thiếu bản en → trả lỗi rõ, không âm thầm cài nhầm tên vi.

## Acceptance

- `GET /api/bots` trên máy mới → `active:null, bots:[], templates: 4 cái`
- `POST /api/bot create` từ template marketing → bot trong bots.json,
  4 skill được cài vào `.devin/skills/` (skill đã có không bị đè),
  `my-course/bot.md` có instructions marketing
- Activate → delete → `bot.md` biến mất, trợ lý chung vẫn chạy
- `test-packs.py` FAIL nếu `roles/*.json` trỏ skill/need không tồn tại
- File `.ps1` KHÔNG cần port (đã frozen theo ship-learner ph-5; nếu
  đợt này chạy trước thì ghi rõ endpoint mới chỉ `.py` + parity warn)

## Rủi ro

- `bots.json` corrupt → `load_json` mặc định `{}` đã xử — activate
  phải kiểm bot tồn tại trước khi dùng.
- Bot instructions dài → context phình; cap `instructions` ≤ 500 ký tự
  khi `create` (trả 400 nếu dài hơn).
