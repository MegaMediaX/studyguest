"""Regression tests for the second full-platform review."""
import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, encounter, progress, quest, review, run, store

RIGHT = {"mcq": "B", "numeric": "-1", "expression": "2xy", "multi": "(2, -2, -1)", "short": "CORRECT idea"}
WRONG = {"mcq": "D", "numeric": "12345", "expression": "x + 1", "multi": "(9, 9, 9)", "short": "no idea"}


@pytest.fixture()
def client(imported, monkeypatch):
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    return TestClient(app_mod.app)


def _tid(imported, i=0):
    return imported["plan"]["sessions"][0]["tasks"][i]["id"]


def _ans(c, tid, v, text, **kw):
    return c.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": text, **kw}).json()


def test_copying_worked_solutions_cannot_win(client, imported):
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    while True:
        for _ in range(3):
            client.post("/api/battle/hint", json={"task_id": tid, "idx": v["problem"]["idx"]})
        v = _ans(client, tid, v, RIGHT[v["problem"]["type"]])
        if v.get("outcome"):
            break
    assert v["outcome"] == "escaped"


def test_mcq_second_try_does_not_count_toward_the_win(imported):
    enc = {"problems": [{}] * 5, "results": [
        {"correct": True, "solved": False, "tries": 2}, {"correct": True, "solved": True, "tries": 1},
        {"correct": True, "solved": True, "tries": 1}, {"correct": False, "solved": False, "tries": 2},
        {"correct": False, "solved": False, "tries": 2}]}
    assert encounter._correct_count(enc) == 2 and not encounter.won(enc)


@pytest.mark.parametrize("today,expect_max", [("2026-10-05", "2026-10-06"), ("2026-10-06", "2026-10-07"),
                                              ("2026-10-07", "2026-10-07")])
def test_review_never_lands_on_or_after_exam_day(imported, monkeypatch, today, expect_max):
    monkeypatch.setenv("STUDYQUEST_TODAY", today)
    tid = _tid(imported)  # Calc II → exam 2026-10-08
    for days in (1, 2, 4):
        assert review._due(days, imported["plan"], tid) <= expect_max


def test_upheld_dispute_after_fail_removes_the_deck_card(client, imported):
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    idx = v["problem"]["idx"]
    m = _ans(client, tid, v, WRONG[v["problem"]["type"]])
    _ans(client, tid, m, WRONG[m["problem"]["type"]])
    assert len(progress.load().get("problem_cards", {})) == 1
    r = client.post("/api/battle/dispute", json={"task_id": tid, "idx": idx, "answer": "UPHOLD b"}).json()
    assert r["upheld"] and progress.load().get("problem_cards", {}) == {}


def test_malformed_ai_lists_do_not_crash():
    q = {"prompt": "2+2?", "type": "numeric", "answer": "4", "traps": 5, "hints": True, "rule": {"x": 1}}
    out = encounter._validate_problem(q)
    assert out["traps"] == [] and out["hints"] == [] and out["rule"] == ""


def test_chimera_is_random_per_run(imported):
    plan = imported["plan"]
    extra = [{"id": f"s{i}", "date": "2026-10-0%d" % (i + 1), "date_label": "", "time": "", "subject": "Calc II",
              "session": f"Topic {i}", "tasks": [{"id": f"t{i}", "text": "x", "kind": "reading", "imported_done": False}]}
             for i in range(6)]
    plan["sessions"] += extra
    p = progress.load()
    p["encounters"] = {f"t{i}": {"problems": [{"prompt": f"P{i}-{j}", "difficulty": 2, "type": "numeric", "answer": "1",
                                               "hints": [], "explain": "", "source": None} for j in range(3)]}
                       for i in range(6)}
    a = encounter.chimera_problems(p, plan, {"id": "run-a", "queue": [{"task_id": "t0", "mode": "task"}]})
    b = encounter.chimera_problems(p, plan, {"id": "run-b", "queue": [{"task_id": "t0", "mode": "task"}]})
    assert len(a) == 5 and len({q["from_topic"] for q in a}) == 5
    assert [q["prompt"] for q in a] != [q["prompt"] for q in b]


def test_clean_wins_get_one_confirmation_card_shaky_wins_start_over(imported):
    p, plan = progress.load(), imported["plan"]
    review.schedule(p, plan, _tid(imported, 0), stars=3)
    review.schedule(p, plan, _tid(imported, 1), stars=1)
    assert p["review"][_tid(imported, 0)]["box"] == 2 and p["review"][_tid(imported, 1)]["box"] == 0


def test_deck_daily_cap_and_shuffled_choices(imported, monkeypatch):
    p = progress.load()
    card = {"id": "c1", "task_id": None, "topic": "T", "box": 0, "due": "2026-09-28",
            "problem": {"type": "mcq", "prompt": "Pick", "answer": 1, "choices": ["a", "b", "c", "d"], "explain": "",
                        "hints": [], "rule": "", "traps": [], "alt_answers": []}}
    p["problem_cards"] = {"c1": card}
    p["log"] = [{"at": "2026-09-28T10:00:00", "event": "deck_answer", "task_id": None}] * 10
    assert review.due_problem_cards(p) == []  # daily budget used
    p["log"] = []
    shown = review.public_card(review.due_problem_cards(p)[0])
    progress.save(p)
    pick = shown["choice_ids"][shown["choices"].index("b")] + 1  # the client sends the original index
    assert review.answer_problem_card("c1", str(pick))["result"] == "right"


def test_mock_days_are_offered(imported, monkeypatch):
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-10-06")
    m = quest.mock_today(progress.load())
    assert m and m["number"] == 2 and m["minutes"] == 75


def test_sending_without_working_goes_to_the_deck(client, imported, monkeypatch):
    monkeypatch.setattr(encounter, "WORK_REQUIRED_COURSES", {"MATH202"})
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    while not v["problem"]["work_required"]:
        v = _ans(client, tid, v, RIGHT[v["problem"]["type"]])
    _ans(client, tid, v, RIGHT[v["problem"]["type"]], no_work=True)
    assert len(progress.load().get("problem_cards", {})) == 1


def test_runs_have_one_rematch_at_most(imported):
    assert run.MAX_REVIEWS == 1


def test_deck_grading_survives_midnight(imported, monkeypatch):
    p = progress.load()
    p["problem_cards"] = {"c1": {"id": "c1", "task_id": None, "topic": "T", "box": 0, "due": "2026-09-28",
                                 "problem": {"type": "mcq", "prompt": "Pick", "answer": 1, "choices": ["a", "b", "c", "d"],
                                             "explain": "", "hints": [], "rule": "", "traps": [], "alt_answers": []}}}
    progress.save(p)
    shown = review.public_card(review.due_problem_cards(progress.load())[0])
    pick = shown["choice_ids"][shown["choices"].index("b")] + 1
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-09-29")  # answered after midnight
    assert review.answer_problem_card("c1", str(pick))["result"] == "right"


def test_clean_zone_can_be_sealed_via_deck_recall(imported):
    from studyquest import world
    p, plan = progress.load(), imported["plan"]
    tids = [t["id"] for s in plan["sessions"] if s["subject"] == "Calc II" and s["session"].startswith(("14.5", "14.6"))
            for t in s["tasks"]]
    for t in tids:
        progress.record_pass(p, plan, t, first_try=True)
    progress.log(p, "deck_answer", tids[0], correct=True)
    gorge = next(z for r in world.build(p, plan) for z in r["zones"] if z["id"] == "gradient-gorge")
    assert gorge["state"] == "sealed"


def test_second_wind_mcq_guess_is_not_solved(client, imported):
    with progress.transaction() as p:
        r = run.start(p, imported["plan"])
        r["perks"] = ["second_wind"]
        rid, tid = r["id"], r["queue"][0]["task_id"]
    v = client.post("/api/battle/start", json={"task_id": tid, "run_id": rid}).json()
    assert v["problem"]["type"] == "mcq"
    _ans(client, tid, v, "D")
    r2 = _ans(client, tid, v, "B")
    assert r2["result"] == "hit" and any("second pick" in n for n in r2["notes"])
    res = progress.load()["encounters"][tid]["results"][-1]
    assert res["solved"] is False


def test_run_summary_minutes_are_battle_time(imported):
    p = {"run": {"id": "r", "session": "s", "queue": [{"task_id": "a", "mode": "task"}], "floor": 1, "perks": [],
                 "offer": [], "state": "active", "started": 0, "log": [{"task_id": "a", "enemy": "x", "won": True,
                                                                        "stars": 2, "minutes": 7}]}, "log": []}
    assert run.finish(p)["summary"]["minutes"] == 7
