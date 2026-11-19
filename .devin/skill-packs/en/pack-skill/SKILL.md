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
   `my-course/skill-exports/skills-<date>.zip` for you to send to the
   bank keeper. The originals in `.devin/skills/` stay untouched. OK?"*
3. Pack:
   ```bash
   mkdir -p my-course/skill-exports
   cd .devin/skills && zip -r ../../my-course/skill-exports/skills-$(date +%Y%m%d).zip <skill1> <skill2>
   # Windows PowerShell:
   # Compress-Archive .devin\skills\<skill1>,.devin\skills\<skill2> my-course\skill-exports\skills-<date>.zip
   ```
4. Report the zip path + how to send: *"send this file to the bank
   keeper (I won't send it myself)"*.
5. Bank keeper: unzip into `.devin/skill-packs/<vi|en>/` → learners
   reinstall via `/api/setup` or copy to `.devin/skills/`.
