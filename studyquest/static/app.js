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
function loading(text) { app.innerHTML = `<section class="card center"><p class="muted">${esc(text)}</p></section>`; }

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
}
function sessionWindow() {
  const s = S.today?.session; if (!s || !s.time || S.today.label !== "today") return null;
  const [a, b] = s.time.replace("—", "–").split("–").map((x) => x.trim());
  if (!a || !b) return null;
  return { start: new Date(`${s.date}T${a}`), end: new Date(`${s.date}T${b}`) };
}
function tick() {
  const sp = LS.get("sprint", null), br = LS.get("break", null), now = Date.now();
  let frac = 0, label = "";
  if (sp) { frac = 1 - (sp.end - now) / (sp.minutes * 60000); label = `⏱ ${fmt((sp.end - now) / 1000)}`; if (now >= sp.end) finishSprint(); }
  else if (br) { frac = 1 - (br.end - now) / (br.minutes * 60000); label = `☕ ${fmt((br.end - now) / 1000)}`; if (now >= br.end) endBreak(); }
  else { const w = sessionWindow(); if (w && now >= w.start && now < w.end) { frac = (now - w.start) / (w.end - w.start); label = `${fmt((w.end - now) / 1000)} left in session`; } }
  $("#timebar-fill").style.width = `${Math.min(100, Math.max(0, frac * 100))}%`;
  $("#hud-clock").textContent = label;
  const big = $("#big-timer"); if (big) big.textContent = sp ? fmt((sp.end - now) / 1000) : br ? fmt((br.end - now) / 1000) : "";
  const hint = $("#hint-wait");
  if (hint) { const left = (S.check.retryAt - now) / 1000; hint.textContent = left > 0 ? `Retry unlocks in ${fmt(left)}` : ""; $("#submit-check").disabled = left > 0; }
}
setInterval(tick, 1000);

// ---------- navigation ----------
document.querySelectorAll("nav button[data-view]").forEach((b) => b.addEventListener("click", () => go(b.dataset.view)));
$("#sound-toggle").addEventListener("click", async () => {
  S.settings.sound = !S.settings.sound;
  $("#sound-toggle").textContent = S.settings.sound ? "🔊" : "🔈";
  await api("/api/settings", { json: S.settings });
});
function go(view) {
  S.view = view;
  document.querySelectorAll("nav button[data-view]").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  ({ quest: renderQuest, review: renderReview, map: renderMap, stats: renderStats })[view]();
}

// ---------- quest ----------
async function loadToday() { S.today = await api("/api/today"); renderHud(S.today); return S.today; }
function currentTask() {
  const tasks = S.today?.session?.tasks || [];
  if (S.taskIndex == null || S.taskIndex >= tasks.length || tasks[S.taskIndex].status === "done") {
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
  if (LS.get("sprint", null)) return renderSprint();
  if (LS.get("break", null)) return renderBreak();
  if (S.phase === "check" && S.check) return renderCheck();
  loading("Loading today's quest…");
  let t;
  try { t = await loadToday(); } catch (e) { if (e.data?.kind === "no_plan") return renderEmpty(); app.innerHTML = ""; return showError(e); }
  const s = t.session;
  if (!s) { app.innerHTML = `<section class="card center"><h1>No sessions left in the plan 🎉</h1></section>`; return; }
  const task = currentTask();
  if (!task) return renderVerdict(s.id);
  const where = t.last ? `<button class="btn link" id="where">Where was I?</button>` : "";
  const qw = !LS.get(`qw-${t.date}`, false) && t.label === "today" ? `<button class="btn link" id="qw">3 quick wins ⚡</button>` : "";
  app.innerHTML = `
    <section class="card" id="task-card">
      <p class="eyebrow">${t.label === "today" ? "Today" : "Next"} · ${esc(s.date_label)} · ${esc(s.time)} · ${esc(s.subject)}</p>
      <h2>${esc(s.session)}</h2>
      ${dots(s.tasks, S.taskIndex)}
      <p class="eyebrow">Task ${S.taskIndex + 1} of ${s.total} · ${esc(task.kind)} ${task.status === "review" ? "· 🔁 review" : ""}</p>
      <div class="task-text">${esc(task.text)}</div>
      <div class="row"><button class="btn primary big" id="start">Start</button></div>
      <div class="row spread">
        <span>${where}${qw}</span>
        <span><button class="btn link" id="check-now">I've done it → check</button><button class="btn link" id="skip">Next task ›</button></span>
      </div>
      <div id="help"></div>
      ${t.backlog.tasks ? `<p class="muted" style="font-size:.85rem;margin-top:14px">${t.backlog.tasks} earlier task(s) still open. They're on the Map when you want them.</p>` : ""}
    </section>`;
  $("#start").onclick = () => renderIntent(task);
  $("#check-now").onclick = () => startCheck(task);
  $("#skip").onclick = () => { S.taskIndex = nextIndex(s.tasks, S.taskIndex); renderQuest(); };
  if (t.last) $("#where").onclick = () => whereWasI(t.last);
  if (qw) $("#qw").onclick = () => renderQuickWins();
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

// ---------- implementation intention + sprint + break ----------
function renderIntent(task) {
  const m = S.settings.sprint_min;
  app.innerHTML = `
    <section class="card">
      <p class="eyebrow">Before you start</p>
      <div class="task-text" style="font-size:1.25rem">${esc(task.text)}</div>
      <label class="q" for="intent">When the timer starts, I will first…</label>
      <input type="text" id="intent" placeholder="open the PDF at §1.1 and write the definition of a level curve" autofocus>
      <div class="row">
        <label class="muted">Sprint <input type="range" id="len" min="5" max="25" value="${m}"> <b id="len-v">${m}</b> min</label>
      </div>
      <div class="row"><button class="btn primary big" id="go">Go</button><button class="btn link" id="back">Back</button></div>
    </section>`;
  $("#len").oninput = (e) => { $("#len-v").textContent = e.target.value; };
  $("#back").onclick = () => renderQuest();
  const start = () => {
    const minutes = +$("#len").value;
    LS.set("sprint", { end: Date.now() + minutes * 60000, minutes, intention: $("#intent").value.trim(), taskId: task.id, taskText: task.text });
    renderSprint();
  };
  $("#go").onclick = start;
  $("#intent").onkeydown = (e) => { if (e.key === "Enter") start(); };
}
function renderSprint() {
  const sp = LS.get("sprint", null);
  app.innerHTML = `
    <section class="card">
      <p class="eyebrow">Sprint · ${sp.minutes} min</p>
      <div class="task-text">${esc(sp.taskText)}</div>
      ${sp.intention ? `<p class="muted">First: ${esc(sp.intention)}</p>` : ""}
      <div class="timer-big" id="big-timer">${fmt((sp.end - Date.now()) / 1000)}</div>
      <div class="row">
        <button class="btn" id="stuck">I'm stuck</button>
        <button class="btn" id="explain">Explain differently</button>
        <button class="btn" id="extend" title="In flow? Keep going">+5 min</button>
        <button class="btn link" id="done-early">Done early → check</button>
      </div>
      <div id="help"></div>
    </section>`;
  $("#stuck").onclick = () => askHelp("stuck", sp.taskId);
  $("#explain").onclick = () => askHelp("explain", sp.taskId);
  $("#done-early").onclick = () => finishSprint(true);
  $("#extend").onclick = () => {
    const cur = LS.get("sprint", null); if (!cur) return;
    LS.set("sprint", { ...cur, end: cur.end + 5 * 60000, minutes: cur.minutes + 5 });
    toast("+5 min"); tick();
  };
}
async function finishSprint(early = false) {
  const sp = LS.get("sprint", null); if (!sp) return;
  LS.set("sprint", null);
  const minutes = early ? Math.max(1, Math.round((Date.now() - (sp.end - sp.minutes * 60000)) / 60000)) : sp.minutes;
  try {
    const r = await api("/api/sprint/done", { json: { minutes, intention: sp.intention, task_id: sp.taskId } });
    loadToday().catch(() => {});
    if (r.events.some((e) => e.type === "streak")) { beep("win"); toast(`🔥 Streak: ${r.streak.current} day${r.streak.current === 1 ? "" : "s"}`); }
  } catch (e) { /* the sprint still happened; don't block the flow */ }
  if (early) { const task = { id: sp.taskId, text: sp.taskText }; return startCheck(task); }
  LS.set("break", { end: Date.now() + S.settings.break_min * 60000, minutes: S.settings.break_min, taskId: sp.taskId, taskText: sp.taskText });
  beep("win");
  renderBreak();
}
function renderBreak() {
  app.innerHTML = `
    <section class="card break">
      <p class="eyebrow">Break</p>
      <h1>Stand up. Water. Look far away.</h1>
      <div class="timer-big" id="big-timer"></div>
      <div class="row" style="justify-content:center">
        <button class="btn primary" id="check">Check the task now</button>
        <button class="btn" id="skipbreak">Skip break</button>
      </div>
    </section>`;
  const br = LS.get("break", null);
  $("#check").onclick = () => { LS.set("break", null); startCheck({ id: br.taskId, text: br.taskText }); };
  $("#skipbreak").onclick = () => endBreak();
  tick();
}
function endBreak() { if (!LS.get("break", null)) return; LS.set("break", null); beep("lose"); if (S.view === "quest") renderQuest(); }

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
function celebrate(events) {
  let xp = 0;
  for (const e of events || []) {
    if (e.type === "xp") xp += e.amount;
    if (e.type === "level_up") { beep("level"); setTimeout(() => toast(`⭐ Level ${e.level}!`), 1400); }
  }
  if (xp) { beep("win"); toast(`+${xp} XP`); }
  loadToday().catch(() => {}); // refresh the HUD (XP bar, streak, review badge)
}
function handleResult(r) {
  const c = S.check;
  if (r.status === "wait") return toast(`Hint time: ${r.seconds}s left`);
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
    <p>No XP lost. This comes back tomorrow, then in 3 and 7 days.</p>
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
  if (v.complete) beep("level");
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
    if (!r.due.length) { app.innerHTML = `<section class="card center"><h1>Nothing due 🎉</h1><p class="muted">Missed items come back after 1, 3 and 7 days.</p></section>`; return; }
    const c = r.due[0];
    app.innerHTML = `<section class="card"><p class="eyebrow">Review · ${r.total_due} due · mixed topics</p>
      <p class="muted">${esc(c.topic)}</p><div class="task-text">${esc(c.text)}</div>
      <div class="row"><button class="btn primary big" id="go">Recall it</button></div></section>`;
    $("#go").onclick = () => startCheck({ id: c.task_id, text: c.text }, "review");
  } catch (e) { app.innerHTML = ""; showError(e); }
}

// ---------- map ----------
async function renderMap() {
  loading("Loading map…");
  try {
    const m = await api("/api/map");
    app.innerHTML = m.zones.map((z) => `
      <section class="card zone"><h2>${esc(z.zone)} <span class="muted">· ${z.cleared}/${z.levels.length} cleared</span></h2>
        <div class="levels">${z.levels.map((l) => `<div class="level ${l.complete ? "cleared" : l.left < l.total ? "partial" : ""}" title="${esc(l.date_label)} · ${esc(l.session)} · ${l.total - l.left}/${l.total}">${esc((l.date || "").slice(8))}</div>`).join("")}</div>
      </section>`).join("") + m.bosses.map((b) => `
      <section class="card"><h2>👹 ${esc(b.name)} ${b.beaten ? "· beaten ✅" : ""}</h2>
        <p class="muted">${b.minutes}-min timed mock from past exams. ${b.unlocked ? "Unlocked." : `Unlocks after “${esc(b.unlock_after)}”.`}${b.best != null ? ` Best: ${Math.round(b.best * 100)}%` : ""}</p>
        <button class="btn ${b.unlocked ? "primary" : ""}" data-boss="${esc(b.id)}" ${b.unlocked ? "" : "disabled"}>Fight</button>
      </section>`).join("") + `<button class="btn link" id="full">Show full plan</button><div id="fullplan"></div>`;
    document.querySelectorAll("[data-boss]").forEach((b) => (b.onclick = () => renderBoss(b.dataset.boss)));
    $("#full").onclick = showFullPlan;
  } catch (e) { app.innerHTML = ""; showError(e); }
}
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
function heatColor(v) { return v <= 0 ? "var(--line)" : `rgba(94,234,212,${0.18 + v * 0.7})`; }
async function renderStats() {
  loading("Loading stats…");
  try {
    const s = await api("/api/stats");
    app.innerHTML = `
      <section class="card"><div class="stat-row">
        <div class="stat"><span class="muted">Level</span><b>${s.level.level}</b><span class="muted">${s.level.xp} XP</span></div>
        <div class="stat"><span class="muted">Streak</span><b>🔥 ${s.streak.current}</b><span class="muted">best ${s.streak.best}${s.streak.freeze_available ? " · ❄️ freeze ready" : ""}</span></div>
        <div class="stat"><span class="muted">Tasks done</span><b>${s.counts.done + s.counts.override}/${s.total}</b><span class="muted">🔁 ${s.counts.review} · overrides ${s.overrides}</span></div>
        <div class="stat"><span class="muted">Sprints</span><b>${s.sprints}</b></div>
      </div></section>
      <section class="card"><h2>Exams</h2>${s.exams.map((e) => `<div class="exam"><span>${esc(e.name)}${e.room ? ` · ${esc(e.time)} ${esc(e.room)}` : ""}</span><b>${e.days === 0 ? "TODAY" : `${e.days} day${e.days === 1 ? "" : "s"}`}</b></div>`).join("")}</section>
      <section class="card"><h2>Mastery by topic</h2><div class="heat">${s.mastery.map((m) => `<div style="background:${heatColor(m.score)}" title="${Math.round(m.score * 100)}%"><b>${esc((m.date || "").slice(5))}</b> ${esc(m.topic)}</div>`).join("")}</div></section>
      <section class="card"><h2>Settings & data</h2>
        <div class="row"><label>Sprint <input type="number" id="set-sprint" min="5" max="25" value="${S.settings.sprint_min}" style="width:70px"> min</label>
        <label>Break <input type="number" id="set-break" min="3" max="5" value="${S.settings.break_min}" style="width:60px"> min</label>
        <button class="btn" id="save-set">Save</button></div>
        <div class="row"><a class="btn primary" href="/api/export">Export CSV for Google Sheets</a>
        <label class="btn">Import checklist<input type="file" id="import-file" accept=".csv,.md,.txt" hidden></label></div>
      </section>`;
    $("#save-set").onclick = async () => {
      try { S.settings = await api("/api/settings", { json: { ...S.settings, sprint_min: +$("#set-sprint").value, break_min: +$("#set-break").value } }); toast("Saved"); }
      catch (e) { showError(e); }
    };
    $("#import-file").onchange = async (ev) => {
      const fd = new FormData(); fd.append("file", ev.target.files[0]);
      try { const r = await api("/api/import", { method: "POST", body: fd }); toast(`Imported ${r.tasks} tasks`); } catch (e) { showError(e); }
    };
  } catch (e) { app.innerHTML = ""; showError(e); }
}

// ---------- boot ----------
(async function boot() {
  try {
    const st = await api("/api/status");
    S.settings = st.settings;
    $("#sound-toggle").textContent = S.settings.sound ? "🔊" : "🔈";
    if (!st.ai.claude.ok) toast(`⚠ ${st.ai.claude.why}`);
    if (!st.has_plan) return renderEmpty();
  } catch (e) { return showError(e); }
  go("quest");
})();
