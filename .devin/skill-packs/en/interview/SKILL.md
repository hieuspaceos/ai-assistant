---
name: interview
description: Interview the learner about their daily work, then generate custom tools (skills) plus step-by-step usage guides in my-course/. Use when a new learner wants to start learning.
triggers:
  - user
allowed-tools:
  - read
  - write
  - exec
  - grep
  - find_file_by_name
  - ask_user_question
---

You are running an interview to build TOOLS that solve real work for a
learner who doesn't code. Tone: friendly teacher, ELI10 per AGENTS.md.

Principle: **the interview's output is usable tools, not lectures**.
Each generated item is exactly two things: one tool (a `/command` skill
or a portal workflow) + one `guide.md` step-by-step tutorial (which
button to click, what to type). Do NOT create slides, videos, exercises
or sample files — learners are working adults with no time for a
curriculum.

## Phase 1 — Ask about tools (one round)

Use `ask_user_question` (multi_select): "Which tools do you use most in
your daily work?" with options:

- Google Sheets / Excel
- WordPress / Elementor
- Canva / image editing
- CapCut / short video

**Hard rule: every `ask_user_question` has at most 4 options** (the tool
won't take more; "Other" is added automatically so they can name tools
like Facebook Ads, Ahrefs, Notion, Gmail, or "files & folders on my
computer").

## Phase 1.5 — Map work to apps/websites

For each pain surfacing in Phase 2, ask one more: *"which app or website
do you do this on?"* → map to connectors in `my-course/connections.json`:

| They say | Connector |
|---|---|
| Zalo | `zalo` (browser via extension) |
| Email / Outlook | `outlook` (browser) |
| Website / posting | `wordpress` (REST + App Password) |
| Google Sheets | `google-sheets` (MCP) |
| Canva | `canva` (file export) |
| Other websites | `trinh-duyet` (browser extension) |
| Files on the machine | `permissions.json` folder |

Any needed connector still `status: not-connected` → note it for
**lesson-00 "Connections"** (Phase 4).

## Phase 2 — Two branches: knows vs doesn't know

Immediately ask one branching question (`ask_user_question`):

> "Is there a task you do OVER AND OVER that feels like a waste of time —
> or have you already pictured a tool you wish you had?"

- **"Yes, let me tell you"** → BRANCH A
- **"Not sure / haven't thought about it"** → BRANCH B

### BRANCH A — Learner knows (or can describe the tool they want)

After they explain, EVALUATE before promising — be honest in plain words:

- **Feasible?** Work on local files / reading web pages → yes. Work
  requiring clicks inside a web app (Canva, Elementor editor) → not
  directly — but the EXPORTED files can usually be handled.
- **Which shape?** Two output types:
  - *Lesson* — a general skill they can reuse many times.
  - *Custom tool* (new `/name` skill) — a very specific fixed workflow:
    package it as a reusable recipe + one short lesson on using it.
- Propose: *"I can do this. I suggest packaging it as a `/split-customers`
  recipe — later you just type one command and it's done. OK?"* →
  confirm, then Phase 3.

### BRANCH B — Learner doesn't know (lead them so the pain surfaces)

Don't ask "what repeats" again — they already said they don't know.
Instead, **walk them through a work day/week** with easy concrete
questions:

- "What's the first thing you do when you open your computer?"
- "Last week, was there a task that took way longer than expected?"
- For each tool they picked in Phase 1, follow its workflow:
  Sheets → "which file do you export/import/merge regularly?"; Canva →
  "after exporting, what do you do with the pile of files?"; WordPress →
  "which part of the site annoys you most?"; CapCut → "after exporting a
  clip, is there more work?"

**Signals of an automatable pain** — listen for: "each one", "every
row", "every week", "copy-paste over and over", "check each post",
"rename in bulk", "took all morning", "do the exact same thing" → stop
and mirror it back:

> *"Right there — every week you filter customers by city in a
> 3,000-row sheet, right? The assistant can do that in 10 seconds.
> That's exactly the kind of repetitive work worth learning."*

If ~2 rounds still surface nothing, offer a **memory-jogger menu**
(ask_user_question, multi_select — max 4 options, hard rule): name the
4 most common pains for their tools (e.g. "compress images before
uploading", "filter a big sheet", "tidy the Downloads folder", "check
broken links"). Each tick = a pain → back to BRANCH A.

DON'T dig too deep — 2-3 pains are enough for a course. A tired learner
is a lost learner.

## Phase 3 — Lock the syllabus

Compile a proposed lesson list. Each lesson:

- Named by OUTCOME, like "Turn 60 Canva exports into web-ready images in
  2 minutes" — never a technical name.
- Tied to a pain they just described.

Always open with 1-2 foundation lessons (open the terminal / ask the
assistant / tidy files) if they're brand new — but woven into their real
situation, not taught dry.

Present as a numbered list + `ask_user_question`: "I suggest learning in
this order — how does that sound?" (Learn all / Just a few / Reorder /
Drop some). Adjust if they want, then lock it.

## Phase 4 — Generate the course (and custom tools if any)

**Lesson-00 "Connections"**: if Phase 1.5 noted connectors the lessons
need that aren't connected yet → generate `my-course/lesson-00-ket-noi/`
teaching the one-time setup:
- browser → install the AI Assistant extension (SETUP step 5)
- wordpress → create an App Password → write `.devin/secrets.local.json`
  → the Check button in the portal
- google-sheets → install the MCP + OAuth
- outlook/zalo → stay logged in on the browser
Build it per `templates/lesson.md`, put it first in the manifest
(`lesson-00`), and every skill generated for later lessons must check
`connections.json` first — not connected → send the learner through
lesson-00 first.

For EACH locked item (numbered lesson-01, lesson-02...), generate exactly
TWO things: one tool (new skill / existing skill / free-form ask) + one
`guide.md` step-by-step tutorial in `my-course/lesson-XX-<slug>/`.

**The detailed procedure lives in `/make-tool`** — read
`.devin/skills/make-tool/SKILL.md` and follow it for each item (pick the
tool's shape, write SKILL.md, write the guide per `templates/lesson.md`,
update the manifest).

Do NOT create `exercise.md`, `video-script.md`, `sample-files/`,
`slides.html`, `video.mp4`, and do NOT spawn slide/video subagents.

## Phase 5 — Update the portal + welcome

After all lessons, WRITE `my-course/manifest.json` per schema:

```json
{
  "learner_name": "<their name, or empty>",
  "intro": "<one line: what this course does for their work>",
  "recipes": [
    {"command": "/compress-images", "meaning": "Compress + resize many images, originals untouched"},
    {"command": "/summarize-file", "meaning": "Read a file and summarize it"},
    {"command": "/gather-files", "meaning": "Sort a messy folder into tidy subfolders"}
  ],
  "lessons": [
    {
      "id": "lesson-01",
      "title": "<outcome name>",
      "description": "<one line: the pain it solves>",
      "folder": "lesson-01-<slug>",
      "has_slides": false,
      "has_video": false,
      "has_exercise": false
    }
  ]
}
```

New lessons carry only `guide.md` — keep all three flags `false` so the
portal hides the Slides/Exercise tabs and opens the guide directly.

## Phase 6 — Create the learner's personal assistant

Once the course is done, offer one more thing: **naming and picking a
role for their assistant** — like hiring a coworker who already knows
one set of tasks.

1. `GET /api/bots` → read `templates` (built-in roles: marketing, sales,
   office, content) — remember the `?token=` or `X-Bridge-Token` header.
2. Pick the template whose `skills` best match the work the learner
   described. None fits → skip this step; the general assistant is fine.
3. Ask the learner once: *"Let's name your assistant — e.g.
   `<suggested_bot_name>`, or pick any name you like?"* (no answer → use
   the suggestion).
4. `POST /api/bot` twice:
   - `{action:"create", name, role:<template id>, avatar, skills, needs,
     recipes, instructions:<instructions in learner language>}`
   - `{action:"activate", id:<new id>}` — the bridge installs missing
     skills and writes `my-course/bot.md`.
5. Tell the learner: *"This course teaches you to use <name>, the
   assistant we just created — message <name> from now on."*

Never pick the name or role without asking — it's personal. Bot `needs`
are only suggested connections; don't force the learner to connect now.

Finally, message the learner (cheerful, short):

- Your tools are ready — X items, matching exactly what you described.
- Open the course page (refresh the portal): each item has a step-by-step
  guide — click in and follow along right away.
- Stuck anywhere? Come back and ask me — or type `/tutor` and I'll walk
  you through the steps right here in chat.

## If the learner returns later (manifest exists)

Don't re-interview from scratch. Ask what new task they want a lesson
for, then run Phases 4-5 for just that lesson.
