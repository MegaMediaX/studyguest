"""Import a checklist (study CSV, Google Sheets CSV export, or markdown) into data/plan.json."""
import csv
import hashlib
import io
import re
from datetime import date, datetime
from pathlib import Path

from . import store

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

HEADER_ALIASES = {
    "done": {"done", "status", "complete", "completed", "✓"},
    "date": {"date", "day"},
    "time": {"time", "slot", "hours"},
    "subject": {"subject", "course", "module"},
    "session": {"session", "topic", "block", "section"},
    "task": {"task", "todo", "item", "description"},
}

ACTION_RE = re.compile(r"^(ask|tell|pack|sleep|confirm|email|book|print)\b", re.I)
EXERCISE_RE = re.compile(
    r"(^(do|solve|redo|sit|correct|check with)\b|textbook\s+\d|\bex\b|\bex\.|\bq\d|assignment|exercise|(?<!2 )problems?\b(?! and)|"
    r"examples?\s+\d|mock|past-exam|\(\d+ examples\))", re.I)
PRODUCE_RE = re.compile(r"^(write|finalize|list)\b|formula sheet", re.I)


def classify(task: str) -> str:
    """reading = recall questions, exercise = final answer/photo, action = one-line evidence,
    produce = describe what you made (formula sheet, weak-topic list)."""
    if ACTION_RE.search(task):
        return "action"
    if PRODUCE_RE.search(task) and not task.lower().startswith("read"):
        return "produce"
    if EXERCISE_RE.search(task) and not task.lower().startswith("read"):
        return "exercise"
    return "reading"


def parse_date(raw: str, year: int) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})", raw) or re.search(r"([A-Za-z]{3})\w*\s+(\d{1,2})", raw)
    if not m:
        return None
    a, b = m.groups()
    day, mon = (a, b) if a.isdigit() else (b, a)
    month = MONTHS.get(mon[:3].lower())
    return date(year, month, int(day)).isoformat() if month else None


def _norm_header(h: str) -> str | None:
    key = h.strip().lower()
    for canon, names in HEADER_ALIASES.items():
        if key in names:
            return canon
    return None


def _truthy(v: str) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y", "x", "✓", "✅", "done"}


def parse_csv(text: str, year: int) -> list[dict]:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = [_norm_header(h) for h in next(reader)]
    if "task" not in header:
        raise ValueError("CSV needs a 'Task' column (got: %s)" % header)
    rows = []
    for raw in reader:
        if not any(c.strip() for c in raw):
            continue
        r = {k: (raw[i] if i < len(raw) else "") for i, k in enumerate(header) if k}
        rows.append({
            "done": _truthy(r.get("done", "")),
            "date": parse_date(r.get("date", ""), year),
            "date_label": r.get("date", "").strip(),
            "time": r.get("time", "").strip(),
            "subject": r.get("subject", "").strip() or "General",
            "session": r.get("session", "").strip() or "Session",
            "task": r["task"].strip(),
        })
    return rows


def parse_markdown(text: str, year: int) -> list[dict]:
    """Headings name sessions ('## Mon 28 Sep · 21:00–22:00 · Calc II · 14.5 Gradient');
    '- [ ]' / '- [x]' lines are tasks."""
    rows, ctx = [], {"date": None, "date_label": "", "time": "", "subject": "General", "session": "Session"}
    for line in text.splitlines():
        h = re.match(r"^#{1,6}\s+(.*)", line)
        if h:
            parts = [p.strip() for p in re.split(r"\s[·|]\s", h.group(1))]
            d = parse_date(parts[0], year)
            time_part = next((p for p in parts if re.search(r"\d{1,2}:\d{2}", p)), "")
            rest = [p for p in parts if p != time_part and not (d and p == parts[0])]
            ctx = {"date": d, "date_label": parts[0] if d else "", "time": time_part,
                   "subject": rest[0] if len(rest) > 1 else ctx["subject"],
                   "session": rest[-1] if rest else h.group(1)}
            continue
        t = re.match(r"^\s*[-*]\s+\[( |x|X)\]\s+(.*)", line)
        if t:
            rows.append({**ctx, "done": t.group(1).lower() == "x", "task": t.group(2).strip()})
    return rows


def rows_to_plan(rows: list[dict], source: str) -> dict:
    sessions, index, seen = [], {}, {}
    for r in rows:
        skey = (r["date"], r["time"], r["subject"], r["session"])
        if skey not in index:
            sid = hashlib.sha1("|".join(map(str, skey)).encode()).hexdigest()[:8]
            index[skey] = {"id": sid, "date": r["date"], "date_label": r["date_label"], "time": r["time"],
                           "subject": r["subject"], "session": r["session"], "tasks": []}
            sessions.append(index[skey])
        # occurrence counter: two identical task lines in one session stay two tasks
        base = "|".join([str(r["date"]), r["session"], r["task"]])
        n = seen.get(base, 0)
        seen[base] = n + 1
        tid = hashlib.sha1(f"{base}|{n}".encode()).hexdigest()[:10]
        index[skey]["tasks"].append({"id": tid, "text": r["task"], "kind": classify(r["task"]),
                                     "imported_done": r["done"]})
    return {"source": source, "imported_at": store.now_iso(), "sessions": sessions,
            "columns": ["Done", "Date", "Time", "Subject", "Session", "Task"]}


def import_file(path: str | Path) -> dict:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    year = store.load_config().get("year", store.today().year)
    rows = parse_markdown(text, year) if path.suffix.lower() in {".md", ".markdown", ".txt"} else parse_csv(text, year)
    if not rows:
        raise ValueError(f"No tasks found in {path.name}")
    plan = rows_to_plan(rows, path.name)
    store.write_json(store.PLAN_FILE, plan)
    return plan


def all_tasks(plan: dict):
    for s in plan["sessions"]:
        for t in s["tasks"]:
            yield s, t
