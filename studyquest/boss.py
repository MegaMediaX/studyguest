"""Boss fights: a timed mock exam built from the past exams in the course folder."""
import secrets
from datetime import datetime, timedelta

from . import ai, corpus, progress, prompts, store

LATE_GRACE_MIN = 5


def _cfg(boss_id: str) -> dict:
    for b in store.load_config().get("bosses", []):
        if b["id"] == boss_id:
            return b
    raise KeyError(f"Unknown boss {boss_id}")


def unlocked(p: dict, plan: dict, b: dict) -> bool:
    gate = [s for s in plan["sessions"] if s["session"] == b["unlock_after_session"]]
    return bool(gate) and all(not progress.session_left(p, s) for s in gate)


def list_bosses(p: dict, plan: dict) -> list[dict]:
    out = []
    for b in store.load_config().get("bosses", []):
        st = p["bosses"].get(b["id"], {})
        out.append({"id": b["id"], "name": b["name"], "course": b["course"], "minutes": b["minutes"],
                    "unlock_after": b["unlock_after_session"], "unlocked": unlocked(p, plan, b),
                    "beaten": st.get("beaten", False), "best": st.get("best"), "active": st.get("active")})
    return out


def _source_chunks(b: dict) -> list[dict]:
    chunks = []
    for d in corpus.load_docs():
        if d["course"] == b["course"] and d["file"] in b["sources"]:
            chunks += [{"file": d["file"], "unit": d["unit"], "n": pg["n"], "src": pg["src"], "text": pg["text"][:2500]}
                       for pg in d["pages"] if pg["src"] != "none"]
    return chunks[:14]


def start(p: dict, plan: dict, boss_id: str, force: bool = False) -> dict:
    b = _cfg(boss_id)
    if not (unlocked(p, plan, b) or force):
        raise PermissionError(f"Locked: finish “{b['unlock_after_session']}” first.")
    chunks = _source_chunks(b)
    if not chunks:
        raise ai.AIUnavailable("No readable past-exam pages found for this boss.")
    reply = ai.ask("claude", prompts.boss(b, chunks))
    qs = [q for q in reply.get("questions", []) if isinstance(q, dict) and q.get("q")][: b["questions"]]
    if not qs:
        raise ai.AIUnavailable("Claude returned no boss questions; try again.")
    run = {"id": secrets.token_hex(4), "started": store.now_iso(),
           "deadline": (datetime.now() + timedelta(minutes=b["minutes"])).isoformat(timespec="seconds"),
           "questions": qs}
    with progress.transaction() as fresh:
        fresh["bosses"].setdefault(boss_id, {})["active"] = run
        progress.log(fresh, "boss_start", None, boss=boss_id)
    return {"boss": b["name"], "run_id": run["id"], "deadline": run["deadline"], "minutes": b["minutes"],
            "questions": [{"q": q["q"], "points": q.get("points", 10),
                           "source": (f"{q['source'].get('file')} p{q['source'].get('n')}"
                                      if isinstance(q.get("source"), dict) else None)}
                          for q in qs]}


def submit(p: dict, plan: dict, boss_id: str, answers: list[str], photo: str | None = None) -> dict:
    st = p["bosses"].get(boss_id, {})
    run = st.get("active")
    if not run:
        raise KeyError("No active boss fight.")
    late = datetime.now() > datetime.fromisoformat(run["deadline"]) + timedelta(minutes=LATE_GRACE_MIN)
    task = {"text": _cfg(boss_id)["name"], "kind": "exercise"}
    r = ai.ask("claude", prompts.grade(task, run["questions"], answers, [], photo),
               images=[photo] if photo else [], cache=False)
    score = max(0.0, min(1.0, float(r.get("score", 0))))
    passed = score >= 0.7 and not late
    events = []
    with progress.transaction() as p:
        st = p["bosses"].get(boss_id, {})
        if (st.get("active") or {}).get("id") != run["id"]:
            raise KeyError("This boss fight was already submitted.")
        if passed and not st.get("beaten"):
            st["beaten"] = True
            events = progress.add_xp(p, progress.XP_BOSS, f"boss: {boss_id}")
        st["best"] = max(st.get("best") or 0, round(score, 2))
        st.setdefault("history", []).append({"at": store.now_iso(), "score": round(score, 2), "late": late})
        st["active"] = None
        progress.log(p, "boss_end", None, boss=boss_id, score=score, late=late)
    return {"score": round(score, 2), "passed": passed, "late": late, "reason": r.get("reason", ""),
            "feedback": [q.get("feedback", "") for q in r.get("per_question", [])],
            "answers": [q.get("answer", "") for q in run["questions"]], "events": events}
