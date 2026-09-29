"""Spaced review (Leitner boxes: 1, 2, 4 days, pulled in before the exam), interleaved rounds, 3 quick wins.

Every task gets a card: failed tasks after two escapes, won tasks right after the win. A card's due date
is never later than the day before its course's next exam, so everything gets one more look in time."""
import random
from datetime import date, timedelta

from . import ai, corpus, progress, prompts, store
from .importer import all_tasks

INTERVALS = [1, 2, 4]  # days until the next review after landing in box 0, 1, 2
ROUND_SIZE = 5


def _due(days: int, plan: dict | None = None, tid: str | None = None, course: str | None = None) -> str:
    """today + days, pulled in before the course's next exam: aim for exam-2 (the eve stays light), never later
    than exam-1, and never "again today" while a later pre-exam day exists."""
    today = store.today()
    due = today + timedelta(days=days)
    course = course or (_course_of(plan, tid) if plan and tid else None)
    exam = _next_exam_day(course)
    if exam:
        latest = exam - timedelta(days=1)
        cap = max(exam - timedelta(days=2), today + timedelta(days=1)) if today + timedelta(days=1) <= latest else latest
        due = min(due, cap)
    return max(due, today).isoformat()


def _course_of(plan: dict, tid: str) -> str | None:
    from .corpus import course_for_subject
    try:
        session, _ = progress.find_task(plan, tid)
    except KeyError:
        return None
    return course_for_subject(session["subject"])


def _next_exam_day(course: str | None):
    from .quest import exams_countdown
    if not course:
        return None
    exam = next((e for e in exams_countdown() if e["course"] == course and e["days"] >= 1), None)
    return date.fromisoformat(exam["date"]) if exam else None


def _exam_days(course: str | None) -> int:
    day = _next_exam_day(course)
    return (day - store.today()).days if day else 999


def schedule(p: dict, plan: dict, tid: str, stars: int = 1) -> list[dict]:
    """Every win gets one spaced check, sized to how shaky it was: a 1★ win starts at box 0 (back tomorrow),
    a ★★/★★★ win gets a single confirmation card at the last box (one recall in ~4 days graduates it and can
    seal the zone). Clean play is never a dead end, and the load stays small."""
    if tid in p["review"]:
        return []
    session, _ = progress.find_task(plan, tid)
    box = 0 if stars <= 1 else len(INTERVALS) - 1
    p["review"][tid] = {"box": box, "due": _due(INTERVALS[box], plan, tid), "topic": session["session"],
                        "subject": session["subject"], "lapses": 0}
    progress.log(p, "review_add", tid, due=p["review"][tid]["due"], why="won")
    return [{"type": "review_scheduled", "due": p["review"][tid]["due"]}]


def on_fail(p: dict, plan: dict, tid: str, from_review: bool = False) -> list[dict]:
    """After 2 fails (or a failed review) the task goes to 🔁 and box 0: back tomorrow."""
    st = progress.task_state(p, tid)
    if st["status"] not in {"done", "override"}:
        st["status"] = "review"
    session, _ = progress.find_task(plan, tid)
    p["review"][tid] = {"box": 0, "due": _due(INTERVALS[0], plan, tid), "topic": session["session"],
                        "subject": session["subject"], "lapses": p["review"].get(tid, {}).get("lapses", 0) + 1}
    progress.log(p, "review_add", tid, due=p["review"][tid]["due"])
    return [{"type": "review_later", "due": p["review"][tid]["due"]}]


def on_pass(p: dict, plan: dict, tid: str) -> list[dict]:
    """A passed review moves the card up a box; passing box 2 graduates it and marks the task done (+5 XP)."""
    card = p["review"].get(tid)
    if not card:
        return progress.record_pass(p, plan, tid, first_try=False)
    today = store.today().isoformat()
    if card.get("last_pass") == today:  # no same-day box jumps (that's massed, not spaced, practice)
        card["due"] = _due(INTERVALS[card["box"]], plan, tid)
        return [{"type": "review_up", "box": card["box"], "due": card["due"]}]
    card["last_pass"] = today
    card["box"] += 1
    if card["box"] >= len(INTERVALS):
        p["review"].pop(tid)
        progress.log(p, "review_graduated", tid)
        return [{"type": "graduated"}] + progress.record_pass(p, plan, tid, first_try=False)
    card["due"] = _due(INTERVALS[card["box"]], plan, tid)
    progress.log(p, "review_pass", tid, box=card["box"], due=card["due"])
    events = [{"type": "review_up", "box": card["box"], "due": card["due"]}]
    # The task itself counts as done once you recall it in review; the card keeps coming back until graduated.
    if progress.task_state(p, tid)["status"] == "review":
        events += progress.record_pass(p, plan, tid, first_try=False)
        p["review"][tid] = card
    return events


def due_cards(p: dict, today: date | None = None) -> list[dict]:
    today = (today or store.today()).isoformat()
    return [{"task_id": tid, **c} for tid, c in p["review"].items() if c["due"] <= today]


def interleave(cards: list[dict], seed: int | None = None) -> list[dict]:
    """Shuffle, then avoid two cards from the same topic back-to-back when possible."""
    rnd = random.Random(seed)
    groups: dict[str, list] = {}
    for c in rnd.sample(cards, len(cards)):
        groups.setdefault(c["topic"], []).append(c)
    out = []
    while any(groups.values()):
        last = out[-1]["topic"] if out else None
        options = [t for t, g in groups.items() if g and t != last] or [t for t, g in groups.items() if g]
        # take from the biggest remaining topic so we don't end with a run of one topic
        top = max(len(groups[t]) for t in options)
        topic = rnd.choice([t for t in options if len(groups[t]) == top])
        out.append(groups[topic].pop())
    return out


def review_round(p: dict, plan: dict) -> list[dict]:
    names = {t["id"]: t["text"] for _, t in all_tasks(plan)}
    cards = interleave(due_cards(p), seed=int(store.today().strftime("%Y%m%d")))[:ROUND_SIZE]
    return [{**c, "text": names.get(c["task_id"], "?")} for c in cards]


# ---------- 3 quick wins ----------

def yesterday_tasks(plan: dict) -> list[tuple[dict, dict]]:
    """Tasks from the most recent plan day before today (yesterday, or the last study day)."""
    today = store.today().isoformat()
    past = sorted({s["date"] for s in plan["sessions"] if s["date"] and s["date"] < today})
    if not past:
        return []
    day = past[-1]
    return [(s, t) for s, t in all_tasks(plan) if s["date"] == day and t["kind"] in {"reading", "exercise"}]


def quick_wins(p: dict, plan: dict) -> dict:
    today = store.today().isoformat()
    qw = p.get("quick_wins", {})
    if qw.get("date") == today and qw.get("questions"):
        return _public_qw(qw)
    items = yesterday_tasks(plan)
    if not items:
        return {"date": today, "questions": [], "note": "Nothing from yesterday yet."}
    chunks, topics = [], []
    for s, t in items[:6]:
        chunks += corpus.retrieve(t["text"], s["session"], s["subject"], k=1)
        topics.append(s["session"])
    chunks = list({(c["file"], c["n"]): c for c in chunks}.values())[:6]
    reply = ai.ask("claude", prompts.quick_wins(chunks, sorted(set(topics))))
    qs = [q for q in reply.get("questions", []) if isinstance(q, dict) and q.get("q")][:3]
    qw = {"date": today, "questions": qs, "results": []}
    with progress.transaction() as fresh:
        fresh["quick_wins"] = qw
    return _public_qw(qw)


def _public_qw(qw: dict) -> dict:
    return {"date": qw["date"], "results": qw.get("results", []),
            "questions": [{"q": q["q"], "source": _src_label(q)} for q in qw["questions"]]}


def _src_label(q: dict) -> str | None:
    src = q.get("source")
    return f"{src.get('file')} p{src.get('n')}" if isinstance(src, dict) and src.get("file") else None


def grade_quick_win(index: int, answer: str) -> dict:
    qs = progress.load().get("quick_wins", {}).get("questions", [])
    if index >= len(qs):
        raise KeyError("No such quick win today.")
    q = qs[index]
    fake_task = {"text": "Warm-up recall", "kind": "reading"}
    r = ai.ask("claude", prompts.grade(fake_task, [q], [answer], [], None), cache=False)
    ok = float(r.get("score", 0)) >= 0.7
    with progress.transaction() as p:
        p["quick_wins"].setdefault("results", []).append({"index": index, "ok": ok})
        progress.log(p, "quick_win", None, index=index, ok=ok)
    return {"ok": ok, "reason": r.get("reason", ""), "answer": q["answer"]}


# ---------- per-problem deck: the exact problems you missed come back ----------

PROBLEM_ROUND = 8
DECK_DAILY = 10   # at most 10 deck cards a day, oldest due first; the rest wait (no review avalanche)


def _pid(prob: dict) -> str:
    import hashlib
    return hashlib.sha1(prob["prompt"].encode()).hexdigest()[:10]


def add_problem_card(p: dict, enc: dict, prob: dict) -> list[dict]:
    """Called when a battle problem wasn't clean (missed, second try, hints). Box 0 → back tomorrow."""
    if prob.get("proof"):
        return []
    deck = p.setdefault("problem_cards", {})
    pid = _pid(prob)
    plan = progress.load_plan()
    tid = enc["task_id"] if enc["task_id"] in {t["id"] for _, t in all_tasks(plan)} else None
    topic = prob.get("from_topic") or (progress.find_task(plan, tid)[0]["session"] if tid else "Mixed")
    keep = {k: prob.get(k) for k in ("type", "prompt", "answer", "choices", "explain", "hints", "rule", "traps",
                                     "alt_answers")}
    course = _course_of(plan, tid) if tid else _course_of_topic(plan, topic)
    deck[pid] = {"id": pid, "task_id": tid, "topic": topic, "course": course, "problem": keep, "box": 0,
                 "due": _due(INTERVALS[0], course=course), "lapses": deck.get(pid, {}).get("lapses", 0) + 1,
                 "added": store.now_iso()}
    return [{"type": "problem_card", "due": deck[pid]["due"]}]


def _course_of_topic(plan: dict, topic: str) -> str | None:
    from .corpus import course_for_subject
    s = next((s for s in plan["sessions"] if s["session"] == topic), None)
    return course_for_subject(s["subject"]) if s else None


def due_problem_cards(p: dict) -> list[dict]:
    """Nearest exam's course first, newest misses first (they're the freshest gaps), within the daily budget."""
    today = store.today().isoformat()
    done_today = sum(1 for e in p.get("log", []) if e["event"] == "deck_answer" and e["at"][:10] == today)
    budget = max(0, DECK_DAILY - done_today)
    cards = [c for c in p.get("problem_cards", {}).values() if c["due"] <= today]
    cards.sort(key=lambda c: c.get("added", ""), reverse=True)
    cards.sort(key=lambda c: _exam_days(c.get("course")))
    mixed = interleave([{**c, "task_id": c["id"]} for c in cards[:budget]],
                       seed=int(store.today().strftime("%Y%m%d")))
    return mixed[:min(PROBLEM_ROUND, budget)]


def _order_for(c: dict) -> list[int]:
    """Shuffle MCQ choices per showing (stable within a day and box) so position can't be memorised."""
    n = len(c["problem"].get("choices") or [])
    order = list(range(n))
    random.Random(f"{c['id']}|{store.today().isoformat()}|{c['box']}").shuffle(order)
    return order


def public_card(c: dict) -> dict:
    q = c["problem"]
    choices, ids = q.get("choices"), None
    if q["type"] == "mcq" and choices:
        ids = _order_for(c)
        choices = [choices[i] for i in ids]
    # the client answers with the ORIGINAL index (choice_ids), so grading never depends on re-shuffling later
    return {"id": c["id"], "topic": c["topic"], "box": c["box"], "type": q["type"], "prompt": q["prompt"],
            "choices": choices, "choice_ids": ids, "rule": q.get("rule") or ""}


def answer_problem_card(pid: str, text: str) -> dict:
    """Grade a deck card; right → next box (1/2/4 days, before the exam), wrong → box 0. +1 XP when right."""
    from . import ai, keycheck, mathcheck, prompts_game
    card = progress.load().get("problem_cards", {}).get(pid)
    if not card:
        raise KeyError("That card isn't in your deck.")
    q = card["problem"]
    if q["type"] in keycheck.CHECKABLE:
        if not mathcheck.readable(q["type"], text, q.get("choices"), q["answer"]):
            return {"result": "unreadable", "feedback": "Couldn't read that. (No attempt used.)"}
        correct = keycheck.matches(q, text)
        why = "" if correct else (keycheck.trap_feedback(q, text) or "")
    else:
        r = ai.ask("claude", prompts_game.judge_short(q, text), cache=False)
        correct, why = float(r.get("score", 0)) >= 0.7, str(r.get("feedback", ""))
    plan = progress.load_plan()
    with progress.transaction() as p:
        c = p.get("problem_cards", {}).get(pid)
        if not c:
            raise KeyError("That card isn't in your deck.")
        events = []
        today = store.today().isoformat()
        if correct and c.get("last_pass") == today:  # right again today: fine, but no same-day box jump
            events = progress.add_xp(p, 1, "deck recall")
        elif correct:
            c["last_pass"] = today
            c["box"] += 1
            events = progress.add_xp(p, 1, "deck recall")
            if c["box"] >= len(INTERVALS):
                p["problem_cards"].pop(pid)
                events.append({"type": "card_graduated"})
            else:
                c["due"] = _due(INTERVALS[c["box"]], plan, c["task_id"], c.get("course"))
        else:
            c.update(box=0, due=_due(INTERVALS[0], plan, c["task_id"], c.get("course")), lapses=c.get("lapses", 0) + 1)
        progress.log(p, "deck_answer", c["task_id"] if c else None, correct=correct)
    answer = f"{'abcdef'[int(q['answer'])]}) {q['choices'][int(q['answer'])]}" if q["type"] == "mcq" else str(q["answer"])
    return {"result": "right" if correct else "wrong", "feedback": why, "answer": answer, "explain": q.get("explain", ""),
            "events": events}
