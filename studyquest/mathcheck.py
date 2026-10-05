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
         "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
         "sec": lambda v: 1 / math.cos(v), "csc": lambda v: 1 / math.sin(v), "cot": lambda v: 1 / math.tan(v)}
_FN_RE = "|".join(sorted(FUNCS, key=len, reverse=True))
DNE_WORDS = {"dne", "doesnotexist", "doesn'texist", "undefined", "noLimit".lower(), "nolimit"}
INF_WORDS = {"∞": "inf", "+∞": "inf", "infinity": "inf", "+infinity": "inf", "inf": "inf",
             "-∞": "-inf", "−∞": "-inf", "-infinity": "-inf", "−infinity": "-inf", "-inf": "-inf"}
CONSTS = {"pi": math.pi, "e": math.e}
VAR_NAMES = {"x", "y", "z", "t", "u", "v", "w", "r", "s", "a", "b", "c", "k", "rho", "theta", "phi", "lam", "mu"}
OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
       ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b}
MAX_LEN = 300
MAX_POW = 50


class NotMath(ValueError):
    pass


def _latex(s: str) -> str:
    r"""Tolerate LaTeX-ish input (the AI's own explanations use it): \frac{a}{b}, e^{xy}, \cdot, \sin."""
    s = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
    for a, b in (("\\cdot", "*"), ("\\times", "*"), ("\\left", ""), ("\\right", ""), ("\\", "")):
        s = s.replace(a, b)
    return s.replace("{", "(").replace("}", ")")


def _functions(s: str) -> str:
    """sin^2(x) -> (sin(x))^2 ; 'ln t', 'sin 2x', 'cosx', 'lnt' -> ln(t), sin(2x), cos(x), ln(t)."""
    s = re.sub(rf"\b({_FN_RE})\s*\^\s*(\d+)\s*\(([^()]*)\)", r"(\1(\3))^\2", s)
    s = re.sub(rf"\b({_FN_RE})\s*\^\s*(\d+)\s*(\d*[a-z]+)", r"(\1(\3))^\2", s)
    s = re.sub(rf"\b({_FN_RE})\s+(\d+(?:\.\d+)?[a-z]*|[a-z]+)\b", r"\1(\2)", s)   # 'ln t', 'sin 2x'

    def glued(m: re.Match) -> str:  # 'cosx' -> cos(x), but leave real names like 'cosh', 'sqrt'
        word = m.group(0)
        if word in FUNCS or word in CONSTS or word in VAR_NAMES:
            return word
        for fn in sorted(FUNCS, key=len, reverse=True):
            rest = word[len(fn):]
            if word.startswith(fn) and rest and all(ch in VAR_NAMES or ch == "e" for ch in rest):
                return f"{fn}({rest})"
        return word
    s = re.sub(r"[a-z]+(?!\()", glued, s)
    return re.sub(r"([a-z0-9)])\s+([a-z(])", r"\1*\2", s)  # 't ln(t)' -> t*ln(t) before spaces vanish


def _strip_lhs(s: str) -> str:
    """'f_x = 2x', 'dw/dt = 1', '∂z/∂x = ...', 'f_x(1,2) = 3' -> just the right-hand side."""
    if s.count("=") != 1:
        return s
    lhs, rhs = s.split("=")
    if re.fullmatch(r"\s*[a-z∂_'′/ ]*(\([^)]*\))?\s*", lhs) and lhs.strip():
        return rhs
    return s


def normalize(text: str) -> str:
    s = str(text).strip().lower()
    if len(s) > MAX_LEN:
        raise NotMath("too long")
    s = re.sub(r"\b(sin|cos|tan)\s*\^\s*\(?\s*[-−]\s*1\s*\)?", r"arc\1", s)  # tan^-1 -> arctan
    s = _strip_lhs(_functions(_latex(s)))
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
        if len(word) > 1 and all(ch in VAR_NAMES or ch == "e" for ch in word):
            return "*".join(word)  # 'xy' -> x*y, 'ye' -> y*e (e = Euler's number)
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
        tree = ast.parse(s, mode="eval")
    except SyntaxError as e:
        raise NotMath(f"can't read “{text}”") from e
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    if any(isinstance(n, ast.Name) and n.id in FUNCS and id(n) not in called for n in ast.walk(tree)):
        raise NotMath("a function without its argument, e.g. √ instead of √(2)")
    return tree


def free_vars(tree) -> set[str]:
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in CONSTS and n.id not in FUNCS}


def value(text: str, env: dict | None = None) -> float:
    return float(_eval(parse(text), env or {}))


def close(a: float, b: float, rel: float = 0.02, abs_tol: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol)


def special(text: str) -> str | None:
    """'DNE' / '∞' style answers (limits) as sentinels."""
    t = re.sub(r"\s+", "", str(text).strip().lower())
    if t in DNE_WORDS:
        return "dne"
    return INF_WORDS.get(t)


def same_number(student: str, key: str, rel: float = 0.02) -> bool:
    if special(student) or special(key):
        return special(student) == special(key)
    student = re.sub(r"^(-?\d+),(\d+)$", r"\1.\2", str(student).strip())  # 1,5 -> 1.5 (comma decimal)
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


def _ijk(text: str) -> list[str] | None:
    """'2i - 3j + k', '1i+2j' -> ['2', '-3', '1'] (None if not unit-vector notation)."""
    t = str(text).strip().replace("−", "-").replace(" ", "")
    if "," in t or not re.search(r"[ijk](?=[+\-]|$)", t):
        return None
    parts = {"i": "0", "j": "0", "k": "0"}
    depth, term, terms = 0, "", []
    for ch in t:
        depth += ch == "("
        depth -= ch == ")"
        if ch in "+-" and depth == 0 and term:
            terms.append(term)
            term = ""
        term += ch
    terms.append(term)
    for term in terms:
        m = re.search(r"\*?([ijk])$", term)  # the unit vector ends its term: '2i', 'x*j', 'y^2k'
        if not m:
            return None
        coef = (term[:m.start()] + term[m.end():]).strip("*")
        coef = {"": "1", "+": "1", "-": "-1"}.get(coef, coef)
        parts[m.group(1)] = coef
    used = "ijk" if "k" in t else "ij"
    return [parts[c] for c in used]


def _unwrap(s: str) -> str:
    """Remove ONE pair of outer brackets only if it encloses the whole text: '(sin(x), cos(y))' -> 'sin(x), cos(y)'."""
    pairs = {"(": ")", "[": "]", "<": ">", "⟨": "⟩", "{": "}"}
    if len(s) >= 2 and s[0] in pairs and s[-1] == pairs[s[0]]:
        depth = 0
        for i, ch in enumerate(s):
            depth += ch in pairs
            depth -= ch in pairs.values()
            if depth == 0 and i < len(s) - 1:
                return s  # the first bracket closes early: '(a)+(b)' isn't wrapped
        return s[1:-1]
    return s


def split_multi(text: str) -> list[str]:
    """'(1, -2)' or '1, -2' or 'x=1, y=-2' or '1i - 2j' -> ['1', '-2'] for point/vector answers."""
    ijk = _ijk(text)
    if ijk:
        return ijk
    s = _unwrap(str(text).strip())
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
    if kind == "multi" and _many_points(str(key)):
        kind = "set"
    if kind == "multi":  # ordered tuple of numbers/expressions, e.g. a point or a vector
        s, k = split_multi(student), split_multi(str(key))
        return len(s) == len(k) and all(same_number(a, b, tolerance) or same_expression(a, b) for a, b in zip(s, k))
    if kind == "equation":
        return same_equation(student, str(key))
    if kind == "line":
        return same_line(student, str(key))
    if kind == "set":
        return same_set(student, str(key), tolerance)
    if kind == "classify":
        return classify_label(student) is not None and classify_label(student) == classify_label(str(key))
    if kind == "direction":
        return same_direction(student, str(key))
    raise ValueError(f"not locally checkable: {kind}")


# ---------- calculus answer kinds ----------

def _side_diff(eq: str):
    """'2x+2y+z=6' -> parsed (lhs - rhs)."""
    if str(eq).count("=") != 1:
        raise NotMath("an equation needs exactly one '='")
    lhs, rhs = str(eq).split("=")
    return parse(f"({lhs}) - ({rhs})")


def same_equation(student: str, key: str, trials: int = 8) -> bool:
    """Same surface/plane: student's (lhs - rhs) is a constant non-zero multiple of the key's."""
    try:
        fs, fk = _side_diff(student), _side_diff(key)
    except NotMath:
        return False
    names = free_vars(fs) | free_vars(fk)
    rnd = random.Random(11)
    ratio, ok = None, 0
    for _ in range(trials * 3):
        env = {n: rnd.uniform(-2.3, 2.7) for n in names}
        try:
            a, b = float(_eval(fs, env)), float(_eval(fk, env))
        except (ArithmeticError, ValueError, NotMath, TypeError):
            continue
        if abs(b) < 1e-9:
            if abs(a) > 1e-6:
                return False
            continue
        r = a / b
        if ratio is None:
            ratio = r
        elif not close(r, ratio, 1e-6, 1e-9):
            return False
        ok += 1
        if ok >= trials:
            break
    return ratio is not None and abs(ratio) > 1e-9 and ok >= 3


def _line_parts(text: str) -> list[str]:
    """'x=1+2t, y=1+2t, z=2+t' or '(1+2t, 1+2t, 2+t)' or 'r(t) = <1+2t, ...>' -> component expressions in t."""
    t = str(text)
    if re.match(r"^\s*r\s*\(\s*t\s*\)\s*=", t):
        t = t.split("=", 1)[1]
    return split_multi(t)


def same_line(student: str, key: str) -> bool:
    """Same line in space: a student point lies on the key line and the directions are parallel."""
    try:
        s_parts, k_parts = _line_parts(student), _line_parts(key)
        if len(s_parts) != len(k_parts) or len(s_parts) < 2:
            return False
        ts = [parse(x) for x in s_parts]
        tk = [parse(x) for x in k_parts]
        s0 = [float(_eval(x, {"t": 0.0})) for x in ts]
        s1 = [float(_eval(x, {"t": 1.0})) for x in ts]
        k0 = [float(_eval(x, {"t": 0.0})) for x in tk]
        k1 = [float(_eval(x, {"t": 1.0})) for x in tk]
    except (NotMath, ArithmeticError, ValueError, TypeError):
        return False
    ds = [b - a for a, b in zip(s0, s1)]
    dk = [b - a for a, b in zip(k0, k1)]
    return _parallel(ds, dk) and _parallel([a - b for a, b in zip(s0, k0)], dk, allow_zero=True)


def _parallel(u: list[float], v: list[float], allow_zero: bool = False) -> bool:
    nu, nv = math.sqrt(sum(a * a for a in u)), math.sqrt(sum(a * a for a in v))
    if nu < 1e-9:
        return allow_zero
    if nv < 1e-9:
        return False
    cos = abs(sum(a * b for a, b in zip(u, v))) / (nu * nv)
    return cos > 1 - 1e-6


def same_direction(student: str, key: str) -> bool:
    """A direction vector: any positive multiple counts ((3,-4) == (3/5,-4/5))."""
    try:
        s = [value(x) for x in split_multi(student)]
        k = [value(x) for x in split_multi(key)]
    except (NotMath, ArithmeticError, ValueError, TypeError):
        return False
    if len(s) != len(k) or not _parallel(s, k):
        return False
    return sum(a * b for a, b in zip(s, k)) > 0


def split_points(text: str) -> list[str]:
    """'(0,0), (1,1)' or '{(0,0);(1,-1)}' -> ['(0,0)', '(1,1)']; bare numbers '1, -1' -> ['1', '-1']."""
    t = str(text).strip().strip("{}[]")
    pts = re.findall(r"[(<⟨][^()<>⟨⟩]*[)>⟩]", t)
    if pts:
        return pts
    return [x.strip() for x in re.split(r"[,;]| and ", t) if x.strip()]


def same_set(student: str, key: str, tolerance: float = 0.02) -> bool:
    """Unordered set of points/values (critical points, Lagrange candidates)."""
    s, k = split_points(student), split_points(key)
    if len(s) != len(k):
        return False
    left = list(k)
    for item in s:
        match = next((kk for kk in left if check("multi" if kk.startswith(("(", "<", "⟨")) else "numeric",
                                                    item, kk, None, tolerance)), None)
        if match is None:
            return False
        left.remove(match)
    return True


CLASSES = [("inconclusive", ("inconclusive", "test fails", "no conclusion", "can't tell", "cannot tell",
                             "d = 0", "d=0")),
           ("saddle", ("saddle",)), ("dne", ("dne", "does not exist", "doesn't exist")),
           ("max", ("max",)), ("min", ("min",)), ("none", ("none", "neither", "no extrem"))]


def classify_label(text: str) -> str | None:
    """'local maximum', 'rel. max', 'Saddle point' -> 'local max' / 'saddle'...; None if unrecognised."""
    t = str(text).strip().lower()
    for label, words in CLASSES:
        if any(w in t for w in words):
            if label in {"max", "min"}:
                scope = "absolute" if any(w in t for w in ("abs", "global")) else "local"
                return f"{scope} {label}"
            return label
    return None


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


def _many_points(key: str) -> bool:
    """A 'multi' key like '(1, -2), (-1, -2)' is a list of points: order shouldn't matter."""
    return len(re.findall(r"[(<⟨][^()<>⟨⟩]*[)>⟩]", key)) >= 2


def readable(kind: str, student: str, choices: list | None = None, key=None) -> bool:
    """Can we even read this answer? Unreadable input must not cost an attempt.
    Words like "idk" or "two" parse as variable names, so free variables are checked against the key."""
    student = str(student or "").strip()
    if not student:
        return False
    if kind == "multi" and key is not None and _many_points(str(key)):
        kind = "set"
    try:
        if kind == "mcq":
            return _choice_index(student, choices or []) is not None
        if kind == "numeric":
            if special(student):
                return True
            student = re.sub(r"^(-?\d+),(\d+)$", r"\1.\2", student)
            return not free_vars(_single(student))
        if kind == "expression":
            allowed = (free_vars(_single(str(key))) if key is not None else VAR_NAMES) | {"c"}
            return free_vars(_single(student)) <= allowed
        if kind == "equation":
            _side_diff(student)
            return True
        if kind == "line":
            parts = _line_parts(student)
            return len(parts) >= 2 and all(free_vars(parse(x)) <= {"t", "s"} for x in parts)
        if kind == "set":
            return bool(split_points(student))
        if kind == "classify":
            return classify_label(student) is not None
        if kind == "direction":
            return all(not free_vars(_single(x)) for x in split_multi(student)) and bool(split_multi(student))
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


_PRETTY = ((" ** ", "^"), (" * ", "·"), ("sqrt", "√"), ("pi", "π"), ("theta", "θ"), ("phi", "φ"), ("rho", "ρ"),
           ("lam", "λ"), ("mu", "μ"))


def pretty(text: str) -> str:
    """How the grader reads one value: '2xy + y^2' -> '2·x·y + y^2'; 'e^xy' -> 'e^x·y' (shows the slip)."""
    s = ast.unparse(_single(text))
    for a, b in _PRETTY:
        s = s.replace(a, b)
    s = re.sub(r"\bdne\b", "DNE", re.sub(r"\binf\b", "∞", s))
    return re.sub(r"(?<![\^\d.])(\d+(?:\.\d+)?)·([a-zα-ω√(])", r"\1\2", s)  # 2·x -> 2x, not x^2·ln(x)


def _approx(text: str) -> str | None:
    try:
        v = value(text)
    except (NotMath, ArithmeticError, ValueError, TypeError):
        return None
    return None if abs(v - round(v)) < 1e-9 else f"≈ {v:.4g}"


def _tuple(parts: list[str]) -> str:
    return "(" + ", ".join(pretty(p) for p in parts) + ")"


def preview(kind: str, student: str, choices: list | None = None, key=None) -> dict:
    """Live 'reads as' line for the answer box: never reveals the key, only how the input was parsed."""
    student = str(student or "").strip()
    if kind == "multi" and key is not None and _many_points(str(key)):
        kind = "set"
    ok = readable(kind, student, choices, key)
    read, approx = "", None
    try:
        if kind == "numeric":
            sp = special(student)
            if sp:
                read = {"dne": "DNE", "inf": "∞", "-inf": "−∞"}.get(sp, sp)
            else:
                student = re.sub(r"^(-?\d+),(\d+)$", r"\1.\2", student)
                read, approx = pretty(student), _approx(student)
        elif kind == "expression":
            read = pretty(student)
        elif kind in {"multi", "direction"}:
            read = _tuple(split_multi(student))
        elif kind == "line":
            read = _tuple(_line_parts(student))
        elif kind == "equation":
            lhs, rhs = student.split("=")
            read = f"{pretty(lhs)} = {pretty(rhs)}"
        elif kind == "set":
            pts = split_points(student)
            read = ", ".join(_tuple(split_multi(p)) if p.startswith(("(", "<", "⟨")) else pretty(p) for p in pts)
        elif kind == "classify":
            read = classify_label(student) or ""
    except (NotMath, ValueError):
        ok = False
    need = None
    if kind in {"multi", "direction"} and key is not None and not ok:
        want, got = len(split_multi(str(key))), len(split_multi(student)) if student else 0
        if want != got:  # the prompt already says how many values; this only counts them
            need = f"This needs {want} values in the order asked, separated by commas (you gave {got})."
    return {"ok": ok and bool(read), "read": read, "approx": approx, "need": need}
