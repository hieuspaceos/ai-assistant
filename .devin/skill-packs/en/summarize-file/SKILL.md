---
name: summarize-file
description: Read a file (CSV, Excel export, TXT, MD, JSON...) and summarize it in plain words — what's inside, how many rows, anything notable.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Summarize a file for someone who doesn't know tech. They want to know
"what's in this file" without opening and reading every line.

## Steps

1. If they haven't pointed at a file, ask: which file, where? (remind
   them to type @ to pick, or drag-and-drop).
2. Read the file. For big CSVs, sample + count lines via command instead
   of reading everything.
3. Answer in this shape, in plain everyday words:
   - **What this file is**: one sentence, e.g. "a list of 3,412
     customers with email and city".
   - **What's inside**: the main columns/sections, translate cryptic
     column names.
   - **Notable**: duplicate rows, empty cells, odd numbers if spotted.
   - End with: "want me to filter/group/find anything in this file?"
4. If the file is a hard-to-read format (xlsx, pdf): convert to a
   readable form (csv, text) in a temp folder yourself, telling them
   first.
