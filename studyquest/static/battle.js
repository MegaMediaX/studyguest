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

async function startBattle(task, mode = "task", runId = null) {
  enterFocus(); // must run inside the click's user gesture, before any await
  notePlay();
  S.phase = "battle";
  G.saidThisBattle = 0;
  loading(task.text ? `Summoning the enemy for “${task.text}”…` : "Descending to the next floor…");
  vex("loading", $(".card"), true); G.saidThisBattle = 0;
  try {
    const [r, econ] = await Promise.all([api("/api/battle/start", { json: { task_id: task.id, mode, run_id: runId } }),
      api("/api/chest").catch(() => ({ economy: {} }))]);
    B.econ = econ.economy || {};
    if (r.state === "already_done") {
      S.phase = "card";
      if (r.run?.state === "done") return renderRunSummary(r.run);
      if (r.run) { G.run = r.run; toast("Already cleared ✅ skipping to the next floor"); return nextFloor(); }
      toast("Already defeated ✅"); return renderQuest();
    }
    if (r.state === "action") { S.phase = "card"; return startCheck(task); }
    B.data = r; B.phase = (r.problem && r.problem.number > 1) || r.rules?.gambit ? "problem" : "lesson";
    B.qStart = Date.now() - (r.elapsed || 0) * 1000;
    if (B.phase === "lesson") markLesson();
    renderBattle();
  } catch (e) { S.phase = "card"; app.innerHTML = `<section class="card"></section>`; showError(e, $(".card")); addBack($(".card")); }
}

function hpBar(hp, ghost) {
  const pct = hp.max ? Math.round((100 * hp.now) / hp.max) : 0;
  const prev = B.prevPct ?? pct; B.prevPct = pct;
  // ghost: where your best past attempt had the enemy's HP after this many problems
  let ghostMark = "";
  if (ghost && B.data?.problem) {
    const done = (B.data.problem.number || 1) - 1;
    const dealt = ghost.per_q.slice(0, done).reduce((a, b) => a + b, 0) * 100;
    const gp = Math.max(0, Math.round((100 * (hp.max - dealt)) / hp.max));
    ghostMark = `<div class="ghost-mark" style="left:${gp}%" title="Your ghost (${esc(ghost.at.slice(0, 10))})">👻</div>`;
  }
  return `<div class="hp"><div class="hp-trail" style="width:${prev}%"></div><div class="hp-fill" style="width:${pct}%"></div>${ghostMark}<span>${hp.now} / ${hp.max} HP</span></div>`;
}
function enemyPanel(d, showIntent = true) {
  const combo = d.combo >= 2 ? `<span class="combo">🔥 x${d.combo}${d.combo >= 3 ? " CRIT ready" : ""}</span>` : "";
  const affix = d.affix ? `<span class="affix">${{ armored: "🛡️ Armored", timed: "⏳ Timed", demands_proof: "📜 Elite: demands proof" }[d.affix] || ""}</span>` : "";
  const intent = showIntent && d.intent && B.phase === "problem" ? `<div class="intent">${d.intent.icon} ${esc(d.intent.text)}</div>` : "";
  return `<div class="enemy">
      <div class="monster-wrap">${intent}<div class="monster" id="monster" aria-hidden="true">${monsterFor(d.enemy)}</div></div>
      <div class="enemy-info"><div class="enemy-name">${esc(d.enemy)} ${affix}</div>${hpBar(d.hp, d.ghost)}
        <div class="muted small">${esc(d.task.text)} ${d.attempt > 1 ? "· rematch" : ""} ${combo}</div>
        ${d.staggered ? `<div class="stagger">💫 Staggered! Finish the last problems: ${d.correct}/${d.need_correct} correct needed so far.</div>` : ""}</div>
      <button class="btn link" id="exit-battle" title="Leave (progress is kept)">✕</button>
    </div>`;
}

function renderBattle(extra = "") {
  const d = B.data;
  B.answered = false;
  const body = B.phase === "lesson" ? lessonHtml(d) : problemHtml(d.problem);
  app.innerHTML = `<section class="card battle">${d.run_id && G.run ? runBar(G.run) : ""}${enemyPanel(d)}${d.notice ? `<div class="notice">${esc(d.notice)}</div>` : ""}${extra}${body}</section>`;
  $("#exit-battle").onclick = () => { exitFocus(); S.phase = "card"; go("quest"); };
  if (B.phase === "lesson") bindLesson(d); else { bindProblem(d.problem); $(".battle").scrollIntoView({ block: "start" }); }
  if (d.ghost && d.problem?.number === 1 && B.phase === "problem") toast(`👻 Your ghost from ${d.ghost.at.slice(5, 10)} is here. Beat it.`);
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
function markLesson() {
  if (B.data?.task?.id) api("/api/battle/lesson", { json: { task_id: B.data.task.id } }).catch(() => {});
}
function bindLesson(d) {
  $("#fight").onclick = () => { B.phase = "problem"; B.qStart = Date.now(); enterFocus(); renderBattle(); };
  if ($("#read-src")) $("#read-src").onclick = () => openReader(d.pages, 0);
}

// ---------- problem ----------
function problemHtml(p) {
  if (!p) return "";
  const input = p.type === "mcq"
    ? `<div class="choices">${p.choices.map((c, i) => `<button class="btn choice" data-i="${i}"><b>${"ABCDEF"[i]}</b> ${esc(c)}</button>`).join("")}</div>`
    : p.type === "short"
      ? `<textarea id="ans" placeholder="${esc(FORMAT_HINT.short)}"></textarea>`
      : `<input type="text" id="ans" autocomplete="off" spellcheck="false" aria-label="Your answer" aria-describedby="fmt">
         <p class="fmt" id="fmt">${esc(FORMAT_HINT[p.type])}</p>`;
  const src = p.source ? `<button class="btn" id="src-link">📄 ${esc(p.source.file)} · ${esc(p.source.unit)} ${p.source.n}</button>` : "";
  return `<div class="problem">
      <p class="eyebrow">Problem ${p.number} of ${p.total} · difficulty ${"◆".repeat(p.difficulty)}${"◇".repeat(3 - p.difficulty)} ${B.data.tries ? "· 2nd try (half damage)" : ""}
        ${B.data.timer ? `· <span id="qtimer" class="qtimer"></span>` : ""}</p>
      <div class="prompt">${esc(p.prompt)}</div>
      ${p.unverified ? `<p class="muted small">⚠ Two graders disagreed on this key, so either answer counts (but it won't count toward ★★★ or seals).</p>` : ""}
      ${p.work_required ? `<p class="exam-style">📝 Exam-style: solve this on paper and send a photo of your working. Correct method = +25%.</p>` : ""}
      <div id="hints"></div>
      ${input}
      ${p.type !== "mcq" ? `<div class="work">
        <label class="btn" for="work-photo">📷 Photo of your working</label>
        <input type="file" id="work-photo" accept="image/*" capture="environment" hidden>
        <span class="muted small" id="work-name">${B.photo?.idx === p.idx ? esc(B.photo.file.name) : p.work_required ? "Required here (or paste an image)." : "Optional: correct method = +25% damage, like the real exam. You can also paste an image."}</span>
        <img id="work-preview" alt="" ${B.photo?.idx === p.idx ? "" : "hidden"}>
      </div>` : ""}
      <div class="row spread">
        <span>${p.type !== "mcq" ? `<button class="btn primary big" id="attack">Attack ⏎</button>` : ""}</span>
        <span>${B.data.rules?.no_hints ? `<span class="muted small">💎 Glass Cannon: no hints</span>` : `<button class="btn" id="rule-btn" title="The formula or theorem to use, without the steps (−10% damage)">📐 Rule</button>
          <button class="btn" id="hint-btn">💡 Hint <span class="muted small">(${p.hints_available - B.data.hint_level} left${B.data.rules?.free_hints ? ", next free" : ""})</span></button>`}</span>
      </div>
      <div id="fx"></div>
      <details class="more"><summary>More help</summary><div class="row">
        <button class="btn" id="explain-btn">Explain differently</button>
        <button class="btn" id="scroll-link">📜 Lesson</button>
        ${src}
        ${B.econ?.consumables?.retry_token && B.data.tries === 1 ? `<button class="btn" id="tok-retry">↺ Retry token</button>` : ""}
        ${B.econ?.consumables?.hint_token && !B.data.rules?.no_hints ? `<button class="btn" id="tok-hint">💡 Hint token</button>` : ""}
      </div></details>
    </div>`;
}
function attachPhoto(p, file) {
  if (!file || !file.type.startsWith("image/")) return toast("That's not an image");
  if (file.size > 12 * 1024 * 1024) return toast("Photo is over 12 MB");
  B.photo = { idx: p.idx, file };
  $("#work-name").textContent = `📎 ${file.name || "pasted image"}: attached. Attack to send it.`;
  const img = $("#work-preview"); img.hidden = false; img.src = URL.createObjectURL(file);
}
function bindProblem(p) {
  if (!p) return;
  if ($("#work-photo")) {
    $("#work-photo").onchange = (e) => attachPhoto(p, e.target.files[0]);
    if (B.photo?.idx === p.idx) { const img = $("#work-preview"); img.src = URL.createObjectURL(B.photo.file); }
  }
  const ans = $("#ans");
  if (ans) { ans.focus(); ans.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitAnswer(ans.value); } }; }
  if ($("#attack")) $("#attack").onclick = () => submitAnswer(ans.value);
  document.querySelectorAll(".choice").forEach((b) => (b.onclick = () => submitAnswer(b.dataset.i === undefined ? "" : String(+b.dataset.i + 1))));
  if ($("#hint-btn")) $("#hint-btn").onclick = () => takeHint(p);
  if ($("#rule-btn")) $("#rule-btn").onclick = () => showRule(p);
  $("#scroll-link").onclick = () => { B.phase = "lesson"; markLesson(); renderBattle(); $("#fight").textContent = "⚔️ Back to the fight"; };
  for (const [id, kind] of [["#tok-retry", "retry_token"], ["#tok-hint", "hint_token"]]) {
    if ($(id)) $(id).onclick = async () => {
      try { const v = await api("/api/battle/token", { json: { task_id: B.data.task.id, kind } }); B.econ.consumables[kind]--; B.data = { ...B.data, ...v }; renderBattle(); toast(kind === "retry_token" ? "↺ Miss undone" : "💡 Next hint is free"); }
      catch (e) { toast(e.message); }
    };
  }
  $("#explain-btn").onclick = () => explainDifferently(p);
  if ($("#src-link")) $("#src-link").onclick = () => {
    const i = B.data.pages.findIndex((x) => x.file === p.source.file && x.n === p.source.n);
    openReader(i >= 0 ? B.data.pages : [{ ...p.source, course: B.data.pages[0]?.course }], Math.max(i, 0));
  };
}
document.addEventListener("keydown", (e) => {
  if (S.phase !== "battle" || B.phase !== "problem" || B.answered || B.busy || !B.data?.problem || B.data.problem.type !== "mcq") return;
  if (!document.querySelector(".choices") || $("#welcome") || $("#campfire") || $("#longsession")) return;
  if ($("#reader") || document.activeElement?.tagName === "TEXTAREA") return;
  const k = e.key.toLowerCase(); const i = "1234".indexOf(k) >= 0 ? "1234".indexOf(k) : "abcd".indexOf(k);
  if (i >= 0 && i < B.data.problem.choices.length) submitAnswer(String(i + 1));
});

async function submitAnswer(text, noWork = false) {
  const p = B.data.problem;
  const photo = B.photo?.idx === p.idx ? B.photo.file : null;
  if (B.busy || (!String(text).trim() && !photo)) return;
  B.busy = true;
  const fx = $("#fx");
  if (photo) fx.innerHTML = `<p class="muted">🧙 Vex is reading your working… (about 15 s)</p>`;
  else if (p.type === "short") fx.innerHTML = `<p class="muted">The judge is reading your answer…</p>`;
  try {
    let r;
    if (photo) {
      const fd = new FormData();
      fd.append("task_id", B.data.task.id); fd.append("idx", p.idx); fd.append("answer", String(text || "")); fd.append("photo", photo, photo.name || "working.png");
      r = await api("/api/battle/answer_photo", { method: "POST", body: fd });
      if (r.result !== "unreadable") B.photo = null;
    } else {
      r = await api("/api/battle/answer", { json: { task_id: B.data.task.id, idx: p.idx, answer: String(text), no_work: noWork } });
    }
    if (r.result === "needs_work") {
      fx.innerHTML = `<div class="helpbox" role="alert">${esc(r.feedback)}
        <div class="row"><label class="btn primary" for="work-photo">📷 Attach photo</label>
        <button class="btn" id="no-work">Send without working (half damage)</button></div></div>`;
      $("#no-work").onclick = () => { B.busy = false; submitAnswer(text, true); };
      fx.scrollIntoView({ block: "nearest" });
      return;
    }
    B.lastAnswer = String(text);
    if (r.result === "unreadable") {
      fx.innerHTML = `<div class="helpbox" role="alert">${esc(r.feedback)}</div>`;
      fx.scrollIntoView({ block: "nearest" }); $("#ans")?.focus();
      return;
    }
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
    FX.play("parry");
    renderBattle();
    floatDamage("🛡 PARRY", "parry"); $("#monster")?.classList.add("strike"); FX.screenShake();
    $(".battle")?.classList.add("hurt"); setTimeout(() => $(".battle")?.classList.remove("hurt"), 400);
    if (r.misses >= 3) vex("three_misses", $(".battle"));
    $("#fx").innerHTML = `<div class="helpbox" role="alert">${esc(r.feedback)}</div>${disputeBtn()}`;
    bindDispute(p);
    $("#fx").scrollIntoView({ block: "nearest" });
    return;
  }
  B.answered = true;
  celebrate(r.events || [], true);
  if (r.result === "hit") FX.play(r.crit ? "crit" : "hit", prev.combo); else FX.play("miss");
  if (r.crit) { FX.flash(); FX.screenShake(); }
  const reveal = r.reveal ? `<div class="reveal"><p class="eyebrow">${r.result === "hit" ? "Why it's right" : "The answer"}</p>
      <p><b>${esc(r.reveal.answer)}</b>${r.reveal.alt?.length ? ` <span class="muted small">(also accepted: ${r.reveal.alt.map(esc).join(", ")})</span>` : ""}</p>${r.reveal.explain ? `<p>${esc(r.reveal.explain)}</p>` : ""}
      ${r.reveal.solution ? `<details><summary>Worked solution</summary><p class="pre">${esc(r.reveal.solution)}</p></details>` : ""}
      ${r.result === "fail" ? disputeBtn() : ""}</div>` : "";
  const next = r.outcome ? `<button class="btn primary big" id="next">${r.outcome === "won" ? "🏆 Claim victory" : "Continue"}</button>`
    : `<button class="btn primary big" id="next">Next ⏎</button>`;
  // show the result on the finished problem, then move on
  app.querySelector(".problem").innerHTML = `<div class="prompt">${esc(p.prompt)}</div>
    <div class="hit-banner ${r.result}">${r.result === "hit" ? (r.crit ? `💥 CRITICAL! −${r.damage}` : `⚔️ Hit! −${r.damage}`) : "💨 Missed"}</div>
    ${(r.notes || []).map((n) => `<p class="muted">${esc(n)}</p>`).join("")}
    ${r.feedback ? `<div class="helpbox">📝 ${esc(r.feedback)}</div>` : ""}${reveal}<div class="row">${next}</div><div id="fx"></div>`;
  $(".enemy").outerHTML = enemyPanel(B.data, false);
  $("#exit-battle").onclick = () => { exitFocus(); S.phase = "card"; go("quest"); };
  if (r.result === "hit") { floatDamage(`−${r.damage}`, r.crit ? "crit" : "hit"); $("#monster").classList.add("shake"); }
  if (r.crit && !B.critSaid) { B.critSaid = true; vex("first_crit", $(".battle")); }
  if (r.result === "fail") bindDispute(p);
  const go_on = () => { B.qStart = Date.now(); return r.outcome ? renderOutcome(r) : renderBattle(); };
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

async function showRule(p) {
  const btn = $("#rule-btn"); btn.disabled = true;
  try {
    const r = await api("/api/battle/rule", { json: { task_id: B.data.task.id, idx: p.idx } });
    B.data.rule_used = true;
    $("#hints").insertAdjacentHTML("beforeend", `<div class="helpbox rule"><b>📐 Rule to apply</b> <span class="muted small">(−10% damage)</span><p class="pre">${esc(r.rule)}</p></div>`);
    btn.textContent = "📐 Rule shown";
  } catch (e) { btn.disabled = false; showError(e, $(".battle")); }
}
async function takeHint(p) {
  try {
    const r = await api("/api/battle/hint", { json: { task_id: B.data.task.id, idx: p.idx } });
    if (!r.hint) return toast("No more hints");
    vex("hint_used", $(".battle"));
    B.data.hint_level = r.hint_level; B.data.combo = 0;
    const label = r.free ? "Free hint" : ["", "Nudge (−25% dmg)", "Next step (−50% dmg)", "Worked solution (0 dmg, but you'll learn it)"][r.hint_level];
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
    const loot = (r.loot || []).map((l, i) => `<div class="loot ${esc(l.rarity)}" style="animation-delay:${0.9 + i * 0.3}s">
        ${l.kind === "theme" ? `<span class="swatch" style="background:${esc(l.color)}"></span> Theme: ${esc(l.name)} <button class="btn link small" data-equip-theme="${esc(l.name)}">Use</button>` : l.kind === "badge" ? `🏅 Badge: ${esc(l.name)}` : `🎖️ Title: ${esc(l.name)} <button class="btn link small" data-equip-title="${esc(l.name)}">Wear</button>`}
        <span class="rarity">${esc(l.rarity)}</span></div>`).join("");
    app.innerHTML = `<section class="card center victory">
        <div class="monster dead">${monsterFor(d.enemy)}</div>
        <h1 class="verdict-ok">${esc(d.enemy)} defeated!</h1>
        <div class="stars">${stars}</div>
        <p class="muted">${esc(r.star_tip || "")}</p>
        <p class="muted small">Best combo x${r.best_combo}${r.focus_breaks === 0 ? " · 🎯 zero tab switches" : ""}</p>
        ${loot ? `<p class="eyebrow">Loot</p><div class="loots">${loot}</div>` : ""}
        ${r.loot_odds ? `<p class="muted small">Loot odds per roll (1 roll per ★, +1 for no tab switches): theme ${Math.round(r.loot_odds.theme * 100)}%, title ${Math.round(r.loot_odds.title * 100)}%. Cosmetic only.</p>` : ""}
        ${r.ghost_result ? `<p>${r.ghost_result.surpassed ? `👻 You beat your ghost from ${esc(r.ghost_result.date.slice(5))}! +1 ◆` : `👻 Your ghost (${esc(r.ghost_result.date.slice(5))}) did better. Next time.`}</p>` : ""}
        <div class="row" style="justify-content:center"><button class="btn primary big" id="next">${nextLabel(r)}</button></div>
      </section>`;
    FX.play("kill");
    vex("win", $(".victory"));
    document.querySelectorAll("[data-equip-title]").forEach((b) => (b.onclick = async () => { await api("/api/equip", { json: { title: b.dataset.equipTitle } }); loadToday(); b.outerHTML = "✓ worn"; }));
    document.querySelectorAll("[data-equip-theme]").forEach((b) => (b.onclick = async () => { const inv = await api("/api/equip", { json: { theme: b.dataset.equipTheme } }); applyTheme(inv.theme_colors[b.dataset.equipTheme]); b.outerHTML = "✓ in use"; }));
  } else {
    app.innerHTML = `<section class="card center">
        <div class="monster">${monsterFor(d.enemy)}💨</div>
        <h1 class="verdict-warn">${esc(d.enemy)} escaped</h1>
        ${r.why ? `<p><b>${esc(r.why)}</b></p>` : ""}
        <p>No XP lost. ${r.rematch ? "Rematch any time; the next fight has new problems." : "It's in your review queue: it comes back tomorrow, then in 2 and 4 days (before your exam)."}</p>
        <div class="row" style="justify-content:center"><button class="btn primary big" id="next">${nextLabel(r)}</button></div>
      </section>`;
    FX.play("lose");
    vex("escaped", $(".card"));
  }
  $("#next").onclick = () => {
    S.taskIndex = null; B.critSaid = false; B.prevPct = null;
    if (r.run?.state === "done") renderRunSummary(r.run);
    else if (r.run?.offer?.length) renderPerkDraft(r.run);
    else go(S.view === "review" ? "review" : "quest");
    maybeCampfire(); // only after you've seen your reward
    maybeLongSession();
  };
  $("#next").focus();
}

function nextLabel(r) {
  if (r.run?.state === "done") return "🏁 Run summary";
  if (r.run?.offer?.length) return "🎁 Choose a perk";
  return r.outcome === "won" ? "Next battle →" : "Continue";
}

// question countdown for timed enemies
setInterval(() => {
  const el = $("#qtimer"); if (!el || !B.data?.timer) return;
  const left = Math.round(B.data.timer - (Date.now() - B.qStart) / 1000);
  el.textContent = left > 0 ? `⏳ ${fmt(left)}` : "⏳ late: half damage"; el.classList.toggle("late", left <= 0);
}, 500);

document.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || S.phase !== "battle" || !B.answered || !$("#next")) return;
  if (e.target?.tagName === "SUMMARY" || e.target === document.body) { e.preventDefault(); $("#next").click(); }
});

// paste an image (screenshot / Continuity Camera) straight into the battle
document.addEventListener("paste", (e) => {
  if (S.phase !== "battle" || B.phase !== "problem" || B.answered || !$("#work-photo")) return;
  const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
  if (!item) return;
  e.preventDefault();
  attachPhoto(B.data.problem, item.getAsFile());
});

// ---------- in-app reader (no other tabs needed) ----------
function openReader(pages, i) {
  const close = () => { $("#reader")?.remove(); };
  const show = async (k) => {
    const pg = pages[k];
    const box = $("#reader .reader-body"); box.innerHTML = `<p class="muted">Loading page…</p>`;
    try {
      const q = `course=${encodeURIComponent(pg.course)}&file=${encodeURIComponent(pg.file)}&n=${pg.n}`;
      const meta = await api(`/api/source?${q}`);
      box.innerHTML = meta.image ? `<img src="/api/source/img?${q}" alt="${esc(meta.file)} ${esc(meta.unit)} ${meta.n}" onload="B.applyZoom && B.applyZoom()">`
        : `<pre class="pre">${esc(meta.text || "(no text on this page)")}</pre>`;
      $("#reader .reader-title").textContent = `${meta.file} · ${meta.unit} ${meta.n} (${k + 1}/${pages.length})`;
    } catch (e) { box.innerHTML = `<p class="notice">${esc(e.message)}</p>`; }
    $("#reader .prev").disabled = k === 0; $("#reader .next").disabled = k === pages.length - 1;
    $("#reader").dataset.k = k;
  };
  close();
  document.body.insertAdjacentHTML("beforeend", `<div id="reader" role="dialog" aria-label="Course page">
      <div class="reader-bar"><span class="reader-title"></span>
        <span><button class="btn zoom-out" aria-label="Zoom out">−</button> <button class="btn zoom-in" aria-label="Zoom in">+</button>
        <button class="btn prev" aria-label="Previous page">‹</button> <button class="btn next" aria-label="Next page">›</button> <button class="btn primary close">Back to battle</button></span></div>
      <div class="reader-body"></div></div>`);
  $("#reader .close").onclick = close;
  B.zoom = B.zoom || (innerWidth < 560 ? 2 : 1);
  const applyZoom = () => { const img = $("#reader .reader-body img"); if (img) img.style.width = `${Math.round(B.zoom * Math.min(900, innerWidth - 36))}px`; };
  $("#reader .zoom-in").onclick = () => { B.zoom = Math.min(4, B.zoom + 0.5); applyZoom(); };
  $("#reader .zoom-out").onclick = () => { B.zoom = Math.max(0.75, B.zoom - 0.5); applyZoom(); };
  B.applyZoom = applyZoom;
  $("#reader .close").focus();
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
  G.saidThisBattle = 0;
  api("/api/battle/focus", { json: { task_id: B.data.task.id } }).catch(() => {});
  const p = B.data.problem;
  if ($("#welcome")) return;
  document.body.insertAdjacentHTML("beforeend", `<div id="welcome" class="overlay" role="dialog" aria-modal="true" aria-label="Welcome back"><div class="card center">
      <h1>Welcome back 👋</h1><p class="muted">You were away ${away >= 60 ? Math.round(away / 60) + " min" : away + " s"}.</p>
      <p>You're fighting <b>${esc(B.data.enemy)}</b>${p ? ` · problem ${p.number} of ${p.total}:` : "."}</p>
      ${p ? `<p class="prompt small">${esc(p.prompt.slice(0, 160))}${p.prompt.length > 160 ? "…" : ""}</p>` : ""}
      <button class="btn primary big" id="resume">Back in ⚔️</button></div></div>`);
  $("#resume").onclick = () => { $("#welcome").remove(); $("#ans")?.focus(); };
  $("#resume").focus();
});

// ---------- campfire (optional break) ----------
function maybeCampfire() {
  const since = LS.get("lastBreak", Date.now());
  if (!LS.get("lastBreak", null)) LS.set("lastBreak", Date.now());
  if (Date.now() - since < S.settings.sprint_min * 60000) return;
  setTimeout(() => {
    if (S.phase === "battle" || $("#campfire")) return;
    document.body.insertAdjacentHTML("beforeend", `<div id="campfire" class="overlay" role="dialog" aria-modal="true" aria-label="Break"><div class="card center">
        <div class="monster">🔥</div><h1>Campfire?</h1>
        <p class="muted">You've been fighting for ${Math.round((Date.now() - since) / 60000)} min. A ${S.settings.break_min}-min rest keeps you sharp.</p>
        <div class="row" style="justify-content:center"><button class="btn primary" id="rest">Rest ${S.settings.break_min} min</button><button class="btn" id="nah">Keep fighting</button></div></div></div>`);
    $("#rest").focus();
    $("#rest").onclick = () => { $("#campfire").remove(); LS.set("lastBreak", Date.now()); LS.set("break", { end: Date.now() + S.settings.break_min * 60000, minutes: S.settings.break_min }); renderBreak(); };
    $("#nah").onclick = () => { $("#campfire").remove(); LS.set("lastBreak", Date.now() - S.settings.sprint_min * 30000); };
  }, 1500);
}
