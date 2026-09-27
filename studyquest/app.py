"""FastAPI backend. Run with ./start.sh (http://localhost:8765)."""
import secrets
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, boss, checker, importer, progress, quest, review, store

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 12 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/heic": ".heic", "image/webp": ".webp"}

app = FastAPI(title="StudyQuest")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.exception_handler(ai.AIUnavailable)
async def _ai_down(_: Request, e: ai.AIUnavailable):
    return JSONResponse({"error": str(e), "kind": "ai_unavailable"}, status_code=503)


@app.exception_handler(KeyError)
async def _missing(_: Request, e: KeyError):
    return JSONResponse({"error": str(e).strip("'\"")}, status_code=404)


@app.exception_handler(FileNotFoundError)
async def _no_plan(_: Request, e: FileNotFoundError):
    return JSONResponse({"error": str(e), "kind": "no_plan"}, status_code=409)


def _state():
    return progress.load(), progress.load_plan()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def api_status():
    has_plan = store.PLAN_FILE.exists()
    return {"ai": ai.status(), "has_plan": has_plan, "settings": progress.load()["settings"]}


@app.get("/api/today")
def api_today():
    p, plan = _state()
    return {**quest.today_quest(p, plan), "last": p.get("last"), "level": progress.level_for(p["xp"]),
            "streak": progress.streak_info(p)}


@app.get("/api/plan")
def api_plan():
    p, plan = _state()
    return {"sessions": [quest.session_view(p, s) for s in plan["sessions"]]}


@app.get("/api/map")
def api_map():
    p, plan = _state()
    return {"zones": quest.world_map(p, plan), "bosses": boss.list_bosses(p, plan)}


@app.get("/api/session/{sid}/verdict")
def api_verdict(sid: str):
    p, plan = _state()
    return quest.verdict(p, plan, sid)


@app.get("/api/stats")
def api_stats():
    p, plan = _state()
    return quest.stats(p, plan)


class CheckStart(BaseModel):
    task_id: str
    mode: str = Field("task", pattern="^(task|review)$")


@app.post("/api/check/start")
def api_check_start(body: CheckStart):
    return checker.start(body.task_id, body.mode)


async def _save_photo(photo: UploadFile | None) -> str | None:
    if photo is None or not photo.filename:
        return None
    ext = IMAGE_TYPES.get(photo.content_type or "")
    if not ext:
        raise HTTPException(400, "Photo must be JPG, PNG, WEBP or HEIC.")
    data = await photo.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(400, "Photo is over 12 MB.")
    store.ensure_dirs()
    path = store.UPLOADS / f"{secrets.token_hex(6)}{ext}"
    path.write_bytes(data)
    return str(path)


@app.post("/api/check/submit")
async def api_check_submit(check_id: str = Form(...), answers: list[str] = Form(default=[]),
                           photo: UploadFile | None = File(default=None)):
    return checker.submit(check_id, answers, await _save_photo(photo))


class Resolve(BaseModel):
    check_id: str
    pick: str = Field(pattern="^(claude|gemini)$")


@app.post("/api/check/resolve")
def api_check_resolve(body: Resolve):
    return checker.resolve(body.check_id, body.pick)


class Help(BaseModel):
    task_id: str
    check_id: str | None = None
    q_index: int = 0


@app.post("/api/help/stuck")
def api_stuck(body: Help):
    return {"step": checker.stuck(body.task_id, body.check_id, body.q_index)}


@app.post("/api/help/explain")
def api_explain(body: Help):
    return checker.explain(body.task_id, body.check_id, body.q_index)


class Override(BaseModel):
    task_id: str
    reason: str = Field(min_length=3, max_length=300)


@app.post("/api/override")
def api_override(body: Override):
    plan = progress.load_plan()
    with progress.transaction() as p:
        return {"events": progress.manual_override(p, plan, body.task_id, body.reason)}


class Sprint(BaseModel):
    minutes: int = Field(ge=1, le=60)
    intention: str = Field("", max_length=300)
    task_id: str | None = None


@app.post("/api/sprint/done")
def api_sprint(body: Sprint):
    with progress.transaction() as p:
        events = progress.record_sprint(p, body.minutes, body.intention, body.task_id)
        return {"events": events, "streak": progress.streak_info(p)}


class Settings(BaseModel):
    sprint_min: int = Field(ge=5, le=25)
    break_min: int = Field(ge=3, le=5)
    sound: bool


@app.post("/api/settings")
def api_settings(body: Settings):
    with progress.transaction() as p:
        p["settings"] = body.model_dump()
        return p["settings"]


@app.get("/api/review")
def api_review():
    p, plan = _state()
    return {"due": review.review_round(p, plan), "total_due": len(review.due_cards(p))}


@app.get("/api/quickwins")
def api_quickwins():
    p, plan = _state()
    return review.quick_wins(p, plan)


class QuickWin(BaseModel):
    index: int = Field(ge=0, le=2)
    answer: str = Field(max_length=2000)


@app.post("/api/quickwins/answer")
def api_quickwin_answer(body: QuickWin):
    return review.grade_quick_win(body.index, body.answer)


class BossStart(BaseModel):
    boss_id: str
    force: bool = False


@app.post("/api/boss/start")
def api_boss_start(body: BossStart):
    p, plan = _state()
    try:
        return boss.start(p, plan, body.boss_id, body.force)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@app.post("/api/boss/submit")
async def api_boss_submit(boss_id: str = Form(...), answers: list[str] = Form(default=[]),
                          photo: UploadFile | None = File(default=None)):
    p, plan = _state()
    return boss.submit(p, plan, boss_id, answers, await _save_photo(photo))


@app.post("/api/import")
async def api_import(file: UploadFile = File(...)):
    suffix = Path(file.filename or "plan.csv").suffix.lower()
    if suffix not in {".csv", ".md", ".markdown", ".txt"}:
        raise HTTPException(400, "Upload a .csv or .md checklist.")
    store.ensure_dirs()
    tmp = store.DATA / f"import_upload{suffix}"
    tmp.write_bytes(await file.read())
    try:
        plan = importer.import_file(tmp)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    p = progress.sync_with_plan(progress.load(), plan)
    progress.save(p)
    return {"sessions": len(plan["sessions"]), "tasks": sum(len(s["tasks"]) for s in plan["sessions"])}


@app.get("/api/export", response_class=PlainTextResponse)
def api_export():
    p, plan = _state()
    return PlainTextResponse(quest.export_csv(p, plan), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=study_checklist_progress.csv"})
