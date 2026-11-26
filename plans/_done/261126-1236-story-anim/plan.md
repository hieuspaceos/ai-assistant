---
title: "Story animation thay sơ đồ vòng quay trên landing"
description: "Thay sơ đồ vòng tròn tĩnh trong section #vong-quay của site/index.html bằng một .story animation 4 scene + frame kết theo sketches/storyboard.md: 5 vai chọn được, mỗi vai một config, nhịp việc-dồn → giải-dồn → nhớ → tự-chạy. Pure CSS/JS, không build step, không dependency."
status: in-progress
priority: P2
effort: M
branch: main
tags: [site, landing, animation, positioning]
created: 2026-11-26
depends-on: reposition (phase-04 xong), sketches/storyboard.md (đã duyệt)
---

# Story animation trên landing

## Bối cảnh

Sơ đồ vòng tròn tĩnh trong `#vong-quay` kể đúng cơ chế nhưng người
xem thường không hiểu — cần "đoạn phim nhỏ". Kịch bản đã chốt trong
`sketches/storyboard.md` (5 vai × 4 scene + frame kết, ~22s play-once,
bản cắt 6s loop cho hero). B2B tách riêng (`storyboard-b2b.md`,
chưa làm ở đợt này).

## Thiết kế tổng thể

- **Một engine, data-driven**: `.story` render 5 scene từ object
  config per vai `{pains[], stake, tasks[], teachWord, memoryLine,
  recipe, payoffText, timeSaved, caption}`. Đổi vai = đổi data.
- **Hybrid Lottie + DOM**: đạo cụ/nhân vật generic (thông báo rớt,
  bot chạy, đồng hồ/lịch lật, người + cà phê) dùng file `.lottie`
  từ lottiefiles.com; nội dung kể chuyện (thoại tiếng Việt, danh sách
  hội thoại, stamp kết quả, sổ công thức) là DOM/CSS phủ lên vì
  chữ đổi theo vai. Chọn file line-art tối giản, nền trong suốt.
- **Vendor local, không CDN**: `@lottiefiles/dotlottie-wc` (~30KB)
  + các file `.lottie` đặt trong `site/assets/story/`. Kiểm chứng
  giấy phép "Lottie Simple License" (miễn phí, link credit trong
  comment nguồn file).
- **Play-once**: chạy một lần khi vào viewport, dừng ở frame kết +
  nút "Xem lại" + CTA. JS off → frame tĩnh Scene 2 (cú wow).
  `prefers-reduced-motion` → hiển thị tĩnh các frame quan trọng.
- **Giữ nguyên anchor** `#vong-quay`, caption, section xung quanh.

### Asset shortlist (xác minh khi phase 1)

| Scene | Cần | Ứng viên lottiefiles |
|-------|-----|----------------------|
| S1 | Thông báo rớt | `notification-bell-Vupmjurlrj`, `inbox-notification-G9b5nohvSy` (~2KB) |
| S2 | Bot chạy/robot làm | `robot-working-on-machine-analyzing-QvvT3yOx5T` (~24KB), `robot-assistant-1neurApak1` |
| S4 | Đồng hồ/lịch + người | tìm "calendar flip", "morning coffee person" — line-art |
| — | Player | `@lottiefiles/dotlottie-wc` vendor vào `assets/` |

## Phases

| # | Phase | Nội dung |
|---|-------|----------|
| 1 | Engine + assets | Vendor `dotlottie-wc` + chọn/tải `.lottie` (kiểm license, đổi màu về accent nếu được); `.story` stage, `.scene` + `.is-on` transition model, phase driver + timer, IntersectionObserver start, play-once + replay, reduced-motion/JS-off fallback |
| 2 | Scene art | CSS/DOM components chồng lên Lottie: đống việc + stake + lịch lật (S1), chuỗi ask→stamp (S2), bubble trí nhớ + recipe stamp vào sổ (S3), người + counter + kết quả sẵn (S4), frame kết |
| 3 | Vai + switcher | 5 config vai theo storyboard, nút "Bạn làm nghề gì?" đổi vai (reset + replay), mặc định marketing |
| 4 | Wire vào site | Thay `.loopwell` SVG trong index.html, giữ caption; thêm `site/story.css` + JS vào script cuối trang |
| 5 | Verify | Test mọi vai, timing ≤22s, fallback, Lottie không nặng trang, không vỡ layout mobile; bản cắt 6s hero = việc sau (riêng) |

## Rủi ro

- **Lottie lạc style** — giảm bằng: chỉ chọn line-art tối giản, chỉnh
  theme về màu accent khi tải; nếu file nào không hợp thì scene đó
  fallback vẽ CSS/SVG.
- **Quá phức tạp** — mỗi scene giữ tối đa ~6 phần tử động; cái nào
  rối thì đơn giản hoá.
- **Timing cảm xúc** — nhịp stamp ~2s/task cần chỉnh bằng mắt sau
  khi xem preview; constants tập trung một chỗ (--dur, per-scene
  hold) để tune nhanh.
- **Không vỡ khi chưa có scheduler** — S4 "tự chạy" là lời hứa đã
  chốt trong storyboard (feature phase sau); copy dùng đúng văn bản
  storyboard, không tự ý hạ.
