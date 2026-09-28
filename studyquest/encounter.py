"""Battles: every task is an enemy. You learn and solve inside the app.

Flow: lesson card (key idea + the actual source pages, viewable in-app) → problems one at a time →
instant feedback. Every problem must be attempted. You win when the enemy's HP (70% of the damage
available) is gone AND at least 60% of the answers were correct, so perks speed things up but
correctness decides. Hints cost damage, never XP; copying the full worked solution earns nothing.
If you don't win, the enemy escapes: a failed attempt (twice → 🔁 review). Rematches get new problems.
"""
import math
import secrets
import threading
import time

from . import (ai, corpus, keycheck, mathcheck, perks, progress, prompts_game, review, rewards, store)
from .corpus import course_for_subject

PASS = 0.7
MIN_CORRECT = 0.6            # share of problems that must be right to win, whatever the damage
FIRST_TRY, SECOND_TRY = 1.0, 0.5
HINT_COST = [0.0, 0.25, 0.5, 1.0]  # fraction of a problem's damage lost at hint level 0..3
MAX_PERK_MULT = 1.5          # all perk multipliers combined can't exceed this
CRIT_COMBO, CRIT_MULT = 3, 1.25
XP_HIT, XP_HIT_LATE = 2, 1
XP_CHIMERA = 10
LOCAL_KINDS = {"mcq", "numeric", "expression", "multi"}
PREFETCH = threading.Semaphore(2)
TIMED_SECONDS = 120
CHIMERA_SIZE = 5
INTENTS = {"mcq": ("🎯", "Quick strike: multiple choice"), "numeric": ("🔢", "Wants a number"),
           "expression": ("✍️", "Wants an expression"), "multi": ("📍", "Wants a point or vector"),
           "short": ("💬", "Wants it in your own words")}

# kept for importers of the old names
LOOT_TITLES, LOOT_THEMES, inventory = rewards.LOOT_TITLES, rewards.LOOT_THEMES, rewards.inventory


# ---------- generation ----------

def _validate_problem(q: dict) -> dict | None:
    """Keep only problems we can grade. Unparsable keys fall back to AI-graded short answers."""
    if not isinstance(q, dict) or not str(q.get("prompt", "")).strip():
        return None
    kind = q.get("type", "short")
    hints = [str(h) for h in (q.get("hints") or []) if str(h).strip()][:3]
    try:
        difficulty = max(1, min(3, int(q.get("difficulty") or 2)))
    except (TypeError, ValueError):
        difficulty = 2
    base = {"type": kind, "prompt": str(q["prompt"]).strip(), "hints": hints,
            "explain": str(q.get("explain", "")), "answer": q.get("answer"), "difficulty": difficulty,
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


def variant_for(attempt: int, mode: str) -> str:
    """First fights share the cached battle; every retry/rematch asks for new problems."""
    if attempt <= 1 and mode == "task":
        return ""
    return (f"This is rematch #{attempt} ({mode}). Write NEW problems: different functions, numbers and "
            f"situations from any earlier battle on this task, testing the same ideas.")


def generate(task: dict, session: dict, variant: str = "") -> dict:
    """One generation per task+variant at a time: a start() during a prefetch waits, then hits the cache."""
    with _GEN_GUARD:
        lock = _GEN_LOCKS.setdefault(f"{task['id']}|{variant}", threading.Lock())
    with lock:
        return _generate(task, session, variant)


def _generate(task: dict, session: dict, variant: str) -> dict:
    chunks = corpus.retrieve(task["text"], session["session"], session["subject"], k=5)
    course = course_for_subject(session["subject"])
    reply = ai.ask("claude", prompts_game.encounter(task, session, chunks, variant, course))
    problems = [p for p in (_validate_problem(q) for q in reply.get("problems", [])) if p][:6]
    if len(problems) < 2:
        raise ai.AIUnavailable("Couldn't build a battle for this task; try again.")
    problems = keycheck.verify(problems)
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
    """Warm the AI cache for upcoming battles (with the right rematch variant) in the background."""
    plan, p = progress.load_plan(), progress.load()

    def work(tid: str) -> None:
        with PREFETCH:
            try:
                session, task = progress.find_task(plan, tid)
                if task["kind"] == "action":
                    return
                prev = p.get("encounters", {}).get(tid) or {}
                mode = "review" if tid in p.get("review", {}) and progress.is_done(p, tid) else "task"
                generate(task, session, variant_for(prev.get("attempt", 0) + 1, mode))
            except Exception:  # noqa: BLE001 - prefetch is best-effort; the real start reports errors
                pass
    for tid in [t for t in task_ids if not str(t).startswith("chimera:")][:4]:
        threading.Thread(target=work, args=(tid,), daemon=True).start()


# ---------- state ----------

def _order(problems: list[dict]) -> list[int]:
    return sorted(range(len(problems)), key=lambda i: problems[i]["difficulty"])


def _public_problem(p: dict, idx: int, total: int) -> dict:
    out = {"idx": idx, "number": None, "total": total, "type": p["type"], "prompt": p["prompt"],
           "hints_available": len(p["hints"]), "difficulty": p["difficulty"], "source": p["source"],
           "unverified": p.get("verified") is False, "from": p.get("from_topic")}
    if p["type"] == "mcq":
        out["choices"] = p["choices"]
    return out


def _correct_count(enc: dict) -> int:
    return sum(1 for r in enc["results"] if r["correct"])


def _view(enc: dict, task: dict | None = None) -> dict:
    cur = enc["current"]
    prob = _public_problem(enc["problems"][cur], cur, len(enc["problems"])) if cur is not None else None
    if prob:
        prob["number"] = len(enc["results"]) + 1
    hp = _hp(enc)
    return {"task": task or _task(enc), "enemy": enc["enemy"], "lesson": enc["lesson"], "pages": enc["pages"],
            "notice": enc["notice"], "hp": hp, "combo": enc["combo"], "problem": prob,
            "tries": enc["tries"], "hint_level": enc["hint_level"], "attempt": enc["attempt"],
            "state": enc["state"], "intent": _intent(enc), "affix": enc.get("affix"), "misses": enc.get("misses", 0),
            "ghost": enc.get("ghost"), "timer": _timer_limit(enc), "mode": enc.get("mode"),
            "elapsed": round(time.time() - enc.get("q_started", time.time())),
            "staggered": hp["now"] == 0 and cur is not None,
            "correct": _correct_count(enc), "need_correct": math.ceil(MIN_CORRECT * len(enc["problems"])),
            "rules": {"no_hints": bool(enc.get("mods", {}).get("no_hints")),
                      "gambit": bool(enc.get("mods", {}).get("gambit")),
                      "free_hints": max(0, enc.get("free_hints", 0) - enc["hint_level"])},
            "run_id": enc.get("run_id")}


def _hp(enc: dict) -> dict:
    max_hp = round(PASS * 100 * len(enc["problems"]))
    return {"max": max_hp, "now": max(0, max_hp - round(enc["damage"]))}


def _new_enc(p: dict, key: str, task: dict, gen: dict, mode: str, run_id: str | None, attempt: int) -> dict:
    mods, affix, in_run = _run_setup(p, run_id, key)
    if affix == "demands_proof":
        gen = _add_proof(gen)
    order = _order(gen["problems"])
    return {"id": secrets.token_hex(4), "task_id": key, "task": task, "attempt": attempt, "state": "fighting",
            "mode": mode, **gen, "queue": order[1:], "current": order[0], "results": [], "damage": 0.0, "combo": 0,
            "best_combo": 0, "tries": 0, "hint_level": 0, "started": time.time(), "focus_breaks": 0,
            "mods": mods, "affix": affix, "run_id": run_id if in_run else None,
            "ghost": p.get("ghosts", {}).get(key), "q_started": time.time(),
            "free_hints": 1 if mods.get("first_hint_free") else 0, "second_wind_used": False, "misses": 0,
            "lesson_opened": False, "last_fail": None}


def start(task_id: str, mode: str = "task", run_id: str | None = None) -> dict:
    """mode 'review' re-fights a task from the spaced-review queue (allowed even when it's done);
    mode 'chimera' is the mixed-topic final floor of a run."""
    if mode == "chimera":
        return start_chimera(task_id, run_id)
    p, plan = progress.load(), progress.load_plan()
    session, task = progress.find_task(plan, task_id)
    if mode == "task" and progress.is_done(p, task_id):
        out = {"state": "already_done", "task": task}
        if run_id:
            from . import run as run_mod
            with progress.transaction() as p:
                if (p.get("run") or {}).get("id") == run_id:
                    out["run"] = run_mod.skip_done(p)
        return out
    active = p.get("encounters", {}).get(task_id)
    if active and active["state"] == "fighting":
        return _view(active, task)
    if task["kind"] == "action":
        return {"state": "action", "task": task}
    attempt = (active or {}).get("attempt", 0) + 1
    gen = generate(task, session, variant_for(attempt, mode))  # slow part, outside the lock
    with progress.transaction() as p:
        active = p.setdefault("encounters", {}).get(task_id)
        if active and active["state"] == "fighting":
            return _view(active, task)
        enc = _new_enc(p, task_id, task, gen, mode, run_id, (active or {}).get("attempt", 0) + 1)
        p["encounters"][task_id] = enc
        progress.set_last(p, task_id, f"Fighting {enc['enemy']} ({task['text']}).")
    return _view(enc, task)


def start_chimera(key: str, run_id: str | None) -> dict:
    """Interleaved final floor: one problem from each of several earlier battles in the same course."""
    with progress.transaction() as p:
        active = p.setdefault("encounters", {}).get(key)
        if active and active["state"] == "fighting":
            return _view(active)
        run = p.get("run") or {}
        problems = chimera_problems(p, progress.load_plan(), run)
        if len(problems) < 3:
            raise ai.AIUnavailable("Not enough earlier battles to build a mixed floor yet.")
        topics = sorted({q["from_topic"] for q in problems})
        task = {"id": key, "text": f"Chimera: mixed review of {len(topics)} topics", "kind": "reading"}
        gen = {"enemy": f"Chimera of {len(topics)} Heads",
               "lesson": {"title": "Mixed review", "formula": "", "example": None,
                          "points": ["Problems come from different topics, in random order.",
                                     "First decide WHICH idea each one needs, then solve.",
                                     f"Topics: {', '.join(topics)}"]},
               "pages": [], "problems": problems, "grounded": True, "notice": None}
        enc = _new_enc(p, key, task, gen, "chimera", run_id, 1)
        p["encounters"][key] = enc
    return _view(enc, task)


def chimera_problems(p: dict, plan: dict, run: dict) -> list[dict]:
    """Up to CHIMERA_SIZE problems, one per earlier battle in the run's course, different topics first."""
    from .importer import all_tasks
    course = None
    for q in run.get("queue", []):
        if not q["task_id"].startswith("chimera:"):
            s, _ = progress.find_task(plan, q["task_id"])
            course = course_for_subject(s["subject"])
            break
    by_topic: dict[str, dict] = {}
    for s, t in all_tasks(plan):
        enc = p.get("encounters", {}).get(t["id"])
        if not enc or course_for_subject(s["subject"]) != course or s["session"] in by_topic:
            continue
        candidates = [q for q in enc.get("problems", []) if not q.get("proof")]
        if candidates:
            pick = max(candidates, key=lambda q: q["difficulty"])
            by_topic[s["session"]] = {**pick, "from_topic": s["session"]}
    return list(by_topic.values())[:CHIMERA_SIZE]


def _run_setup(p: dict, run_id: str | None, task_id: str) -> tuple[dict, str | None, bool]:
    """Perks and affixes apply only to the run's *current* floor task; anything else is a plain battle."""
    from . import run as run_mod
    run = p.get("run")
    if not run_id or not run or run["id"] != run_id or run["state"] != "active":
        return {}, None, False
    if run["floor"] >= len(run["queue"]) or run["queue"][run["floor"]]["task_id"] != task_id:
        return {}, None, False
    return perks.mods_for(run["perks"]), run_mod.affix_for(run, run["floor"], p), True


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
    if prob.get("from_topic"):
        return {"icon": "🐲", "text": f"From: {prob['from_topic'][:40]}"}
    if enc.get("affix") == "armored":
        return {"icon": "🛡️", "text": "Armored: only clean first-try hits land"}
    if enc.get("affix") == "timed":
        return {"icon": "⏳", "text": f"Winding up: {_timer_limit(enc)} s per question (late = half damage)"}
    icon, text = INTENTS.get(prob["type"], ("⚔️", "Attacks"))
    return {"icon": icon, "text": text}


def lesson_opened(task_id: str) -> None:
    """Scholar's Gambit only pays when the lesson really was skipped."""
    with progress.transaction() as p:
        enc = p.get("encounters", {}).get(task_id)
        if enc and enc["state"] == "fighting":
            enc["lesson_opened"] = True


# ---------- answering ----------

def _grade(prob: dict, answer: str) -> tuple[bool, str]:
    if prob["type"] in LOCAL_KINDS:
        return keycheck.matches(prob, answer), ""
    r = ai.ask("claude", prompts_game.judge_short(prob, answer), cache=False)
    return float(r.get("score", 0)) >= PASS, str(r.get("feedback", ""))


FORMAT_HELP = {"mcq": "Pick A–D (or 1–4).", "numeric": "Type a number, e.g. -2, 3/4, sqrt(2)/2 or 3pi/4.",
               "expression": "Type an expression, e.g. 2xy + y^2 or e^(xy).",
               "multi": "Type all the parts, e.g. (1, -2) or (2/3, 1/3, 2/3)."}


def answer(task_id: str, idx: int, text: str) -> dict:
    enc = _active(progress.load(), task_id)
    if enc["current"] != idx:
        raise KeyError("That problem is already finished. Reload.")
    prob = enc["problems"][idx]
    if prob["type"] in LOCAL_KINDS and not mathcheck.readable(prob["type"], text, prob.get("choices"), prob["answer"]):
        return {"result": "unreadable", "feedback": f"Couldn't read that. {FORMAT_HELP[prob['type']]} "
                                                    f"(No attempt used.)"}
    correct, feedback = _grade(prob, text)  # AI (short answers) runs outside the lock
    with progress.transaction() as p:
        enc = _active(p, task_id)
        if enc["current"] != idx:
            raise KeyError("That problem is already finished. Reload.")
        return _resolve(p, enc, prob, text, correct, feedback)


def dispute(task_id: str, idx: int, text: str) -> dict:
    """'I think I'm right': a wrong grade gets a second look from Claude — on a pending miss, or on the
    problem you just failed (worth second-try damage, since the first answer was wrong)."""
    enc = _active(progress.load(), task_id)
    kind = _dispute_kind(enc, idx)
    if not kind:
        raise KeyError("Nothing to dispute.")
    prob = enc["problems"][idx]
    r = ai.ask("claude", prompts_game.judge_dispute(prob, text), cache=False)
    upheld = bool(r.get("student_correct"))
    reason = str(r.get("reason", ""))
    with progress.transaction() as p:
        enc = _active(p, task_id)
        if _dispute_kind(enc, idx) != kind:  # someone answered/disputed meanwhile
            raise KeyError("That problem changed meanwhile. Reload.")
        progress.log(p, "dispute", task_id, upheld=upheld, problem=prob["prompt"][:80])
        if not upheld:
            return {"upheld": False, "reason": reason}
        if kind == "pending":
            enc["tries"] = 0  # the miss is struck: counts as a clean first-try hit
            return {"upheld": True, **_resolve(p, enc, prob, text, True, reason)}
        return {"upheld": True, **_regrade_fail(p, enc, idx, reason)}


def _dispute_kind(enc: dict, idx: int) -> str | None:
    if enc["current"] == idx and enc["tries"] >= 1:
        return "pending"
    last = enc.get("last_fail")
    if last and last["idx"] == idx and not last.get("disputed"):
        return "failed"
    return None


def _regrade_fail(p: dict, enc: dict, idx: int, reason: str) -> dict:
    last = enc["last_fail"]
    last["disputed"] = True
    result = next(r for r in reversed(enc["results"]) if r["idx"] == idx)
    dmg = 100.0 * SECOND_TRY * (1 - HINT_COST[min(last["paid_hints"], 3)]) * _perk_mult(enc)
    if last["paid_hints"] >= 3:
        dmg = 0.0
    result.update(correct=True, damage=round(dmg))
    enc["damage"] += dmg
    events = progress.add_xp(p, XP_HIT_LATE, "dispute upheld", enc["task_id"]) if dmg > 0 else []
    return {"result": "hit", "damage": round(dmg), "crit": False, "feedback": reason, "reveal": None,
            "events": events, "notes": ["⚖️ The judge sided with you."], **_view(enc)}


def _active(p: dict, task_id: str) -> dict:
    enc = p.get("encounters", {}).get(task_id)
    if not enc or enc["state"] != "fighting":
        raise KeyError("No battle in progress for this task.")
    return enc


def _perk_mult(enc: dict) -> float:
    mods = enc.get("mods", {})
    mult = mods.get("dmg_mult", 1.0)
    if mods.get("deep_focus") and enc["focus_breaks"] == 0:
        mult *= 1.5
    if mods.get("gambit") and not enc.get("lesson_opened"):
        mult *= 1.25
    return min(mult, MAX_PERK_MULT)


def _damage(enc: dict, prob: dict, correct: bool) -> tuple[float, float, bool, list[str]]:
    """Returns (damage, base multiplier, crit, notes). All perk/affix maths lives here."""
    mods, notes = enc.get("mods", {}), []
    if not correct:
        return 0.0, 0.0, False, notes
    # free hints can pay for nudges, never for the full worked solution (the last hint)
    last_hint_used = prob["hints"] and enc["hint_level"] >= len(prob["hints"])
    paid_hints = 3 if last_hint_used else max(0, enc["hint_level"] - enc.get("free_hints", 0))
    mult = (FIRST_TRY if enc["tries"] == 1 else SECOND_TRY) * (1 - HINT_COST[min(paid_hints, 3)])
    if last_hint_used:
        notes.append("📖 You used the worked solution: no damage, but now you've seen how it's done")
    if enc.get("affix") == "armored" and (enc["tries"] > 1 or enc["hint_level"] > 0):
        notes.append("🛡️ Blocked: armored enemies only take clean hits")
        mult = 0.0
    limit = _timer_limit(enc)
    if limit and time.time() - enc.get("q_started", time.time()) > limit:
        notes.append("⏳ Too slow: half damage")
        mult *= 0.5
    crit = mult > 0 and enc["combo"] >= mods.get("crit_combo", CRIT_COMBO)
    dmg = 100.0 * mult * (CRIT_MULT if crit else 1.0) * _perk_mult(enc)
    return dmg, mult, crit, notes


def _resolve(p: dict, enc: dict, prob: dict, text: str, correct: bool, feedback: str) -> dict:
    enc["tries"] += 1
    if not correct:
        enc["misses"] = enc.get("misses", 0) + 1
        rewards.on_miss(p)
    if not correct and enc["tries"] < 2:
        enc["combo"] = 0
        note = ""
        if enc.get("mods", {}).get("second_wind") and not enc.get("second_wind_used"):
            enc["second_wind_used"], enc["tries"] = True, 0
            note = " 🌬️ Second Wind: this retry is at full damage."
        return {"result": "miss", "feedback": (feedback or "Not quite. Try again or take a hint.") + note,
                **_view(enc)}
    clean = correct and enc["tries"] == 1 and enc["hint_level"] == 0
    enc["combo"] = enc["combo"] + 1 if clean else 0
    dmg, mult, crit, notes = _damage(enc, prob, correct)
    enc["damage"] += dmg
    enc["best_combo"] = max(enc["best_combo"], enc["combo"])
    enc["results"].append({"idx": enc["current"], "correct": correct, "tries": enc["tries"],
                           "hints": enc["hint_level"], "damage": round(dmg), "answer": text[:300]})
    enc["last_fail"] = None if correct else {
        "idx": enc["current"], "paid_hints": max(0, enc["hint_level"] - enc.get("free_hints", 0))}
    events = []
    if correct and dmg > 0:  # no XP for copying the worked solution
        events = progress.add_xp(p, XP_HIT if mult >= FIRST_TRY else XP_HIT_LATE, "hit", enc["task_id"])
        events += rewards.on_hit(p, clean=clean, crit=crit, topic=_topic(enc))
    reveal = {"answer": _answer_text(prob), "explain": prob["explain"],
              "solution": "" if clean else (prob["hints"][-1] if prob["hints"] else ""),
              "alt": [str(a) for a in prob.get("alt_answers", [])]}
    out = {"result": "hit" if correct else "fail", "damage": round(dmg), "crit": crit, "feedback": feedback,
           "reveal": reveal, "events": events, "notes": notes}
    _advance(enc)
    if enc["current"] is None:  # every problem must be attempted
        out.update(_finish(p, enc))
    return {**out, **_view(enc)}


def _topic(enc: dict) -> str | None:
    if enc.get("mode") == "chimera":
        return None
    try:
        session, _ = progress.find_task(progress.load_plan(), enc["task_id"])
        return session["session"]
    except KeyError:
        return None


def _answer_text(prob: dict) -> str:
    if prob["type"] == "mcq":
        return f"{'abcdef'[prob['answer']]}) {prob['choices'][prob['answer']]}"
    return str(prob["answer"])


def _advance(enc: dict) -> None:
    """Adaptive order: on a combo take the hardest left, after a miss the easiest; proofs come last."""
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
        if enc["current"] != idx:
            raise KeyError("That problem is already finished.")
        prob = enc["problems"][idx]
        if enc.get("mods", {}).get("no_hints"):
            raise ValueError("💎 Glass Cannon: no hints this run.")
        if enc["hint_level"] >= len(prob["hints"]):
            return {"hint_level": enc["hint_level"], "hint": None}
        enc["hint_level"] += 1
        enc["combo"] = 0
        last = enc["hint_level"] == len(prob["hints"])
        progress.set_last(p, enc["task_id"], f"Hint on {enc['enemy']}: {prob['hints'][enc['hint_level'] - 1][:120]}")
        return {"hint_level": enc["hint_level"], "hint": prob["hints"][enc["hint_level"] - 1], "last": last,
                "free": not last and enc["hint_level"] <= enc.get("free_hints", 0)}


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
            if enc.get("mods", {}).get("no_hints"):
                raise ValueError("💎 Glass Cannon: no hints this run, so the token stays in your bag.")
            enc["free_hints"] = enc.get("free_hints", 0) + 1
        else:
            raise ValueError("Unknown token.")
        econ["consumables"][kind] -= 1
        progress.log(p, "token", task_id, kind=kind)
        return _view(enc)


def focus_break(task_id: str) -> None:
    with progress.transaction() as p:
        enc = p.get("encounters", {}).get(task_id)
        if enc and enc["state"] == "fighting":
            enc["focus_breaks"] += 1


# ---------- ending ----------

def _task(enc: dict) -> dict:
    if enc.get("task"):
        return enc["task"]
    _, task = progress.find_task(progress.load_plan(), enc["task_id"])
    return task


def _stars(enc: dict) -> int:
    """Stars count correct answers, not damage (perks can't buy stars)."""
    n = len(enc["problems"])
    clean = sum(1 for r in enc["results"] if r["correct"] and r["tries"] == 1 and r["hints"] == 0)
    correct = _correct_count(enc)
    return 3 if clean == n else 2 if correct / n >= 0.8 else 1


def star_tip(enc: dict, stars: int) -> str:
    if stars == 3:
        return "Perfect: every answer clean on the first try."
    n = len(enc["problems"])
    misses = sum(1 for r in enc["results"] if not r["correct"] or r["tries"] > 1)
    hints = sum(1 for r in enc["results"] if r["hints"])
    parts = [f"{misses} missed first try"] if misses else []
    parts += [f"{hints} used hints"] if hints else []
    return f"★★★ = all {n} clean on the first try, no hints ({', '.join(parts) or 'almost'})."


def won(enc: dict) -> bool:
    return _hp(enc)["now"] == 0 and _correct_count(enc) >= math.ceil(MIN_CORRECT * len(enc["problems"]))


def _finish(p: dict, enc: dict) -> dict:
    if enc.get("mode") == "chimera":
        return _finish_chimera(p, enc)
    plan = progress.load_plan()
    tid = enc["task_id"]
    victory = won(enc)
    enc["state"] = "won" if victory else "escaped"
    enc["ended"] = time.time()
    progress.record_sprint(p, max(1, round((enc["ended"] - enc["started"]) / 60)), "battle", tid)
    if victory:
        stars = _stars(enc)
        if enc.get("mode") == "review" or progress.task_state(p, tid)["status"] == "review":
            events = review.on_pass(p, plan, tid)  # keeps the Leitner card moving up
        else:
            events = progress.record_pass(p, plan, tid, first_try=enc["attempt"] == 1)
            events += review.schedule(p, plan, tid)  # wins get spaced review too
        best = p.setdefault("stars", {})
        best[tid] = max(best.get(tid, 0), stars)
        p.setdefault("bestiary", {})[tid] = {"enemy": enc["enemy"], "stars": best[tid], "at": store.now_iso()}
        loot = rewards.roll_loot(p, stars, enc["focus_breaks"] == 0)
        events += rewards.win_bounties(p, enc, stars)
        gh = rewards.ghost(p, enc)
        events += gh["events"]
        progress.set_last(p, tid, f"Defeated {enc['enemy']} ({stars}★).")
        out = {"outcome": "won", "stars": stars, "star_tip": star_tip(enc, stars), "loot": loot,
               "loot_odds": rewards.LOOT_ODDS, "events": events, "ghost_result": gh["result"],
               "focus_breaks": enc["focus_breaks"], "best_combo": enc["best_combo"]}
    else:
        fails = progress.record_fail(p, tid)
        events = review.on_fail(p, plan, tid) if enc["attempt"] >= 2 or enc.get("mode") == "review" else []
        gh = rewards.ghost(p, enc)
        progress.set_last(p, tid, f"{enc['enemy']} escaped. Rematch later.")
        out = {"outcome": "escaped", "events": events, "fails": fails, "rematch": enc["attempt"] < 2,
               "ghost_result": gh["result"], "why": _escape_reason(enc)}
    from . import run as run_mod
    out.update(run_mod.on_battle_end(p, enc, out))
    return out


def _escape_reason(enc: dict) -> str:
    need = math.ceil(MIN_CORRECT * len(enc["problems"]))
    if _correct_count(enc) < need:
        return f"You got {_correct_count(enc)} of {len(enc['problems'])} right; {need} are needed to win."
    return "Not enough damage: hints and second tries hit softer."


def _finish_chimera(p: dict, enc: dict) -> dict:
    victory = won(enc)
    enc["state"] = "won" if victory else "escaped"
    enc["ended"] = time.time()
    stars = _stars(enc) if victory else 0
    events = progress.add_xp(p, XP_CHIMERA, "chimera") if victory else []
    out = {"outcome": "won" if victory else "escaped", "stars": stars, "loot": [], "events": events,
           "star_tip": star_tip(enc, stars) if victory else "", "loot_odds": rewards.LOOT_ODDS,
           "focus_breaks": enc["focus_breaks"], "best_combo": enc["best_combo"], "ghost_result": None,
           "rematch": True, "why": "" if victory else _escape_reason(enc)}
    from . import run as run_mod
    out.update(run_mod.on_battle_end(p, enc, out))
    return out
