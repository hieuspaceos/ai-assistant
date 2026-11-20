# ai-assistant — Troubleshooting Runbook

Sự cố đã gặp thật + cách xử lý. Cập nhật khi gặp lỗi mới.

## 1. Health check nhanh

```bash
curl -s http://localhost:8080/web/ | head -1        # portal sống
curl -s http://localhost:7682/api/health            # chat-bridge {"ok":true}
curl -s -X POST http://localhost:7684/api/browser \
  -d '{"action":"status"}'                          # ext-bridge {"connected":true}
```

Log: `.logs/{portal,chat-bridge,ext-bridge,ttyd}.log` dưới root.

## 2. Khởi động

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Portal không lên | port 8080 bị chiếm | `lsof -i :8080` (macOS) / `netstat -ano \| findstr 8080` (Win); xem `.logs/portal.log` |
| `{"connected":false}` mọi action | extension chưa nạp | Mở `chrome://extensions` → bật "Trợ Lý AI"; sau khi sửa `extension/*.js` → `{"action":"reload"}` |
| Chat không trả lời | não ACP chết / license / chưa đăng nhập | Chạy lệnh não tay (`brain.json` → `cmd`) xem lỗi; xem `.logs/chat-bridge.log`; bridge tự thử bật lại ở lượt gửi sau |
| Chat báo "không chạy được 'X'" | não `X` trong `brain.json` chưa cài | Panel ⚙ Cài đặt → Bộ não → chọn não khác; hoặc cài `X` rồi gửi lại |
| Đổi não mà chat vẫn não cũ | bridge chưa reload | `POST /api/brain` tự restart agent; kiểm `GET /api/health` → trường `brain` |
| Tab Terminal trống | ttyd chưa cài | Chế độ Chat vẫn dùng được; cài ttyd hoặc bỏ qua |

## 3. Extension / lái trình duyệt

| Triệu chứng | Xử lý |
|---|---|
| `No tab with id` | Tab bị đóng hoặc restart → `tabs` lấy ID mới, đừng giữ ID cũ |
| Extension từ chối trang | Trang hệ thống (`chrome://`, newtab, extensions page) không inject content.js được — mở trang web thường |
| `click`/`type` không ăn | App chặn event giả (Zalo, Sheets) → nhóm `t*`: `tclick`/`ttype`/`tinsert` (CDP) |
| Banner "đang gỡ lỗi" kẹt | `tdetach` tháo debugger |
| `screenshot` lỗi `MAX_CAPTURE_..._PER_SECOND` | Chrome giới hạn — `wait` vài giây rồi chụp lại |
| `styles`/`dom` trả ít phần tử | `styles sel=body depth=3` chỉ ~120 phần tử đầu — đo thêm từng section |
| Trang chặn bot | 4 nấc trong skill clone-trang: wait→đo lại, tự bấm checkbox, nhờ học viên bấm, đổi site |
| Tab hiện DOM cũ sau khi sửa file | `open` lại URL kèm `?v=N` chống cache (reload action có lúc không đổi DOM) |

## 4. Clone pipeline

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Accordion thiếu đáp án | Đo DOM tĩnh — chỉ panel đang mở có nội dung | Pha 1a: bấm từng control → `ref-states.md` |
| Menu clone bấm không đi đâu | Site nguồn là SPA/MPA nhiều route, dựng nhầm một trang | Pha 1b khảo sát trước; router băm |
| Section clone sáng thay vì tối | CSS nguồn dùng wrapper nền tối — DOM không nói ra | Audit nền bằng `ref-css` trước khi so |
| Chữ trắng trên nền trắng trong card | Card sáng kế thừa `color` của section tối | Gán lại `color` mực trong card |
| `clone-compare` báo hàng loạt "chỉ có ở nguồn" | Tên class clone ≠ nguồn | Gắn `data-cs-ref` rồi `harvest` thay vì so trực tiếp |
| `shot` báo >50% khác | Section nền là ảnh placeholder ≠ ảnh gốc | Bình thường — pixel-diff chỉ dùng cho khối ít ảnh |
| `PIL` not found | Không cần — clone-compare parse BMP tay qua `sips` | macOS only cho `shot`; styles/harvest chạy mọi nơi |

## 5. Viewer / lưu trang

| Triệu chứng | Xử lý |
|---|---|
| Lưu xong mất bản cũ | `chat-bridge` tạo `<file>.bak` trước khi ghi — **chỉ có sau khi restart bridge** với code mới; kiểm tra file `.bak` tồn tại |
| `save-page` bị 400 | Path phải là `.html` dưới `my-course/`, không `..` — đúng thiết kế sandbox |
| Viewer không sửa được phần tử | Phần tử thiếu marker `data-cs-*` — mở file, gắn marker đúng loại |
| Sửa xong muốn về bản cũ | Copy `<file>.bak` đè lên file chính |

## 6. Emergency

- **Bridge chết giữa chừng**: process không tự restart — chạy lại
  `start.sh`/`start.bat`; file đang sửa không mất (lưu trên đĩa).
- **Học viên sửa hỏng JSON** (`config/permissions/connections`):
  `load_json` có default → bridge không crash; sửa tay file về JSON hợp
  lệ theo mẫu trong `codebase-summary.md`.
- **File clone hỏng không mở được**: về `.bak`; kiểm tĩnh bằng
  `html.parser` đếm thẻ đóng/mở trước khi sửa tiếp.
