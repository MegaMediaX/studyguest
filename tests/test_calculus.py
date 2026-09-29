"""Calculus review: answer formats a MATH202 student actually types, content rules, exam focus."""
import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, encounter, mathcheck, progress, quest

CASES = [
    # notation
    ("expression", "y e^(x y)", "y*exp(x*y)", True), ("expression", "ye^{xy}", "y*exp(x*y)", True),
    ("expression", "x + e^{x}cos(y) + y^2", "x+exp(x)*cos(y)+y**2", True),
    ("expression", "e^(t-1) - cos(t ln t)(ln t + 1)", "exp(t-1)-(log(t)+1)*cos(t*log(t))", True),
    ("expression", "dw/dt = 2t", "2*t", True), ("expression", "sin^2(x)", "sin(x)**2", True),
    ("expression", "log x", "log(x)", True), ("expression", r"\frac{1}{x+y}", "1/(x+y)", True),
    ("expression", "cosx + cosy", "cos(x)+cos(y)", True), ("expression", "xe^y", "x*exp(y)", True),
    ("expression", "tan x sec x", "tan(x)/cos(x)", True), ("expression", "2xy", "2*x*y + 1", False),
    # limits
    ("numeric", "DNE", "DNE", True), ("numeric", "does not exist", "dne", True), ("numeric", "0", "DNE", False),
    ("numeric", "∞", "inf", True), ("numeric", "1,5", "1.5", True),
    # vectors
    ("multi", "i + 2j", "(1, 2)", True), ("multi", "2i - 3j + k", "(2, -3, 1)", True), ("multi", "<1, 2>", "(1, 2)", True),
    ("multi", "x i + y^2 j", "(x, y**2)", True), ("multi", "(sin(x), cos(y))", "(sin(x), cos(y))", True),
    # planes / lines / sets / classification / directions
    ("equation", "2x+2y+z=6", "z = 6 - 2*x - 2*y", True), ("equation", "2(x-1)+2(y-1)+(z-2)=0", "2*x+2*y+z=6", True),
    ("equation", "4x+4y+2z=12", "2*x+2*y+z=6", True), ("equation", "2x+2y+z=5", "2*x+2*y+z=6", False),
    ("line", "x=1+2t, y=1+2t, z=2+t", "(1+2*t, 1+2*t, 2+t)", True), ("line", "(3+4t, 3+4t, 3+2t)", "(1+2*t, 1+2*t, 2+t)", True),
    ("line", "(1+t, 1+2t, 2+t)", "(1+2*t, 1+2*t, 2+t)", False),
    ("set", "(1,1), (0,0)", "(0,0), (1,1)", True), ("set", "(0,0)", "(0,0), (1,1)", False),
    ("classify", "Saddle point", "saddle", True), ("classify", "relative maximum", "local max", True),
    ("classify", "local min", "local max", False),
    ("direction", "(3,-4)", "(3/5,-4/5)", True), ("direction", "(-3,4)", "(3/5,-4/5)", False),
]


@pytest.mark.parametrize("kind,student,key,ok", CASES)
def test_calculus_answer_formats(kind, student, key, ok):
    assert mathcheck.readable(kind, student, None, key)
    assert mathcheck.check(kind, student, key) is ok


def test_new_kinds_validate_and_bad_keys_fall_back():
    q = {"prompt": "Tangent plane?", "type": "equation", "answer": "2*x + 2*y + z = 6", "hints": [], "difficulty": 2}
    assert encounter._validate_problem(q)["type"] == "equation"
    bad = {**q, "answer": "2x+2y+z"}  # not an equation
    assert encounter._validate_problem(bad)["type"] == "short"
    c = {"prompt": "Classify (0,0)", "type": "classify", "answer": "saddle", "hints": [], "difficulty": 1}
    assert encounter._validate_problem(c)["type"] == "classify"


def test_mcq_traps_given_as_choice_text_become_indices():
    q = {"prompt": "?", "type": "mcq", "choices": ["a", "b", "c", "d"], "answer": 1, "hints": [], "difficulty": 1,
         "traps": [{"answer": "c", "why": "You forgot the unit vector."}]}
    assert encounter._validate_problem(q)["traps"] == [{"answer": "2", "why": "You forgot the unit vector."}]


def test_at_most_one_mcq_in_math202(imported, monkeypatch):
    import json
    monkeypatch.setattr(encounter, "WORK_REQUIRED_COURSES", {"MATH202"})
    many = {"enemy": "E", "lesson": {}, "problems": [
        {"type": "mcq", "prompt": f"Q{i}", "choices": ["a", "b", "c", "d"], "answer": 1, "difficulty": 1 + i % 3,
         "hints": ["h"]} for i in range(3)] + [
        {"type": "numeric", "prompt": f"N{i}", "answer": "2", "difficulty": 2, "hints": ["h"]} for i in range(3)]}
    monkeypatch.setattr(ai, "runner", lambda *a: json.dumps(many))
    session, task = progress.find_task(imported["plan"], imported["plan"]["sessions"][0]["tasks"][0]["id"])
    g = encounter._generate(task, session, "")
    assert sum(1 for p in g["problems"] if p["type"] == "mcq") == 1


def test_exam_focus_points_at_the_exam_course(imported, monkeypatch):
    f = quest.exam_focus(progress.load(), imported["plan"])
    assert f and f["course"] == "MATH202" and f["zone"] == "gradient-gorge"
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-09-20")  # 18 days out: no nudge yet
    assert quest.exam_focus(progress.load(), imported["plan"]) is None


def test_zone_preview_lists_exercises_before_reading(imported, monkeypatch):
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    c = TestClient(app_mod.app)
    q = c.get("/api/run/preview", params={"zone": "gradient-gorge"}).json()["queue"]
    plan = imported["plan"]
    kinds = [next(t["kind"] for s in plan["sessions"] for t in s["tasks"] if t["id"] == tid) for tid in q]
    assert kinds[0] == "exercise"
