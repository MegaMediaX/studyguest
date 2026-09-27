"""Every test runs against a throwaway data dir and a fake AI, so nothing real is called or overwritten."""
import json
import re
import shutil
from pathlib import Path

import pytest

from studyquest import ai, store

ROOT = Path(__file__).resolve().parent.parent

SAMPLE_CSV = """Done,Date,Time,Subject,Session,Task
FALSE,Mon · 28 Sep,21:00–22:00,Calc II,"14.5 Gradient, directional derivative",∇f and D_u f = ∇f·u (unit vector!)
FALSE,Mon · 28 Sep,21:00–22:00,Calc II,"14.5 Gradient, directional derivative",Do Fares Ex 1.11–1.15
FALSE,Mon · 28 Sep,21:00–22:00,Calc II,"14.5 Gradient, directional derivative",Pack pen and ID
FALSE,Tue · 29 Sep,21:00–22:00,Machinery,Transformer regulation,Voltage regulation & efficiency
TRUE,Tue · 29 Sep,21:00–22:00,Machinery,Transformer regulation,Per-unit system (base S & V)
FALSE,Wed · 30 Sep,21:00–22:00,Calc II,14.6 Linearization,3-variable linearization
"""


class FakeAI:
    """Deterministic stand-in for claude/agy. Grades by looking for the word CORRECT in the answers."""

    def __init__(self):
        self.calls = []
        self.gemini_score = None  # set to force a Gemini disagreement

    def __call__(self, provider, prompt, images):
        self.calls.append((provider, prompt[:80]))
        src = re.search(r'<source file="([^"]+)" \w+="(\d+)"', prompt)
        source = {"file": src.group(1), "n": int(src.group(2))} if src else None
        if prompt.startswith("You are a strict but kind tutor"):
            n = 3 if "3 short retrieval" in prompt else 1
            return json.dumps({"questions": [{"q": f"Q{i + 1}?", "answer": f"A{i + 1}", "type": "formula",
                                              "source": source} for i in range(n)]})
        if prompt.startswith("You design a short learning battle"):
            src2 = source or None
            return json.dumps({"enemy": "Gradient Golem", "lesson": {"title": "Grad", "points": ["p1"], "formula": "D_u f = ∇f·u",
                               "example": {"problem": "e", "steps": ["s"], "answer": "a"}},
                               "problems": [
                {"type": "mcq", "prompt": "Unit?", "choices": ["no", "yes", "maybe", "?"], "answer": 1, "difficulty": 1,
                 "hints": ["h1", "h2", "sol"], "explain": "because", "source": src2},
                {"type": "numeric", "prompt": "D_u f?", "answer": "-1", "difficulty": 2, "hints": ["h1", "h2", "sol"],
                 "explain": "x", "source": src2},
                {"type": "expression", "prompt": "f_x of x^2 y?", "answer": "2*x*y", "difficulty": 2,
                 "hints": ["h1", "h2", "sol"], "explain": "x", "source": {"file": "made-up.pdf", "n": 9}},
                {"type": "multi", "prompt": "grad?", "answer": "(2, -2, -1)", "difficulty": 3, "hints": ["h1", "h2", "sol"],
                 "explain": "x", "source": src2},
                {"type": "numeric", "prompt": "broken key", "answer": "two and a half", "difficulty": 3,
                 "hints": ["h"], "explain": "x"}]})
        if prompt.startswith("Grade a one-line"):
            return json.dumps({"score": 1.0 if "CORRECT" in prompt else 0.0, "feedback": "ok"})
        if prompt.startswith("An auto-grader marked"):
            return json.dumps({"student_correct": "UPHOLD" in prompt, "reason": "equivalent form"})
        if prompt.startswith("Grade a student"):
            items = json.loads(re.search(r"Items: (\[.*?\])\n", prompt, re.S).group(1))
            ok = [("CORRECT" in it["student"]) for it in items]
            score = sum(ok) / len(ok)
            if provider == "gemini" and self.gemini_score is not None:
                score = self.gemini_score
            return json.dumps({"score": score, "confidence": 0.9, "reason": f"{provider} says {score:.2f}",
                               "per_question": [{"ok": o, "feedback": "fb"} for o in ok]})
        if "Give ONE hint" in prompt:
            return json.dumps({"hint": "Think about the unit vector. It matters. Normalize first. Extra sentence."})
        if "smallest next step" in prompt:
            return json.dumps({"step": "Write the gradient formula."})
        if "Explain the idea" in prompt:
            return json.dumps({"explanation": "Like a hill."})
        if prompt.startswith("Warm-up"):
            return json.dumps({"questions": [{"q": f"W{i}", "answer": "x", "source": source} for i in range(3)]})
        if prompt.startswith("Build a"):
            return json.dumps({"questions": [{"q": "B1", "answer": "1", "points": 10, "source": source}]})
        return json.dumps({"text": "?"})


@pytest.fixture()
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(store, "DATA", data)
    monkeypatch.setattr(store, "CORPUS", data / "corpus")
    monkeypatch.setattr(store, "CACHE", data / "cache")
    monkeypatch.setattr(store, "UPLOADS", data / "uploads")
    monkeypatch.setattr(store, "PLAN_FILE", data / "plan.json")
    monkeypatch.setattr(store, "PROGRESS_FILE", data / "progress.json")
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-09-28")
    store.ensure_dirs()
    # a tiny corpus: one course file with two pages
    doc = {"course": "MATH202", "file": "Multivariable-functions.pdf", "path": "/x.pdf", "unit": "page", "mtime": 0,
           "pages": [{"n": 1, "src": "text", "text": "gradient directional derivative unit vector D_u f = grad f . u"},
                     {"n": 2, "src": "none", "text": ""}]}
    (data / "corpus" / "MATH202").mkdir(parents=True)
    (data / "corpus" / "MATH202" / "Multivariable-functions.pdf.json").write_text(json.dumps(doc))
    from studyquest import corpus
    corpus._INDEX.clear()
    fake = FakeAI()
    monkeypatch.setattr(ai, "runner", fake)
    csv_path = tmp_path / "plan.csv"
    csv_path.write_text(SAMPLE_CSV, encoding="utf-8")
    yield {"data": data, "csv": csv_path, "fake": fake, "tmp": tmp_path}
    corpus._INDEX.clear()


@pytest.fixture()
def imported(env):
    from studyquest import importer, progress
    plan = importer.import_file(env["csv"])
    p = progress.sync_with_plan(progress.load(), plan)
    progress.save(p)
    return {**env, "plan": plan}
