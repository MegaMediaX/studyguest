"""Photos of handwritten working in battles."""
import io
import shutil

import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, photos, progress

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
       b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")


@pytest.fixture()
def client(imported, monkeypatch):
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    monkeypatch.setattr(photos, "normalize", lambda p: p)  # keep tests fast and OS-independent
    return TestClient(app_mod.app)


def _to_numeric(client, tid):
    """Advance to the numeric problem (answers: mcq B first)."""
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    while v["problem"]["type"] != "numeric":
        v = client.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": "B"}).json()
    return v


def _send(client, tid, v, answer=""):
    return client.post("/api/battle/answer_photo", data={"task_id": tid, "idx": v["problem"]["idx"], "answer": answer},
                       files={"photo": ("work.png", io.BytesIO(PNG), "image/png")}).json()


def test_correct_method_earns_bonus_and_bounty(client, imported):
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    v = _to_numeric(client, tid)
    r = _send(client, tid, v, "-1")
    assert r["result"] == "hit" and r["damage"] >= 125 and any("Method checked" in n for n in r["notes"])
    assert progress.load()["encounters"][tid]["results"][-1]["work"]["method_ok"] is True


def test_right_answer_wrong_method_is_half_damage_with_the_first_wrong_step(client, imported):
    imported["fake"].work = {"method_ok": False, "feedback": "Line 3: you used v instead of v/|v|."}
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    v = _to_numeric(client, tid)
    r = _send(client, tid, v, "-1")
    assert r["result"] == "hit" and r["damage"] <= 63 and "Line 3" in r["feedback"]


def test_photo_only_answer_is_read_from_the_photo(client, imported):
    imported["fake"].work = {"final_answer": "-1"}
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    v = _to_numeric(client, tid)
    r = _send(client, tid, v, "")
    assert r["result"] == "hit"


def test_blurry_photo_costs_no_attempt(client, imported):
    imported["fake"].work = {"readable": False, "feedback": "The photo is too dark."}
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    v = _to_numeric(client, tid)
    r = _send(client, tid, v, "-1")
    assert r["result"] == "unreadable" and "too dark" in r["feedback"]
    assert client.post("/api/battle/start", json={"task_id": tid}).json()["tries"] == 0


def test_non_images_are_rejected(client, imported):
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    r = client.post("/api/battle/answer_photo", data={"task_id": tid, "idx": v["problem"]["idx"]},
                    files={"photo": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400


@pytest.mark.skipif(not shutil.which("sips"), reason="macOS sips only")
def test_normalize_converts_to_small_jpeg(tmp_path):
    src = tmp_path / "shot.png"
    src.write_bytes(PNG)
    out = photos.normalize(src)
    assert out.suffix == ".jpg" and out.exists() and not src.exists()
