---
description: Run the done-check for a task, right here in the terminal
argument-hint: <task text or id>
---
Run a StudyQuest done-check for: $ARGUMENTS

1. Run `.venv/bin/python -m studyquest.cli check-start "$ARGUMENTS"` and read the JSON.
   - If `status` is `already_done`, say so and stop.
   - If there is a `notice`, show it.
2. Show me the questions one by one, with the 📄 source under each. Do NOT reveal or hint at answers.
   Wait for my answers. If I want to send a photo of my working, take its file path.
3. Submit: `.venv/bin/python -m studyquest.cli check-submit <check_id> -a "<answer 1>" -a "<answer 2>" ...`
   (add `--photo <path>` if I gave one). Quote each answer safely for the shell.
4. Handle the result:
   - `passed`: celebrate briefly and show the XP events.
   - `retry`: show the hint (max 3 sentences), wait until I say I'm ready (at least 60 s), then ask the
     same questions again and resubmit with the same check_id. If you get `wait`, tell me the seconds left.
   - `disagree`: show Claude's and Gemini's score + reason side by side, ask me to pick, then run
     `.venv/bin/python -m studyquest.cli resolve <check_id> claude|gemini`.
   - `review_later`: say it comes back tomorrow (then 3 and 7 days), and show the reference answers.

Never mark a task done any other way. If I insist, the only path is a logged manual override:
`.venv/bin/python -m studyquest.cli override "<task>" --reason "<my reason>"` (0 XP).
