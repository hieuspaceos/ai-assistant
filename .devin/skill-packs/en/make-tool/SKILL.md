---
name: make-tool
description: Package a repeated task into a personal tool — generate a new /command skill plus walkthrough.json (interactive step-by-step guide in the portal) and a readable guide.md in workspace/, and update the manifest. Use when the learner describes work they want turned into a recipe, or wants to "save what you just did as a tool for next time".
triggers:
  - user
  - model
allowed-tools:
  - read
  - write
  - exec
  - grep
  - find_file_by_name
  - ask_user_question
---

You turn one concrete task of the learner's into a reusable TOOL plus a
step-by-step guide. Like writing a dish into the household recipe book —
next time they just call it by name.

## Input

The learner describes a task (e.g. "every week I compress Canva exports,
rename them, upload to the site"), or points at work you just finished
("save this as a tool for next time"). If the description is vague, ask
AT MOST 2 questions first: which files/app does this work on? what does
"done" look like?

## Procedure

1. **Pick the tool's shape** — exactly one of three:
   - *New skill* `.devin/skills/<tool-name>/SKILL.md` — a fixed workflow
     repeated many times.
   - *Existing skill* — `/compress-images`, `/split-customers`… already
     covers it → don't rebuild, just write a guide teaching how to call
     it.
   - *Free-form ask* — too one-off to deserve a skill → just write a
     guide teaching how to phrase the request.
2. **Write SKILL.md** (if a new skill): full frontmatter
   `name`/`description`/`triggers`/`allowed-tools`; body is a recipe —
   the steps to take, what to ask first, safety rules (never touch
   originals, announce before running). Name: lowercase, hyphens,
   no accents (e.g. `compress-facebook-images`). If possible, run it
   once on a permitted folder to prove the recipe works.
3. **Write walkthrough.json** per `templates/walkthrough.json` — the
   interactive step-by-step guide in the portal (small modal, many steps
   do the real action right inside it). This is the main product. Think
   as the LEARNER's action chain (not the agent's): whatever they must
   prepare/type/approve becomes a matching step —
   - app needs to be open first (Zalo, Canva, logged-in site) → `open-url`
   - their own info needed (shop name, link, number) → `input` into a var
   - source file/folder needed → `pick-file` into a var
   - typing a command / answering the assistant → `prompt` (prefill is
     copy-paste runnable)
   - a permission dialog will appear → `wait-perm`
   - they must click a spot in the portal → `spotlight` + `click_target`
   - opening result files/folders → `open`
   - verify the result before finishing → `check` (expectation + a
     "not there — ask the assistant" button)
   **After EVERY prompt/wait-run, place an optional `prompt` "Reply to
   the assistant" then a `wait-run`** — the assistant often asks ad-hoc
   questions mid-run (confirmations, data meaning) and you can't predict
   how many; this loop absorbs them all.
   Open with a `say` intro, close with `done` ("next time just type …").
   Put it in `workspace/tool-XX-<slug>/` (XX = next manifest number).
4. **Write guide.md** per `templates/lesson.md` — the readable version
   of the same walkthrough (same steps, page form for re-reading/print).
5. **Self-check before finishing**:
   - run `python3 tools/test-walkthrough.py` — must PASS
   - each step is ONE action; `prefill`/`placeholder` runnable
   - `{{var}}` in prefills must match a `var` from an earlier
     input/pick-file step
   - guide.md: every `### Step` has ONE action + ONE ✅ line, no banned
     words ("simply", "just", "obviously", "easy")
   Fix whatever's off before moving to step 6.
6. **Update `workspace/manifest.json`**: add the lesson entry with
   `"has_slides": false, "has_video": false, "has_exercise": false,
   "has_walkthrough": true`; for a new skill also add to `recipes`:
   `{"command": "/<name>", "meaning": "<one-line meaning>"}`.
7. **Tell the learner** (short, plain words): the tool's name, where to
   type `/command`, and which portal item holds the guide. Add: *"if you
   forget later, reopen the guide or type `/guide` and I'll walk you
   through it."*

## Don't

- Don't generate slides, videos, exercises, or sample files.
- Don't overwrite an existing skill — on a name clash, ask whether to
  rename or update.
- Don't build a skill for a task done only once — a guide is enough.
