# Trợ lý AI — hệ thống tự sinh khoá học cá nhân hoá

Không phải một khoá học viết sẵn. Đây là **một cỗ máy sinh khoá học**
chạy trên Devin CLI: học viên được phỏng vấn về công việc thật → agent
tự thiết kế giáo trình → sinh bài học (guide + bài tập + slide + kịch
bản video) giải quyết đúng nỗi đau của họ → hiển thị qua một portal web
local có nhúng terminal.

Đối tượng: nhân viên văn phòng không biết code (marketing, content, SEO,
design — Google Sheets, WordPress, Canva, CapCut). Windows là chính;
macOS/Linux chạy được bằng `start.sh`. Hỗ trợ **tiếng Việt và English**
— onboarding lần đầu hỏi ngôn ngữ.

**Trang giới thiệu:** https://troly.hieuspace.com — giải thích bằng
video demo thật, có nút tải bản macOS (file `troly` một file duy nhất,
xem `tools/build.sh`).

## Trải nghiệm của học viên

1. Cài một lần theo `SETUP.md` (Windows Terminal + Devin CLI + ttyd).
2. Double-click `start.bat` (hoặc `bash start.sh`) → browser mở portal.
3. **Onboarding lần đầu**: chọn ngôn ngữ (vi/en) → điền tên → chọn
   **"não" AI** (xem mục dưới) → chọn folder trợ lý được đọc → chọn app
   muốn kết nối. Ghi vào `my-course/config.json` + `permissions.json`;
   cài đúng skill pack (`/phong-van` cho vi, `/interview` cho en).
4. Mở tab **💬 Hỏi trợ lý** → gõ `/phong-van`.
   Tab này có 2 chế độ: **Chat** (mặc định — bong bóng tin nhắn,
   chữ đậm/nghiêng/heading như Word) và **Terminal** (CLI của não qua
   ttyd). Chat chạy qua `tools/chat-bridge.ps1` → não ACP theo
   `brain.json` (`tools/chat-bridge.py` trên macOS/Linux).
5. Agent hỏi: bạn dùng tool nào? Việc nào lặp lại tốn thời gian?
   → draft giáo trình → học viên chốt.
6. Agent sinh từng bài vào `my-course/lesson-XX-*/`: `guide.md`,
   `exercise.md`, `video-script.md`, `sample-files/`; đồng thời 2
   background subagent dựng `slides.html` (`slide-builder`) và
   `video.mp4` nếu đủ tool (`video-builder`).
7. `manifest.json` cập nhật → portal refresh là thấy khoá học riêng.
8. Học: xem slide → đọc guide → làm bài tập → kẹt thì hỏi lại trong tab
   chat (`/hoc-bai` = chế độ gia sư dẫn từng bước).

## Đổi "não" của trợ lý (brain.json)

Trợ lý không gắn chết một hãng AI — não là **bất kỳ agent CLI nào nói
chuẩn ACP** (JSON-RPC qua stdin/stdout). `brain.json` ở gốc project ghi
não đang dùng: `cmd`+`args` = lệnh mở chế độ ACP (chat), `terminal` =
lệnh cho chế độ Terminal.

- Preset sẵn trong onboarding: **Devin** (`devin acp`), **Gemini**
  (`gemini --acp`), **OpenCode**, **Goose** — ACP native; **Codex** và
  **Claude Code** qua adapter `npx -y @agentclientprotocol/codex-acp` /
  `claude-agent-acp` (vẫn cần CLI gốc đã đăng nhập).
- Đổi ở **onboarding** hoặc **panel ⚙ Cài đặt** (dropdown chỉ liệt kê
  não đã cài trên máy); não khác nhập lệnh tự do ở onboarding.
  Đổi xong bridge restart agent ngay — không cần chạy lại `start`.
- Não chưa cài hoặc process rớt: chat báo lỗi rõ thay vì treo, và tự
  thử bật lại ở lượt gửi sau.

## Clone một trang web thành trang của học viên

Skill `/clone-trang`: gửi link một trang đẹp → agent đo trực tiếp trên
trình duyệt thật (DOM, computed style, trạng thái tương tác, kiến trúc
route) → dựng lại một file `.html` giống hệt về khung, nội dung thay
bằng của học viên. Pipeline: đo → khảo sát → token → dựng → so → giao,
với vòng so tự động (`tools/clone-compare.py`: style-diff theo
`data-cs-ref` + pixel-diff qua `sips`, không cần Pillow).

- Site nhiều trang → một file `.html` với router băm (`#/route` →
  `data-cs-page`), trang chi tiết (bài viết/sản phẩm…) clone mẫu và
  đánh dấu `data-cs-template` để `/trang-moi` nhân bản khi học viên
  viết thêm.
- Kết quả mở trong viewer `web/clone-view.html` — trang hiện toàn
  màn hình trong portal, bấm **Sửa nội dung** rồi click thẳng vào
  chữ/ảnh/nút để chỉnh tại chỗ (nhờ marker `data-cs-*`), **Lưu lại
  trang** ghi về file gốc và tự tạo `.bak`.
- Số liệu đo giữ trong `my-course/clone-work/<tên-site>/` để lần sau
  chỉnh tiếp không phải đo lại.

## Cấu trúc folder

```
ai-assistant/
├── AGENTS.md                  # persona "giáo viên ELI10" + quy tắc an toàn (áp cho mọi session)
├── SETUP.md                   # hướng dẫn cài đặt cho học viên (Windows)
├── brain.json                 # "não" đang dùng — agent CLI nói ACP (đổi trong onboarding / ⚙ Cài đặt, mặc định devin)
├── start.bat                  # launcher: chat-bridge (7682) + ttyd (7681) + ext-bridge (7684) + portal (8080) + mở browser
├── tools/serve.ps1            # static server PowerShell thuần, chặn dotfiles (serve.py cho macOS/Linux)
├── tools/ext-bridge.py        # cầu nối extension: HTTP API cho agent + WS cho extension (7684)
├── tools/chat-bridge.ps1      # cầu nối browser ↔ não ACP (Windows; .py cho macOS/Linux)
├── tools/chat-terminal.ps1    # chạy ttyd theme sáng + font lớn (chế độ Terminal)
├── intro/slides.html          # deck giới thiệu tĩnh (Bài 0)
├── web/                       # portal: index.html + app.js + styles.css + clone-view.html (viewer sửa trang clone)
├── tools/clone-compare.py     # pha "so" của /clone-trang: style-diff + pixel-diff, không cần Pillow
├── templates/                 # khung bài học / bài tập / kịch bản video / slide deck
├── .devin/
│   ├── skills/                # skill đang dùng — được onboarding copy từ skill-packs
│   ├── skill-packs/
│   │   ├── vi/                # skill tiếng Việt (/phong-van /hoc-bai /doc-zalo /dang-bai ...)
│   │   └── en/                # English skills (/interview /tutor /read-zalo /publish-post ...)
│   └── agents/
│       ├── slide-builder.md   # subagent dựng slides.html từ nội dung bài
│       └── video-builder.md   # subagent: kịch bản quay (luôn có) + video.mp4 (bonus)
├── extension/                 # MV3 extension "Trợ Lý AI" — điều khiển browser thật
└── my-course/                 # khoá học cá nhân hoá + config/permissions/connections + clone-work/<site>/
```

## Triết lý thiết kế

- **Giải quyết nỗi đau, không dạy lý thuyết.** Bài học sinh ra từ việc
  học viên kể là tốn thời gian — không phải giáo trình có sẵn.
- **ELI10.** Mọi khái niệm có phép so sánh đời thường (terminal = cửa sổ
  chat, skill = sổ công thức, approve = ký giấy phép). Quy tắc viết
  trong `AGENTS.md`.
- **Không skill vẫn làm được — có skill thì tốt hơn.** Bài học dạy cả
  cách nhờ tự do lẫn "công thức nhanh" (`/nen-anh`...). Khi học viên lặp
  một request nhiều lần, agent được chỉ để gợi ý gói thành skill mới.
- **An toàn mặc định.** Agent là lớp bảo vệ cuối: luôn nói trước khi
  đụng file, làm việc trên bản copy, chặn paste secrets.

## Onboard một đồng nghiệp

1. Gửi họ **troly.hieuspace.com** — nút tải trỏ GitHub Release mới
   nhất. Trên macOS chỉ cần file `troly` một file; Windows dùng
   `start.bat` theo `SETUP.md` (bản `.exe` đóng gói bằng
   `tools/build.sh` trên máy Windows).
2. Xong. Mọi thứ còn lại agent tự lo với học viên.

**Cập nhật:** portal tự kiểm GitHub Releases khi mở — có bản mới hiện
banner trỏ trang tải; file `troly` mới chỉ đè code, không đụng
`~/TroLyAI` (my-course, brain, secrets). Extension báo "bản cũ" trong
pill góc phải → cập nhật app rồi gỡ + Load unpacked lại; auto-update
thật chỉ có khi extension lên Web Store.

## Nâng cấp sau này (note)

- Chế độ **Chat** nói ACP chuẩn nên não đổi được (`brain.json` —
  Gemini/Codex/Claude…); nâng cấp sau: Devin Desktop/editor ACP thay
  toàn bộ stack nhúng nếu muốn trải nghiệm "app" hơn nữa.
- **Devin Cloud** (app.devin.ai): sandbox an toàn cho người mới, đổi lại
  phải upload file + cloud credits.
- `video-builder` hiện chỉ chắc chắn xuất `video-script.md` — để quay
  video thật kiểu Khan Academy dùng kịch bản đó + OBS; auto-render MP4
  cần Edge headless + ffmpeg + giọng TTS tiếng Việt trên máy học viên.
- Subagent tốn thêm credits — cân nhắc pin `model:` rẻ hơn trong
  `.devin/agents/*.md` nếu muốn tiết kiệm.
