"""Battle rewards: cosmetic loot (published odds), ghosts of past attempts, bounty/shard hooks."""
import random

from . import bounties, store

LOOT_TITLES = ["Gradient Tamer", "Chain-Rule Ninja", "Saddle-Point Surfer", "Lagrange Whisperer", "Flux Wrangler",
               "Transformer Tamer", "Per-Unit Paladin", "Reluctance Ranger", "Phasor Pilot", "Integral Knight",
               "Limit Breaker", "Tangent Plane Pilot"]
LOOT_THEMES = {"teal": "#5eead4", "violet": "#a78bfa", "amber": "#fbbf24", "rose": "#fb7185", "sky": "#38bdf8",
               "lime": "#a3e635"}
# Per roll after a win; you get one roll per star, +1 for zero tab switches. Shown on the victory screen.
LOOT_ODDS = {"theme": 0.18, "title": 0.32}
SHARD_STREAK = 5


def roll_loot(p: dict, stars: int, laser_focus: bool, rnd: random.Random | None = None) -> list[dict]:
    """Cosmetic only, no duplicates."""
    rnd = rnd or random.Random()
    inv = p.setdefault("loot", {"titles": [], "themes": ["teal"], "badges": []})
    drops = []
    for _ in range(stars + (1 if laser_focus else 0)):
        roll = rnd.random()
        if roll < LOOT_ODDS["theme"]:
            left = [t for t in LOOT_THEMES if t not in inv["themes"]]
            if left:
                t = rnd.choice(left)
                inv["themes"].append(t)
                drops.append({"kind": "theme", "name": t, "color": LOOT_THEMES[t], "rarity": "rare"})
        elif roll < LOOT_ODDS["theme"] + LOOT_ODDS["title"]:
            left = [t for t in LOOT_TITLES if t not in inv["titles"]]
            if left:
                t = rnd.choice(left)
                inv["titles"].append(t)
                drops.append({"kind": "title", "name": t, "rarity": "uncommon"})
    if laser_focus and "Laser Focus" not in inv["badges"]:
        inv["badges"].append("Laser Focus")
        drops.append({"kind": "badge", "name": "Laser Focus", "rarity": "epic"})
    return drops


def inventory(p: dict) -> dict:
    inv = p.get("loot", {"titles": [], "themes": ["teal"], "badges": []})
    return {**inv, "theme_colors": {t: LOOT_THEMES[t] for t in inv["themes"] if t in LOOT_THEMES}
            | {t: c for t, c in _rare_themes().items() if t in inv["themes"]},
            "equipped": p.get("settings", {}).get("equipped", {}),
            "bestiary": list(p.get("bestiary", {}).values()), "odds": LOOT_ODDS}


def _rare_themes() -> dict:
    from .run import RARE_THEMES
    return RARE_THEMES


def theme_color(name: str | None) -> str | None:
    return (LOOT_THEMES | _rare_themes()).get(name) if name else None


def on_hit(p: dict, clean: bool, crit: bool, topic: str | None) -> list[dict]:
    """Key shards from 5 clean hits in a row (across battles), plus bounty progress."""
    econ = p.setdefault("economy", {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {}})
    events = []
    if clean:
        econ["streak"] = econ.get("streak", 0) + 1
        if econ["streak"] % SHARD_STREAK == 0:
            events += bounties.add_shards(p, 1, f"{SHARD_STREAK} clean hits in a row")
        if topic:
            events += bounties.on_event(p, "clean_hits", topic=topic)
    if crit:
        events += bounties.on_event(p, "crits")
    return events


def on_miss(p: dict) -> None:
    p.setdefault("economy", {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {}})["streak"] = 0


def win_bounties(p: dict, enc: dict, stars: int) -> list[dict]:
    events = []
    if all(r["hints"] == 0 for r in enc["results"]):
        events += bounties.on_event(p, "no_hint_win")
    if enc.get("mode") == "review":
        events += bounties.on_event(p, "rematch_clear")
    if stars == 3:
        events += bounties.on_event(p, "three_stars")
    if enc.get("affix") == "demands_proof":
        events += bounties.on_event(p, "proof_win")
        if enc.get("mods", {}).get("proof_shards"):
            events += bounties.add_shards(p, enc["mods"]["proof_shards"], "Proofsmith")
    return events


def ghost(p: dict, enc: dict) -> dict:
    """Compare with your best past attempt on this task (per question, not per second); keep the best."""
    per_q = [round(r["damage"] / 100, 2) for r in enc["results"]]
    total = round(sum(per_q) / max(len(enc["problems"]), 1), 3)
    ghosts = p.setdefault("ghosts", {})
    old = ghosts.get(enc["task_id"])
    events, result = [], None
    if old:
        result = {"then": old["total"], "now": total, "surpassed": total > old["total"], "date": old["at"][:10]}
        if total > old["total"]:
            events += [{"type": "surpassed"}] + bounties.add_shards(p, 1, "surpassed your ghost")
    if not old or total > old["total"]:
        ghosts[enc["task_id"]] = {"at": store.now_iso(), "per_q": per_q, "total": total,
                                  "hints": sum(r["hints"] for r in enc["results"])}
    return {"events": events, "result": result}
