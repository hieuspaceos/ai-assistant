---
name: work-excel
description: Read/write/filter/merge/format .xlsx files with openpyxl — originals untouched, results to new files. Use when the learner needs Excel work done without opening Excel by hand.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Process `.xlsx` files for someone who doesn't code, using Python
`openpyxl`. Golden rule: **NEVER overwrite the original** — read the
original, write to a new file (`<name>-new.xlsx` or a result folder).

## Check the tool (first time)

```bash
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
# Windows: PY=.venv\Scripts\python or py
$PY -c "import openpyxl"
```

Run every python command in this skill with `$PY`. Missing package →
`python3 tools/ensure-deps.py` — builds a private `.venv/` in the data
folder without touching system Python (the launcher also runs it on every
start). Tell them first: *"I need a small Python package to read Excel —
about 30 seconds."*

## Common tasks

| Task | How |
|---|---|
| Read/view content | `load_workbook(file, data_only=True)` → walk sheets/rows |
| Filter rows | iterate `iter_rows`, keep matching rows → write new workbook |
| Merge files | read each → append rows into target workbook (header once) |
| Split by column | group by column value → one file per group (see `/split-customers`) |
| Change format | `cell.font`, `cell.fill`, `column_dimensions[w].width`, `freeze_panes` |
| Add sheet | `wb.create_sheet(name)` |

## Standard steps

1. Ask clearly: which file, what to do, expected result. For big files,
   read the first rows and confirm the structure with them first.
2. Announce in plain words: *"I'll read file X, do Y, write to new file
   Z — the original stays untouched. OK?"*
3. Run a Python script inside the working folder (no scattered scripts —
   write into `workspace/` or the current lesson folder).
4. Verify the result (row count, sample rows) before reporting.
5. Report SHORT and human: *"done — 3,000 rows filtered to 412 in
   `hanoi-customers-new.xlsx`"*. Open the result folder for them.

## Notes

- Old `.xls`: `openpyxl` can't read — convert via `pandas + xlrd` or ask
  them to Save As .xlsx once.
- Formulas: `data_only=True` returns cached values (file must have been
  opened in Excel to cache them); unopened files → `None`, tell them.
- Complex formatting (merged cells, charts, embedded images): `openpyxl`
  preserves most but not everything — for critical files, work on a copy
  and have them open-check it.
