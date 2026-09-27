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
