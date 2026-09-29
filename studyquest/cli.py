"""Terminal entry point used by the /quest-* slash commands.

    .venv/bin/python -m studyquest.cli today
    .venv/bin/python -m studyquest.cli status
    .venv/bin/python -m studyquest.cli import study_checklist.csv
    .venv/bin/python -m studyquest.cli export
    .venv/bin/python -m studyquest.cli check "gradient"            # interactive in a real terminal
    .venv/bin/python -m studyquest.cli check-start "gradient"      # non-interactive: prints questions
    .venv/bin/python -m studyquest.cli check-submit <check_id> -a "answer 1" -a "answer 2" [--photo img.jpg]
    .venv/bin/python -m studyquest.cli resolve <check_id> claude|gemini
    .venv/bin/python -m studyquest.cli override <task> --reason "why"
"""
import argparse
import json
import sys

from . import ai, checker, importer, progress, quest, store


def _out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def find_task(query: str) -> tuple[dict, dict]:
    """Task id, or a case-insensitive substring; today's session wins ties, then the earliest open task."""
    p, plan = progress.load(), progress.load_plan()
    q = query.strip().lower()
    hits = [(s, t) for s, t in importer.all_tasks(plan) if t["id"] == q or q in t["text"].lower()]
    if not hits:
        raise SystemExit(f"No task matches “{query}”.")
    today = store.today().isoformat()
    hits.sort(key=lambda st: (st[0]["date"] != today, progress.is_done(p, st[1]["id"]), st[0]["date"] or ""))
    return hits[0]


def cmd_today(_a) -> None:
    p, plan = progress.load(), progress.load_plan()
    t = quest.today_quest(p, plan)
    s = t["session"]
    if not s:
        print("No sessions left in the plan.")
        return
    print(f"{'TODAY' if t['label'] == 'today' else 'NEXT'} · {s['date_label']} · {s['time']} · {s['subject']}")
    print(f"  {s['session']}  ({s['total'] - s['left']}/{s['total']} done)")
    for task in s["tasks"]:
        print(f"  {task['icon']} {task['text']}   [{task['kind']}, id {task['id']}]")
    if t["backlog"]["tasks"]:
        print(f"\n  {t['backlog']['tasks']} earlier task(s) still open in {t['backlog']['sessions']} session(s).")
    if t["review_due"]:
        print(f"  🔁 {t['review_due']} review card(s) due.")
    v = quest.verdict(p, plan, s["id"])
    print(f"\n  {v['headline']}" + (f" · {v.get('suggestion', '')}" if not v["complete"] else ""))


def cmd_status(_a) -> None:
    p, plan = progress.load(), progress.load_plan()
    st = quest.stats(p, plan)
    lv, sk = st["level"], st["streak"]
    print(f"Level {lv['level']} · {lv['xp']} XP ({lv['span'] - lv['into']} to next)")
    print(f"Streak 🔥 {sk['current']} (best {sk['best']}){' · ❄️ freeze available' if sk['freeze_available'] else ''}")
    c = st["counts"]
    print(f"Tasks: ✅ {c['done']}  ☑️ {c['override']} override  🔁 {c['review']}  ⬜ {c['todo']}  of {st['total']}")
    print(f"Review due: {st['review_due']}")
    open_sessions = [s for s in plan["sessions"] if progress.session_left(p, s) and s["date"]
                     and s["date"] <= store.today().isoformat()]
    if open_sessions:
        print("Left (up to today):")
        for s in open_sessions:
            print(f"  {s['date_label']:14} {s['session'][:48]:48} {len(progress.session_left(p, s))} left")
    print("Exams:")
    for e in st["exams"]:
        print(f"  {e['name']:18} {e['date']}  in {e['days']} day(s)")
    ai_st = ai.status()
    for name, v in ai_st.items():
        print(f"AI {name}: {'ok' if v['ok'] else v['why']}")


def cmd_import(a) -> None:
    plan = importer.import_file(a.file)
    p = progress.sync_with_plan(progress.load(), plan)
    progress.save(p)
    print(f"Imported {len(plan['sessions'])} sessions, {sum(len(s['tasks']) for s in plan['sessions'])} tasks "
          f"into {store.PLAN_FILE}")


def cmd_export(_a) -> None:
    p, plan = progress.load(), progress.load_plan()
    print(f"Wrote {quest.write_export(p, plan)} (paste into Google Sheets: File → Import → Replace sheet)")


def cmd_check_start(a) -> None:
    s, t = find_task(a.task)
    _out(checker.start(t["id"], "review" if a.review else "task"))


def cmd_check_submit(a) -> None:
    _out(checker.submit(a.check_id, a.answer or [], a.photo))


def cmd_resolve(a) -> None:
    _out(checker.resolve(a.check_id, a.pick))


def cmd_override(a) -> None:
    _, t = find_task(a.task)
    p, plan = progress.load(), progress.load_plan()
    events = progress.manual_override(p, plan, t["id"], a.reason)
    progress.save(p)
    _out({"task": t["text"], "events": events})


def cmd_check(a) -> None:
    """Interactive done-check for a real terminal."""
    s, t = find_task(a.task)
    r = checker.start(t["id"])
    if r["status"] == "already_done":
        print("Already done ✅")
        return
    print(f"\n{t['text']}  ({t['kind']})")
    if r.get("notice"):
        print(f"⚠ {r['notice']}")
    while True:
        answers = []
        for i, q in enumerate(r["questions"], 1):
            print(f"\n{i}. {q['q']}" + (f"\n   📄 {q['source']}" if q["source"] else ""))
            answers.append(input("   > "))
        res = checker.submit(r["check_id"], answers)
        if res["status"] == "wait":
            input(f"Hint time: {res['seconds']}s left. Press Enter to continue…")
            continue
        if res["status"] == "disagree":
            print(f"\nClaude {res['claude']['score']:.0%}: {res['claude']['reason']}")
            print(f"Gemini {res['gemini']['score']:.0%}: {res['gemini']['reason']}")
            pick = ""
            while pick not in {"claude", "gemini"}:
                pick = input("Which grade is fair? (claude/gemini) ").strip().lower()
            res = checker.resolve(r["check_id"], pick)
        print(f"\n{res['status'].upper()} · {res['score']:.0%} · {res['reason']}")
        if res["status"] == "retry":
            print(f"💡 {res['hint']}")
            input(f"Take {res['hint_seconds']}s with the hint, then press Enter to retry…")
            continue
        for e in res.get("events", []):
            print("  ", e)
        if res["status"] == "review_later":
            print("Reference answers:", *res["answers"], sep="\n  ")
        return


def cmd_pregen(a) -> None:
    """Build (and cache) the first battle of every open task in a course, so each opens instantly."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from . import encounter
    from .corpus import course_for_subject
    p, plan = progress.load(), progress.load_plan()
    todo = [(s, t) for s, t in importer.all_tasks(plan) if course_for_subject(s["subject"]) == a.course
            and t["kind"] != "action" and not progress.is_done(p, t["id"]) and (not a.until or (s["date"] or "") <= a.until)]
    print(f"Pre-generating {len(todo)} {a.course} battles, {a.workers} at a time (cached; safe to stop and rerun)")

    def one(st):
        s, t = st
        prev = p.get("encounters", {}).get(t["id"]) or {}
        mode = "review" if t["id"] in p.get("review", {}) and progress.is_done(p, t["id"]) else "task"
        encounter.generate(t, s, encounter.variant_for(prev.get("attempt", 0) + 1, mode))
        return t["text"]
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(one, st): st for st in todo}
        for f in as_completed(futs):
            done += 1
            try:
                print(f"  [{done}/{len(todo)}] ok  {f.result()[:60]}", flush=True)
            except Exception as e:  # noqa: BLE001 - keep going; the app will retry on open
                print(f"  [{done}/{len(todo)}] ERR {futs[f][1]['text'][:50]}: {e}", flush=True)


def main(argv: list[str] | None = None) -> None:
    store.ensure_dirs()
    ap = argparse.ArgumentParser(prog="studyquest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("today").set_defaults(fn=cmd_today)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("export").set_defaults(fn=cmd_export)
    x = sub.add_parser("import"); x.add_argument("file"); x.set_defaults(fn=cmd_import)
    x = sub.add_parser("check"); x.add_argument("task"); x.set_defaults(fn=cmd_check)
    x = sub.add_parser("check-start"); x.add_argument("task"); x.add_argument("--review", action="store_true")
    x.set_defaults(fn=cmd_check_start)
    x = sub.add_parser("check-submit"); x.add_argument("check_id"); x.add_argument("-a", "--answer", action="append")
    x.add_argument("--photo"); x.set_defaults(fn=cmd_check_submit)
    x = sub.add_parser("resolve"); x.add_argument("check_id"); x.add_argument("pick", choices=["claude", "gemini"])
    x.set_defaults(fn=cmd_resolve)
    x = sub.add_parser("pregen"); x.add_argument("--course", default="MATH202"); x.add_argument("--workers", type=int, default=2)
    x.add_argument("--until", help="only sessions up to this date (YYYY-MM-DD)"); x.set_defaults(fn=cmd_pregen)
    x = sub.add_parser("override"); x.add_argument("task"); x.add_argument("--reason", required=True)
    x.set_defaults(fn=cmd_override)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except (FileNotFoundError, ai.AIUnavailable, KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
