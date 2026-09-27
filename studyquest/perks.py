"""Perks drafted between floors of a run. They change how you practise, never skip problems.

Each perk's `mods` are merged into a battle's `enc["mods"]` and applied server-side in encounter.py.
"""
import random

PERKS = {
    "scholars_lens": {"name": "Scholar's Lens", "icon": "🔍", "gate": "always", "mods": {"first_hint_free": True},
                      "desc": "Your first hint each battle is free.", "flavor": "Vex polishes it on his sleeve."},
    "glass_cannon": {"name": "Glass Cannon", "icon": "💎", "gate": "accuracy75", "mods": {"dmg_mult": 2.0, "no_hints": True},
                     "desc": "Double damage. No hints.", "flavor": "Hit twice as hard. You trust yourself?"},
    "second_wind": {"name": "Second Wind", "icon": "🌬️", "gate": "always", "mods": {"second_wind": True},
                    "desc": "Your first wrong answer each battle doesn't count: retry at full damage.",
                    "flavor": "Everyone slips once."},
    "chain_lightning": {"name": "Chain Lightning", "icon": "⚡", "gate": "always", "mods": {"crit_combo": 2},
                        "desc": "Crits need a 2-combo instead of 3.", "flavor": "Momentum is a weapon."},
    "deep_focus": {"name": "Deep Focus", "icon": "🎯", "gate": "always", "mods": {"deep_focus": True},
                   "desc": "+50% damage while you never leave the tab during a battle.",
                   "flavor": "The world can wait eight minutes."},
    "proofsmith": {"name": "Proofsmith", "icon": "📜", "gate": "always", "mods": {"proof_shards": 2},
                   "desc": "Proof enemies drop 2 key shards.", "flavor": "Explain it, own it."},
    "chronoshard": {"name": "Chronoshard", "icon": "⏳", "gate": "always", "mods": {"timer_bonus": 60},
                    "desc": "Timed enemies give you +60 s per question.", "flavor": "Borrowed seconds."},
    "gambit": {"name": "Scholar's Gambit", "icon": "🎲", "gate": "always", "mods": {"gambit": True},
               "desc": "Skip the lesson scroll: +25% damage (it stays one tap away).",
               "flavor": "You've read this before. Probably."},
}
OFFER_SIZE = 3


def eligible(perk_id: str, accuracy: float) -> bool:
    gate = PERKS[perk_id]["gate"]
    return gate == "always" or (gate == "accuracy75" and accuracy >= 0.75)


def offer(owned: list[str], accuracy: float, rnd: random.Random | None = None) -> list[str]:
    rnd = rnd or random.Random()
    pool = [k for k in PERKS if k not in owned and eligible(k, accuracy)]
    return rnd.sample(pool, min(OFFER_SIZE, len(pool)))


def mods_for(perk_ids: list[str]) -> dict:
    mods: dict = {}
    for pid in perk_ids:
        mods.update(PERKS.get(pid, {}).get("mods", {}))
    return mods


def public(perk_id: str) -> dict:
    p = PERKS[perk_id]
    return {"id": perk_id, "name": p["name"], "icon": p["icon"], "desc": p["desc"], "flavor": p["flavor"]}
