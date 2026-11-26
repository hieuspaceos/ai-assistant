# Trợ Lý AI — an assistant that does real work, and teaches you to use it

An AI assistant that **does real work on your machine**: reads Zalo,
updates Google Sheets, processes files, posts to WordPress, builds web
pages — using your own signed-in browser, no code required.

And it's the only assistant that **teaches you how to use it**: on first
run it interviews you about your actual job → designs a personal course
→ generates lessons (guide + exercises + slides + video script) that
solve your real pain points, served through a local web portal.

Audience: office workers who don't code (marketing, content, SEO,
design — Google Sheets, WordPress, Canva, CapCut). Windows is the
primary platform; macOS/Linux works via `start.sh`. Supports
**Vietnamese and English** — first-run onboarding asks for a language.

**Landing page:** https://troly.hieuspace.com — explains with a real
demo video and has download buttons (single file per OS — `troly` for
macOS, `TroLyAI.exe` for Windows, see `tools/build.sh`).

## The learner experience

1. Install once following `SETUP.md` (Windows Terminal + Devin CLI +
   ttyd).
2. Double-click `start.bat` (or `bash start.sh`) → the portal opens in
   the browser.
3. **First-run onboarding**: pick a language (vi/en) → enter your name
   → pick an AI **"brain"** (see below) → choose folders the assistant
   may read → choose apps to connect. Writes
   `my-course/config.json` + `permissions.json`; installs the matching
   skill pack (`/phong-van` for vi, `/interview` for en) and writes the
   language's recipes into `manifest.json`.
4. Open the **💬 Ask the assistant** tab → type `/phong-van`.
   This tab has 2 modes: **Chat** (default — message bubbles,
   bold/italic/headings like Word) and **Terminal** (the brain's CLI
   via ttyd). Chat goes through `tools/chat-bridge.ps1` → the ACP brain
   picked by `brain.json` (`tools/chat-bridge.py` on macOS/Linux).
5. The agent asks: which tools do you use? What repetitive work eats
   your time? → drafts a syllabus → the learner approves it.
6. The agent generates each lesson into `my-course/lesson-XX-*/`:
   `guide.md`, `exercise.md`, `video-script.md`, `sample-files/`; two
   background subagents build `slides.html` (`slide-builder`) and
   `video.mp4` when the tools exist (`video-builder`).
7. `manifest.json` updates → refresh the portal and the personal course
   is there.
8. Learn: watch slides → read the guide → do the exercise → when
   stuck, ask in the chat tab (`/hoc-bai` = tutor mode, step by step).

## Swapping the assistant's "brain" (brain.json)

The assistant isn't locked to one AI vendor — the brain is **any agent
CLI that speaks ACP** (JSON-RPC over stdin/stdout). `brain.json` at the
project root records the active brain: `cmd`+`args` = the command that
starts ACP mode (chat), `terminal` = the command for Terminal mode.

- Onboarding presets: **Devin** (`devin acp`), **Gemini**
  (`gemini --acp`), **OpenCode**, **Goose** — native ACP; **Codex** and
  **Claude Code** via the `npx -y @agentclientprotocol/codex-acp` /
  `claude-agent-acp` adapters (still need the underlying CLI logged in).
- Switch in **onboarding** or the **⚙ Settings panel** (the dropdown
  only lists brains actually installed); other brains get a free-form
  command field in onboarding. The bridge restarts the agent
  immediately — no need to re-run `start`.
- Missing or crashed brain: chat reports a clear error instead of
  hanging, and retries the launch on the next send.

## For companies — fleet management & updates

The same binary runs standalone for individuals, but a company placing
`fleet.json` + `license.json` into `.devin/` turns every employee
machine into a **fleet member**: a push-only beacon
(`tools/beacon.py` / `beacon.ps1`) reports a sanitized snapshot every
15 minutes to a **collector** — counts and status only, never chat
content or file contents.

- **Collector** — `tools/collector.py` (self-host, 3 tiers: LAN /
  customer VPS / vendor-hosted) or `worker/` (Cloudflare Workers +
  D1 + R2, live at `troly.hieuspace.com/fleet/`). Pairing: shared
  `beacon_secret` → pending → admin approves → per-machine
  `machine_key` (revocable per employee).
- **Dashboard** — `collector-web/index.html`: login by account or
  admin key. Two admin roles on the hosted tier: **master** (vendor —
  creates orgs, issues licenses, manages accounts, rotates org
  secrets) and **company admin** (sees/approves only own org's
  machines, pushes packs).
- **Distribution** — releases signed ed25519 (private key offline)
  flow vendor → collector → machines with stage + rollback; per-org
  **packs** (skills/workflows/rules) push company customization to
  every machine without touching code.

Details: `docs/fleet.md`, `docs/distribution.md`, `docs/SECURITY.md`.

## Cloning a web page into the learner's own page

The `/clone-trang` skill (en: `/clone-page`): paste a link to a page
you like → the agent measures it live in your real browser (DOM,
computed styles, interaction states, route architecture) → rebuilds a
`.html` file identical in structure with your content in place.
Pipeline: measure → survey → tokens → build → compare → deliver, with
an automated compare loop (`tools/clone-compare.py`: style-diff by
`data-cs-ref` + pixel-diff via `sips`, no Pillow needed).

- Multi-page site → one `.html` file with a hash router (`#/route` →
  `data-cs-page`); detail pages (posts/products…) get cloned from a
  `data-cs-template` mold so `/trang-moi` (en: `/new-page`) can spawn
  more when the learner writes new content.
- Results open in the `web/clone-view.html` viewer — the page fills the
  portal, click **Edit content** then click directly on text/images/
  buttons to edit in place (thanks to `data-cs-*` markers); **Save
  page** writes back to the source file and auto-creates a `.bak`.
- Measurements stay in `my-course/clone-work/<site-name>/` so later
  edits don't need re-measuring.

## Folder structure

```
ai-assistant/
├── AGENTS.md                  # "ELI10 teacher" persona + safety rules (applies to every session)
├── SETUP.md                   # install guide for learners (Windows)
├── brain.json                 # active brain — an ACP-speaking agent CLI (change in onboarding / ⚙ Settings, default devin)
├── start.bat / start.sh       # launcher: chat-bridge (7682) + ttyd via term-gate (7681) + ext-bridge (7684) + portal (8080) + open browser
├── tools/serve.ps1            # pure-PowerShell static server: dotfile block, CSP on course pages, Range (serve.py on macOS/Linux — + Host check, keep-alive)
├── tools/ext-bridge.py        # extension bridge: HTTP API for the agent + token-authed WS for the extension (7684)
├── tools/chat-bridge.ps1      # browser ↔ ACP brain bridge: long-poll, respond-gate, prompt lock; on Windows also spawns the brain under the restricted `troly-agent` user (CreateProcessWithLogonW + NTFS ACL — set up once via setup-agent-user.ps1); .py on macOS/Linux spawns under Seatbelt
├── tools/term-gate.*          # gate between ttyd and the brain — requires the connection code before exec (.sh/.ps1 — the .cmd is only an arg-less forwarder since batch can't read argv safely)
├── tools/read-brain.ps1       # validated brain.json read (charset + deny-list) shared by start.bat + chat-terminal.ps1
├── tools/gen-sandbox.py       # generates .devin/agent.sb from permissions.json — macOS enforcement (re-validates each grant at profile build: path_sensitive + symlink-divergence + rw_grant_ok)
├── tools/path_guard.py        # sensitive-path policy shared by chat-bridge (request/apply checks) and gen-sandbox (enforcement) — underscore name required so hyphenated scripts can import it
├── tools/launcher.py          # supervisor inside the packaged binary — builds ~/TroLyAI, spawns all processes
├── tools/chat-terminal.ps1    # ttyd launcher, light theme + large font (Terminal mode)
├── tools/beacon.py/.ps1       # fleet beacon — push-only snapshot 15' → collector (fleet machines only)
├── tools/collector.py         # fleet collector: pairing/approve/revoke, license check, dashboard, release+pack store
├── tools/update.py            # pull signed release: no-redirect → sha256 → ed25519 → stage → apply at boot + rollback
├── tools/apply-pack.py        # apply org pack (skills/workflows/rules) — lint exec_allowlist, never overrides consent
├── tools/make-license.py      # vendor: sign license.json (HMAC org|seats|expiry|issued)
├── tools/sign-release.py + ed25519.py  # vendor: sign release offline (private key never in repo)
├── tools/backup.py            # snapshot .devin/ + my-course/ before update/pack-apply
├── tools/content_guard.py     # UNTRUSTED-content wrapper, injection detect, env allowlist scrub
├── tools/test-*.py            # stdlib smoke tests: bridge endpoints, .py↔.ps1 parity, fleet lifecycle, worker 2-tier, packs sync
├── worker/                    # port of collector.py → Cloudflare Workers + D1 + R2 (hosted tier, /fleet/)
├── collector-web/             # fleet dashboard: login (account or admin key) + role-based tabs
├── deploy/                    # company install kit: install.ps1/sh, DEPLOY.md, force-install.md, vendor-infra.md
├── packs/                     # per-org config packs (skills/workflows/rules — the "same codebase" differentiator)
├── intro/slides.html          # static intro deck (Lesson 0)
├── site/                      # landing page troly.hieuspace.com (deployed via the gh-pages branch + CNAME)
├── plans/                     # multi-phase work plans (executed and in-flight)
├── web/                       # portal: index.html + app.js + styles.css + clone-view.html (clone editor)
├── tools/clone-compare.py     # /clone-trang "compare" phase: style-diff + pixel-diff, no Pillow
├── templates/                 # lesson / exercise / video-script / slide-deck scaffolds
├── .devin/
│   ├── skills/                # active skills — copied from skill-packs by onboarding
│   ├── skill-packs/
│   │   ├── vi/                # Vietnamese skills (/phong-van /hoc-bai /doc-zalo /clone-trang …)
│   │   ├── en/                # English skills (/interview /tutor /read-zalo /clone-page …)
│   │   └── recipes/           # <lang>.json — sidebar recipes written to manifest on setup
│   └── agents/
│       ├── slide-builder.md   # subagent that builds slides.html from lesson content
│       └── video-builder.md   # subagent: shooting script (always) + video.mp4 (bonus)
├── extension/                 # "Trợ Lý AI" MV3 extension — drives the real browser
└── my-course/                 # the personalized course + config/permissions/connections + clone-work/<site>/ (gitignored — local DOM refs)
```

## Design philosophy

- **Solve pain, don't teach theory.** Lessons are generated from what
  the learner says wastes their time — not a pre-canned syllabus.
- **ELI10.** Every concept gets an everyday analogy (terminal = chat
  window with the computer, skill = recipe book, approve = signing a
  permission slip). The rules live in `AGENTS.md`.
- **Works without skills — better with them.** Lessons teach both
  free-form asking and the "quick recipe" (`/nen-anh`…). When a learner
  repeats a request often, the agent is told to suggest packaging it as
  a new skill.
- **Safe by default.** The agent is the last line of defense: always
  announces before touching files, works on copies, blocks pasted
  secrets. Belt-and-suspenders on top: every bridge requires the
  connection code, Terminal mode asks for it again inside the shell
  (`term-gate`), permission cards only accept live pending requests
  with a loopback `Origin` — both the internal consent cards and the
  brain's own ACP permission cards (the agent can't self-approve: on
  macOS the "Allow" button lives in a native OS dialog the
  sandboxed agent can't fake or click), "delete lesson" moves the
  folder to `my-course/.trash/` so a misclick is recoverable,
  course/clone pages run sandboxed to an opaque origin (can't read the connection code or frame the portal), and on macOS the
  brain runs inside a Seatbelt sandbox generated from
  `permissions.json` — write-allowlist (`my-course/` only) plus hard
  deny-write on the assistant's own code (`tools/`, `brain.json`,
  `.git/`…), so even a granted or hand-edited `read-write` on a parent
  folder can't plant code that runs outside the sandbox. On Windows
  the brain runs under the restricted `troly-agent` local user with
  equivalent NTFS ACLs (one-time admin setup via
  `tools/setup-agent-user.ps1` — without it the bridge falls back to
  policy-only and warns) — see `docs/SECURITY.md`.

## Onboarding a colleague

1. Send them **troly.hieuspace.com** — the download button points at
   the latest GitHub Release. On macOS it's just the single `troly`
   file; Windows uses `start.bat` per `SETUP.md` (a packaged `.exe`
   built by `tools/build.sh` on a Windows machine).
2. Done. The agent handles everything else with the learner.

**Updates:** the portal checks GitHub Releases on open — a new version
shows a banner linking to the download; the new `troly` file overwrites
code only, never touches `~/TroLyAI` (my-course, brain, secrets). Fleet
machines update over the collector channel instead: ed25519-signed
zips staged by `update.py` and applied at next boot with rollback. The
extension reports "outdated" in the top-right pill → update the app,
then remove + Load unpacked again; real auto-update only exists once
the extension ships to the Web Store.

## Future upgrades (notes)

- **Chat** mode speaks standard ACP so brains are swappable
  (`brain.json` — Gemini/Codex/Claude…); a later upgrade could be Devin
  Desktop/editor ACP replacing the whole embedded stack for a more
  "app-like" feel.
- **Devin Cloud** (app.devin.ai): a safe sandbox for beginners, at the
  cost of file uploads + cloud credits.
- `video-builder` currently guarantees `video-script.md` only — real
  Khan-style recording uses that script + OBS; auto-rendered MP4 needs
  headless Edge + ffmpeg + a Vietnamese TTS voice on the learner's
  machine.
- Subagents cost extra credits — consider pinning a cheaper `model:` in
  `.devin/agents/*.md` to save money.
