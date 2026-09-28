"""Second opinion on AI answer keys: Gemini solves the problems blind; mismatches accept both answers.

Runs at generation time (so during background prefetch) and is cached like every AI call.
A problem whose key and Gemini's answer disagree is marked unverified: the student's answer is
accepted if it matches either, and the UI says so. Failures here never block a battle.
"""
import json

from . import ai, mathcheck

CHECKABLE = {"mcq", "numeric", "expression", "multi"}


def _prompt(problems: list[tuple[int, dict]]) -> str:
    items = []
    for i, q in problems:
        item = {"i": i, "type": q["type"], "problem": q["prompt"]}
        if q["type"] == "mcq":
            item["choices"] = q["choices"]
        items.append(item)
    return f"""Solve each problem independently and carefully. Give only the final answer.
Formats: mcq = the 0-based index of the correct choice; numeric = a number or exact form like "sqrt(2)/2";
expression = in x, y, z using * and ** (e.g. "2*x*y"); multi = a tuple like "(1, -2)".
Problems: {json.dumps(items, ensure_ascii=False)}
Reply with JSON only: {{"answers": [{{"i": 0, "answer": "..."}}]}}"""


def verify(problems: list[dict]) -> list[dict]:
    todo = [(i, q) for i, q in enumerate(problems) if q["type"] in CHECKABLE]
    if not todo or not ai.gemini_enabled():
        return problems
    try:
        reply = ai.ask("gemini", _prompt(todo), effort="low")
    except ai.AIUnavailable:
        return problems
    answers = {a.get("i"): a.get("answer") for a in reply.get("answers", []) if isinstance(a, dict)}
    out = []
    for i, q in enumerate(problems):
        alt = answers.get(i)
        if q["type"] not in CHECKABLE or alt is None:
            out.append(q)
            continue
        if _agrees(q, alt):
            out.append({**q, "verified": True})
        else:
            out.append({**q, "verified": False, "alt_answers": [alt]})
    return out


def _agrees(q: dict, alt) -> bool:
    try:
        if q["type"] == "mcq":
            return int(alt) == int(q["answer"])
        return mathcheck.check(q["type"], str(alt), q["answer"], q.get("choices"))
    except (TypeError, ValueError):
        return False


def match_kind(q: dict, student: str) -> str | None:
    """'key' if it matches the answer key, 'alt' if only Gemini's disputed alternative, else None."""
    if mathcheck.check(q["type"], student, q["answer"], q.get("choices")):
        return "key"
    for alt in q.get("alt_answers", []):
        try:
            if mathcheck.check(q["type"], student, int(alt) if q["type"] == "mcq" else str(alt), q.get("choices")):
                return "alt"
        except (TypeError, ValueError):
            continue
    return None


def matches(q: dict, student: str) -> bool:
    """Correct if it matches the key, or (for an unverified key) Gemini's alternative."""
    return match_kind(q, student) is not None


def trap_feedback(q: dict, student: str) -> str | None:
    """A known wrong answer ("forgot to normalise") gets its targeted explanation."""
    for trap in q.get("traps", []):
        try:
            if mathcheck.check(q["type"], student, trap["answer"] if q["type"] != "mcq" else int(trap["answer"]),
                               q.get("choices")):
                return trap["why"]
        except (TypeError, ValueError, KeyError):
            continue
    return None
