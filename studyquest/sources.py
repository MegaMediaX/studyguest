"""Show course pages inside the app: PDF pages as images, PPTX slides as their picture or text.

Files are looked up by (course, file) in the extracted corpus only, so a request can never read
an arbitrary path from disk.
"""
import hashlib
from pathlib import Path

from . import corpus, store

DPI = 110


def _doc(course: str, file: str) -> dict:
    doc = store.read_json(corpus.corpus_path(course, file))
    if not doc or doc.get("file") != file:
        raise KeyError(f"Unknown source {file}")
    return doc


def page(course: str, file: str, n: int) -> dict:
    doc = _doc(course, file)
    pg = next((x for x in doc["pages"] if x["n"] == n), None)
    if pg is None:
        raise KeyError(f"{file} has no {doc['unit']} {n}")
    has_image = file.lower().endswith(".pdf") or (file.lower().endswith(".pptx") and image_path(course, file, n))
    return {"file": file, "course": course, "n": n, "unit": doc["unit"], "count": len(doc["pages"]),
            "text": pg["text"], "src": pg["src"], "image": bool(has_image)}


def image_path(course: str, file: str, n: int) -> Path | None:
    doc = _doc(course, file)
    src = Path(doc["path"])
    if not 1 <= n <= len(doc["pages"]) or not src.exists():
        return None
    out_dir = store.DATA / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = hashlib.sha1(f"{src}|{n}|{DPI}".encode()).hexdigest()[:16]
    if src.suffix.lower() == ".pdf":
        out = out_dir / f"{stem}.png"
        if not out.exists():
            import pymupdf
            with pymupdf.open(src) as d:
                d[n - 1].get_pixmap(dpi=DPI).save(out)
        return out
    if src.suffix.lower() == ".pptx":
        return corpus._render(src, n)  # largest picture on the slide, if any
    return None
