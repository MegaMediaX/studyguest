"""One wrapper for both CLIs. No API keys: Claude via `claude -p`, Gemini via `agy -p`.

- timeouts + retries with backoff
- disk cache in data/cache/ keyed by sha1(provider|prompt|image bytes), so nothing is generated twice
- replies are parsed as JSON (fenced or bare)
- runs in a neutral temp cwd with hooks disabled, so the app never triggers your SessionEnd work-log hook
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import store


EXTRA_BIN_DIRS = [Path.home() / ".local/bin", Path("/opt/homebrew/bin"), Path("/usr/local/bin"),
                  Path.home() / ".npm-global/bin", Path.home() / ".claude/local"]


def find_bin(name: str) -> str | None:
    """PATH first, then the usual install dirs: a terminal started without the user's
    shell profile (e.g. an IDE or app pane) often lacks ~/.local/bin."""
    found = shutil.which(name)
    if found:
        return found
    for d in EXTRA_BIN_DIRS:
        p = d / name
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


class AIUnavailable(RuntimeError):
    """Raised with a message that is safe to show in the UI."""


def _cfg() -> dict:
    return store.load_config().get("ai", {})


def _clean_env() -> dict:
    # Nested-session markers from a parent Claude Code would change CLI behaviour; drop them.
    return {k: v for k, v in os.environ.items() if not (k.startswith("CLAUDE_CODE_") or k == "CLAUDECODE")}


def claude_cmd(images: list[Path]) -> list[str]:
    cmd = [find_bin("claude") or "claude", "-p", "--output-format", "json", "--no-session-persistence", "--strict-mcp-config",
           "--settings", json.dumps({"disableAllHooks": True})]
    model = _cfg().get("claude_model")
    if model:
        cmd += ["--model", model]
    if images:
        cmd += ["--tools", "Read", "--allowedTools", "Read"]
        for d in {str(p.parent) for p in images}:
            cmd += ["--add-dir", d]
    else:
        cmd += ["--tools", ""]
    return cmd


def gemini_cmd(prompt: str, images: list[Path], effort: str = "medium") -> list[str]:
    # agy's default (high) effort can spend its whole budget thinking and return an empty reply
    timeout = int(_cfg().get("gemini_timeout_s", 150))
    cmd = [find_bin("agy") or "agy", "-p", prompt, "--output-format", "json", "--print-timeout", f"{timeout}s", "--effort", effort]
    for d in {str(p.parent) for p in images}:
        cmd += ["--add-dir", d]
    return cmd


def _run(cmd: list[str], stdin: str | None, timeout: int) -> str:
    with tempfile.TemporaryDirectory() as cwd:
        proc = subprocess.run(cmd, input=stdin if stdin is not None else "", capture_output=True, text=True,
                              timeout=timeout, cwd=cwd, env=_clean_env())
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip()[:300] or f"exit {proc.returncode}")
    return proc.stdout


def _unwrap(provider: str, raw: str) -> str:
    """Turn the CLI's JSON envelope into the model's text reply."""
    env = json.loads(raw)
    if provider == "claude":
        text = env.get("result", "")
        if env.get("is_error"):
            if "login" in text.lower() or "logged in" in text.lower():
                raise AIUnavailable("Claude CLI is not logged in. Run `claude` in a terminal and type /login once.")
            raise RuntimeError(text[:300])
        return text
    if env.get("status") not in (None, "SUCCESS"):
        raise RuntimeError(f"agy status {env.get('status')}: {str(env)[:200]}")
    return env.get("response", "")


def parse_json_reply(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    if not candidate:
        raise ValueError(f"No JSON in reply: {text[:200]}")
    return json.loads(candidate)


def _cache_key(provider: str, prompt: str, images: list[Path]) -> str:
    h = hashlib.sha1(f"{provider}|{prompt}".encode())
    for p in images:
        h.update(Path(p).read_bytes())
    return h.hexdigest()


# Tests replace this with a fake: runner(provider, prompt, images) -> reply text
runner = None


def ask(provider: str, prompt: str, *, images: list[Path] | None = None, want_json: bool = True,
        cache: bool = True, effort: str | None = None) -> dict | str:
    images = [Path(p) for p in (images or [])]
    key = _cache_key(provider, prompt, images)
    cache_file = store.CACHE / f"{key}.json"
    if cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["reply"]

    if runner is None:
        check_available(provider)
    cfg = _cfg()
    retries = int(cfg.get("retries", 2))
    timeout = int(cfg.get(f"{provider}_timeout_s", 180))
    last_err = None
    for attempt in range(retries + 1):
        try:
            if runner is not None:
                text = runner(provider, prompt, images)
            elif provider == "claude":
                text = _unwrap("claude", _run(claude_cmd(images), prompt, timeout))
            else:
                level = effort or (_cfg().get("gemini_effort", "medium") if attempt == 0 else "low")
                text = _unwrap("gemini", _run(gemini_cmd(prompt, images, level), None, timeout + 30))
            reply = parse_json_reply(text) if want_json else text.strip()
            if cache:
                store.write_json(cache_file, {"provider": provider, "at": store.now_iso(), "reply": reply})
            return reply
        except AIUnavailable:
            raise
        except (subprocess.TimeoutExpired, RuntimeError, ValueError, json.JSONDecodeError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1) if runner is None else 0)
    raise AIUnavailable(f"{provider} failed after {retries + 1} tries: {str(last_err)[:200]}")


_status_cache: dict = {}


def status(refresh: bool = False) -> dict:
    """{'claude': {'ok': bool, 'why': str}, 'gemini': {...}}; cached for the process lifetime."""
    if _status_cache and not refresh:
        return _status_cache
    out = {}
    claude = find_bin("claude")
    if not claude:
        out["claude"] = {"ok": False, "why": "`claude` not found (looked in PATH and ~/.local/bin, /opt/homebrew/bin)"}
    else:
        try:
            raw = subprocess.run([claude, "auth", "status"], capture_output=True, text=True, timeout=20,
                                 env=_clean_env()).stdout
            ok = bool(json.loads(raw).get("loggedIn"))
            out["claude"] = {"ok": ok, "why": "" if ok else "Claude CLI not logged in: run `claude`, then /login"}
        except Exception as e:  # noqa: BLE001 - any failure here just means "unknown"
            out["claude"] = {"ok": False, "why": f"could not check claude auth: {e}"}
    out["gemini"] = ({"ok": True, "why": ""} if find_bin("agy")
                     else {"ok": False, "why": "`agy` not found: Gemini second opinions are disabled"})
    _status_cache.clear()
    _status_cache.update(out)
    return out


def check_available(provider: str) -> None:
    st = status()[provider]
    if not st["ok"]:
        raise AIUnavailable(st["why"])


def gemini_enabled() -> bool:
    return runner is not None or status()["gemini"]["ok"]


def short(text: str, max_sentences: int = 3) -> str:
    """Hard cap for hints: at most N sentences."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:max_sentences])
