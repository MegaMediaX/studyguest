// Meta layer: mentor "Old Vex", runs + perk draft, chests, bounties, economy chip, hyperfocus guard.
"use strict";

const G = { lines: null, run: null, saidThisBattle: 0, saidThisRun: 0, playStarted: null, longWarnedAt: 0 };
const LONG_SESSION_MS = 90 * 60000;

// ---------- mentor ----------
async function mentorLines() {
  if (!G.lines) { try { G.lines = await (await fetch("/static/mentor.json")).json(); } catch { G.lines = {}; } }
  return G.lines;
}
async function vex(event, where, force = false) {
  const lines = (await mentorLines())[event]; if (!lines?.length) return;
  if (!force && (G.saidThisBattle >= 1 || G.saidThisRun >= 3)) return;
  const recent = LS.get("vexRecent", []);
  const fresh = lines.filter((l) => !recent.includes(l));
  const line = (fresh.length ? fresh : lines)[Math.floor(Math.random() * (fresh.length ? fresh.length : lines.length))];
  LS.set("vexRecent", [line, ...recent].slice(0, 12));
  G.saidThisBattle++; G.saidThisRun++;
  const host = where || $(".card"); if (!host) return;
  host.querySelector(".vex")?.remove();
  host.insertAdjacentHTML("afterbegin", `<div class="vex" role="note"><span class="vex-face">🧙</span><div><b>Old Vex</b><p>${esc(line)}</p></div></div>`);
}

// ---------- economy chip + Rift ----------
function econChip(e) {
  if (!e) return "";
  const c = e.consumables || {};
  return `<span class="econ" title="Key shards → keys → chests">🔑 ${e.keys || 0} · ◆ ${e.shards || 0}/3${c.hint_token ? ` · 💡×${c.hint_token}` : ""}${c.retry_token ? ` · ↺×${c.retry_token}` : ""}</span>`;
}
function riftBanner(rift) {
  if (!rift) return "";
  const pct = rift.total ? Math.round((100 * rift.sealed) / rift.total) : 0;
  return `<div class="rift"><div class="rift-top"><b>🌀 The Rift opens in ${rift.days} day${rift.days === 1 ? "" : "s"}</b>
      <span class="muted small">${esc(rift.name)}</span></div>
      <div class="rift-bar"><div style="width:${pct}%"></div></div>
      <div class="muted small">Sealed ${rift.sealed} of ${rift.total} floors before it.${rift.next ? ` Next: ${esc(rift.next)}.` : ""}</div></div>`;
}

// ---------- bounties ----------
async function bountiesCard() {
  try {
    const b = await api("/api/bounties");
    return `<section class="card bounties"><div class="row spread" style="margin-top:0"><h2 style="margin:0">📜 Today's bounties</h2>${econChip(b.economy)}</div>
      ${b.items.map((x) => `<div class="bounty ${x.done ? "done" : ""}">
          <div class="row spread" style="margin:0"><span>${x.done ? "✅" : "▫️"} ${esc(x.text)}</span>
          <span class="muted small">+${x.reward.shards} ◆ ${!x.done && b.rerolls > 0 ? `<button class="btn link small" data-reroll="${esc(x.id)}">reroll</button>` : ""}</span></div>
          <div class="mini-bar"><div style="width:${Math.round((100 * x.progress) / x.target)}%"></div></div></div>`).join("")}
      ${b.economy.keys > 0 ? `<div class="row"><button class="btn primary" id="open-chest">🎁 Open a chest (${b.economy.keys} key${b.economy.keys > 1 ? "s" : ""})</button></div>` : ""}
    </section>`;
  } catch { return ""; }
}
function bindBounties() {
  document.querySelectorAll("[data-reroll]").forEach((btn) => (btn.onclick = async () => {
    try { await api("/api/bounties/reroll", { json: { bounty_id: btn.dataset.reroll } }); renderQuest(); } catch (e) { toast(e.message); }
  }));
  if ($("#open-chest")) $("#open-chest").onclick = () => openChest();
}

// ---------- runs ----------
function runBar(run) {
  if (!run) return "";
  const pips = Array.from({ length: run.floors }, (_, i) => {
    const log = run.log[i];
    return `<span class="pip ${log ? (log.won ? "won" : "lost") : i === run.floor ? "now" : ""}" title="Floor ${i + 1}${i === run.floors - 1 && run.floors >= 3 ? " (elite)" : ""}">${log ? (log.won ? "★" : "✕") : i === run.floors - 1 && run.floors >= 3 ? "👑" : i + 1}</span>`;
  }).join("");
  const perksHtml = run.perks.map((p) => `<span class="perk-chip" title="${esc(p.name)}: ${esc(p.desc)}">${p.icon}</span>`).join("");
  return `<div class="runbar"><span class="muted small">RUN</span>${pips}<span class="perks">${perksHtml}</span></div>`;
}
async function startRun() {
  try {
    const r = await api("/api/run/start", { method: "POST" });
    G.run = r.run; G.saidThisRun = 0;
    api("/api/battle/prefetch", { json: { task_ids: r.run.queue.slice(1, 4) } }).catch(() => {});
    FX.play("perk");
    nextFloor();
  } catch (e) { toast(e.message); }
}
function nextFloor() {
  const n = G.run?.next; if (!n) return renderQuest();
  startBattle({ id: n.task_id, text: "" }, n.mode, G.run.id);
}
function renderPerkDraft(run) {
  G.run = run;
  FX.play("perk");
  app.innerHTML = `<section class="card center draft">
      ${runBar(run)}
      <h1>Floor ${run.floor} cleared</h1>
      <p class="muted">Vex tosses you three trinkets. Take one; it lasts the whole run.</p>
      <div class="perk-cards">${run.offer.map((p, i) => `<button class="perk-card" data-perk="${esc(p.id)}" style="animation-delay:${i * 0.15}s">
          <div class="perk-icon">${p.icon}</div><b>${esc(p.name)}</b><p>${esc(p.desc)}</p><p class="muted small"><i>${esc(p.flavor)}</i></p></button>`).join("")}</div>
    </section>`;
  vex("perk", $(".draft"), true);
  document.querySelectorAll("[data-perk]").forEach((b) => (b.onclick = async () => {
    try { const r = await api("/api/run/perk", { json: { perk_id: b.dataset.perk } }); G.run = r.run; toast(`${b.querySelector(".perk-icon").textContent} ${b.querySelector("b").textContent}`); nextFloor(); }
    catch (e) { toast(e.message); }
  }));
}
function renderRunSummary(run) {
  G.run = null;
  const s = run.summary;
  celebrate(run.events || []);
  app.innerHTML = `<section class="card center victory">
      ${runBar(run)}
      <h1 class="verdict-ok">Run complete</h1>
      <div class="stat-row" style="justify-content:center;text-align:center">
        <div class="stat"><span class="muted">Floors</span><b>${s.cleared}/${s.floors}</b></div>
        <div class="stat"><span class="muted">Stars</span><b>${"★".repeat(Math.min(s.stars, 12)) || "0"}</b></div>
        <div class="stat"><span class="muted">Time</span><b>${s.minutes}m</b></div></div>
      <p class="muted">Perks: ${run.perks.map((p) => `${p.icon} ${esc(p.name)}`).join(" · ") || "none"}</p>
      <div class="row" style="justify-content:center">
        ${run.keys > 0 ? `<button class="btn primary big" id="open-chest">🎁 Open chest (${run.keys} 🔑)</button>` : ""}
        <button class="btn ${run.keys > 0 ? "" : "primary big"}" id="done">Back to the floor</button></div>
    </section>`;
  vex("run_done", $(".victory"), true);
  FX.play("kill");
  if ($("#open-chest")) $("#open-chest").onclick = () => openChest();
  $("#done").onclick = () => go("quest");
}

// ---------- chests ----------
async function openChest() {
  const info = await api("/api/chest");
  app.innerHTML = `<section class="card center chest-screen">
      <div class="chest" id="chest">🎁</div>
      <p class="muted small">Odds: cosmetic ${info.odds.cosmetic * 100}% · consumable ${info.odds.consumable * 100}% · legendary ${info.odds.rare * 100}%.
      No duplicates. A legendary is guaranteed within ${info.pity} chests. Nothing is ever bought.</p>
      <div id="chest-result"></div>
      <div class="row" style="justify-content:center"><button class="btn primary big" id="crack">Open (1 🔑)</button><button class="btn" id="back">Later</button></div>
    </section>`;
  $("#back").onclick = () => go("quest");
  $("#crack").onclick = async () => {
    $("#crack").disabled = true;
    try {
      const r = await api("/api/chest/open", { method: "POST" });
      const chest = $("#chest");
      for (let i = 0; i < r.shakes; i++) { chest.classList.remove("wiggle"); void chest.offsetWidth; chest.classList.add("wiggle"); await new Promise((ok) => setTimeout(ok, 420)); }
      FX.play("chest"); FX.flash(); chest.textContent = "✨";
      const d = r.drop;
      $("#chest-result").innerHTML = `<div class="loot ${esc(d.rarity === "legendary" ? "epic" : d.rarity)}" style="max-width:420px;margin:12px auto">
          ${d.kind === "theme" ? `<span class="swatch" style="background:${esc(d.color)}"></span> Theme: ${esc(d.name)}` : d.kind === "title" ? `🎖️ Title: ${esc(d.name)}` : `🧪 ${esc(d.name)}`}
          <span class="rarity">${esc(d.rarity)}</span></div>`;
      $("#crack").outerHTML = r.economy.keys > 0 ? `<button class="btn primary" id="again">Open another (${r.economy.keys} 🔑)</button>` : "";
      if ($("#again")) $("#again").onclick = () => openChest();
    } catch (e) { toast(e.message); $("#crack").disabled = false; }
  };
}

// ---------- hyperfocus guard ----------
// Counts from your first battle of this sitting; shown only between battles, never mid-problem.
function notePlay() { if (!G.playStarted) G.playStarted = Date.now(); }
function maybeLongSession() {
  if (!G.playStarted || Date.now() - G.playStarted < LONG_SESSION_MS || Date.now() - G.longWarnedAt < LONG_SESSION_MS) return;
  if ($("#longsession")) return;
  G.longWarnedAt = Date.now();
  document.body.insertAdjacentHTML("beforeend", `<div id="longsession" class="overlay" role="dialog" aria-modal="true" aria-label="Long session"><div class="card center"><div class="monster">🧙</div>
      <h1>Bank the win?</h1><p id="long-line" class="muted"></p>
      <p class="small muted">Stopping now earns a rested bonus: +1 ◆ key shard (once a day).</p>
      <div class="row" style="justify-content:center"><button class="btn primary" id="stop-now">Stop for now</button><button class="btn" id="one-more">One more floor</button></div></div></div>`);
  mentorLines().then((l) => { $("#long-line").textContent = (l.long_session || [""])[0]; });
  $("#stop-now").focus();
  $("#stop-now").onclick = async () => {
    $("#longsession").remove();
    try { celebrate((await api("/api/rest", { method: "POST" })).events); } catch { /* bonus is optional */ }
    G.playStarted = null;
    app.innerHTML = `<section class="card center"><h1>See you tomorrow ⚔️</h1><p class="muted">Rest is when memory sets.</p></section>`;
  };
  $("#one-more").onclick = () => $("#longsession").remove();
}
