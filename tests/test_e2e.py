"""End-to-end: a faked study session through the HTTP API, exactly as the browser drives it."""
import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, checker, progress


@pytest.fixture()
def client(imported, monkeypatch):
    monkeypatch.setattr(checker, "HINT_SECONDS", 0)
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    return TestClient(app_mod.app)


def _today_tasks(c):
    return c.get("/api/today").json()["session"]["tasks"]


def test_full_session(client, imported):
    c = client
    today = c.get("/api/today").json()
    assert today["session"]["left"] == 3
    reading, exercise, action = today["session"]["tasks"]
    assert (reading["kind"], exercise["kind"], action["kind"]) == ("reading", "exercise", "action")

    # sprint -> streak
    r = c.post("/api/sprint/done", json={"minutes": 12, "intention": "open the notes", "task_id": reading["id"]}).json()
    assert r["streak"]["current"] == 1

    # reading task: fail once -> hint (<=3 sentences, no feedback leak) -> retry pass = +5
    chk = c.post("/api/check/start", json={"task_id": reading["id"]}).json()
    assert len(chk["questions"]) == 3 and chk["questions"][0]["source"] == "Multivariable-functions.pdf, page 1"
    assert "answer" not in chk["questions"][0]
    r = c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["no", "no", "no"]}).json()
    assert r["status"] == "retry" and r["feedback"] == []
    assert r["hint"].count(".") <= 3
    r = c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["CORRECT"] * 3}).json()
    assert r["status"] == "passed" and {"type": "xp", "amount": 5, "reason": "passed on retry"} in r["events"]

    # exercise with a photo upload, first try = +10
    chk = c.post("/api/check/start", json={"task_id": exercise["id"]}).json()
    files = {"photo": ("work.png", b"\x89PNG fake", "image/png")}
    r = c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["CORRECT"]}, files=files).json()
    assert r["status"] == "passed"

    # action task: local check, needs concrete detail
    chk = c.post("/api/check/start", json={"task_id": action["id"]}).json()
    r = c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["ok"]}).json()
    assert r["status"] == "retry"
    r = c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["Packed pen, calculator and ID card"]}).json()
    assert r["status"] == "passed"
    assert any(e["type"] == "session_complete" and e["bonus"] == 20 for e in r["events"])

    v = c.get(f"/api/session/{today['session']['id']}/verdict").json()
    assert v["complete"] and v["headline"] == "✅ Session complete"
    stats = c.get("/api/stats").json()
    assert stats["level"]["xp"] == 5 + 10 + 5 + 20  # retry, first try, action-on-retry, session
    assert c.post("/api/check/start", json={"task_id": reading["id"]}).json()["status"] == "already_done"

    csv_text = c.get("/api/export").text
    assert csv_text.count("TRUE") == 4  # 3 passed + 1 imported


def test_two_fails_go_to_review_and_come_back(client, imported, monkeypatch):
    c = client
    tid = _today_tasks(c)[0]["id"]
    chk = c.post("/api/check/start", json={"task_id": tid}).json()
    c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["x"] * 3})
    r = c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["x"] * 3}).json()
    assert r["status"] == "review_later" and r["answers"] == ["A1", "A2", "A3"]
    assert _today_tasks(c)[0]["status"] == "review"
    assert c.get("/api/review").json()["total_due"] == 0
    monkeypatch.setenv("STUDYQUEST_TODAY", "2026-09-29")
    due = c.get("/api/review").json()
    assert due["total_due"] == 1 and due["due"][0]["task_id"] == tid
    chk = c.post("/api/check/start", json={"task_id": tid, "mode": "review"}).json()
    r = c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["CORRECT"] * 3}).json()
    assert r["status"] == "passed" and any(e["type"] == "review_up" for e in r["events"])
    assert progress.load()["xp"] == 5


def test_graders_disagree_student_picks(client, imported):
    imported["fake"].gemini_score = 0.9
    c = client
    tid = _today_tasks(c)[0]["id"]
    chk = c.post("/api/check/start", json={"task_id": tid}).json()
    # 2 of 3 right = 0.67 (fail, in the second-opinion band); Gemini says 0.9 (pass) -> disagreement
    r = c.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["CORRECT", "CORRECT", "no"]}).json()
    assert r["status"] == "disagree" and r["claude"]["score"] == pytest.approx(0.67, 0.01) and r["gemini"]["score"] == 0.9
    r = c.post("/api/check/resolve", json={"check_id": chk["check_id"], "pick": "gemini"}).json()
    assert r["status"] == "passed" and r["graded_by"] == "gemini"
    events = [e for e in progress.load()["log"] if e["event"] == "grader_pick"]
    assert events and events[0]["pick"] == "gemini"


def test_override_is_logged_no_xp(client):
    tid = _today_tasks(client)[0]["id"]
    r = client.post("/api/override", json={"task_id": tid, "reason": "did it with a tutor"}).json()
    assert r["events"][0] == {"type": "override", "xp": 0}
    assert progress.load()["xp"] == 0
    assert client.post("/api/override", json={"task_id": tid, "reason": ""}).status_code == 422


def test_help_endpoints(client):
    tid = _today_tasks(client)[0]["id"]
    assert client.post("/api/help/stuck", json={"task_id": tid}).json()["step"] == "Write the gradient formula."
    r = client.post("/api/help/explain", json={"task_id": tid}).json()
    assert r == {"by": "gemini", "text": "Like a hill."}


def test_boss_locked_then_forced(client):
    bosses = client.get("/api/map").json()["bosses"]
    assert bosses and not bosses[0]["unlocked"]
    assert client.post("/api/boss/start", json={"boss_id": bosses[0]["id"]}).status_code == 403


def test_bad_upload_rejected(client):
    tid = _today_tasks(client)[1]["id"]
    chk = client.post("/api/check/start", json={"task_id": tid}).json()
    files = {"photo": ("x.exe", b"MZ", "application/octet-stream")}
    r = client.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["a"]}, files=files)
    assert r.status_code == 400


def test_ai_down_is_a_clear_503(client, monkeypatch):
    def down(*_):
        raise ai.AIUnavailable("Claude CLI is not logged in. Run `claude` in a terminal and type /login once.")
    monkeypatch.setattr(ai, "runner", down)
    tid = _today_tasks(client)[0]["id"]
    r = client.post("/api/check/start", json={"task_id": tid})
    assert r.status_code == 503 and "login" in r.json()["error"]


def test_import_endpoint(client, imported):
    r = client.post("/api/import", files={"file": ("p.csv", imported["csv"].read_bytes(), "text/csv")}).json()
    assert r == {"sessions": 3, "tasks": 6}
    assert client.post("/api/import", files={"file": ("p.exe", b"x", "x")}).status_code == 400


# ---- regressions from the code review ----

def test_restarting_a_failed_check_resumes_it_instead_of_resetting(client, monkeypatch):
    monkeypatch.setattr(checker, "HINT_SECONDS", 60)
    tid = _today_tasks(client)[0]["id"]
    chk = client.post("/api/check/start", json={"task_id": tid}).json()
    client.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["x"] * 3})
    again = client.post("/api/check/start", json={"task_id": tid}).json()
    assert again["check_id"] == chk["check_id"] and again["attempt"] == 2 and again["retry_in"] > 50
    r = client.post("/api/check/submit", data={"check_id": chk["check_id"], "answers": ["CORRECT"] * 3}).json()
    assert r["status"] == "wait"


def test_concurrent_passes_award_session_bonus_once(client, imported):
    from concurrent.futures import ThreadPoolExecutor
    tasks = _today_tasks(client)
    checks = [client.post("/api/check/start", json={"task_id": t["id"]}).json() for t in tasks]
    answers = [["CORRECT"] * 3, ["CORRECT"], ["Packed pen, calculator and ID card"]]
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda ca: client.post("/api/check/submit", data={"check_id": ca[0]["check_id"], "answers": ca[1]}),
                      zip(checks, answers)))
    p = progress.load()
    assert p["xp"] == 10 * 3 + 20
    assert all(p["tasks"][t["id"]]["status"] == "done" for t in tasks)


def test_bad_citation_page_is_dropped_not_a_500(imported, monkeypatch):
    import json as _json
    monkeypatch.setattr(ai, "runner", lambda *a: _json.dumps({"questions": [
        {"q": "ok?", "answer": "a", "source": {"file": "Multivariable-functions.pdf", "n": "1"}},
        {"q": "bad?", "answer": "a", "source": {"file": "Multivariable-functions.pdf", "n": "p.12"}}]}))
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    r = checker.start(tid)
    assert [q["q"] for q in r["questions"]] == ["ok?"]


def test_task_naming_unknown_file_gets_no_foreign_citations(imported):
    from studyquest import corpus
    assert corpus.retrieve("Read “Nonexistent-notes.pdf” §2", "14.5 Gradient", "Calc II") == []
    assert corpus.missing_files_for("Read “Nonexistent-notes.pdf” §2", "Calc II") == ["Nonexistent-notes.pdf"]
    assert corpus._match_file("practiceexam1.pdf", "exam1.pdf") == 0
    assert corpus._match_file("Course Notes/Ch.2 Double Integrals.pdf", "Ch.2 Double Integrals") == 1
