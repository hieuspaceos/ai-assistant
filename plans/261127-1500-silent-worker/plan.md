---
title: "Silent worker — trợ lý làm việc trong im lặng: cửa sổ agent riêng (không nhảy tab), CDP input nền, uia-bridge cho app native (Windows), kênh /api/notify báo việc xong"
description: "Hiện trạng: extension DOM events đã im lặng nhưng nhóm t* và screenshot gọi tabs.update(active:true) → giật tab lên trước mặt học viên; computer-use tầng OS chiếm hẳn chuột+màn hình. Mục tiêu: mọi việc web chạy trong một cửa sổ Chrome riêng của trợ lý (focused:false, cùng profile → giữ phiên đăng nhập), input 'thật' bắn vào tab nền qua CDP + Emulation.setFocusEmulationEnabled, screenshot qua Page.captureScreenshot (không cần active). App native Windows có 'uia-bridge' — bản ext-bridge cho UI Automation, chỉ dùng Invoke/Value pattern (không di chuột, không SetFocus). Xong việc → POST /api/notify → toast portal + toast OS. Phase 0 là spike go/no-go trước khi commit hướng."
status: draft
priority: P1
effort: L
branch: main
tags: [extension, bridge, windows, ux, uia, notify]
created: 2026-11-27
---

# Silent worker — trợ lý làm việc trong im lặng

## Bối cảnh

Khiếu nại của chủ: "AI xài thì user không xài được — mất chuột, mất màn
hình". Phân tách kỹ thuật hiện trạng (đã audit code):

| Đường điều khiển | Có chiếm máy không |
|---|---|
| DOM events (`click`/`type`/`scroll`/`key`/`paste`/`read`...) | Không — hoàn toàn nền |
| Nhóm `t*` (`tclick`/`ttype`/`tinsert`/`tkey`/`tmove`/`tright`) qua CDP `Input.*` | Không chiếm chuột OS, NHƯNG `chrome.tabs.update(active:true)` trong mọi handler → **giật tab lên trước mặt** |
| `screenshot` (`captureVisibleTab`) | **Giật tab** — API chỉ chụp được tab đang active |
| `open` | Mở tab `active:true` trong cửa sổ học viên đang nhìn |
| Computer-use tầng OS (native app) | **Chiếm chuột + màn hình** — vấn đề nặng nhất |

Kết luận: vấn đề web-side là **hành vi code**, không phải giới hạn
platform — `Input.dispatch*` và `Page.captureScreenshot` đều chạy được
trên tab nền. Vấn đề OS-side mới cần cơ chế mới (UIA).

## Mục tiêu (theo lời chủ)

1. Gọn nhất — không thêm daemon nặng, tái dùng pattern ext-bridge.
2. Không nhảy tab lên giữa màn hình — mọi thao tác nền.
3. Xong việc → bắn notification cho user.

## Kiến trúc đích

```
                    ┌─ cửa sổ Chrome "agent" (focused:false, 1 window riêng)
   agent ──HTTP──▶ ext-bridge :7684 ──WS──▶ extension ──┤   cùng profile → giữ login
                    └─ DOM actions + t* (không activate)

   agent ──HTTP──▶ uia-bridge :7685 ──▶ Windows: UI Automation
                    Invoke/Value only —            macOS: Accessibility API (AX)
                    không chuột, không SetFocus

   agent ──POST /api/notify──▶ chat-bridge :7682 ──▶ toast portal (long-poll có sẵn)
                                                 ──▶ OS toast (PS toast XML / osascript)

   computer-use OS-level = fallback cuối, chỉ khi cả 3 đường trên bó tay,
   và skill phải báo học viên trước.
```

## Phase

| Phase | Việc | Phụ thuộc |
|---|---|---|
| 00 | **Spike go/no-go** (trước khi build): (a) `Input.*` + `Emulation.setFocusEmulationEnabled` trên tab nền có gõ được Zalo `#richInput` và Sheets grid không; (b) `Page.captureScreenshot` trên tab nền; (c) `windows.create focused:false` + `tabs.update` có raise window không; (d) coverage nút bấm nền: UIA trên Win11 VM (UTM) — Zalo desktop, hộp thoại file, Notepad; AX trên mac — Finder dialog, Safari, Zalo macOS | — |
| 01 | Extension "agent window" + silent `t*`/`screenshot`/`open` | 00a–c |
| 02 | `tools/uia-bridge.py` (:7685, Windows) + package troly.spec | 00d |
| 03 | `/api/notify` (py+ps1 parity) → toast portal + OS toast; cập nhật skills + AGENTS.md + tests | 01 (tận dụng), song song được với 02 |

Chi tiết từng phase: `phase-01-agent-window.md`, `phase-02-uia-bridge.md`,
`phase-03-notify-rollout.md`. Audit chéo với code: `audit.md` — 4 vá đã
ghép vào phase files (A1 throttle tab nền → spike 00e; A2 agentWinId
qua storage.session + marker page; A3 consent attach app; A4 guard
bấm nhầm cửa sổ học viên).

## Quyết định của chủ (đã chốt)

1. **Cửa sổ agent giữ lại luôn** — tạo một lần, tái dùng phiên đăng
   nhập; học viên đóng tay được, lần sau tự tạo lại.
2. **uia-bridge làm cả Windows + macOS** — chủ code trên mac và có máy
   ảo Windows 11 (UTM) để test. Windows = đường UIA; macOS = đường
   Accessibility API (AX) qua pyobjc, cùng API shape.
3. **Nút không bấm nền được** → báo lỗi thẳng thắn, không lén rơi về
   chuột thật. Danh sách cụ thể loại nút nào: bảng trong
   `phase-02-uia-bridge.md` mục "Nút nào bấm nền được / không được".
4. **Banner "đang gỡ lỗi"**: MV3 không tắt được — nhưng nó chỉ hiện trong
   cửa sổ agent, không phải cửa sổ học viên. Chấp nhận.

## Rủi ro chính

| Rủi ro | Giảm |
|---|---|
| CDP input tab nền không được một số app (check `document.hasFocus` trước khi đã emulate) | Spike 00a trước; fallback: giữ đường activate cũ cho tab ngoài cửa sổ agent |
| `tabs.update(active:true)` trong cửa sổ nền vẫn raise cửa sổ trên một số Windows | Spike 00c; vá: `windows.update(focused:false)` đẩy lại sau activate |
| Electron app (Zalo desktop) expose UIA kém → uia-bridge "mù" | Spike 00d đo trước; thực tế hầu hết việc Zalo qua Zalo **Web** nên blast radius nhỏ |
| Banner debugger + cửa sổ lạ làm học viên hoang mang | Onboarding/AGENTS giải thích "cửa sổ của trợ lý — đừng đóng"; title/pinned gợi ý |
| Portal XSS qua nội dung notify | Render `textContent`, strip control chars, giới hạn độ dài — notify là **dữ liệu, không phải lệnh** |

## Ra ngoài phạm vi

- Child session / Windows Sandbox / cloud browser — lưu cho tier B2B
  (docs/fleet.md), không hợp máy học viên cá nhân.
- Computer-use fallback vẫn giữ nguyên skill hiện có — chỉ hạ ưu tiên.
