# Plan 5/5 — IMA pilot: case study đầu tiên trên khách thật

Ngày: 2026-11-25. Mục tiêu: triển khai cho **IMA** (công ty du lịch,
`ima-crm`: Sales → Operator → Kế toán, ~10 site WordPress headless)
như deal pilot — ra được adoption metrics + case study để đi bán.

**Bối cảnh đã có:**
- `plans/2026-11-20-ai-assistant-integration-brainstorm.md` (ima-crm):
  chọn phương án A — agent per-máy + MCP vào `mcp-server :3010` +
  extension lái Zalo/portal.
- `pet/ima-assistant` fork + P0 đã xong phần code (AGENTS.md IMA,
  skill ket-noi-ima/tra-tour, mcp config, my-course template).
- **Quyết định mới (plan 2): không fork** — IMA trở thành
  `packs/ima/` trong ai-assistant; máy NV chạy ai-assistant chuẩn +
  pack. Fork migrate, deprecated.

**Phụ thuộc:** plan 1 (fleet), plan 2 (distribution + pack), plan 4
(extension Web Store — bắt buộc trước khi cài cho người khác).

## Tasks

### Phase 01 — Migrate fork → `packs/ima/`

- [x] `tools/sync-fork.sh` (plan 2, phase 02.5) — kéo code mới nhất vào
      fork trước để không mất việc đang dùng.
- [x] Bóc phần riêng của fork thành `packs/ima/`:
      - **TOÀN BỘ skill riêng của fork** → `packs/ima/skills/`:
        `ket-noi-ima`, `tra-tour`, `lam-tour*` (6 skill), `lam-khach`,
        `bao-cao`, `gui-ope`, `xem-lai`, `xuat-tour`,
        `doc-zalo-tao-lead` — diff thực tế ~14 skill, không chỉ 2
        (audit round 5).
      - Luật CRM (7 luật trong AGENTS.md fork) →
        `packs/ima/rules.local.md`
      - MCP cần **HAI file** (audit round 5 — fork hiện chỉ có một):
        `mcp_config.json` = não (Devin CLI tự đọc từ cwd —
        `session/new` truyền `mcpServers:[]` nên MCP vào não nhờ
        CLI load file, không qua bridge) + `mcp_config.local.json`
        = probe kết nối + whitelist sandbox đọc (chat-bridge:1000,
        gen-sandbox:212). Pack ship cả hai template; URL env-param
        hoá (local `127.0.0.1:3010` vs public).
      - `my-course/` template → `packs/ima/course-template/`
      - `packs/ima/pack.json` gom tất cả + `dept` mapping.
- [x] Persona sales trong AGENTS.md fork → chuyển phần "giọng nói/
      vai trò" sang `bot` IMA trong pack (bot.md vốn là chỗ persona);
      rules.local.md chỉ giữ luật nghiệp vụ.
- [ ] Xoá `pet/ima-assistant` khi pack chạy thử OK trên một máy test —
      ghi lại trong progress.log của repo pet.

### Phase 02 — Deploy mcp-server public + gate thật

(từ P0 còn nợ — cần credentials thật)

- [ ] Deploy `mcp.imagetraveldmc.com` qua CapRover + DNS (theo plan
      ima-crm — việc của repo kia, liệt kê ở đây để tracking).
- [ ] JWT per-employee: mcp-server auth per user (sales chỉ thấy tour
      của mình — đã có authorizeTripEventWrite từ P0).
- [ ] GATE: máy test chat → `whoami` đúng người → đọc tour thật qua
      endpoint public → nhiều session đồng thời không rớt.
- [x] `connections.json` mẫu trong pack: entry `ima-crm` probe type
      `mcp` trỏ URL public. Probe `mcp` check `mcp_config.local.json`
      (chat-bridge:999-1003) — file này phải có mặt trước khi đánh
      "đã kết nối".
- [x] Verify end-to-end MCP: hiện chỉ probe-check là có config, chưa
      chứng minh tool thật tới não — GATE `whoami` là lần chứng minh
      đầu tiên trên core. Nếu CLI không tự load `mcp_config.json`
      thì phải sửa `session/new` nạp servers (thay đổi bridge nhỏ —
      khai OPEN_OK không cần gate vì là GET-equivalent? — không,
      session/new là nội bộ, không phải endpoint).

### Phase 03 — Workflow theo phòng ban (plan 3 đọc được format này)

Mỗi workflow = `packs/ima/workflows/<id>.json` — prompt soạn sẵn
theo quy trình tour thật + checklist verify:

| Dept | Workflow | Làm gì |
|---|---|---|
| Sales | `tra-tour-nhanh` | Tra cứu tour/availability qua MCP — prompt + kết quả |
| Sales | `doc-zalo-lead` | Đọc Zalo Web → trích lead → điền draft booking qua MCP |
| Sales | `tao-bao-gia` | Từ tour code → draft báo giá (docx từ template) |
| Operator | `kiem-vendor` | Đối chiếu dịch vụ tour vs vendor confirm |
| Kế toán | `gom-hoa-don` | Gom hoá đơn/bill theo tour → file tổng hợp |
| Content | `dang-tin-tour` | Đăng tour/tin lên 1 trong 10 site WP headless (REST API — đã có skill dang-bai) |
| Tất cả | `bao-cao-tuan` | Đọc CRM → tóm tắt tuần theo người/phòng |

- [x] Viết 7 file workflow (ưu tiên `tra-tour-nhanh` +
      `doc-zalo-lead` trước — đúng 2 việc brainstorm nêu là giá trị).
- [x] `requires` đúng: `doc-zalo-lead` cần connection `trinh-duyet`
      + tab zalo; `tra-tour-nhanh` cần connection `ima-crm`.
- [x] `test-packs.py` chạy qua pack IMA — validate schema + tồn tại
      connection/skill tham chiếu.

### Phase 04 — Rollout pilot

- [ ] Chọn ~5 nhân viên (2 sales, 1 operator, 1 kế toán, 1 content) —
      đủ nhỏ để support tay.
- [ ] Bộ cài: ai-assistant chuẩn + `license.json` (org IMA, seats 10,
      expiry +6 tháng) + `fleet.json` (collector = máy IT IMA).
- [ ] Cài theo `deploy/install.ps1` + force-install extension qua
      policy (nếu IMA có MDM) hoặc unpacked tay tạm.
- [ ] Collector: IMA có domain + CapRover → **customer-hosted**:
      `fleet.imagetraveldmc.com` là một app trong CapRover của họ
      (cert LE sẵn có) — remote beacon được, metadata ở lại hạ tầng
      IMA. Đây cũng là mẫu triển khai để viết vào case study.
- [ ] Onboarding mỗi máy 30': mở portal → workflow list → chạy thử
      `tra-tour-nhanh` → tick checklist.

### Phase 05 — Đo + case study

- [ ] 2-4 tuần: dashboard collector đếm lượt `done`/máy/ngày, workflow
      nào được bấm, lỗi nào tái diễn → sửa pack, phát lại (đúng cơ chế
      distribution — không đi từng máy).
- [ ] Hỏi chủ: metric họ quan tâm (thời gian trả lời khách? số booking
      draft?) — ghi baseline trước cài để so.
- [ ] `docs/case-study-ima.md` — viết như case DOVI của AgileOps:
      bài toán, cách triển khai, số liệu adoption, phản hồi nhân viên.
      Đây là tài liệu bán hàng chính.

## GATE

- 5 máy IMA beacon lên collector; dashboard thấy đủ máy + license.
- Workflow `tra-tour-nhanh` chạy được trên máy sales thật, đọc đúng
  tour của người đó (JWT scope).
- Update code + pack mới phát từ collector → 5 máy tự nhận, không ai
  phải đi cài lại.
- Case study doc có số liệu thật.

## Rủi ro / mở

- `mcp.imagetraveldmc.com` public — mcp-server của ima-crm phải đứng
  vững (rate-limit + audit đã có từ P0; thêm uptime monitor).
- Zalo Web của sales: session login hết hạn/đổi máy → workflow Zalo
  chết → preflight của workflow-layer phải bắt được (đã thiết kế).
- SWE-2/Devin làm việc văn phòng tiếng Việt — pilot chính là nơi đo;
  nếu não yếu thì đổi preset não cho IMA ngay (brain.json = pack cũng
  gợi ý được).

## Kết quả (phần in-repo xong 2026-11-25)

- `packs/IMA/pack.json` **v3**: 14 skill IMA + `bots[ima-sales]` (persona
  tách khỏi rules — giọng đồng nghiệp, thuật ngữ tour, cấm jargon) +
  `rules_local_md` chắt còn 7 luật CRM + báo cáo + an toàn +
  `connections` (ima-crm/trinh-duyet/zalo/outlook/wordpress) +
  `permissions_template` (~/Downloads read).
- `workflows` trong pack: index.json + 7 quy trình theo phòng ban
  (tra-tour-nhanh, doc-zalo-lead, tao-bao-gia [sales]; kiem-vendor
  [operator]; gom-hoa-don [ke-toan]; dang-tin-tour [content];
  bao-cao-tuan [van-phong]) — requires trỏ đúng connection, gom-hoa-don
  có verify count-glob.
- `apply-pack.py` mở 2 kênh mới có whitelist: `devin_files` (chỉ
  mcp_config.json + mcp_config.local.json + env-allowlist.json — pack
  được đặt MCP config cho não/probe, KHÔNG đụng token/key/license) +
  `mycourse_files` (CHỈ máy mới, .md/.json/.jsonl — ima-rules scaffold,
  rules-cua-toi, ima-sandbox write-guard).
- `sync-fork.sh` → merge thay vì overwrite: pack tay-dựng
  (workflows/bots/rules chắt/devin_files) sống sót re-sync; skills +
  connections vẫn hút từ fork; rules_local_md chỉ hút lần đầu.
- VERIFY thật: apply-pack --file packs/IMA/pack.json lên máy giả —
  skills/workflows+mcp+rules+bot+index đủ chỗ; máy mới được thêm
  mycourse_files + permissions; máy cũ giữ nguyên file cá nhân.
- NỢ OPS (ngoài repo): deploy mcp.imagetraveldmc.com + JWT per-user
  (repo ima-crm), extension lên Store (plan 4 GATE ops), bộ cài +
  license IMA 10 ghế + fleet.imagetraveldmc.com, onboarding 5 máy,
  đo 2-4 tuần, docs/case-study-ima.md.
