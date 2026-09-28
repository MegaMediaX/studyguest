"""Spaced review (Leitner boxes: 1, 2, 4 days, pulled in before the exam), interleaved rounds, 3 quick wins.

Every task gets a card: failed tasks after two escapes, won tasks right after the win. A card's due date
is never later than the day before its course's next exam, so everything gets one more look in time."""
import random
from datetime import date, timedelta

from . import ai, corpus, progress, prompts, store
from .importer import all_tasks

INTERVALS = [1, 2, 4]  # days until the next review after landing in box 0, 1, 2
ROUND_SIZE = 5


def _due(days: int, plan: dict | None = None, tid: str | None = None) -> str:
    """today + days, but no later than the day before this task's course exam (when that's still ahead)."""
    today = store.today()
    due = today + timedelta(days=days)
    cap = _exam_cap(plan, tid) if plan and tid else None
    if cap and today < cap < due:
        due = cap
    return due.isoformat()


def _exam_cap(plan: dict, tid: str):
    from .corpus import course_for_subject
    from .quest import exams_countdown
    try:
        session, _ = progress.find_task(plan, tid)
    except KeyError:
        return None
    course = course_for_subject(session["subject"])
    exam = next((e for e in exams_countdown() if e["course"] == course and e["days"] >= 2), None)
    return date.fromisoformat(exam["date"]) - timedelta(days=1) if exam else None


def schedule(p: dict, plan: dict, tid: str) -> list[dict]:
    """A won task enters spaced review (box 0 → back tomorrow) unless it already has a card."""
    if tid in p["review"]:
        return []
    session, _ = progress.find_task(plan, tid)
    p["review"][tid] = {"box": 0, "due": _due(INTERVALS[0], plan, tid), "topic": session["session"],
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
