# Distribution — phát hành + cập nhật + config-pack

Hai kênh đi XUỐNG máy nhân viên (đều pull, không push vào máy):

| Kênh | Mang gì | Tin cậy bằng |
|---|---|---|
| **Release** | code: tools/, web/, extension/, skill-packs, docs | chữ ký **ed25519** — private key offline phía vendor |
| **Pack** | khác biệt của cty: skills, bots, connections, workflows, rules.local.md, permissions_template, exec_allowlist | org scope của collector + lint phía máy — cố ý không ký (xem `decision-log.md`) |

"Một code base duy nhất — khác biệt giữa các cty nằm trong `packs/`" —
không fork repo.

## Chuỗi release

```
vendor: build-release.sh  → test suite + secret-scan + CHANGELOG
                          → zip → sign-release.py ký ed25519
                          → releases/<ver>/{zip, manifest.json}
   ↓ đẩy lên
origin: troly.hieuspace.com/releases/   (file tĩnh — mirror ở đâu cũng
                                         được, sig bảo vệ nội dung)
   ↓ collector config "upstream" kéo 6h/lần (mirror_loop)
collector: DATA/releases/{latest.json, <file>.zip}
   ↓ beacon 15' trả {"update": man} → update.py kéo
máy NV: verify sha256 → verify sig (vendor-pubkey) → backup → stage
        → launcher apply_pending() lúc mở app sau → backup-code-* giữ
        → `troly --rollback` khi bản mới hỏng
```

### Vì sao ed25519 chứ không HMAC

Khoá đối xứng phải nằm trên máy để verify → trích ra được → kẻ chiếm
một máy forge release cho cả org. Với ed25519: máy chỉ nhúng
`tools/vendor-pubkey` (public — lộ không sao); private key
`~/.troly-release-key` ở máy vendor, offline, không commit.

`sig = ed25519(bytes.fromhex(sha256(zip)))` — ký trên 32 byte của
hexdigest. `tools/ed25519.py` là reference impl public-domain thuần
Python, chậm (~1s) nhưng chỉ verify một manifest mỗi lần update.

### An toàn đường tải (update.py)

- **Không follow redirect** — redirect sang host lạ = abort (DNS/proxy
  bị chơi).
- zip url tuyệt đối phải cùng host manifest.
- sha256 khớp manifest rồi mới verify sig — một mắt xích gãy = abort,
  không đè gì.
- **Whitelist zip entry**: chỉ `tools/ web/ extension/ templates/
  collector-web/ .devin/skill-packs/` + file lõi (AGENTS.md, VERSION…);
  `..`, absolute, backslash → abort (zip-slip).
- Trước khi stage: `backup.py` chụp `my-course/` + state `.devin/`.

## Config-pack

`packs/<org>/pack.json` — vendor soạn (hoặc `sync-fork.sh` hút từ fork
cũ), admin đẩy qua `POST /api/packs`:

```json
{"org": "IMA", "pack_version": 3,
 "skills": {"<id>": {"SKILL.md": "…", …}},
 "bots": [{...}], "connections": [{...}],
 "workflows": {"<file>.json": {...}},
 "rules_local_md": "…",
 "permissions_template": [{"path": "…", "access": "read-write"}],
 "exec_allowlist": ["git *"]}
```

Máy áp qua `apply-pack.py` (beacon gọi khi inbox có `pack`):

- skills → ghi đè `.devin/skills/<id>/` (pack là sự thật của cty; skill
  user tự tạo id khác thì giữ).
- bots/connections → **merge theo id**, không xoá cái user tự tạo;
  connections giữ `status`/probe hiện có.
- workflows → `my-course/workflows/`; rules → `.devin/rules.local.md`
  (AGENTS.md đọc, đứng trên lời dặn thường, dưới luật an toàn lõi).
- `permissions_template` + `exec_allowlist` → **chỉ máy chưa onboard**
  (chưa có learner_name) — pack không được đè consent máy đang chạy.
- Lint `exec_allowlist`: pattern chứa `|`, `;`, `>`, `sudo`, `rm `,
  `curl`… → reject cả pack (allowlist độc = kênh chạy code tuỳ ý).
- org trong pack ≠ org máy → abort. Tải pack org khác → collector 403.

## Thao tác vendor

```bash
bash tools/build-release.sh 1.0.3        # cổng đầy đủ → releases/1.0.3/
# đẩy origin (file tĩnh)
scp releases/1.0.3/* vps:site/releases/
# hoặc đẩy thẳng vào collector của một cty:
curl -X POST -H "X-Admin-Key: …" --data-binary @troly-1.0.3.zip \
     http://collector:8790/api/releases/troly-1.0.3.zip
curl -X POST -H "X-Admin-Key: …" -H "Content-Type: application/json" \
     -d @manifest.json http://collector:8790/api/releases
# trên hosted tier (worker): upload release chỉ master — dùng session
# Bearer của tài khoản master, không phải admin_key của org khách
```

Pack: `python3 tools/sync-fork.sh` (interim, hút từ fork) hoặc viết tay
`packs/<org>/pack.json` → `POST /api/packs`.

## Test

`python3 tools/test-distribution.py` — dựng collector thật + máy giả:
pair→approve→key → upload zip+manifest → beacon báo update → update.py
stage → `apply_pending` → VERSION đổi → pack áp merge → mọi abort path
(sha sai, sig sai, zip-slip, whitelist, org khác, allowlist độc).
