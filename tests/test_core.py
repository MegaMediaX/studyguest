"""Unit tests: import, classification, XP/levels, streaks, Leitner, export, AI wrapper."""
from datetime import date

import pytest

from studyquest import ai, importer, progress, quest, review, store


@pytest.mark.skipif(not (store.ROOT / "study_checklist.csv").exists(), reason="personal checklist not in repo")
def test_import_real_checklist_counts(env):
    plan = importer.import_file(store.ROOT / "study_checklist.csv")
    tasks = list(importer.all_tasks(plan))
    assert len(plan["sessions"]) == 31
    assert len(tasks) == 147
    assert len({t["id"] for _, t in tasks}) == 147


def test_parse_date_formats():
    assert importer.parse_date("Sat · 26 Sep", 2026) == "2026-09-26"
    assert importer.parse_date("2026-10-08", 2026) == "2026-10-08"
    assert importer.parse_date("08/10/2026", 2026) == "2026-10-08"
    assert importer.parse_date("Oct 8", 2026) == "2026-10-08"
    assert importer.parse_date("", 2026) is None


@pytest.mark.parametrize("text,kind", [
    ("Read ch2-Trans-M.pptx slides 23–31", "reading"),
    ("Textbook 14.5: 2,10,14", "exercise"),
    ("Do Farah Q5–Q7", "exercise"),
    ("Ask Dr. Chanbour: Quiz 2 day + scope", "action"),
    ("Write 1-page Chapter 1 formula sheet", "produce"),
    ("Y-Y ratio a + its 2 problems and fixes", "reading"),
])
def test_classify(text, kind):
    assert importer.classify(text) == kind


def test_markdown_import(env):
    md = env["tmp"] / "plan.md"
    md.write_text("## Mon 28 Sep · 21:00–22:00 · Calc II · Gradient\n- [ ] Tangent plane\n- [x] Read notes\n")
    plan = importer.import_file(md)
    s = plan["sessions"][0]
    assert (s["date"], s["subject"], s["session"]) == ("2026-09-28", "Calc II", "Gradient")
    assert [t["imported_done"] for t in s["tasks"]] == [False, True]


def test_duplicate_task_lines_get_distinct_ids(env):
    rows = [{"done": False, "date": "2026-09-28", "date_label": "", "time": "", "subject": "S", "session": "X",
             "task": "Same"}] * 2
    plan = importer.rows_to_plan(rows, "x")
    ids = [t["id"] for t in plan["sessions"][0]["tasks"]]
    assert len(set(ids)) == 2


def test_imported_done_becomes_logged_override_without_xp(imported):
    p = progress.load()
    assert len(p["overrides"]) == 1 and p["overrides"][0]["reason"] == "imported as done"
    assert p["xp"] == 0


def test_levels():
    assert progress.level_for(0)["level"] == 1
    assert progress.level_for(99)["level"] == 1
    assert progress.level_for(100)["level"] == 2
    assert progress.level_for(300)["level"] == 3


def test_xp_first_try_retry_and_session_bonus(imported):
    p, plan = progress.load(), imported["plan"]
    s = plan["sessions"][0]
    a, b, c = (t["id"] for t in s["tasks"])
    progress.record_pass(p, plan, a, first_try=True)
    progress.record_pass(p, plan, b, first_try=False)
    assert p["xp"] == 15
    events = progress.record_pass(p, plan, c, first_try=True)
    assert any(e["type"] == "session_complete" and e["bonus"] == 20 for e in events)
    assert p["xp"] == 45
    assert progress.record_pass(p, plan, a, first_try=True) == []  # no double XP


def test_override_needs_reason_gives_no_xp_and_no_session_bonus(imported):
    p, plan = progress.load(), imported["plan"]
    s = plan["sessions"][0]
    with pytest.raises(ValueError):
        progress.manual_override(p, plan, s["tasks"][0]["id"], "  ")
    for t in s["tasks"]:
        progress.manual_override(p, plan, t["id"], "did it on paper")
    assert p["xp"] == 0 and s["id"] not in p["sessions_awarded"]
    assert len(p["overrides"]) == 1 + 3  # the imported TRUE row + 3


def test_streak_with_weekly_freeze():
    p = {"sprint_days": ["2026-09-24", "2026-09-25", "2026-09-27", "2026-09-28"]}
    info = progress.streak_info(p, date(2026, 9, 28))
    assert info["current"] == 4  # 26 Sep bridged by the week's free freeze
    p = {"sprint_days": ["2026-09-24", "2026-09-27", "2026-09-28"]}
    assert progress.streak_info(p, date(2026, 9, 28))["current"] == 2  # two missed days: broken
    p = {"sprint_days": ["2026-09-27"]}
    assert progress.streak_info(p, date(2026, 9, 28))["current"] == 1  # today not over yet


def test_leitner_boxes(imported, monkeypatch):
    p, plan = progress.load(), imported["plan"]
    tid = plan["sessions"][0]["tasks"][0]["id"]
    review.on_fail(p, plan, tid)
    assert p["tasks"][tid]["status"] == "review" and p["review"][tid]["due"] == "2026-09-29"
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-09-29")
    review.on_pass(p, plan, tid)
    assert p["review"][tid]["box"] == 1 and p["review"][tid]["due"] == "2026-10-01"
    assert p["tasks"][tid]["status"] == "done" and p["xp"] == 5
    review.on_pass(p, plan, tid)  # same day again: no box jump (spaced, not massed)
    assert p["review"][tid]["box"] == 1
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-10-01")
    review.on_pass(p, plan, tid)
    assert p["review"][tid]["box"] == 2 and p["review"][tid]["due"] == "2026-10-05"
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-10-05")
    events = review.on_pass(p, plan, tid)
    assert tid not in p["review"] and events[0]["type"] == "graduated"
    assert p["xp"] == 5  # already done: no extra XP on graduation


def test_interleave_avoids_same_topic_in_a_row():
    cards = [{"topic": t, "task_id": str(i)} for i, t in enumerate("AAABBBCCC")]
    out = review.interleave(cards, seed=1)
    assert all(out[i]["topic"] != out[i + 1]["topic"] for i in range(len(out) - 1))


def test_today_quest_and_verdict(imported):
    p, plan = progress.load(), imported["plan"]
    t = quest.today_quest(p, plan)
    assert t["label"] == "today" and t["session"]["session"].startswith("14.5")
    v = quest.verdict(p, plan, t["session"]["id"])
    assert not v["complete"] and v["headline"] == "⚠️ 3 tasks left"
    assert v["slot"]["date"] == "2026-09-30"  # next Calc II session


def test_export_roundtrip(imported):
    p, plan = progress.load(), imported["plan"]
    tid = plan["sessions"][0]["tasks"][0]["id"]
    progress.record_pass(p, plan, tid, first_try=True)
    lines = quest.export_csv(p, plan).splitlines()
    assert lines[0] == "Done,Date,Time,Subject,Session,Task"
    assert lines[1].startswith("TRUE,Mon · 28 Sep")
    assert lines[5].startswith("TRUE,Tue")  # imported TRUE stays TRUE
    assert sum(l.startswith("TRUE") for l in lines) == 2


def test_ai_parse_json_reply():
    assert ai.parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai.parse_json_reply('Sure! {"a": 2} done') == {"a": 2}
    with pytest.raises(ValueError):
        ai.parse_json_reply("no json")


def test_ai_cache_and_hint_cap(env):
    r1 = ai.ask("claude", "Explain the idea behind X")
    r2 = ai.ask("claude", "Explain the idea behind X")
    assert r1 == r2 and len(env["fake"].calls) == 1
    assert ai.short("One. Two. Three. Four.") == "One. Two. Three."


def test_ai_retries_then_raises(env, monkeypatch):
    calls = []

    def broken(provider, prompt, images):
        calls.append(1)
        return "not json"
    monkeypatch.setattr(ai, "runner", broken)
    with pytest.raises(ai.AIUnavailable):
        ai.ask("claude", "x", cache=False)
    assert len(calls) == 3


def test_claude_cmd_disables_hooks_and_tools():
    cmd = ai.claude_cmd([])
    assert "--settings" in cmd and "disableAllHooks" in cmd[cmd.index("--settings") + 1]
    assert cmd[cmd.index("--tools") + 1] == ""


def test_review_due_dates_never_pass_the_exam(imported, monkeypatch):
    p, plan = progress.load(), imported["plan"]
    tid = plan["sessions"][0]["tasks"][0]["id"]  # Calc II → MATH202 Exam I on 2026-10-08
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-10-05")
    review.on_fail(p, plan, tid)
    review.on_pass(p, plan, tid)
    review.on_pass(p, plan, tid)
    assert p["review"][tid]["due"] <= "2026-10-07"


def test_wins_are_scheduled_for_review(imported):
    p, plan = progress.load(), imported["plan"]
    tid = plan["sessions"][0]["tasks"][0]["id"]
    progress.record_pass(p, plan, tid, first_try=True)
    assert review.schedule(p, plan, tid)[0]["due"] == "2026-09-29"
    assert review.schedule(p, plan, tid) == []  # no duplicate card
