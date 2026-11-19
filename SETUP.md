# Cài đặt một lần — xong dùng mãi

File này hướng dẫn cài những thứ cần có trên máy Windows để học.
Chỉ làm **một lần duy nhất**. Kẹt bước nào cứ hỏi người phụ trách
hoặc chụp màn hình gửi họ.

> Máy công ty không cho cài phần mềm? Gửi file này cho IT, nhờ họ làm
> hộ — họ đọc sẽ hiểu ngay.

---

## Bước 1 — Cài "cửa sổ chat với máy tính" (Windows Terminal)

1. Mở **Microsoft Store** (bấm phím Windows, gõ "store").
2. Gõ tìm **Windows Terminal** → bấm **Get / Cài đặt**.
3. Hoặc nếu có `winget`: mở PowerShell, chạy
   `winget install Microsoft.WindowsTerminal`.

## Bước 2 — Cài "người giúp việc" (Devin CLI)

1. Bấm phím **Windows**, gõ `powershell`, Enter — một cửa sổ xanh/đen hiện ra.
2. Dán đúng dòng này vào rồi Enter:

   ```powershell
   irm https://cli.devin.ai/install.ps1 | iex
   ```

3. Chờ nó chạy xong, **đóng PowerShell, mở lại**.
4. Gõ `devin` → Enter. Trình duyệt sẽ mở trang đăng nhập — đăng nhập
   bằng tài khoản công ty cấp.

## Bước 3 — Cài thêm cho chế độ "Terminal" (ttyd, không bắt buộc)

`start.bat` tự thử cài ttyd qua winget lần đầu chạy — thường không cần
làm gì thêm. Muốn cài tay trước (hoặc lần đó winget lỗi), mở PowerShell:

```powershell
winget install --id tsl0922.ttyd -e
```

*(Tab "Hỏi trợ lý" có 2 chế độ: **Chat** dùng được ngay không cần cài
gì thêm; **Terminal** — dạng dòng lệnh cho ai muốn trải nghiệm CLI
thật — mới cần ttyd. Không cài thì bấm nút Terminal sẽ thấy hướng
dẫn thay thế.)*

## Bước 4 — Cài thêm để tạo video bài giảng (không bắt buộc)

Video hướng dẫn của mỗi bài được quay tự động lúc tạo khoá học.
Việc đó cần 2 thứ: **Python** (chương trình dựng phim) và **ffmpeg**
(chương trình ghép phim). Mở PowerShell, chạy lần lượt:

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Gyan.FFmpeg -e
```

*(Không cài thì khoá học vẫn tạo bình thường — chỉ là các bài không có
video, xem slide và hướng dẫn thay thế. Khi nào cài xong, nhờ trợ lý
"quay lại video cho bài X" là được.)*

## Bước 5 — Cài "cánh tay" trong trình duyệt (extension Trợ Lý AI, không bắt buộc)

Extension này là một nút nhỏ nằm trong trình duyệt của bạn. Nó giống
cánh tay của trợ lý vươn vào trang web bạn đang mở — nhờ nó, trợ lý
đọc được và thao tác trên Zalo Web, Outlook, trang quản trị website...
mà bạn KHÔNG phải đăng nhập lại.

Cần Python (đã cài ở Bước 4). Cài một lần:

1. Mở **Chrome** hoặc **Edge**, gõ vào thanh địa chỉ:
   `chrome://extensions` (Edge: `edge://extensions`)
2. Bật công tắc **Developer mode / Chế độ nhà phát triển** ở góc trên
   bên phải.
3. Bấm nút **Load unpacked / Tải tiện ích đã giải nén** → chọn folder
   `extension` nằm trong folder `ai-assistant` → bấm **Select Folder**.
4. Trên thanh công cụ xuất hiện icon mũ tốt nghiệp xanh. Bấm icon ghim
   (📌) để nó luôn hiện.

Kiểm tra: mở portal, hỏi trợ lý "bạn thấy trình duyệt của tôi không?" —
nếu icon hiện chữ **ON** màu xanh là đã kết nối.

*(Không cài thì trợ lý vẫn làm việc với file và folder bình thường —
chỉ là không chạm được vào trang web đang mở.)*

## Bước 5.5 — Cài thêm gói Python (không bắt buộc)

Cần cho skill Excel/Word (`/lam-excel`, `/lam-word`) và render video:

```
py -m pip install -r requirements.txt
```

Máy macOS/Linux: `python3 -m pip install -r requirements.txt`.

## Bước 6 — Mở khoá học

Vào folder `ai-assistant`, **double-click `start.bat`** (macOS/Linux:
`bash start.sh`).

**Lần đầu mở**: trang "thiết lập lần đầu" hiện ra — chọn ngôn ngữ →
điền tên → chọn folder trợ lý được đọc → chọn app muốn kết nối → xong.
Từ lần sau vào thẳng portal.

Trình duyệt sẽ mở trang web khoá học với danh sách bài bên trái.
Xong! Bấm tab **💬 Hỏi trợ lý**, gõ `/phong-van` để nó tạo khoá học
riêng cho bạn.

### Thông tin đăng nhập app (WordPress, Zalo OA...)

Trợ lý hỏi kết nối app nào thì ghi vào `.devin/secrets.local.json`
(file này đã được gitignore — không bao giờ lên git). **Đừng dán mật
khẩu/token vào ô chat** — ghi vào file theo hướng dẫn của trợ lý.

---

## Lỗi thường gặp

| Bạn thấy | Làm gì |
|---|---|
| `'devin' is not recognized` | Đóng hết PowerShell, mở lại. Chưa được thì cài lại Bước 2. |
| Không chạy được lệnh `irm` | Bạn đang ở CMD/Git Bash chứ không phải PowerShell. Gõ `powershell` trước. |
| `start.bat` báo thiếu devin | Làm lại Bước 2. |
| Tab Chat trống trơn | Đóng rồi mở lại `start.bat` — cửa sổ "Tro ly AI chat" chạy nền phải còn nguyên. |
| Chế độ Terminal trống | ttyd chưa chạy — chạy `tools\chat-terminal.ps1` trong PowerShell, hoặc dùng chế độ Chat. |
| Bài học không có video | Thiếu Python hoặc ffmpeg — làm Bước 4 rồi nhờ trợ lý quay lại. |
| Trợ lý bảo "không thấy trình duyệt" | Extension chưa cài hoặc trình duyệt chưa mở — làm Bước 5, mở Chrome/Edge lên. |
| Trang web không mở | Mở tay `http://localhost:8080/web/` trong trình duyệt. |

## Tắt/mở lại mỗi ngày

- **Tắt**: đóng các cửa sổ nền tên "Tro ly AI ..." (có thể tới 4 cái:
  portal, chat, terminal, browser) + tab trình duyệt.
- **Mở lại**: double-click `start.bat` — đăng nhập đã lưu sẵn.
