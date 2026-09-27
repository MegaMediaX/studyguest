"""FastAPI backend. Run with ./start.sh (http://localhost:8765)."""
import secrets
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, boss, bounties, checker, encounter, importer, progress, quest, review, run, sources, store, world

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 12 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/heic": ".heic", "image/webp": ".webp"}

app = FastAPI(title="StudyQuest")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def _no_stale_assets(request: Request, call_next):
    """Revalidate app files on every load so an update never runs against old JS."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(ai.AIUnavailable)
async def _ai_down(_: Request, e: ai.AIUnavailable):
    return JSONResponse({"error": str(e), "kind": "ai_unavailable"}, status_code=503)


@app.exception_handler(KeyError)
async def _missing(_: Request, e: KeyError):
    return JSONResponse({"error": str(e).strip("'\"")}, status_code=404)


@app.exception_handler(ValueError)
async def _bad(_: Request, e: ValueError):
    return JSONResponse({"error": str(e)}, status_code=409)


@app.exception_handler(FileNotFoundError)
async def _no_plan(_: Request, e: FileNotFoundError):
    return JSONResponse({"error": str(e), "kind": "no_plan"}, status_code=409)


def _state():
    return progress.load(), progress.load_plan()


@app.get("/")
def index():
    """index.html with ?v=<mtime> on every asset, so a browser never runs stale JS after an update."""
    import re
    from fastapi.responses import HTMLResponse
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    def bust(m: re.Match) -> str:
        f = STATIC / m.group(2)
        return f'{m.group(1)}/static/{m.group(2)}?v={int(f.stat().st_mtime) if f.exists() else 0}"'
    return HTMLResponse(re.sub(r'((?:src|href)=")/static/([\w.\-]+)"', bust, html))


@app.get("/api/status")
def api_status():
    has_plan = store.PLAN_FILE.exists()
    p = progress.load()
    theme = p["settings"].get("equipped", {}).get("theme")
    return {"ai": ai.status(), "has_plan": has_plan, "settings": p["settings"],
            "theme_color": encounter.LOOT_THEMES.get(theme) if theme else None}


@app.get("/api/today")
def api_today():
    p, plan = _state()
    return {**quest.today_quest(p, plan), "last": p.get("last"), "level": progress.level_for(p["xp"]),
            "streak": progress.streak_info(p), "title": p["settings"].get("equipped", {}).get("title")}


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
    sprint_min: int = Field(ge=5, le=60)
    break_min: int = Field(ge=3, le=10)
    sound: bool
    focus_fullscreen: bool = True
    fx: str = Field("full", pattern="^(full|calm|off)$")


@app.post("/api/settings")
def api_settings(body: Settings):
    with progress.transaction() as p:
        p["settings"] = {**p["settings"], **body.model_dump()}
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


# ---------- battles ----------

class BattleStart(BaseModel):
    task_id: str
    mode: str = Field("task", pattern="^(task|review)$")
    run_id: str | None = Field(None, max_length=12)


@app.post("/api/battle/start")
def api_battle_start(body: BattleStart):
    return encounter.start(body.task_id, body.mode, body.run_id)


class BattleAnswer(BaseModel):
    task_id: str
    idx: int = Field(ge=0, le=20)
    answer: str = Field(max_length=500)


@app.post("/api/battle/answer")
def api_battle_answer(body: BattleAnswer):
    return encounter.answer(body.task_id, body.idx, body.answer)


@app.post("/api/battle/dispute")
def api_battle_dispute(body: BattleAnswer):
    return encounter.dispute(body.task_id, body.idx, body.answer)


class BattleRef(BaseModel):
    task_id: str
    idx: int = Field(0, ge=0, le=20)


@app.post("/api/battle/hint")
def api_battle_hint(body: BattleRef):
    return encounter.hint(body.task_id, body.idx)


@app.post("/api/battle/focus")
def api_battle_focus(body: BattleRef):
    encounter.focus_break(body.task_id)
    return {"ok": True}


class Prefetch(BaseModel):
    task_ids: list[str] = Field(max_length=5)


@app.post("/api/battle/prefetch")
def api_battle_prefetch(body: Prefetch):
    encounter.prefetch(body.task_ids)
    return {"ok": True}


@app.get("/api/source")
def api_source(course: str, file: str, n: int):
    return sources.page(course, file, n)


@app.get("/api/source/img")
def api_source_img(course: str, file: str, n: int):
    path = sources.image_path(course, file, n)
    if not path:
        raise HTTPException(404, "No image for this page")
    return FileResponse(path, headers={"Cache-Control": "max-age=86400"})


@app.get("/api/inventory")
def api_inventory():
    return encounter.inventory(progress.load())


class Equip(BaseModel):
    title: str | None = Field(None, max_length=60)
    theme: str | None = Field(None, max_length=20)


@app.post("/api/equip")
def api_equip(body: Equip):
    with progress.transaction() as p:
        inv = p.get("loot", {"titles": [], "themes": ["teal"]})
        eq = p["settings"].setdefault("equipped", {})
        if body.title is not None:
            if body.title and body.title not in inv["titles"]:
                raise HTTPException(400, "You haven't found that title yet.")
            eq["title"] = body.title
        if body.theme is not None:
            if body.theme not in inv["themes"]:
                raise HTTPException(400, "You haven't found that theme yet.")
            eq["theme"] = body.theme
        return encounter.inventory(p)


class Token(BaseModel):
    task_id: str
    kind: str = Field(pattern="^(hint_token|retry_token)$")


@app.post("/api/battle/token")
def api_battle_token(body: Token):
    return encounter.use_token(body.task_id, body.kind)


# ---------- runs, bounties, chests ----------

@app.get("/api/run")
def api_run():
    r = progress.load().get("run")
    return {"run": run.public(r) if r and r["state"] == "active" else None}


class RunStart(BaseModel):
    zone: str | None = Field(None, max_length=40)


@app.post("/api/run/start")
def api_run_start(body: RunStart | None = None):
    plan = progress.load_plan()
    with progress.transaction() as p:
        return {"run": run.public(run.start(p, plan, body.zone if body else None))}


@app.get("/api/world")
def api_world():
    p, plan = _state()
    return {"regions": world.build(p, plan), "bosses": boss.list_bosses(p, plan)}


class PerkPick(BaseModel):
    perk_id: str = Field(max_length=30)


@app.post("/api/run/perk")
def api_run_perk(body: PerkPick):
    with progress.transaction() as p:
        return {"run": run.choose_perk(p, body.perk_id)}


@app.post("/api/run/end")
def api_run_end():
    with progress.transaction() as p:
        if not p.get("run") or p["run"]["state"] != "active":
            raise KeyError("No active run.")
        return {"run": run.finish(p, abandoned=True)}


@app.get("/api/bounties")
def api_bounties():
    plan = progress.load_plan()
    with progress.transaction() as p:
        b = bounties.today_bounties(p, plan)
        return {**b, "economy": p.get("economy", {"shards": 0, "keys": 0, "consumables": {}})}


class Reroll(BaseModel):
    bounty_id: str = Field(max_length=5)


@app.post("/api/bounties/reroll")
def api_bounty_reroll(body: Reroll):
    plan = progress.load_plan()
    with progress.transaction() as p:
        return bounties.reroll(p, plan, body.bounty_id)


@app.get("/api/chest")
def api_chest():
    return {**run.odds(), "economy": progress.load().get("economy", {"shards": 0, "keys": 0, "consumables": {}})}


@app.post("/api/chest/open")
def api_chest_open():
    with progress.transaction() as p:
        return run.open_chest(p)
