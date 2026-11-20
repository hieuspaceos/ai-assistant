# ai-assistant — API Reference

Ba endpoint group, tất cả bind `127.0.0.1`, JSON thuần, không auth
(trust boundary = loopback — xem `SECURITY.md`).

---

## 1. ext-bridge :7684 — lái trình duyệt (`tools/ext-bridge.py`)

```
POST http://localhost:7684/api/browser
{"action": "<action>", "tabId": <id>, ...params}
→ {"ok": true, ...} | {"ok": false, "err": "..."}
```

Extension kết nối `ws://localhost:7684/ws/ext` — `connected:false` nghĩa
là extension chưa mở/chưa nạp.

| action | params | Trả về |
|---|---|---|
| `status` | — | extension có nối không |
| `tabs` | — | danh sách tab `{id, url, title}` |
| `open` | `url` | `tabId` tab mới |
| `activate` | `tabId` | focus tab |
| `close` | `tabId` | đóng tab |
| `snapshot` | `tabId?` | cây phần tử có `ref` e1,e2… để bấm |
| `click` | `tabId?, ref\|text` | bấm theo ref hoặc chữ hiển thị |
| `type` | `tabId?, ref, text` | gõ vào ô |
| `scroll` | `tabId?, dy, sel?` | cuộn trang/vùng (`dy:-99999` về đầu) |
| `scrollables` | `tabId?` | vùng cuộn s1,s2… cho `scroll sel=` |
| `query` | `tabId?, sel, attr?` | text/attr của phần tử khớp selector |
| `read` | `tabId?, sel?` | toàn văn trang đã lọc gọn |
| `fetch` | `tabId?, url` | tải URL bằng phiên của tab (đọc được sheet private) |
| `key` | `tabId?, sel?, ref?, key` | Enter/Tab/Escape/Delete/mũi tên |
| `paste` | `tabId?, sel?, text` | dán text/TSV qua clipboard |
| `rect` | `tabId?, sel\|ref` | toạ độ tâm phần tử |
| `dom` | `tabId?, sel?` | HTML sống đã render (toàn trang hoặc vùng) |
| `styles` | `tabId?, sel, deep?, depth?` | computed style + box (~120 phần tử đầu khi deep) |
| `assets` | `tabId?` | ảnh, SVG, font, link CSS, background-image |
| `css` | `tabId?` | nội dung stylesheet (rule đầy đủ; `blocked` → fetch href) |
| `screenshot` | `tabId?` | chụp tab → đường dẫn file `.shots/` |
| `wait` | `tabId?, ms` | chờ (tối đa 5s) |
| `reload` | — | nạp lại extension sau khi sửa code |

**Nhóm t* — input THẬT qua CDP** (app chặn event giả như Zalo #richInput,
grid Google Sheets):

| action | Dùng khi |
|---|---|
| `tclick` `sel\|ref\|x,y` | click giả không ăn |
| `tright` | mở context menu |
| `tmove` | hover lộ nút/menu ẩn |
| `ttype` `sel\|ref, text` | gõ vào editor phức tạp |
| `tinsert` `text, mode?` | chèn tại con trỏ; `mode=char` ghi vào grid Sheets |
| `tkey` `key, modifiers?` | phím thật (`modifiers:4` = Cmd/Ctrl) |
| `tdetach` | tháo debugger, tắt banner "đang gỡ lỗi" |

Lưu ý: `screenshot` dính `MAX_CAPTURE_..._PER_SECOND` của Chrome — đợi
vài giây chụp lại, đừng bỏ ảnh (ảnh là chuẩn so của clone-pipeline).

---

## 2. chat-bridge :7682 — portal chat + quản trị (`tools/chat-bridge.py`)

Body limit: 1 MB mặc định, **8 MB riêng `/api/save-page`** (trang clone
có ảnh base64).

### GET

| Path | Trả về |
|---|---|
| `/api/health` | `{"ok":true}` |
| `/api/poll` | output mới từ session `devin acp` (chat.html poll) |
| `/api/permissions` | nội dung `permissions.json` |
| `/api/connections` | nội dung `connections.json` |
| `/api/config` | nội dung `config.json` |

### POST

| Path | Body | Tác dụng |
|---|---|---|
| `/api/prompt` | `{text}` | gửi prompt vào `devin acp` |
| `/api/respond` | `{id, optionId}` | trả lời câu hỏi agent đang hỏi (`__cancel__` = huỷ) |
| `/api/delete-lesson` | `{folder}` | xoá bài + gỡ khỏi manifest |
| `/api/save-page` | `{file, html}` | ghi `.html` **chỉ dưới `my-course/`**; tự tạo `<file>.bak` trước khi ghi đè; chặn `..` |
| `/api/permissions` | `{path, access, note?}` | thêm folder được phép (`read`/`read-write`) |
| `/api/remove-permission` | `{path}` | gỡ quyền |
| `/api/connections` | `{app, ...}` | cập nhật trạng thái kết nối app |
| `/api/remove-connection` | `{id}` | gỡ kết nối |
| `/api/secrets` | `{app, fields}` | lưu field bí mật (ô `secret:true` trong connections) |
| `/api/setup` | `{language, learner_name, ...}` | onboarding: ghi config, cài skill pack đúng ngôn ngữ |
| `/api/check-connection` | `{id}` | probe trạng thái app (http/tabs) |

---

## 3. serve :8080 — static file server (`tools/serve.py`)

Không có API — chỉ GET file tĩnh. Đặc điểm:

- Chặn đường dẫn chứa dotfiles (`.devin`, `.git`) — secrets của học viên
  nằm trong `.devin/`, không được lộ ra HTTP.
- `GET /web/` → portal · `/my-course/trang-*.html` → file clone ·
  `/web/clone-view.html?src=/my-course/<file>.html` → viewer sửa trang.

## 4. ttyd :7681 — terminal (tuỳ chọn)

`ttyd -p 7681 -i 127.0.0.1 -W devin` — websocket terminal, portal nhúng
qua iframe. Không có HTTP API cho agent.
