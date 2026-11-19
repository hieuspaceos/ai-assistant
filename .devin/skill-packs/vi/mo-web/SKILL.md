---
name: mo-web
description: Điều khiển trình duyệt THẬT của học viên qua extension "Trợ Lý AI" — mở trang, đọc nội dung, bấm nút, gõ chữ, chụp màn hình. Dùng khi cần Zalo Web, Outlook web, WordPress admin, hoặc trang bất kỳ đang đăng nhập sẵn trên máy họ.
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

Trợ Lý AI có một "cánh tay" trong trình duyệt của học viên: extension đã
cài sẵn, nói chuyện với máy qua `http://localhost:7683`. Dùng nó khi việc
nằm trên một trang web — đặc biệt trang học viên ĐÃ đăng nhập (Zalo,
Outlook, wp-admin...) vì browser này giữ sẵn phiên đăng nhập của họ.

## Kiểm tra trước khi dùng (bắt buộc)

```
curl -s http://localhost:7683/api/browser/status
# hoặc PowerShell: Invoke-RestMethod http://localhost:7683/api/browser/status
```

- `{"connected": true}` → dùng được.
- `{"connected": false}` → DỪNG, nói với học viên bằng lời thường: *"mình
  cần cái nút Trợ Lý AI trong trình duyệt để giúp việc này. Bạn mở Chrome
  (hoặc Edge) lên, nếu góc trên bên phải có hình mũ tốt nghiệp màu xanh là
  xong. Chưa có thì mình hướng dẫn cài — mất khoảng 2 phút."* Rồi dẫn họ
  theo mục "Cài extension" trong SETUP.md. Không bao giờ tự ý bỏ qua bước
  này rồi làm cách khác trong lặng lặng.

## Cách ra lệnh

Mọi lệnh là một POST JSON về `http://localhost:7683/api/browser`:

```
curl -s -X POST http://localhost:7683/api/browser -d '{"action":"<action>", ...}'
# PowerShell:
# Invoke-RestMethod -Method Post http://localhost:7683/api/browser `
#   -Body '{"action":"tabs"}' -ContentType 'application/json'
```

| Action | Tham số | Làm gì |
|---|---|---|
| `tabs` | — | Liệt kê các tab học viên đang mở (id, title, url) |
| `open` | `url` | Mở tab mới, trả `tabId` |
| `activate` | `tabId` | Chuyển tới tab |
| `close` | `tabId` | Đóng tab (hỏi học viên trước nếu là tab của họ) |
| `snapshot` | `tabId?` | Đọc "cây phần tử" của trang — mỗi nút/ô có ref `e1`, `e2`... |
| `click` | `tabId?`, `ref` hoặc `text` | Bấm phần tử theo ref, hoặc theo chữ hiển thị (site dùng div như Zalo/FB) |
| `type` | `tabId?`, `ref`/`sel`, `text` | Gõ chữ vào ô (xóa nội dung cũ trước) |
| `key` | `tabId?`, `ref`/`sel`, `key` | Gửi phím Enter/Tab/Escape/Delete/mũi tên — app thường nhận được, grid canvas của Sheets thì KHÔNG |
| `paste` | `tabId?`, `sel?`, `text` | Dán text/TSV như thao tác dán — chỉ tác dụng với app nhận sự kiện giả, Sheets grid KHÔNG nhận |
| `scroll` | `tabId?`, `dy`, `sel?` | Cuộn trang `dy` pixel; có `sel` thì cuộn vùng đó (khung chat, bảng). `dy` âm = cuộn lên. Trả `atTop`/`atBottom` để biết khi dừng |
| `scrollables` | `tabId?` | Liệt kê các vùng cuộn được trong trang → ref `s1`, `s2`... dùng với `scroll` `sel=sN` |
| `query` | `tabId?`, `sel`, `attr?` | Lấy chữ của mọi phần tử khớp CSS selector; có `attr` thì lấy thuộc tính (src, href) |
| `read` | `tabId?`, `sel?` | Lấy toàn văn nội dung trang (hoặc một vùng), đã lọc, tối đa ~8000 chữ |
| `fetch` | `tabId?`, `url` | Tải URL bằng phiên đăng nhập của tab (cùng origin) — đọc được trang/file private, vd CSV Google Sheets qua `gviz/tq?tqx=out:csv` |
| `screenshot` | `tabId?` | Chụp tab → trả `file` (đường dẫn PNG để đọc lại) |
| `wait` | `tabId?`, `ms` | Chờ trang tải (tối đa 5 giây/lần) |
| `reload` | — | Nạp lại extension sau khi sửa code — tự kết nối lại |
| `tclick` | `tabId?`, `sel`/`ref` hoặc `x`,`y` | **Click chuột THẬT** (qua CDP) — dùng khi app bỏ qua click giả (Zalo, FB, editor khó tính). Tab sẽ được đưa lên trước |
| `tright` | giống `tclick` | **Chuột phải THẬT** — mở context menu của app |
| `tmove` | giống `tclick` | **Hover THẬT** — lộ nút/menu chỉ hiện khi rê chuột |
| `ttype` | `tabId?`, `sel`/`ref`, `text` | **Gõ chữ THẬT** — click thật vào ô rồi chèn text. Đường duy nhất gõ được vào editor Zalo (`#richInput`), có thể cả grid Sheets/Docs |
| `tinsert` | `tabId?`, `text`, `mode?` | **Chèn text THẬT** tại con trỏ đang đứng; `mode=char` bắn phím từng ký tự — ghi được vào grid Google Sheets (xem `/cap-nhat-sheet`) |
| `tkey` | `tabId?`, `sel`/`ref`?, `key`, `modifiers?` | **Nhấn phím THẬT** (Enter, mũi tên...); `modifiers` bitmask 4=Cmd/Ctrl |
| `tdetach` | `tabId?` | Tắt banner "đang gỡ lỗi" sau khi dùng xong nhóm `t*` |

Bỏ `tabId` = thao tác trên tab học viên đang nhìn.

## Nhịp làm việc chuẩn

1. `tabs` xem họ đang mở gì, hoặc `open` trang cần.
2. `wait` ngắn → `snapshot` để có ref các phần tử.
3. `click`/`type` theo ref → `wait` → `snapshot` lại (ref ĐỔI sau mỗi
   lần trang thay đổi — đừng dùng ref cũ của snapshot trước đó).
4. Kẹt → `screenshot` rồi đọc file ảnh để xem trang đang như thế nào.
5. `click`/`type`/`key` báo ok nhưng trang không đổi (chữ không vào ô,
   nút không nhận) → app đó check sự kiện thật → chuyển sang `tclick`/
   `ttype`/`tkey`. Xong nhớ `tdetach`. Nếu `t*` cũng không ăn (Sheets
   grid vẫn còn nghi) → báo học viên giới hạn đó, đừng thử bừa tiếp.
6. Báo lại cho học viên bằng lời thường, không dán JSON.

## Luật an toàn — không được phá

- **Gửi đi** = hành động có hậu quả ra ngoài: gửi tin Zalo, gửi email,
  đăng bài public, xoá nội dung. TRƯỚC khi `click` nút Gửi/Đăng/Xoá phải
  hỏi học viên: *"mình sắp bấm Gửi — tin này sẽ đi thật. Bạn đồng ý không?"*
  Được đồng ý mới bấm.
- Không `type` vào ô `password`, không đọc giá trị ô mật khẩu. Nếu trang
  đòi đăng nhập/captcha/2FA: dừng, nhờ học viên làm tay, bảo họ báo lại
  khi xong.
- Học viên đang dùng chung browser này — đừng đóng tab của họ (`close`)
  khi chưa hỏi; mở tab mới cho việc của mình.
- Trang hệ thống (`chrome://`, Web Store) không cho extension chạy — nếu
  lệnh báo lỗi "không cho extension chạy", giải thích cho học viên và
  chuyển hướng (mở trang khác).
