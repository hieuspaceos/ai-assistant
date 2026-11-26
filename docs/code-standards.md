# ai-assistant — Code Standards

Quy ước giữ cho codebase nhất quán. Nền tảng lớn nhất: **máy học viên
chỉ có Python chuẩn + PowerShell + browser** — mọi file mới phải chạy
được không cần cài thêm.

## Nguyên tắc nền

- **Không build step, không framework.** HTML/CSS/JS thuần cho portal và
  file clone; Python stdlib cho bridge/tool; PowerShell thuần cho bản
  Windows. Không npm/pip install trong code path của học viên.
- **Hai bản song song khi cần OS**: `*.py` cho macOS/Linux, `*.ps1` +
  `*.bat` cho Windows — cùng contract, cùng port.
- **Bind `127.0.0.1`** cho mọi server — không lộ ra LAN.
- **Ngôn ngữ**: code + tên file + key JSON = tiếng Anh; chữ hiển thị cho
  học viên + docs = theo `config.json → language` (mặc định `vi`).

## Phong cách nói với học viên (từ AGENTS.md)

- ELI10: mỗi khái niệm có phép so sánh đời thường trước (terminal = cửa
  sổ chat, skill = sổ công thức, folder = ngăn tủ).
- Cấm: "đơn giản thôi", "chỉ cần", "hiển nhiên", "dễ mà".
- Kết luận trước, chi tiết sau. Một lần một việc, một câu hỏi.
- Trước khi đụng file: nói bằng lời thường mình sắp làm gì + file gốc
  còn không.

## Python

- Stdlib only. Không pip install (Pillow, requests…) — nếu cần tính năng
  ngoài stdlib thì viết tay (xem `clone-compare.py` parse BMP thay
  Pillow) hoặc gọi tool có sẵn của OS (`sips`, `curl`).
- HTTP server: `http.server` + `ThreadingHTTPServer`; body limit có
  chủ đích (`/api/save-page` 8 MB vì ảnh base64, còn lại 1 MB).
- File JSON của học viên: đọc bằng helper `load_json` có default — file
  có thể bị học viên sửa tay, không crash vì JSON lỗi.

## JavaScript / HTML / CSS

- Không framework, không import ngoài trừ `web/vendor/` đóng gói sẵn.
- File clone: MỘT file tự chạy, CSS nhúng, JS tự viết cho hiệu ứng —
  không copy script trang mẫu (bẩn + tracking).
- Marker `data-cs-*` là contract — giữ đúng tên/ý nghĩa trong
  `clone-pipeline.md`; từ vựng `data-cs-type` và `data-cs-template` là
  **mở**, đặt slug mới khi cần nhưng phải mô tả đúng.

## Skill authoring

- Format frontmatter + checklist, xem `skills-system.md`.
- Ghi **bẫy thật đã gặp**, không viết lý thuyết — skill sống nhờ kinh
  nghiệm tích luỹ, mỗi lần clone/test lòi lỗi mới thì vá vào skill.
- `clone-trang` và `trang-moi` không nằm trong skill-packs (cài trực
  tiếp); skill đồng bộ pack thì sửa cả `skills/` lẫn `skill-packs/`.

## Rejection patterns — đừng làm

- ❌ Thêm dependency (npm package, pip, CDN script) vào code path học
  viên — máy họ không có môi trường dev.
- ❌ Framework/router/component library cho portal hay file clone.
- ❌ Tách file clone thành nhiều file — viewer sửa một file.
- ❌ Server bind `0.0.0.0` hay auth bằng cách "không ai biết port".
- ❌ Ghi file ngoài `workspace/` khi chưa có trong `permissions.json`.
- ❌ Log/in ra secrets, token, app password.
- ❌ Comment giải thích điều code đã nói — comment cho "tại sao", bẫy
  thật, số đo từ site nguồn.
- ❌ File `.cmd`/`.bat` đọc argv (`%1`) hay input không tin cậy — mọi
  expansion trong batch được re-parse nên ký tự `"` phá quote → `&`
  chạy lệnh (đã là lỗ hổng RCE của term-gate.cmd). Việc đó phải là
  `.ps1` (PowerShell không re-lex argv).
