// Battles: lesson scroll → problems one at a time → instant feedback → victory + loot.
// Shares globals with app.js ($, S, api, esc, toast, beep, celebrate, loading, showError, go).
"use strict";

const MONSTERS = ["👾", "🐉", "🦂", "👹", "🦑", "🤖", "🐙", "🧟", "🦖", "👻", "🕷️", "🐺"];
const B = { data: null, phase: "lesson", busy: false, left: null };

function monsterFor(name) {
  let h = 0; for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return MONSTERS[h % MONSTERS.length];
}
const FORMAT_HINT = {
  numeric: "A number or exact form: 5/√2 · sqrt(2)/2 · 3pi/4 · -1.25",
  expression: "An expression: 2xy + y^2 · e^(xy) · sqrt(x^2+y^2)",
  multi: "A point or vector: (1, -2) or (2/3, 1/3, 2/3)",
  short: "One line in your own words",
};

async function startBattle(task, mode = "task") {
  S.phase = "battle";
  loading(`Summoning the enemy for “${task.text}”…`);
  try {
    const r = await api("/api/battle/start", { json: { task_id: task.id, mode } });
    if (r.state === "already_done") { toast("Already defeated ✅"); S.phase = "card"; return renderQuest(); }
    if (r.state === "action") { S.phase = "card"; return startCheck(task); }
    B.data = r; B.phase = r.problem && r.problem.number > 1 ? "problem" : "lesson";
    enterFocus();
    renderBattle();
  } catch (e) { S.phase = "card"; app.innerHTML = `<section class="card"></section>`; showError(e, $(".card")); addBack($(".card")); }
}

function hpBar(hp) {
  const pct = hp.max ? Math.round((100 * hp.now) / hp.max) : 0;
  return `<div class="hp"><div class="hp-fill" style="width:${pct}%"></div><span>${hp.now} / ${hp.max} HP</span></div>`;
}
function enemyPanel(d) {
  const combo = d.combo >= 2 ? `<span class="combo">🔥 x${d.combo}${d.combo >= 3 ? " CRIT ready" : ""}</span>` : "";
  return `<div class="enemy">
      <div class="monster" id="monster" aria-hidden="true">${monsterFor(d.enemy)}</div>
      <div class="enemy-info"><div class="enemy-name">${esc(d.enemy)}</div>${hpBar(d.hp)}
        <div class="muted small">${esc(d.task.text)} ${d.attempt > 1 ? "· rematch" : ""} ${combo}</div></div>
      <button class="btn link" id="exit-battle" title="Leave (progress is kept)">✕</button>
    </div>`;
}

function renderBattle(extra = "") {
  const d = B.data;
  const body = B.phase === "lesson" ? lessonHtml(d) : problemHtml(d.problem);
  app.innerHTML = `<section class="card battle">${enemyPanel(d)}${d.notice ? `<div class="notice">${esc(d.notice)}</div>` : ""}${extra}${body}</section>`;
  $("#exit-battle").onclick = () => { exitFocus(); S.phase = "card"; go("quest"); };
  if (B.phase === "lesson") bindLesson(d); else bindProblem(d.problem);
}

// ---------- lesson ----------
function lessonHtml(d) {
  const L = d.lesson, ex = L.example;
  return `<div class="scroll">
      <p class="eyebrow">📜 Scroll of knowledge · 1 minute</p>
      <h2>${esc(L.title)}</h2>
      <ul class="points">${L.points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
      ${L.formula ? `<div class="formula">${esc(L.formula)}</div>` : ""}
      ${ex ? `<details class="example"><summary>See a worked example</summary><p><b>${esc(ex.problem)}</b></p>
        <ol>${(ex.steps || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ol><p>→ <b>${esc(ex.answer)}</b></p></details>` : ""}
      ${d.pages.length ? `<button class="btn" id="read-src">📖 Read the course pages here (${d.pages.length})</button>` : ""}
    </div>
    <div class="row"><button class="btn primary big" id="fight">⚔️ Fight!</button></div>`;
}
function bindLesson(d) {
  $("#fight").onclick = () => { B.phase = "problem"; enterFocus(); renderBattle(); };
  if ($("#read-src")) $("#read-src").onclick = () => openReader(d.pages, 0);
}

// ---------- problem ----------
function problemHtml(p) {
  if (!p) return "";
  const input = p.type === "mcq"
    ? `<div class="choices">${p.choices.map((c, i) => `<button class="btn choice" data-i="${i}"><b>${"ABCDEF"[i]}</b> ${esc(c)}</button>`).join("")}</div>`
    : p.type === "short"
      ? `<textarea id="ans" placeholder="${esc(FORMAT_HINT.short)}"></textarea>`
      : `<input type="text" id="ans" autocomplete="off" spellcheck="false" placeholder="${esc(FORMAT_HINT[p.type])}">`;
  const src = p.source ? `<button class="btn link small" id="src-link">📄 ${esc(p.source.file)} · ${esc(p.source.unit)} ${p.source.n}</button>` : "";
  return `<div class="problem">
      <p class="eyebrow">Problem ${p.number} of ${p.total} · ${"★".repeat(p.difficulty)}${"☆".repeat(3 - p.difficulty)} ${B.data.tries ? "· 2nd try (half damage)" : ""}</p>
      <div class="prompt">${esc(p.prompt)}</div>
      ${src}
      <div id="hints"></div>
      ${input}
      <div class="row spread">
        <span>${p.type !== "mcq" ? `<button class="btn primary big" id="attack">Attack ⏎</button>` : ""}</span>
        <span><button class="btn" id="hint-btn">💡 Hint <span class="muted small">(${p.hints_available - B.data.hint_level} left)</span></button>
        <button class="btn link" id="explain-btn">Explain differently</button></span>
      </div>
      <div id="fx"></div>
    </div>`;
}
function bindProblem(p) {
  if (!p) return;
  const ans = $("#ans");
  if (ans) { ans.focus(); ans.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitAnswer(ans.value); } }; }
  if ($("#attack")) $("#attack").onclick = () => submitAnswer(ans.value);
  document.querySelectorAll(".choice").forEach((b) => (b.onclick = () => submitAnswer(b.dataset.i === undefined ? "" : String(+b.dataset.i + 1))));
  $("#hint-btn").onclick = () => takeHint(p);
  $("#explain-btn").onclick = () => explainDifferently(p);
  if ($("#src-link")) $("#src-link").onclick = () => {
    const i = B.data.pages.findIndex((x) => x.file === p.source.file && x.n === p.source.n);
    openReader(i >= 0 ? B.data.pages : [{ ...p.source, course: B.data.pages[0]?.course }], Math.max(i, 0));
  };
}
document.addEventListener("keydown", (e) => {
  if (S.phase !== "battle" || B.phase !== "problem" || !B.data?.problem || B.data.problem.type !== "mcq") return;
  if ($("#reader") || document.activeElement?.tagName === "TEXTAREA") return;
  const k = e.key.toLowerCase(); const i = "1234".indexOf(k) >= 0 ? "1234".indexOf(k) : "abcd".indexOf(k);
  if (i >= 0 && i < B.data.problem.choices.length) submitAnswer(String(i + 1));
});

async function submitAnswer(text) {
  if (B.busy || !String(text).trim()) return;
  B.busy = true;
  const p = B.data.problem;
  const fx = $("#fx"); if (p.type === "short") fx.innerHTML = `<p class="muted">The judge is reading your answer…</p>`;
  try {
    const r = await api("/api/battle/answer", { json: { task_id: B.data.task.id, idx: p.idx, answer: String(text) } });
    B.lastAnswer = String(text);
    handleHit(r, p);
  } catch (e) { showError(e, $(".battle")); } finally { B.busy = false; }
}

function floatDamage(text, cls) {
  const m = $("#monster"); if (!m) return;
  const f = document.createElement("div"); f.className = `dmg ${cls}`; f.textContent = text; m.append(f);
  setTimeout(() => f.remove(), 1100);
}

function handleHit(r, p) {
  const prev = B.data;
  B.data = { ...prev, ...r, task: prev.task, lesson: prev.lesson, pages: prev.pages };
  if (r.result === "miss") {
    beep("lose");
    renderBattle();
    floatDamage("🛡 PARRY", "parry"); $("#monster")?.classList.add("block");
    $("#fx").innerHTML = `<div class="helpbox">${esc(r.feedback)}</div>${disputeBtn()}`;
    bindDispute(p);
    return;
  }
  celebrate(r.events || []);
  if (r.result === "hit") beep(r.crit ? "level" : "win"); else beep("lose");
  const reveal = r.reveal ? `<div class="reveal"><p class="eyebrow">${r.result === "hit" ? "Why it's right" : "The answer"}</p>
      <p><b>${esc(r.reveal.answer)}</b></p>${r.reveal.explain ? `<p>${esc(r.reveal.explain)}</p>` : ""}
      ${r.reveal.solution ? `<details><summary>Worked solution</summary><p class="pre">${esc(r.reveal.solution)}</p></details>` : ""}
      ${r.result === "fail" ? disputeBtn() : ""}</div>` : "";
  const next = r.outcome ? `<button class="btn primary big" id="next">${r.outcome === "won" ? "🏆 Claim victory" : "Continue"}</button>`
    : `<button class="btn primary big" id="next">Next ⏎</button>`;
  // show the result on the finished problem, then move on
  app.querySelector(".problem").innerHTML = `<div class="prompt">${esc(p.prompt)}</div>
    <div class="hit-banner ${r.result}">${r.result === "hit" ? (r.crit ? `💥 CRITICAL! −${r.damage}` : `⚔️ Hit! −${r.damage}`) : "💨 Missed"}</div>
    ${reveal}<div class="row">${next}</div><div id="fx"></div>`;
  $(".enemy").outerHTML = enemyPanel(B.data);
  $("#exit-battle").onclick = () => { exitFocus(); S.phase = "card"; go("quest"); };
  if (r.result === "hit") { floatDamage(`−${r.damage}`, r.crit ? "crit" : "hit"); $("#monster").classList.add("shake"); }
  if (r.result === "fail") bindDispute(p);
  const go_on = () => (r.outcome ? renderOutcome(r) : renderBattle());
  $("#next").onclick = go_on; $("#next").focus();
}

function disputeBtn() { return `<button class="btn link" id="dispute">I think I'm right</button>`; }
function bindDispute(p) {
  const b = $("#dispute"); if (!b) return;
  b.onclick = async () => {
    b.disabled = true; b.textContent = "Asking the judge…";
    try {
      const r = await api("/api/battle/dispute", { json: { task_id: B.data.task.id, idx: p.idx, answer: B.lastAnswer || $("#ans")?.value || "" } });
      if (!r.upheld) { b.outerHTML = `<p class="muted">Judge: ${esc(r.reason)}</p>`; return; }
      toast("✅ Judge agrees with you!"); handleHit({ ...r, result: "hit" }, p);
    } catch (e) { b.textContent = "Couldn't reach the judge"; }
  };
}

async function takeHint(p) {
  try {
    const r = await api("/api/battle/hint", { json: { task_id: B.data.task.id, idx: p.idx } });
    if (!r.hint) return toast("No more hints");
    B.data.hint_level = r.hint_level; B.data.combo = 0;
    const label = ["", "Nudge (−25% dmg)", "Next step (−50% dmg)", "Worked solution (0 dmg, but you'll learn it)"][r.hint_level];
    $("#hints").insertAdjacentHTML("beforeend", `<div class="helpbox"><b>💡 ${label}</b><p class="pre">${esc(r.hint)}</p></div>`);
    $("#hint-btn").innerHTML = `💡 Hint <span class="muted small">(${p.hints_available - r.hint_level} left)</span>`;
  } catch (e) { showError(e, $(".battle")); }
}
async function explainDifferently(p) {
  $("#hints").insertAdjacentHTML("beforeend", `<div class="helpbox muted" id="exp-wait">Asking for another angle…</div>`);
  try {
    const r = await api("/api/help/explain", { json: { task_id: B.data.task.id } });
    $("#exp-wait").outerHTML = `<div class="helpbox">💡 <span class="muted">(${esc(r.by)})</span> ${esc(r.text)}</div>`;
  } catch (e) { $("#exp-wait").remove(); showError(e, $(".battle")); }
}

// ---------- outcome ----------
function renderOutcome(r) {
  exitFocus();
  S.phase = "card";
  const d = B.data;
  if (r.outcome === "won") {
    const stars = [1, 2, 3].map((i) => `<span class="star ${i <= r.stars ? "on" : ""}" style="animation-delay:${i * 0.25}s">★</span>`).join("");
    const loot = (r.loot || []).map((l, i) => `<div class="loot ${l.rarity}" style="animation-delay:${0.9 + i * 0.3}s">
        ${l.kind === "theme" ? `<span class="swatch" style="background:${esc(l.color)}"></span> Theme: ${esc(l.name)}` : l.kind === "badge" ? `🏅 Badge: ${esc(l.name)}` : `🎖️ Title: ${esc(l.name)}`}
        <span class="rarity">${esc(l.rarity)}</span></div>`).join("");
    app.innerHTML = `<section class="card center victory">
        <div class="monster dead">${monsterFor(d.enemy)}</div>
        <h1 class="verdict-ok">${esc(d.enemy)} defeated!</h1>
        <div class="stars">${stars}</div>
        <p class="muted">Best combo x${r.best_combo}${r.focus_breaks === 0 ? " · 🎯 zero tab switches" : ""}</p>
        ${loot ? `<p class="eyebrow">Loot</p><div class="loots">${loot}</div>` : ""}
        <div class="row" style="justify-content:center"><button class="btn primary big" id="next">Next battle →</button></div>
      </section>`;
    beep("level");
  } else {
    app.innerHTML = `<section class="card center">
        <div class="monster">${monsterFor(d.enemy)}💨</div>
        <h1 class="verdict-warn">${esc(d.enemy)} escaped</h1>
        <p>No XP lost. ${r.rematch ? "Rematch any time; the next fight has fresh problems." : "It's in your review queue: it comes back tomorrow, then in 3 and 7 days."}</p>
        <div class="row" style="justify-content:center"><button class="btn primary big" id="next">Continue</button></div>
      </section>`;
  }
  $("#next").onclick = () => { S.taskIndex = null; go(S.view === "review" ? "review" : "quest"); };
  $("#next").focus();
  maybeCampfire();
}

// ---------- in-app reader (no other tabs needed) ----------
function openReader(pages, i) {
  const close = () => { $("#reader")?.remove(); };
  const show = async (k) => {
    const pg = pages[k];
    const box = $("#reader .reader-body"); box.innerHTML = `<p class="muted">Loading page…</p>`;
    try {
      const q = `course=${encodeURIComponent(pg.course)}&file=${encodeURIComponent(pg.file)}&n=${pg.n}`;
      const meta = await api(`/api/source?${q}`);
      box.innerHTML = meta.image ? `<img src="/api/source/img?${q}" alt="${esc(meta.file)} ${esc(meta.unit)} ${meta.n}">`
        : `<pre class="pre">${esc(meta.text || "(no text on this page)")}</pre>`;
      $("#reader .reader-title").textContent = `${meta.file} · ${meta.unit} ${meta.n} (${k + 1}/${pages.length})`;
    } catch (e) { box.innerHTML = `<p class="notice">${esc(e.message)}</p>`; }
    $("#reader .prev").disabled = k === 0; $("#reader .next").disabled = k === pages.length - 1;
    $("#reader").dataset.k = k;
  };
  close();
  document.body.insertAdjacentHTML("beforeend", `<div id="reader" role="dialog" aria-label="Course page">
      <div class="reader-bar"><span class="reader-title"></span>
        <span><button class="btn prev">‹</button> <button class="btn next">›</button> <button class="btn primary close">Back to battle</button></span></div>
      <div class="reader-body"></div></div>`);
  $("#reader .close").onclick = close;
  $("#reader .prev").onclick = () => show(+$("#reader").dataset.k - 1);
  $("#reader .next").onclick = () => show(+$("#reader").dataset.k + 1);
  show(i);
}
document.addEventListener("keydown", (e) => {
  if (!$("#reader")) return;
  if (e.key === "Escape") $("#reader").remove();
  if (e.key === "ArrowRight") $("#reader .next")?.click();
  if (e.key === "ArrowLeft") $("#reader .prev")?.click();
});

// ---------- focus mode ----------
function enterFocus() {
  if (!S.settings?.focus_fullscreen || document.fullscreenElement) return;
  document.documentElement.requestFullscreen?.().catch(() => {});
}
function exitFocus() { if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {}); }
document.addEventListener("visibilitychange", () => {
  if (S.phase !== "battle" || !B.data) return;
  if (document.hidden) { B.left = Date.now(); return; }
  if (!B.left) return;
  const away = Math.round((Date.now() - B.left) / 1000); B.left = null;
  if (away < 3) return;
  api("/api/battle/focus", { json: { task_id: B.data.task.id } }).catch(() => {});
  const p = B.data.problem;
  document.body.insertAdjacentHTML("beforeend", `<div id="welcome" class="overlay"><div class="card center">
      <h1>Welcome back 👋</h1><p class="muted">You were away ${away >= 60 ? Math.round(away / 60) + " min" : away + " s"}.</p>
      <p>You're fighting <b>${esc(B.data.enemy)}</b>${p ? ` · problem ${p.number} of ${p.total}:` : "."}</p>
      ${p ? `<p class="prompt small">${esc(p.prompt.slice(0, 160))}${p.prompt.length > 160 ? "…" : ""}</p>` : ""}
      <button class="btn primary big" id="resume">Back in ⚔️</button></div></div>`);
  $("#resume").onclick = () => { $("#welcome").remove(); $("#ans")?.focus(); };
});

// ---------- campfire (optional break) ----------
function maybeCampfire() {
  const since = LS.get("lastBreak", Date.now());
  if (!LS.get("lastBreak", null)) LS.set("lastBreak", Date.now());
  if (Date.now() - since < S.settings.sprint_min * 60000) return;
  setTimeout(() => {
    if (S.phase === "battle") return;
    document.body.insertAdjacentHTML("beforeend", `<div id="campfire" class="overlay"><div class="card center">
        <div class="monster">🔥</div><h1>Campfire?</h1>
        <p class="muted">You've been fighting for ${Math.round((Date.now() - since) / 60000)} min. A ${S.settings.break_min}-min rest keeps you sharp.</p>
        <div class="row" style="justify-content:center"><button class="btn primary" id="rest">Rest ${S.settings.break_min} min</button><button class="btn" id="nah">Keep fighting</button></div></div></div>`);
    $("#rest").onclick = () => { $("#campfire").remove(); LS.set("lastBreak", Date.now()); LS.set("break", { end: Date.now() + S.settings.break_min * 60000, minutes: S.settings.break_min }); renderBreak(); };
    $("#nah").onclick = () => { $("#campfire").remove(); LS.set("lastBreak", Date.now() - S.settings.sprint_min * 30000); };
  }, 1500);
}
