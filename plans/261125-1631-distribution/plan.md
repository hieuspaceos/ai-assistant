# Plan 2/5 — Distribution: update channel + company config-pack

Ngày: 2026-11-25. Mục tiêu: sau khi cài xong N máy, **fix bug và đẩy
workflow mới không phải đi từng máy**. Mọi thứ đi theo hướng pull — máy
chủ động hỏi, không ai push vào máy từ ngoài (giữ threat model).

## Hai loại dữ liệu, một đường vận chuyển

| Loại | Từ đâu | Áp vào đâu | Tần suất |
|---|---|---|---|
| **Release** (code app) | Server vendor → collector mirror → máy | Đè `tools/ web/ extension/ serve.py...` | Khi có bản mới |
| **Config-pack** (workflow cty) | Collector cty → máy | `.devin/skills/`, `bots.json`, `connections.json`, workflow files | Khi admin up pack mới |

Collector (plan 1) là điểm phát chung: beacon đã ghi
`.devin/fleet-inbox.json` khi có `{update, pack}` — hai consumer đọc
inbox đó.

## Nguyên tắc lớn: KHÔNG fork, chỉ pack

Bài học từ `ima-assistant` (fork copy 20/11 đã lạc hậu toàn bộ fix
audit): **100% khác biệt giữa các cty là dữ liệu** — skills, rules,
mcp_config, bot, template. 0% là code. Vậy:

- Code chỉ sống ở ai-assistant → mọi máy mọi cty chạy CÙNG một
  release → đồng bộ = đúng việc update channel làm.
- Khác biệt cty = `packs/<org>/` trong repo này → phát qua
  config-pack. Cty mới = pack mới, không bao giờ fork repo.
- Fork `ima-assistant` migrate về `packs/ima/` khi plan này xong —
  interim dùng `tools/sync-fork.sh` (Phase 02.5) để kéo code mới.

### Một thay đổi nhỏ trong core: `rules.local.md`

`AGENTS.md` core không được cty sửa (chứa luật an toàn) nhưng luật
nghiệp vụ cty cần chỗ: AGENTS.md thêm 1 dòng "nếu
`.devin/rules.local.md` tồn tại thì đọc — luật cty nằm DƯỚI mọi luật
file này". Pack ghi file đó; AGENTS.md đi theo release — hai kênh
không giẫm nhau.

## Tasks

### Phase 01 — Release format + `tools/update.py`

- [ ] Release format:
  ```
  releases/<ver>/manifest.json  {"version","url","sha256","min_ver","sig"}
  releases/<ver>/troly-<ver>.zip  (code dirs: tools/ web/ extension/
                                   *.bat *.sh tools/launcher.py
                                   AGENTS.md CLAUDE.md templates/
                                   .devin/skill-packs/)
  ```
  Build bằng `tools/build-release.sh` — zip từ repo, kèm manifest.
  Lưu ý: `.devin/` chứa CẢ state lẫn content — chỉ `skill-packs/` đi
  theo release; mọi file khác trong `.devin/` là state máy (whitelist
  không đụng). `AGENTS.md` root cũng đi release (luật cty ở
  `rules.local.md` rồi nên root AGENTS.md do vendor sở hữu).
- [ ] `build-release.sh` = release-readiness gate (học GoClaw
      audit pipeline — audit round 5):
      1. Chạy test suite (`test-gates`, `test-packs`, `test-bridges`,
         `test-parity`, `test-content-guard`) — đỏ thì dừng.
      2. **Secret-scan output zip** (học gitleaks của họ): quét mọi
         entry trong zip bằng pattern token/key/password/`BEGIN.*KEY`
         + danh sách tên file cấm (`bridge.token`, `secrets.local.json`,
         `*.pem`, `mcp_config.local.json` nếu chứa credential thật) →
         thấy thì FAIL. Đây là rào chặn tai nạn lớn nhất: credential
         máy dev bị zip đi phát cho mọi máy.
      3. Check `CHANGELOG.md` có entry cho version mới (fleet kéo về
         cần biết đổi gì để support).
      4. Refuse nếu git tree bẩn (release phải từ commit sạch — tag
         manifest với commit hash).
- [ ] `tools/update.py` — chạy khi (a) launcher khởi động và
      (b) `fleet-inbox.json` báo `update`:
      1. GET manifest — thứ tự nguồn: `collector` trong `fleet.json`
         trước (LAN nhanh), fallback release origin của vendor
         `https://troly.hieuspace.com/releases/latest.json` (file tĩnh
         trên site — đã có `site/` + domain; host bằng static hosting
         là đủ, không cần server động); ver mới ≤ hiện tại → thôi.
      2. Tải zip về `~/.troly-update/` → check sha256 → bung ra thư mục
         staging. **Không follow redirect** (học ssrf.go của GoClaw —
         CheckRedirect refuse): manifest/zip chỉ nhận từ đúng host đã
         cấu hình; server trả redirect → abort. Tránh collector bị sửa
         DNS/proxy kéo về host lạ.
      2b. Trước khi đè code: `tools/backup.py` snapshot `my-course/`
         + `.devin/` state vào `.devin/backup-<ts>/` (manifest.json +
         preflight disk-space — học internal/backup của họ: kiểm đĩa
         trống trước khi nén, thiếu chỗ thì abort chứ không nửa chừng).
      2c. Cũng chạy backup trước khi `apply-pack` ghi đè skills/bots —
         pack sai muốn revert được.
      3. Copy đè lên install dir, **whitelist-state KHÔNG đụng**:
         `my-course/` toàn bộ (config, permissions, connections, bots,
         bài học, workflows đã áp); trong `.devin/`: `bridge.token`,
         `secrets.local.json`, `machine.id`, `license.json`,
         `fleet*.json`, `mcp_config*.json`, `rules.local.md`,
         `pack-version`, `update-pending.json`, `backup-*`,
         `agent.sb`, `skills/` (skill máy đã cài), `beacon.cursor`;
         `*.log`, `.logs/`. Cách chắc nhất: zip chỉ chứa một tập path
         cho phép (code dirs + skill-packs + AGENTS/CLAUDE/templates)
         — update.py từ chối mọi entry ngoài tập đó + từ chối
         `..`/absolute → zip-slip.
      4. Ghi `.devin/update-pending.json` {ver, ts} → launcher thấy file
         này ở lần tick sau → restart các con → xoá file → boot vào bản
         mới.
- [ ] **Không tự vá file đang chạy**: update.py chỉ stage + đánh dấu;
      việc swap xảy ra giữa hai lần boot. Windows khoá file đang chạy —
      pattern này né được hoàn toàn.
- [ ] Rollback: trước khi đè, copy code dirs hiện tại sang
      `.devin/backup-<ver>/`; boot lỗi → launcher phát hiện con die 3
      lần → khôi phục backup, xoá pending, báo lên beacon
      (`update_failed`).

### Phase 02.5 — Interim: `tools/sync-fork.sh` (trước khi fleet xong)

- [ ] Script rsync code dirs `tools/ web/ extension/ *.sh *.bat
      start.sh launcher.py serve.py` từ ai-assistant → fork đích
      (arg đường dẫn), whitelist KHÔNG đụng: `AGENTS.md`, `.devin/skills`,
      `.devin/mcp_config*.json`, `.devin/rules.local.md`,
      `.devin/bridge.token`, `.devin/secrets.local.json`,
      `my-course/**`, `.logs/`.
- [ ] Dry-run flag in danh sách file sẽ đè trước khi chạy.
- [ ] Chạy ngay một lần cho `pet/ima-assistant` để kéo toàn bộ fix
      audit vòng 4-6.
- [ ] Đánh dấu deprecated trong README fork: "sẽ migrate sang
      packs/ima khi distribution xong — không commit thêm vào fork".

### Phase 02 — Config-pack format + apply engine

- [ ] Pack format `pack.json`:
  ```json
  {"pack_version": 7, "org": "IMA",
   "skills": {"<skill-id>": {"SKILL.md": "...", ...files}},
   "bots": [{"id","name","avatar","instructions",...}],
   "connections": [{"id","name","open_url",...}],
   "workflows": {"<wf-id>.json": {...}},
   "permissions_template": [{"path","access"}],
   "exec_allowlist": ["ls *", "cat my-course/**"]}
  ```
  `exec_allowlist` → `.devin/exec-allowlist.json` (plan 6) — CHỈ áp
  máy mới như permissions_template; pack lint reject pattern nguy
  hiểm (`*` trần, `rm *`, pipe-to-shell).
- [ ] `tools/apply-pack.py` — chạy khi inbox báo `pack > applied`:
      - `skills/` → ghi vào `.devin/skills/<id>/` (ghi đè — pack là
        nguồn sự thật của cty; skill học viên tự tạo ID khác thì giữ).
      - `bots` → merge vào `bots.json` theo `id` (update hoặc append;
        không xoá bot không có trong pack — bot user tự tạo giữ nguyên).
      - `connections` → merge theo `id`, không ghi đè `status` probe
        hiện có.
      - `workflows` → ghi `my-course/workflows/` (plan 3 đọc chỗ này).
      - `rules.local.md` → ghi `.devin/rules.local.md` (luật nghiệp
        vụ cty — AGENTS.md core đọc nếu tồn tại).
      - `permissions_template` → CHỈ áp cho máy chưa onboard
        (config.learner_name rỗng) — không bao giờ ghi đè permissions
        đã duyệt của máy đang chạy (đó là consent của user).
      - Ghi `.devin/pack-version` → lần sau không áp lại.
- [ ] Áp pack xong → regen `agent.sb` (`gen_sandbox_profile` đã sẵn) +
      bump manifest nếu skills mới — không cần restart bridge, skill
      đọc lúc spawn não.

### Phase 03 — Collector endpoints (nối plan 1)

- [ ] `GET /api/releases/latest` → manifest; `GET /releases/<ver>.zip`
      static → máy tải từ collector (LAN nhanh, không phụ thuộc internet
      — doanh nghiệp có thể chặn outbound cho máy NV).
- [ ] `POST /api/releases` (admin_key) — vendor/IT upload release lên
      collector. Hoặc collector tự mirror: `COLLECTOR_UPSTREAM` env →
      định kỳ kéo manifest từ server vendor về cache.
- [ ] `POST /api/packs` (admin_key) — upload pack.json; `GET
      /api/packs/<org>/latest` → beacon so `pack_version`.
- [ ] Beacon response `{update: <ver>, pack: <n>}` giờ tính thật từ
      releases+packs trên collector thay vì stub.

### Phase 04 — Parity + an toàn + tests

- [ ] `update.ps1`, `apply-pack.ps1` — cùng contract (staging, whitelist,
      pending-file, backup). Windows path khác nhau nhưng state dirs
      giống hệt.
- [ ] An toàn update — chữ ký BẤT ĐỐI XỨNG (sửa sau audit):
      `sig` trong manifest = ed25519(sha256(zip)) ký bằng vendor
      private key; mỗi máy nhúng `tools/vendor-pubkey` + verifier
      ed25519 pure-python vendored (~150 dòng, stdlib-only, verify
      một manifest là đủ nhanh). KHÔNG dùng HMAC — khoá đối xứng phải
      nằm trên máy để verify → trích ra được → forge release cho cả
      org. Private key ký release giữ OFFLINE phía vendor
      (`tools/sign-release.py`). Kẻ chiếm collector vẫn không cài
      được mã lên mọi máy.
- [ ] `test-distribution.py`: pack apply idempotent (áp 2 lần = 1 lần),
      merge không xoá dữ liệu user, zip-slip bị chặn, sha256 sai → abort,
      license/pack_version state đúng.
- [ ] `docs/fleet.md` thêm mục: vòng đời một bản release từ vendor tới
      máy NV; cách IT cty tự phát pack (không cần vendor).
- [ ] `SECURITY.md`: thêm threat "collector bị chiếm → phát mã" —
      mitigate bằng vendor release_sig; "pack độc" → pack chỉ ghi được
      skills/bots/workflows, không ghi code bridge; permissions_template
      chỉ áp máy mới.

## GATE

- Đổi version 1.0.2 → 1.0.3 giả, build release, đặt lên collector →
  máy dev tự nhận qua beacon → update.py stage → restart vào bản mới →
  `GET /api/health` trả 1.0.3.
- Pack mẫu chứa 1 skill mới + 1 bot → máy dev pull về → skill xuất hiện
  trong `.devin/skills/`, `/api/bots` trả bot mới, permissions user không
  bị đụng.
- Zip chứa `../evil` → update abort; sha sai → abort.

## Rủi ro / mở

- Update hỏng giữa chừng trên máy NV xa → backup+restore path phải test
  kỹ trên Windows thật (file lock).
- Pack skills ghi đè — skill cty sửa tay trên máy NV sẽ bị pack sau đè
  lại → quy ước rõ trong DEPLOY.md: "skill cty chỉ sửa qua pack".

## Kết quả (đã implement — test-distribution.py xanh toàn phần)

- `tools/ed25519.py` vendored + `tools/sign-release.py` + cặp khoá
  vendor (pubkey trong `tools/vendor-pubkey`, private key
  `~/.troly-release-key` — ngoài repo). **Bug thật bị test bắt**: thứ
  tự `Hint` trong checkvalid → sig verify fail ngay GATE đầu.
- `tools/update.py`: pull manifest (collector trước → origin vendor),
  KHÔNG follow redirect, zip-url cùng host manifest, sha256 → ed25519
  → backup → stage whitelist (chống zip-slip + entry ngoài tập) →
  `.devin/update-pending.json`.
- `launcher.py`: `apply_pending()` trong bootstrap (đè code, backup
  `.devin/backup-code-*`, giữ 2), `--rollback`, check update lúc boot
  qua `run_tool_silent` (thread phụ).
- `tools/apply-pack.py`: org check → lint exec_allowlist → backup →
  merge idempotent (skills ghi đè, bots/connections merge theo id,
  workflows, rules.local.md; permissions_template + exec_allowlist CHỈ
  máy chưa onboard).
- `tools/backup.py`: snapshot my-course + state .devin, preflight dung
  lượng đĩa, giữ 5 bản.
- `tools/build-release.sh`: cổng git sạch → VERSION khớp → CHANGELOG
  có mục → chạy hết test suite → zip (.devin/ tách: chỉ skill-packs
  ship) → secret-scan zip → ký → `releases/<ver>/`.
- `tools/sync-fork.sh`: hút skills IMA riêng + bots/connections/perms +
  AGENTS.md → `packs/IMA/pack.json` v1 (14 skill); báo code khác biệt
  để merge tay.
- `tools/collector.py`: `GET /api/releases/latest`, `GET /releases/<f>`,
  `GET /packs/<org>/<v>.json` (machine_key, pack scope org), admin
  `POST /api/releases/<f>` (zip raw ≤200MB) + `POST /api/releases`
  (manifest) + `GET/POST /api/packs`; `mirror_loop` kéo upstream 6h/lần
  (config `"upstream": {"url": …}`); hint `{update, pack}` tính từ
  `DATA/releases/` + `DATA/packs/` thật.
- `beacon.py/.ps1`: ghi inbox → spawn update + apply-pack nền;
  `TROLY_BEACON_ONCE=1` cho chạy một vòng (test).
- `AGENTS.md`: đọc `.devin/rules.local.md` — trên lời dặn thường,
  dưới luật an toàn lõi.
- `CHANGELOG.md` mới; `docs/distribution.md` + SECURITY.md section
  "Phân phối" (ghi rõ residual: pack chưa ký — tin admin_key+lint;
  ký sau nếu khách đòi).
- GATE đạt trong test: release 1.0.2→1.0.3 qua collector → máy stage
  → apply → VERSION đổi; pack v1 áp đủ 6 loại payload; sha sai/sig
  sai/zip-slip/whitelist/org-lệch/allowlist-độc đều abort sạch.
- Còn lại là ops: đẩy `releases/` lên troly.hieuspace.com, cấu hình
  `"upstream"` trong collector.json từng khách, test file-lock trên
  Windows thật khi pilot.
