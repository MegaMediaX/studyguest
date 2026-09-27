---
description: Import a checklist (CSV, Google Sheets CSV export, or markdown)
argument-hint: <file>
---
Import the checklist at: $ARGUMENTS

Run `.venv/bin/python -m studyquest.cli import "$ARGUMENTS"` and report how many sessions and tasks were imported.
Progress is keyed by task id, so re-importing the same plan keeps existing progress. Rows marked Done=TRUE
in the file become logged overrides (0 XP). If the import fails, show the error and the expected columns:
`Done, Date, Time, Subject, Session, Task` (CSV) or `## <date> · <time> · <subject> · <session>` headings
with `- [ ] task` lines (markdown).
