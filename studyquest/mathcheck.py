"""Instant, local answer checking (no AI round-trip, so feedback is < 1 s).

- numbers: "0.5", "1/2", "3√2", "2*sqrt(3)/3", "pi/4", "1.2e-3", "45%"
- expressions in x, y, z, t, r, θ...: compared by evaluating both at random points
- MCQ: letter or index

Parsing uses Python's ast with a strict whitelist: no names, calls or attributes beyond the ones below.
"""
import ast
import math
import random
import re

FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
         "ln": math.log, "log": math.log, "asin": math.asin, "acos": math.acos, "atan": math.atan,
         "arcsin": math.asin, "arccos": math.acos, "arctan": math.atan, "abs": abs,
         "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh}
CONSTS = {"pi": math.pi, "e": math.e}
VAR_NAMES = {"x", "y", "z", "t", "u", "v", "w", "r", "s", "a", "b", "c", "k", "rho", "theta", "phi", "lam", "mu"}
OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
       ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b}
MAX_LEN = 300
MAX_POW = 50


class NotMath(ValueError):
    pass


def normalize(text: str) -> str:
    s = str(text).strip().lower()
    if len(s) > MAX_LEN:
        raise NotMath("too long")
    s = re.sub(r"^[a-z_]\w*(\([^)]*\))?\s*=\s*", "", s) if s.count("=") == 1 else s  # "f_x = 2x" -> "2x"
    repl = {"√": "sqrt", "π": "pi", "θ": "theta", "φ": "phi", "ϕ": "phi", "ρ": "rho", "λ": "lam", "μ": "mu",
            "×": "*", "·": "*", "⋅": "*", "÷": "/", "−": "-", "–": "-", "^": "**", "²": "**2", "³": "**3",
            "°": "*pi/180", "%": "/100"}
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"sqrt\s*(\d+(\.\d+)?|[a-z])", r"sqrt(\1)", s)       # sqrt2 -> sqrt(2)
    s = re.sub(r"(\d)\s*([a-z(])", r"\1*\2", s)                     # 2x, 3sqrt(2), 2(x+1)
    s = re.sub(r"\)\s*([\d(a-z])", r")*\1", s)                       # (x+1)(x-1), )x
    return s.replace(" ", "")


def _implicit_names(s: str) -> str:
    """xy -> x*y for runs of single-letter variables that aren't a known function/constant."""
    def fix(m: re.Match) -> str:
        word = m.group(0)
        if word in FUNCS or word in CONSTS or word in VAR_NAMES:
            return word
        if all(ch in VAR_NAMES for ch in word):
            return "*".join(word)
        return word
    return re.sub(r"[a-z]+", fix, s)


def _eval(node, env: dict):
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _eval(node.left, env), _eval(node.right, env)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POW:
            raise NotMath("exponent too large")
        return OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand, env)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.Name):
        if node.id in CONSTS:
            return CONSTS[node.id]
        if node.id in env:
            return env[node.id]
        raise NotMath(f"unknown name {node.id}")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and len(node.args) == 1:
        return FUNCS[node.func.id](_eval(node.args[0], env))
    raise NotMath("unsupported syntax")


def parse(text: str):
    s = _implicit_names(normalize(text))
    try:
        return ast.parse(s, mode="eval")
    except SyntaxError as e:
        raise NotMath(f"can't read “{text}”") from e


def free_vars(tree) -> set[str]:
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in CONSTS and n.id not in FUNCS}


def value(text: str, env: dict | None = None) -> float:
    return float(_eval(parse(text), env or {}))


def close(a: float, b: float, rel: float = 0.02, abs_tol: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol)


def same_number(student: str, key: str, rel: float = 0.02) -> bool:
    try:
        return close(value(student), value(key), rel)
    except (NotMath, ArithmeticError, ValueError, TypeError):
        return False


def same_expression(student: str, key: str, rel: float = 1e-4, trials: int = 6) -> bool:
    """Equal at several random points (in the key's variables) → treat as the same expression."""
    try:
        t_s, t_k = parse(student), parse(key)
    except NotMath:
        return False
    names = free_vars(t_k) | free_vars(t_s)
    if not free_vars(t_s) <= free_vars(t_k) | {"c"}:
        return False
    rnd = random.Random(7)
    ok = 0
    for _ in range(trials * 3):
        env = {n: rnd.uniform(0.3, 2.1) for n in names}
        try:
            a, b = float(_eval(t_s, env)), float(_eval(t_k, env))
        except (ArithmeticError, ValueError, NotMath, TypeError):
            continue  # outside the domain at this point; try another
        if not close(a, b, rel, 1e-9):
            return False
        ok += 1
        if ok >= trials:
            return True
    return ok >= 2


def split_multi(text: str) -> list[str]:
    """'(1, -2)' or '1, -2' or 'x=1, y=-2' -> ['1', '-2'] for point/vector answers."""
    s = str(text).strip().strip("()[]<>⟨⟩{}")
    parts = [p.strip() for p in re.split(r"[,;]", s) if p.strip()]
    return [re.sub(r"^[a-zA-Zα-ω_]\w*\s*=\s*", "", p) for p in parts]


def check(kind: str, student: str, key, choices: list | None = None, tolerance: float = 0.02) -> bool:
    student = str(student or "").strip()
    if not student:
        return False
    if kind == "mcq":
        idx = _choice_index(student, choices or [])
        return idx is not None and idx == int(key)
    if kind == "numeric":
        return same_number(student, str(key), tolerance)
    if kind == "expression":
        return same_expression(student, str(key))
    if kind == "multi":  # ordered tuple of numbers/expressions, e.g. a point or a vector
        s, k = split_multi(student), split_multi(str(key))
        return len(s) == len(k) and all(same_number(a, b, tolerance) or same_expression(a, b) for a, b in zip(s, k))
    raise ValueError(f"not locally checkable: {kind}")


def _choice_index(student: str, choices: list) -> int | None:
    s = student.strip().lower().rstrip(").")
    if len(s) == 1 and s in "abcdef":
        i = "abcdef".index(s)
        return i if i < max(len(choices), 1) else None
    if s.isdigit():
        return int(s) - 1 if 1 <= int(s) <= max(len(choices), 1) else None
    for i, c in enumerate(choices):
        if s == str(c).strip().lower():
            return i
    return None


def _single(text: str):
    """Parse one value/expression; a tuple ("one, one") is not a single answer."""
    tree = parse(text)
    if isinstance(tree.body, ast.Tuple):
        raise NotMath("several values where one was expected")
    return tree


def readable(kind: str, student: str, choices: list | None = None, key=None) -> bool:
    """Can we even read this answer? Unreadable input must not cost an attempt.
    Words like "idk" or "two" parse as variable names, so free variables are checked against the key."""
    student = str(student or "").strip()
    if not student:
        return False
    try:
        if kind == "mcq":
            return _choice_index(student, choices or []) is not None
        if kind == "numeric":
            return not free_vars(_single(student))
        if kind == "expression":
            allowed = (free_vars(_single(str(key))) if key is not None else VAR_NAMES) | {"c"}
            return free_vars(_single(student)) <= allowed
        if kind == "multi":
            parts = split_multi(student)
            key_parts = split_multi(str(key)) if key is not None else None
            if not parts or (key_parts is not None and len(parts) != len(key_parts)):
                return False
            for i, part in enumerate(parts):
                allowed = free_vars(_single(key_parts[i])) if key_parts else VAR_NAMES
                if not free_vars(_single(part)) <= allowed:
                    return False
            return True
    except NotMath:
        return False
    return True
