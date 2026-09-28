"""Daily bounties: 3 small goals, seeded by date. They reward correctness and spacing, never time spent."""
import random

from . import progress, quest, store

TEMPLATES = {
    "clean_hits": {"text": "Land {n} clean hits on {topic}", "n": 5, "reward": 2, "needs_topic": True},
    "no_hint_win": {"text": "Win a battle without hints", "n": 1, "reward": 1},
    "rematch_clear": {"text": "Beat a rematch from your review queue", "n": 1, "reward": 2},
    "three_stars": {"text": "Earn ★★★ on any enemy", "n": 1, "reward": 2},
    "proof_win": {"text": "Defeat an enemy that demands proof", "n": 1, "reward": 2},
    "run_clear": {"text": "Clear every floor of a run", "n": 1, "reward": 3},
    "crits": {"text": "Land {n} critical hits", "n": 3, "reward": 1},
    "show_work": {"text": "Show correct working on {n} problems (📷 photo)", "n": 2, "reward": 2},
}


def _weakest_topic(p: dict, plan: dict) -> str:
    today = store.today().isoformat()
    rows = [m for m in quest.mastery(p, plan) if m["date"] and m["date"] <= today] or quest.mastery(p, plan)
    return min(rows, key=lambda m: m["score"])["topic"] if rows else "any topic"


def _make(kind: str, topic: str | None, idx: int) -> dict:
    t = TEMPLATES[kind]
    return {"id": f"b{idx}", "kind": kind, "topic": topic if t.get("needs_topic") else None,
            "text": t["text"].format(n=t["n"], topic=topic or "any topic"), "target": t["n"], "progress": 0,
            "reward": {"shards": t["reward"]}, "done": False}


def today_bounties(p: dict, plan: dict) -> dict:
    """Generated lazily once per day; deterministic for the date. One always targets the weakest topic."""
    today = store.today().isoformat()
    b = p.get("bounties")
    if b and b.get("date") == today:
        return b
    rnd = random.Random(today)
    others = rnd.sample([k for k in TEMPLATES if k != "clean_hits"], 2)
    items = [_make("clean_hits", _weakest_topic(p, plan), 1)] + [_make(k, None, i + 2) for i, k in enumerate(others)]
    p["bounties"] = {"date": today, "items": items, "rerolls": 1}
    return p["bounties"]


def reroll(p: dict, plan: dict, bounty_id: str) -> dict:
    b = today_bounties(p, plan)
    if b["rerolls"] < 1:
        raise ValueError("No rerolls left today.")
    item = next((x for x in b["items"] if x["id"] == bounty_id), None)
    if not item or item["done"]:
        raise KeyError("Can't reroll that bounty.")
    used = {x["kind"] for x in b["items"]}
    kind = random.Random().choice([k for k in TEMPLATES if k not in used and k != "clean_hits"])
    b["items"][b["items"].index(item)] = _make(kind, None, int(bounty_id[1:]))
    b["rerolls"] -= 1
    return b


def on_event(p: dict, kind: str, topic: str | None = None, amount: int = 1) -> list[dict]:
    """Advance matching bounties; pay shards on completion. Called inside a progress transaction."""
    b = p.get("bounties")
    if not b or b.get("date") != store.today().isoformat():
        return []
    events = []
    for item in b["items"]:
        if item["done"] or item["kind"] != kind or (item["topic"] and topic and item["topic"] != topic):
            continue
        if item["topic"] and not topic:
            continue
        item["progress"] = min(item["target"], item["progress"] + amount)
        if item["progress"] >= item["target"]:
            item["done"] = True
            events.append({"type": "bounty", "text": item["text"], "shards": item["reward"]["shards"]})
            events += add_shards(p, item["reward"]["shards"], "bounty")
    return events


SHARDS_PER_KEY = 3


def add_shards(p: dict, n: int, why: str) -> list[dict]:
    econ = p.setdefault("economy", {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {}})
    econ["shards"] += n
    events = [{"type": "shard", "amount": n, "why": why}]
    while econ["shards"] >= SHARDS_PER_KEY:
        econ["shards"] -= SHARDS_PER_KEY
        econ["keys"] += 1
        events.append({"type": "key"})
    progress.log(p, "shards", None, amount=n, why=why)
    return events
