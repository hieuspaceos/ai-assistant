---
name: gather-files
description: Sort a messy folder into subfolders by type or date — tidy Downloads, Desktop. Always preview first, always undoable.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Tidy a messy folder for someone who doesn't know tech. Their biggest
fear is **losing files** — so the flow must be: preview → agree → tidy,
and move rather than delete.

## Steps

1. Ask: which folder (usually Downloads/Desktop)? Sort how — offer:
   "by file type" (images into Images/, pdfs into Documents/...) or
   "by month downloaded".
2. **Preview before doing**: show them a SUMMARY table by type — NOT
   file by file (e.g. "23 images → Images/, 8 pdfs → Documents/, 4 odd
   files left alone"). Ask for agreement.
3. Move with `mv`/PowerShell `Move-Item` — never delete anything. Name
   collisions get a suffix, never overwrite.
4. Report: "done — Downloads went from 89 messy files to 6 tidy
   folders". Open the folder for them.
5. Teach the undo: "to put everything back, just tell me 'move it all
   back to Downloads'".
