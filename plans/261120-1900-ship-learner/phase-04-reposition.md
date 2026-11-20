# Phase 4 — Định vị lại: assistant-first

> **Status: xong** — README, site (đã deploy live), SETUP, PDR,
> web/index.html, app.js i18n đều lead "trợ lý làm việc thật". Verify
> live troly.hieuspace.com 20/11.

## Mục tiêu

Thông điệp ngoài cùng dẫn bằng **trợ lý làm việc thật** (giá trị hàng
ngày, giữ chân), khoá học tự sinh là differentiator — không còn lead
bằng "cỗ máy sinh khoá học" khiến người nghe tưởng đây là LMS.

## File động

| File | Action | Việc |
|---|---|---|
| `README.md` | modify | đoạn mở đầu viết lại; section "learner experience" lead bằng assistant, course là bước nó tự làm |
| `site/index.html` (landing) | modify | headline + hero copy theo hướng mới |
| `SETUP.md` | modify | đoạn giới thiệu đầu file |
| `docs/project-overview-pdr.md` | modify | Executive Summary đổi trật tự: assistant trước, course machine là cách nó onboard |
| `docs/extension-store-listing.md` | modify | mô tả listing nhấn "trợ lý làm việc" |
| `web/index.html` | modify | **surface lớn nhất plan gốc sót** — `<title>` + `brand-sub` + `hero-sub` đang lead "khoá học của riêng bạn"; đổi sang assistant-first |
| `web/onboarding.html` | modify | câu chào/welcome text nếu còn lead bằng khoá học |

## Chi tiết

### Thông điệp mới (chuẩn, mọi nơi bám theo)

- **vi**: *"Trợ lý AI làm việc thật trên máy bạn — đọc Zalo, cập nhật
  Sheet, xử lý file, dựng trang web. Và nó tự thiết kế một khoá học
  riêng để dạy bạn dùng nó."*
- **en**: *"An AI assistant that does real work on your machine — reads
  your chats, updates sheets, processes files, builds web pages. And it
  designs a personal course to teach you how to use it."*

### Checklist copy cần săn

- `README.md` L1-7 ("Not a pre-written course. This is a course-
  generating machine…") → viết lại mở bằng assistant; đoạn course
  machine giữ làm đoạn 2.
- Landing hero: headline + sub + CTA.
- SETUP mở đầu: câu "file này hướng dẫn cài…" thêm 1 câu định vị.
- PDR Executive Summary: trật tự hai câu đổi chỗ.
- Tagline trong `extension/manifest.json` `description` — giữ nguyên
  (đã đúng: "cánh tay của trợ lý").

### Nguyên tắc khi viết lại

- Kết quả trước, cơ chế sau: "đọc hết tin Zalo chưa đọc trong 30 giây"
  trước "extension lái trình duyệt".
- Không xoá phần course — nó là moat; chỉ đổi thứ tự kể.
- Giữ nguyên cấu trúc file/anchor/link — chỉ đổi lời.

## Acceptance

- Người đọc README/landing 15 giây trả lời được "nó là trợ lý làm
  việc", không nhầm thành "web bán khoá học"
- Không còn chỗ nào lead bằng "course-generating machine" ở surface
  đầu tiên (README, landing, SETUP)
- Mọi link/anchor cũ còn nguyên

## Rủi ro

- Viết lại copy mà lạc giọng ELI10 (đoán từ ngữ kỹ thuật vào tagline)
  — review theo `code-standards.md` mục phong cách.
