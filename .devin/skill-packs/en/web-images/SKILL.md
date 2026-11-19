---
name: web-images
description: Rename + compress a batch of Canva exports into web-ready images — originals untouched, results in a new folder. Use when the learner just exported a pile of Canva images and needs them ready for a website, WordPress, or the team.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

You're about to process a batch of Canva exports for someone who does
NOT know tech. Their folder is usually full of files like
`Untitled design.png`, `facebook post (1).png` — heavy, messy names, not
web-usable.

Golden rule: **NEVER touch the originals** — always copy to a new folder
first, then rename + compress.

## Steps

1. Ask in plain words (use ask_user_question if unclear):
   - Which folder holds the images? (suggest: drag the folder into the
     chat, or type @ to pick)
   - What naming style? Offer 2-3 easy choices: "by campaign name, e.g.
     `spring-sale-01`" / "by post name" / "keep the original idea, just
     clean it up".
   - What are the images for? Suggest: "Website/WordPress" / "Social
     media" / "Email" — each purpose has its own size.
2. Announce in plain words first, e.g.: *"I'll make a folder `web-images`
   next to the original, copy 23 images over, rename them
   `spring-sale-01.webp` through `spring-sale-23.webp` and compress
   lightly — originals stay perfect. OK?"*
3. Execute:
   - On the learner's Windows machine prefer PowerShell + .NET
     (`System.Drawing`) or `ffmpeg`/`magick` if already installed. On
     macOS use built-in `sips`. If a tool needs installing, explain
     briefly first.
   - Web-safe names: lowercase, no accents/special chars, hyphens for
     spaces, 2-digit numbering (`name-01`, `name-02`...). Briefly
     explain: "so the website doesn't choke on filenames and the images
     stay in order".
   - Size by purpose: website → max 1600px wide, convert to .webp if
     possible; social → 1080px; email → 1200px, jpeg quality 80.
4. Report LIKE A HUMAN: "done — 23 images in `web-images`, from 95MB
   down to 4MB, all nicely named". Open the result folder for them.
5. Gentle reminder: "next time you finish a Canva export, just type
   `/web-images` and I'll do the same thing".
