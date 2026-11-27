---
title: "UX polish — khởi động gọn & lỗi nói tiếng Việt: start scripts tôn trọng config.terminal, nút Việc mới, stderr → card báo lỗi, spike OAuth trình duyệt, nộp extension lên Web Store"
description: "Phần ẩn Terminal đã làm trong launcher.py + portal toggle, nhưng start.bat/start.sh vẫn spawn ttyd lúc boot (start.bat còn tự cài qua winget). stderr của não bị DEVNULL nên lỗi OAuth hết phiên không thành card tiếng Việt được. Chưa có nút bắt đầu hội thoại mới. Extension zip đã sẵn trong dist/ chỉ chờ nộp store. Plan gom các việc nhỏ cho cảm giác 'mượt' ngay."
status: done
priority: P1
effort: M
branch: main
tags: [ux, startup, error-handling, extension]
created: 2026-11-27
---
> **Trạng thái (2026-01):** phase 01–07 đã code xong cả hai bridge
> (.py + .ps1) + portal; test suite xanh (test-bridges 154/154,
> parity, gates, content-guard…). Spike phase 04 xem `findings.md` —
> codex → kịch bản A, còn lại → B (devin cần verify trên máy thật).
> Còn lại duy nhất: checklist ops — nộp `dist/troly-ext-*.zip` lên
> Chrome Web Store (việc của chủ, không phải code).
> Khoảng trống đã biết: stderr não đường sandbox Windows (C# AgentSpawn
> vẫn dup stderr → NUL) — card lỗi vẫn có nhưng tail rỗng.

# UX polish — khởi động gọn & lỗi nói tiếng Việt

## Bối cảnh

Audit so với báo cáo nâng cấp bên ngoài cho thấy phần "giấu CLI" đã làm
một nửa ở hai đầu khác nhau:

| Đã có | Còn thiếu |
|---|---|
| `launcher.py` `terminal_enabled()` default TẮT; portal có toggle `term-toggle` → `config.terminal` | `start.bat`/`start.sh` spawn ttyd vô điều kiện; `start.bat` tự `winget install ttyd` |
| `spawn_brain()` chạy ngay khi bridge boot (đã pre-warm) | Lần gửi đầu vẫn có thể chờ handshake — đo trước khi tuyên bố xong |
| Card "não chưa cài" tiếng Việt khi `Popen` fail | `stderr` → `DEVNULL`: OAuth hết phiên, crash khởi động… não chết mà không biết tại sao |
| Onboarding web: folder quyền + chọn/cài não | Đăng nhập não vẫn = "Mở terminal đăng nhập" — cửa sổ lệnh trước mặt người không biết code |
| `dist/troly-ext-0.2.zip` sẵn sàng cho Web Store | Chưa nộp — SETUP.md vẫn bắt bật Developer mode + Load unpacked |
| `session/new` có sẵn trong handshake ACP | Không có nút "Việc mới" — muốn hội thoại sạch phải restart cả app |
| Nút Chat/Terminal đã giấu khi `terminal=false` | `chat.html` vẫn `padding-bottom:52px` + pill `#chat-modebar` rỗng vẫn render → khoảng trống chết dưới input (ảnh chủ 27-11) |
| `session/cancel` trong spec ACP | Không nút Dừng — não chạy sai chỉ có cách chờ hoặc restart app |
| `/api/reveal` mở Finder/Explorer có sẵn | Đường dẫn file trong tin nhắn không bấm được; học viên tự mò folder |
| AGENTS.md bảo "chụp màn hình dán vào chat" | Textarea không nhận ảnh — không có đường đưa ảnh vào prompt |
| `/api/pick-folder` + `/api/reveal` | **macOS-only (osascript)** — định hướng Windows-first mà Windows phải gõ path tay; walkthrough nút "Mở folder" chết êm trên Windows |
| `config.language` chọn ở onboarding | Không đường đổi sau — Settings thiếu toggle ngôn ngữ |
| `send()` không check `res.ok` + nút disabled lúc busy | Gõ Enter lúc não đang làm bị nuốt êm; prompt 409 (tab khác) treo không báo |
| `send_error` mặc định của serve.py | Trang 404 tiếng Anh trần trước mặt học viên (F-017 từng gặp) |
| `.logs/` đầy đủ cho debug | Học viên không có đường gói nhật ký gửi khi báo lỗi |

## Mục tiêu

Người dùng cá nhân mở app → chỉ thấy portal + chat, não đã ấm, lỗi gì
cũng đọc được bằng lời thường kèm nút xử lý. Không cửa sổ lệnh nào
hiện ra ngoài ý muốn.

## Phase

| Phase | Việc | Phụ thuộc |
|---|---|---|
| 01 | `start.bat`/`start.sh` tôn trọng `config.terminal` — không spawn/không cài ttyd khi Terminal tắt | — |
| 02 | Nút **"Việc mới"** trong chat → `session/new` (hoặc respawn não nếu não không nhận session thứ hai) | — |
| 03 | Đọc stderr của não → dịch lỗi quen thuộc thành card tiếng Việt kèm nút xử lý; `CREATE_NO_WINDOW`/console cho bản đóng gói Windows | — |
| 04 | **Spike**: não nào (devin/gemini/codex/claude) đăng nhập được qua trình duyệt tự quay về? → quyết đổi bước OAuth trong onboarding | 03 (stderr đã đọc được) |
| 05 | Đánh bóng khung chat: hết khoảng trống chết, nút Dừng (`session/cancel`), dán ảnh, slash-menu skill, reveal-link file, card perm replay mờ, cuộn không giật | — (riêng `/api/skills` có thể gộp với endpoint của trust-harness phase 02) |
| 06 | **Windows parity**: `FolderBrowserDialog` cho `/api/pick-folder` + `explorer /select` cho `/api/reveal` — vá đúng hướng B2C-Windows | — |
| 07 | Portal polish: đổi ngôn ngữ trong Cài đặt, xếp-1-tin khi busy + check `res.ok`, trang lỗi êm, nút gói nhật ký hỗ trợ | 06 (support-bundle cần reveal chạy trên Windows) |
| — | *Checklist ops*: nộp `dist/troly-ext-*.zip` lên Chrome Web Store (unlisted trước) | — |

Chi tiết: `phase-01-start-scripts.md`, `phase-02-viec-moi.md`,
`phase-03-stderr-cards.md`, `phase-04-oauth-browser-spike.md`,
`phase-05-chat-polish.md`, `phase-06-windows-parity.md`,
`phase-07-portal-polish.md`.

## Rủi ro chính

| Rủi ro | Giảm |
|---|---|
| `session/new` thứ hai trên cùng process ACP bị não từ chối | Phase 02 thử trước; fallback = respawn não (đường `spawn_brain` có sẵn, mất vài giây) |
| Đọc stderr làm rò rỉ log nhạy cảm vào history | Chỉ parse pattern lỗi đã biết → card; stderr thô chỉ ghi `.logs/brain-stderr.log` (đã gitignore), không đưa vào `chat-history.jsonl` |
| `console=False` trong troly.spec làm mất log boot của exe | Log launcher đã ghi `.logs/` từ trước — kiểm trên VM Win11 trước khi đổi |
| OAuth browser phụ thuộc từng não | Đó là lý do phase 04 là spike, không phải commit |

## Ra ngoài phạm vi

- Checkpoint/hoàn tác, verify skill, quyền 15 phút → plan `trust-harness`.
- Macro không LLM → plan `no-llm-macro`.
- `uia-bridge` → plan `silent-worker` (đã có).
