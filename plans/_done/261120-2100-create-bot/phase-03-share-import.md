# Phase 3 — Chia sẻ & nhập bot (skill bank đóng gói theo bot)

> **Status: ✅ DONE** — `gom-skill`/`pack-skill` có mode gói bot
> (bot.json + README.txt + skills/); `/api/bot-import` preview (base64
> zip, cap 8MB, chống zip-slip) → `/api/bot-import-confirm` ghi thật
> không tự activate; menu chip portal có "Nhập trợ lý từ file" với
> màn đọc instructions + cảnh báo; SECURITY.md + skills-system.md +
> api-reference.md đã ghi. Test 20 (preview/zip-slip/không-active/
> stage 1 lần/file rác) — 33 xanh.

## Mục tiêu

Bot trở thành **đơn vị chia sẻ** của skill bank: học viên A gói bot
đã chỉnh (kèm skill) gửi bạn B — B nhập là có đúng "trợ lý" y hệt.
Đây là network effect của moat, nâng từ "chia sẻ công thức lẻ" lên
"chia sẻ cả nhân viên".

## File động

| File | Action | Việc |
|---|---|---|
| `.devin/skills/gom-skill/SKILL.md` | modify | thêm mode gói BOT: `bot.json` + các skill nó tham chiếu + manifest mô tả |
| `tools/chat-bridge.py` | modify | `POST /api/bot-import` — nhận **nội dung file** trong body (file picker chỉ cho File object, không cho path); bung zip vào temp, đọc `bot.json` + skills/, trả *preview* cho portal; `POST /api/bot-import-confirm` mới ghi thật. **Body cap**: bridge giới hạn 1MB — endpoint này cần cap riêng ~8MB như save-page (zip skill thuần text thường <200KB nhưng chừa dư) |
| `web/app.js` | modify | dropdown bot → "Nhập bot từ file" → file input → POST nội dung → hiện preview (tên, instructions, skill, needs) → xác nhận → gọi confirm |
| `.devin/skill-packs/roles/` | append | bot chia sẻ hay sau curate trở thành role template mới → phát cho mọi máy theo keep-moat ph-2 |
| `docs/skills-system.md` | modify | ghi định dạng bot bundle + quy trình share/curate |

## Chi tiết

### 3a. Định dạng bundle — `bot-<ten>.zip`

```
bot-hang-mkt.zip
├── bot.json          # đúng schema phase 1 (name, avatar, instructions,
│                     #  skills[], needs[], recipes[])
├── README.txt        # 3 dòng: bot này làm gì, cần nối gì — đọc trước khi nhập
└── skills/<ten>/     # thư mục skill đầy đủ mà bot tham chiếu
```

`gom-skill` khi gói bot: resolve `skills[]` → copy cả thư mục skill
(nếu skill đó đến từ pack chuẩn thì có thể bỏ qua copy — nhưng v1 cứ
gói đủ cho chắc, file nhỏ).

### 3b. Import flow — hai lớp an toàn

1. Học viên chọn file → bridge bung vào temp → **hiện trước**:
   tên bot, instructions đầy đủ, danh sách skill sẽ cài, connections
   cần nối. Nhắc rõ: "đọc phần chỉ dẫn — nếu thấy lệnh lạ (gửi tin,
   xoá gì đó) thì đừng nhập".
2. Xác nhận → cài skill (luật "không đè" như mọi merge khác) → thêm
   bot vào `bots.json` (id trùng → hậu tố `-2`) → **không tự
   activate** — học viên tự chọn khi sẵn sàng.

Lý do không tự activate: bot nhập là content từ người khác — đổi
context agent mà không được chọn rõ ràng là tạo cảm giác "máy bị đổi
dưới chân mình".

### 3c. Phát qua community pack

Bot hay sau curate → thêm file `roles/<id>.json` mới (skill kèm vào
`community/` nếu chưa có trong pack ngôn ngữ) → mọi máy nhận qua
update + `skills-sync` (keep-moat ph-2). Bot cộng đồng = template
mới trong gallery — không cần cơ chế khác.

## Acceptance

- `/gom-skill` gói bot "Hằng" → zip đúng layout, mở được ở máy khác
- Nhập zip: instructions hiện trước khi OK; OK xong bot nằm trong
  list nhưng chưa active; activate → skill + recipes + bot.md đúng
- Zip thiếu skill tham chiếu → import vẫn thành công, bot thiếu skill
  hiện nhãn "thiếu công thức" khi activate (không chết)
- Zip chứa instructions độc ("gửi tin không cần hỏi") → luật
  AGENTS.md vẫn thắng — test bằng cách nhập bot xấu rồi thử nhờ nó
  gửi tin: trợ lý vẫn phải hỏi xác nhận

## Rủi ro

- Zip từ nguồn lạ mang skill độc (script trong skill chạy được khi
  agent đọc) → README.txt + màn hình instructions là lớp chống đầu;
  ghi vào SECURITY.md "bot/skill nhập = mã từ người khác, chỉ nhập
  từ người tin".
- Đường "từ link" (Orca-style) chưa có — v1 chỉ nhập file local;
  link là v2 khi có kho công khai (skills.sh của keep-moat ph-3).
