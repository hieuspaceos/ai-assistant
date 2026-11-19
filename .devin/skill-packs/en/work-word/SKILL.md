---
name: work-word
description: Fill templates and format .docx files with python-docx — replace placeholders, fill tables, batch-generate from data. Originals/templates untouched, results to new files.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Create/edit `.docx` files for someone who doesn't code, using Python
`python-docx`. Golden rule: **NEVER overwrite the original/template** —
results always go to new files.

## Check the tool (first time)

```bash
python3 -c "import docx"  # Windows: py -c "import docx"
```

Missing → `pip install -r requirements.txt` (`python-docx` is listed).

## Main job: batch-fill a template

The real scenario: a contract/letter template `.docx` with placeholders
like `{{name}}`, `{{date}}` + an Excel list of recipients → generate a
filled `.docx` per person.

1. Ask: where's the template, where's the data (Excel/CSV), how to name
   output files (suggest: by recipient `letter-<name>.docx`).
2. Read the template: walk `doc.paragraphs` + `doc.tables` (each
   `table.rows` → `row.cells` → `cell.paragraphs`) for `{{...}}`
   placeholders. **List the found placeholders for them to confirm** —
   typos are common.
3. Read the data (Excel via openpyxl, CSV via `csv` stdlib).
4. For each data row: reload template → replace text inside each `run`
   (placeholder within one run → replace directly; split across runs →
   join paragraph text, replace, reassign to the first run).
5. Write `output/<name>.docx` per row — new folder, template untouched.
6. Report: *"done — 25 letters in `letters/`, each filled with the right
   name/date"*. Open the folder for them.

## Other jobs

- **Read content**: walk paragraphs + tables → text (supports
  `/summarize-file` for .docx).
- **Format**: `run.bold`, `font.size`, `paragraph.alignment`, styles
  `Heading 1`... — match the sample they provide.
- **Tables**: `doc.add_table(rows, cols)` + fill cells.

## Notes

- Old `.doc` (not `.docx`): `python-docx` can't read — ask them to Save
  As .docx once.
- Textboxes, headers/footers, comments: limited support — if the template
  has them, verify on a copy and tell them which parts can't be filled.
- Images in the template are preserved; insert new ones via
  `doc.add_picture(path, width=Cm(n))`.
