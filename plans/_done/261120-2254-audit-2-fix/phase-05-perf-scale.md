# Phase 05 — Hiệu năng & scale hygiene

## Vá

**P1–P6, S14, C1–C3** — perf theo mức độ ảnh hưởng + scale tài nguyên.

## 5.1 — `serve.ps1` async + stream (P1 — Windows = primary)

Hai vấn đề: `GetContext()` đơn luồng serialize mọi request; `ReadAllBytes`
đọc toàn file kể cả Range.

Viết lại vòng lặp:

```powershell
$listener.Start()
while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    Start-ThreadJob -ScriptBlock $handleCtx -ArgumentList $ctx | Out-Null
}
```

- `Start-ThreadJob` (ThreadJob module — có sẵn PS7; PS5.1 cần
  `Install-Module ThreadJob` hoặc dùng runspace pool viết tay ~40 dòng —
  chọn runspace pool để không thêm dependency).
- File stream: `[IO.File]::OpenRead($resolved)` + `Seek($s)` + copy đoạn
  `CopyTo($res.OutputStream)` — Range không còn đọc full file.
- `CopyTo` theo chunk 256KB; `ContentLength64` set đúng (giữ keep-alive
  của HttpListener).
- Mọi logic khác (dotfile block, CSP, mime, Range parse, blocklist
  phase-04) giữ nguyên — chỉ đổi IO path + concurrency.

## 5.2 — `hist_write` buffered + rotate trong session (P2 + P3)

`chat-bridge.py`:

- Giữ fd mở module-level (`_hist_fd`), flush mỗi 32 event hoặc khi event
  `done`/`err`/`ready` — đóng fd đúng cách ở shutdown (atexit).
- Đếm write; mỗi 500 lần → `rotate_history()` (không còn chỉ-lúc-boot).
  Giữ `HIST_MAX_BYTES` 2MB + `MAX_EVENTS` 3000.

## 5.3 — `.logs/*.log` rotation (C1)

`launcher.py` watchdog loop (đã chạy 1s/vòng): mỗi 1h kiểm
`<DATA>/.logs/*.log` >5MB → giữ 1MB đuôi (đọc tail + ghi lại). Cùng mẫu
`.shots` cap-50 đã có.

## 5.4 — `content.js` perf (P4, P5) + `tinsert` (P6) + `fetch` guard (S14)

- `actClick`: 2-pass trong 1 map — vẫn đọc innerText 1 lần nhưng
  **early-exit** khi gặp exact-match đầu tiên (không cần scan hết 6000).
- `assets` bg-scan: prefilter `el.getAttribute('style')` có chứa
  `background` hoặc tag là `[style],[class]`… — thực tế chỉ cần giảm
  5000 → 1500 cap + bỏ qua element `hidden/display:none` trước khi
  `getComputedStyle` (đã có `visible()`).
- `tinsert` mode `char`: `p.ms` param (default 35, min 5) — agent tự điều
  chỉnh khi cần nhanh; docs trong docstring ext-bridge.
- `fetch` action: kẹp URL cùng site với tab đang mở — eTLD+1 heuristic
  (2 label cuối + known 2-level TLD ngắn gọn như `co.uk`, `com.vn`):
  `new URL(p.url)` host không cùng site `location.hostname` →
  `{ok:false, err:"chỉ tải được URL cùng site đang mở"}`. gviz
  (docs.google.com) vẫn qua vì cùng site `google.com` với
  sheets.google.com.

## 5.5 — Seed `my-course` gọn (C2)

`launcher.py` `_copy_tree` với `SEED_DIRS`: skip `my-course/clone-work`
(DOM site thật bên thứ 3 — vừa IP/privacy vừa phình binary). Giữ
lesson-* + manifest + json (course demo vẫn là sản phẩm). `build.sh`
không đổi — exclusion ở launcher.

## 5.6 — Bind-loopback assert (C3)

3 server (`serve.py`, `chat-bridge.py`, `ext-bridge.py`) + ttyd spawn:
bind host lấy từ `BIND_HOST = os.environ.get("TROLY_BIND","127.0.0.1")`;
assert nếu `BIND_HOST` không phải loopback thì bắt buộc
`TROLY_ALLOW_REMOTE=1` mới chạy — fail-closed trước khi ai đó đổi bind
cho relay.

## 5.7 — `chat.html` 2-tab reset storm (nhỏ)

Cursor `since` lưu localStorage theo tab-id → 2 tab mở không đạp nhau
replay 3000 events. Nhỏ — làm nếu còn thời gian, không block phase.

## Test

- serve.ps1: benchmark 20 request song song (trước/sau) — verify trên
  máy Windows thật; Range trên file lớn không alloc toàn file.
- test-bridges.py: hist fd reuse (file handle mở 1 lần — kiểm qua flush
  count gián tiếp), fetch same-site guard là unit test JS (test thủ công
  qua ext-bridge action — khó tự động → verify tay + checklist).
- Seed: chạy `launcher.py bootstrap` vào tmp → `my-course/clone-work`
  không tồn tại.

## Done khi

Portal Windows tải asset song song; video tua không đọc full file; log
không phình vô hạn; `fetch` chỉ đi cùng site.
