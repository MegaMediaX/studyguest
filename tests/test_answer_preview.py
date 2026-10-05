"""Math keypad + live preview: the 'reads as' line shows how the grader parses input, never the key."""
import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, mathcheck


@pytest.mark.parametrize("kind,student,key,read,ok", [
    ("numeric", "sqrt(2)/2", None, "√(2) / 2", True), ("numeric", "3pi/4", None, "3π / 4", True),
    ("numeric", "DNE", None, "DNE", True), ("numeric", "∞", None, "∞", True), ("numeric", "two", None, "two", False),
    ("expression", "e^xy", "exp(x*y)", "e^x·y", True),            # the slip is visible before attacking
    ("expression", "e^(xy)", "exp(x*y)", "e^(x·y)", True),
    ("multi", "i - 2j", "(1, -2)", "(1, -2)", True), ("multi", "<1, -2>", "(1, -2)", "(1, -2)", True),
    ("equation", "2x+2y+z=6", "2*x+2*y+z=6", "2x + 2y + z = 6", True),
    ("line", "x=1+2t, y=1-t, z=3t", None, "(1 + 2t, 1 - t, 3t)", True),
    ("set", "(0,0), (1,-1)", None, "(0, 0), (1, -1)", True),
    ("classify", "Saddle point", None, "saddle", True),
    ("numeric", "(", None, "", False), ("numeric", "", None, "", False),
])
def test_preview_reads_like_the_grader(kind, student, key, read, ok):
    r = mathcheck.preview(kind, student, None, key)
    assert r["read"] == read and r["ok"] is ok


def test_preview_shows_decimal_only_for_non_integers():
    assert mathcheck.preview("numeric", "sqrt(2)/2")["approx"] == "≈ 0.7071"
    assert mathcheck.preview("numeric", "4/2")["approx"] is None


def test_preview_endpoint_never_leaks_the_key_or_costs_an_attempt(imported, monkeypatch):
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    c = TestClient(app_mod.app)
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    v = c.post("/api/battle/start", json={"task_id": tid}).json()
    c.post("/api/battle/lesson", json={"task_id": tid})
    for _ in range(6):
        p = v["problem"]
        if p["type"] not in {"mcq", "short"}:
            break
        v = c.post("/api/battle/answer", json={"task_id": tid, "idx": p["idx"],
                                                "answer": {"mcq": "B", "short": "CORRECT idea"}[p["type"]]}).json()
    p = v["problem"]
    assert p["type"] not in {"mcq", "short"}
    r = c.post("/api/battle/preview", json={"task_id": tid, "idx": p["idx"], "answer": "12345"}).json()
    assert set(r) == {"ok", "read", "approx", "need"} and r["read"]
    again = c.post("/api/battle/start", json={"task_id": tid}).json()
    assert again["problem"]["idx"] == p["idx"] and not again.get("tries")


@pytest.mark.parametrize("kind,student", [("equation", "2x + y = √"), ("numeric", "sqrt"), ("expression", "ln + x")])
def test_function_without_argument_is_unreadable_not_a_wasted_try(kind, student):
    assert not mathcheck.readable(kind, student, None, "2*x+y=3" if kind == "equation" else "x")
    assert not mathcheck.preview(kind, student)["ok"]


def test_multi_counts_missing_parts_and_shows_dne():
    key = "(1, -1, 0, DNE)"
    r = mathcheck.preview("multi", "DNE", None, key)
    assert not r["ok"] and "needs 4 values" in r["need"] and "gave 1" in r["need"]
    r = mathcheck.preview("multi", "1, -1, 0, dne", None, key)
    assert r["ok"] and r["read"] == "(1, -1, 0, DNE)" and r["need"] is None
    assert mathcheck.check("multi", "1, -1, 0, DNE", key)


def _battle_on_numeric(c, tid):
    v = c.post("/api/battle/start", json={"task_id": tid}).json()
    c.post("/api/battle/lesson", json={"task_id": tid})
    while v["problem"]["type"] != "numeric":
        p = v["problem"]
        ans = {"mcq": "B", "expression": "2xy", "multi": "(2, -2, -1)", "short": "CORRECT idea"}[p["type"]]
        v = c.post("/api/battle/answer", json={"task_id": tid, "idx": p["idx"], "answer": ans}).json()
    return v["problem"]


def test_every_step_only_after_the_solution_is_visible_and_checked_against_key(imported, env, monkeypatch):
    fake_ai = env["fake"]
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    c = TestClient(app_mod.app)
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    p = _battle_on_numeric(c, tid)
    r = c.post("/api/battle/steps", json={"task_id": tid, "idx": p["idx"]})
    assert r.status_code == 409  # not before the answer or the last hint
    fake_ai.step_finals = ["7"]  # first attempt ends at the wrong answer -> retried, second matches the key
    c.post("/api/battle/answer", json={"task_id": tid, "idx": p["idx"], "answer": "-1"})
    r = c.post("/api/battle/steps", json={"task_id": tid, "idx": p["idx"]}).json()
    assert [s["rule"] for s in r["steps"]] == ["given", "ln(a^p) = p·ln a"]
    assert sum("step-by-step" in call[1] for call in fake_ai.calls) == 2


def test_steps_that_never_reach_the_key_are_not_shown(imported, env, monkeypatch):
    fake_ai = env["fake"]
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    c = TestClient(app_mod.app)
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    p = _battle_on_numeric(c, tid)
    c.post("/api/battle/answer", json={"task_id": tid, "idx": p["idx"], "answer": "-1"})
    fake_ai.step_finals = ["7", "8"]
    r = c.post("/api/battle/steps", json={"task_id": tid, "idx": p["idx"]})
    assert r.status_code == 503 and "matches the answer" in r.text


def test_battle_minutes_count_active_time_not_days_away(imported, env, monkeypatch):
    import time as _t
    from studyquest import encounter, progress
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    c = TestClient(app_mod.app)
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    v = c.post("/api/battle/start", json={"task_id": tid}).json()
    real = _t.time()
    monkeypatch.setattr(encounter.time, "time", lambda: real + 2 * 86400)  # came back two days later
    for _ in range(5):
        p = v["problem"]
        ans = {"mcq": "B", "numeric": "-1", "expression": "2xy", "multi": "(2, -2, -1)", "short": "CORRECT idea"}[p["type"]]
        v = c.post("/api/battle/answer", json={"task_id": tid, "idx": p["idx"], "answer": ans}).json()
        if not v.get("problem"):
            break
    mins = [s["minutes"] for s in progress.load()["sprints"] if s["intention"] == "battle"]
    assert mins and mins[-1] <= 15 * 5 // 1


def test_review_fixes_power_preview_inverse_trig_and_point_lists():
    assert mathcheck.preview("expression", "x^2 ln(x)", None, "x**2*log(x)")["read"] == "x^2·ln(x)"
    assert mathcheck.check("expression", "tan^-1(x)", "atan(x)")
    assert mathcheck.check("numeric", "sin^(-1)(1)", "pi/2")
    key = "(1, -2), (-1, -2)"  # a 'multi' key that lists points: any order
    assert mathcheck.check("multi", "(-1,-2), (1,-2)", key) and not mathcheck.check("multi", "(1,-2)", key)
