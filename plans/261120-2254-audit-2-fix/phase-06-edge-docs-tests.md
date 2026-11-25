# Phase 06 — Edge cases + CI + docs + verify tổng

## Vá

**S8, S9, S10-sh, S13-CI** + cập nhật tài liệu + test tổng hợp.

## 6.1 — `options.html` persist sau verify (S8)

Hiện options ghi `chrome.storage.local` TRƯỚC khi bridge chấp nhận — phá
invariant "chỉ persist sau khi WS mở".

- Bỏ `chrome.storage.local.set` ở options; chỉ `sendMessage({t:'set-token'})`
  → background persist trong `ws.onopen` (đã có sẵn).
- Ô input vẫn prefill từ storage (đọc là ok); nút Lưu hiện trạng thái
  "đang thử nối…" rồi badge ON/! tự nói kết quả.

## 6.2 — `term-gate.sh` POSIX + 3 lần thử (S10)

- `read -t` không POSIX (dash) → spawn bằng bash rõ ràng: `start.sh`
  `ttyd … -a bash tools/term-gate.sh`, `launcher.py` `["bash", gate]`.
- Loop 3 lần nhập mã (đúng docs "sai 3 lần/timeout 90s"), `read -r -t 90`.

## 6.3 — S9: token trong argv `ttyd -a`

Không vá được sạch mà không mất autofill (`?arg=` là cơ chế duy nhất của
ttyd). Xử lý:

- `SECURITY.md` ghi accepted-risk rõ: token hiện trong `ps` — chỉ đáng
  kể trên máy multi-user; khuyến nghị `TROLY_TERM_STRICT=1` (env mới):
  khi set, portal KHÔNG autofill `?arg=` và term-gate luôn hỏi mã tay.
- `app.js`: đọc env flag qua `/api/health` field mới `termStrict` (field
  cộng thêm, không phá parity — ps1 trả undefined → falsey).

## 6.4 — CI pins (S13)

`.github/workflows/build.yml`:

- Pin actions theo SHA: `actions/checkout@<sha-v4>`, `setup-python@<sha-v5>`,
  `upload-artifact@<sha-v4>`, `download-artifact@<sha-v4>` (comment giữ tag
  để đọc).
- `pip install pyinstaller` → pin `pyinstaller==<ver>` (bản ≥7 ngày tuổi).

## 6.5 — Docs cập nhật

- `docs/SECURITY.md`: thêm hàng trust-boundary mới — consent-gate
  (`local_pending`), cmd denylist + terminal regex, probe schema,
  secrets url-wipe, sandbox write-allowlist (vùng ghi mới), accepted-risk
  S9 + `TROLY_TERM_STRICT`, limitation Windows nâng cấp cảnh báo (S5).
- `docs/api-reference.md`: ghi `202 {pending}` contract của 4 endpoint
  gated + `termStrict` trong `/api/health`.
- `docs/troubleshooting-runbook.md`: mục "card xác nhận nằm trong tab
  chat — không thấy thì poll history".
- README "Design philosophy > Safe by default" thêm 1 dòng consent-gate.

## 6.6 — Test tổng + verify

`tools/test-bridges.py` — mọi check mới đã rải ở phase-01..05 tổng hợp
chạy xanh 1 lượt trên macOS (sandbox tests tự skip off-Darwin).
`test-parity.py` + `test-packs.py` pass. Verify tay trên Windows cho
phần .ps1 (checklist trong phase-04/05).

## Done khi

- `python tools/test-bridges.py` → all pass.
- `SECURITY.md` phản ánh đúng kiến trúc mới (gate, write-allowlist,
  probe schema, accepted risks rõ).
- Không còn finding audit nào mở — mỗi mục hoặc đã vá hoặc đã ghi
  accepted-risk có lý do.
