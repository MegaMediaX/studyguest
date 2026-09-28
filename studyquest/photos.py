"""Photos of handwritten working: normalise uploads so Claude can read them quickly.

iPhone photos arrive as HEIC and are often 4000+ px; `sips` (built into macOS) converts to JPEG and
shrinks to MAX_SIDE. On other systems, or if sips fails, the original file is kept.
"""
import shutil
import subprocess
from pathlib import Path

MAX_SIDE = 1600


def normalize(path: str | Path) -> Path:
    src = Path(path)
    sips = shutil.which("sips")
    if not sips:
        return src
    out = src.with_suffix(".jpg") if src.suffix.lower() != ".jpg" else src
    cmd = [sips, "-s", "format", "jpeg", "-Z", str(MAX_SIDE), str(src), "--out", str(out)]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
    except (subprocess.SubprocessError, OSError):
        return src
    if out != src and out.exists():
        src.unlink(missing_ok=True)
        return out
    return src
