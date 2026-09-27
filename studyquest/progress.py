"""progress.json: task status, XP, levels, streaks with weekly freeze, overrides, 'where was I'."""
import threading
from contextlib import contextmanager
from datetime import date, timedelta

from . import store
from .importer import all_tasks

XP_FIRST_TRY = 10
XP_RETRY = 5
XP_SESSION = 20
XP_BOSS = 50
LOG_LIMIT = 3000


def empty_progress() -> dict:
    cfg = store.load_config()
    return {
        "version": 1, "xp": 0, "tasks": {}, "sessions_awarded": [], "sprint_days": [], "sprints": [],
        "review": {}, "overrides": [], "log": [], "last": None, "bosses": {}, "quick_wins": {},
        "settings": dict(cfg.get("defaults", {})),
    }


def load() -> dict:
    return store.read_json(store.PROGRESS_FILE) or empty_progress()


def save(p: dict) -> None:
    p["log"] = p["log"][-LOG_LIMIT:]
    store.write_json(store.PROGRESS_FILE, p)


_LOCK = threading.RLock()


@contextmanager
def transaction():
    """Load, mutate, save under one lock so concurrent requests can't lose updates or double-award XP.
    Never call the AI inside a transaction; do slow work first, then open one."""
    with _LOCK:
        p = load()
        yield p
        save(p)


def load_plan() -> dict:
    plan = store.read_json(store.PLAN_FILE)
    if not plan:
        raise FileNotFoundError("No plan yet. Import a checklist first (/quest-import study_checklist.csv).")
    return plan


def task_state(p: dict, tid: str) -> dict:
    return p["tasks"].setdefault(tid, {"status": "todo", "attempts": 0, "fails": 0, "xp": 0, "passed_at": None})


def log(p: dict, event: str, task_id: str | None = None, **detail) -> None:
    p["log"].append({"at": store.now_iso(), "event": event, "task_id": task_id, **detail})


def sync_with_plan(p: dict, plan: dict) -> dict:
    """Rows marked Done=TRUE in an imported sheet become logged overrides (no XP)."""
    for _, t in all_tasks(plan):
        st = task_state(p, t["id"])
        if t.get("imported_done") and st["status"] == "todo":
            st["status"] = "override"
            p["overrides"].append({"task_id": t["id"], "at": store.now_iso(), "reason": "imported as done"})
            log(p, "override", t["id"], reason="imported as done")
    return p


def find_task(plan: dict, tid: str):
    for s, t in all_tasks(plan):
        if t["id"] == tid:
            return s, t
    raise KeyError(f"Unknown task id {tid}")


def is_done(p: dict, tid: str) -> bool:
    return p["tasks"].get(tid, {}).get("status") in {"done", "override"}


def session_left(p: dict, session: dict) -> list[dict]:
    return [t for t in session["tasks"] if not is_done(p, t["id"])]


# ---------- XP & levels ----------

def level_for(xp: int) -> dict:
    """Level L starts at 50*L*(L-1) XP: 0, 100, 300, 600, 1000, 1500..."""
    lvl = 1
    while xp >= 50 * (lvl + 1) * lvl:
        lvl += 1
    lo, hi = 50 * lvl * (lvl - 1), 50 * (lvl + 1) * lvl
    return {"level": lvl, "xp": xp, "into": xp - lo, "span": hi - lo}


def add_xp(p: dict, amount: int, reason: str, task_id: str | None = None) -> list[dict]:
    before = level_for(p["xp"])["level"]
    p["xp"] += amount
    log(p, "xp", task_id, amount=amount, reason=reason)
    events = [{"type": "xp", "amount": amount, "reason": reason}]
    after = level_for(p["xp"])["level"]
    if after > before:
        events.append({"type": "level_up", "level": after})
    return events


def record_pass(p: dict, plan: dict, tid: str, first_try: bool) -> list[dict]:
    st = task_state(p, tid)
    if st["status"] in {"done", "override"}:
        return []
    amount = XP_FIRST_TRY if first_try else XP_RETRY
    st.update(status="done", passed_at=store.now_iso(), xp=amount)
    p["review"].pop(tid, None)
    log(p, "pass", tid, first_try=first_try)
    events = add_xp(p, amount, "first try" if first_try else "passed on retry", tid)
    session, _ = find_task(plan, tid)
    events += maybe_award_session(p, session)
    return events


def maybe_award_session(p: dict, session: dict) -> list[dict]:
    if session["id"] in p["sessions_awarded"] or session_left(p, session):
        return []
    if any(p["tasks"].get(t["id"], {}).get("status") == "override" for t in session["tasks"]):
        return [{"type": "session_complete", "bonus": 0, "note": "overrides used, no session bonus"}]
    p["sessions_awarded"].append(session["id"])
    return [{"type": "session_complete", "bonus": XP_SESSION}] + add_xp(p, XP_SESSION, "full session")


def record_fail(p: dict, tid: str) -> int:
    st = task_state(p, tid)
    st["fails"] += 1
    log(p, "fail", tid, fails=st["fails"])
    return st["fails"]


def manual_override(p: dict, plan: dict, tid: str, reason: str) -> list[dict]:
    if not reason.strip():
        raise ValueError("An override needs a reason; it is logged.")
    st = task_state(p, tid)
    st["status"] = "override"
    p["review"].pop(tid, None)
    p["overrides"].append({"task_id": tid, "at": store.now_iso(), "reason": reason.strip()})
    log(p, "override", tid, reason=reason.strip())
    session, _ = find_task(plan, tid)
    return [{"type": "override", "xp": 0}] + maybe_award_session(p, session)


# ---------- streaks ----------

def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def streak_info(p: dict, today: date | None = None) -> dict:
    """A streak day = at least 1 sprint. One missed day per ISO week is bridged by a free freeze.
    Today not having a sprint yet never breaks the streak (the day isn't over)."""
    today = today or store.today()
    days = {date.fromisoformat(d) for d in p["sprint_days"]}
    if not days:
        return {"current": 0, "best": 0, "freeze_available": True, "today_done": False}

    def run_ending(end: date) -> tuple[int, set]:
        count, used, d = 0, set(), end
        while True:
            if d in days:
                count += 1
            elif _iso_week(d) not in used and (d - timedelta(days=1)) in days and count > 0:
                used.add(_iso_week(d))  # bridge a single missed day
            else:
                break
            d -= timedelta(days=1)
        return count, used

    start = today if today in days else today - timedelta(days=1)
    current, used = run_ending(start) if (start in days or start - timedelta(days=1) in days) else (0, set())
    best = max([run_ending(d)[0] for d in days] + [current])
    return {"current": current, "best": best, "today_done": today in days,
            "freeze_available": _iso_week(today) not in used}


def record_sprint(p: dict, minutes: int, intention: str, task_id: str | None) -> list[dict]:
    day = store.today().isoformat()
    first_today = day not in p["sprint_days"]
    if first_today:
        p["sprint_days"].append(day)
    p["sprints"].append({"at": store.now_iso(), "minutes": minutes, "intention": intention, "task_id": task_id})
    log(p, "sprint", task_id, minutes=minutes)
    return [{"type": "streak", **streak_info(p)}] if first_today else []


def set_last(p: dict, task_id: str | None, recap: str) -> None:
    p["last"] = {"task_id": task_id, "recap": recap[:200], "at": store.now_iso()}
