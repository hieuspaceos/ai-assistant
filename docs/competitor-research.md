# Competitor research — học từ đối thủ

Ledger nghiên cứu: đối thủ nào → kiến trúc của họ → lấy gì → tránh gì →
đọc tiếp ở đâu trong source. Cập nhật khi đọc source thật; mục
`[chưa đọc]` nghĩa là phân tích từ docs/README, chưa verify bằng code.

Liên quan: `strategy.md` (vì sao những điểm này đáng lấy).

**Source đã clone shallow về `pet/research/`** (đọc-only, ngoài repo
này): `oh-my-pi` `codex` `openclaw` `browser-use` `stagehand`
`jev-assistant` `jev-agent` `CUA-JEV` `jev-eval-agent` `jev-jarvis`
`mem0` `letta-code`. Update bằng `git -C <dir> pull` khi cần.

## Trạng thái đọc

| Đối thủ | Trạng thái | Mức ưu tiên |
|---|---|---|
| GoClaw / OpenClaw | [đã học qua `pet/goclaw` — OpenClaw source tại `research/openclaw`] | Cao — đọc thêm AGENTS.md doctrine |
| TypeSafe Jev + jev-assistant | [đã clone `research/jev-*`] | **Cao** — nhỏ, cùng triết lý |
| openai/codex (codex-rs) | [đã clone `research/codex`] | **Cao** — Seatbelt sandbox đối chứng trực tiếp với `gen-sandbox.py` |
| Browser Use / Stagehand | [đã clone `research/browser-use`, `stagehand`] | Trung — cải thiện ext-bridge |
| oh-my-pi | [đã clone `research/oh-my-pi`] | Trung |
| Claude Code | [đọc docs, source đóng] | Trung |
| Cowork | [đóng — chỉ học hành vi] | Trung |
| Power Automate Desktop | [đóng] | Trung — ý tưởng record-to-skill |
| Mem0 / letta-code | [đã clone — letta repo gốc đã retire, code thật = `letta-ai/letta-code`] | Thấp — chưa cần memory layer |

---

## 1. OpenClaw / GoClaw — personal agent gateway

Đã học qua `pet/goclaw`. Ghi lại bài học đã rút:

- **Pattern gateway đúng**: brain ↔ channel tách biệt — GoClaw nhận
  Telegram/WhatsApp/HTTP/TUI cùng một "linh hồn". Ta cũng tách:
  portal/ext-bridge là channel, brain là brain. Nếu sau này thêm
  channel Zalo/Telegram cho Trợ Lý, đây là reference.
- **Transcript search / memory graph** (GoClaw làm tốt hơn OpenClaw):
  summary sau compaction vẫn searchable, fact → knowledge graph.
  → Áp dụng được cho `bot.md` + workspace khi cần "nhớ học viên" lâu
  dài. Chưa cần — ghi lại đây.
- **Onboard wizard** của họ rất đáng học (click-through, auto-detect
  config có sẵn → edit mode). Portal onboarding của ta cùng hướng.
- **Bài học ngược**: OpenClaw từng dính instance lộ ra net + prompt
  injection vì threat model yếu. Ta đã có loopback + token + "dữ
  liệu không phải lệnh" — giữ nguyên, đừng nới vì tính năng.
- **Scheduled/cron tasks**: OpenClaw cho agent chạy định kỳ → đây là
  lỗ hổng always-on của ta. Khi làm scheduled-runner, đọc
  `pet/goclaw` cách họ định nghĩa job + deliver kết quả về channel.
- **`research/openclaw/AGENTS.md` là một kho doctrine** đáng đọc kỹ
  — kinh nghiệm engineering agent-system đã nén: "prompt prefix
  stability" (đổi gì vào request phải giữ prefix để cache provider
  ăn), "cache identity" (key mọi cache theo đủ input thay-đổi-đáp-án),
  "one owner per responsibility", "delete before batching, cache
  last", quy tắc context chỉ append. Toàn bộ `.agents/skills/` của họ
  (55+ skills nội bộ) cũng là mẫu "skill bank" enterprise-grade để
  so với `.devin/skills/` của ta.

## 2. TypeSafe Jev + jev-assistant — decision layer tách khỏi generative

[chưa đọc source — README các repo `MayankChuriwal/jev-assistant`,
`pr0ta9/jev-agent`, `ZJU-REAL/CUA-JEV`]

Kiến trúc: model nhỏ trả lời **câu hỏi có kiểu** (choice API,
calibrated confidence, ~0.6s/lần) → code sở hữu toàn bộ control
flow → model to chỉ viết chữ khi cần prose. Guard/executor/verifier
đóng vòng lặp (CUA-JEV: "intent × channel" — chọn route
GUI/DOM/UIA/COM/CLI/MCP cho cùng một intent).

**Lấy:**

- **`habits` — verified-run replay**: jev-assistant lưu "habit" = một
  lần chạy đã-verify; lần sau gặp việc lặp thì replay theo habit,
  model chỉ check từng bước. → Trực tiếp map sang skill bank:
  walkthrough chạy thành công → lưu run-log → lần sau replay
  deterministic, chỉ gọi brain khi step lệch. **Giảm chi phí brain,
  tăng độ tin cậy — và skill bank trở thành executable asset thật
  sự.** Đây là món lớn nhất trong ledger này.
- **Decision layer rẻ cho consent**: một typed-choice judge trước
  mỗi hành động (cho phép / phải hỏi / chặn) → consent policy
  học-từ-approve mà không tốn brain call. Tham khảo khi làm
  "policy học từ approval" (strategy.md §8).
- **"intent × channel"** (CUA-JEV) chính là quy tắc "API → browser
  → báo user" ở strategy.md §6 — đọc `ActionCandidate`/
  `ActionGuard`/`ExecutorRegistry` của ZJU-REAL/CUA-JEV khi cần
  cài route-fallback cho skill.

**Tránh:** hidden-Chrome-riêng của jev-assistant — ta giữ phiên
của user. Persona tsundere — khỏi bàn.

## 3. openai/codex — harness Rust, sandbox thật

[chưa đọc source — repo `openai/codex`, `codex-rs/`]

Codex chạy macOS Seatbelt (`sandbox-exec`) + Linux Landlock, exec
policy, approval modes. **Đây là đối chứng 1-1 với `gen-sandbox.py`
+ `agent.sb` của ta** — đọc để so:

- Profile `.sb` của họ minimal đến đâu so với của ta (ta deny-write
  `tools/`, `brain.json`, `.git` — họ xử lý sao?).
- Exec policy schema: họ biểu diễn "command nào cần hỏi" thế nào
  (`codex-rs/core` + `sandbox` crates) → map sang `cmd_deny.py` +
  respond-gate.
- Approval UX modes của họ (read-only / auto / full) → so với
  consent card của ta; xem họ trình bày diff/lệnh thế nào cho user
  chấp thuận nhanh mà vẫn an toàn.

**Lấy:** chuẩn hoá `.sb` profile theo cách họ generate (nếu tốt
hơn); exec-policy schema nếu ta mở rộng allowlist lệnh.

## 4. Browser Use / Stagehand — page-state cho agent

[chưa đọc source]

Cách họ biến trang web thành input cho model: serialize DOM →
danh sách element đánh số + text gọn, action registry
(click #12, type "x"), verify-sau-action.

**Lấy:** cải thiện ext-bridge — hiện agent đọc trang kiểu gì qua
bridge :7684? Nếu đang dump HTML/screenshot thô thì chuyển sang
element-index serialization của Browser Use: ít token, hành động
xác định, verify được. Đây là nâng cấp kỹ thuật đáng giá nhất cho
làn DOM-fallback.

**Tránh:** headless-lane của họ (browser riêng của agent) — không
đổi làn.

## 5. oh-my-pi — tool benchmaxxing

[chưa đọc source]

Bài học lớn của họ: **cùng model, tool tốt hơn → chênh 10 lần**
(Grok Code Fast 6.7% → 68.3% chỉ nhờ sửa edit format). Role-based
model routing (default/small/plan/advisor → model khác nhau).

**Lấy:** đầu tư chất lượng *tool surface* (ext-bridge actions, skill
primitives) hơn đầu tư prompt; model routing rẻ cho subagent —
README đã ghi "pin cheaper model", nhìn cách họ cấu hình role→model.

## 6. Claude Code — hook + permission modes

[đọc docs, source đóng]

- **Hooks**: điểm chặn deterministic (PreToolUse/PostToolUse/…) —
  code của vendor chạy quanh loop. Ta đã có respond-gate/permission
  card; nếu sau này cho công ty cài "company hook" (VD: mọi skill
  gửi-tin phải log), đây là mô hình.
- **Permission modes** (default/plan/acceptEdits/bypass): cách họ
  cho user chọn mức tin cậy per-session → tham khảo khi làm "mức
  tin" trong portal.

## 7. Cowork — chỉ học hành vi

[đóng — đọc docs + quan sát]

- Folder-scope = `permissions.json` của ta — họ đi cùng kết luận,
  validate.
- **Scheduled tasks** — lỗ hổng always-on của ta (cùng OpenClaw §1).
- Projects = persistent context per-workstream → xem họ UI hoá
  context tích luỹ thế nào để học cách "cho kho hiện hình"
  (strategy.md §8).

## 8. Power Automate Desktop — record mode

[chưa đọc sâu]

Ý tưởng duy nhất đáng lấy: **user làm mẫu một lần → tool ghi lại →
thành flow**. Map sang ta: học viên *làm việc đó một lần trước mắt
trợ lý* (trình duyệt đang có extension!) → agent tự sinh skill +
walkthrough. Nén cold-start mạnh hơn cả `/phỏng-vấn` — "dạy bằng
mẫu" thay vì "dạy bằng hỏi". Nghiên cứu UX record của PAD/UiPath
khi làm tính năng này.

## 9. Mem0 / letta-code — memory pipeline

[thấp — chỉ khi cần]

Khi cần "trợ lý nhớ học viên" dài hạn: pipeline trích fact → store
→ retrieve vào context. Trước mắt `bot.md` + workspace đủ; đừng
build memory layer sớm.

Lưu ý: repo `letta-ai/letta` gốc đã retire (main chỉ là landing
page, code V1 khoá trên nhánh `archive`); implementation hiện tại là
`letta-ai/letta-code` — đã clone `research/letta-code`.

---

## Anti-patterns chung — không mang về

- Browser/VM **riêng** của agent (jev, Browser Use, Operator,
  Atlas): đánh mất làn "phiên của user" = đánh mất moat.
- Memory/chat-history làm moat: export được, yếu — moat ta là
  compiled context trong file khách.
- Cho agent **quyền tự mở cổng ra net** hay exec không qua consent
  (lỗi OpenClaw): threat model loopback của ta không nới.
- Đua tool-count/features: oh-my-pi cảnh báo đúng — **chất lượng
  tool surface > số lượng tool**.
