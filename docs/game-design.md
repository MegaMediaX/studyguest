# StudyQuest: game design spec (v2)

Goal: make StudyQuest feel like a game one wants to start ("one more run") while keeping retrieval practice, spacing and correct answers at the centre. Written 2026-09-28 for one learner (Mechatronics, ADHD). MATH202 Exam I is on 2026-10-08, MECT313 Quiz 2 around 2026-10-12, MECT313 Midterm around 2026-10-19.
Evidence tags: **[E]** evidence (paper, meta-analysis, company A/B data), **[D]** designer practice or talk (credible, not controlled), **[O]** opinion or analysis. Sources are numbered and listed at the end.

---

## 1. Diagnosis: why it still feels like "a quiz with a skin"

Blunt version: every battle has the same shape. Lesson, 5 questions, HP bar goes down, stars. The enemy is a progress bar with a name. Nothing the player **decides** changes the next few minutes, so there is no game, only feedback.

1. **No meaningful choices.** Games hook through decisions with consequences: pick a relic, take a risky path, spend or save [D: 3, 4, 13]. In StudyQuest the only decision is "answer the question", which is the work itself. Hints are the one lever, and they are framed as a penalty.
2. **Every enemy is the same.** HP is always 70% of the available damage, with no abilities, patterns or phases. A Transformer enemy and a Lagrange enemy play the same way. Slay the Spire gets most of its variety from enemy *intent*: you read what the enemy will do and respond [D: 3].
3. **No run structure.** Each battle is a separate transaction. There is no arc across a session (build up, then a climax), no carry-over power, and nothing at stake from one battle to the next. "One more run" comes from runs that are short, each run being different, and meta-progress surviving death [D: 4, 5].
4. **Rewards don't change anything.** The loot is titles and colour themes. Cosmetics are fine, but when *all* loot is cosmetic, it stops mattering after the first few. Sailer and Homner found that reward and status elements on their own help less than challenge, meaningful goals and narrative [E: 1].
5. **No world and no one to talk to.** There is no place, no character and no threat. The "exam in 10 days" is the most urgent thing in the student's life, and the game does not use it as a story.
6. **Weak game feel.** A hit is a number changing. "Juice" (hit-stop, particles, screen shake, layered sound, rising pitch on combos) is what makes the same input feel alive [D: 6]. Balatro's scoring cascade is a slot-machine-like sequence of sound and animation that the player builds themselves [O: 7].
7. **The daily loop is thin.** A streak and a freeze are the only reason to come back. There are no daily goals that change, nothing to look forward to (a chest, a zone unlock), and the tie to the exam date is only a countdown.
8. **The ADHD fit is incomplete.** The interest-based nervous system responds to **novelty, challenge, urgency and interest** [O/clinical: 8]. The current design gives immediate feedback and some challenge, but little novelty (same format every time) and only passive urgency (a date).

What already works and must be kept: instant grading, spaced "rematches", tiered hints, a boss mock exam that mirrors the real exam, and a focus mode with a recap. Those are the learning core [E: 9, 10].

---

## 2. Core loop redesign

```
SECOND-TO-SECOND  read enemy intent -> solve -> SUBMIT -> hit-stop + damage number + sfx (pitch rises with combo)
     |                                   wrong -> enemy attacks the shield, mentor says one line, worked step shown
MINUTE-TO-MINUTE  BATTLE (3-6 problems, 4-8 min) -> loot drop (key shard / gold) -> PERK DRAFT (pick 1 of 3)
     |
SESSION (= a RUN, 20-35 min)
   [Floor 1: warm-up (spaced review enemy)] -> perk -> [Floor 2: new topic] -> perk -> [Floor 3: elite w/ ability]
        -> perk/rest -> [Floor 4: mini-boss (mixed/interleaved)] -> RUN SUMMARY: ghost comparison, chest, bounty ticks
   Losing a run is fine: you keep XP, bestiary entries, mastery ticks and "notes" (Hades rule: death still pays) [D: 5]
     |
DAY    open app -> mentor greeting + 3 bounties + world threat meter -> 1-2 runs -> chest -> close with a
       "tomorrow's rematches" preview (the next reason to come back: a known enemy returning)
     |
UNTIL EXAM   world map: course = region, topic cluster = zone. Zones unlock by mastery. "The Rift" (exam)
       advances one step per day. Sealing a zone (mastery) pushes back its corruption. Final boss = mock exam,
       unlocked when the zones in scope are sealed or 3 days before the exam, whichever comes first.
```

Design rules for the loop:
- **A run is always ≤ 35 min** and can be paused at any floor boundary. Floors are natural break points, so a break never breaks the run.
- **Floor 1 is always a due rematch** (spacing) and **floor 4 always mixes topics** (interleaving [E: 11]). The game layer decides the order, and the learning science decides what goes on each floor.
- **Every reward points back to studying**: keys come from correct streaks, perks change how you practise, zones open through mastery.

---

## 3. Mechanics catalogue (22)

Format: **what it is** / StudyQuest mapping / why it hooks / learning risk / cost / needs.

1. **Runs with floors (Expeditions).** A session is a 4-floor run through one zone / Hooks: short, bounded arc with a climax; "one more run" [D: 4, 5] / Risk: the run could push aside what is due. Fix: floor 1 is always the SRS pick / **M** / `progress.run`, `/api/run/*`, run HUD.
2. **Perk draft between floors.** Pick 1 of 3 perks that last for the run. They change *learning behaviour*, not only numbers (list in §4.1) / Hooks: build choices and risk/reward, like Slay the Spire relics or Vampire Survivors level-ups [D: 3, 13] / Risk: perks that remove scaffolds (Glass Cannon) on topics that are too hard. Fix: gate them on topic accuracy / **M** / perk table, `enc.mods`.
3. **Enemy intents and affixes.** An enemy shows what it will do next ("Winding up: next question timed 90 s") / Hooks: reading and responding to intent is the core of Slay the Spire [D: 3]; novelty for ADHD [8] / Risk: timers raise anxiety. Timers are only on well-learned topics and are always opt-out / **M** / affix field on encounter.
4. **"Demands proof" enemies.** Can only be finished by a short written explanation ("Why is this point a saddle?"), which the AI grades / Hooks: a different verb / **Learning-positive**: self-explanation, g = 0.55 [E: 12] / Risk: AI grading mistakes. Keep the existing dispute button / **S** (short answers already exist).
5. **Bosses with phases.** The mock exam gets 3 phases: MCQ barrage, then derivation, then a "desperation" phase (one long problem). HP carries across phases / Hooks: a climax that feels like a set piece / Risk: none if the content matches the exam / **M** / `boss.phases[]`.
6. **Elites and mini-bosses with interleaving.** A floor-4 "Chimera" draws problems from 2–3 topics / **Learning-positive**: interleaving beat blocked practice in >12 RCTs [E: 11] / Risk: harder, feels worse in the moment. Frame it as "elite" so harder is expected / **S**.
7. **In-world mentor NPC.** "Old Vex", a retired machine-smith who lost a duel to the Rift. Short scripted lines react to events (first crit, 3 misses, returning after a break, a zone sealed) / Hooks: relatedness and narrative; Hades delivers story through short reactive lines after each run [D: 5] / Risk: nagging. Lines are rare and never guilt-trip / **S** / `mentor.json` line bank.
8. **Daily bounties.** Three a day, e.g. "Land 5 first-try hits on partials", "Beat a Demands-proof enemy", "Clear a rematch before noon". One free reroll / Hooks: a fresh short goal every day; novelty [8]; Duolingo-style daily quests [O: 14] / Risk: bounties that reward volume over accuracy. Every bounty is about correctness or spacing / **S**.
9. **Key and chest economy.** Every 5-correct streak gives a key shard (3 shards = 1 key); a key opens a chest at the end of the run / Hooks: anticipation, collection, variable reward [O: 15] / Risk: variable rewards look like slot machines [E: 16]. Fix: published odds, no purchase, no dupes, pity guarantee (§5) / **S–M**.
10. **World map per course.** Regions: "Calculus Highlands" (MATH202) and "The Foundry" (MECT313). Zones = topic clusters (Limits Pass, Partial Peaks, Gradient Gorge, Lagrange Lake, Integral Depths / Flux Mines, Transformer Tower, Synchronous Citadel). Zones unlock by mastery and exam scope / Hooks: visible progress, a sense of place / Risk: none / **M** / `/api/world`.
11. **Exam countdown as world threat.** "The Rift opens in 10 days." Corruption spreads across zones as the date nears; sealing a zone (≥ Proficient) stops it there / Hooks: turns real urgency into story; urgency is an ADHD motivator [8] / Risk: anxiety. The Rift meter only ever shows what is *sealed* vs *left*, never "you are behind" / **S–M**.
12. **Ghost of past self.** During a rematch, a faded bar shows your previous attempt's damage per question. Beat it for a "Surpassed" badge / Hooks: competition with no social pressure; clear evidence of progress / Risk: none. It rewards accuracy, not speed / **S** / `ghosts[task_id]`.
13. **Mastery tiers per topic (Khan-style).** Attempted, Familiar, Proficient, Mastered, shown as a zone seal level [E-ish: 17] / Hooks: competence, completing a collection / Risk: inflated mastery. Mastered needs a correct answer in a *spaced* rematch (≥ 2 days later) / **S**.
14. **Mastery-gated unlocks.** New enemy types, perks and zones unlock at mastery milestones, never from time played / Hooks: unlocks feel earned (Hades meta-progression) [D: 5] / Risk: none / **S**.
15. **Juice pass.** 60–80 ms hit-stop, floating damage numbers, crit flash, small screen shake, HP bar that drains with a trailing ghost bar, combo counter with rising pitch, a cascade on enemy death / Hooks: game feel [D: 6, 7] / Risk: distraction. Keep it under 600 ms and add a "calm mode" / **S**.
16. **Sound and music.** WebAudio-synthesised sfx (no asset files needed); optional instrumental lo-fi or ambient loop per region that gets more intense in boss phases / Hooks: immersion / **Evidence**: music *with lyrics* hurts reading comprehension (g ≈ −0.19 overall, lyrics worst) [E: 18], so instrumental only, default low volume, off in exam mode / **S–M**.
17. **Avatar and equipment.** A small pixel/emoji avatar with slots (head, tool, cloak). Most items are cosmetic; a few give *learning-positive* perks such as "Engineer's Loupe: unit-check hint on numeric answers" or "Notebook: saves your wrong answers as flashcards" / Hooks: ownership, identity / Risk: power creep. Cap at one functional item / **M**.
18. **Bestiary lore that teaches.** Each enemy entry unlocks one "field note": a formula and a common mistake (e.g. "Saddle Wraith: D < 0, not D = 0") / Hooks: collecting / **Learning-positive**: builds a review sheet / **S**.
19. **Risk/reward nodes on the map.** Between floors: "Elite (harder, +1 key)" or "Campfire (review 3 flashcards, restore shield)" / Hooks: choice [D: 3] / Risk: skipping hard content. The elite is required on floor 4 anyway / **M**.
20. **Shield instead of hearts.** Wrong answers damage a shield that only affects that run's *rewards*. Studying is never locked [E-ish: 19, 20] / Risk: none / **S**.
21. **Session-end hook ("tomorrow's rematch").** The last screen shows which enemy returns tomorrow and its timer, plus the chest you will get from tomorrow's bounties / Hooks: a Zeigarnik-style open loop, investment [O: 21] / **S**.
22. **Weekend amulet / flexible streak.** The streak counts *study days per week* (e.g. 5 of 7) instead of consecutive days, and one freeze is earned by bounties / Hooks: streaks drive return visits [E: 22], but a broken streak demotivates [E: 23] / **S**.

---

## 4. Top 8 to build now

Ranked by hook per effort. All state goes into `data/progress.json` through `store.write_json` (atomic). IDs are short strings. Every mechanic that changes damage runs **server-side** in `encounter.py`, so the client cannot fake it.

### 4.1 Runs + perk draft (M, the backbone)
**Data** (`progress.run`, null when no run is active):
```json
{"id":"r-7f3a","zone":"gradient-gorge","course":"MATH202","floor":2,"floors":4,
 "queue":["<due_rematch_tid>","<new_tid>","<elite_tid>","<miniboss:mixed>"],
 "perks":["scholars_lens"],"offer":["glass_cannon","second_wind","chain_lightning"],
 "shield":3,"shards":1,"gold":40,"started":"2026-09-28T19:02:00","log":[{"tid":"...","stars":3,"dmg":0.86}]}
```
`progress.run_history[]` stores the summaries (the last 50 are enough for ghosts and stats).
**Perk table** (`studyquest/perks.py`, a constant dict. `mods` is merged into `enc["mods"]` when a battle starts):
| id | name | effect (mods) | gate |
|---|---|---|---|
| scholars_lens | Scholar's Lens | first hint each battle costs 0 | always |
| glass_cannon | Glass Cannon | damage ×2, hints disabled | topic accuracy ≥ 75% |
| second_wind | Second Wind | first wrong answer per battle can be retried at full damage | always |
| chain_lightning | Chain Lightning | crit needs combo 2 instead of 3 | always |
| deep_focus | Deep Focus | +50% damage while focus mode never broken this battle | always |
| proofsmith | Proofsmith | Demands-proof enemies drop 2 shards | always |
| slow_time | Chronoshard | timed enemies get +60 s | always |
| cartographer | Cartographer | a correct answer on the first try reveals the next enemy's intent/topic | always |
| gambit | Scholar's Gambit | skip the lesson card: +25% damage; lesson stays one tap away | Familiar+ |
**Endpoints:** `POST /api/run/start {zone}` → builds the queue (the first due rematch in that course, then the next unfinished task in the zone, then the elite, then the mixed mini-boss) and returns the run. `GET /api/run`. `POST /api/run/perk {id}` (must be in `offer`) → advances to the next floor. `POST /api/run/end {abandon?}` → summary. `battle/start` gains an optional `run_id`. When a battle finishes, if a run is active, it appends to `run.log` and sets `offer` (3 random perks the player doesn't already have and passes the gate for).
**Integration points:** in `encounter._resolve`, `dmg *= mods.get("dmg_mult",1)`, and the crit check uses `mods.get("crit_combo", CRIT_COMBO)`. In `encounter.hint`, the cost is 0 when `mods.first_hint_free` is set and it is the first hint. `glass_cannon` makes `/api/battle/hint` return 409.
**UI:** run bar at the top (4 floor pips, perk icons, shield, shards). The perk screen shows 3 cards that flip in one after another, each with a one-line effect and a flavour line.
**Copy:** "Floor 2 cleared. Vex tosses you three trinkets. Take one." / Glass Cannon: "Hit twice as hard. No hints. You trust yourself?"

### 4.2 Juice + sound (S, biggest feel-per-hour)
Client only (`static/fx.js`, about 150 lines). WebAudio synthesis: `hit()` is a square blip whose pitch goes up one semitone per combo step (capped at +7); `crit()` adds a noise burst plus an octave; `miss()` is a low thud; `kill()` is an arpeggio; `chest()` is a rising sweep. Visuals: CSS `@keyframes` for shake (4 px, 120 ms), a white flash overlay on crit, floating `-18` numbers (translateY −40 px, fade), and a 70 ms `setTimeout` freeze before the HP bar tweens. The HP bar has a trailing "ghost" segment that drains 300 ms later (the classic fighting-game read). `settings.fx = "full"|"calm"|"off"`; exam/boss mode forces calm. Optional music: `settings.music = "off"|"lofi"` loops a user-supplied instrumental file from `static/audio/` at volume 0.25 and ducks during the lesson card. **No lyrics** [18].

### 4.3 Enemy intents + affixes (M)
Add `affix` to each generated encounter, picked in `encounter.start` by rule, not by the AI:
- `timed` (only if topic mastery ≥ Familiar): "Charging: 120 s per question." Each question the timer runs out on gets half damage, and **nothing else is lost**.
- `armored`: only first-try answers do damage; hint damage is shown as "blocked". Used on rematches of Proficient topics.
- `demands_proof`: the final blow must be a `short` self-explanation question ("Explain in 1–2 sentences why…"), graded by the AI.
- `mimic`: 1 of the 5 problems comes from a different mastered topic (interleaving) and is shown as "?".
- `regenerating` (mini-boss only): heals 10% if you use a tier-3 hint, so the player learns to pull back before fully revealing the answer.
`encounter._view` returns `intent: {icon, text}` for the *next* question. The UI shows it as a speech bubble above the enemy, e.g. "⏳ Winding up. Next strike is timed."

### 4.4 Mentor NPC "Old Vex" (S)
`static/mentor.json`: `{event: [lines...]}` with about 8 lines per event. Events: `greet_morning`, `greet_return_after_gap`, `first_crit`, `three_misses`, `hint_used`, `zone_sealed`, `run_lost`, `boss_unlocked`, `tab_return`. Selection happens on the client; `progress.mentor_seen` stores recently used line ids so lines don't repeat within 3 days. Rate limit: at most 1 line per battle and 3 per run. `three_misses` lines always point to a concrete step, never a feeling: "Three misses. Check the sign of D before you classify. It's usually the sign." `run_lost`: "The Rift took that one. You kept the notes. They'll be sharper next time." (the Hades rule [5]). Portrait: one SVG, 4 expressions. Optional later: the AI rewrites a line using the specific wrong answer.

### 4.5 Daily bounties (S)
`progress.bounties = {"date":"2026-09-28","items":[{"id":"b1","kind":"first_try","topic":"partials","target":5,"progress":2,"reward":{"shards":2},"done":false}],"rerolls":1}`. They are generated lazily on the first `GET /api/bounties` each day from a template pool: `first_try(topic,n)`, `rematch_clear(n)`, `proof_win(1)`, `no_hint_battle(1)`, `run_clear(1)`, `seal_progress(zone)`, `early_bird` (a rematch before 12:00). At least one bounty targets the **weakest** topic (lowest mastery score). Progress updates in the same code path as XP. `POST /api/bounties/reroll {id}`. Copy: "Bounty: Partial Peaks: land 5 clean hits. Reward: 2 key shards."

### 4.6 Keys + chests (S–M)
Shards come from a 5-streak of correct answers (resets on a miss), from bounties and from Proofsmith. 3 shards = 1 key. At run end, a key opens a chest (`POST /api/chest/open`). **The loot table is public and shown on the chest screen**: 60% cosmetic (new title/theme/avatar part, **no duplicates** until the pool is empty), 30% consumable (Hint Token, Retry Token, Timer +60 s, max 3 held), 10% rare (animated theme or bestiary gold frame). A pity rule guarantees a rare within 8 chests. No currency is bought or bought with; there are no timers on chests. Animation: shake ×3 (the *number* of shakes hints at rarity, which is the honest version of "anticipation"), then a burst plus the `chest()` sfx. Data: `progress.keys`, `progress.shards`, `progress.consumables{}`, `progress.chest_pity`.

### 4.7 World map + Rift countdown (M)
`GET /api/world` returns `[{region, course, exam:{name,date,days}, zones:[{id,name,tasks:[tid],mastery:0..1,tier,state:"locked|open|sealed|corrupted"}]}]`, built from `plan.json` sessions grouped by topic (add a static `zones.json` that maps session titles to zone ids). Rules: a zone *opens* when the previous one reaches Familiar or its exam is ≤ 7 days away. It is *sealed* at ≥ 80% of tasks Proficient, one of them confirmed by a spaced rematch. Corruption = `max(0, 1 - days_left/21)` across unsealed zones, shown as a purple haze in SVG. UI: a full-screen SVG map, one region per tab, a "Start run here" button per zone, and a Rift meter at the top. Copy: "The Rift opens in 10 days (Exam I, ECB13). Sealed 2 of 6 zones. Lagrange Lake is spreading." It never says "you are behind"; it only states what is left.

### 4.8 Ghost of past self (S)
When a battle finishes, save `progress.ghosts[tid] = {"at":..., "per_q":[1,0.5,0,1,1], "stars":2, "hints":1}` (keep the best and the latest). In `battle/start`, return `ghost` if one exists. The UI shows a thin translucent HP track that drops at the ghost's pace *per question*, not per second, so it rewards accuracy rather than speed. Finishing ahead gives a "Surpassed" stamp and +1 shard. Copy: "Your ghost from Sep 24 is here. It needed 2 hints. You?"

**Build order:** 4.2 (half a day), then 4.1 + 4.4 (a day), then 4.3 + 4.5 + 4.6 (a day), then 4.7 + 4.8 (a day). Tests: extend `tests/test_core.py` for the perk mod maths, bounty generation that is deterministic per date (seed with the date), and the pity counter.

---

## 5. Guardrails (what we won't do, and why)

1. **No shame streaks.** The streak is "days per week", with earned freezes and no "you lost your streak!" screen. Broken streaks reduce motivation and self-rated commitment [E: 23]. Duolingo's own data shows that forgiving mechanics (weekend amulet) *raise* retention [E: 22].
2. **Studying is never locked.** No hearts or energy. Mistakes cost run rewards, never access. Duolingo's hearts and energy systems drew sustained complaints that they punish the mistakes learning needs [O/E: 19, 20].
3. **Randomness stays transparent, with nothing to buy.** Odds are published, there is a pity cap, no dupes, and no money or time-gated chests. Paid variable rewards are linked to problem gambling [E: 16]. Here randomness only chooses *which* cosmetic you get.
4. **Black-hat drives at low dose, only where honest.** Scarcity, loss and unpredictability (Octalysis drives 6–8) produce urgency but also anxiety [O: 24]. The only black-hat element is the real exam date, presented as story and never as guilt.
5. **No notifications that nag.** At most one opt-in local reminder per day, worded as an invitation ("Vex has a rematch ready"). No guilt copy, no "we miss you".
6. **Correctness decides progress.** XP, shards, mastery and seals come only from correct answers, spaced rematches and explanations. Nothing rewards time-in-app or clicking. Mastery needs a spaced confirmation so it can't be inflated by cramming [E: 9, 10].
7. **The game layer can't replace retrieval.** Every floor is real problems. Perks can change scaffolding, but no perk skips a problem or reveals an answer for free. Floor 1 is always what spacing says is due.
8. **Juice has a budget.** Animations stay under 600 ms, calm mode is always available, and exam and boss modes are calm by default. The mock exam must feel like the real exam.
9. **No music with lyrics** during problems [E: 18].
10. **Hyperfocus guard.** After 90 min of runs, Vex suggests stopping and banks a small "rested" bonus for next time, so stopping pays too. ADHD hyperfocus can override breaks; the game should help end sessions, not stretch them.
11. **No leaderboards against strangers.** The only rival is your past self: relatedness without social comparison.

---

## Sources

1. Sailer & Homner (2020), *The Gamification of Learning: a Meta-analysis*, Educ. Psych. Review. Cognitive g=0.49, motivational g=0.36, behavioural g=0.25. [E] https://eric.ed.gov/?id=EJ1245270 · https://www.semanticscholar.org/paper/The-Gamification-of-Learning:-a-Meta-analysis-Sailer-Homner/be6769b967370c9852210e2fb7a34e499902f814
2. Recent education gamification meta-analysis (context). [E] https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10591086/
3. Giovannetti, *Slay the Spire: Metrics Driven Design and Balance*, GDC 2019. [D] https://www.gdcvault.com/play/1025731/-Slay-the-Spire-Metrics · https://www.youtube.com/watch?v=7rqfbvnO_H0
4. Balatro design commentary (LocalThunk quotes, compulsion loop analysis). [O] https://en.wikipedia.org/wiki/Balatro · https://gmtk.substack.com/p/balatros-cursed-design-problem
5. Kasavin on Hades: death as narrative reward. [D] https://www.gamedeveloper.com/design/how-supergiant-weaves-narrative-rewards-into-i-hades-i-cycle-of-perpetual-death · GDC: https://gdcvault.com/play/1027149/Breathing-Life-into-Greek-Myth
6. Jonasson & Purho, *Juice It or Lose It*, GDC Europe 2012. [D] https://www.gdcvault.com/play/1016487/juice-it-or-lose · https://www.youtube.com/watch?v=Fy0aCDmgnxg
7. Balatro as a "compulsion loop" analysis. [O] https://errorandexp.substack.com/p/unpacking-balatros-addicting-game
8. Dodson's interest-based nervous system (Interest, Novelty, Challenge, Urgency). A clinical framework, not tested in controlled studies. [O] https://neurodivergentinsights.com/interest-based-nervous-system/ · https://www.psychologytoday.com/us/blog/empowered-with-adhd/202408/this-concept-transformed-my-life-with-adhd
9. Roediger & Karpicke (2006), *The Power of Testing Memory*. [E] http://psychnet.wustl.edu/memory/wp-content/uploads/2018/04/Roediger-Karpicke-2006_PPS.pdf
10. Spacing meta-analytic review. [E] http://www.lscp.net/persons/ramus/docs/EPR20.pdf
11. Rohrer et al., interleaved mathematics practice RCT (2019) and guide. [E] https://gwern.net/doc/psychology/spaced-repetition/2019-rohrer.pdf · http://uweb.cas.usf.edu/~drohrer/pdfs/Interleaved_Mathematics_Practice_Guide.pdf
12. Bisra et al. (2018), *Inducing Self-Explanation: a Meta-Analysis*, g=0.55. [E] https://link.springer.com/article/10.1007/s10648-018-9434-x
13. Vampire Survivors design analyses (level-up choices, banish, constant reward). [O] https://www.kokutech.com/blog/gamedev/design-patterns/power-fantasy/vampire-survivors · https://gmdq.substack.com/p/vampire-survivors-banish-mechanic
14. Third-party Duolingo gamification write-ups (leagues and XP boost figures are **unverified**). [O] https://www.strivecloud.io/blog/gamification-examples-boost-user-retention-duolingo · https://www.orizon.co/blog/duolingos-gamification-secrets
15. Eyal's Hook model and Chou's critique of it. [O] https://amplitude.com/blog/the-hook-model · https://yukaichou.com/gamification-analysis/hook-model-octalysis-habit-addiction/
16. Loot boxes and problem gambling (after Zendle & Cairns 2018); arousal from rare rewards. [E] https://pmc.ncbi.nlm.nih.gov/articles/PMC9295209/ · https://pmc.ncbi.nlm.nih.gov/articles/PMC7882574/
17. Khan Academy mastery levels and "skills to proficient" (company correlational data). [E-weak] https://support.khanacademy.org/hc/en-us/articles/5548760867853--How-do-Khan-Academy-s-Mastery-levels-work · https://blog.khanacademy.org/why-khan-academy-will-be-using-skills-to-proficient-to-measure-learning-outcomes/
18. Background music and reading: meta-analytic g≈−0.19, lyrics worst. [E] https://journalofcognition.org/articles/10.5334/joc.273 · https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11027201/
19. Duolingo energy/hearts backlash. [O] https://www.classcentral.com/report/duolingo-breaks-hearts-for-energy/ · https://medium.com/design-bootcamp/how-duolingos-new-energy-system-is-failing-its-users-16738c83117b
20. *When Gamification Spoils Your Learning* (qualitative case study of Duolingo misuse). [E-qual] https://arxiv.org/pdf/2203.16175
21. Chen, *Flow in Games* (MFA thesis): player-driven difficulty inside the flow channel. [D] https://www.jenovachen.com/flowingames/Flow_in_games_final.pdf
22. Duolingo blog: Streak Wager +14% D7 retention; Weekend Amulet +4% week-later return, −5% streak loss. [E, company A/B] https://blog.duolingo.com/how-streaks-keep-duolingo-learners-committed-to-their-language-goals/
23. Silverman & Barasch (2023), *On or Off Track: How (Broken) Streaks Affect Consumer Decisions*, JCR. [E] https://academic.oup.com/jcr/article-abstract/49/6/1095/6623414 · https://www.udel.edu/udaily/2024/march/power-of-streaks-motivation-jackie-silverman/
24. Chou, Octalysis white hat vs black hat. [O, framework] https://yukaichou.com/gamification-study/white-hat-black-hat-gamification-octalysis-framework/
25. ADHD serious games systematic review (children; context only). [E, indirect] https://games.jmir.org/2025/1/e60937
