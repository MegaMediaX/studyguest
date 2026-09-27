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

1. Open **Quest**: one task card. Press **Start**, write your first step, and a 12-minute sprint begins.
2. When the timer ends, take the break, then **Check**: answer 2–3 recall questions (or give a final answer / photo).
3. Pass at 70% or more for ✅ and XP. A miss gives you a hint, 60 s, and one retry. Two misses make it 🔁, and it comes back in 1, 3 and 7 days.
4. Stuck? **I'm stuck** gives the smallest next step. **Explain differently** asks Gemini for another angle.
5. End of session: the verdict shows what's left and where to fit it. **Export CSV** puts the `Done` column back into your Google Sheet.

Terminal: `/quest-today`, `/quest-check <task>`, `/quest-status`, `/quest-import <file>`, `/quest-export`.

The research behind the design is in [docs/research.md](docs/research.md). Rules for maintainers and for Claude are in [CLAUDE.md](CLAUDE.md).
