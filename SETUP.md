# Cài đặt một lần — xong dùng mãi

> **Cách nhanh nhất (khuyến nghị):** tải file `troly` từ trang phát hành
> → https://github.com/hieuspaceos/ai-assistant/releases/latest → chạy
> là xong. File tự dựng mọi thứ trong `~/TroLyAI` rồi mở portal — không
> cần Python, không cần các bước dưới.
> *(macOS: file `troly` · Windows: file `TroLyAI.exe` — lấy đúng file cho máy mình.)*
>
> **Lần đầu mở bị máy "chặn"?** File `troly` cho macOS đã ký số +
> notarize nên mở là chạy — không còn bước nào. Trên Windows có thể
> gặp màn hình xanh SmartScreen (file `.exe` chưa ký — cảnh báo bình
> thường, không phải virus): bấm **More info** rồi **Run anyway**.
>
> **Cập nhật sau này:** portal sẽ tự báo "Có bản mới" — bấm vào là ra
> trang tải. Tải file mới chạy đè là xong, công cụ và cài đặt giữ
> nguyên. Extension báo "bản cũ" thì xoá và Load unpacked lại.
>
> Các bước thủ công bên dưới dành cho máy dev hoặc khi chưa có file `troly`
> cho nền tảng của bạn.



File này hướng dẫn cài **Trợ lý AI** — một trợ lý làm việc thật trên
máy bạn (đọc Zalo, xử lý file, cập nhật Sheet…) và tự dạy bạn dùng nó
qua bộ công cụ riêng. Chỉ làm **một lần duy nhất**. Kẹt bước nào cứ
hỏi người phụ trách hoặc chụp màn hình gửi họ.

> Máy công ty không cho cài phần mềm? Gửi file này cho IT, nhờ họ làm
> hộ — họ đọc sẽ hiểu ngay.

---

## Bước 1 — Cài "cửa sổ chat với máy tính" (Windows Terminal)

1. Mở **Microsoft Store** (bấm phím Windows, gõ "store").
2. Gõ tìm **Windows Terminal** → bấm **Get / Cài đặt**.
3. Hoặc nếu có `winget`: mở PowerShell, chạy
   `winget install Microsoft.WindowsTerminal`.

## Bước 2 — Cài "não" cho trợ lý

Trợ lý cần một chương trình AI để suy nghĩ — gọi là "não". Lần chạy
đầu, trang hướng dẫn (onboarding) có sẵn nút **"Cài não này"** — bấm
một cái là trợ lý tự tải và cài, không cần gõ lệnh, không cần quyền
admin:

1. Chọn **Gemini CLI** — miễn phí với tài khoản Google cá nhân, gợi ý
   cho người mới (đã có tài khoản AI trả phí như Devin thì chọn não đó,
   cũng cài được bằng một nút).
2. Bấm **"Cài não này"** → để yên vài phút, trợ lý tự tải và cài.
3. Xong bấm **"Mở terminal đăng nhập não"** — một cửa sổ dòng lệnh mở
   ra, trình duyệt bật trang đăng nhập Google, đăng nhập xong quay lại
   bấm **"kiểm tra lại"** là dùng được.

*(Đường tay — chỉ khi cài tự động lỗi: nút **"hướng dẫn tay ↗"** trong
onboarding mở đúng trang của hãng. Windows: `winget install
OpenJS.NodeJS` rồi `npm install -g @google/gemini-cli` trong
PowerShell; macOS làm theo trang hãng. Não khác — Claude Code, Codex,
OpenCode, Goose — cài tay theo hãng rồi chọn trong ⚙ Cài đặt → Bộ não.)*

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

## Bước 4 — Cài Python (không bắt buộc, nhưng nên)

Trợ lý dùng Python cho nhiều việc lặt vặt (đọc Excel, nén ảnh, gọi
extension…). Mở PowerShell, chạy:

```powershell
winget install --id Python.Python.3.12 -e
```

*(Không cài vẫn dùng được — trợ lý sẽ tự tìm cách khác, chỉ chậm hơn
một chút.)*

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

**Icon hiện dấu `!`?** Extension đang chờ "mã kết nối". Thường thì chỉ
cần mở portal lên (bằng file `start`) là nó tự nhận mã. Không được thì
vào portal → ⚙ Cài đặt → mục **Mã kết nối** → bấm Sao chép → mở trang
options của extension (chuột phải vào icon → Options) rồi dán vào.

**Đã cài extension từ bản cũ (trước bản có "mã kết nối")?** Extension
giờ có ID cố định nên Chrome coi nó là tiện ích mới — vào
`chrome://extensions`, gỡ bản cũ, rồi "Load unpacked" lại folder
`extension` như trên.

*(Không cài thì trợ lý vẫn làm việc với file và folder bình thường —
chỉ là không chạm được vào trang web đang mở.)*

## Bước 5.5 — Gói Python cho skill Excel/Word (tự động)

Trợ lý tự cài các gói này vào môi trường riêng `.venv/` trong folder
dữ liệu mỗi lần mở app — bạn không cần làm gì. Chỉ khi skill báo thiếu
gói (máy offline lúc mở app lần đầu chẳng hạn), chạy tay:

```
python3 tools/ensure-deps.py     # Windows: py tools\ensure-deps.py
```

## Bước 6 — Mở portal

Vào folder `ai-assistant`, **double-click `start.bat`** (macOS/Linux:
`bash start.sh`).

**Lần đầu mở**: trang "thiết lập lần đầu" hiện ra — chọn ngôn ngữ →
điền tên → chọn folder trợ lý được đọc → chọn app muốn kết nối → xong.
Từ lần sau vào thẳng portal.

Trình duyệt sẽ mở portal với danh sách bài/công cụ bên trái.
Xong! Bấm tab **💬 Hỏi trợ lý**, gõ `/phong-van` để nó tạo bộ công cụ
riêng cho bạn — mỗi công cụ đi kèm một màn hướng dẫn từng-bước làm thật
(nút **▶ Dùng ngay**).

### Thông tin đăng nhập app (WordPress, Zalo OA...)

Trợ lý hỏi kết nối app nào thì ghi vào `.devin/secrets.local.json`
(file này đã được gitignore — không bao giờ lên git). **Đừng dán mật
khẩu/token vào ô chat** — ghi vào file theo hướng dẫn của trợ lý.

---

## Bước 7 — Lồng an toàn cho trợ lý (không bắt buộc, cần quyền admin)

Mặc định trợ lý chạy chung tài khoản với bạn — nó tự giữ quy tắc, nhưng
máy tính không ép được. Bước này tạo một "tài khoản phụ" kém quyền tên
`troly-agent`: trợ lý chạy trong đó nên **dù có bị lừa cũng không đọc/ghi
được gì ngoài những ngăn tủ bạn đã cho phép** (giống cơ chế sẵn có trên
macOS).

1. Bấm phím Windows, gõ `powershell` → **chuột phải** "Windows
   PowerShell" → chọn **Run as administrator** → Yes.
2. Dán lệnh này rồi Enter — chọn đúng dòng theo cách bạn cài:

   ```powershell
   # Cài bằng file TroLyAI.exe tải về:
   powershell -ExecutionPolicy Bypass -File "$HOME\TroLyAI\tools\setup-agent-user.ps1"

   # Hoặc nếu bạn có folder ai-assistant (tải source):
   powershell -ExecutionPolicy Bypass -File "$HOME\ai-assistant\tools\setup-agent-user.ps1"
   ```

3. Xong — không cần làm lại. Lần mở `start.bat` kế tiếp trợ lý tự chạy
   trong lồng. Bỏ qua bước này cũng không sao: trợ lý vẫn chạy bình
   thường và sẽ nhắc trong chat rằng nó chưa ở trong lồng.

## Lỗi thường gặp

| Bạn thấy | Làm gì |
|---|---|
| `'devin' is not recognized` | Đóng hết PowerShell, mở lại. Chưa được thì cài lại Bước 2. |
| Không chạy được lệnh `irm` | Bạn đang ở CMD/Git Bash chứ không phải PowerShell. Gõ `powershell` trước. |
| `start.bat` báo thiếu devin | Làm lại Bước 2. (Nếu bạn cố ý dùng não AI khác — `brain.json` — thì thông báo này chỉ là nhắc não đó chưa cài.) |
| Trợ lý bảo "không chạy được 'X'" | Não `X` chưa cài. Mở portal → ⚙ Cài đặt → Bộ não → chọn lại Devin hoặc não khác đã cài. |
| Tab Chat trống trơn | Đóng rồi mở lại `start.bat` — cửa sổ "Tro ly AI chat" chạy nền phải còn nguyên. |
| Chế độ Terminal trống | ttyd chưa chạy — chạy `tools\chat-terminal.ps1` trong PowerShell, hoặc dùng chế độ Chat. |
| Bài mới không thấy nút "▶ Dùng ngay" | Bài đó chưa có walkthrough — nhờ trợ lý "làm màn hướng dẫn từng bước cho bài X". |
| Trợ lý bảo "không thấy trình duyệt" | Extension chưa cài hoặc trình duyệt chưa mở — làm Bước 5, mở Chrome/Edge lên. |
| Trang web không mở | Mở tay `http://localhost:8080/web/` trong trình duyệt. |

## Tắt/mở lại mỗi ngày

- **Tắt**: đóng các cửa sổ nền tên "Tro ly AI ..." (có thể tới 4 cái:
  portal, chat, terminal, browser) + tab trình duyệt.
- **Mở lại**: double-click `start.bat` — đăng nhập đã lưu sẵn.
