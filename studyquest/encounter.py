"""Battles: every task is an enemy. You learn and solve inside the app.

Flow: lesson card (key idea + the actual source pages, viewable in-app) → problems one at a time →
instant feedback. Correct answers deal damage; the enemy's HP equals the pass threshold (70% of the
total damage available), so defeating it == passing the done-check. Hints are tiered and cost damage,
never XP. If the problems run out first, the enemy escapes: that's a failed attempt (twice → 🔁 review).
"""
import random
import secrets
import threading
import time

from . import ai, bounties, corpus, mathcheck, perks, progress, prompts_game, review, store

PASS = 0.7
FIRST_TRY, SECOND_TRY = 1.0, 0.5
HINT_COST = [0.0, 0.25, 0.5, 1.0]  # fraction of a problem's damage lost at hint level 0..3
CRIT_COMBO = 3
XP_HIT, XP_HIT_LATE = 2, 1
LOCAL_KINDS = {"mcq", "numeric", "expression", "multi"}
PREFETCH = threading.Semaphore(2)
TIMED_SECONDS = 120
SHARD_STREAK = 5
INTENTS = {"mcq": ("🎯", "Quick strike: multiple choice"), "numeric": ("🔢", "Wants a number"),
           "expression": ("✍️", "Wants an expression"), "multi": ("📍", "Wants a point or vector"),
           "short": ("💬", "Wants it in your own words")}

LOOT_TITLES = ["Gradient Tamer", "Chain-Rule Ninja", "Saddle-Point Surfer", "Lagrange Whisperer", "Flux Wrangler",
               "Transformer Tamer", "Per-Unit Paladin", "Reluctance Ranger", "Phasor Pilot", "Integral Knight",
               "Limit Breaker", "Tangent Plane Pilot"]
LOOT_THEMES = {"teal": "#5eead4", "violet": "#a78bfa", "amber": "#fbbf24", "rose": "#fb7185", "sky": "#38bdf8",
               "lime": "#a3e635"}


# ---------- generation ----------

def _validate_problem(q: dict) -> dict | None:
    """Keep only problems we can grade. Unparsable keys fall back to AI-graded short answers."""
    if not isinstance(q, dict) or not str(q.get("prompt", "")).strip():
        return None
    kind = q.get("type", "short")
    hints = [str(h) for h in (q.get("hints") or []) if str(h).strip()][:3]
    base = {"type": kind, "prompt": str(q["prompt"]).strip(), "hints": hints,
            "explain": str(q.get("explain", "")), "answer": q.get("answer"),
            "difficulty": max(1, min(3, int(q.get("difficulty") or 2))),
            "source": q.get("source") if isinstance(q.get("source"), dict) else None}
    try:
        if kind == "mcq":
            choices = [str(c) for c in q.get("choices") or []]
            if not 2 <= len(choices) <= 6 or not 0 <= int(q["answer"]) < len(choices):
                return None
            return {**base, "choices": choices, "answer": int(q["answer"])}
        if kind == "numeric":
            mathcheck.value(str(q["answer"]))
        elif kind == "expression":
            mathcheck.parse(str(q["answer"]))
        elif kind == "multi":
            for part in mathcheck.split_multi(str(q["answer"])):
                mathcheck.parse(part)
        elif kind != "short":
            return None
    except (mathcheck.NotMath, KeyError, TypeError, ValueError, ArithmeticError):
        return {**base, "type": "short", "answer": str(q.get("answer", ""))}
    return base


_GEN_LOCKS: dict[str, threading.Lock] = {}
_GEN_GUARD = threading.Lock()


def generate(task: dict, session: dict) -> dict:
    """One generation per task at a time: a start() during a prefetch waits, then hits the AI cache."""
    with _GEN_GUARD:
        lock = _GEN_LOCKS.setdefault(task["id"], threading.Lock())
    with lock:
        return _generate(task, session)


def _generate(task: dict, session: dict) -> dict:
    chunks = corpus.retrieve(task["text"], session["session"], session["subject"], k=5)
    reply = ai.ask("claude", prompts_game.encounter(task, session, chunks))
    problems = [p for p in (_validate_problem(q) for q in reply.get("problems", [])) if p][:6]
    if len(problems) < 2:
        raise ai.AIUnavailable("Couldn't build a battle for this task; try again.")
    valid_refs = {(c["file"], c["n"]): c["unit"] for c in chunks}
    lesson = reply.get("lesson") or {}
    pages = [{"file": c["file"], "n": c["n"], "unit": c["unit"], "course": c["course"]} for c in chunks]
    for p in problems:
        src = p.get("source") or {}
        try:
            key = (src.get("file"), int(src.get("n")))
        except (TypeError, ValueError):
            key = None
        p["source"] = {"file": key[0], "n": key[1], "unit": valid_refs[key]} if key in valid_refs else None
    return {"enemy": str(reply.get("enemy") or "Mystery Beast")[:40],
            "lesson": {"title": str(lesson.get("title", task["text"]))[:120],
                       "points": [str(x) for x in (lesson.get("points") or [])][:4],
                       "formula": str(lesson.get("formula", ""))[:300],
                       "example": lesson.get("example") if isinstance(lesson.get("example"), dict) else None},
            "pages": pages, "problems": problems, "grounded": bool(chunks),
            "notice": _notice(task, session, chunks)}


def _notice(task: dict, session: dict, chunks: list[dict]) -> str | None:
    scanned = corpus.scanned_files_for(task["text"], session["subject"])
    missing = corpus.missing_files_for(task["text"], session["subject"])
    if scanned:
        return f"“{', '.join(scanned)}” has no readable text yet, so this battle uses related course pages."
    if missing and not chunks:
        return f"“{', '.join(missing)}” isn't in your course folders, so these are general topic problems."
    if not chunks:
        return "No course file matched this task, so these are general topic problems."
    return None


def prefetch(task_ids: list[str]) -> None:
    """Warm the AI cache for the next battles in the background so they open instantly."""
    plan = progress.load_plan()

    def work(tid: str) -> None:
        with PREFETCH:
            try:
                session, task = progress.find_task(plan, tid)
                if task["kind"] != "action":
                    generate(task, session)
            except Exception:  # noqa: BLE001 - prefetch is best-effort; the real start reports errors
                pass
    for tid in task_ids[:3]:
        threading.Thread(target=work, args=(tid,), daemon=True).start()


# ---------- state ----------

def _order(problems: list[dict]) -> list[int]:
    return sorted(range(len(problems)), key=lambda i: problems[i]["difficulty"])


def _public_problem(p: dict, idx: int, total: int) -> dict:
    out = {"idx": idx, "number": None, "total": total, "type": p["type"], "prompt": p["prompt"],
           "hints_available": len(p["hints"]), "difficulty": p["difficulty"],
           "source": p["source"]}
    if p["type"] == "mcq":
        out["choices"] = p["choices"]
    return out


def _view(enc: dict, task: dict) -> dict:
    cur = enc["current"]
    done = len(enc["results"])
    prob = _public_problem(enc["problems"][cur], cur, len(enc["problems"])) if cur is not None else None
    if prob:
        prob["number"] = done + 1
    return {"task": task, "enemy": enc["enemy"], "lesson": enc["lesson"], "pages": enc["pages"],
            "notice": enc["notice"], "hp": _hp(enc), "combo": enc["combo"], "problem": prob,
            "tries": enc["tries"], "hint_level": enc["hint_level"], "attempt": enc["attempt"],
            "state": enc["state"], "intent": _intent(enc), "affix": enc.get("affix"), "misses": enc.get("misses", 0),
            "ghost": enc.get("ghost"), "timer": _timer_limit(enc),
            "elapsed": round(time.time() - enc.get("q_started", time.time())),
            "rules": {"no_hints": bool(enc.get("mods", {}).get("no_hints")),
                      "gambit": bool(enc.get("mods", {}).get("gambit")),
                      "free_hints": max(0, enc.get("free_hints", 0) - enc["hint_level"])},
            "run_id": enc.get("run_id")}


def _hp(enc: dict) -> dict:
    max_hp = round(PASS * 100 * len(enc["problems"]))
    return {"max": max_hp, "now": max(0, max_hp - round(enc["damage"]))}


def start(task_id: str, mode: str = "task", run_id: str | None = None) -> dict:
    """mode 'review' re-fights a task from the spaced-review queue (allowed even when it's done)."""
    p, plan = progress.load(), progress.load_plan()
    session, task = progress.find_task(plan, task_id)
    if mode == "task" and progress.is_done(p, task_id):
        return {"state": "already_done", "task": task}
    active = p.get("encounters", {}).get(task_id)
    if active and active["state"] == "fighting":
        return _view(active, task)
    if task["kind"] == "action":
        return {"state": "action", "task": task}
    gen = generate(task, session)  # slow part, outside the lock
    with progress.transaction() as p:
        active = p.setdefault("encounters", {}).get(task_id)
        if active and active["state"] == "fighting":
            return _view(active, task)
        attempt = (active or {}).get("attempt", 0) + 1
        mods, affix = _run_setup(p, run_id)
        if affix == "demands_proof":
            gen = _add_proof(gen)
        order = _order(gen["problems"])
        enc = {"id": secrets.token_hex(4), "task_id": task_id, "attempt": attempt, "state": "fighting", "mode": mode,
               **gen, "queue": order[1:], "current": order[0], "results": [], "damage": 0.0, "combo": 0,
               "best_combo": 0, "tries": 0, "hint_level": 0, "started": time.time(), "focus_breaks": 0,
               "mods": mods, "affix": affix, "run_id": run_id, "ghost": p.get("ghosts", {}).get(task_id),
               "q_started": time.time(), "free_hints": 1 if mods.get("first_hint_free") else 0,
               "second_wind_used": False, "misses": 0}
        p["encounters"][task_id] = enc
        progress.set_last(p, task_id, f"Fighting {enc['enemy']} ({task['text']}).")
    return _view(enc, task)


def _run_setup(p: dict, run_id: str | None) -> tuple[dict, str | None]:
    from . import run as run_mod
    run = p.get("run")
    if not run_id or not run or run["id"] != run_id or run["state"] != "active":
        return {}, None
    return perks.mods_for(run["perks"]), run_mod.affix_for(run, run["floor"])


def _add_proof(gen: dict) -> dict:
    """'Demands proof' elites: the final blow is a 1–2 sentence explanation of the hardest problem."""
    hardest = max(gen["problems"], key=lambda q: q["difficulty"])
    proof = {"type": "short", "prompt": f"Final blow: explain in 1–2 sentences WHY this works. {hardest['prompt']}",
             "answer": hardest.get("explain") or str(hardest["answer"]), "hints": hardest["hints"],
             "explain": hardest.get("explain", ""), "difficulty": 3, "source": hardest.get("source"), "proof": True}
    return {**gen, "problems": gen["problems"] + [proof]}


def _timer_limit(enc: dict) -> int | None:
    return TIMED_SECONDS + enc["mods"].get("timer_bonus", 0) if enc.get("affix") == "timed" else None


def _intent(enc: dict) -> dict | None:
    cur = enc["current"]
    if cur is None:
        return None
    prob = enc["problems"][cur]
    if prob.get("proof"):
        return {"icon": "📜", "text": "Demands proof: explain why, in your own words"}
    if enc.get("affix") == "armored":
        return {"icon": "🛡️", "text": "Armored: only clean first-try hits land"}
    if enc.get("affix") == "timed":
        return {"icon": "⏳", "text": f"Winding up: {_timer_limit(enc)} s per question (late = half damage)"}
    icon, text = INTENTS.get(prob["type"], ("⚔️", "Attacks"))
    return {"icon": icon, "text": text}


# ---------- answering ----------

def _grade(prob: dict, answer: str) -> tuple[bool, str]:
    if prob["type"] in LOCAL_KINDS:
        return mathcheck.check(prob["type"], answer, prob["answer"], prob.get("choices")), ""
    r = ai.ask("claude", prompts_game.judge_short(prob, answer), cache=False)
    return float(r.get("score", 0)) >= PASS, str(r.get("feedback", ""))


def answer(task_id: str, idx: int, text: str) -> dict:
    enc = _active(progress.load(), task_id)
    if enc["current"] != idx:
        raise KeyError("That problem is already finished. Reload.")
    prob = enc["problems"][idx]
    correct, feedback = _grade(prob, text)  # AI (short answers) runs outside the lock
    with progress.transaction() as p:
        enc = _active(p, task_id)
        if enc["current"] != idx:
            raise KeyError("That problem is already finished. Reload.")
        return _resolve(p, enc, prob, text, correct, feedback)


def dispute(task_id: str, idx: int, text: str) -> dict:
    """'I think I'm right': a wrong local grade gets a second look from Claude."""
    enc = _active(progress.load(), task_id)
    if enc["current"] != idx or enc["tries"] == 0:
        raise KeyError("Nothing to dispute.")
    prob = enc["problems"][idx]
    r = ai.ask("claude", prompts_game.judge_dispute(prob, text), cache=False)
    upheld = bool(r.get("student_correct"))
    with progress.transaction() as p:
        enc = _active(p, task_id)
        progress.log(p, "dispute", task_id, upheld=upheld)
        if not upheld:
            return {"upheld": False, "reason": str(r.get("reason", ""))}
        enc["tries"] = 0  # counts as a clean first-try hit
        res = _resolve(p, enc, prob, text, True, str(r.get("reason", "")))
        return {"upheld": True, **res}


def _active(p: dict, task_id: str) -> dict:
    enc = p.get("encounters", {}).get(task_id)
    if not enc or enc["state"] != "fighting":
        raise KeyError("No battle in progress for this task.")
    return enc


def _damage(enc: dict, correct: bool) -> tuple[float, float, bool, list[str]]:
    """Returns (damage, base multiplier, crit, notes). All perk/affix maths lives here."""
    mods, notes = enc.get("mods", {}), []
    if not correct:
        return 0.0, 0.0, False, notes
    paid_hints = max(0, enc["hint_level"] - enc.get("free_hints", 0))
    mult = (FIRST_TRY if enc["tries"] == 1 else SECOND_TRY) * (1 - HINT_COST[min(paid_hints, 3)])
    if enc.get("affix") == "armored" and (enc["tries"] > 1 or enc["hint_level"] > 0):
        notes.append("🛡️ Blocked: armored enemies only take clean hits")
        mult = 0.0
    limit = _timer_limit(enc)
    if limit and time.time() - enc.get("q_started", time.time()) > limit:
        notes.append("⏳ Too slow: half damage")
        mult *= 0.5
    crit = enc["combo"] >= mods.get("crit_combo", CRIT_COMBO)
    dmg = 100.0 * mult * (1.25 if crit else 1.0) * mods.get("dmg_mult", 1.0)
    if mods.get("deep_focus") and enc["focus_breaks"] == 0:
        dmg *= 1.5
    if mods.get("gambit"):
        dmg *= 1.25
    return dmg, mult, crit, notes


def _resolve(p: dict, enc: dict, prob: dict, text: str, correct: bool, feedback: str) -> dict:
    enc["tries"] += 1
    if not correct:
        enc["misses"] = enc.get("misses", 0) + 1
        p.setdefault("economy", {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {}})["streak"] = 0
    if not correct and enc["tries"] < 2:
        enc["combo"] = 0
        note = ""
        if enc.get("mods", {}).get("second_wind") and not enc.get("second_wind_used"):
            enc["second_wind_used"], enc["tries"] = True, 0
            note = " 🌬️ Second Wind: this retry is at full damage."
        return {"result": "miss", "feedback": (feedback or "Not quite. Try again or take a hint.") + note,
                **_view(enc, _task(enc))}
    enc["combo"] = enc["combo"] + 1 if correct and enc["tries"] == 1 and enc["hint_level"] == 0 else 0
    dmg, mult, crit, notes = _damage(enc, correct)
    enc["damage"] += dmg
    enc["best_combo"] = max(enc["best_combo"], enc["combo"])
    enc["results"].append({"idx": enc["current"], "correct": correct, "tries": enc["tries"],
                           "hints": enc["hint_level"], "damage": round(dmg), "answer": text[:300]})
    xp_events = []
    if correct:
        xp_events = progress.add_xp(p, XP_HIT if mult >= FIRST_TRY else XP_HIT_LATE, "hit", enc["task_id"])
        xp_events += _economy_on_hit(p, enc, clean=enc["tries"] == 1 and enc["hint_level"] == 0, crit=crit)
    clean = correct and enc["tries"] == 1
    # always explain *why* (elaborated feedback beats right/wrong); the full solution only when it was a struggle
    reveal = {"answer": _answer_text(prob), "explain": prob["explain"],
              "solution": "" if clean else (prob["hints"][-1] if prob["hints"] else "")}
    out = {"result": "hit" if correct else "fail", "damage": round(dmg), "crit": crit, "feedback": feedback,
           "reveal": reveal, "events": xp_events, "notes": notes}
    _advance(enc)
    if _hp(enc)["now"] == 0 or enc["current"] is None:
        out.update(_finish(p, enc))
    return {**out, **_view(enc, _task(enc))}


def _economy_on_hit(p: dict, enc: dict, clean: bool, crit: bool) -> list[dict]:
    """Key shards from 5 clean hits in a row (across battles), plus bounty progress."""
    econ = p.setdefault("economy", {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {}})
    events = []
    if clean:
        econ["streak"] = econ.get("streak", 0) + 1
        if econ["streak"] % SHARD_STREAK == 0:
            events += bounties.add_shards(p, 1, f"{SHARD_STREAK} clean hits in a row")
        session, _ = progress.find_task(progress.load_plan(), enc["task_id"])
        events += bounties.on_event(p, "clean_hits", topic=session["session"])
    if crit:
        events += bounties.on_event(p, "crits")
    return events


def _answer_text(prob: dict) -> str:
    if prob["type"] == "mcq":
        return f"{'abcdef'[prob['answer']]}) {prob['choices'][prob['answer']]}"
    return str(prob["answer"])


def _advance(enc: dict) -> None:
    """Adaptive order: on a combo take the hardest left, after a miss the easiest."""
    enc["tries"], enc["hint_level"], enc["q_started"] = 0, 0, time.time()
    enc["free_hints"] = 1 if enc.get("mods", {}).get("first_hint_free") else 0
    if not enc["queue"]:
        enc["current"] = None
        return
    probs = enc["problems"]
    normal = [i for i in enc["queue"] if not probs[i].get("proof")] or enc["queue"]
    pick = (max if enc["combo"] >= 2 else min)(normal, key=lambda i: probs[i]["difficulty"])
    enc["queue"].remove(pick)
    enc["current"] = pick


def hint(task_id: str, idx: int) -> dict:
    with progress.transaction() as p:
        enc = _active(p, task_id)
        prob = enc["problems"][idx]
        if enc["current"] != idx:
            raise KeyError("That problem is already finished.")
        if enc.get("mods", {}).get("no_hints"):
            raise ValueError("💎 Glass Cannon: no hints this run.")
        if enc["hint_level"] >= len(prob["hints"]):
            return {"hint_level": enc["hint_level"], "hint": None}
        enc["hint_level"] += 1
        enc["combo"] = 0
        progress.set_last(p, enc["task_id"], f"Hint on {enc['enemy']}: {prob['hints'][enc['hint_level'] - 1][:120]}")
        return {"hint_level": enc["hint_level"], "hint": prob["hints"][enc["hint_level"] - 1],
                "last": enc["hint_level"] == len(prob["hints"]),
                "free": enc["hint_level"] <= enc.get("free_hints", 0)}


def use_token(task_id: str, kind: str) -> dict:
    """Chest consumables: hint_token = next hint free; retry_token = undo the miss on this problem."""
    with progress.transaction() as p:
        enc = _active(p, task_id)
        econ = p.setdefault("economy", {"shards": 0, "keys": 0, "chests_since_rare": 0, "consumables": {}})
        if econ["consumables"].get(kind, 0) < 1:
            raise ValueError("You don't have that token.")
        if kind == "retry_token":
            if enc["tries"] != 1:
                raise ValueError("A Retry Token undoes a miss; you haven't missed this one.")
            enc["tries"] = 0
        elif kind == "hint_token":
            enc["free_hints"] = enc.get("free_hints", 0) + 1
        else:
            raise ValueError("Unknown token.")
        econ["consumables"][kind] -= 1
        progress.log(p, "token", task_id, kind=kind)
        return _view(enc, _task(enc))


def focus_break(task_id: str) -> None:
    with progress.transaction() as p:
        enc = p.get("encounters", {}).get(task_id)
        if enc and enc["state"] == "fighting":
            enc["focus_breaks"] += 1


# ---------- ending ----------

def _task(enc: dict) -> dict:
    _, task = progress.find_task(progress.load_plan(), enc["task_id"])
    return task


def _stars(enc: dict) -> int:
    clean = all(r["correct"] and r["tries"] == 1 and r["hints"] == 0 for r in enc["results"])
    ratio = enc["damage"] / (100 * len(enc["problems"]))
    return 3 if clean else 2 if ratio >= 0.85 else 1


def _finish(p: dict, enc: dict) -> dict:
    plan = progress.load_plan()
    tid = enc["task_id"]
    won = _hp(enc)["now"] == 0
    enc["state"] = "won" if won else "escaped"
    enc["ended"] = time.time()
    progress.record_sprint(p, max(1, round((enc["ended"] - enc["started"]) / 60)), "battle", tid)
    if won:
        stars = _stars(enc)
        if enc.get("mode") == "review" or progress.task_state(p, tid)["status"] == "review":
            events = review.on_pass(p, plan, tid)  # keeps the Leitner card moving up
        else:
            events = progress.record_pass(p, plan, tid, first_try=enc["attempt"] == 1)
        best = p.setdefault("stars", {})
        best[tid] = max(best.get(tid, 0), stars)
        p.setdefault("bestiary", {})[tid] = {"enemy": enc["enemy"], "stars": best[tid], "at": store.now_iso()}
        loot = _roll_loot(p, stars, enc["focus_breaks"] == 0)
        events += _win_bounties(p, enc, stars)
        ghost = _ghost(p, enc)
        events += ghost["events"]
        progress.set_last(p, tid, f"Defeated {enc['enemy']} ({stars}★).")
        out = {"outcome": "won", "stars": stars, "loot": loot, "events": events, "ghost_result": ghost["result"],
               "focus_breaks": enc["focus_breaks"], "best_combo": enc["best_combo"]}
    else:
        fails = progress.record_fail(p, tid)
        events = review.on_fail(p, plan, tid) if enc["attempt"] >= 2 or enc.get("mode") == "review" else []
        ghost = _ghost(p, enc)
        progress.set_last(p, tid, f"{enc['enemy']} escaped. Rematch later.")
        out = {"outcome": "escaped", "events": events, "fails": fails, "rematch": enc["attempt"] < 2,
               "ghost_result": ghost["result"]}
    from . import run as run_mod
    out.update(run_mod.on_battle_end(p, enc, out))
    return out


def _win_bounties(p: dict, enc: dict, stars: int) -> list[dict]:
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


def _ghost(p: dict, enc: dict) -> dict:
    """Compare with your previous best attempt on this task (per question, not per second), keep the best."""
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


def _roll_loot(p: dict, stars: int, laser_focus: bool) -> list[dict]:
    """Cosmetic only. Chance scales with stars; zero tab switches adds a bonus roll."""
    rnd = random.Random()
    inv = p.setdefault("loot", {"titles": [], "themes": ["teal"], "badges": []})
    drops = []
    rolls = stars + (1 if laser_focus else 0)
    for _ in range(rolls):
        roll = rnd.random()
        if roll < 0.18:
            left = [t for t in LOOT_THEMES if t not in inv["themes"]]
            if left:
                t = rnd.choice(left)
                inv["themes"].append(t)
                drops.append({"kind": "theme", "name": t, "color": LOOT_THEMES[t], "rarity": "rare"})
        elif roll < 0.5:
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
    return {**inv, "theme_colors": {t: LOOT_THEMES[t] for t in inv["themes"]},
            "equipped": p.get("settings", {}).get("equipped", {}),
            "bestiary": list(p.get("bestiary", {}).values())}
