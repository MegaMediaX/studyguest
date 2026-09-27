# StudyQuest

A local, game-like study app for short-attention study sessions. You don't tick tasks yourself: you
earn the tick by passing a quick check written from your own course files. Claude (`claude -p`) writes
and grades the checks. Gemini (`agy -p`) gives second opinions and alternative explanations.
No API keys are needed.

## Start

    ./start.sh            # first run creates .venv and installs requirements, then opens http://localhost:8765

You need the `claude` CLI logged in (`claude`, then `/login`). `agy` is optional: without it, the Gemini
features switch off.

## Import your plan

Put `study_checklist.csv` (columns `Done, Date, Time, Subject, Session, Task`) next to `start.sh`. It's
imported automatically on first start. To re-import later, use Stats → Import, or run
`/quest-import <file>` in Claude Code. A Google Sheets CSV export or a markdown checklist
(`## Mon 28 Sep · 21:00–22:00 · Calc II · Topic` followed by `- [ ] task` lines) also works.

Course folders (`MATH202 - Calculus II/`, …) go next to it too. Map them in `config.json`, then run:

    .venv/bin/python -m studyquest.corpus          # extract text
    .venv/bin/python -m studyquest.corpus --ocr    # OCR scanned pages once (cached)

## How to play

1. **Quest** shows today's floor. Press **▶ Start a run**: up to 4 enemies (floor 1 is a due rematch, the last one is an elite that demands a written proof).
2. Each battle opens with a 1-minute lesson scroll. **📖 Read the course pages here** shows the real PDF pages inside the app, so you don't need another window.
3. Solve the problems on paper and type the answer. Numbers, expressions, points and multiple choice are graded instantly. Right answers deal damage, 3 in a row gives crits, and hints cost damage, never XP.
4. Between floors you pick 1 of 3 perks. Five clean hits in a row give a key shard; 3 shards make a key, and a key opens a chest (odds shown, nothing to buy). Daily bounties give shards too.
5. Lose a fight and you keep your XP. The enemy comes back as a rematch with fresh problems, and on rematches your ghost shows how your past self did. **Export CSV** puts the `Done` column back into your Google Sheet.

Terminal: `/quest-today`, `/quest-check <task>`, `/quest-status`, `/quest-import <file>`, `/quest-export`.

The research behind the design is in [docs/research.md](docs/research.md). Rules for maintainers and for Claude are in [CLAUDE.md](CLAUDE.md).
