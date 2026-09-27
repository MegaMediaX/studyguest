// Game feel: synthesised sfx (no audio files), hit-stop, crit flash, trailing HP bar.
// settings.fx = "full" | "calm" | "off". Calm keeps sounds soft and skips shake/flash.
"use strict";

const FX = (() => {
  let ctx = null;
  const mode = () => (S.settings?.fx || "full");
  const soundOn = () => S.settings?.sound !== false && mode() !== "off";
  function ac() { if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)(); return ctx; }

  function tone(freq, t0, dur, type = "square", vol = 0.12) {
    const c = ac(), o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t0);
    const v = mode() === "calm" ? vol * 0.5 : vol;
    g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(v, t0 + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(c.destination); o.start(t0); o.stop(t0 + dur + 0.02);
    return o;
  }
  function noise(t0, dur, vol = 0.08) {
    const c = ac(), len = Math.floor(c.sampleRate * dur), buf = c.createBuffer(1, len, c.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const src = c.createBufferSource(), g = c.createGain(); src.buffer = buf; g.gain.value = mode() === "calm" ? vol / 2 : vol;
    src.connect(g); g.connect(c.destination); src.start(t0);
  }
  const semis = (base, n) => base * Math.pow(2, n / 12);

  const sfx = {
    hit(combo = 0) { const t = ac().currentTime; tone(semis(440, Math.min(combo, 7)), t, 0.09); tone(semis(660, Math.min(combo, 7)), t + 0.05, 0.08, "triangle"); },
    crit(combo = 0) { const t = ac().currentTime; noise(t, 0.12, 0.1); tone(semis(880, Math.min(combo, 7)), t, 0.14); tone(semis(1320, Math.min(combo, 7)), t + 0.06, 0.16, "sawtooth", 0.07); },
    miss() { const t = ac().currentTime; tone(130, t, 0.18, "sine", 0.18); tone(98, t + 0.06, 0.2, "sine", 0.12); },
    parry() { const t = ac().currentTime; tone(1200, t, 0.05, "square", 0.06); tone(900, t + 0.04, 0.08, "triangle", 0.06); },
    kill() { const t = ac().currentTime; [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, t + i * 0.08, 0.18, "triangle", 0.1)); },
    chest() { const c = ac(), t = c.currentTime, o = tone(200, t, 0.6, "sawtooth", 0.06); o.frequency.exponentialRampToValueAtTime(1600, t + 0.55); },
    shard() { const t = ac().currentTime; tone(1568, t, 0.1, "sine", 0.08); tone(2093, t + 0.07, 0.12, "sine", 0.06); },
    perk() { const t = ac().currentTime; [392, 523, 659].forEach((f, i) => tone(f, t + i * 0.06, 0.12, "triangle", 0.08)); },
    lose() { const t = ac().currentTime; [392, 330, 262].forEach((f, i) => tone(f, t + i * 0.12, 0.2, "sine", 0.1)); },
  };
  function play(name, arg) { if (!soundOn()) return; try { sfx[name]?.(arg); } catch { /* audio unavailable */ } }

  // 70 ms freeze before the HP bar moves: the "impact" read
  function hitStop(ms = 70) { return new Promise((r) => setTimeout(r, mode() === "full" ? ms : 0)); }
  function flash() {
    if (mode() !== "full") return;
    const f = document.createElement("div"); f.className = "flash"; document.body.append(f); setTimeout(() => f.remove(), 180);
  }
  function screenShake() {
    if (mode() !== "full") return;
    document.body.classList.remove("shake-screen"); void document.body.offsetWidth; document.body.classList.add("shake-screen");
  }
  return { play, hitStop, flash, screenShake };
})();
