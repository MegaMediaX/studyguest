"""Battles: local grading, damage/HP = pass threshold, hints, combos, escape → review, loot, focus."""
import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, encounter, mathcheck, progress

RIGHT = {"mcq": "B", "numeric": "-1", "expression": "2xy", "multi": "(2, -2, -1)", "short": "CORRECT idea"}
WRONG = {"mcq": "D", "numeric": "12345", "expression": "x + 1", "multi": "(9, 9, 9)", "short": "no idea"}


@pytest.fixture()
def client(imported, monkeypatch):
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    return TestClient(app_mod.app)


def _reading_id(imported):
    return imported["plan"]["sessions"][0]["tasks"][0]["id"]


def _answer(c, tid, view, right=True):
    p = view["problem"]
    text = RIGHT[p["type"]] if right else WRONG[p["type"]]
    return c.post("/api/battle/answer", json={"task_id": tid, "idx": p["idx"], "answer": text}).json()


@pytest.mark.parametrize("kind,student,key,ok", [
    ("numeric", "1/2", "0.5", True), ("numeric", "3√2", "4.2426", True), ("numeric", "0.6", "0.5", False),
    ("expression", "2xy", "2*x*y", True), ("expression", "y^2+2x", "2*x+y**2", True),
    ("expression", "x*y*2+1", "2*x*y", False), ("expression", "(x+1)(x-1)", "x^2-1", True),
    ("multi", "x=1, y=-2", "(1,-2)", True), ("multi", "(1,2)", "(1,-2)", False),
    ("mcq", "b", 1, True), ("mcq", "2", 1, True), ("mcq", "a", 1, False),
    ("expression", "__import__('os').system('x')", "x", False), ("numeric", "9**9**9", "1", False),
])
def test_mathcheck(kind, student, key, ok):
    assert mathcheck.check(kind, student, key, ["a", "b", "c", "d"]) is ok


def test_generation_validates_problems_and_citations(imported):
    session, task = progress.find_task(imported["plan"], _reading_id(imported))
    g = encounter.generate(task, session)
    types = [p["type"] for p in g["problems"]]
    assert types == ["mcq", "numeric", "expression", "multi", "short"]  # unparsable numeric key -> short
    assert g["problems"][2]["source"] is None  # made-up citation dropped
    assert g["problems"][0]["source"]["file"] == "Multivariable-functions.pdf"


def test_perfect_battle_wins_three_stars_xp_and_loot(client, imported):
    tid = _reading_id(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    assert v["hp"] == {"max": 350, "now": 350} and "answer" not in v["problem"]
    assert v["problem"]["difficulty"] == 1  # easiest first
    crits = 0
    while True:
        r = _answer(client, tid, v)
        assert r["result"] == "hit" and r["reveal"]["explain"] and not r["reveal"]["solution"]
        crits += r["crit"]
        if r.get("outcome"):
            break
        v = r
    assert r["outcome"] == "won" and r["stars"] == 3
    assert crits >= 1  # combo of 3 → crit
    p = progress.load()
    assert p["tasks"][tid]["status"] == "done"
    assert p["xp"] >= 10  # task XP + per-hit XP
    assert p["bestiary"][tid]["enemy"] == "Gradient Golem"
    assert any(b["kind"] == "badge" and b["name"] == "Laser Focus" for b in r["loot"])
    assert client.post("/api/battle/start", json={"task_id": tid}).json()["state"] == "already_done"


def test_miss_then_retry_half_damage_and_reveal(client, imported):
    tid = _reading_id(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    r = _answer(client, tid, v, right=False)
    assert r["result"] == "miss" and r["hp"]["now"] == 350 and r["tries"] == 1
    r = _answer(client, tid, r, right=True)
    assert r["result"] == "hit" and r["damage"] == 50 and r["reveal"]["answer"].startswith("b)")


def test_hints_cost_damage_not_xp(client, imported):
    tid = _reading_id(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    idx = v["problem"]["idx"]
    h = client.post("/api/battle/hint", json={"task_id": tid, "idx": idx}).json()
    assert h == {"hint_level": 1, "hint": "h1", "last": False, "free": False}
    xp_before = progress.load()["xp"]
    r = _answer(client, tid, v)
    assert r["damage"] == 75 and progress.load()["xp"] >= xp_before


def test_losing_twice_goes_to_review_no_xp_lost(client, imported):
    tid = _reading_id(imported)
    for attempt in (1, 2):
        v = client.post("/api/battle/start", json={"task_id": tid}).json()
        assert v["attempt"] == attempt
        while True:
            r = _answer(client, tid, v, right=False)
            r = _answer(client, tid, r, right=False) if r["result"] == "miss" else r
            if r.get("outcome"):
                break
            v = r
        assert r["outcome"] == "escaped"
    p = progress.load()
    assert p["tasks"][tid]["status"] == "review" and tid in p["review"] and p["xp"] == 0


def test_dispute_can_overturn_a_wrong_local_grade(client, imported):
    tid = _reading_id(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    _answer(client, tid, v, right=False)
    r = client.post("/api/battle/dispute", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": "UPHOLD b"}).json()
    assert r["upheld"] and r["result"] == "hit" and r["damage"] == 100


def test_resume_keeps_progress_and_focus_break_costs_badge(client, imported):
    tid = _reading_id(imported)
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    r = _answer(client, tid, v)
    client.post("/api/battle/focus", json={"task_id": tid})
    again = client.post("/api/battle/start", json={"task_id": tid}).json()
    assert again["problem"]["number"] == 2 and again["hp"]["now"] == r["hp"]["now"]
    while True:
        again = _answer(client, tid, again)
        if again.get("outcome"):
            break
    assert again["focus_breaks"] == 1 and not any(l["name"] == "Laser Focus" for l in again["loot"])


def test_source_viewer_only_serves_corpus_files(client):
    ok = client.get("/api/source", params={"course": "MATH202", "file": "Multivariable-functions.pdf", "n": 1})
    assert ok.status_code == 200 and "gradient" in ok.json()["text"]
    bad = client.get("/api/source", params={"course": "MATH202", "file": "../../etc/passwd", "n": 1})
    assert bad.status_code == 404


def test_equip_only_owned_items(client):
    assert client.post("/api/equip", json={"theme": "violet"}).status_code == 400
    assert client.post("/api/equip", json={"theme": "teal"}).json()["equipped"]["theme"] == "teal"
