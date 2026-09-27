"""All prompt templates in one place. Every reply must be JSON."""
import json


def _sources_block(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"<source file=\"{c['file']}\" {c['unit']}=\"{c['n']}\" via=\"{c['src']}\">\n{c['text']}\n</source>"
        for c in chunks)


def questions(task: dict, session: dict, chunks: list[dict], n: int, variant: str = "") -> str:
    kind = task["kind"]
    if kind == "exercise":
        ask = (f"Pick ONE concrete problem that belongs to this assignment and appears in the sources "
               f"(copy its statement). The student must give a short FINAL answer (a number, expression, "
               f"point, or classification). Give 1 question.")
    elif kind == "produce":
        ask = ("The student claims they produced this item. Ask 1 question that only someone who made it can "
               "answer quickly (e.g. 'write the 3 formulas from your sheet for X').")
    else:
        ask = (f"Write {n} short retrieval questions (a formula, a definition, or 'explain in one line'). "
               f"Each answerable in under 1 minute, from memory.")
    grounding = (
        "Use ONLY the sources below. Each question must cite the exact file and page/slide it came from."
        if chunks else
        "No course file matched this task. Write questions on the task's topic from standard course "
        "knowledge and set source to null.")
    return f"""You are a strict but kind tutor building a done-check for a Mechatronics student.
Task: {task['text']}
Session: {session['session']} ({session['subject']})
{ask}
{grounding} {variant}

Reply with JSON only:
{{"questions": [{{"q": "...", "answer": "short reference answer", "type": "formula|definition|explain|exercise",
  "source": {{"file": "exact file name from the source tag", "n": 12}}}}]}}

{_sources_block(chunks)}"""


def grade(task: dict, qs: list[dict], answers: list[str], chunks: list[dict], photo: str | None) -> str:
    items = [{"q": q["q"], "reference": q["answer"], "student": a} for q, a in zip(qs, answers)]
    photo_line = (f"\nThe student also uploaded a photo of their working: read the image file {photo} "
                  f"and grade the final answer and method in it.") if photo else ""
    return f"""Grade a student's done-check for the task "{task['text']}".
Accept equivalent forms (algebraically equal, different notation, rounding within 2%, same idea in other words).
A blank or "idk" answer scores 0 for that question.{photo_line}

Items: {json.dumps(items, ensure_ascii=False)}

Reply with JSON only:
{{"score": 0.0-1.0, "confidence": 0.0-1.0, "reason": "one sentence",
  "per_question": [{{"ok": true, "feedback": "max 1 sentence, name what is wrong without giving the answer"}}]}}

Sources for reference:
{_sources_block(chunks)}"""


def hint(task: dict, qs: list[dict], answers: list[str], feedback: list[str]) -> str:
    return f"""A student failed a quick check on "{task['text']}".
Questions: {json.dumps([q['q'] for q in qs], ensure_ascii=False)}
Their answers: {json.dumps(answers, ensure_ascii=False)}
Grader feedback: {json.dumps(feedback, ensure_ascii=False)}
Give ONE hint that points at the key idea they missed. Never give the final answer. Max 3 sentences.
Reply with JSON only: {{"hint": "..."}}"""


def stuck(task: dict, question: str | None, chunks: list[dict]) -> str:
    return f"""A student with ADHD is stuck on: "{question or task['text']}" (task: {task['text']}).
Give only the smallest next step they can do in 2 minutes. Not the solution. Max 3 sentences.
Reply with JSON only: {{"step": "..."}}

{_sources_block(chunks[:2])}"""


def explain_differently(task: dict, question: str | None) -> str:
    return f"""Explain the idea behind "{question or task['text']}" (course topic: {task['text']}) in a different way
than a textbook would: use an everyday analogy or a picture-in-words, then one tiny worked example.
Max 5 short sentences. Reply with JSON only: {{"explanation": "..."}}"""


def quick_wins(chunks: list[dict], topics: list[str]) -> str:
    return f"""Warm-up for a student: write 3 one-minute recall questions from yesterday's topics: {topics}.
Mix the topics. Use only the sources and cite file + page/slide for each.
Reply with JSON only: {{"questions": [{{"q": "...", "answer": "...", "type": "formula|definition|explain",
  "source": {{"file": "...", "n": 1}}}}]}}

{_sources_block(chunks)}"""


def boss(cfg: dict, chunks: list[dict]) -> str:
    return f"""Build a {cfg['minutes']}-minute mock exam "{cfg['name']}" with {cfg['questions']} questions.
Scope: {cfg['scope']}. Base every question on a past-exam question in the sources (you may change numbers
slightly). Each question needs a short final answer that can be checked.
Reply with JSON only: {{"questions": [{{"q": "...", "answer": "...", "points": 10,
  "source": {{"file": "...", "n": 1}}}}]}}

{_sources_block(chunks)}"""
