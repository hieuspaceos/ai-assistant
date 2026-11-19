---
name: export-canva
description: Get Canva exports onto the machine and process them — guide the learner's export, gather files into a folder, hand off to compress/rename/publish. The assistant does NOT click inside the Canva editor.
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

Canva has no durable automation path inside the editor — the right flow
is: **the learner exports → the assistant processes the files**. This
skill standardizes the front half: export where, name what, then what.

## Step 1 — Export

Guide the learner on Canva (they click, you instruct):

1. **Share** button (top right) → **Download**.
2. File type: PNG (normal images) / JPG (white background, lighter) /
   PDF (print). Multi-page designs → Canva downloads a **.zip**.
3. Files land in `~/Downloads` by default.

## Step 2 — Gather into a working folder

- `.zip` → extract into a `<design-name>` folder in Downloads or an
  allowed folder (check `permissions.json` first).
- Loose files → gather into one folder.

## Step 3 — Process by need

| Need | Hand to |
|---|---|
| Images for web/WordPress | `/web-images` (rename + compress → webp) |
| Images for email/social | `/compress-images` |
| Publish to WordPress | `/publish-post` (upload processed images) |
| See what's in the pile | `/summarize-file` |

## Notes

- Canva Pro exports `.svg`/`.pdf print`: for image work convert to
  png/jpg first (sips/ImageMagick).
- Learners often forget multi-page → zip: remind them "if the design has
  pages, tick the pages or download the whole zip and I'll extract it".
- Never drive the Canva editor via the extension (complex layout, could
  break their work) — the editor is theirs alone.
