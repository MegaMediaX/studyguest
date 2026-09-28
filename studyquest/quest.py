"""Read-side views: today's quest, session verdict, world map, stats, CSV export."""
import csv
import io
from datetime import date

from . import progress, review, store
from .importer import all_tasks

STATUS_ICON = {"todo": "⬜", "done": "✅", "review": "🔁", "override": "☑️"}


def _status(p: dict, tid: str) -> str:
    return p["tasks"].get(tid, {}).get("status", "todo")


def _task_view(p: dict, t: dict) -> dict:
    st = _status(p, t["id"])
    return {"id": t["id"], "text": t["text"], "kind": t["kind"], "status": st, "icon": STATUS_ICON[st],
            "stars": p.get("stars", {}).get(t["id"], 0),
            "battle": (p.get("encounters", {}).get(t["id"]) or {}).get("state")}


def session_view(p: dict, s: dict, with_tasks: bool = True) -> dict:
    left = progress.session_left(p, s)
    v = {k: s[k] for k in ("id", "date", "date_label", "time", "subject", "session")}
    v.update(total=len(s["tasks"]), left=len(left), complete=not left)
    if with_tasks:
        v["tasks"] = [_task_view(p, t) for t in s["tasks"]]
    return v


def today_quest(p: dict, plan: dict) -> dict:
    today = store.today().isoformat()
    todays = [s for s in plan["sessions"] if s["date"] == today]
    backlog = [s for s in plan["sessions"] if s["date"] and s["date"] < today and progress.session_left(p, s)]
    # the first unfinished session today; if all are finished, the last one (so the UI shows its verdict)
    current = next((s for s in todays if progress.session_left(p, s)), todays[-1] if todays else None)
    upcoming = next((s for s in plan["sessions"] if s["date"] and s["date"] > today), None)
    label = "today"
    if current is None and not todays and upcoming:
        current, label = upcoming, "next"
    return {
        "date": today, "label": label,
        "session": session_view(p, current) if current else None,
        "today_sessions": [session_view(p, s, with_tasks=False) for s in todays],
        "all_done_today": bool(todays) and all(not progress.session_left(p, s) for s in todays),
        "next_session": session_view(p, upcoming, with_tasks=False) if upcoming else None,
        "backlog": {"sessions": len(backlog), "tasks": sum(len(progress.session_left(p, s)) for s in backlog)},
        "review_due": len(review.due_cards(p)),
        "rift": rift(p, plan, current),
        "mock_today": mock_today(p),
    }


def mock_today(p: dict) -> dict | None:
    """On a planned mock date (and not yet taken today), invite the timed paper mock."""
    today = store.today().isoformat()
    for b in store.load_config().get("bosses", []):
        if today in b.get("unlock_on", []):
            taken = any(h["at"][:10] == today for h in p.get("bosses", {}).get(b["id"], {}).get("history", []))
            if not taken:
                n = b["unlock_on"].index(today) + 1
                return {"boss_id": b["id"], "name": b["name"], "minutes": b["minutes"], "number": n}
    return None


def rift(p: dict, plan: dict, session: dict | None) -> dict | None:
    """The next exam for this session's course, counted in the same zones as the World map."""
    from . import world
    from .corpus import course_for_subject
    if not session:
        return None
    course = course_for_subject(session["subject"])
    region = next((r for r in world.build(p, plan) if r["course"] == course), None)
    if not region or not region["exam"]:
        return None
    scope = [z for z in region["zones"] if z["exam"] and z["exam"]["name"] == region["exam"]["name"]]
    nxt = next((z["name"] for z in scope if z["state"] != "sealed" and z["state"] != "locked"), None)
    return {"name": region["exam"]["name"], "days": region["exam"]["days"],
            "sealed": sum(1 for z in scope if z["state"] == "sealed"), "total": len(scope), "next": nxt, "unit": "zones"}


def exam_scope(p: dict, plan: dict) -> dict | None:
    """Tasks for the nearest exam only (so Stats shows what matters now, not a wall of 147)."""
    from .corpus import course_for_subject
    exam = next(iter(exams_countdown()), None)
    if not exam:
        return None
    sessions = [s for s in plan["sessions"] if s["date"] and s["date"] <= exam["date"]
                and course_for_subject(s["subject"]) == exam["course"]]
    ids = {s["id"] for s in sessions}
    tasks = [t for s in sessions for t in s["tasks"]]
    return {"exam": exam["name"], "days": exam["days"], "session_ids": sorted(ids),
            "done": sum(1 for t in tasks if progress.is_done(p, t["id"])), "total": len(tasks)}


def next_day_task_ids(p: dict, plan: dict) -> list[str]:
    today = store.today().isoformat()
    later = [s for s in plan["sessions"] if s["date"] and s["date"] > today]
    if not later:
        return []
    day = later[0]["date"]
    return [t["id"] for s in later if s["date"] == day for t in s["tasks"]
            if t["kind"] != "action" and not progress.is_done(p, t["id"])]


def next_free_slot(plan: dict, session: dict) -> dict | None:
    """First session of the same subject after today; else the next plan day that isn't an exam day."""
    today = store.today().isoformat()
    exam_days = {e["date"] for e in store.load_config().get("exams", [])}
    for s in plan["sessions"]:
        if s["date"] and s["date"] > today and s["subject"] == session["subject"] and s["id"] != session["id"]:
            return {"date": s["date"], "date_label": s["date_label"], "time": s["time"], "session": s["session"]}
    for s in plan["sessions"]:
        if s["date"] and s["date"] > today and s["date"] not in exam_days:
            return {"date": s["date"], "date_label": s["date_label"], "time": s["time"], "session": s["session"]}
    return None


def verdict(p: dict, plan: dict, session_id: str) -> dict:
    s = next((x for x in plan["sessions"] if x["id"] == session_id), None)
    if not s:
        raise KeyError(f"Unknown session {session_id}")
    left = progress.session_left(p, s)
    if not left:
        return {"complete": True, "headline": "✅ Session complete", "session": s["session"], "left": []}
    slot = next_free_slot(plan, s)
    tip = (f"Add them to {slot['date_label']} {slot['time']} ({slot['session']})." if slot
           else "No later slot in the plan; pick a free evening.")
    return {"complete": False, "headline": f"⚠️ {len(left)} task{'s' if len(left) > 1 else ''} left",
            "session": s["session"], "left": [_task_view(p, t) for t in left], "suggestion": tip, "slot": slot}


def world_map(p: dict, plan: dict) -> list[dict]:
    zones = {}
    for s in plan["sessions"]:
        zones.setdefault(s["subject"], []).append(session_view(p, s, with_tasks=False))
    return [{"zone": z, "levels": lv, "cleared": sum(1 for l in lv if l["complete"])} for z, lv in zones.items()]


def mastery(p: dict, plan: dict) -> list[dict]:
    """Per-topic score 0..1: first-try pass 1.0, retry/review pass 0.7, 🔁 0.2, override 0.5, todo 0."""
    out = []
    for s in plan["sessions"]:
        vals = []
        for t in s["tasks"]:
            st = p["tasks"].get(t["id"], {})
            status = st.get("status", "todo")
            if status == "done":
                vals.append(1.0 if st.get("xp") == progress.XP_FIRST_TRY else 0.7)
            else:
                vals.append({"review": 0.2, "override": 0.5}.get(status, 0.0))
        out.append({"id": s["id"], "subject": s["subject"], "topic": s["session"], "date": s["date"],
                    "score": round(sum(vals) / len(vals), 2) if vals else 0})
    return out


def exams_countdown() -> list[dict]:
    today = store.today()
    out = []
    for e in store.load_config().get("exams", []):
        days = (date.fromisoformat(e["date"]) - today).days
        if days >= 0:
            out.append({**e, "days": days})
    return sorted(out, key=lambda e: e["days"])


def stats(p: dict, plan: dict) -> dict:
    tasks = list(all_tasks(plan))
    counts = {k: 0 for k in STATUS_ICON}
    for _, t in tasks:
        counts[_status(p, t["id"])] += 1
    return {"level": progress.level_for(p["xp"]), "streak": progress.streak_info(p), "counts": counts,
            "scope": exam_scope(p, plan), "deck": len(p.get("problem_cards", {})),
            "total": len(tasks), "sprints": len(p["sprints"]), "overrides": len(p["overrides"]),
            "mastery": mastery(p, plan), "exams": exams_countdown(), "review_due": len(review.due_cards(p))}


def export_csv(p: dict, plan: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(plan.get("columns", ["Done", "Date", "Time", "Subject", "Session", "Task"]))
    for s, t in all_tasks(plan):
        done = "TRUE" if progress.is_done(p, t["id"]) else "FALSE"
        w.writerow([done, s["date_label"] or s["date"] or "", s["time"], s["subject"], s["session"], t["text"]])
    return buf.getvalue()


def write_export(p: dict, plan: dict) -> str:
    path = store.DATA / f"export_{store.today().isoformat()}.csv"
    path.write_text(export_csv(p, plan), encoding="utf-8")
    return str(path)

