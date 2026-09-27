"""The done-check: questions -> answers -> grade (Claude, Gemini second opinion) -> pass / hint+retry / review.

A task only becomes done through record_pass() here, or through progress.manual_override() (logged, 0 XP).
Check state lives in progress["checks"] so a page reload or a terminal session can continue it.
"""
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from . import ai, corpus, progress, prompts, review, store

HINT_SECONDS = 60
MAX_ATTEMPTS = 2
ACTION_MIN_CHARS = 12


def _threshold() -> float:
    return float(store.load_config().get("ai", {}).get("pass_threshold", 0.7))


def _valid_source(q: dict, chunks: list[dict]) -> bool:
    src = q.get("source") if isinstance(q.get("source"), dict) else {}
    try:
        n = int(src.get("n"))
    except (TypeError, ValueError):
        return False  # unparsable page number = invalid citation, dropped
    if not (isinstance(q.get("q"), str) and q["q"].strip()):
        return False
    src["n"] = n
    return any(c["file"] == src.get("file") and int(c["n"]) == n for c in chunks)


def _public_q(q: dict) -> dict:
    """What the browser sees: never the reference answer."""
    src = q.get("source")
    label = None
    if src:
        label = f"{src['file']}, {src.get('unit', 'page')} {src['n']}"
    return {"q": q["q"], "type": q.get("type", "explain"), "source": label}


def _generate(task: dict, session: dict, variant: str = "") -> tuple[list[dict], list[dict], str | None, bool]:
    """Returns (questions, chunks, notice, grounded)."""
    if task["kind"] == "action":
        q = {"q": "What exactly did you do? One line with the concrete detail (who, what was said, what you packed…).",
             "answer": "", "type": "action", "source": None}
        return [q], [], None, True

    chunks = corpus.retrieve(task["text"], session["session"], session["subject"])
    scanned = corpus.scanned_files_for(task["text"], session["subject"])
    notice = None
    missing = corpus.missing_files_for(task["text"], session["subject"])
    if scanned:
        notice = (f"“{', '.join(scanned)}” is scanned and has no text yet, so questions can't quote it. "
                  f"Run `python -m studyquest.corpus --ocr` once to fix this.")
    elif missing and not chunks:
        notice = (f"“{', '.join(missing)}” isn't in the course folders I extracted, so questions can't quote it. "
                  f"Add the file and run `python -m studyquest.corpus`.")
    n = 3 if task["kind"] == "reading" else 1
    reply = ai.ask("claude", prompts.questions(task, session, chunks, n, variant))
    qs = reply.get("questions", [])[:n]
    if chunks:
        units = {(c["file"], c["n"]): c["unit"] for c in chunks}
        qs = [q for q in qs if _valid_source(q, chunks)]
        for q in qs:
            q["source"]["unit"] = units[(q["source"]["file"], int(q["source"]["n"]))]
        if not qs:
            raise ai.AIUnavailable("Claude's questions didn't cite the provided sources; try again.")
        return qs, chunks, notice, True
    qs = [q for q in qs if isinstance(q, dict) and isinstance(q.get("q"), str) and q["q"].strip()]
    if not qs:
        raise ai.AIUnavailable("Claude returned no usable questions; try again.")
    for q in qs:
        q["source"] = None
        q.setdefault("answer", "")
    notice = notice or "No course file matched this task, so these are general topic questions (not source-quoted)."
    return qs, [], notice, False


def start(task_id: str, mode: str = "task") -> dict:
    """mode: 'task' (normal done-check) or 'review' (spaced review; fresh questions)."""
    p, plan = progress.load(), progress.load_plan()
    session, task = progress.find_task(plan, task_id)
    if mode == "task" and progress.is_done(p, task_id):
        return {"status": "already_done", "task": task}
    variant = ""
    if mode == "review":
        box = p["review"].get(task_id, {}).get("box", 0)
        variant = f"(Review round {box + 1}: ask different questions than a first check would.)"
    existing = _open_check(p, task_id, mode)
    if existing:  # resume: no fresh attempt 1, no skipping the hint wait
        return _check_view(existing, task, session)
    qs, chunks, notice, grounded = _generate(task, session, variant)
    with progress.transaction() as p:
        existing = _open_check(p, task_id, mode)
        if existing:
            return _check_view(existing, task, session)
        cid = secrets.token_hex(4)
        chk = {"id": cid, "task_id": task_id, "mode": mode, "kind": task["kind"], "attempt": 1, "questions": qs,
               "chunks": chunks, "notice": notice, "grounded": grounded, "created": store.now_iso(),
               "retry_after": None, "state": "open"}
        p.setdefault("checks", {})[cid] = chk
        progress.set_last(p, task_id, f"Started the check for “{task['text']}”.")
    return _check_view(chk, task, session)


def _open_check(p: dict, task_id: str, mode: str) -> dict | None:
    return next((c for c in p.get("checks", {}).values()
                 if c["task_id"] == task_id and c["mode"] == mode and c["state"] in {"open", "retry", "disagree"}),
                None)


def _check_view(chk: dict, task: dict, session: dict) -> dict:
    wait = 0
    if chk.get("retry_after"):
        wait = max(0, int((datetime.fromisoformat(chk["retry_after"]) - datetime.now()).total_seconds()))
    return {"status": "open", "check_id": chk["id"], "task": task, "session": session["session"],
            "questions": [_public_q(q) for q in chk["questions"]], "notice": chk["notice"],
            "grounded": chk["grounded"], "attempt": chk["attempt"], "retry_in": wait,
            "state": chk["state"], "hint": chk.get("hint"),
            "disagree": ({k: {"score": chk["pending"][k]["score"], "reason": chk["pending"][k].get("reason", "")}
                          for k in ("claude", "gemini")} if chk["state"] == "disagree" else None)}


def _grade_action(answers: list[str]) -> dict:
    ok = len((answers or [""])[0].strip()) >= ACTION_MIN_CHARS
    return {"score": 1.0 if ok else 0.0, "confidence": 1.0,
            "reason": "Concrete detail given." if ok else "Add the concrete detail (who / what / result).",
            "per_question": [{"ok": ok, "feedback": ""}]}


def _grade_ai(provider: str, task: dict, chk: dict, answers: list[str], photo: str | None) -> dict:
    images = [Path(photo)] if photo else []
    r = ai.ask(provider, prompts.grade(task, chk["questions"], answers, chk["chunks"], photo),
               images=images, cache=False)
    r["score"] = max(0.0, min(1.0, float(r.get("score", 0))))
    r["confidence"] = max(0.0, min(1.0, float(r.get("confidence", 0.5))))
    return r


def _needs_second_opinion(r: dict) -> bool:
    cfg = store.load_config().get("ai", {})
    lo, hi = cfg.get("second_opinion_band", [0.55, 0.85])
    return lo <= r["score"] <= hi or r["confidence"] < cfg.get("second_opinion_below_confidence", 0.7)


def _get_open(p: dict, check_id: str) -> dict:
    chk = p.get("checks", {}).get(check_id)
    if not chk or chk["state"] not in {"open", "retry"}:
        raise KeyError("This check is closed or unknown; start a new one.")
    return chk


def submit(check_id: str, answers: list[str], photo: str | None = None) -> dict:
    p, plan = progress.load(), progress.load_plan()
    chk = _get_open(p, check_id)
    if chk["retry_after"] and datetime.now() < datetime.fromisoformat(chk["retry_after"]):
        wait = int((datetime.fromisoformat(chk["retry_after"]) - datetime.now()).total_seconds())
        return {"status": "wait", "seconds": wait}
    _, task = progress.find_task(plan, chk["task_id"])
    answers = [a.strip() for a in (answers or [])] + [""] * (len(chk["questions"]) - len(answers or []))

    if chk["kind"] == "action":
        result = _grade_action(answers)
    else:
        result = _grade_ai("claude", task, chk, answers, photo)
        if ai.gemini_enabled() and _needs_second_opinion(result):
            try:
                second = _grade_ai("gemini", task, chk, answers, photo)
            except ai.AIUnavailable as e:
                second = None
                result["gemini_error"] = str(e)
            if second is not None:
                result["gemini"] = second
                if (result["score"] >= _threshold()) != (second["score"] >= _threshold()):
                    with progress.transaction() as p:
                        chk = _still_same(p, check_id, chk["attempt"])
                        chk.update(state="disagree", pending={"answers": answers, "claude": result, "gemini": second})
                    return {"status": "disagree", "check_id": check_id,
                            "claude": {"score": result["score"], "reason": result.get("reason", "")},
                            "gemini": {"score": second["score"], "reason": second.get("reason", "")}}
                result["score"] = (result["score"] + second["score"]) / 2
    hint = _maybe_hint(task, chk, answers, result)
    with progress.transaction() as p:
        chk = _still_same(p, check_id, chk["attempt"])
        return _apply(p, plan, chk, task, answers, result, hint)


def _still_same(p: dict, check_id: str, attempt: int) -> dict:
    """Grading ran outside the lock; make sure nobody graded this attempt meanwhile."""
    chk = _get_open(p, check_id)
    if chk["attempt"] != attempt:
        raise KeyError("This attempt was already graded (another tab?). Reload.")
    return chk


def _maybe_hint(task: dict, chk: dict, answers: list[str], result: dict) -> str | None:
    """Hints need an AI call, so they are made before the progress lock is taken."""
    if result["score"] >= _threshold() or chk["attempt"] >= MAX_ATTEMPTS:
        return None
    return _hint(task, chk, answers, [q.get("feedback", "") for q in result.get("per_question", [])])


def resolve(check_id: str, pick: str) -> dict:
    """The student picks which grader to trust when Claude and Gemini disagree."""
    if pick not in {"claude", "gemini"}:
        raise ValueError("pick must be 'claude' or 'gemini'")
    plan = progress.load_plan()
    peek = progress.load().get("checks", {}).get(check_id)
    if not peek or peek["state"] != "disagree":
        raise KeyError("Nothing to resolve for this check.")
    _, task = progress.find_task(plan, peek["task_id"])
    hint = _maybe_hint(task, peek, peek["pending"]["answers"], peek["pending"][pick])
    with progress.transaction() as p:
        chk = p.get("checks", {}).get(check_id)
        if not chk or chk["state"] != "disagree":
            raise KeyError("Nothing to resolve for this check.")
        pend = chk.pop("pending")
        result = {**pend[pick], "picked": pick}
        progress.log(p, "grader_pick", chk["task_id"], pick=pick,
                     claude=pend["claude"]["score"], gemini=pend["gemini"]["score"])
        return _apply(p, plan, chk, task, pend["answers"], result, hint)


def _apply(p: dict, plan: dict, chk: dict, task: dict, answers: list[str], result: dict,
           hint: str | None = None) -> dict:
    """Runs inside a progress transaction: no AI calls here."""
    tid = chk["task_id"]
    _prune(p, chk)
    chk.setdefault("attempts", []).append({"at": store.now_iso(), "answers": answers, "score": result["score"],
                                           "reason": result.get("reason", "")})
    progress.task_state(p, tid)["attempts"] += 1
    feedback = [q.get("feedback", "") for q in result.get("per_question", [])]
    base = {"score": round(result["score"], 2), "reason": result.get("reason", ""), "feedback": feedback,
            "graded_by": result.get("picked") or ("claude+gemini" if "gemini" in result else "claude")}

    if result["score"] >= _threshold():
        chk["state"] = "passed"
        if chk["mode"] == "review":
            events = review.on_pass(p, plan, tid)
        else:
            events = progress.record_pass(p, plan, tid, first_try=chk["attempt"] == 1)
        progress.set_last(p, tid, f"Passed “{task['text']}”.")
        return {"status": "passed", **base, "events": events}

    progress.record_fail(p, tid)
    if chk["attempt"] < MAX_ATTEMPTS:
        h = hint or "Re-read the source page named under the question, then try again."
        chk.update(state="retry", attempt=chk["attempt"] + 1, hint=h,
                   retry_after=(datetime.now() + timedelta(seconds=HINT_SECONDS)).isoformat(timespec="seconds"))
        progress.set_last(p, tid, f"Failed once on “{task['text']}”. Hint: {h}")
        # no per-question feedback on a retry: it tends to contain the answer
        return {"status": "retry", **{**base, "feedback": []}, "hint": h, "hint_seconds": HINT_SECONDS}

    chk["state"] = "failed"
    events = review.on_fail(p, plan, tid, from_review=chk["mode"] == "review")
    progress.set_last(p, tid, f"“{task['text']}” moved to review later.")
    return {"status": "review_later", **base, "events": events,
            "answers": [q["answer"] for q in chk["questions"]]}


def _prune(p: dict, current: dict) -> None:
    """Closed checks drop their source text so progress.json stays small and readable."""
    for c in p.get("checks", {}).values():
        if c is not current and c["state"] in {"passed", "failed"}:
            c.pop("chunks", None)
    for old in list(p["checks"])[:-200]:
        p["checks"].pop(old)


def _hint(task: dict, chk: dict, answers: list[str], feedback: list[str]) -> str:
    if chk["kind"] == "action":
        return "Write the concrete detail: who you contacted and what they said, or what exactly you did."
    try:
        return ai.short(ai.ask("claude", prompts.hint(task, chk["questions"], answers, feedback),
                               cache=False).get("hint", ""))
    except ai.AIUnavailable:
        return "Re-read the source page named under the question, then try again."


def stuck(task_id: str, check_id: str | None = None, q_index: int = 0) -> str:
    p, plan = progress.load(), progress.load_plan()
    session, task = progress.find_task(plan, task_id)
    chk = p.get("checks", {}).get(check_id) if check_id else None
    question = chk["questions"][q_index]["q"] if chk and q_index < len(chk["questions"]) else None
    chunks = chk["chunks"] if chk else corpus.retrieve(task["text"], session["session"], session["subject"], k=2)
    return ai.short(ai.ask("claude", prompts.stuck(task, question, chunks)).get("step", ""))


def explain(task_id: str, check_id: str | None = None, q_index: int = 0) -> dict:
    p, plan = progress.load(), progress.load_plan()
    _, task = progress.find_task(plan, task_id)
    chk = p.get("checks", {}).get(check_id) if check_id else None
    question = chk["questions"][q_index]["q"] if chk and q_index < len(chk["questions"]) else None
    provider = "gemini" if ai.gemini_enabled() else "claude"
    text = ai.ask(provider, prompts.explain_differently(task, question)).get("explanation", "")
    return {"by": provider, "text": ai.short(text, 5)}
