"""Runs, perks, affixes, ghosts, bounties, shards/keys, chests."""
import random

import pytest
from fastapi.testclient import TestClient

from studyquest import ai, app as app_mod, bounties, perks, progress, run

RIGHT = {"mcq": "B", "numeric": "-1", "expression": "2xy", "multi": "(2, -2, -1)", "short": "CORRECT idea"}


@pytest.fixture()
def client(imported, monkeypatch):
    monkeypatch.setattr(ai, "_status_cache", {"claude": {"ok": True, "why": ""}, "gemini": {"ok": True, "why": ""}})
    return TestClient(app_mod.app)


def _win(c, tid, run_id=None, mode="task"):
    v = c.post("/api/battle/start", json={"task_id": tid, "mode": mode, "run_id": run_id}).json()
    while True:
        r = c.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"],
                                                "answer": RIGHT[v["problem"]["type"]]}).json()
        if r.get("outcome"):
            return v, r
        v = r


def test_perk_offer_respects_gates():
    offer = perks.offer([], accuracy=0.2, rnd=random.Random(1))
    assert len(offer) == 3 and "glass_cannon" not in offer
    assert "glass_cannon" in perks.offer(list(set(perks.PERKS) - {"glass_cannon", "gambit", "chronoshard"}), 0.9)
    assert perks.mods_for(["glass_cannon", "chain_lightning"]) == {"dmg_mult": 2.0, "no_hints": True, "crit_combo": 2}


def test_run_with_perk_draft_and_proof_elite(client, imported):
    r = client.post("/api/run/start").json()["run"]
    assert r["floors"] == 2 and r["floor"] == 0  # 2 non-action tasks today, no due rematch
    first = r["next"]["task_id"]
    v, out = _win(client, first, r["id"])
    assert out["outcome"] == "won" and len(out["run"]["offer"]) == 3
    pick = out["run"]["offer"][0]["id"]
    r = client.post("/api/run/perk", json={"perk_id": pick}).json()["run"]
    assert r["floor"] == 1 and r["perks"][0]["id"] == pick and r["offer"] == []
    assert client.post("/api/run/perk", json={"perk_id": "gambit"}).status_code == 404
    v, out = _win(client, r["next"]["task_id"], r["id"])
    assert out["run"]["state"] == "done" and out["run"]["summary"]["cleared"] == 2


def test_glass_cannon_doubles_damage_and_blocks_hints(client, imported):
    with progress.transaction() as p:
        run.start(p, imported["plan"])
        p["run"]["perks"] = ["glass_cannon"]
        rid, tid = p["run"]["id"], p["run"]["queue"][0]["task_id"]
    v = client.post("/api/battle/start", json={"task_id": tid, "run_id": rid}).json()
    assert v["rules"]["no_hints"]
    assert client.post("/api/battle/hint", json={"task_id": tid, "idx": v["problem"]["idx"]}).status_code == 409
    r = client.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": "B"}).json()
    assert r["damage"] == 200


def test_demands_proof_affix_ends_with_explanation(client, imported):
    with progress.transaction() as p:
        run.start(p, imported["plan"])
        p["run"]["queue"] = p["run"]["queue"] * 2  # 4 floors → last is the proof elite
        p["run"]["floor"] = 3
        rid, tid = p["run"]["id"], p["run"]["queue"][3]["task_id"]
    v = client.post("/api/battle/start", json={"task_id": tid, "run_id": rid}).json()
    assert v["affix"] == "demands_proof" and v["hp"]["max"] == 70 * 6
    types = []
    while True:
        types.append(v["problem"]["type"])
        r = client.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"],
                                                     "answer": RIGHT[v["problem"]["type"]]}).json()
        if r.get("outcome"):
            break
        v = r
    assert types[-1] == "short" or r["hp"]["now"] == 0


def test_shards_keys_and_chest(client, imported):
    with progress.transaction() as p:
        ev = bounties.add_shards(p, 4, "test")
    assert [e["type"] for e in ev] == ["shard", "key"]
    econ = client.get("/api/chest").json()
    assert econ["economy"]["keys"] == 1 and econ["odds"]["rare"] == 0.10
    opened = client.post("/api/chest/open").json()
    assert opened["drop"]["kind"] in {"theme", "title", "consumable"} and opened["economy"]["keys"] == 0
    assert client.post("/api/chest/open").status_code == 409


def test_chest_pity_guarantees_legendary():
    p = {"economy": {"shards": 0, "keys": 1, "chests_since_rare": run.PITY - 1, "consumables": {}},
         "loot": {"titles": [], "themes": ["teal"], "badges": []}, "log": []}
    out = run.open_chest(p, random.Random(0))
    assert out["drop"]["rarity"] == "legendary" and out["shakes"] == 3


def test_five_clean_hits_give_a_shard_and_bounties_progress(client, imported):
    b = client.get("/api/bounties").json()
    assert len(b["items"]) == 3 and b["items"][0]["kind"] == "clean_hits"
    assert b == client.get("/api/bounties").json()  # stable for the day
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    _win(client, tid)
    p = progress.load()
    hits = len(p["encounters"][tid]["results"])  # crits can finish the enemy before all 5 problems
    assert p["economy"]["streak"] == hits
    assert p["bounties"]["items"][0]["progress"] == hits  # weakest topic here = today's session
    with progress.transaction() as q:
        q["economy"]["streak"] = 4
    tid2 = imported["plan"]["sessions"][0]["tasks"][1]["id"]
    _win(client, tid2)
    econ = progress.load()["economy"]
    assert econ["shards"] >= 1 or econ["keys"] >= 1


def test_ghost_of_past_self(client, imported, monkeypatch):
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    # first attempt: miss everything once, then answer right (half damage) → a weak ghost
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    while True:
        m = client.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": "zzz"}).json()
        r = client.post("/api/battle/answer", json={"task_id": tid, "idx": m["problem"]["idx"],
                                                     "answer": RIGHT[m["problem"]["type"]]}).json()
        if r.get("outcome"):
            break
        v = r
    assert progress.load()["ghosts"][tid]["total"] == pytest.approx(0.5, abs=0.01)
    v, out = _win(client, tid, mode="review")
    assert v["ghost"] and out["ghost_result"]["surpassed"]
    assert any(e["type"] == "surpassed" for e in out["events"])


def test_retry_token_undoes_a_miss(client, imported):
    with progress.transaction() as p:
        p["economy"] = {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {"retry_token": 1}}
    tid = imported["plan"]["sessions"][0]["tasks"][0]["id"]
    v = client.post("/api/battle/start", json={"task_id": tid}).json()
    client.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": "zzz"})
    t = client.post("/api/battle/token", json={"task_id": tid, "kind": "retry_token"}).json()
    assert t["tries"] == 0
    r = client.post("/api/battle/answer", json={"task_id": tid, "idx": v["problem"]["idx"], "answer": "B"}).json()
    assert r["damage"] == 100
