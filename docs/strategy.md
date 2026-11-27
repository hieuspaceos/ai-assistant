# Strategy — sứ mệnh, định vị, moat (đọc khi thấy lạc hướng)

Doc này là la bàn, không phải spec. Viết từ buổi phân tích 2026-11 —
khi thị trường đổi thì sửa lại, đừng sửa để hợp với việc mình đang
làm. Nếu một quyết định đi ngược doc này, hoặc doc sai, hoặc quyết
định sai — phải ghi lý do vào `decision-log.md`.

---

## 1. Sứ mệnh

Cho mỗi người làm việc văn phòng **không biết code** một người giúp
việc AI làm việc thật — đọc Zalo, xử lý file, đăng web, build trang —
trên **chính máy và tài khoản của họ**, và dạy họ dùng nó ngày càng
giỏi.

Với công ty: mỗi nhân viên có một **agent endpoint quản lý được** —
công ty quyết nó đụng được gì, biết nó làm gì, và **giữ lại toàn bộ
know-how khi nhân viên nghỉ**.

## 2. Luận điểm thời đại (định hướng mọi quyết định)

- **Model commoditize.** Frontier model đủ thông minh cho việc văn
  phòng; chênh lệch còn lại là độ tin cậy agentic (90% vs 98% mỗi
  bước → nhân luỹ qua 50 bước). Độ tin cậy đó ngày càng do
  **harness** quyết định: context nhét gì, tool ra sao, permission,
  hồi phục khi kẹt. → Chiến trường là lớp bọc quanh model, không
  phải model.
- **App sẽ tự xây agent và xây tường.** Vendor không muốn agent
  ngoài đọc dữ liệu của họ (Amazon kiện Perplexity, API đóng dần,
  pay-per-crawl). Tương lai: mỗi app một agent **trung thành với
  vendor app**, cộng cổng agent chính thức (MCP/A2A/API trả phí).
- **AI là "user" tiếp theo của phần mềm.** User giao việc qua chat
  nhưng **verify bằng artifact** (preview, file, dashboard) — chat là
  kênh điều khiển, không phải không gian làm việc. Walkthrough +
  consent card của ta đúng hình dáng này hơn là chat thuần.
- **Hệ quả:** người thắng không phải ai có model tốt nhất, mà ai giữ
  **consent + context tích luỹ + vị trí trung lập trung thành với
  user/công ty**.

## 3. Trợ Lý là gì — nói cho đúng

Không phải "một chatbot nữa", không phải agentic harness sở hữu vòng
lặp (vòng lặp nằm trong brain). Chính xác:

> **Outer harness / governance enclosure cho pluggable ACP brains**
> — "Zed-for-office-workers với consent layer + skill bank".
> Với sếp công ty: "MDM cho AI worker của nhân viên".

```
Model → inner harness (brain CLI: Devin/Gemini/Codex/Claude…)
      → TRỢ LÝ: consent + sandbox │ capability (browser, file, .venv)
                │ knowledge (skills, AGENTS persona, permissions)
                │ surface (portal, walkthrough, fleet)
```

Suy ra: **mượn phần commodity (model, agent loop), tự xây phần
moat.** Không ai "phát minh" harness bằng cách tự viết model.

## 4. Moat — thứ thật sự đáng giá

Phân biệt rõ: chat history/memory là moat YẾU (export được, vendor
khác hấp thụ nhanh). Moat thật:

1. **Compiled context đã kiểm chứng** — skill bank chạy đúng trên
   hệ thống thật của công ty, `permissions.json`, `rules.local.md`.
   Không phải "biết về bạn" mà là "đã chạy đúng trong nhà bạn".
   **Nằm trong file của khách** — moat trung thực: format mở được
   nhưng khách sợ mất cái *máy thực thi* + know-how, không sợ mất
   file. Khách *muốn* bị khoá kiểu này.
2. **Consent UX cho người không tự bảo vệ được** — card loopback,
   brain không tự approve, "dữ liệu không phải lệnh". Consent policy
   được học qua từng lần approve → agent mới phải hỏi lại từ đầu →
   switching cost thứ hai.
3. **Vị trí trung lập** — brain-agnostic qua ACP: hưởng mọi tiến bộ
   model bằng `brain.json`, không bị khoá vendor. "Mượn danh tính
   user" (lái phiên đăng nhập sẵn) né nguyên bài toán agent-identity
   chưa có chuẩn — lợi thế trong giai đoạn chuyển tiếp.

## 5. Tài sản: khấu hao vs tăng giá

| Tài sản | Định vị |
|---|---|
| Lái trình duyệt qua DOM | **Khấu hao** — công nghệ cầu nối cho long-tail app không mở cổng (Zalo cá nhân, WP tự host, phần mềm nội bộ). Duy trì, không mở rộng đầu tư |
| Khung chat/portal UI | **Commodity** — mọi vendor đều có. Đủ tốt là được, đừng đua |
| Consent + sandbox + content_guard | **Tăng giá** — khi agent chi tiền/gửi tin/xoá được, lớp này là hạ tầng bắt buộc của công ty |
| Skill bank + packs + fleet | **Tăng giá mạnh nhất** — context tích luỹ chia sẻ được; switching cost thật |
| Context trong file khách | Bản copy know-how phía công ty — tích luỹ càng lâu moat càng sâu |

## 6. Ba làn lấy dữ liệu — số phận và thứ tự ưu tiên

| Làn | Số phận | Hành động |
|---|---|---|
| Cổng chính thức (API, MCP, OA) | Tồn tại nhưng bị siết + thu phí | **Ưu tiên khi có** — `/zalo-oa` là mẫu |
| Phiên của chính user (extension/DOM) | Khó đóng nhất — "tay của user", không phải scraper | Làn chính cho app không-API; plan B nếu vendor giết web client: automation app native tầng OS |
| Scrape/headless không đăng nhập | Chết — chặn kỹ thuật + kiện | Không làm |

**Quy tắc viết skill: "API trước → browser fallback → báo user".**

## 7. Đối thủ đáng canh (theo thứ tự gần → xa)

1. **Claude Cowork + Claude in Chrome** — cùng hình dáng nhất (agent
   cho non-dev, folder permission, lái trình duyệt). Đệm của ta:
   tiếng Việt, Zalo, phỏng vấn→skill→walkthrough, fleet, context
   trong file khách. Theo dõi từng release.
2. **OS-level harness** — Copilot Actions / Gemini OS / Apple
   Intelligence: đặc quyền đọc mọi app ta không có. Wedge: cross-OS,
   tiếng Việt, governed-by-employer không phải by-Microsoft.
3. **In-app agents** (Kiki…) — ăn từng mảnh trong-app, không xuyên
   app. Nếu Kiki đủ tốt cho việc-trong-Zalo, giá trị ta vẫn còn ở
   chuỗi xuyên-app.
4. **Copilot Studio** — governance mạnh nhất nhưng sân khác (M365);
   doanh nghiệp VN nhỏ không đứng trong hệ đó.
5. **Brain vendors ship UI non-dev** (Devin Desktop…) — đệm là lớp
   dạy + consent + trung lập.

## 8. Nguyên tắc ra quyết định — "không lạc"

- **Không tái hiện agent loop.** Brain vendor làm tốt hơn ta. Đầu tư
  vào thứ inner harness không tự làm được: consent, browser-of-user,
  teaching, skill bank.
- **Không đua chat surface.** Portal đủ tốt; tiền dồn vào context +
  consent.
- **Mọi giá trị rút ra phải rơi vào file của user/công ty.**
  Workspace + skill bank là bản copy phía ta — app nào khóa cửa thì
  tri thức đã rút vẫn còn.
- **Bán outcome, không bán kênh.** "Đăng bài xong" chứ không "đọc
  được Zalo" — đường đi bên trong đổi được mà sản phẩm vẫn nguyên.
- **Mở cổng ngược ra ngoài** (expose năng lực qua MCP khi hệ sinh
  thái chín muồi) — vừa host vừa server, kẻo bị nuốt khi
  agent-to-agent tới.
- **`/phỏng-vấn` là cơ chế gieo moat** — nén cold-start chính là
  tăng switching cost. Cho context tích luỹ **hiện hình** (user thấy
  "kho của mình: N công thức, N folder, N kết nối").
- **Cài đặt một-click là ưu tiên sống còn** — điểm duy nhất khiến
  đúng-đối-tượng bỏ cuộc trước khi thấy giá trị (extension lên Web
  Store, gói binary gọn).

## 9. Điểm yếu đã biết — không tự lừa

- Install friction cao cho đúng audience (brain CLI + OAuth +
  extension sideload).
- DOM-driving gãy khi vendor đổi UI / giết web client.
- Phụ thuộc ACP của N brain — test parity là gánh bảo trì cố định.
- Không always-on — chết khi tắt máy (Lindy/Manus/Cowork scheduled
  chạy 24/7). Cân nhắc scheduled-runner phía collector.
- Đọc/gửi Zalo Web qua extension = gray zone ToS — dần chuyển mảng
  gửi sang OA API.
- Security tự cuộn, không SOC2/audit bên ngoài — bán enterprise sẽ
  bị hỏi.

## 10. Non-goals (nhắc lại)

- Không tự build/host model. Không trở thành agentic brain — brain
  là linh kiện mượn.
- Không cạnh tranh với ChatGPT/Copilot ở khung chat cho người biết
  tiếng Anh.
- Không làm cloud-agent chạy VM của mình (đánh mất làn
  "phiên-của-user" + local-first).
