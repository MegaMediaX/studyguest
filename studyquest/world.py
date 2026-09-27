"""World map: each course is a region, each topic cluster a zone (config.json "world").

Zone states:
- locked:  not reachable yet (previous zone below Familiar and its sessions are still in the future)
- open:    playable
- sealed:  Mastered = ≥ 80% mastery AND confirmed by a spaced rematch win (can't be crammed)
Unsealed zones before an exam show corruption = max(0, 1 − days_left / 21). Copy only states what's left.
"""
from datetime import date

from . import progress, quest, review, store
from .corpus import course_for_subject

TIERS = [(0.8, "Proficient"), (0.4, "Familiar"), (0.01, "Attempted"), (0.0, "Unexplored")]
OPEN_BEFORE_EXAM_DAYS = 7
CORRUPTION_WINDOW = 21


def zone_of(session: dict, cfg: list[dict]) -> str | None:
    """Later zones in a region win ties (review keeps come after the topics they review)."""
    course = course_for_subject(session["subject"])
    title = session["session"].lower()
    hit = None
    for region in cfg:
        if region["course"] != course:
            continue
        for z in region["zones"]:
            if any(m.lower() in title for m in z["match"]):
                hit = z["id"]
    return hit


def _task_score(p: dict, tid: str) -> float:
    st = p["tasks"].get(tid, {})
    status = st.get("status", "todo")
    if status == "done":
        return 1.0 if p.get("stars", {}).get(tid, 0) >= 2 or st.get("xp") == progress.XP_FIRST_TRY else 0.7
    return {"review": 0.2, "override": 0.5}.get(status, 0.0)


def _confirmed(p: dict, task_ids: set[str]) -> bool:
    """A spaced rematch win on any task in the zone (Leitner card moved up or graduated)."""
    return any(e.get("task_id") in task_ids and e["event"] in {"review_pass", "review_graduated"} for e in p["log"])


def _tier(mastery: float, confirmed: bool) -> str:
    if mastery >= 0.8 and confirmed:
        return "Mastered"
    return next(name for floor, name in TIERS if mastery >= floor)


def build(p: dict, plan: dict) -> list[dict]:
    cfg = store.load_config().get("world", [])
    today = store.today()
    exams = quest.exams_countdown()
    due = {c["task_id"] for c in review.due_cards(p)}
    grouped: dict[str, list[dict]] = {}
    for s in plan["sessions"]:
        zid = zone_of(s, cfg)
        if zid:
            grouped.setdefault(zid, []).append(s)
    regions = []
    for region in cfg:
        exam = next((e for e in exams if e["course"] == region["course"]), None)
        zones, prev_tier = [], "Mastered"
        for i, z in enumerate(region["zones"]):
            zone = _zone(p, z, grouped.get(z["id"], []), exams, region["course"], due, today, i, prev_tier)
            prev_tier = zone["tier"]
            zones.append(zone)
        sealed = sum(1 for z in zones if z["state"] == "sealed")
        in_scope = [z for z in zones if exam and z["exam"] and z["exam"]["name"] == exam["name"]]
        regions.append({"course": region["course"], "region": region["region"], "icon": region.get("icon", ""),
                        "exam": exam, "zones": zones, "sealed": sealed,
                        "scope_sealed": sum(1 for z in in_scope if z["state"] == "sealed"), "scope_total": len(in_scope)})
    return regions


def _zone(p: dict, z: dict, sessions: list[dict], exams: list[dict], course: str, due: set[str],
          today: date, index: int, prev_tier: str) -> dict:
    tasks = [t for s in sessions for t in s["tasks"]]
    ids = {t["id"] for t in tasks}
    mastery = round(sum(_task_score(p, t["id"]) for t in tasks) / len(tasks), 2) if tasks else 0.0
    tier = _tier(mastery, _confirmed(p, ids))
    last_date = max((s["date"] for s in sessions if s["date"]), default=None)
    first_date = min((s["date"] for s in sessions if s["date"]), default=None)
    exam = next((e for e in exams if e["course"] == course and (not last_date or e["date"] >= last_date)), None)
    days = exam["days"] if exam else None
    reachable = (index == 0 or prev_tier in {"Familiar", "Proficient", "Mastered"}
                 or (first_date and first_date <= today.isoformat())
                 or (days is not None and days <= OPEN_BEFORE_EXAM_DAYS))
    state = "sealed" if tier == "Mastered" else "open" if reachable and tasks else "locked"
    corruption = 0.0 if state == "sealed" or days is None else round(max(0.0, 1 - days / CORRUPTION_WINDOW), 2)
    open_tasks = [t for t in tasks if not progress.is_done(p, t["id"]) and t["kind"] != "action"]
    bestiary = [b for tid, b in p.get("bestiary", {}).items() if tid in ids]
    return {"id": z["id"], "name": z["name"], "icon": z.get("icon", ""), "x": z["x"], "y": z["y"],
            "mastery": mastery, "tier": tier, "state": state, "corruption": corruption,
            "exam": {"name": exam["name"], "days": days} if exam else None,
            "sessions": [{"id": s["id"], "session": s["session"], "date_label": s["date_label"],
                          "left": len(progress.session_left(p, s)), "total": len(s["tasks"])} for s in sessions],
            "tasks": len(tasks), "done": sum(1 for t in tasks if progress.is_done(p, t["id"])),
            "open_tasks": [t["id"] for t in open_tasks], "rematches": len(ids & due),
            "enemies": [{"enemy": b["enemy"], "stars": b["stars"]} for b in bestiary]}


def zone_queue(p: dict, plan: dict, zone_id: str, max_floors: int) -> list[dict]:
    """A run in this zone: its due rematch first (spacing), then its open tasks in plan order."""
    zone = next((z for r in build(p, plan) for z in r["zones"] if z["id"] == zone_id), None)
    if not zone:
        raise KeyError(f"Unknown zone {zone_id}")
    if zone["state"] == "locked":
        raise ValueError(f"{zone['name']} is still locked. Get the previous zone to Familiar first.")
    cfg = store.load_config().get("world", [])
    ids = {t["id"] for s in plan["sessions"] if zone_of(s, cfg) == zone_id for t in s["tasks"]}
    queue = [{"task_id": c["task_id"], "mode": "review"} for c in review.due_cards(p) if c["task_id"] in ids][:1]
    queue += [{"task_id": tid, "mode": "task"} for tid in zone["open_tasks"] if tid not in {q["task_id"] for q in queue}]
    if not queue:
        raise KeyError(f"Nothing left to fight in {zone['name']}. Rematches will appear here when they're due.")
    return queue[:max_floors]
