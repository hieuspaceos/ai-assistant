---
name: make-tool
description: Package a repeated task into a personal tool — generate a new /command skill plus a step-by-step guide.md tutorial in my-course/, and update the manifest. Use when the learner describes work they want turned into a recipe, or wants to "save what you just did as a tool for next time".
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
3. **Write guide.md** per `templates/lesson.md` — an onboarding-style
   step-by-step tutorial: each `### Step N` is ONE action (which button
   to click, what to type, which box to tick), followed by a "✅ you'll
   know it worked when…" line. Put it in `my-course/lesson-XX-<slug>/`
   (XX = next number in the manifest). Name steps from the "step
   vocabulary" in the template (Type a command, Approve a dialog, Open
   the result…) so every guide looks familiar.
4. **Self-check the guide before finishing** — reread the file and
   verify:
   - every `### Step` has exactly ONE action + ONE ✅ line
   - step names come from the step vocabulary
   - no banned words ("simply", "just", "obviously", "easy")
   - sample prompts are copy-paste runnable
   Fix whatever's off before moving to step 5.
5. **Update `my-course/manifest.json`**: add the lesson entry with
   `"has_slides": false, "has_video": false, "has_exercise": false`;
   for a new skill also add to `recipes`:
   `{"command": "/<name>", "meaning": "<one-line meaning>"}`.
6. **Tell the learner** (short, plain words): the tool's name, where to
   type `/command`, and which portal item holds the guide. Add: *"if you
   forget later, reopen the guide or type `/tutor` and I'll walk you
   through it."*

## Don't

- Don't generate slides, videos, exercises, or sample files.
- Don't overwrite an existing skill — on a name clash, ask whether to
  rename or update.
- Don't build a skill for a task done only once — a guide is enough.
