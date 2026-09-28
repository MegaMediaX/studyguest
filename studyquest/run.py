"""Runs (a session = up to 4 floors, a perk draft between floors) and chests (published odds, pity, no dupes).

Floor 1 is a due rematch when one exists (spacing decides), then the session's open tasks.
Losing a battle never ends a run: you keep XP, bestiary and notes, and move on (the Hades rule).
"""
import random
import secrets
import time

from . import bounties, perks, progress, review, rewards, store

MAX_FLOORS = 4
CHEST_ODDS = {"cosmetic": 0.60, "consumable": 0.30, "rare": 0.10}
PITY = 8
RARE_THEMES = {"aurora": "#7dd3fc", "gold": "#facc15", "ember": "#fb923c"}
CONSUMABLES = {"hint_token": "Hint Token: your next hint is free", "retry_token": "Retry Token: undo one miss"}
MAX_CONSUMABLE = 3


def _session_for_run(p: dict, plan: dict) -> dict | None:
    from .quest import today_quest
    t = today_quest(p, plan)
    sid = (t.get("session") or {}).get("id")
    return next((s for s in plan["sessions"] if s["id"] == sid), None)


def start(p: dict, plan: dict, zone: str | None = None) -> dict:
    if p.get("run") and p["run"]["state"] == "active":
        return p["run"]
    if zone:
        from . import world
        return _new_run(p, with_chimera(p, plan, world.zone_queue(p, plan, zone, MAX_FLOORS)), zone,
                        next(z["name"] for r in world.build(p, plan) for z in r["zones"] if z["id"] == zone))
    session = _session_for_run(p, plan)
    if not session:
        raise KeyError("No session to run.")
    return _new_run(p, plan_queue(p, plan, session), session["id"], session["session"])


MAX_REVIEWS = 2


def plan_queue(p: dict, plan: dict, session: dict | None = None) -> list[dict]:
    """Up to 2 due rematches first (spacing decides), then the session's open tasks, then — if enough
    earlier battles exist in this course — a mixed-topic Chimera as the final floor (interleaving)."""
    session = session or _session_for_run(p, plan)
    if not session:
        raise KeyError("No session to run.")
    queue = [{"task_id": c["task_id"], "mode": "review"} for c in review.interleave(review.due_cards(p))[:MAX_REVIEWS]]
    for t in session["tasks"]:
        if len(queue) >= MAX_FLOORS:
            break
        if t["kind"] != "action" and not progress.is_done(p, t["id"]) and all(q["task_id"] != t["id"] for q in queue):
            queue.append({"task_id": t["id"], "mode": "task"})
    if not queue:
        raise KeyError("Nothing left to fight on this floor. Try the Review tab or tomorrow's session.")
    return with_chimera(p, plan, queue)


def with_chimera(p: dict, plan: dict, queue: list[dict]) -> list[dict]:
    from .encounter import chimera_problems
    if len(queue) < 2:
        return queue
    probe = {"queue": queue}
    if len(chimera_problems(p, plan, probe)) < 3:
        return queue
    return queue[:MAX_FLOORS - 1] + [{"task_id": f"chimera:{secrets.token_hex(3)}", "mode": "chimera"}]


def _new_run(p: dict, queue: list[dict], where_id: str, label: str) -> dict:
    p["run"] = {"id": secrets.token_hex(3), "session_id": where_id, "session": label, "queue": queue, "floor": 0,
                "perks": [], "offer": [], "state": "active", "started": time.time(), "log": []}
    progress.log(p, "run_start", None, floors=len(queue), where=label)
    return p["run"]


def skip_done(p: dict) -> dict | None:
    """Floors whose task you finished outside the run are skipped, so a run can never get stuck."""
    run = p.get("run")
    if not run or run["state"] != "active":
        return None
    while run["floor"] < len(run["queue"]):
        entry = run["queue"][run["floor"]]
        if entry["mode"] != "task" or not progress.is_done(p, entry["task_id"]):
            break
        run["log"].append({"task_id": entry["task_id"], "enemy": "(already cleared)", "won": True, "stars": 0,
                           "skipped": True})
        run["floor"] += 1
    if run["floor"] >= len(run["queue"]):
        return finish(p)
    return public(run)


def affix_for(run: dict, floor: int, p: dict | None = None) -> str | None:
    """Rule-based affixes. The last floor of a 3+ floor run is an elite that demands proof (unless it's the
    Chimera). Armored only on rematches of cards you've already recalled once (box ≥ 1), never on fresh
    failures — that would trap the weakest topics in a lose-repeat loop."""
    n = len(run["queue"])
    entry = run["queue"][floor]
    if entry["mode"] == "chimera":
        return None
    if n >= 3 and floor == n - 1:
        return "demands_proof"
    if entry["mode"] == "review" and p and p.get("review", {}).get(entry["task_id"], {}).get("box", 0) >= 1:
        return "armored"
    return None


def on_battle_end(p: dict, enc: dict, outcome: dict) -> dict:
    run = p.get("run")
    if not run or run["state"] != "active" or enc.get("run_id") != run["id"]:
        return {}
    if run["floor"] >= len(run["queue"]) or run["queue"][run["floor"]]["task_id"] != enc["task_id"]:
        return {}  # only the current floor's battle can advance the run
    run["log"].append({"task_id": enc["task_id"], "enemy": enc["enemy"], "won": outcome["outcome"] == "won",
                       "stars": outcome.get("stars", 0)})
    run["floor"] += 1
    if run["floor"] >= len(run["queue"]):
        return {"run": finish(p)}
    run["offer"] = perks.offer(run["perks"], _accuracy(p, run))
    return {"run": public(run)}


def _accuracy(p: dict, run: dict) -> float:
    res = [r for tid in [q["task_id"] for q in run["queue"]]
           for r in (p.get("encounters", {}).get(tid, {}) or {}).get("results", [])]
    clean = sum(1 for r in res if r["correct"] and r["tries"] == 1 and r["hints"] == 0)
    return clean / len(res) if len(res) >= 5 else 0.0


def choose_perk(p: dict, perk_id: str) -> dict:
    run = p.get("run")
    if not run or perk_id not in run.get("offer", []):
        raise KeyError("That perk isn't on offer.")
    run["perks"].append(perk_id)
    run["offer"] = []
    return public(run)


def finish(p: dict, abandoned: bool = False) -> dict:
    run = p["run"]
    run["state"] = "abandoned" if abandoned else "done"
    cleared = sum(1 for x in run["log"] if x["won"])
    summary = {"id": run["id"], "session": run["session"], "floors": len(run["queue"]), "cleared": cleared,
               "stars": sum(x["stars"] for x in run["log"]), "perks": run["perks"],
               "minutes": round((time.time() - run["started"]) / 60), "at": store.now_iso(), "abandoned": abandoned}
    events = []
    if not abandoned and cleared == len(run["queue"]):
        events = bounties.on_event(p, "run_clear")
    p.setdefault("run_history", []).append(summary)
    p["run_history"] = p["run_history"][-50:]
    progress.log(p, "run_end", None, cleared=cleared, abandoned=abandoned)
    return {**public(run), "summary": summary, "events": events, "keys": p.get("economy", {}).get("keys", 0)}


def public(run: dict) -> dict:
    return {"id": run["id"], "session": run["session"], "floor": run["floor"], "floors": len(run["queue"]),
            "perks": [perks.public(x) for x in run["perks"]], "offer": [perks.public(x) for x in run["offer"]],
            "state": run["state"], "log": run["log"], "queue": [q["task_id"] for q in run["queue"]],
            "next": run["queue"][run["floor"]] if run["state"] == "active" and run["floor"] < len(run["queue"]) else None}


# ---------- chests ----------

def odds() -> dict:
    return {"odds": CHEST_ODDS, "pity": PITY, "consumables": CONSUMABLES}


def open_chest(p: dict, rnd: random.Random | None = None) -> dict:
    rnd = rnd or random.Random()
    econ = p.setdefault("economy", {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {}})
    if econ["keys"] < 1:
        raise ValueError("You need a key. Keys come from 5 clean hits in a row and from bounties.")
    econ["keys"] -= 1
    inv = p.setdefault("loot", {"titles": [], "themes": ["teal"], "badges": []})
    roll = rnd.random()
    tier = "rare" if econ["chests_since_rare"] >= PITY - 1 or roll < CHEST_ODDS["rare"] else \
        "consumable" if roll < CHEST_ODDS["rare"] + CHEST_ODDS["consumable"] else "cosmetic"
    drop = _rare(inv, rnd) if tier == "rare" else _cosmetic(inv, rnd) if tier == "cosmetic" else None
    if drop is None:
        drop = _consumable(econ, rnd)
    econ["chests_since_rare"] = 0 if drop.get("rarity") == "legendary" else econ["chests_since_rare"] + 1
    progress.log(p, "chest", None, drop=drop["name"])
    return {"drop": drop, "shakes": {"legendary": 3, "rare": 2}.get(drop["rarity"], 1), "economy": econ}


def _rare(inv: dict, rnd: random.Random) -> dict | None:
    left = [t for t in RARE_THEMES if t not in inv["themes"]]
    if not left:
        return None
    t = rnd.choice(left)
    inv["themes"].append(t)
    return {"kind": "theme", "name": t, "color": RARE_THEMES[t], "rarity": "legendary"}


def _cosmetic(inv: dict, rnd: random.Random) -> dict | None:
    titles = [t for t in rewards.LOOT_TITLES if t not in inv["titles"]]
    themes = [t for t in rewards.LOOT_THEMES if t not in inv["themes"]]
    if themes and (not titles or rnd.random() < 0.4):
        t = rnd.choice(themes)
        inv["themes"].append(t)
        return {"kind": "theme", "name": t, "color": rewards.LOOT_THEMES[t], "rarity": "rare"}
    if titles:
        t = rnd.choice(titles)
        inv["titles"].append(t)
        return {"kind": "title", "name": t, "rarity": "uncommon"}
    return None


def _consumable(econ: dict, rnd: random.Random) -> dict:
    options = [k for k in CONSUMABLES if econ["consumables"].get(k, 0) < MAX_CONSUMABLE] or list(CONSUMABLES)
    k = rnd.choice(options)
    econ["consumables"][k] = min(MAX_CONSUMABLE, econ["consumables"].get(k, 0) + 1)
    return {"kind": "consumable", "name": CONSUMABLES[k], "id": k, "rarity": "common"}

