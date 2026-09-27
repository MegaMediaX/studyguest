"""World map: zone mapping, tiers, locking, sealing via spaced rematch, zone runs."""
import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, progress, review, store, world

RIGHT = {"mcq": "B", "numeric": "-1", "expression": "2xy", "multi": "(2, -2, -1)", "short": "CORRECT idea"}


@pytest.fixture()
def client(imported, monkeypatch):
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    return TestClient(app_mod.app)


def test_zone_of_prefers_later_zone_and_respects_course():
    cfg = store.load_config()["world"]
    assert world.zone_of({"subject": "Calc II", "session": "14.5 Gradient"}, cfg) == "gradient-gorge"
    assert world.zone_of({"subject": "Machinery", "session": "Midterm review: transformers"}, cfg) == "midterm-keep"
    assert world.zone_of({"subject": "Machinery", "session": "Timed mock midterm (MCQ)"}, cfg) == "midterm-keep"
    assert world.zone_of({"subject": "Calc II", "session": "Something else"}, cfg) is None


def test_world_states(client, imported):
    regions = client.get("/api/world").json()["regions"]
    calc = next(r for r in regions if r["course"] == "MATH202")
    gorge = next(z for z in calc["zones"] if z["id"] == "gradient-gorge")
    assert gorge["state"] == "open" and gorge["tier"] == "Unexplored" and gorge["tasks"] == 4
    assert gorge["exam"]["name"] == "MATH202 Exam I" and 0 < gorge["corruption"] < 1
    depths = next(z for z in calc["zones"] if z["id"] == "integral-depths")
    assert depths["state"] == "locked" and depths["tasks"] == 0  # no sessions in the sample plan
    assert calc["exam"]["days"] == 10


def test_sealing_needs_mastery_and_a_spaced_rematch(imported):
    p, plan = progress.load(), imported["plan"]
    tids = [t["id"] for s in plan["sessions"] if s["subject"] == "Calc II" and s["session"].startswith(("14.5", "14.6"))
            for t in s["tasks"]]
    for t in tids:
        progress.record_pass(p, plan, t, first_try=True)
    gorge = next(z for r in world.build(p, plan) for z in r["zones"] if z["id"] == "gradient-gorge")
    assert gorge["tier"] == "Proficient" and gorge["state"] == "open"  # mastery alone doesn't seal
    review.on_fail(p, plan, tids[0])
    review.on_pass(p, plan, tids[0])  # a spaced rematch win
    gorge = next(z for r in world.build(p, plan) for z in r["zones"] if z["id"] == "gradient-gorge")
    assert gorge["tier"] == "Mastered" and gorge["state"] == "sealed" and gorge["corruption"] == 0


def test_run_in_a_zone(client, imported):
    r = client.post("/api/run/start", json={"zone": "gradient-gorge"}).json()["run"]
    assert r["session"] == "Gradient Gorge" and r["floors"] == 3  # 3 non-action tasks in 14.5/14.6
    assert client.post("/api/run/end").status_code == 200
    assert client.post("/api/run/start", json={"zone": "integral-depths"}).status_code == 409  # locked
    assert client.post("/api/run/start", json={"zone": "nowhere"}).status_code == 404
