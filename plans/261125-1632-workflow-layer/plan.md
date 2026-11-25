# Plan 3/5 — Workflow layer: "bấm là chạy" + checklist verify

Ngày: 2026-11-25. Mục tiêu: biến `.devin/skills/` (vốn là "công thức dạy
học viên") thành **workflow triển khai** — nhân viên cty không cần biết
gì, mở portal → bấm nút → trợ lý làm → checklist hiện để soát kết quả.
Đây là sản phẩm bàn giao cho doanh nghiệp, không phải giáo trình.

## Nguyên tắc thiết kế

- **Zero bridge change**: workflow là file JSON tĩnh dưới
  `my-course/workflows/` → serve bởi :8080 như mọi nội dung khác.
  Portal đọc file, bấm nút → gửi `POST /api/prompt` hiện có. Không
  endpoint mới → `test-gates.py` không đụng tới.
- Workflow = **prompt được soạn sẵn + checklist kiểm chứng do người
  tick**. Não vẫn nhận prompt qua kênh cũ — skill tương ứng (nếu có)
  chỉ là công thức não tự dùng thêm.
- Phân phối qua config-pack (plan 2) — `workflows/` nằm trong pack.

## Format

`my-course/workflows/index.json` + `my-course/workflows/<id>.json`:

```json
// index.json — portal đọc trước để render danh sách
{"workflows": ["loc-khach-tinh", "dang-tour-moi", "doc-zalo-lead"]}
```

```json
// <id>.json
{
  "id": "loc-khach-tinh",
  "title": {"vi": "Tách khách theo tỉnh", "en": "Split customers by province"},
  "desc": {"vi": "File Excel khách lớn → mỗi tỉnh một file", "en": "..."},
  "icon": "📊",
  "dept": "sales",                       // phòng ban — pack gán sẵn, dashboard lọc
  "prompt": "Đọc file {{file}} trong Downloads, tách theo cột tỉnh thành, mỗi tỉnh xuất một file vào folder mới 'khach-theo-tinh'. File gốc giữ nguyên. Báo cáo số lượng mỗi tỉnh khi xong.",
  "inputs": [                            // field hỏi trước khi chạy (optional)
    {"key": "file", "label": {"vi": "Tên file khách"}, "placeholder": "khach-thang-11.xlsx"}
  ],
  "requires": {
    "connections": ["trinh-duyet"],      // cần extension nối? cần app nào?
    "permissions": ["~/Downloads"]       // cần folder nào được phép?
  },
  "checklist": [                         // hiện SAU khi agent xong — người tick
    "Mở folder 'khach-theo-tinh' thấy đủ file theo tỉnh",
    "File gốc vẫn còn nguyên trong Downloads",
    "Mở thử 2 file — số dòng khớp báo cáo"
  ],
  "verify": {                            // (B.3 — học quality gates GoClaw) máy tự check
    "glob": "khach-theo-tinh/*.xlsx",    //   trước khi hỏi người: đủ file không?
    "min_count": 5
  },
  "schedule": "0 8 * * MON"              // (B.4 — post-pilot) cron: tự chạy sáng T2
}
```

`verify` (optional): check được bằng máy — `glob` + `min_count`,
`file_exists`, `connection_status`. Sau event `done` → portal/bridge
tự chạy verify → báo xanh/đỏ TRƯỚC khi hiện checklist tay. Checklist
người vẫn giữ cho phần máy không đo được.
`schedule` (optional, phase sau): cron expr — launcher/beacon tick →
đúng giờ tự gửi prompt (vẫn qua consent nếu workflow khai `confirm:
true` — mặc định true: tự chạy ≠ tự làm). Đây là bản deterministic
của "heartbeat" (GoClaw có `internal/heartbeat` — agent tự thức dậy
định kỳ rồi TỰ QUYẾT có báo không); mình chọn bản prompt-cố-định vì
an toàn hơn — autonomous wake-up để sau khi fleet ổn.

Còn hai ý tưởng học được nhưng để `future` (ghi để không quên):
- `skill_search`: pack cty >20 skill thì não cần tìm-skill thay vì
  nạp hết (họ có BM25 `internal/skills`) — chưa cần vì pack nhỏ.
- `knowledge/`: pack ship thêm folder tri thức cty (SOP, danh mục
  dịch vụ...) mà skill tham chiếu — học `internal/vault` của họ.

## Tasks

### Phase 01 — Loader + UI danh sách trong portal

- [x] `web/index.html`: thêm section `#workflows` trong nav (dưới
      `#recipes`): "Quy trình" — render card: icon + title + desc +
      dept tag + nút "Chạy".
- [x] `web/app.js`: `loadWorkflows()` — fetch
      `/my-course/workflows/index.json` (trần, :8080 không cần token —
      nhớ `bfetch` chỉ gắn token cho :7682/:7684 nên dùng `fetch`
      thường cho :8080). File không có → section ẩn (single-user không
      bị nhiễu).
- [x] i18n vi/en cho nhãn section — title/desc lấy theo `config.language`
      fallback vi.
- [x] Group theo `dept` nếu >1 dept — doanh nghiệp nhiều phòng ban nhìn
      gọn.

### Phase 02 — Chạy workflow: inputs + preflight + prompt

- [x] Bấm "Chạy" → panel nhỏ:
      1. Nếu có `inputs` → form điền (text ngắn, không file picker —
         non-coder gõ tên file).
      2. Preflight: `requires.connections` — GET /api/connections, app
         cần mà status ≠ connected → cảnh báo "cần mở Zalo trước" kèm
         nút mở `open_url`; `requires.permissions` — GET
         /api/permissions, folder thiếu → hướng dẫn "nhờ trợ lý xin
         quyền" (không tự grant — đó là consent của user).
      3. Soạn prompt: template `{{key}}` thay bằng input → gửi
         `POST /api/prompt` {text} y hệt gõ tay → chuyển sang tab chat
         cho user xem nó làm.
- [x] Prompt soạn sẵn luôn kèm: "xong thì nói rõ từng mục trong
      CHECKLIST sau đúng hay sai" — tự in checklist trong câu trả lời,
      nhân viên đối chiếu bằng mắt.

### Phase 03 — Checklist verify sau khi agent xong

- [x] Lưu `running_workflow` trong tab: khi event `done` tới (đã có
      kênh /api/poll qua chat.html) → hiện panel checklist bên dưới
      khung chat: từng mục checkbox + nút "Tất cả đúng" / "Có vấn đề".
- [x] "Có vấn đề" → prefill prompt: "workflow `<id>` vừa chạy có vấn
      đề ở mục: <mục user tick sai> — kiểm tra lại và sửa" → gửi tiếp.
      Vòng sửa tự nhiên.
- [x] Kết quả tick (không gửi đi đâu — chỉ UI); adoption đo bằng
      beacon đếm event `done` là đủ cho dashboard.
- [x] Nếu chạy từ chat.html (iframe) — checklist panel đặt ở portal
      cha, đọc poll events chung... hoặc đơn giản hơn: checklist render
      trong chat pane ngay dưới iframe chat (portal cha quản), trạng
      thái done lấy từ `bfetch /api/poll` của chính portal — portal đã
      poll cho ext-status sẵn? Kiểm lại app.js poll loop — nếu không có
      thì thêm poll nhẹ khi workflow đang chạy.

### Phase 03.5 — Verify tự động (B.3)

- [x] Engine `verify`: sau `done` của workflow run → đánh giá
      `verify.glob`/`min_count`/`file_exists` bằng portal (đọc qua
      `GET /api/check-path` có sẵn hoặc nhờ agent check) → chip
      xanh "máy kiểm thấy đủ" / đỏ "thiếu — xem checklist".
- [x] Đỏ → auto-prefill prompt sửa (giống nút "Có vấn đề").

### Phase 04 — Pack mẫu + tích hợp distribution + docs

- [x] 3 workflow mẫu dựng sẵn trong repo (`my-course/workflows/`):
      `gom-downloads` (gom file Downloads theo loại), `nen-anh-web`
      (nén ảnh Canva đăng web), `tom-tat-tuan` (đọc file + tóm tắt).
      Mỗi cái map vào skill sẵn có → prompt tái dùng đúng công thức.
- [x] `test-packs.py` mở rộng: validate schema workflow file (id khớp
      tên file, prompt không rỗng, checklist ≥1 mục, requires trỏ id
      connection có thật trong connections mẫu).
- [x] `docs/codebase-summary.md` mục workflows; `DEPLOY.md` (plan 4)
      ghi cách IT/đội triển khai viết workflow cho cty.

## GATE

- `my-course/workflows/` có 3 file → portal hiện 3 card → bấm chạy
  `gom-downloads` → prompt đi vào chat → agent làm → `done` → checklist
  hiện → tick "có vấn đề" → prefill prompt sửa gửi được.
- Xoá `workflows/` → portal không hiện section, không lỗi.
- Workflow khai `requires.connections: ["zalo"]` mà zalo status
  ≠ connected → preflight chặn + hướng dẫn mở.

## Rủi ro / mở

- Prompt soạn sẵn trong file JSON = nội dung não đọc — pack độc có thể
  bơm prompt xấu? Pack đi từ collector cty (tin tưởng nội bộ) +
  permissions/sandbox vẫn kẹp hành vi — rủi ro giống hệt bot.md, đã có
  mô hình. Ghi vào SECURITY.md residual.
- `{{inputs}}` tự do → injection vào prompt? Prompt là của chính user
  gửi — không có biên tin cậy nào bị vượt (agent nhận prompt từ user
  y hệt gõ tay). Vẫn escape khi render vào DOM (escapeHtml sẵn có).

## Kết quả (implement xong 2026-11-25)

- `my-course/workflows/`: index.json + 3 mẫu (gom-downloads,
  nen-anh-web — có verify dir glob, tom-tat-tuan — verify file output).
- `web/index.html` + `app.js` + `styles.css`: section #workflows trong
  nav (group theo dept khi >1), overlay chạy (inputs + preflight cảnh
  báo không chặn cứng), POST /api/prompt → switchTab chat, watch poll
  đợi done (mốc baseline, timeout ~10'), verify qua count-glob → chip
  xanh/đỏ, checklist panel fixed — "Có vấn đề" gửi prompt sửa + đợi
  done tiếp; verify đỏ → auto gửi fix prompt.
- `GET /api/count-glob` (mới, .py + .ps1 parity): trả SỐ file khớp glob
  — không tên file; pattern chặn ../ và /; dir sensitive → 0. Sửa luôn
  drift: check-path .ps1 thiếu Test-SensitivePath so với .py.
- `tools/test-packs.py` mục 7: validate schema workflow (id=tên file,
  prompt rỗng, checklist≥1, requires.connections khớp id app, {{key}}
  phải khai inputs, title có vi, verify.glob không ..).
- docs/codebase-summary.md mục workflows; DEPLOY.md mục 6 viết workflow.
- CHƯA LÀM: `schedule` cron (plan ghi phase sau — cần launcher tick +
  consent confirm, để post-pilot). GATE end-to-end (bấm nút → agent làm
  → checklist) cần não thật — verify tay khi pilot; phần machine-check
  (count-glob live, schema, parity, gates) đã xanh.
