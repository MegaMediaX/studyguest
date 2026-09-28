"""Regression tests for the full-platform review (one per finding)."""
import threading

import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, corpus, encounter, keycheck, progress, run

RIGHT = {"mcq": "B", "numeric": "-1", "expression": "2xy", "multi": "(2, -2, -1)", "short": "CORRECT idea"}
WRONG = {"mcq": "D", "numeric": "12345", "expression": "x + 1", "multi": "(9, 9, 9)", "short": "no idea"}


@pytest.fixture()
def client(imported, monkeypatch):
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    return TestClient(app_mod.app)


def _tid(imported, i=0):
    return imported["plan"]["sessions"][0]["tasks"][i]["id"]


def _ans(c, tid, v, text):
    return c.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": text}).json()


def test_dispute_cannot_be_used_twice_or_concurrently(client, imported):
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    _ans(client, tid, v, WRONG[v["problem"]["type"]])
    body = {"task_id": tid, "idx": v["problem"]["idx"], "answer": "UPHOLD b"}
    results = []
    threads = [threading.Thread(target=lambda: results.append(client.post("/api/battle/dispute", json=body)))
               for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 404]
    enc = progress.load()["encounters"][tid]
    assert len(enc["results"]) == 1 and round(enc["damage"]) == 100


def test_dispute_after_a_fail_regrades_at_second_try_damage(client, imported):
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    idx = v["problem"]["idx"]
    m = _ans(client, tid, v, WRONG[v["problem"]["type"]])
    f = _ans(client, tid, m, WRONG[m["problem"]["type"]])
    assert f["result"] == "fail"
    r = client.post("/api/battle/dispute", json={"task_id": tid, "idx": idx, "answer": "UPHOLD b"}).json()
    assert r["upheld"] and r["damage"] == 50
    assert client.post("/api/battle/dispute", json={"task_id": tid, "idx": idx, "answer": "UPHOLD b"}).status_code == 404


def test_keyboard_style_resubmit_of_a_finished_problem_is_rejected(client, imported):
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    _ans(client, tid, v, RIGHT[v["problem"]["type"]])
    again = client.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": "B"})
    assert again.status_code == 404


def test_off_floor_battles_get_no_perks_and_dont_advance_the_run(client, imported):
    with progress.transaction() as p:
        r = run.start(p, imported["plan"])
        r["perks"] = ["glass_cannon"]
        rid, first, second = r["id"], r["queue"][0]["task_id"], r["queue"][1]["task_id"]
    v = client.post("/api/battle/start", json={"task_id": second, "run_id": rid}).json()
    assert v["run_id"] is None and not v["rules"]["no_hints"]
    while True:
        v = _ans(client, second, v, RIGHT[v["problem"]["type"]])
        if v.get("outcome"):
            break
    assert "run" not in v and progress.load()["run"]["floor"] == 0


def test_source_viewer_rejects_unknown_courses():
    with pytest.raises(KeyError):
        corpus.corpus_path("../secret", "x.pdf")
    assert corpus.corpus_path("MATH202", "../../etc/passwd").name == "_.._etc_passwd.json"


def test_rematches_get_new_problems(client, imported):
    tid = _tid(imported)
    fake = imported["fake"]
    for _ in range(2):  # lose once so the next start is a rematch
        v = client.post("/api/battle/start", json={"task_id": tid}).json()
        while True:
            v = _ans(client, tid, v, WRONG[v["problem"]["type"]])
            v = _ans(client, tid, v, WRONG[v["problem"]["type"]]) if v["result"] == "miss" else v
            if v.get("outcome"):
                break
    prompts = [c[1] for c in fake.calls if c[0] == "claude" and c[1].startswith("You design")]
    assert len(prompts) == 2  # second battle was generated fresh, not served from cache


def test_perks_cannot_replace_correct_answers(client, imported):
    with progress.transaction() as p:
        r = run.start(p, imported["plan"])
        r["perks"] = ["glass_cannon", "deep_focus", "gambit"]
        rid, tid = r["id"], r["queue"][0]["task_id"]
    v = client.post("/api/battle/start", json={"task_id": tid, "run_id": rid}).json()
    answers = []
    for i in range(5):  # 2 right, 3 wrong
        right = i < 2
        v2 = _ans(client, tid, v, RIGHT[v["problem"]["type"]] if right else WRONG[v["problem"]["type"]])
        if v2["result"] == "miss":
            v2 = _ans(client, tid, v2, WRONG[v2["problem"]["type"]])
        answers.append(v2)
        if v2.get("outcome"):
            break
        v = v2
    assert answers[-1]["outcome"] == "escaped" and "right" in answers[-1]["why"]
    assert answers[0]["damage"] == 150  # capped


def test_gambit_needs_the_lesson_skipped(client, imported):
    with progress.transaction() as p:
        r = run.start(p, imported["plan"])
        r["perks"] = ["gambit"]
        rid, tid = r["id"], r["queue"][0]["task_id"]
    v = client.post("/api/battle/start", json={"task_id": tid, "run_id": rid}).json()
    client.post("/api/battle/lesson", json={"task_id": tid})
    assert _ans(client, tid, v, RIGHT[v["problem"]["type"]])["damage"] == 100


def test_worked_solution_pays_nothing_even_with_free_hints(client, imported):
    with progress.transaction() as p:
        r = run.start(p, imported["plan"])
        r["perks"] = ["scholars_lens"]
        rid, tid = r["id"], r["queue"][0]["task_id"]
    v = client.post("/api/battle/start", json={"task_id": tid, "run_id": rid}).json()
    for _ in range(3):
        client.post("/api/battle/hint", json={"task_id": tid, "idx": v["problem"]["idx"]})
    xp = progress.load()["xp"]
    r = _ans(client, tid, v, RIGHT[v["problem"]["type"]])
    assert r["damage"] == 0 and progress.load()["xp"] == xp


def test_unreadable_answers_do_not_cost_an_attempt(client, imported):
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    r = _ans(client, tid, v, "t=")
    assert r["result"] == "unreadable"
    again = client.post("/api/battle/start", json={"task_id": tid}).json()
    assert again["tries"] == 0


def test_unverified_keys_accept_either_answer(imported):
    q = {"type": "numeric", "prompt": "x?", "answer": "3", "choices": None}
    imported["fake"].key_answers = [{"i": 0, "answer": "4"}]
    out = keycheck.verify([q])[0]
    assert out["verified"] is False and keycheck.matches(out, "4") and keycheck.matches(out, "3")
    imported["fake"].key_answers = [{"i": 0, "answer": "3.0"}]
    assert keycheck.verify([{**q, "prompt": "y?"}])[0]["verified"] is True


def test_armored_only_after_a_recall(imported):
    r = {"queue": [{"task_id": "a", "mode": "review"}, {"task_id": "b", "mode": "task"}]}
    assert run.affix_for(r, 0, {"review": {"a": {"box": 0}}}) is None
    assert run.affix_for(r, 0, {"review": {"a": {"box": 1}}}) == "armored"


def test_hint_token_kept_under_glass_cannon(client, imported):
    with progress.transaction() as p:
        r = run.start(p, imported["plan"])
        r["perks"] = ["glass_cannon"]
        rid, tid = r["id"], r["queue"][0]["task_id"]
        p["economy"] = {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {"hint_token": 1}}
    client.post("/api/battle/start", json={"task_id": tid, "run_id": rid})
    assert client.post("/api/battle/token", json={"task_id": tid, "kind": "hint_token"}).status_code == 409
    assert progress.load()["economy"]["consumables"]["hint_token"] == 1


def test_chimera_floor_mixes_topics(client, imported):
    # three earlier battles in the same course → a run gets a mixed final floor
    from studyquest import store
    plan = imported["plan"]
    extra = {"id": "s-extra", "date": "2026-10-01", "date_label": "Thu · 1 Oct", "time": "21:00–22:00",
             "subject": "Calc II", "session": "14.7 Extrema", "tasks": [
                 {"id": "t-extra", "text": "Critical points + 2nd derivative test", "kind": "reading",
                  "imported_done": False}]}
    plan["sessions"].append(extra)
    store.write_json(store.PLAN_FILE, plan)
    with progress.transaction() as p:
        assert run.with_chimera(p, plan, [{"task_id": "a", "mode": "task"}]) == [{"task_id": "a", "mode": "task"}]
    calc = [t["id"] for s in plan["sessions"] if s["subject"] == "Calc II" for t in s["tasks"] if t["kind"] != "action"]
    for tid in calc:
        client.post("/api/battle/start", json={"task_id": tid})
    with progress.transaction() as p:
        for tid in calc:
            p["encounters"][tid]["state"] = "escaped"
        queue = run.with_chimera(p, plan, [{"task_id": calc[0], "mode": "task"}, {"task_id": calc[1], "mode": "task"}])
    assert queue[-1]["mode"] == "chimera"
    with progress.transaction() as p:
        probs = encounter.chimera_problems(p, plan, {"queue": queue})
    assert len({q["from_topic"] for q in probs}) == len(probs) == 3
    assert client.post("/api/battle/start", json={"task_id": queue[-1]["task_id"], "mode": "chimera"}).status_code == 503
    with progress.transaction() as p:
        r = run._new_run(p, queue, "x", "test")
        r["floor"] = len(queue) - 1
        rid = r["id"]
    v = client.post("/api/battle/start", json={"task_id": queue[-1]["task_id"], "mode": "chimera", "run_id": rid}).json()
    assert v["enemy"].startswith("Chimera") and v["problem"]["from"]


def test_run_preview_lists_floors(client):
    q = client.get("/api/run/preview").json()["queue"]
    assert len(q) >= 1


def test_rest_bonus_once_a_day(client):
    assert client.post("/api/rest").json()["events"][0]["type"] == "shard"
    assert client.post("/api/rest").json()["events"] == []


def test_run_skips_floors_already_cleared_elsewhere(client, imported):
    with progress.transaction() as p:
        r = run.start(p, imported["plan"])
        first, rid = r["queue"][0]["task_id"], r["id"]
        progress.record_pass(p, imported["plan"], first, first_try=True)
    out = client.post("/api/battle/start", json={"task_id": first, "run_id": rid}).json()
    assert out["state"] == "already_done" and out["run"]["floor"] == 1
    assert client.get("/api/run").json()["run"]["floor"] == 1
