# StudyQuest: how to run and manage it

StudyQuest is Marven's local, game-like study app (Mechatronics). Claude Code is the game master:
it runs the app, answers the `/quest-*` commands, and tutors. Gemini (`agy -p`) is the second opinion.

## Run

    ./start.sh                          # http://localhost:8765 (local only)
    .venv/bin/python -m pytest -q       # tests (fake AI, throwaway data dir)

## Layout

| Path | What |
|---|---|
| `studyquest/importer.py` | CSV / Google Sheets CSV / markdown checklist → `data/plan.json`; classifies tasks |
| `studyquest/progress.py` | `data/progress.json`: status, XP, levels, streaks + weekly freeze, overrides, "where was I" |
| `studyquest/checker.py` | the done-check: questions → grade → pass / hint + retry / 🔁 review |
| `studyquest/review.py` | Leitner spaced review (1/3/7 days), interleaving, daily 3 quick wins |
| `studyquest/boss.py` | timed mock exam built from past exams |
| `studyquest/quest.py` | today's quest, session verdict, map, stats, CSV export |
| `studyquest/ai.py` | the only place that calls `claude -p` / `agy -p` (timeouts, retries, cache) |
| `studyquest/corpus.py` | course files → `data/corpus/`; OCR of scanned pages; retrieval |
| `studyquest/cli.py` | terminal entry used by `.claude/commands/quest-*.md` |
| `config.json` | courses, file aliases (Fares, Farah, textbook), exam dates, bosses, AI thresholds |
| `docs/research.md` | evidence behind each ADHD design choice, with verified citations |

## Data files (human-readable JSON, never commit `data/`)

- `data/plan.json`: sessions → tasks. Task id = `sha1(date|session|task|occurrence)`, so re-imports keep progress.
- `data/progress.json`: `tasks[id].status` ∈ `todo | done | review | override`, `xp`, `sprint_days`,
  `review` (Leitner cards), `overrides` (with reasons), `checks` (open done-checks), `log`.
- `data/corpus/<COURSE>/<file>.json`: per page/slide text, `src` = `text | ocr | none`.
- `data/cache/`: AI replies keyed by prompt hash. Safe to delete (costs regeneration).

## Rules (don't break these)

1. **A task is done only through a passed check** (`checker.submit` → `progress.record_pass`) or a
   **manual override** (`progress.manual_override`): logged with a reason, 0 XP, no session bonus.
   Never edit `progress.json` by hand to mark something done.
2. Pass ≥ 70%. Fail → one hint (max 3 sentences, never the answer) + 60 s, then retry. Second fail → 🔁,
   Leitner box 0 (back tomorrow, then 3, then 7 days).
3. Gemini grades again when Claude's score is 0.55–0.85 or its confidence < 0.7. If one passes and
   the other fails, Marven picks; the pick is logged.
4. XP: +10 first try, +5 retry or review, +20 full session, +50 boss (once). Never subtract XP.
   Streak = a day with ≥ 1 sprint; one missed day per ISO week is bridged free.
5. Questions must cite file + page/slide from the provided sources; invalid citations are dropped.
   If a named file is scanned without OCR text, say so. Don't guess its content.
6. Hints and "stuck" steps: max 3 sentences. Explanations: max 5.
7. `ai.py` runs the CLIs in a temp cwd with `disableAllHooks`, so app calls never trigger the
   SessionEnd work-log hook. Keep it that way.
8. Show one session at a time; only show the full plan when asked.

## Common jobs

    .venv/bin/python -m studyquest.cli import study_checklist.csv    # (re)import the plan
    .venv/bin/python -m studyquest.corpus                            # re-extract after new Moodle files
    .venv/bin/python -m studyquest.corpus --ocr                      # OCR scanned pages (cached, resumable)
    .venv/bin/python -m studyquest.corpus --status                   # which files have no text
    .venv/bin/python -m studyquest.cli status

To test against another date: `STUDYQUEST_TODAY=2026-10-04`. To use a scratch data dir: `STUDYQUEST_DATA=/tmp/x`.
New exam or boss: edit `config.json` (`exams`, `bosses`). New course: add it under `courses` with its folder.
