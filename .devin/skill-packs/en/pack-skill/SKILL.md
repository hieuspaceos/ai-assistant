---
name: pack-skill
description: Package generated skills in .devin/skills/ into a zip to send back to the skill bank — share a "recipe" the assistant made with other learners.
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

Useful skills born on a learner's machine live in `.devin/skills/<name>/`.
To reach the shared bank: zip them up → the learner sends the file to the
bank keeper (mail/Zalo) → keeper merges into `.devin/skill-packs/<lang>/`.

## Steps

1. List skills in `.devin/skills/` with their `description:` line → ask
   which to share (`ask_user_question`, multi_select — up to 4 rounds if
   many). **Skip** the built-in skills (already in skill-packs) — only
   package NEW generated ones.
2. Announce: *"I'll pack the 2 skills you picked into
   `workspace/skill-exports/skills-<date>.zip` for you to send to the
   bank keeper. The originals in `.devin/skills/` stay untouched. OK?"*
3. Pack:
   ```bash
   mkdir -p workspace/skill-exports
   cd .devin/skills && zip -r ../../workspace/skill-exports/skills-$(date +%Y%m%d).zip <skill1> <skill2>
   # Windows PowerShell:
   # Compress-Archive .devin\skills\<skill1>,.devin\skills\<skill2> workspace\skill-exports\skills-<date>.zip
   ```
4. Report the zip path + how to send: *"send this file to the bank
   keeper (I won't send it myself)"*.
5. Bank keeper: unzip into `.devin/skill-packs/<vi|en>/` → learners
   reinstall via `/api/setup` or copy to `.devin/skills/`.

## Bot mode — "share the whole assistant"

Besides single skills, you can pack a **bot** from `workspace/bots.json`
(a named assistant + the skills it uses). The file imports on another
machine via "Import assistant" in the header chip menu.

1. Read `workspace/bots.json` → list `bots[]` (name + role) → ask the
   learner which one to share.
2. Write `bot.json` from that object — schema fields only:
   `name, avatar, role, skills, needs, recipes, instructions`
   (NO `id`, NO `triggers`).
3. Write a 3-line `README.txt`: what the bot does, which apps it needs,
   plus "read the instructions before importing".
4. Copy each skill in `bot["skills"]` from `.devin/skills/<name>/` into
   `skills/<name>/` in the bundle (pack system skills too — small files,
   the receiving side never overwrites existing skills).
5. Zip into `workspace/skill-exports/bot-<slug>.zip` with this layout:

   ```
   bot-mia.zip
   ├── bot.json
   ├── README.txt
   └── skills/<name>/SKILL.md (+ files)
   ```

   Use python `zipfile` (Windows may lack `zip`):
   ```bash
   python3 -c "import zipfile,glob,os
   z=zipfile.ZipFile('workspace/skill-exports/bot-<slug>.zip','w')
   z.write('bot.json'); z.write('README.txt')
   [z.write(f,os.path.relpath(f,'.')) for f in glob.glob('skills/**/*',recursive=True) if os.path.isfile(f)]
   z.close()"
   ```
   (run from a temp folder containing bot.json + README.txt + skills/)
6. Report the path — the learner sends it themselves, never auto-send.
