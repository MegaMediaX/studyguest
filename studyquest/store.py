"""Paths, config and atomic JSON storage. Every data file stays human-readable."""
import json
import os
import tempfile
import threading
from datetime import date, datetime
from pathlib import Path

ROOT = Path(os.environ.get("STUDYQUEST_ROOT", Path(__file__).resolve().parent.parent))
DATA = Path(os.environ.get("STUDYQUEST_DATA", ROOT / "data"))
CORPUS = DATA / "corpus"
CACHE = DATA / "cache"
UPLOADS = DATA / "uploads"
PLAN_FILE = DATA / "plan.json"
PROGRESS_FILE = DATA / "progress.json"

_lock = threading.RLock()


def ensure_dirs() -> None:
    for d in (DATA, CORPUS, CACHE, UPLOADS):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    """Write via temp file + rename so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def today() -> date:
    """Overridable for tests and demos: STUDYQUEST_TODAY=2026-09-28."""
    forced = os.environ.get("STUDYQUEST_TODAY")
    return date.fromisoformat(forced) if forced else date.today()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
