---
title: "Khoá các cửa mở + tăng tốc — audit bảo mật/hiệu năng/mở rộng 2026-11-20"
description: "Audit vòng 2 (kiểm chứng bằng test thật trên máy) xác nhận 3 lỗ hổng: ttyd -W nhận WS từ mọi origin → shell mở trần; serve.py không check Host → rebinding đọc file trên macOS; mọi .html trong my-course/ chạy script cùng origin với bridge_token + /api/respond nhận id tuỳ ý → tự duyệt quyền. Kèm điểm hiệu năng (full-DOM scan, render stream O(n²)) và nợ mở rộng (poll chặt, prompt không serialize, race ext-bridge)"
status: draft
priority: P0
effort: M
branch: main
tags: [security, perf, hardening, parity]
created: 2026-11-20
depends-on: 261120-1635-fix-audit (test infra test-bridges.py/parity đã có, tái dùng)
---

# Khoá các cửa mở — vá audit 2026-11-20

## Bối cảnh — audit vòng 2 chứng minh được gì

Đã kiểm chứng bằng cách chạy thật (không phỏng đoán):

| # | Vấn đề | Mức | Bằng chứng |
|---|--------|-----|-----------|
| A | `ttyd -W` không `-c`/`-O` → nhận WS từ **mọi Origin/Host** | **Cao** | Test trực tiếp trên ttyd 1.7.7 máy dev: handshake `Origin: evil.example.com` + `Host: attacker-via-rebind.com` → `101 Switching Protocols`. Bất kỳ trang `localhost:*` nào cũng có shell quyền user |
| B | Mọi `.html` trên `:8080` (slide, clone) chạy script **cùng origin với `localStorage.bridge_token`** | **Cao** | `iframe()` dùng `sandbox="allow-scripts allow-same-origin"` (tương đương không sandbox); clone-view iframe không sandbox; `/api/save-page` không lọc nội dung; clone có sẵn `<script>` hợp lệ |
| C | `/api/respond` nhận `id`/`optionId` tuỳ ý — không kiểm pending | Cao (vào chuỗi B) | `chat-bridge.py:520-534` — trang độc tự duyệt permission card, bypass lớp chặn con người |
| D | `serve.py` không check `Host` → DNS rebinding đọc file (macOS/Linux) | Trung bình | Không lộ token (localStorage theo host:port), read-only, Chrome chặn phần lớn qua PNA — nhưng Safari/Firefox + nav top-level còn hở. **Windows an toàn hơn** nhờ http.sys prefix `localhost` |
| E | `next_id` race trong ext_call → response về sai pending | Nhỏ | `ext-bridge.py:200` — tăng id ngoài lock, thread-per-conn |
| F | `ws_recv` không cap kích thước frame → memory DoS | Nhỏ | `ext-bridge.py:128-150` |
| G | content.js quét full-DOM ép reflow (actClick text, scrollableEls, assets) | Trung bình | `innerText`/`getComputedStyle` lặp trên hàng chục nghìn node — giật rõ trên Zalo/Sheets |
| H | chat.html re-parse markdown **toàn văn** mỗi chunk → O(n²) | Trung bình | `chat.html:222-227` |
| I | Poll 900ms = thread mới mỗi request; không long-poll | Nhỏ | chậm thừa, tốn thread |
| J | Prompt không serialize — 2 tab gửi đồng thời đan xen event | Nhỏ | `/api/prompt` không busy flag |

Nguyên nhân gốc của A+B+C cùng một mẹ: **token chỉ bảo vệ được cửa nào
đi qua nó** — ttyd là cửa thứ 3 không qua tay code tự viết nên tuột khỏi
mô hình; còn "vùng nội dung" (my-course html) nằm chung origin với
"chìa khoá nhà" nên script trong vùng đó thừa hưởng quyền.

## Thiết kế tổng thể

1. **Khoá cửa thứ 3** — `ttyd -O` (check-origin). Chọn `-O` không phải
   `-c` vì: WS của ttyd hợp lệ phát từ chính document `localhost:7681`
   (iframe), còn trang lạ `localhost:PORT_khác` có Origin khác → bị từ
   chối. `-c` basic-auth không dùng được vì browser không cho credential
   nhúng trong iframe src. Residual: rebinding (Origin==Host sau rebind)
   — ghi nhận trong SECURITY.md, giảm thêm khi phase 1 có Host check.
2. **Cách ly credential khỏi vùng nội dung bằng CSP** thay vì tách port:
   thêm `Content-Security-Policy` cho `.html` dưới `/my-course/` + `/intro/`
   với `connect-src 'none'` → script trong clone/slide vẫn chạy (nút
   chuyển slide cần), nhưng **không gọi được bridge** (fetch/XHR/WS/
   sendBeacon đều chết). Chọn CSP vì: ~15 dòng mỗi file serve, KHÔNG động
   portal/app.js/clone-view, trong khi tách port (:8081) phải sửa serve
   + start script + CORS + mọi URL trong portal — blast radius lớn hơn
   nhiều. Residual ghi rõ: exfil token qua `<img src=https://evil>` vẫn
   được (img-src mở https: cho ảnh học viên chèn) nhưng token đó vô dụng
   với kẻ xa — bridge chỉ loopback và Origin-check chặn trang lạ.
3. **Siết `/api/respond`** — bridge nhớ map `id → optionIds` khi broadcast
   perm; respond chỉ nhận id đang pending + optionId có trong danh sách
   (+ `__cancel__`); dùng xong xoá (one-shot), xoá hết khi `done`/`ready`.
4. **Hiệu năng** — đúng 2 chỗ đo được là đau: full-DOM scan (cache kết
   quả text một pass, cap số node) và render stream (batch bằng rAF).
   Không "tối ưu" lan man.
5. **Mở rộng** — chỉ làm phần rẻ có ích ngay: long-poll `/api/poll` +
   serialize prompt; phần lớn (multi-session, sandbox agent) để out of
   scope vì là viết lại, không phải vá.

Parity: mọi thay đổi `.py` có bản `.ps1` tương đương (hoặc ghi rõ lý do
miễn — vd serve.ps1 đã an toàn Host nhờ http.sys). Test mới bổ sung vào
`tools/test-bridges.py` (harness `check()` có sẵn).

## Phases

| # | Phase | Nội dung | Link |
|---|-------|----------|------|
| 1 | Khoá cửa mở | `ttyd -O` (start.sh + chat-terminal.ps1); `serve.py` Host check; ext-bridge race + WS cap | [phase-01](./phase-01-open-doors.md) |
| 2 | CSP cách ly | CSP header cho `.html` dưới `/my-course/`, `/intro/` — serve.py + serve.ps1; verify clone-view edit vẫn sống | [phase-02](./phase-02-csp-isolation.md) |
| 3 | Siết respond | pending-perm map + validate id/optionId + one-shot — `.py` + `.ps1` | [phase-03](./phase-03-respond-gate.md) |
| 4 | Hiệu năng | content.js: 1-pass text scan + cap node; chat.html: rAF batch render; vendor cache header | [phase-04](./phase-04-perf-scans.md) |
| 5 | Mở rộng + kiểm chứng | long-poll `/api/poll`; serialize `/api/prompt`; test mới; cập nhật SECURITY.md/decision-log; checklist Windows | [phase-05](./phase-05-scale-tests.md) |

## Rủi ro chính

- **R1** (kế thừa plan trước): mọi `.ps1` là **UTF-8 có BOM — bắt buộc
  giữ**, mất BOM → vỡ font tiếng Việt trên Windows 5.1.
- **R2**: CSP siết quá tay làm clone chết (ảnh https: học viên chèn, font
  remote) → whitelist rộng `img-src/style-src/font-src` gồm `https:`,
  chỉ siết `connect-src` + `form-action` + `base-uri` — chỗ đau nhất.
  Rollback = bỏ header, không migration.
- **R3**: `ttyd -O` trên bản ttyd cũ không có flag → start fail ngay (dễ
  thấy, không âm thầm). ttyd `-O` có từ 1.4.x; winget/brew đều bản mới.
- **R4**: pending-perm map lọt trường hợp agent gửi perm khi UI đang
  reconnect/reset → dọn map khi broadcast `ready`/`done` để không kẹt.
- **R5**: refactor actClick đổi thứ tự ưu tiên khớp → hỏng /doc-zalo.
  Giữ nguyên hai bước khớp (exact → contains, chọn nhỏ nhất), chỉ đổi
  cách thu thập text thành 1 pass.
- **R6**: long-poll trên ThreadingHTTPServer giữ 1 thread/client — OK ở
  1 client; cap `wait` ≤ 30s + timeout sạch. `.ps1` (HttpListener) phức
  tạp hơn — nếu vướng, cho `.py` trước + ghi nợ parity vào plan.

## Out of scope

- Tách `my-course/` sang port riêng (:8081) — phương án mạnh hơn CSP
  nhưng động nhiều file; chỉ làm nếu CSP tỏ ra thiếu hoặc khi làm relay.
- Sandbox process agent (chạy trong container/Seatbelt) — thay đổi mô
  hình vận hành, bàn riêng.
- Giảm quyền extension (`debugger`, `<all_urls>`) — là trade-off của
  nhóm action `t*`, không bỏ được mà giữ tính năng.
- Multi-session / multi-browser / multi-brain đồng thời.
- Relay/VPS — đã có plan `261120-1500-relay-mobile`.
- Enforce `permissions.json` ở tầng hệ thống (hiện là policy cho agent,
  không phải boundary kỹ thuật) — sửa SECURITY.md gọi đúng tên, enforce
  thật thuộc mục sandbox ở trên.

## Thứ tự thực thi

Phase 1→2→3 làm liền (đều vài chục dòng, đóng các chuỗi tấn công). Phase
4 độc lập, làm sau. Phase 5 chốt test + doc. Mỗi phase commit riêng.
