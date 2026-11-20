# Phase 3 — Não miễn phí trong onboarding

> **Status: code xong — chưa verify E2E với Gemini thật** (mục 3c vẫn cần
> một vòng chat `gemini --acp` qua bridge). Thêm giá trị `byok` ngoài
> `free`/`paid` cho opencode/goose — app miễn phí nhưng cần tự nối model,
> gọi "free" là quá lời.

## Mục tiêu

Học viên KHÔNG có sẵn subscription AI nào vẫn chọn được một não dùng
được ngay mà không trả tiền — gỡ rào cản kinh tế lớn nhất của sản phẩm.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/chat-bridge.py` | modify | `BRAIN_PRESETS` thêm trường `cost`; `/api/brain` trả cost trong preset list |
| `web/onboarding.html` | modify | bước chọn não: badge "miễn phí"/"trả phí", sort free lên đầu khi không não nào installed |
| `web/app.js` | modify | panel ⚙ Bộ não hiện badge cost tương tự |
| `site/` (landing) | modify | mục "não AI": nói rõ có lựa chọn miễn phí — trợ lý không bắt trả tiền |
| `SETUP.md` | modify | mục cài não: hai đường "miễn phí (Gemini)" / "đã có sẵn (Devin, Claude…)" |

## Chi tiết

### 3a. `BRAIN_PRESETS` — thêm `cost`

```python
{"id": "gemini", ..., "cost": "free",
 "desc": {"vi": "Miễn phí với tài khoản Google cá nhân — não gợi ý cho người mới",
          "en": "Free with a personal Google account — suggested brain for new users"}},
{"id": "devin", ..., "cost": "paid", ...},
# claude/codex/opencode/goose: "paid" hoặc "free" tuỳ thực tế lúc implement
```

`GET /api/brain` trả `cost` trong mỗi preset (cùng `installed` hiện có).

### 3b. Onboarding — ưu tiên free

- Sort preset: `installed` trước → `cost:"free"` trước → còn lại.
- Badge nhỏ cạnh tên não: "miễn phí"/"free" (xanh lá) hoặc "cần tài
  khoản trả phí" (xám).
- Nếu KHÔNG có não nào `installed`: preselect Gemini + hint dẫn trang
  cài (đã có cơ chế `install.url`/`install.hint`).
- Copy minh bạch: *"Trợ lý cần một não AI để suy nghĩ. Gemini dùng
  miễn phí theo chính sách hiện tại của Google; các não khác cần tài
  khoản trả phí của hãng."* — không hứa "miễn phí mãi mãi".

### 3c. Verify trước khi viết copy

- Kiểm quota free tier Gemini CLI tại thời điểm implement (đã từng có
  ~60 req/phút, ~1000 req/ngày với tài khoản cá nhân — con số đổi theo
  chính sách Google). Chỉ ghi "miễn phí" khi còn đúng.
- `gemini --acp` + đăng nhập tài khoản Google cá nhân: test một vòng
  chat thật qua bridge — skill `/phong-van` chạy được là đủ.

## Acceptance

- Máy sạch (chỉ có gemini CLI): onboarding chọn được Gemini, chat
  `/phong-van` chạy end-to-end
- `GET /api/brain` trả `cost` cho mọi preset
- Không chỗ copy nào hứa não miễn phí vĩnh viễn

## Rủi ro

- Google đổi chính sách free tier → copy đã né bằng "theo chính sách
  hiện tại".
- Gemini free tier yếu hơn não trả phí ở tác vụ dài (clone trang,
  sinh khoá học) → chấp nhận: mục tiêu là "vào được cửa", nâng não sau
  khi học viên thấy giá trị.
