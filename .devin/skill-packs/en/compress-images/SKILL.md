---
name: compress-images
description: Compress and resize many images at once — originals untouched, results in a new folder. Use when the learner needs images for web upload, email, or social media.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

You're about to batch-compress/resize images for someone who does NOT
know tech. Golden rule: **NEVER touch the originals** — always write to
a new folder.

## Steps

1. Ask in plain words (ask_user_question if unclear):
   - Which folder holds the images? (suggest dragging it in, or typing @)
   - What are they for? Suggest: "Website" / "Email" / "Facebook-
     Instagram" — each purpose has a different size.
2. Announce in plain words first, e.g.: *"I'll make a folder
   `small-images` next to the original, copy 47 images over and shrink
   them — originals stay perfect. OK?"*
3. Execute:
   - On Windows prefer PowerShell + .NET (`System.Drawing`) or
     `ffmpeg`/`magick` if already installed. On macOS use `sips`. If a
     tool needs installing, explain briefly first.
   - Web: max 1600px wide, convert to .webp if possible. Email: max
     1200px, jpeg quality 80. Social: 1080px.
   - Rename results web-safe: lowercase, no accents, hyphens for spaces
     (briefly explain: "so the website doesn't choke on filenames").
4. Report LIKE A HUMAN: "done — 47 images in `small-images`, from 210MB
   down to 18MB". Open the result folder for them (`explorer <folder>`
   on Windows, `open <folder>` on macOS).
5. Gentle reminder: "next time just type `/compress-images` and I'll do
   the same thing".
