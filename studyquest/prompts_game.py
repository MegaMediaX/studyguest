"""Prompts for battles. Every reply must be JSON."""
import json

from .prompts import _sources_block

TYPE_GUIDE = """Problem types (prefer the machine-checkable ones; the app grades them instantly):
- "mcq": 4 choices, "answer" = index 0-3. Good for concepts, traps, "which formula".
- "numeric": "answer" = a number or simple exact form like "sqrt(2)/2", "3*pi/4", "0.35".
- "expression": "answer" in x, y, z (or r, theta, t) using * and ** (e.g. "2*x*y + y**2", "exp(x*y)*cos(y)").
- "multi": an ordered tuple like a point, vector or pair, e.g. "(1, -2)" or "(2/3, 1/3, 2/3)".
- "short": one-line explanation; graded by a tutor. Use at most once."""


COURSE_FORMAT = {
    "MATH202": ("The real exam is written and you must show working. Use at most 1 mcq; prefer numeric, "
                "expression and multi problems whose final answer needs real working (not recognition)."),
    "MECT313": ("The real midterm is multiple choice, closed book. Make at least 3 of the 5 problems mcq with "
                "plausible distractors built from common mistakes (wrong ratio, forgot √3, mixed up primary/"
                "secondary, per-unit base errors), plus quick numeric problems."),
}


def encounter(task: dict, session: dict, chunks: list[dict], variant: str = "", course: str | None = None) -> str:
    if task["kind"] == "exercise":
        focus = ("This is an exercise task. Turn the assigned exercises into the problems: copy the actual problem "
                 "statements from the sources when they are there (numbers included) and ask for the final result. "
                 "If a solution appears in the sources, use it for the answer key; otherwise solve carefully.")
    elif task["kind"] == "produce":
        focus = ("The student must produce a summary (e.g. formula sheet). Make problems that make them recall and "
                 "write each key formula or item (expression/mcq), so doing the battle builds the sheet.")
    else:
        focus = ("This is a learning task. Teach the idea in the lesson, then check and apply it: start with 1-2 easy "
                 "concept problems, then computations that use the idea.")
    return f"""You design a short learning battle for a Mechatronics student with ADHD, inside a study game.
Task: {task['text']}
Session: {session['session']} ({session['subject']})
{focus}
{COURSE_FORMAT.get(course or "", "")}
{variant}

Write:
1. "enemy": a fun 2-3 word monster name tied to the topic (e.g. "Gradient Golem", "Reluctance Wraith").
2. "lesson": the key idea in at most 4 short bullet points (≤ 20 words each), one key "formula" line, and one
   tiny worked "example" with 2-4 steps. Plain text math (∇f, f_x, √, ∫, θ).
3. "problems": 5 problems, difficulty 1 (easy) to 3 (hard), mixed types. Each has 3 "hints": a nudge, a concrete
   next step, and a full worked solution (the last one). Plus "explain": 1 sentence on why the answer is right,
   and "rule": the general rule, formula or theorem needed, stated WITHOUT this problem's numbers (1 line),
   and "traps": 1-2 common WRONG answers students give, each with "why" = the mistake in one sentence
   (e.g. {{"answer": "-5", "why": "You used v itself instead of the unit vector v/|v|."}}).
   Numbers must be exact and self-consistent; double-check every answer key.
{TYPE_GUIDE}
Base the problems on the sources below and cite them with the exact file name and page/slide number.

Reply with JSON only:
{{"enemy": "...", "lesson": {{"title": "...", "points": ["..."], "formula": "...",
  "example": {{"problem": "...", "steps": ["..."], "answer": "..."}}}},
 "problems": [{{"type": "numeric", "prompt": "...", "answer": "...", "choices": null, "difficulty": 1,
   "hints": ["nudge", "step", "worked solution"], "explain": "...", "rule": "D_u f = ∇f · u, with u a unit vector",
   "traps": [{{"answer": "...", "why": "..."}}],
   "source": {{"file": "...", "n": 1}}}}]}}

{_sources_block(chunks)}"""


def rule_for(prob: dict) -> str:
    return f"""State the general rule, formula or theorem a student must apply to solve this problem.
Write it generally (symbols, not this problem's numbers), max 2 short lines, no steps and no final answer.
Problem: {prob['prompt']}
Reply with JSON only: {{"rule": "..."}}"""


def judge_short(prob: dict, answer: str) -> str:
    return f"""Grade a one-line student answer. Accept the same idea in other words; be kind but accurate.
Question: {prob['prompt']}
Reference: {prob['answer']}
Student: {json.dumps(answer, ensure_ascii=False)}
Reply with JSON only: {{"score": 0.0-1.0, "feedback": "max 1 sentence, don't give the answer away if wrong"}}"""


def judge_work(prob: dict, answer: str, photo: str) -> str:
    typed = f"The student also typed this final answer: {json.dumps(answer, ensure_ascii=False)}." if answer.strip() \
        else "The student typed no answer: read the final answer from the photo."
    return f"""Check a student's handwritten working for one problem. Read the image file {photo}.
Problem: {prob['prompt']}
Answer key: {prob['answer']}  ({prob.get('explain', '')})
{typed}
Judge like an exam marker: is the final answer right (equivalent forms and rounding within 2% are fine), and is the
method valid (right formula, steps follow, no lucky cancellation)? If anything is wrong, name the FIRST wrong step
concretely ("line 3: you used v instead of the unit vector v/|v|"). NEVER state the correct final answer or
the key's numbers in the feedback: the student may still retry. If there is no working at all, say what the first
step should be about, not its result. If the photo is unreadable or not about this problem, set readable false.
Reply with JSON only: {{"readable": true, "final_answer": "...", "final_correct": true, "method_ok": true,
  "feedback": "max 2 sentences"}}"""


def judge_dispute(prob: dict, answer: str) -> str:
    return f"""An auto-grader marked a student's answer wrong. Decide if the student is actually right
(equivalent form, different but valid notation, rounding, or the answer key itself is wrong).
Question: {prob['prompt']}
Answer key: {prob['answer']}  ({prob.get('explain', '')})
Student: {json.dumps(answer, ensure_ascii=False)}
Reply with JSON only: {{"student_correct": true, "reason": "one sentence"}}"""
