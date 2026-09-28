// World map: regions (courses) → zones (topic clusters) on an SVG map, with the Rift countdown.
"use strict";

const W = { data: null, region: null, zone: null };
const TIER_ICON = { Unexplored: "·", Attempted: "◔", Familiar: "◑", Proficient: "◕", Mastered: "✦" };

async function renderWorld() {
  loading("Unrolling the map…");
  try {
    const [data, runState] = await Promise.all([api("/api/world"), api("/api/run").catch(() => ({ run: null }))]);
    W.data = data; G.run = runState.run;
    const today = S.today || await loadToday().catch(() => null);
    const hereSession = today?.session?.session;
    const regions = W.data.regions;
    if (!W.region || !regions.some((r) => r.course === W.region)) {
      W.region = (regions.find((r) => r.zones.some((z) => z.sessions.some((s) => s.session === hereSession))) || regions[0])?.course;
    }
    const region = regions.find((r) => r.course === W.region);
    const here = region.zones.find((z) => z.sessions.some((s) => s.session === hereSession));
    if (!W.zone || !region.zones.some((z) => z.id === W.zone)) W.zone = (here || region.zones.find((z) => z.state === "open") || region.zones[0]).id;
    app.innerHTML = `
      <div class="region-tabs">${regions.map((r) => `<button class="btn ${r.course === W.region ? "primary" : ""}" data-region="${esc(r.course)}">${r.icon} ${esc(r.region)} <span class="small">${r.sealed}/${r.zones.length} ✦</span></button>`).join("")}</div>
      ${regionRift(region)}
      ${innerWidth < 560 ? zoneList(region, here) : `<section class="card map-card"><svg class="worldmap" viewBox="0 0 820 400" role="img" aria-label="${esc(region.region)} map">${mapSvg(region, here)}</svg></section>`}
      <div id="zone-panel"></div>
      ${W.data.bosses.map((b) => `<section class="card"><h2>👹 ${esc(b.name)} ${b.beaten ? "· beaten ✅" : ""}</h2>
        <p class="muted">${b.minutes}-min timed mock from past exams. ${b.unlocked ? "Unlocked." : `Unlocks after “${esc(b.unlock_after)}”.`}${b.best != null ? ` Best: ${Math.round(b.best * 100)}%` : ""}</p>
        <button class="btn ${b.unlocked ? "primary" : ""}" data-boss="${esc(b.id)}" ${b.unlocked ? "" : "disabled"}>Fight</button></section>`).join("")}
      <button class="btn link" id="full">Show full plan</button><div id="fullplan"></div>`;
    document.querySelectorAll("[data-region]").forEach((b) => (b.onclick = () => { W.region = b.dataset.region; W.zone = null; renderWorld(); }));
    document.querySelectorAll(".zone-item").forEach((b) => (b.onclick = () => { selectZone(b.dataset.zone); $("#zone-panel").scrollIntoView({ block: "start" }); }));
    document.querySelectorAll(".zone-node").forEach((g) => {
      g.onclick = () => selectZone(g.dataset.zone);
      g.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectZone(g.dataset.zone); } };
    });
    document.querySelectorAll("[data-boss]").forEach((b) => (b.onclick = () => renderBoss(b.dataset.boss)));
    $("#full").onclick = showFullPlan;
    selectZone(W.zone);
  } catch (e) { app.innerHTML = ""; showError(e); }
}

// phones: a vertical path is readable where an 820-wide map would shrink labels to ~6px
function zoneList(region, here) {
  return `<section class="card zone-list">${region.zones.map((z, i) => `
    <button class="zone-item ${z.state} ${W.zone === z.id ? "selected" : ""}" data-zone="${esc(z.id)}">
      <span class="zi-icon">${z.state === "locked" ? "🔒" : z.state === "sealed" ? "✦" : esc(z.icon)}</span>
      <span class="zi-main"><b>${esc(z.name)}</b>${here && here.id === z.id ? " 🚩" : ""}
        <span class="zi-sub">${esc(z.tier)} · ${Math.round(z.mastery * 100)}%${z.rematches ? ` · ${z.rematches} rematch due` : ""}${z.corruption > 0 && z.state !== "sealed" ? ` · 🌀 ${Math.round(z.corruption * 100)}%` : ""}</span>
        <span class="mini-bar"><span style="width:${Math.round(z.mastery * 100)}%"></span></span></span>
    </button>${i < region.zones.length - 1 ? '<span class="zi-edge" aria-hidden="true"></span>' : ""}`).join("")}</section>`;
}

function regionRift(r) {
  if (!r.exam) return `<div class="rift"><b>${r.icon} ${esc(r.region)}</b> <span class="muted small">No exam scheduled for this region.</span></div>`;
  const pct = r.scope_total ? Math.round((100 * r.scope_sealed) / r.scope_total) : 0;
  const left = r.zones.filter((z) => z.exam?.name === r.exam.name && z.state !== "sealed").map((z) => z.name);
  return `<div class="rift"><div class="rift-top"><b>🌀 The Rift opens in ${r.exam.days} day${r.exam.days === 1 ? "" : "s"}</b>
      <span class="muted small">${esc(r.exam.name)}${r.exam.room ? ` · ${esc(r.exam.time)} ${esc(r.exam.room)}` : ""}</span></div>
      <div class="rift-bar"><div style="width:${pct}%"></div></div>
      <div class="muted small">Sealed ${r.scope_sealed} of ${r.scope_total} zones in its path.${left.length ? ` Still open: ${left.map(esc).join(", ")}.` : " Every zone is sealed. 🛡️"}</div></div>`;
}

function mapSvg(region, here) {
  const zs = region.zones;
  const path = zs.map((z, i) => `${i ? "L" : "M"}${z.x},${z.y}`).join(" ");
  // lit path: up to the last reachable zone
  const lastOpen = zs.reduce((k, z, i) => (z.state !== "locked" ? i : k), 0);
  const lit = zs.slice(0, lastOpen + 1).map((z, i) => `${i ? "L" : "M"}${z.x},${z.y}`).join(" ");
  const deco = decoFor(region.course);
  const nodes = zs.map((z) => zoneNode(z, here && here.id === z.id)).join("");
  return `
    <defs>
      <radialGradient id="corrupt"><stop offset="0%" stop-color="#a855f7" stop-opacity=".75"/><stop offset="100%" stop-color="#a855f7" stop-opacity="0"/></radialGradient>
      <linearGradient id="land-${esc(region.course)}" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="${region.course === "MECT313" ? "#1f1712" : "#101c1a"}"/><stop offset="100%" stop-color="#0f1115"/></linearGradient>
    </defs>
    <rect x="0" y="0" width="820" height="400" rx="18" fill="url(#land-${esc(region.course)})"/>
    ${deco}
    <path d="${path}" class="trail"/>
    <path d="${lit}" class="trail lit"/>
    ${nodes}`;
}

function decoFor(course) {
  const icons = course === "MECT313" ? ["⚙️", "🔩", "⚡", "🛠️", "🔥", "⚙️", "🔌"] : ["🌲", "⛰️", "🌲", "🪨", "🌲", "⛰️", "🌿"];
  const spots = [[40, 60], [300, 70], [520, 330], [760, 340], [150, 360], [640, 60], [420, 110], [770, 60], [30, 190], [560, 380]];
  return spots.map(([x, y], i) => `<text x="${x}" y="${y}" class="deco">${icons[i % icons.length]}</text>`).join("");
}

function zoneNode(z, isHere) {
  const r = 34, circ = 2 * Math.PI * (r + 6);
  const ring = z.state === "locked" ? "" : `<circle cx="${z.x}" cy="${z.y}" r="${r + 6}" class="ring-bg"/>
    <circle cx="${z.x}" cy="${z.y}" r="${r + 6}" class="ring ${z.state}" stroke-dasharray="${(circ * z.mastery).toFixed(1)} ${circ.toFixed(1)}" transform="rotate(-90 ${z.x} ${z.y})"/>`;
  const haze = z.corruption > 0 && z.state !== "locked"
    ? `<circle cx="${z.x}" cy="${z.y}" r="${60 + 30 * z.corruption}" fill="url(#corrupt)" opacity="${(0.25 + 0.6 * z.corruption).toFixed(2)}" class="haze"/>` : "";
  const badge = z.rematches ? `<g><circle cx="${z.x + 30}" cy="${z.y - 30}" r="11" class="badge-dot"/><text x="${z.x + 30}" y="${z.y - 26}" class="badge-txt">${z.rematches}</text></g>` : "";
  const flag = isHere ? `<text x="${z.x - 8}" y="${z.y - 50}" class="here">🚩</text>` : "";
  const sel = W.zone === z.id ? "selected" : "";
  return `<g class="zone-node ${z.state} ${sel}" data-zone="${esc(z.id)}" tabindex="0" role="button" aria-label="${esc(z.name)}: ${z.state}, ${esc(z.tier)}">
      ${haze}${ring}
      <circle cx="${z.x}" cy="${z.y}" r="${r}" class="node-body"/>
      <text x="${z.x}" y="${z.y + 10}" class="node-icon">${z.state === "locked" ? "🔒" : z.state === "sealed" ? "✦" : esc(z.icon)}</text>
      <text x="${z.x}" y="${z.y + 62}" class="node-label">${esc(z.name)}</text>
      <text x="${z.x}" y="${z.y + 80}" class="node-sub">${esc(TIER_ICON[z.tier] || "")} ${esc(z.tier)} · ${Math.round(z.mastery * 100)}%</text>
      ${badge}${flag}
    </g>`;
}

function selectZone(id) {
  W.zone = id;
  document.querySelectorAll(".zone-node, .zone-item").forEach((g) => g.classList.toggle("selected", g.dataset.zone === id));
  const region = W.data.regions.find((r) => r.course === W.region);
  const z = region.zones.find((x) => x.id === id);
  if (!z) return;
  const canRun = z.state !== "locked" && (z.open_tasks.length || z.rematches);
  const status = z.state === "sealed" ? "✦ Sealed: the Rift can't touch this zone."
    : z.state === "locked" ? "🔒 Locked: get the previous zone to Familiar, or wait until its sessions come up."
      : z.corruption > 0 ? `🌀 The Rift is ${Math.round(z.corruption * 100)}% into this zone. Seal it: reach 80% and win one spaced rematch here.`
        : "Open. Reach 80% and win a spaced rematch here to seal it.";
  $("#zone-panel").innerHTML = `<section class="card zone-panel">
      <div class="row spread" style="margin-top:0"><h2 style="margin:0">${esc(z.icon)} ${esc(z.name)}</h2><span class="tier tier-${esc(z.tier.toLowerCase())}">${esc(z.tier)}</span></div>
      <div class="floor-progress"><div style="width:${Math.round(z.mastery * 100)}%"></div></div>
      <p class="muted small">${status}</p>
      <div class="zone-grid">
        <div><p class="eyebrow">Floors (sessions)</p>${z.sessions.map((s) => `<div>${s.left === 0 ? "✅" : "▫️"} ${esc(s.date_label)} · ${esc(s.session)} <span class="muted small">${s.total - s.left}/${s.total}</span></div>`).join("") || '<span class="muted">No sessions planned here yet.</span>'}</div>
        <div><p class="eyebrow">Bestiary here</p>${z.enemies.map((b) => `<div>${monsterFor(b.enemy)} ${esc(b.enemy)} <span class="stars-sm">${"★".repeat(b.stars)}</span></div>`).join("") || '<span class="muted">No enemies defeated here yet.</span>'}</div>
      </div>
      <div class="row">${G.run ? `<button class="btn primary big" id="zone-continue">▶ Continue your run in ${esc(G.run.session)} (floor ${G.run.floor + 1}/${G.run.floors})</button>
        <button class="btn link" id="zone-endrun">End it to start here</button>` : canRun ? `<button class="btn primary big" id="zone-run">▶ Start a run here <span class="small">(${Math.min(4, z.open_tasks.length + (z.rematches ? 1 : 0))} floors${z.rematches ? `, ${z.rematches} rematch` : ""})</span></button>` : ""}
        ${z.exam ? `<span class="muted small">${esc(z.exam.name)} in ${z.exam.days} days</span>` : ""}</div>
    </section>`;
  if ($("#zone-continue")) $("#zone-continue").onclick = () => { go("quest"); };
  if ($("#zone-endrun")) $("#zone-endrun").onclick = async () => { await api("/api/run/end", { method: "POST" }); G.run = null; selectZone(z.id); };
  if ($("#zone-run")) $("#zone-run").onclick = async () => {
    try {
      const r = await api("/api/run/start", { json: { zone: z.id } });
      G.run = r.run; G.saidThisRun = 0; S.view = "quest";
      document.querySelectorAll("nav button[data-view]").forEach((b) => b.classList.toggle("active", b.dataset.view === "quest"));
      api("/api/battle/prefetch", { json: { task_ids: r.run.queue.slice(1, 4) } }).catch(() => {});
      FX.play("perk"); nextFloor();
    } catch (e) { toast(e.message); }
  };
}
