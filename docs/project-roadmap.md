# ai-assistant — Project Roadmap

Hướng đi đã biết, xếp theo độ sẵn sàng. Stateful — cập nhật khi xong
việc hoặc đổi ưu tiên.

## Đang vững — không cần động

- Portal + Chat/Terminal qua não ACP (mặc định `devin acp`) + ttyd
- Não đổi được: `brain.json` + `/api/brain` + bước chọn não trong
  onboarding và panel Cài đặt (Gemini/Codex/Claude/OpenCode/Goose)
- Onboarding + skill packs vi/en
- Extension + ext-bridge (~25 action, nhóm t* qua CDP)
- Clone pipeline đầu-cuối (đo → khảo sát → token → dựng → so → giao)
- Viewer sửa tại chỗ + `.bak` + `/trang-moi` nhân bản template

## Gần — công nghệ đã có, chỉ thiếu nối

| Việc | Ghi chú |
|---|---|
| Mobile viewport cho clone | Extension chưa đổi được kích thước cửa sổ — hiện kiểm tĩnh media query. CDP `Emulation.setDeviceMetricsOverride` là đường đi nếu cần ảnh mobile thật |
| `clone-compare` trên Windows | `shot` cần `sips` (macOS). PowerShell `System.Drawing` đổi BMP tương đương — port khi có học viên Windows cần so ảnh |
| Backup nhiều mốc | `.bak` giữ 1 bản. Nếu học viên hay sửa hỏng: versioned `.bak-<timestamp>` hoặc git init trong my-course |
| Skill pack đồng bộ hai chiều | `clone-trang`/`trang-moi` chưa có trong `skill-packs/` — muốn onboard máy mới có sẵn thì copy vào cả `vi/` lẫn `en/` |
| Kiểm tĩnh file clone tự động | Đếm data-cs/section, parse thẻ — có thể thêm mode `check` vào clone-compare.py |

## Xa — cần quyết định sản phẩm

| Việc | Câu hỏi mở |
|---|---|
| Devin Desktop/editor ACP thay stack nhúng | Portal giờ là vỏ — nâng cấp khi muốn trải nghiệm "app" hơn; đánh đổi: mất quyền kiểm soát UI |
| Devin Cloud (app.devin.ai) | Sandbox an toàn cho người mới nhưng phải upload file + trả cloud credits |
| `video.mp4` thật | `video-builder` chỉ chắc chắn ra kịch bản — quay kiểu Khan cần Edge headless + ffmpeg + TTS tiếng Việt |
| Đa học viên trên một máy | Hiện một `my-course/` duy nhất — nếu cần profile thì manifest/config theo user |
| Publish clone ra ngoài | File tĩnh up Netlify/GitHub Pages được, nhưng là việc kỹ thuật với học viên — chỉ làm khi có nhu cầu thật |

## Nguyên tắc ưu tiên

- Máy học viên không có môi trường dev → mọi tính năng mới phải chạy
  được không cần cài thêm (xem `code-standards.md` → rejection patterns).
- Sửa skill từ lỗi thật, không phòng ngừa suông — mỗi lần clone/test
  lòi lỗi mới thì vá vào skill trước khi viết tính năng mới.
