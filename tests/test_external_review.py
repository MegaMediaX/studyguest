"""Regression tests for the external (game dev / ADHD teacher / researcher) review."""
import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, boss, encounter, keycheck, mathcheck, progress, review, store

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


@pytest.mark.parametrize("kind,text,key,ok", [
    ("numeric", "idk", "3", False), ("numeric", "two", "3", False), ("numeric", "one, one", "3", False),
    ("numeric", "x", "3", False), ("numeric", "sqrt(2)/2", "1", True),
    ("expression", "idk", "2*x*y", False), ("expression", "2xy", "2*x*y", True),
    ("multi", "(1, two)", "(1, 2)", False), ("multi", "(1, -2)", "(1, 2)", True),
])
def test_words_and_tuples_are_unreadable(kind, text, key, ok):
    assert mathcheck.readable(kind, text, None, key) is ok


def test_all_correct_on_second_tries_still_wins(client, imported):
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    while True:
        m = _ans(client, tid, v, WRONG[v["problem"]["type"]])
        r = _ans(client, tid, m, RIGHT[m["problem"]["type"]])
        if r.get("outcome"):
            break
        v = r
    assert r["outcome"] == "won" and r["hp"]["now"] > 0  # HP left, but every answer was right


def test_known_mistakes_are_named(imported):
    q = {"type": "numeric", "answer": "-1", "choices": None,
         "traps": [{"answer": "-5", "why": "You used v instead of the unit vector."}]}
    assert keycheck.trap_feedback(q, "-5") == "You used v instead of the unit vector."
    assert keycheck.trap_feedback(q, "7") is None


def test_answer_only_matching_disputed_key_caps_stars(imported):
    enc = {"problems": [{}] * 2, "results": [{"correct": True, "tries": 1, "hints": 0, "via_alt": True},
                                             {"correct": True, "tries": 1, "hints": 0}]}
    assert encounter._stars(enc) == 2


def test_exam_style_problem_asks_for_working(client, imported, monkeypatch):
    monkeypatch.setattr(encounter, "WORK_REQUIRED_COURSES", {"MATH202"})
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    while not v["problem"]["work_required"]:
        v = _ans(client, tid, v, RIGHT[v["problem"]["type"]])
    r = _ans(client, tid, v, RIGHT[v["problem"]["type"]])
    assert r["result"] == "needs_work"
    r = _ans(client, tid, v, RIGHT[v["problem"]["type"]], no_work=True)
    assert r["result"] == "hit" and any("No working" in n for n in r["notes"])


def test_missed_problems_enter_the_deck_and_come_back(client, imported, monkeypatch):
    tid = _tid(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    prompt = v["problem"]["prompt"]
    m = _ans(client, tid, v, WRONG[v["problem"]["type"]])
    _ans(client, tid, m, WRONG[m["problem"]["type"]])
    deck = progress.load()["problem_cards"]
    assert len(deck) == 1
    assert client.get("/api/review").json()["problems"] == []  # due tomorrow
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-09-29")
    cards = client.get("/api/review").json()["problems"]
    assert cards[0]["prompt"] == prompt and "answer" not in cards[0]
    card = cards[0]
    ans = str(card["choices"].index("yes") + 1) if card["type"] == "mcq" else RIGHT[card["type"]]
    r = client.post("/api/review/problem", json={"pid": card["id"], "answer": ans}).json()
    assert r["result"] == "right" and progress.load()["problem_cards"][cards[0]["id"]]["box"] == 1


def test_mock_boss_unlocks_on_its_date(imported, monkeypatch):
    p, plan = progress.load(), imported["plan"]
    b = next(x for x in store.load_config()["bosses"] if x["id"] == "math202-exam1")
    assert not boss.unlocked(p, plan, b)
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-10-04")
    assert boss.unlocked(p, plan, b)


def test_no_hint_bounty_is_gone():
    from studyquest import bounties
    assert "no_hint_win" not in bounties.TEMPLATES
