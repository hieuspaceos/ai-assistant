# ai-assistant — Clone Pipeline (`/clone-trang` + `/trang-moi`)

Tài liệu kỹ thuật của cụm tính năng lớn nhất hệ thống. Source of truth
cho quy trình: `.devin/skills/clone-trang/SKILL.md` — doc này mô tả
kiến trúc và contract, không thay skill.

## Mục tiêu

Học viên thấy một trang đẹp → muốn "một trang giống y chang nhưng là của
mình". Kết quả: một file `.html` tự chạy trong `my-course/`, **giống hệt
về khung** (bố cục, màu, font, khoảng cách, hiệu ứng) còn **nội dung là
của học viên** — sửa được tại chỗ trong viewer của portal.

## Pipeline 6 nhịp

```
0. Chuẩn bị      hỏi link + nội dung học viên, ngôn ngữ site, kiểu ảnh
                 placeholder; tạo clone-work/<slug-site>/
1. Đo trên trang sống   qua extension: dom, styles, assets, css,
                 screenshot + ref-shot-<anchor>.png (site một trang)
1a. Trạng thái   bấm TỪNG accordion/tab/dropdown/modal → ref-states.md
                 (DOM tĩnh không chứa panel đang đóng)
1b. Kiến trúc    landing / SPA hash-route / MPA; gom link kể cả trong
                 submenu; đo dom+shot TỪNG route → ref-dom-<route>.*
2. Tokens        ref-styles + ref-css → tokens.md (màu, type scale,
                 spacing, radius, shadow — "DNA" của trang)
3. Dựng          MỘT file .html, CSS nhúng, theo KHUNG CHUẨN + markers;
                 JS tự viết cho hiệu ứng thấy được; title/favicon = của
                 học viên; router băm nếu nhiều route
4. So & sửa      audit nền → kiểm tĩnh → so từng route/anchor →
                 clone-compare.py → trạng thái tương tác → mobile.
                 Tối đa 4 vòng, ghi lại phần chưa đạt
5. Giao          mở trong clone-view.html, hướng dẫn Sửa nội dung → Lưu
```

## Marker contract — `data-cs-*`

Bên ngoài file clone giống trang mẫu; bên trong tuân một contract duy
nhất để viewer/agent/`trang-moi`/compare-tool nhận diện đồng nhất.

| Marker | Gắn trên | Ai dùng, để làm gì |
|---|---|---|
| `data-cs` | mỗi `<section>` lớn | Tên khối hiển thị khi hover trong viewer |
| `data-cs-type` | mỗi `<section>` | Loại khối — **từ vựng mở** (`nav hero features content gallery pricing faq testimonial cta form blog post footer misc` + slug tự đặt: `slider team stats map…`) |
| `data-cs-text` | h1/h2/p/li/span… | Bấm → sửa chữ tại chỗ |
| `data-cs-img` | `<img>` | Bấm → đổi ảnh + alt |
| `data-cs-link` | `<a>`/nút | Bấm → sửa chữ nút + href |
| `data-cs-bg` | khối có nền | Bấm → đổi màu/ảnh nền |
| `data-cs-page` | `<div>` bọc sections một route | Router băm hiện/ẩn trang |
| `data-cs-template` | trang chi tiết mẫu | "Khuôn" để `/trang-moi` nhân bản — **từ vựng mở** (`post tour product recipe…`), đúng MỘT cái mỗi loại |
| `data-cs-ref` | section + phần tử lớn | Selector nguồn tương ứng (`el` trong ref-styles.json) — `clone-compare.py harvest` khớp đúng phần tử |

Design tokens bắt buộc là CSS variable trên `:root` (`--cs-font`,
`--cs-primary`, `--cs-bg`, `--cs-radius`, `--cs-gap`…) — không rải giá
trị rời.

## Site nhiều route → router băm trong một file

```html
<header data-cs data-cs-type="nav">…menu trỏ #/route như site gốc…</header>
<main>
  <div data-cs-page="/">…sections trang chủ…</div>
  <div data-cs-page="/gioi-thieu">…</div>
</main>
```

Router ~20 dòng tự viết: đọc `location.hash` → hiện `data-cs-page`
khớp (`#/a`→`/a`, mặc định `/`) → ẩn phần còn lại → `is-active` menu →
scroll đầu trang hoặc tới `id` khi hash dạng `#/route#id`.

- Trang con không clone (`#/blog/<slug>`) → khớp cha gần nhất (`/blog`).
- Route cấp 1 chưa clone (site quá nhiều route) → link trỏ URL thật của
  site gốc — trung thực hơn là rơi về trang chủ.

## clone-view.html — viewer sửa tại chỗ

`http://localhost:8080/web/clone-view.html?src=/my-course/<file>.html`

Trang hiện toàn màn hình trong portal + thanh công cụ:

- **Sửa nội dung** → bấm vào phần tử có marker → chỉnh ngay (text
  inline, ảnh, link, nền, khối).
- **Lưu lại trang** → `POST :7682/api/save-page` → bridge tạo `.bak`
  rồi ghi file (sandbox: chỉ `.html` dưới `my-course/`).
- **Tải về máy** → xuất file serialize hiện tại.

File clone KHÔNG nhúng script sửa — viewer inject khi render, nên file
đứng một mình vẫn sạch.

## /trang-moi — thêm trang chi tiết sau clone

"Viết thêm bài blog/tour/sản phẩm" → skill quét `my-course/*.html` tìm
`data-cs-template`:

1. Nhiều site có template → **hỏi site nào** (không đoán).
2. Nhân bản khối `data-cs-page` của template → slug mới từ tiêu đề.
3. Đổ nội dung vào `data-cs-text/img`; **xoá `data-cs-template`** khỏi
   bản mới (template chỉ một).
4. Copy card đầu listing → sửa → chèn lên đầu grid.
5. Kiểm tĩnh sau chèn (đếm template vẫn 1, route parse được) → mở
   viewer ngay trang mới.

## tools/clone-compare.py — so tự động (pha 4)

```
python3 tools/clone-compare.py harvest <clone.html> <tabId> [-o out.json]
    → đo styles mọi phần tử data-cs-ref trên tab clone qua bridge
python3 tools/clone-compare.py styles <ref-styles.json> <clone-styles.json>
    → từng chỗ lệch px>2 / rgb>8 + phần tử chỉ có một bên
python3 tools/clone-compare.py shot <ref.png> <clone.png>
    → % pixel khác qua sips (macOS, không cần Pillow); chỉ dùng cho
      khối ít ảnh — section nền là ảnh khác nhau thì % cao là đương nhiên
```

Bridge mặc định `http://127.0.0.1:7684`, đổi bằng `--bridge` hoặc env
`BROWSER_BRIDGE`.

## clone-work/<slug-site>/ — số liệu đo

MỖI SITE MỘT FOLDER — site sau không ghi đè site trước. Nội dung:

| File | Từ action |
|---|---|
| `ref-dom.html`, `ref-dom-<route>.html` | `dom` |
| `ref-styles.json` | `styles` body depth=3 + TỪNG section |
| `ref-css/` | `css` |
| `ref-assets.json` | `assets` |
| `ref-shot*.png` | `screenshot` (đầu trang + từng anchor/route) |
| `ref-states.md` | tay — nội dung sau khi bấm control (1a) |
| `tokens.md` | pha 2 — DNA trang |

Giữ lại sau khi giao — lần sau chỉnh tiếp/clone thêm route không phải
đo lại.

## Luật bản quyền (cứng)

- ĐƯỢC giống hệt: layout, màu, font, spacing, radius, shadow, cấu trúc,
  kiểu icon, hiệu ứng.
- KHÔNG mang sang: chữ nguyên văn, ảnh, logo, tên thương hiệu, title/
  favicon. Ngoại lệ tạm: giữ chữ nguồn để đối chiếu kỹ thuật ở pha 4 —
  giao phải thay + báo phần còn là chữ mẫu.
- Icon kỹ thuật (mũi tên, check, social) tái dùng SVG được; icon logo
  thì không.
- Backend (form lưu data, giỏ hàng, đăng nhập) = khung giả lập — báo
  thẳng học viên.

## Bẫy đã gặp (vì sao pipeline như hiện tại)

| Bẫy | Bài học ghi vào skill |
|---|---|
| Đo DOM tĩnh → accordion chỉ 1/9 đáp án | Pha 1a bấm từng control → ref-states.md |
| Coi SPA 7 route như một trang | Pha 1b khảo sát kiến trúc trước khi dựng |
| So chỉ đầu trang → 4 section sau sai nền | Pha 4 so TỪNG route/anchor + audit nền bằng CSS trước |
| Style-diff nhiễu vì khác tên class | `data-cs-ref` + harvest |
| `styles` body depth=3 không tới section cuối | Đo thêm từng section |
| Menu "Liên hệ" chưa clone rơi về trang chủ | Route cấp 1 chưa clone → link URL thật |
| Sửa hỏng trong viewer mất bản gốc | `.bak` trước khi ghi đè |
