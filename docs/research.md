# StudyQuest: research behind the design

StudyQuest is a study app for a university student with ADHD. Each design principle below is linked to the feature it justifies and to sources that were checked (authors, year, title, journal, DOI) against Crossref, Europe PMC or the publisher page in September 2026.
Most learning-science evidence comes from general student populations, not ADHD samples. Each entry says which it is.

**Strength legend**
- **Strong**: meta-analyses or large, repeated experimental findings that apply directly to the feature.
- **Moderate**: solid experiments or reviews, but indirect (lab tasks, children, non-ADHD students) or with mixed results.
- **Weak**: few studies, conflicting findings, or a large gap between the evidence and the feature.
- **Anecdotal**: mostly self-report, surveys or community practice, with little controlled evidence.

---

## 1. Short work blocks + breaks
**What the app does:** Default 10–15 min sprints (5–25 selectable), each followed by a 3–5 min break screen.

**Source(s):**
- Biwer, F., Wiradhany, W., oude Egbrink, M. G. A., & de Bruin, A. B. H. (2023). Understanding effort regulation: Comparing 'Pomodoro' breaks and self-regulated breaks. *British Journal of Educational Psychology, 93*(S2), 353–367. https://doi.org/10.1111/bjep.12593
- Göksu, Wiradhany, & de Bruin (2026). When to take a break: Comparing effects of systematic short (Pomodoro) and self-regulated breaks on subjective experience and actual learning. *Behavioral Sciences, 16*(7), 1158. https://doi.org/10.3390/bs16071158
- Huang-Pollock, C. L., Karalunas, S. L., Tam, H., & Moore, A. N. (2012). Evaluating vigilance deficits in ADHD: A meta-analysis of CPT performance. *Journal of Abnormal Psychology, 121*(2), 360–371. https://doi.org/10.1037/a0027205

**Evidence in one line:** In Biwer et al. (n=87), systematic breaks (including 24/6 min "Pomodoro" breaks) gave better mood and efficiency than self-chosen breaks. The 2026 follow-up (n=176, 12 min study/3 min break) found **no learning difference**, and students preferred self-regulated breaks, finding frequent breaks disruptive. Children with ADHD show large overall deficits on continuous performance tests (47 studies), but only small-to-moderate extra decline *over time*.

**Strength:** **Weak–Moderate.** There are only a few real-study-session experiments with general (non-ADHD) students, and their results conflict about very short blocks. The ADHD vigilance data comes from children on lab tasks and does not show that attention collapses after N minutes. "Pomodoro" itself is a popular technique, not an evidence-based protocol. **Design implication:** keep lengths selectable and let the user extend a block that is going well.

## 2. Visible time for time blindness
**What the app does:** An always-visible countdown bar during a sprint.

**Source(s):**
- Barkley, R. A. (1997). Behavioral inhibition, sustained attention, and executive functions: Constructing a unifying theory of ADHD. *Psychological Bulletin, 121*(1), 65–94. https://doi.org/10.1037/0033-2909.121.1.65
- Toplak, M. E., Dockstader, C., & Tannock, R. (2006). Temporal information processing in ADHD: Findings to date and new methods. *Journal of Neuroscience Methods, 151*(1), 15–29. https://doi.org/10.1016/j.jneumeth.2005.09.018
- Noreika, V., Falter, C. M., & Rubia, K. (2013). Timing deficits in attention-deficit/hyperactivity disorder (ADHD): Evidence from neurocognitive and neuroimaging studies. *Neuropsychologia, 51*(2), 235–266. https://doi.org/10.1016/j.neuropsychologia.2012.09.036

**Evidence in one line:** Reviews find consistent ADHD-related problems with duration discrimination, reproduction and estimation. Barkley's theory places a weak internal "sense of time" at the core of ADHD and recommends making time external.

**Strength:** **Moderate** for the timing deficit itself (ADHD-specific reviews). **Weak** for the feature: no source here tests whether a visible countdown improves studying. The bar is a reasonable way to make time external, as Barkley's theory suggests, but it is untested.

## 3. Immediate, frequent rewards
**What the app does:** XP and a sound play right after each passed check.

**Source(s):**
- Sonuga-Barke, E. J. S., Taylor, E., Sembi, S., & Smith, J. (1992). Hyperactivity and delay aversion—I. The effect of delay on choice. *Journal of Child Psychology and Psychiatry, 33*(2), 387–398. https://doi.org/10.1111/j.1469-7610.1992.tb00874.x
- Sonuga-Barke, E. J. S. (2002). Psychological heterogeneity in AD/HD—a dual pathway model of behaviour and cognition. *Behavioural Brain Research, 130*(1–2), 29–36. https://doi.org/10.1016/S0166-4328(01)00432-6
- Luman, M., Oosterlaan, J., & Sergeant, J. A. (2005). The impact of reinforcement contingencies on AD/HD: A review and theoretical appraisal. *Clinical Psychology Review, 25*(2), 183–213. https://doi.org/10.1016/j.cpr.2004.11.001

**Evidence in one line:** Hyperactive children chose small immediate rewards to cut down total waiting (delay aversion). Across 22 studies (N=1181), reinforcement improved task performance, somewhat more in ADHD, and children with ADHD preferred immediate over delayed reward.

**Strength:** **Moderate.** The findings are ADHD-specific and replicated, but mostly in children doing lab tasks, not adults studying. Luman et al. also note that ADHD groups can look *less* physiologically sensitive to reward, so frequent, clear feedback matters more than large rewards.

## 4. Retrieval practice over rereading
**What the app does:** Sessions are built around answering checks (recall), not rereading notes.

**Source(s):**
- Roediger, H. L., III, & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science, 17*(3), 249–255. https://doi.org/10.1111/j.1467-9280.2006.01693.x
- Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J., & Willingham, D. T. (2013). Improving students' learning with effective learning techniques: Promising directions from cognitive and educational psychology. *Psychological Science in the Public Interest, 14*(1), 4–58. https://doi.org/10.1177/1529100612453266

**Evidence in one line:** Testing beats restudying for delayed retention. Dunlosky et al. rate practice testing "high utility" and rereading "low utility".

**Strength:** **Strong** (large, replicated literature and a major review), but from **general populations**, not ADHD specifically.

## 5. Spaced repetition (1 / 3 / 7 days, Leitner-like)
**What the app does:** Items come back after 1, 3 and 7 days, moving up or down "boxes" depending on correctness.

**Source(s):**
- Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin, 132*(3), 354–380. https://doi.org/10.1037/0033-2909.132.3.354
- Dunlosky et al. (2013), above: distributed practice rated "high utility".

**Evidence in one line:** Spreading practice over time reliably beats massing it, and the best gap grows with how long you need to remember.

**Strength:** **Strong** for spacing in general (meta-analysis, **general populations**). The exact 1/3/7 schedule is a practical choice, not an empirically optimised one.

## 6. Interleaving
**What the app does:** Mixes problem types within a session instead of blocking them by topic.

**Source(s):**
- Rohrer, D., & Taylor, K. (2007). The shuffling of mathematics problems improves learning. *Instructional Science, 35*(6), 481–498. https://doi.org/10.1007/s11251-007-9015-8

**Evidence in one line:** Mixed (shuffled) practice felt harder and performed worse during practice, but gave much better scores on a delayed test than blocked practice.

**Strength:** **Moderate.** These are lab experiments with non-ADHD college students on maths problems. Dunlosky et al. (2013) rate interleaving only "moderate utility" because the evidence is narrower. It may frustrate at first, so the app should say why it is used.

## 7. One thing on screen
**What the app does:** Shows one question or task at a time, with no side panels or feeds.

**Source(s):**
- Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. *Cognitive Science, 12*(2), 257–285. https://doi.org/10.1207/s15516709cog1202_4

**Evidence in one line:** Working memory is limited, and processing that doesn't serve learning uses up capacity needed to learn.

**Strength:** **Moderate / indirect.** Cognitive load theory is well established (general populations), but Sweller (1988) is about problem-solving strategies, not screen layout. Applying it to "one thing on screen" for ADHD is a reasonable inference, not a tested result.

## 8. Implementation intentions
**What the app does:** Before starting, the user fills in "If [situation], then I will [action]", e.g. "If I open my phone, I tap Where was I?".

**Source(s):**
- Gollwitzer, P. M. (1999). Implementation intentions: Strong effects of simple plans. *American Psychologist, 54*(7), 493–503. https://doi.org/10.1037/0003-066X.54.7.493
- Gollwitzer, P. M., & Sheeran, P. (2006). Implementation intentions and goal achievement: A meta-analysis of effects and processes. *Advances in Experimental Social Psychology, 38*, 69–119. https://doi.org/10.1016/S0065-2601(06)38002-1
- Gawrilow, C., & Gollwitzer, P. M. (2008). Implementation intentions facilitate response inhibition in children with ADHD. *Cognitive Therapy and Research, 32*(2), 261–280. https://doi.org/10.1007/s10608-007-9150-1 (online 2007)

**Evidence in one line:** If-then plans reliably improve follow-through on goals (meta-analysis). In children with ADHD, if-then plans improved Go/NoGo inhibition to control-group levels, and worked best combined with stimulant medication.

**Strength:** **Strong** in general populations (meta-analysis). **Moderate** for ADHD: one paper with two studies, in children, on a lab inhibition task rather than studying.

## 9. Gamification that doesn't punish
**What the app does:** XP, levels and streak "freezes", with no lost progress, no red failure screens and no guilt messages after a missed day.

**Source(s):**
- Sailer, M., & Homner, L. (2020). The gamification of learning: A meta-analysis. *Educational Psychology Review, 32*(1), 77–112. https://doi.org/10.1007/s10648-019-09498-w (online 2019)

**Evidence in one line:** Gamification has small positive effects on cognitive (g = 0.49), motivational (g = 0.36) and behavioural (g = 0.25) learning outcomes. Only the cognitive effect held up in the most rigorous studies.

**Strength:** **Moderate** for gamification in general (meta-analysis, **general populations**, effects vary). The "non-punishing" part (no loss or shame mechanics) is a design choice based on principles 3 and 10, **not directly tested** in the cited source.

## 10. Easy re-entry after distraction
**What the app does:** A "Where was I?" button shows the last task plus a 1-line recap.

**Source(s):**
- Altmann, E. M., & Trafton, J. G. (2002). Memory for goals: An activation-based model. *Cognitive Science, 26*(1), 39–83. https://doi.org/10.1207/s15516709cog2601_2
- Monk, C. A., Trafton, J. G., & Boehm-Davis, D. A. (2008). The effect of interruption duration and demand on resuming suspended goals. *Journal of Experimental Psychology: Applied, 14*(4), 299–313. https://doi.org/10.1037/a0014402
- Mark, G., Gudith, D., & Klocke, U. (2008). The cost of interrupted work: More speed and stress. *Proceedings of CHI 2008*, 107–110. https://doi.org/10.1145/1357054.1357072

**Evidence in one line:** Suspended goals fade from memory, and the model predicts that cues help people resume. Longer and more demanding interruptions lengthened resumption time. Interrupted workers kept up quality by working faster, at the cost of more stress and frustration.

**Strength:** **Moderate.** These are solid lab/HCI studies and a cognitive model, all in **non-ADHD adults**. A visible cue of the last task follows directly from the memory-for-goals model, but StudyQuest's button itself is untested.

---

## Not implemented: body doubling
**What the app does:** Nothing. StudyQuest does **not** implement body doubling (working alongside another person, live or virtual).

**Source(s):**
- Eagle, T., Baltaxe-Admony, L. B., & Ringland, K. E. (2023). Proposing body doubling as a continuum of space/time and mutuality: An investigation with neurodivergent participants. *ASSETS '23.* https://doi.org/10.1145/3597638.3614486
- Eagle, T., Baltaxe-Admony, L. B., & Ringland, K. E. (2024). "It was something I naturally found worked and heard about later": An investigation of body doubling with neurodivergent participants. *ACM Transactions on Accessible Computing, 17*(3). https://doi.org/10.1145/3689648

**Evidence in one line:** A survey of about 220 mostly neurodivergent people describes how and why they body double and proposes a model of it. There are no controlled outcome trials.

**Strength:** **Anecdotal.** The evidence is self-report and descriptive only. There is no controlled evidence that body doubling improves study outcomes in ADHD.

---

## Verification notes
- **All DOIs above were resolved** via the Crossref API. Titles, authors, journals, volumes and pages match the registry. Abstract-level claims were checked on Europe PMC or publisher/ACM pages, except Gollwitzer (1999), Gollwitzer & Sheeran (2006), Sweller (1988) and Rohrer & Taylor (2007). Their one-line summaries reflect the well-known findings but their abstracts were **not re-read** this session.
- **Corrections to the brief:**
  - The Biwer et al. 2023 BJEP paper is titled "Understanding effort regulation: Comparing 'Pomodoro' breaks and self-regulated breaks". No paper titled "Systematic breaks" was found. A 2026 follow-up (Göksu et al., *Behavioral Sciences*) found **no learning benefit** of 12/3 min systematic breaks, which weakens principle 1.
  - Toplak, Dockstader & Tannock (2006) is in the *Journal of Neuroscience Methods* (151:15–29).
  - The Sonuga-Barke 1992 paper is "Hyperactivity and delay aversion—I", *JCPP* 33(2), DOI ...tb00874.x (with Taylor, Sembi, Smith).
  - Gawrilow & Gollwitzer is dated 2008 (vol. 32) but was published online in 2007, so Crossref lists 2007.
  - Sailer & Homner is dated 2020 (vol. 32) but was published online in 2019.
- **Not verified / not used:** The effect size of the Gollwitzer & Sheeran (2006) meta-analysis is not quoted because it was not re-checked. No source was found that tests a visible countdown bar, "one item on screen", non-punishing gamification or a resume button with ADHD students specifically. Those links are inferences, labelled as such above.
- **Pomodoro:** The fixed 25/5 Pomodoro Technique is a popular productivity method. Apart from the break studies above (general students, mixed results), no controlled evidence for it was found, and none in ADHD.
- **Body doubling:** Only descriptive/survey HCI work was found (Eagle et al. 2023, 2024). A 2025 EEG pilot (Schuenke et al., ASSETS '25, doi:10.1145/3663547.3759743) exists but was not reviewed and is not relied on.

---

## Part 2: Making it a game (not a timer)

Part 1 justified *when* and *how long* to study. Part 2 covers what makes the session itself enjoyable: solving calculus and electrical-machines problems as "battles". Sources were checked against Crossref (and abstracts on OpenAlex, Semantic Scholar, Europe PMC or ERIC) in September 2026. Same strength legend as above. Unless stated, evidence is from **general (non-ADHD) populations**.

### 11. Solve inside the app, with instant feedback per answer
**What the app does:** The core loop is answer → graded at once → short explanation, not "read a chapter, then take a quiz".

**Source(s):**
- Hattie, J., & Timperley, H. (2007). The power of feedback. *Review of Educational Research, 77*(1), 81–112. https://doi.org/10.3102/003465430298487
- Shute, V. J. (2008). Focus on formative feedback. *Review of Educational Research, 78*(1), 153–189. https://doi.org/10.3102/0034654307313795
- Van der Kleij, F. M., Feskens, R. C. W., & Eggen, T. J. H. M. (2015). Effects of feedback in a computer-based learning environment on students' learning outcomes: A meta-analysis. *Review of Educational Research, 85*(4), 475–511. https://doi.org/10.3102/0034654314564881
- Kluger, A. N., & DeNisi, A. (1996). The effects of feedback interventions on performance: A historical review, a meta-analysis, and a preliminary feedback intervention theory. *Psychological Bulletin, 119*(2), 254–284. https://doi.org/10.1037/0033-2909.119.2.254

**Evidence in one line:** In computer-based settings (40 studies), elaborated feedback (an explanation) beat right/wrong only (ES 0.49 vs 0.05) and was larger in maths; delayed timing *lowered* effects overall. Kluger & DeNisi (607 effects) found feedback helps on average (d = 0.41) but over a third of feedback interventions made performance *worse*, especially when feedback pulls attention toward the self rather than the task. Shute recommends feedback that is non-evaluative, specific and timely.

**Strength:** **Strong** that task-focused, elaborated feedback helps (meta-analyses, general populations). **Moderate** on timing: Van der Kleij found immediate feedback better for lower-order learning but the timing × level interaction was not significant. Retrieval practice (Part 1, §4) already favours answering over rereading.

### 12. "Battle" framing: enemies, HP bars, floors
**What the app does:** Each task is an enemy with an HP bar; correct answers deal damage, streaks give combos/critical hits, a session is a dungeon floor.

**Source(s):**
- Sailer & Homner (2020), Part 1 §9: https://doi.org/10.1007/s10648-019-09498-w
- Bedwell, W. L., Pavlas, D., Heyne, K., Lazzara, E. H., & Salas, E. (2012). Toward a taxonomy linking game attributes to learning. *Simulation & Gaming, 43*(6), 729–760. https://doi.org/10.1177/1046878112439444
- Landers, R. N. (2014). Developing a theory of gamified learning: Linking serious games and gamification of learning. *Simulation & Gaming, 45*(6), 752–768. https://doi.org/10.1177/1046878114563660
- Armstrong, M. B., & Landers, R. N. (2017). An evaluation of gamified training: Using narrative to improve reactions and learning. *Simulation & Gaming, 48*(4), 513–538. https://doi.org/10.1177/1046878117703749

**Evidence in one line:** In Sailer & Homner, including game fiction was a significant moderator, making gamification more effective for *behavioural* outcomes. Landers' theory says game elements work mainly by changing learning behaviour (e.g. time on task), not by teaching directly. Bedwell et al. give the attribute taxonomy ("game fiction", "conflict/challenge", "assessment") that Landers builds on. But Armstrong & Landers (n=273) found narrative raised satisfaction (d = 0.65) with no gain in declarative knowledge and *lower* procedural knowledge (d = −0.40).

**Strength:** **Moderate** for fiction raising engagement/behaviour; **weak or negative** for fiction improving learning by itself. **Design implication:** the fiction must be a thin skin over the maths (damage = correct steps), never extra reading or text that competes with the problem.

### 13. Flow and challenge–skill balance (adaptive difficulty)
**What the app does:** Picks the next enemy so the success rate stays roughly in a "hard but winnable" band; tougher enemies (bosses) appear as mastery grows.

**Source(s):**
- Csikszentmihalyi, M. (1990). *Flow: The psychology of optimal experience.* Harper & Row. (Book; no DOI.)
- Hamari, J., Shernoff, D. J., Rowe, E., Coller, B., Asbell-Clarke, J., & Edwards, T. (2016). Challenging games help students learn: An empirical study on engagement, flow and immersion in game-based learning. *Computers in Human Behavior, 54*, 170–179. https://doi.org/10.1016/j.chb.2015.07.045
- Sampayo-Vargas, S., Cope, C. J., He, Z., & Byrne, G. J. (2013). The effectiveness of adaptive difficulty adjustments on students' motivation and learning in an educational computer game. *Computers & Education, 69*, 452–462. https://doi.org/10.1016/j.compedu.2013.07.004

**Evidence in one line:** Flow theory holds that absorption happens when challenge matches skill. In a survey of 173 players of two learning games, challenge predicted learning directly and via engagement; immersion did not. In Sampayo-Vargas et al., an adaptive-difficulty game gave higher learning than non-adaptive activities, with **no difference in motivation**.

**Strength:** **Moderate** for adaptivity helping learning (one experiment; ITS evidence in §17 also supports it). **Weak** for adaptivity raising motivation (the one experiment found none). Hamari et al. is correlational survey data; how "learning" was measured was not confirmed this session. General populations.

### 14. Self-determination theory: competence, autonomy, relatedness — and reward risks
**What the app does:** Gives visible competence (stars, cleared floors), choice (which floor, which enemy, when to take hints), and keeps rewards informational ("you mastered chain rule") rather than controlling ("do 10 more or lose your streak").

**Source(s):**
- Ryan, R. M., Rigby, C. S., & Przybylski, A. (2006). The motivational pull of video games: A self-determination theory approach. *Motivation and Emotion, 30*(4), 344–360. https://doi.org/10.1007/s11031-006-9051-8
- Deci, E. L., Koestner, R., & Ryan, R. M. (1999). A meta-analytic review of experiments examining the effects of extrinsic rewards on intrinsic motivation. *Psychological Bulletin, 125*(6), 627–668. https://doi.org/10.1037/0033-2909.125.6.627
- Mekler, E. D., Brühlmann, F., Tuch, A. N., & Opwis, K. (2017). Towards understanding the effects of individual gamification elements on intrinsic motivation and performance. *Computers in Human Behavior, 71*, 525–534. https://doi.org/10.1016/j.chb.2015.08.048
- Hanus, M. D., & Fox, J. (2015). Assessing the effects of gamification in the classroom: A longitudinal study on intrinsic motivation, social comparison, satisfaction, effort, and academic performance. *Computers & Education, 80*, 152–161. https://doi.org/10.1016/j.compedu.2014.08.019

**Evidence in one line:** Across four studies, perceived autonomy, competence and relatedness each predicted game enjoyment and wanting to keep playing. In 128 experiments, expected tangible rewards undermined free-choice intrinsic motivation (performance-contingent d = −0.28), while positive feedback *enhanced* it (d = 0.33). Points/levels/leaderboards raised quantity of work but acted as extrinsic incentives (Mekler et al.), and a semester-long badge/leaderboard course showed falling motivation and satisfaction versus a plain course (Hanus & Fox).

**Strength:** **Strong** for "positive informational feedback helps, expected contingent rewards can undermine" (meta-analysis, mostly children and college students, not ADHD). **Moderate** for SDT needs predicting game enjoyment (survey studies). Relatedness is weakly served by a solo app; no social features are planned.

### 15. Variable rewards: random cosmetic loot after a win
**What the app does:** After a cleared enemy, a random cosmetic drop (skin, title, colour). No money, no purchase, no gameplay advantage, and nothing lost by skipping it.

**Source(s):**
- Howard-Jones, P. A., & Demetriou, S. (2009). Uncertainty and engagement with learning games. *Instructional Science, 37*(6), 519–536. https://doi.org/10.1007/s11251-008-9073-6
- Ozcelik, E., Cagiltay, N. E., & Ozcelik, N. S. (2013). The effect of uncertainty on learning in game-like environments. *Computers & Education, 67*, 12–20. https://doi.org/10.1016/j.compedu.2013.02.009
- Zendle, D., & Cairns, P. (2018). Video game loot boxes are linked to problem gambling: Results of a large-scale survey. *PLOS ONE, 13*(11), e0206767. https://doi.org/10.1371/journal.pone.0206767

**Evidence in one line:** Three studies found chance elements in a science quiz game changed engagement and the talk around learning. In 140 engineering undergraduates, uncertain point rewards improved learning and related positively to motivation. Separately, in 7,422 gamers, spending on paid loot boxes was linked to problem-gambling severity (η² = 0.054), more than other in-game purchases.

**Strength:** **Weak.** The two learning studies used uncertain *points tied to answers*, not cosmetic drops, and are small. The loot-box link is correlational and about *paid* boxes. People with ADHD may be more drawn to reward uncertainty (Part 1 §3; Bioulac et al. §19), which is a reason to keep drops cosmetic, free and infrequent. **Ethical note:** never sell drops, never show near-misses, never make loot the reason to keep studying.

### 16. Mastery stars (1–3) and visible progress bars
**What the app does:** Each task earns 1–3 stars (accuracy, few hints); floor and topic progress bars fill as tasks are mastered.

**Source(s):**
- Kivetz, R., Urminsky, O., & Zheng, Y. (2006). The goal-gradient hypothesis resurrected: Purchase acceleration, illusionary goal progress, and customer retention. *Journal of Marketing Research, 43*(1), 39–58. https://doi.org/10.1509/jmkr.43.1.39
- Mekler et al. (2017), §14.

**Evidence in one line:** People accelerated effort as they neared a reward (café loyalty cards; a song-rating site), and even illusory head starts (12-stamp card with 2 free stamps) sped completion.

**Strength:** **Weak–Moderate** for this app. The goal-gradient effect is solid in consumer field data, but it is **not a learning study** and not ADHD. Stars tied to mastery are informational feedback (§14), which is the safer kind; stars that reward speed or volume risk the quantity-over-quality effect Mekler et al. found. Short bars (one floor) will show the gradient more often than long ones (whole course).

### 17. Tiered hints (nudge → step → worked solution) and worked examples
**What the app does:** Three hint levels; the last one shows a full worked solution, then a similar problem to try. Using hints costs a star, never HP or progress.

**Source(s):**
- Sweller, J., & Cooper, G. A. (1985). The use of worked examples as a substitute for problem solving in learning algebra. *Cognition and Instruction, 2*(1), 59–89. https://doi.org/10.1207/s1532690xci0201_3
- Atkinson, R. K., Derry, S. J., Renkl, A., & Wortham, D. (2000). Learning from examples: Instructional principles from the worked examples research. *Review of Educational Research, 70*(2), 181–214. https://doi.org/10.3102/00346543070002181
- Renkl, A., & Atkinson, R. K. (2003). Structuring the transition from example study to problem solving in cognitive skill acquisition: A cognitive load perspective. *Educational Psychologist, 38*(1), 15–22. https://doi.org/10.1207/s15326985ep3801_3
- Kalyuga, S., Ayres, P., Chandler, P., & Sweller, J. (2003). The expertise reversal effect. *Educational Psychologist, 38*(1), 23–31. https://doi.org/10.1207/s15326985ep3801_4
- Koedinger, K. R., & Aleven, V. (2007). Exploring the assistance dilemma in experiments with cognitive tutors. *Educational Psychology Review, 19*(3), 239–264. https://doi.org/10.1007/s10648-007-9049-0
- Aleven, V., & Koedinger, K. R. (2000). Limitations of student control: Do students know when they need help? *ITS 2000, LNCS 1839*, 292–303. https://doi.org/10.1007/3-540-45108-0_33
- VanLehn, K. (2011). The relative effectiveness of human tutoring, intelligent tutoring systems, and other tutoring systems. *Educational Psychologist, 46*(4), 197–221. https://doi.org/10.1080/00461520.2011.611369
- Kulik, J. A., & Fletcher, J. D. (2016). Effectiveness of intelligent tutoring systems: A meta-analytic review. *Review of Educational Research, 86*(1), 42–78. https://doi.org/10.3102/0034654315581420

**Evidence in one line:** Studying worked examples beats unaided problem solving early in learning (algebra); fading example steps into practice eases the move to solving alone; the benefit reverses as expertise grows. Step-based tutors reached d = 0.76, close to human tutoring (0.79); 50 ITS evaluations gave a median +0.66 SD (smaller on standardised tests). The "assistance dilemma" is when to give vs withhold help, and students often do not seek help well on their own.

**Strength:** **Strong** for worked examples and step-level tutoring (reviews and meta-analyses, general populations, much of it maths). **Moderate** for the specific three-tier ladder: it follows the tutoring literature but this exact ladder is untested. Aleven & Koedinger suggest nudging help use (e.g. offer a hint after two wrong tries) rather than leaving it fully to the student. Sweller & Cooper and Kalyuga et al. abstracts were not re-read this session.

### 18. Staying inside one page: focus mode and tab-leave detection
**What the app does:** Optional fullscreen focus mode. If the tab is hidden (Page Visibility API), the app pauses the enemy, shows a "welcome back" recap on return, never penalises, and awards a positive badge for a floor with zero tab switches.

**Source(s):**
- Leroy, S. (2009). Why is it so hard to do my work? The challenge of attention residue when switching between work tasks. *Organizational Behavior and Human Decision Processes, 109*(2), 168–181. https://doi.org/10.1016/j.obhdp.2009.04.002
- Monsell, S. (2003). Task switching. *Trends in Cognitive Sciences, 7*(3), 134–140. https://doi.org/10.1016/S1364-6613(03)00028-7
- Mark, G., Czerwinski, M., & Iqbal, S. T. (2018). Effects of individual differences in blocking workplace distractions. *Proceedings of CHI 2018*, 1–12. https://doi.org/10.1145/3173574.3173666
- Reid, R., Trout, A. L., & Schartz, M. (2005). Self-regulation interventions for children with attention deficit/hyperactivity disorder. *Exceptional Children, 71*(4). ERIC EJ697216: https://eric.ed.gov/?id=EJ697216
- Part 1 §10 (Altmann & Trafton 2002; Monk et al. 2008) for resumption cues.

**Evidence in one line:** Leaving a task unfinished leaves "attention residue" that hurts the next task; switching tasks carries reliable time and error costs. Blocking online distractions for a week raised self-rated focus and productivity in 32 information workers, most for those with lower self-control of work. A meta-analysis of self-monitoring and related self-regulation interventions in children with ADHD found combined effects above 1.0 for on-task behaviour and academic accuracy/productivity.

**Strength:** **Moderate** for switch costs and attention residue (lab studies, non-ADHD adults). **Weak** for blockers (one small exploratory field study, self-report, non-ADHD). **Moderate** for self-monitoring in ADHD, but in **children**, in classrooms, and not via an app. The tab-leave badge is a self-monitoring cue; making it punitive would contradict §14, so it stays positive-only.

### 19. ADHD and video games
**What the app does:** Relies on game-like immediacy (instant hits, short fights) to hold attention, without claiming to treat ADHD.

**Source(s):**
- Kollins, S. H., DeLoss, D. J., Cañadas, E., Lutz, J., Findling, R. L., Keefe, R. S. E., et al. (2020). A novel digital intervention for actively reducing severity of paediatric ADHD (STARS-ADHD): A randomised controlled trial. *The Lancet Digital Health, 2*(4), e168–e178. https://doi.org/10.1016/S2589-7500(20)30017-0
- US FDA De Novo decision DEN200026 (EndeavorRx), 2020. https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN200026.pdf
- Peñuelas-Calvo, I., Jiang-Lin, L. K., Girela-Serrano, B., et al. (2022). Video games for the assessment and treatment of attention-deficit/hyperactivity disorder: A systematic review. *European Child & Adolescent Psychiatry, 31*(1), 5–20. https://doi.org/10.1007/s00787-020-01557-w
- Bioulac, S., Arfi, L., & Bouvard, M. (2008). Attention deficit/hyperactivity disorder and video games: A comparative study of hyperactive and control children. *European Psychiatry, 23*(2), 134–141. https://doi.org/10.1016/j.eurpsy.2007.11.002
- Dovis, S., Van der Oord, S., Wiers, R. W., & Prins, P. J. M. (2015). Improving executive functioning in children with ADHD: Training multiple executive functions within the context of a computer game. *PLOS ONE, 10*(4), e0121651. https://doi.org/10.1371/journal.pone.0121651
- Part 1 §3 (Luman et al. 2005; Sonuga-Barke) for reward sensitivity and delay aversion.

**Evidence in one line:** In 348 children aged 8–12, the AKL-T01 game (later EndeavorRx, the first FDA-authorised game-based treatment) improved an objective attention score more than a control game (median change 0.88, p = 0.006), but parent/clinician-rated symptoms improved in both groups without a significant difference. A gamified training kept compliance high (97%) in 89 children with ADHD, with gains mostly on trained tasks. A systematic review sees gamification as a key mechanism in ADHD game tools. Children with ADHD played as much as controls but a subgroup showed more problematic play.

**Strength:** **Moderate** that immediate, game-style feedback can hold engagement in ADHD (children, reward-sensitivity literature). **Weak** for gamified *academic learning* in ADHD: no controlled trial in university students with ADHD learning maths or engineering was found. EndeavorRx trains attention; it does not teach content, was industry-funded, and was tested in children. **Caution:** the same pull can become overuse, so floors end naturally (Part 1 §1 breaks).

### 20. "Juice": animations, sound, damage numbers
**What the app does:** Short hit animations, a damage number, a sound on a correct answer, screen shake on a critical; all can be turned down or off.

**Source(s):**
- Hicks, K., Gerling, K., Dickinson, P., & Vanden Abeele, V. (2019). Juicy game design: Understanding the impact of visual embellishments on player experience. *Proceedings of CHI PLAY '19*, 185–197. https://doi.org/10.1145/3311350.3347171

**Evidence in one line:** Across two studies (n=40, n=32), visual embellishments raised visual appeal in all games tested but affected competence and other experience measures only in some circumstances; no learning outcome was measured.

**Strength:** **Weak.** "Juice" is widely recommended by game designers, but controlled evidence is thin and says nothing about learning. Treat it as polish that must not delay the next problem or add clutter (Part 1 §7).

---

### Design rules for Part 2
1. **Feedback within about 1 s, task-focused and elaborated.** Grade locally (symbolic/numeric check in the page) whenever possible; show *why* after wrong answers; never comment on the person (§11).
2. **Fiction is a skin, not content.** Damage, HP and combos map one-to-one to correct steps; no story text between problems (§12).
3. **Keep success in a "hard but winnable" band** with adaptive enemy choice, and track learning, not just engagement, since adaptivity helped learning more than motivation (§13, §17).
4. **Rewards informational, not controlling.** Stars say what was mastered; nothing is lost for stopping, skipping or using hints; no streak threats (§14, Part 1 §9).
5. **Loot is cosmetic, free, unexpected and never sold.** No near-miss animations, no currency, no gating of content behind drops (§15).
6. **Help on a ladder, offered not forced.** Nudge → step → worked solution, then a matched problem; offer the next hint after repeated errors; fade worked steps as stars accumulate (§17).
7. **Notice leaving, never punish it.** Pause and recap on return; reward zero-switch floors positively; fullscreen stays optional (§18, Part 1 §10).
8. **Juice is short and optional.** Animations under the feedback budget, a mute/reduce-motion toggle, and no effect that blocks the next input (§20).

### Verification notes (Part 2)
- **Crossref-resolved:** every DOI in §11–§20 was matched on Crossref (authors, year, title, venue, volume, pages). Abstract-level claims were checked on OpenAlex, Semantic Scholar, Europe PMC or ERIC. Abstracts **not re-read** this session: Sweller & Cooper (1985), Kalyuga et al. (2003), Monsell (2003), Bedwell et al. (only the abstract, not the empirical card-sort details), Koedinger & Aleven (2007) and Peñuelas-Calvo et al. (2022) (only short summaries seen). Their lines state well-known or summary-level findings only.
- **Corrections to the brief:**
  - Hicks et al. (2019) "Juicy game design" is in **CHI PLAY '19** (Annual Symposium on Computer-Human Interaction in Play), not CHI, and the authors are Hicks, **Gerling, Dickinson** & Vanden Abeele.
  - The Lancet Digital Health DOI is registered with an upper-case "S2589-7500(20)30017-0".
- **Reid, Trout & Schartz (2005):** confirmed via the ERIC record EJ697216 (authors, title, journal, year, abstract). No DOI was found on Crossref, so the ERIC URL is given; vol. 71(4) comes from secondary listings and page numbers are not quoted.
- **Kollins et al. (2020) secondary outcomes:** "improved in both groups, no significant between-group difference" for ADHD-RS/IRS comes from the follow-up paper (Kollins et al. 2021, *npj Digital Medicine*, doi:10.1038/s41746-021-00429-0) summarising STARS-ADHD, not from the 2020 abstract itself.
- **Hamari et al. (2016):** learning was measured through the player survey; whether it was self-reported or tested was not confirmed, so it is described as correlational.
- **Deci et al. (1999):** the abstract lists *expected* rewards as undermining; the claim that surprise rewards are safer is inferred from that, not quoted from the paper.
- **Not found:** any controlled study of battle framing, loot drops, star ratings, tab-leave detection or "juice" with ADHD students, or of gamified maths/engineering learning in university students with ADHD. Those links are inferences, labelled as such.
- **Csikszentmihalyi (1990):** a book with no DOI; cited for the theory only.
