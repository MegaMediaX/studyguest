// StudyQuest frontend: one thing on screen at a time. Vanilla JS, no build step.
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const app = $("#app");
const S = { view: "quest", today: null, taskIndex: null, phase: "card", check: null, help: null, settings: null };
const LS = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode: fine */ } },
};

// ---------- helpers ----------
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
async function api(path, opts = {}) {
  const init = { ...opts };
  if (opts.json) { init.method = init.method || "POST"; init.headers = { "Content-Type": "application/json" }; init.body = JSON.stringify(opts.json); }
  const res = await fetch(path, init);
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw Object.assign(new Error(data.error || data.detail || res.statusText), { data, status: res.status });
  return data;
}
// Math as a student reads it: code-style keys (x**2, exp(x), log(t), 2*x*y, f_xx) → x², eˣ-style, ln, 2xy, subscripts.
// Always escapes first, so it's safe to put the result into innerHTML.
function mathHtml(text) {
  let s = esc(text);
  s = s.replace(/\bexp\(/g, "e^(").replace(/\blog\(/g, "ln(").replace(/\bsqrt\(/g, "√(").replace(/\bpi\b/g, "π")
    .replace(/\btheta\b/g, "θ").replace(/\bphi\b/g, "φ").replace(/\brho\b/g, "ρ").replace(/\blam\b/g, "λ");
  s = s.replace(/\*\*/g, "^");
  s = s.replace(/\^\{([^{}]{1,12})\}/g, "<sup>$1</sup>")                 // e^{xy}
    .replace(/\^\(([^()]{1,14})\)/g, "<sup>$1</sup>")                     // e^(x*y)
    .replace(/\^(-?[0-9a-zA-Zθφ]{1,3})/g, "<sup>$1</sup>");                // x^2, e^x
  s = s.replace(/(\d)\*(?=[a-zA-Zα-ωθφρλπ√(])/g, "$1")                      // 2*x -> 2x
    .replace(/(?<![a-zA-Z])([a-zA-Z])\*(?=[a-zA-Z](?![a-zA-Z(]))/g, "$1")       // x*y -> xy (single letters)
    .replace(/([a-zA-Z)])\*(?=[a-zA-Z(√])/g, "$1·")                           // cos(x)*y -> cos(x)·y
    .replace(/\*/g, "·");
  s = s.replace(/\b([a-zA-Z∇])_\{?([a-zA-Z0-9]{1,3})\}?/g, "$1<sub>$2</sub>")  // f_xx, W_xy
    .replace(/\)_([a-zA-Z0-9]{1,3})\b/g, ")<sub>$1</sub>");                       // (f_x)_x
  s = s.replace(/\b(?:choice |option )?index ([0-5])\b/gi, (_, i) => `choice ${"ABCDEF"[+i]}`);
  return s;
}
function fmt(sec) { sec = Math.max(0, Math.round(sec)); return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`; }
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), 2600);
}
function beep(kind = "win") {
  if (!S.settings?.sound) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const notes = kind === "win" ? [660, 880, 1320] : kind === "level" ? [523, 659, 784, 1047] : [440, 330];
    notes.forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = f; o.type = "sine"; o.connect(g); g.connect(ctx.destination);
      const t0 = ctx.currentTime + i * 0.11;
      g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(0.18, t0 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.18); o.start(t0); o.stop(t0 + 0.2);
    });
  } catch { /* no audio: fine */ }
}
function showError(e, where = app) {
  const msg = e?.data?.kind === "ai_unavailable" ? `AI not available: ${e.message}` : e.message || String(e);
  const box = document.createElement("div"); box.className = "notice"; box.textContent = msg;
  where.prepend(box);
}
function loading(text) {
  app.innerHTML = `<section class="card center"><p class="muted">${esc(text)}</p><p class="muted small" id="load-timer"></p></section>`;
  const t0 = Date.now();
  clearInterval(loading._t);
  loading._t = setInterval(() => {
    const el = $("#load-timer"); if (!el) return clearInterval(loading._t);
    const s = Math.round((Date.now() - t0) / 1000);
    el.textContent = s < 5 ? "" : s < 90 ? `${s} s · a brand-new battle takes 30–90 s; later floors are ready instantly`
      : `${s} s · still building (Claude + a second check of every answer key)`;
  }, 1000);
}

// ---------- HUD & time bar ----------
function renderHud(t) {
  if (!t) return;
  const lv = t.level;
  $("#hud-level").textContent = `Lv ${lv.level}`;
  $("#hud-xpfill").style.width = `${Math.round((100 * lv.into) / lv.span)}%`;
  $("#hud-level").title = `${lv.xp} XP (${lv.span - lv.into} to next level)`;
  $("#hud-streak").textContent = `🔥 ${t.streak.current}${t.streak.freeze_available ? "" : " ❄️"}`;
  $("#hud-streak").title = `Streak ${t.streak.current} (best ${t.streak.best}). ${t.streak.freeze_available ? "1 free freeze left this week." : "Freeze used this week."}`;
  const b = $("#review-badge"); b.textContent = t.review_due; b.classList.toggle("hidden", !t.review_due);
  $("#hud-title").textContent = t.title ? `· ${t.title}` : "";
}
function sessionWindow() {
  const s = S.today?.session; if (!s || !s.time || S.today.label !== "today") return null;
  const [a, b] = s.time.replace("—", "–").split("–").map((x) => x.trim());
  if (!a || !b) return null;
  return { start: new Date(`${s.date}T${a}`), end: new Date(`${s.date}T${b}`) };
}
function tick() {
  const br = LS.get("break", null), now = Date.now();
  let frac = 0, label = "";
  if (br) { frac = 1 - (br.end - now) / (br.minutes * 60000); label = `☕ ${fmt((br.end - now) / 1000)}`; if (now >= br.end) endBreak(); }
  else { const w = sessionWindow(); if (w && now >= w.start && now < w.end) { frac = (now - w.start) / (w.end - w.start); label = `${fmt((w.end - now) / 1000)} left in session`; } }
  $("#timebar-fill").style.width = `${Math.min(100, Math.max(0, frac * 100))}%`;
  $("#hud-clock").textContent = label;
  const big = $("#big-timer"); if (big) big.textContent = br ? fmt((br.end - now) / 1000) : "";
  const hint = $("#hint-wait");
  if (hint) { const left = (S.check.retryAt - now) / 1000; hint.textContent = left > 0 ? `Retry unlocks in ${fmt(left)}` : ""; $("#submit-check").disabled = left > 0; }
}
setInterval(tick, 1000);

// ---------- navigation ----------
document.querySelectorAll("nav button[data-view]").forEach((b) => b.addEventListener("click", () => go(b.dataset.view)));
$("#sound-toggle").addEventListener("click", async () => {
  const before = S.settings.sound;
  S.settings.sound = !before;
  $("#sound-toggle").textContent = S.settings.sound ? "🔊" : "🔈";
  try { await api("/api/settings", { json: S.settings }); }
  catch (e) { S.settings.sound = before; $("#sound-toggle").textContent = before ? "🔊" : "🔈"; toast("Couldn't save the sound setting"); }
});
function go(view) {
  S.view = view;
  document.querySelectorAll("nav button[data-view]").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  ({ quest: renderQuest, review: renderReview, map: renderWorld, stats: renderStats })[view]();
}

// ---------- quest ----------
async function loadToday() { S.today = await api("/api/today"); renderHud(S.today); return S.today; }
function currentTask() {
  const tasks = S.today?.session?.tasks || [];
  if (S.taskIndex == null || S.taskIndex < 0 || S.taskIndex >= tasks.length || tasks[S.taskIndex].status === "done") {
    const i = tasks.findIndex((t) => t.status === "todo");
    S.taskIndex = i >= 0 ? i : tasks.findIndex((t) => t.status === "review");
  }
  return S.taskIndex >= 0 ? tasks[S.taskIndex] : null;
}
function dots(tasks, cur) {
  return `<div class="dots" aria-label="Session progress">${tasks.map((t, i) =>
    `<span class="dot ${t.status === "done" || t.status === "override" ? "done" : t.status === "review" ? "review" : ""} ${i === cur ? "current" : ""}" title="${esc(t.text)}"></span>`).join("")}</div>`;
}

async function renderQuest() {
  if (LS.get("break", null)) return renderBreak();
  if (S.phase === "check" && S.check) return renderCheck();
  loading("Loading today's floor…");
  let t;
  try { t = await loadToday(); } catch (e) { if (e.data?.kind === "no_plan") return renderEmpty(); app.innerHTML = ""; return showError(e); }
  const s = t.session;
  if (!s) { app.innerHTML = `<section class="card center"><h1>No floors left in the plan 🎉</h1></section>`; return; }
  const task = currentTask();
  if (!task) return renderVerdict(s.id);
  const cleared = s.tasks.filter((x) => x.status === "done" || x.status === "override").length;
  const nodes = s.tasks.map((x, i) => {
    const icon = x.status === "done" || x.status === "override" ? "✅" : x.status === "review" ? "🔁" : x.kind === "action" ? "📌" : i === S.taskIndex ? "⚔️" : "❔";
    return `<button class="node ${i === S.taskIndex ? "current" : ""} ${x.status}" data-i="${i}" title="${esc(x.text)}">
      <span>${icon}</span><small>${x.stars ? "★".repeat(x.stars) : ""}</small></button>`;
  }).join('<span class="edge"></span>');
  const where = t.last ? `<button class="btn link" id="where">Where was I?</button>` : "";
  const qw = !LS.get(`qw-${t.date}`, false) && t.label === "today" ? `<button class="btn link" id="qw">⚡ 3 quick wins</button>` : "";
  const fighting = task.battle === "fighting";
  const [bounty, runState] = await Promise.all([bountiesCard(), api("/api/run").catch(() => ({ run: null }))]);
  G.run = runState.run;
  const runBtn = G.run ? `<button class="btn primary big" id="run">${G.run.offer?.length ? "🎁 Choose your perk" : `▶ Continue run · floor ${G.run.floor + 1}/${G.run.floors}`}</button>`
    : `<button class="btn primary big" id="run">▶ Start a run <span class="small">(up to 4 floors, perks, a chest)</span></button>`;
  const ef = t.exam_focus;
  const focus = ef && (s.subject && !/calc/i.test(s.subject) || ef.behind) ? `<section class="card exam-focus" role="region" aria-label="Exam focus">
      <h2>📐 ${esc(ef.exam)} in ${esc(ef.days)} day${ef.days === 1 ? "" : "s"}</h2>
      <p>${ef.behind ? `${esc(ef.behind)} tasks from earlier sessions are waiting. ` : ""}Next up: <b>${esc(ef.zone_name)}</b>.</p>
      <div class="row"><button class="btn primary big" id="focus-go">▶ Start a ${esc(ef.course)} run</button></div></section>` : "";
  const mock = t.mock_today ? `<section class="card mock-day" role="region" aria-label="Mock exam reminder"><h2>📄 Mock exam day ${esc(t.mock_today.number)}/2</h2>
      <p>Take the ${esc(t.mock_today.name)}: ${esc(t.mock_today.minutes)} minutes, closed book, full working on paper. It's the best predictor of Exam I.</p>
      <div class="row"><button class="btn primary big" id="mock-go">Start the timed mock</button></div></section>` : "";
  app.innerHTML = `
    ${mock}${focus}${riftBanner(t.rift)}
    <section class="card" id="task-card">
      <p class="eyebrow">${t.label === "today" ? "Today's session" : "Next session"} · ${esc(s.date_label)} · ${esc(s.time)} · ${esc(s.subject)}</p>
      <h1 class="floor-title">${esc(s.session)}</h1>
      <div class="floor-progress"><div style="width:${Math.round((100 * cleared) / s.total)}%"></div></div>
      <div class="path">${nodes}</div>
      <p class="eyebrow">Selected task · ${S.taskIndex + 1} of ${s.total} in this session ${task.status === "review" ? "· 🔁 rematch" : ""}</p>
      <div class="task-text">${esc(task.text)}</div>
      <div class="row">${runBtn}</div>
      <details class="more"><summary>Other options</summary>
        <div class="row"><button class="btn" id="start">${task.kind === "action" ? "📌 Mark this task with proof" : fighting ? "⚔️ Resume this battle" : "⚔️ Fight only this task"}</button>
          ${G.run ? `<button class="btn" id="abandon">End run</button>` : ""}
          <button class="btn" id="skip">Select another task ›</button>${where.replace("btn link", "btn")}${qw.replace("btn link", "btn")}</div>
      </details>
      <div id="help"></div>
    </section>${bounty}`;
  bindBounties();
  if ($("#mock-go")) $("#mock-go").onclick = () => renderBoss(t.mock_today.boss_id);
  if ($("#focus-go")) $("#focus-go").onclick = async () => {
    enterFocus();
    try {
      if (G.run && G.run.session !== ef.zone_name) { await api("/api/run/end", { method: "POST" }); G.run = null; }
      const r = await api("/api/run/start", { json: { zone: ef.zone } });
      G.run = r.run; G.saidThisRun = 0; FX.play("perk"); nextFloor();
    } catch (e) { toast(e.message); }
  };
  if (ef) api(`/api/run/preview?zone=${encodeURIComponent(ef.zone)}`).then((r) => api("/api/battle/prefetch", { json: { task_ids: r.queue.slice(0, 4) } })).catch(() => {});
  $("#run").onclick = () => (G.run ? (G.run.offer?.length ? renderPerkDraft(G.run) : nextFloor()) : startRun());
  if ($("#abandon")) $("#abandon").onclick = async () => { const r = await api("/api/run/end", { method: "POST" }); renderRunSummary(r.run); };
  if (!LS.get(`greeted-${t.date}`, false)) { LS.set(`greeted-${t.date}`, true); vex("greet", $("#task-card"), true); }
  $("#start").onclick = () => (task.kind === "action" ? startCheck(task) : startBattle(task));
  $("#skip").onclick = () => { S.taskIndex = nextIndex(s.tasks, S.taskIndex); renderQuest(); };
  document.querySelectorAll(".node").forEach((n) => (n.onclick = () => { S.taskIndex = +n.dataset.i; renderQuest(); }));
  if (t.last) $("#where").onclick = () => whereWasI(t.last);
  if (qw) $("#qw").onclick = () => renderQuickWins();
  // warm the run's floors (including floor 1) so Start opens instantly
  api("/api/run/preview").then((r) => api("/api/battle/prefetch", { json: { task_ids: r.queue.slice(0, 4) } })).catch(() => {});
}
function nextIndex(tasks, i) {
  for (let k = 1; k <= tasks.length; k++) { const j = (i + k) % tasks.length; if (tasks[j].status !== "done" && tasks[j].status !== "override") return j; }
  return i;
}
function whereWasI(last) {
  const tasks = S.today.session.tasks; const i = tasks.findIndex((x) => x.id === last.task_id);
  if (i >= 0) S.taskIndex = i;
  renderQuest().then(() => { $("#help").innerHTML = `<div class="helpbox">↩ ${esc(last.recap)}</div>`; });
}
function renderEmpty() {
  app.innerHTML = ""; app.append($("#tpl-empty").content.cloneNode(true));
  $("#import-file").onchange = async (ev) => {
    const fd = new FormData(); fd.append("file", ev.target.files[0]);
    try { const r = await api("/api/import", { method: "POST", body: fd }); toast(`Imported ${r.tasks} tasks`); go("quest"); } catch (e) { showError(e); }
  };
}

// ---------- campfire break ----------
function renderBreak() {
  app.innerHTML = `
    <section class="card break">
      <div class="monster">🔥</div>
      <p class="eyebrow">Campfire</p>
      <h1>Stand up. Water. Look far away.</h1>
      <div class="timer-big" id="big-timer"></div>
      <div class="row" style="justify-content:center"><button class="btn primary" id="skipbreak">Back to the dungeon</button></div>
    </section>`;
  $("#skipbreak").onclick = () => endBreak(true);
  tick();
}
function endBreak(manual = false) {
  if (!LS.get("break", null)) return;
  LS.set("break", null); LS.set("lastBreak", Date.now());
  if (!manual) beep("win");
  if (S.view === "quest" && S.phase !== "battle") renderQuest();
}

// ---------- help ----------
async function askHelp(kind, taskId) {
  const box = $("#help"); if (!box) return;
  box.innerHTML = `<div class="helpbox muted">${kind === "stuck" ? "Finding the smallest next step…" : "Asking for another angle…"}</div>`;
  try {
    const body = { task_id: taskId, check_id: S.check?.check_id || null, q_index: 0 };
    const r = await api(`/api/help/${kind}`, { json: body });
    box.innerHTML = `<div class="helpbox">${kind === "stuck" ? "👣 " + esc(r.step) : `💡 <span class="muted">(${esc(r.by)})</span> ${esc(r.text)}`}</div>`;
  } catch (e) { box.innerHTML = ""; showError(e, box); }
}

// ---------- the done-check ----------
async function startCheck(task, mode = "task") {
  S.phase = "check";
  loading("Claude is writing your check from the course files… (can take ~30 s)");
  try {
    const r = await api("/api/check/start", { json: { task_id: task.id, mode } });
    if (r.status === "already_done") { toast("Already done ✅"); S.phase = "card"; return renderQuest(); }
    S.check = { ...r, mode, retryAt: Date.now() + (r.retry_in || 0) * 1000 };
    if (r.disagree) return renderDisagree({ check_id: r.check_id, ...r.disagree });
    renderCheck(r.hint ? `<div class="helpbox">💡 <b>Hint</b> (attempt ${r.attempt}): ${esc(r.hint)}</div>` : "");
  } catch (e) { S.phase = "card"; app.innerHTML = `<section class="card"></section>`; showError(e, $(".card")); addBack($(".card")); }
}
function addBack(el) { const b = document.createElement("button"); b.className = "btn"; b.textContent = "Back"; b.onclick = () => go(S.view); el.append(b); }
function renderCheck(extra = "") {
  const c = S.check;
  const photo = ["exercise", "produce"].includes(c.task.kind);
  app.innerHTML = `
    <section class="card">
      <p class="eyebrow">Check · ${esc(c.task.kind)} · attempt ${c.attempt}${c.mode === "review" ? " · review" : ""}</p>
      <div class="task-text" style="font-size:1.2rem">${esc(c.task.text)}</div>
      ${c.notice ? `<div class="notice">${esc(c.notice)}</div>` : ""}
      ${extra}
      <form id="check-form">
        ${c.questions.map((q, i) => `
          <label class="q" for="a${i}">${i + 1}. ${esc(q.q)}${q.source ? `<span class="src">📄 ${esc(q.source)}</span>` : ""}</label>
          <textarea id="a${i}" name="answers" placeholder="Your answer"></textarea>`).join("")}
        ${photo ? `<label class="q">Or upload a photo of your working <input type="file" name="photo" accept="image/*" capture="environment"></label>` : ""}
        <div class="row">
          <button class="btn primary big" id="submit-check" type="submit">Check</button>
          <span id="hint-wait" class="muted"></span>
        </div>
      </form>
      <div class="row spread">
        <span><button class="btn" id="stuck">I'm stuck</button> <button class="btn" id="explain">Explain differently</button></span>
        <span><button class="btn link" id="override">Manual override</button><button class="btn link" id="leave">Leave</button></span>
      </div>
      <div id="help"></div>
    </section>`;
  $("#check-form").onsubmit = submitCheck;
  $("#stuck").onclick = () => askHelp("stuck", c.task.id);
  $("#explain").onclick = () => askHelp("explain", c.task.id);
  $("#leave").onclick = () => { S.phase = "card"; S.check = null; go(S.view); };
  $("#override").onclick = () => doOverride(c.task);
  tick();
}
async function submitCheck(ev) {
  ev.preventDefault();
  const fd = new FormData(ev.target); fd.append("check_id", S.check.check_id);
  $("#submit-check").disabled = true; $("#submit-check").textContent = "Grading…";
  try { handleResult(await api("/api/check/submit", { method: "POST", body: fd })); }
  catch (e) { $("#submit-check").disabled = false; $("#submit-check").textContent = "Check"; showError(e, $(".card")); }
}
function celebrate(events, quiet = false) {
  let xp = 0; const extra = [];
  for (const e of events || []) {
    if (e.type === "xp") xp += e.amount;
    if (e.type === "level_up") { FX.play("kill"); setTimeout(() => toast(`⭐ Level ${e.level}!`), 1400); }
    if (e.type === "shard") { FX.play("shard"); extra.push(`+${e.amount} ◆`); }
    if (e.type === "key") extra.push("🔑 Key!");
    if (e.type === "bounty") extra.push(`📜 Bounty done: ${e.text}`);
  }
  if (xp || extra.length) { if (!quiet) beep("win"); toast([xp ? `+${xp} XP` : "", ...extra].filter(Boolean).join("  ·  ")); }
  loadToday().catch(() => {}); // refresh the HUD (XP bar, streak, review badge)
}
function handleResult(r) {
  const c = S.check;
  if (r.status === "wait") {
    const b = $("#submit-check"); if (b) { b.disabled = false; b.textContent = "Check"; }
    return toast(`Hint time: ${r.seconds}s left`);
  }
  if (r.status === "disagree") return renderDisagree(r);
  if (r.status === "passed") {
    celebrate(r.events);
    const session = r.events.find((e) => e.type === "session_complete");
    S.phase = "card"; S.check = null;
    if (c.mode === "review") return renderReview();
    app.innerHTML = `<section class="card center burst"><h1 class="verdict-ok">✅ Passed</h1><p>${esc(r.reason)}</p>
      <p class="muted">Score ${Math.round(r.score * 100)}% · graded by ${esc(r.graded_by)}</p>
      <div class="row" style="justify-content:center"><button class="btn primary big" id="next">${session ? "See session result" : "Next task"}</button></div></section>`;
    $("#next").onclick = () => renderQuest();
    return;
  }
  if (r.status === "retry") {
    S.check.attempt = 2; S.check.retryAt = Date.now() + r.hint_seconds * 1000;
    beep("lose");
    return renderCheck(`<div class="helpbox">💡 <b>Hint</b> (${Math.round(r.score * 100)}%): ${esc(r.hint)}</div>
      ${r.feedback.filter(Boolean).map((f) => `<p class="muted">• ${esc(f)}</p>`).join("")}`);
  }
  // review_later
  S.phase = "card"; S.check = null;
  app.innerHTML = `<section class="card"><h1 class="verdict-warn">🔁 Review later</h1>
    <p>No XP lost. This comes back tomorrow, then in 2 and 4 days, before your exam.</p>
    <h2>Reference answers</h2><ol>${(r.answers || []).map((a) => `<li>${esc(a)}</li>`).join("")}</ol>
    <div class="row"><button class="btn primary" id="next">Next task</button></div></section>`;
  $("#next").onclick = () => (c.mode === "review" ? renderReview() : renderQuest());
}
function renderDisagree(r) {
  app.innerHTML = `
    <section class="card">
      <h1>The graders disagree</h1>
      <p class="muted">Read both and pick the one you think is fair.</p>
      <div class="grid2">
        <div class="card pick" id="pick-claude"><h2>Claude: ${Math.round(r.claude.score * 100)}%</h2><p>${esc(r.claude.reason)}</p></div>
        <div class="card pick" id="pick-gemini"><h2>Gemini: ${Math.round(r.gemini.score * 100)}%</h2><p>${esc(r.gemini.reason)}</p></div>
      </div>
    </section>`;
  const pick = async (who) => { try { handleResult(await api("/api/check/resolve", { json: { check_id: r.check_id, pick: who } })); } catch (e) { showError(e); } };
  $("#pick-claude").onclick = () => pick("claude");
  $("#pick-gemini").onclick = () => pick("gemini");
}
async function doOverride(task) {
  const reason = prompt("Manual override: mark done without a check.\nIt's logged and gives 0 XP. Reason?");
  if (!reason || reason.trim().length < 3) return;
  try { await api("/api/override", { json: { task_id: task.id, reason } }); toast("Marked done (override, 0 XP)"); S.phase = "card"; S.check = null; renderQuest(); }
  catch (e) { showError(e); }
}

// ---------- session verdict ----------
async function renderVerdict(sid) {
  const v = await api(`/api/session/${sid}/verdict`);
  if (v.complete) { beep("level"); api("/api/prefetch/tomorrow", { method: "POST" }).catch(() => {}); }
  app.innerHTML = `
    <section class="card ${v.complete ? "center burst" : ""}">
      <p class="eyebrow">${esc(v.session)}</p>
      <h1 class="${v.complete ? "verdict-ok" : "verdict-warn"}">${esc(v.headline)}</h1>
      ${v.complete ? "<p>Nice. Rest, or do a review round.</p>" : `
        <ul class="left">${v.left.map((t) => `<li>${t.icon} ${esc(t.text)}</li>`).join("")}</ul>
        <p>👉 ${esc(v.suggestion)}</p>`}
      <div class="row" ${v.complete ? 'style="justify-content:center"' : ""}>
        <button class="btn primary" id="rev">Review round</button><button class="btn" id="map">Map</button>
      </div>
    </section>`;
  $("#rev").onclick = () => go("review");
  $("#map").onclick = () => go("map");
}

// ---------- quick wins ----------
async function renderQuickWins() {
  loading("Picking 3 quick wins from yesterday…");
  try {
    const qw = await api("/api/quickwins");
    if (!qw.questions.length) { toast(qw.note || "Nothing from yesterday"); return renderQuest(); }
    let i = qw.results.length;
    const step = () => {
      if (i >= qw.questions.length) { LS.set(`qw-${qw.date}`, true); toast("Warm-up done ⚡"); return renderQuest(); }
      const q = qw.questions[i];
      app.innerHTML = `<section class="card"><p class="eyebrow">Quick win ${i + 1} of 3 · 1 minute</p>
        <label class="q" for="qa">${esc(q.q)}${q.source ? `<span class="src">📄 ${esc(q.source)}</span>` : ""}</label>
        <textarea id="qa"></textarea><div class="row"><button class="btn primary" id="qs">Check</button><button class="btn link" id="qskip">Skip</button></div><div id="help"></div></section>`;
      $("#qskip").onclick = () => { i++; step(); };
      $("#qs").onclick = async () => {
        $("#qs").disabled = true;
        const r = await api("/api/quickwins/answer", { json: { index: i, answer: $("#qa").value } });
        if (r.ok) beep("win");
        $("#help").innerHTML = `<div class="helpbox">${r.ok ? "✅" : "↺"} ${esc(r.reason)}<br><span class="muted">Answer: ${esc(r.answer)}</span></div>
          <div class="row"><button class="btn primary" id="qn">Next</button></div>`;
        $("#qn").onclick = () => { i++; step(); };
      };
    };
    step();
  } catch (e) { app.innerHTML = ""; showError(e); addBack(app); }
}

// ---------- review ----------
async function renderReview() {
  S.view = "review";
  loading("Loading review…");
  try {
    const r = await api("/api/review");
    if (r.problems.length) return renderDeck(r);
    if (!r.due.length) {
      app.innerHTML = `<section class="card center"><h1>Nothing due 🎉</h1><p class="muted">Missed items come back after 1, 2 and 4 days, always before your exam.${r.deck_size ? ` ${r.deck_size} problem card(s) are waiting for later days.` : ""}</p></section>`;
      return;
    }
    const c = r.due[0];
    app.innerHTML = `<section class="card"><p class="eyebrow">Review · ${r.total_due} due · mixed topics</p>
      <p class="muted">${esc(c.topic)}</p><div class="task-text">${esc(c.text)}</div>
      <div class="row"><button class="btn primary big" id="go">⚔️ Rematch</button></div></section>`;
    $("#go").onclick = () => startBattle({ id: c.task_id, text: c.text }, "review");
  } catch (e) { app.innerHTML = ""; showError(e); }
}

// the exact problems you missed, interleaved, one at a time
function renderDeck(r) {
  let i = 0;
  const step = () => {
    if (i >= r.problems.length) { toast("Deck round done ✅"); return renderReview(); }
    const c = r.problems[i];
    const input = c.type === "mcq"
      ? `<div class="choices">${c.choices.map((x, k) => `<button class="btn choice" data-k="${(c.choice_ids ? c.choice_ids[k] : k) + 1}"><b>${"ABCDEF"[k]}</b> ${esc(x)}</button>`).join("")}</div>`
      : `<input type="text" id="deck-ans" autocomplete="off" aria-label="Your answer">`;
    app.innerHTML = `<section class="card"><p class="eyebrow">Missed problems · ${i + 1} of ${r.problems.length} · box ${c.box + 1}/3</p>
      <p class="muted">${esc(c.topic)}</p><div class="prompt">${mathHtml(c.prompt)}</div>${input}
      <div class="row">${c.type !== "mcq" ? `<button class="btn primary" id="deck-go">Check ⏎</button>` : ""}
      ${c.rule ? `<button class="btn" id="deck-rule">📐 Rule</button>` : ""}</div><div id="fx"></div></section>`;
    const send = async (text) => {
      if (!String(text).trim()) return;
      let res;
      try { res = await api("/api/review/problem", { json: { pid: c.id, answer: String(text) } }); }
      catch (e) { $("#fx").innerHTML = `<div class="notice">Couldn't check that (${esc(e.message)}). Try again.</div>`; return; }
      if (res.result === "unreadable") { $("#fx").innerHTML = `<div class="helpbox">${esc(res.feedback)}</div>`; return; }
      celebrate(res.events || []);
      FX.play(res.result === "right" ? "hit" : "miss");
      $("#fx").innerHTML = `<div class="${res.result === "right" ? "reveal" : "helpbox"}"><b>${res.result === "right" ? "✅ Right" : "↺ Not yet: it comes back tomorrow"}</b>
        ${res.feedback ? `<p>${esc(res.feedback)}</p>` : ""}<p>Answer: <b>${esc(res.answer)}</b></p>${res.explain ? `<p class="muted">${esc(res.explain)}</p>` : ""}</div>
        <div class="row"><button class="btn primary" id="deck-next">Next ⏎</button></div>`;
      $("#deck-next").onclick = () => { i++; step(); }; $("#deck-next").focus();
    };
    if ($("#deck-ans")) { $("#deck-ans").focus(); $("#deck-ans").onkeydown = (e) => { if (e.key === "Enter") send(e.target.value); }; }
    if ($("#deck-go")) $("#deck-go").onclick = () => send($("#deck-ans").value);
    document.querySelectorAll("[data-k]").forEach((b) => (b.onclick = () => send(b.dataset.k)));
    if ($("#deck-rule")) $("#deck-rule").onclick = () => { $("#fx").innerHTML = `<div class="helpbox rule"><b>📐 Rule</b><p class="pre">${esc(c.rule)}</p></div>`; };
  };
  step();
}

// ---------- map ----------
async function showFullPlan() {
  const p = await api("/api/plan");
  $("#fullplan").innerHTML = p.sessions.map((s) => `<section class="card"><p class="eyebrow">${esc(s.date_label)} · ${esc(s.time)} · ${esc(s.subject)}</p>
    <h2>${esc(s.session)}</h2>${s.tasks.map((t) => `<div>${t.icon} ${esc(t.text)}</div>`).join("")}</section>`).join("");
}

// ---------- boss ----------
async function renderBoss(id) {
  loading("Summoning the boss from past exams… (can take ~1 min)");
  try {
    const b = await api("/api/boss/start", { json: { boss_id: id } });
    LS.set("sprint", null);
    const end = new Date(b.deadline).getTime();
    app.innerHTML = `<section class="card"><p class="eyebrow">👹 ${esc(b.boss)} · ${b.minutes} min · closed book</p>
      <div class="timer-big" id="boss-timer"></div>
      <p class="exam-style">📄 Treat this like the real exam: closed book, full working on paper, then type each final answer and attach a photo of your pages at the end.</p>
      <form id="boss-form">${b.questions.map((q, i) => `<label class="q" for="b${i}">${i + 1}. ${esc(q.q)} <span class="muted">(${q.points} pts)</span>${q.source ? `<span class="src">📄 based on ${esc(q.source)}</span>` : ""}</label><textarea id="b${i}" name="answers"></textarea>`).join("")}
      <label class="q">Photo of your working (optional) <input type="file" name="photo" accept="image/*"></label>
      <div class="row"><button class="btn primary big" type="submit">Submit</button></div></form></section>`;
    const t = setInterval(() => { const el = $("#boss-timer"); if (!el) return clearInterval(t); el.textContent = fmt((end - Date.now()) / 1000); }, 1000);
    $("#boss-form").onsubmit = async (ev) => {
      ev.preventDefault(); clearInterval(t);
      const fd = new FormData(ev.target); fd.append("boss_id", id);
      loading("Grading the boss fight…");
      const r = await api("/api/boss/submit", { method: "POST", body: fd });
      celebrate(r.events);
      app.innerHTML = `<section class="card ${r.passed ? "center burst" : ""}"><h1 class="${r.passed ? "verdict-ok" : "verdict-warn"}">${r.passed ? "👹 Boss defeated!" : "Not yet"} · ${Math.round(r.score * 100)}%</h1>
        <p>${esc(r.reason)}${r.late ? " (submitted late)" : ""}</p><h2>Answers</h2><ol>${r.answers.map((a, i) => `<li>${esc(a)}<br><span class="muted">${esc(r.feedback[i] || "")}</span></li>`).join("")}</ol></section>`;
    };
  } catch (e) { app.innerHTML = ""; showError(e); addBack(app); }
}

// ---------- stats ----------

async function renderStats() {
  loading("Loading stats…");
  try {
    const s = await api("/api/stats");
    app.innerHTML = `
      <section class="card"><div class="stat-row">
        <div class="stat"><span class="muted">Level</span><b>${s.level.level}</b><span class="muted">${s.level.xp} XP</span></div>
        <div class="stat"><span class="muted">Streak</span><b>🔥 ${s.streak.current}</b><span class="muted">best ${s.streak.best}${s.streak.freeze_available ? " · ❄️ freeze ready" : ""}</span></div>
        ${s.scope ? `<div class="stat"><span class="muted">${esc(s.scope.exam)}</span><b>${s.scope.done}/${s.scope.total}</b><span class="muted">tasks in scope · ${s.scope.days} days</span></div>` : ""}
        <div class="stat"><span class="muted">Review deck</span><b>${s.deck}</b><span class="muted">missed problems waiting</span></div>
        <div class="stat"><span class="muted">Sprints</span><b>${s.sprints}</b></div>
      </div></section>
      <section class="card"><h2>Exams</h2>${s.exams.map((e) => `<div class="exam"><span>${esc(e.name)}${e.room ? ` · ${esc(e.time)} ${esc(e.room)}` : ""}</span><b>${e.days === 0 ? "TODAY" : `${e.days} day${e.days === 1 ? "" : "s"}`}</b></div>`).join("")}</section>
      <section class="card"><div class="row spread" style="margin-top:0"><h2 style="margin:0">Mastery${s.scope && !S.showAll ? `: ${esc(s.scope.exam)} scope` : ": all topics"}</h2>
        ${s.scope ? `<button class="btn link small" id="show-all">${S.showAll ? "Show exam scope only" : "Show everything"}</button>` : ""}</div>
        <div class="heat">${s.mastery.filter((m) => !s.scope || S.showAll || s.scope.session_ids.includes(m.id)).map((m) => `<div class="heat-tile"><b>${esc((m.date || "").slice(5))}</b> ${esc(m.topic)}
        <span class="heat-pct">${Math.round(m.score * 100)}%</span><span class="heat-bar"><span style="width:${Math.round(m.score * 100)}%"></span></span></div>`).join("")}</div></section>
      <section class="card" id="inventory"><h2>Inventory</h2><p class="muted">Loading…</p></section>
      <section class="card"><h2>Settings & data</h2>
        <div class="row"><label>Campfire every <input type="number" id="set-sprint" min="5" max="60" value="${S.settings.sprint_min}" style="width:70px"> min</label>
        <label>for <input type="number" id="set-break" min="3" max="10" value="${S.settings.break_min}" style="width:60px"> min</label>
        <label><input type="checkbox" id="set-fs" ${S.settings.focus_fullscreen !== false ? "checked" : ""}> Full-screen focus mode in battles</label>
        <label>Effects <select id="set-fx">${["full", "calm", "off"].map((m) => `<option ${S.settings.fx === m ? "selected" : ""}>${m}</option>`).join("")}</select></label>
        <button class="btn" id="save-set">Save</button></div>
        <div class="row"><a class="btn primary" href="/api/export">Export CSV for Google Sheets</a>
        <label class="btn">Import checklist<input type="file" id="import-file" accept=".csv,.md,.txt" hidden></label></div>
      </section>`;
    if ($("#show-all")) $("#show-all").onclick = () => { S.showAll = !S.showAll; renderStats(); };
    $("#save-set").onclick = async () => {
      try { S.settings = await api("/api/settings", { json: { sprint_min: +$("#set-sprint").value, break_min: +$("#set-break").value, sound: S.settings.sound, focus_fullscreen: $("#set-fs").checked, fx: $("#set-fx").value } }); toast("Saved"); }
      catch (e) { showError(e); }
    };
    $("#import-file").onchange = async (ev) => {
      const fd = new FormData(); fd.append("file", ev.target.files[0]);
      try { const r = await api("/api/import", { method: "POST", body: fd }); toast(`Imported ${r.tasks} tasks`); } catch (e) { showError(e); }
    };
    renderInventory(await api("/api/inventory"));
  } catch (e) { app.innerHTML = ""; showError(e); }
}
function renderInventory(inv) {
  const eq = inv.equipped || {};
  $("#inventory").innerHTML = `<h2>Inventory</h2>
    <p class="eyebrow">Titles</p><div class="row">${inv.titles.length ? inv.titles.map((t) => `<button class="btn ${eq.title === t ? "primary" : ""}" data-title="${esc(t)}">🎖️ ${esc(t)}</button>`).join("") : '<span class="muted">Win battles to find titles.</span>'}</div>
    <p class="eyebrow" style="margin-top:14px">Themes</p><div class="row">${Object.entries(inv.theme_colors).map(([n, c]) => `<button class="btn ${(eq.theme || "teal") === n ? "primary" : ""}" data-theme="${esc(n)}"><span class="swatch" style="background:${esc(c)}"></span> ${esc(n)}</button>`).join("")}</div>
    <p class="eyebrow" style="margin-top:14px">Badges</p><div>${inv.badges.length ? inv.badges.map((b) => `🏅 ${esc(b)}`).join(" · ") : '<span class="muted">None yet. Finish a battle without switching tabs.</span>'}</div>
    <p class="eyebrow" style="margin-top:14px">Bestiary (${inv.bestiary.length})</p><div class="bestiary">${inv.bestiary.map((b) => `<div><span class="big-emoji">${monsterFor(b.enemy)}</span> ${esc(b.enemy)} <span class="stars-sm">${"★".repeat(b.stars)}${"☆".repeat(3 - b.stars)}</span></div>`).join("") || '<span class="muted">Defeated enemies appear here.</span>'}</div>`;
  document.querySelectorAll("[data-title]").forEach((b) => (b.onclick = async () => {
    const t = b.dataset.title === eq.title ? "" : b.dataset.title;
    renderInventory(await api("/api/equip", { json: { title: t } })); loadToday();
  }));
  document.querySelectorAll("[data-theme]").forEach((b) => (b.onclick = async () => {
    const inv2 = await api("/api/equip", { json: { theme: b.dataset.theme } });
    applyTheme(inv2.theme_colors[b.dataset.theme]); renderInventory(inv2);
  }));
}

function applyTheme(color) { if (color) document.documentElement.style.setProperty("--accent", color); }

// ---------- boot ----------
(async function boot() {
  try {
    const st = await api("/api/status");
    S.settings = st.settings;
    applyTheme(st.theme_color);
    $("#sound-toggle").textContent = S.settings.sound ? "🔊" : "🔈";
    if (!st.ai.claude.ok) toast(`⚠ ${st.ai.claude.why}`);
    if (!st.has_plan) return renderEmpty();
  } catch (e) { return showError(e); }
  go("quest");
})();
