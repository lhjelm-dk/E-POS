# LinkedIn article — master draft (v2)

> **Assembly notes (not part of the article):**
> - Paste section by section into LinkedIn's article editor; insert each image at its `[IMAGE: …]` slot and copy the caption text under it.
> - Images live in `docs/img/`, numbered in article order (01–23). All app screenshots use a synthetic prospect and placeholder calibration. Nothing proprietary.
> - ⚠️ **Neither link may go live until the git-history scrub is done** (old commits contain reference PDFs and the real calibration; Streamlit Cloud deploys from the repo).
> - Open decisions, marked inline: [NAMING] the vendor DHI database, [REF] the exact Roden citation.

---

[IMAGE: 01_pos_monster.png — Every prospect must get past the four-headed POS monster guarding the portfolio gate. (Image: AI-generated, in case the geology didn't give it away.)]

## Prospect risking is easy!

To find the Probability Of Success (POS), you just estimate the probability that there is a source rock, a trap, a reservoir and a top seal. You multiply the four numbers together, and if the result comes out below 25%, you go back and revisit your numbers so that your managers don't get too concerned. You might be tempted to assign probability to timing considerations too, like "what about the risk that the trap formed *after* the hydrocarbon migration?", but as you know: multiplying in more small numbers makes the end result way smaller, and no one will drill a 6% prospect. So maybe just keep it at four risk elements!

That is roughly how risking was introduced to me, and during my career I have had the slow realisation that assigning a POS to a prospect is perhaps a bit more complicated.

I have been particularly interested in the "math" of prospect POS: play analysis, well POS vs Pg, DHI modification, multi-segment dependency, and how we end up with numbers that are defendable and will, in the end, actually match the success rate of the portfolio. There are of course other fascinating sides to risking, like how group knowledge improves assessments, biases, political pressure, the peer-review process, evaluation consistency, look-back analysis and the psychology of the whole thing. But my itch has always been the mechanics. How do you actually derive a probability value? How do you communicate the uncertainty, and quantify the fuzziness, the incomplete data, the assumptions and the unknowns? And how do you incorporate auxiliary knowledge from seismic DHIs, seeps or EM responses?

Eventually these thoughts turned into a side project, built with Python and a lot of AI discussions to capture ideas and test new assessment methods. The current result is **E-POS**, an open tool for evidence-supported prospect probability assessment. This article is about how I currently view probability assessment, what I built to cope with it, and hopefully you will find it interesting or educational. Or, more likely, conclude that I have over-engineered a simple exploration task.

And yes, the name. An *epos* is a Greek heroic poem. Leaving the comfort of certainty to face complex data, financial stakes and the steady pain of failed predictions, while confronting my own biases along the way, felt like a journey worthy of the pun.

---

## "OK, so assigning a prospect POS might be a bit more complicated"

**1. We are biased, and we know it.** Bond and co-workers have documented how anchoring, availability and motivated reasoning shape interpretation and risk assessment, and why independent assurance processes exist (Bond et al., 2022). The uncomfortable part is that knowing about bias does not remove it. Structure and documentation help more than good intentions: if the evidence behind a number is written down, someone can at least challenge it.

**2. You rarely live long enough to be calibrated.** The honest test of a risking process is hindsight: did the prospects you called 20% come in about one time in five? That requires a large drilled portfolio, a stable method, and assessors who stay put. Most of us learn on moving targets, with portfolios too small for the statistics to bite. Rose built a whole discipline around this problem, and the large companies run assurance teams to enforce consistency; it remains the hardest problem in risking.

**3. The arithmetic stops being innocent the moment risk elements are dependent.** Multiplying probabilities assumes independence. But is reservoir presence independent of seal presence in the same depositional system? Is the migration pathway independent of our reservoir? If you risk "migration" in one factor and "charge timing" in another, have you counted the same uncertainty twice? Double-counting dependent evidence systematically *understates* POS. The worst part is that we often cannot say, geologically, which elements are dependent, and it probably varies from basin to basin. Which would suggest different risk models for different basins, except nobody wants that in the company procedures.

**4. Putting a number on deep uncertainty is its own problem.** How do you know that 40% rather than 50% of reservoir units in this setting, at these depths, will have sufficient permeability? Often you don't. A single number like 0.4 silently claims more knowledge than you have. There is a real difference between "the evidence is split" and "we have no evidence", and classical probability has no way to write that difference down. And a related practical question follows: which risk element would actually respond to mitigation effort, and which would not?

**5. And then your friendly geophysicist leans over.** "It looks OK on the AVO, by the way." How much should that move your number? Five points? Fifteen? Direct fluid indicators carry real information, but folding them in by gut feel is how the same anomaly gets counted twice, once in the reservoir factor and once as a bonus on top.

Each of these challenges has a literature behind it. What I wanted was a place where they meet a working tool.

---

## So I built one

E-POS (Evidence-supported Probability of Success) is a Streamlit app I built to make assessments traceable, and it grew into a small laboratory for the methods themselves. The design goals, mapped against the problems above:

**Start from a complete checklist, not a blank page.** The default risk model is a structured checklist of the petroleum-system conditions that must all be in place for an accumulation: 26 risk elements organised under the four classic pillars (Charge, Closure, Reservoir, Retention). Each pillar is assessed twice, mirrored: once at **play level** (does the system work regionally?) and once at **prospect level**, conditional on the play (does it work right here?). The checklist forces the awkward questions on the table before the multiplication starts.

[IMAGE: 03_risk_model_hierarchy.png — The combination hierarchy: P(G) = P(Play) × P(Conditional Prospect), four pillars each, with grouped sub-elements below. Twenty-six chances to ask "what exactly do we know about this?"]

[IMAGE: 04_risk_table_checklist.png — The working checklist: every sub-element with its success criterion, its evidence flag and its combination operator. No hidden numbers.]

**And the risk model is yours to change.** The 26 elements are a starting point, not a doctrine. You can build your own model, regroup elements, and choose *how* sub-elements combine: weakest-link (min), product, mean, or sufficiency-weighted. That choice is exactly the dependency question from challenge 3, made explicit and auditable instead of buried in a spreadsheet formula.

[IMAGE: 06_operator_settings.png — Combination operators per pillar: min/min for dependent elements, product for independent ones, and the difference is visible in the result. The dependency assumption becomes a setting you can defend, not a habit.]

**Document evidence, not just numbers.** The core method is Evidence Support Logic (ESL), built on David Blockley's interval probability and the "Italian Flag": every risk element carries evidence *for* (green), evidence *against* (red), and an explicit *don't know* (white). A probability of 0.40 backed by strong conflicting evidence and a 0.40 that is mostly white are different geological situations, and the tool keeps them distinguishable. In practice something interesting happens here: being asked separately "what supports this?" and "what contradicts this?" forces a different discussion than agreeing on a single number. People who would happily settle on "70%" turn out to disagree, productively, about *why*.

[IMAGE: 05_element_assessment.png — Assessing one element: evidence for, evidence against, and the unknown in between, with the per-element chance-adequacy plot below. The argument this forces is the actual product.]

[IMAGE: 07_overview_flags.png — Every element as an Italian Flag: green for, red against, white for what we genuinely don't know. The point estimate and the defensible interval travel together.]

**Let two methods disagree, visibly.** The app computes the classic multiplicative POS *and* the ESL roll-up from the same evidence, side by side. They differ for structural reasons, and the gap is a data-quality signal: a large spread usually means conflicting or thin evidence somewhere that the multiplication quietly absorbed.

[IMAGE: 08_esl_vs_classic.png — Two methods, one set of evidence. When they diverge, that is the assessment telling you where to look.]

**Diagnose, don't just compute.** Which elements actually drive the result? A sensitivity tornado ranks every sub-element by its potential impact on the headline POS, which is also a first answer to the mitigation question: effort spent on the top bars buys real probability, effort on the bottom bars buys tidier paperwork. An uncertainty index tracks how robust the result is to your stance on the unknowns.

[IMAGE: 09_tornado.png — The tornado at sub-element level: migration questions dominate this prospect. Now we know where the next survey budget should go.]

[IMAGE: 10_uncertainty_index.png — The uncertainty index and its stance trajectory: how the headline P(G) and the uncertainty co-vary as you sweep from pessimistic to optimistic treatment of the unknowns. The defensible range is the honest answer.]

**A different take on the chance-adequacy matrix.** The classic chance-vs-adequacy plot is an industry workhorse, and it earned that status: it shows in one glance which assessments are confident and which are guesses. It also has well-known conceptual wrinkles (its "forbidden" upper-centre region really only applies to a binary state of nature, not to a probability). E-POS keeps everything that works, plots every element by chance vs evidential *commitment*, and treats the old no-go region as a labelled historical reference rather than a rule. The confident-but-middling elements are not forbidden; they are usually carrying conflicting evidence, and conflicting evidence is geologically significant. Find them, discuss them, document them.

[IMAGE: 11_cam.png — Every risk element in chance vs commitment space. The interesting ones sit confident-but-middling: that is usually conflict, and conflict is a finding, not an error.]

**Open the geophysics black box.** The DFI/DHI update is a Bayesian conditioning: the seismic evidence enters as a likelihood ratio R, fully visible, with the success and failure populations drawn on screen. You can see exactly why the number moved, and by how much, instead of nodding at a percentage that fell out of a workflow. Honesty requires a caveat here: defining DHI *quality* is a discipline of its own, and I have no database to quantify the likelihood of fluid cases from a geophysical response. So the tool offers a conceptual R tool where you define the density functions for the fluid cases yourself, and I have tried to reverse-engineer learnings from recently published DHI statistics (Monigle et al., 2025) and from publicly available snippets of a vendor DHI-consortium database [NAMING: keep generic, or name it?] to demonstrate possible approaches. For this to carry real weight in a drilling decision you would need solid in-house statistics, or the established industry toolboxes from Rose & Associates.

[IMAGE: 12_dfi_custom_setup.png — The DFI update without the black box: success and failure likelihood curves, a strength reading, and a likelihood ratio you can defend in a peer review.]

[IMAGE: 13_dfi_custom_curves_geox.png — Multi-case mode: separate density functions per fluid case (oil, gas, water, low-saturation gas, non-reservoir), the resulting R as a function of DHI strength with Simm's rule-of-thumb bands, and the six P(DFI | case) likelihoods ready for hand-off to an external assessment tool.]

[IMAGE: 14_dfi_char_density.png — The characteristic-scoring pathway: where this prospect sits in the drilled success and failure populations, reverse-engineered from published per-attribute statistics.]

**And show what the update actually does.** Two plots I keep coming back to: the iso-DHI map shows how the same seismic evidence would move a prior of *any* quality (and that a weak DHI correctly downgrades an otherwise strong prior), and the what-if sweep shows the posterior as a function of any input you choose to stress.

[IMAGE: 15_dfi_iso_dhi_map.png — The prior-to-posterior map: each curve is one DHI strength. Above the diagonal the evidence helps, below it hurts. The same anomaly does very different work depending on the prior it meets.]

[IMAGE: 16_dfi_sensitivity_sweep.png — What-if: posterior P(G) swept against the combined reservoir chance, one curve per stance on the unknowns. The star is the current prospect.]

**Resolve the update onto the geology.** A single likelihood ratio moves the headline number, but it cannot tell you *which* pillar the seismic evidence actually speaks to. E-POS resolves the update onto the geological factors, the way the established industrial tools do: the reservoir channel and the hydrocarbon-system channel separately. More on why that matters below.

[IMAGE: 17_dfi_pillar_attribution.png — The update resolved per pillar: the headline rises three points while the Reservoir marginal falls four. An aggregate likelihood ratio can never show you this.]

**The DHI should constrain volumes too.** Risk is only half the story: a strong DHI also says something about where the hydrocarbon contact can be. The tool blends the geological column-height distribution with the DFI-implied contact, weighted by how much the seismic evidence has earned the right to be trusted.

[IMAGE: 18_vol_weight.png — Geological volume distribution, DFI-implied distribution, and the recommended blend: the DHI score decides how much the contact is allowed to move toward the seismic answer.]

**Keep the reportable number honest.** One page collects the prior, the update, the posterior and the defensible interval, ready for a review meeting and reproducible from the saved evidence.

[IMAGE: 19_final_pos.png — The reportable page: prior, DFI update, posterior, interval. The whole chain on one screen.]

[IMAGE: 20_cam_post_dfi.png — And back on the chance-adequacy plot: the headline before and after the DFI update, drawn against the zone bands, so the seismic evidence is visible in the same picture as the geological one.]

**Reference tables, for calibration with care.** I have also compiled published risk-table schemes (Milkov 2015, Malvić 2009, CCOP 2000) as in-app reference material, building on the compilation work of A. Uyanik (geocos-v2-0.onrender.com). They are anchors for consistency, not answers; use with care!

[IMAGE: 21_reference_tables.png — Published risk tables as in-app reference: useful anchors, dangerous autopilot.]

---

## Things that building it taught me

**Incorporating uncertainty into risk assessment is not a trivial task.** The mathematics gets difficult fast, and the consequences are sometimes hard to comprehend. My coping strategy in the tool is *translation*: every evidence-based result is always shown next to what it corresponds to in classical risking language. The uncertainty index next to the familiar single number, the revised chance-adequacy plots next to the classic V, tornado plots to show what the uncertainty actually does to the headline. If a method cannot explain itself in the language assessors already speak, it will not be used, and it probably should not be.

**Classical probability cannot say "don't know", and that matters more than I thought.** Blockley's 2013 paper makes a point that sounds philosophical and turns out to be intensely practical: standard probability forces p(not-H) = 1 − p(H), so all your belief is always committed somewhere. The Italian Flag drops that axiom. Belief becomes an interval, and the white in the middle is incompleteness you can carry through the whole assessment instead of hiding it inside a falsely precise point. Once you have seen your portfolio's white, you cannot unsee it.

**The Bayesian update quietly eats your "don't know".** Here is the tension nobody warned me about: the geological prior in E-POS is interval-valued, proudly carrying its incompleteness. Then the seismic evidence arrives, Bayes' theorem does its thing, and the output is a single point. The update is mathematically correct and epistemically lossy at the same time. The tool's answer is to keep the interval visible next to the posterior, but the deeper lesson is that hybrid methods have seams, and you should know where yours are.

**A supportive anomaly can make your reservoir *less* likely.** This one came from an unexpected source: a patent by Martinelli, Stabell and Langlie describing the Bayesian machinery behind a well-known commercial tool. Work the numbers on their example and something counterintuitive falls out. A bright amplitude raises the overall POS, *and at the same time lowers the probability that the reservoir is present*, because part of what could produce that anomaly is a non-reservoir lithology. A single likelihood ratio applied to the headline number can never show you this; you have to resolve the update onto the geological factors. I rebuilt that single-segment logic in E-POS, and watching the headline go up while the reservoir marginal goes down remains my favourite plot in the app (see the pillar-attribution screenshot above).

There is also a historical aside I enjoyed: the old "no-go zone" of the industry's risk matrix, the forbidden region where you are confident but the chance is middling. It turns out to be an artefact of treating geology as a binary state of nature; for a probability it simply does not apply, a point made in an operator's own internal review. E-POS keeps it as a labelled historical reference, not a rule.

[IMAGE: 22_theory_risking_v.png — The Risking V: chance vs confidence, pinned to the base rate when you know nothing, opening toward 0 and 1 as evidence accumulates. The grey region is the old binary-era "no-go", kept for the history lesson.]

---

## What this is not

In the spirit of challenge 1 (bias) and challenge 2 (calibration), some honesty:

- E-POS is **not calibrated against drilled outcomes**. It structures judgement; it does not replace the long, humbling feedback loop of post-drill reviews.
- So far it models a **single prospect segment**, not multi-segment dependencies or portfolio effects.
- All screenshots here use a **synthetic prospect** and a synthetic calibration. No proprietary data is included or implied.
- It is an educational and personal tool, not a substitute for any company's assurance process.

The theory section in the app explains how the tool works and the theory behind ESL and the Bayesian modification, with references to the papers that deserve the credit: Rose (2001), Milkov (2015), Blockley (2013), Simm (2016), Bond et al. (2022), Monigle et al. (2025), Roden, Forrest & Holeywell (2012) [REF: confirm exact citation], and others.

[IMAGE: 23_theory_overview.png — The in-app Theory & Guide: the reasoning, the maths, the workflow and the references. The tool should be able to explain itself.]

---

## Try it

The app runs in the browser: **e-pos.streamlit.app** *(⚠️ placeholder — do not publish before deployment + history scrub)*

Source code and the full theory write-up: **github.com/<user>/e-pos** *(⚠️ placeholder — scrub first)*

If you risk prospects for a living, I would genuinely value your constructive criticism. By my own assessment the tool is 60% complete and 20% incomplete, and the remaining 20% will probably have to come from your feedback! 🇮🇹 ;o)

*What were you taught about prospect risking that turned out to be less simple than advertised?*

---
---

## Teaser post (separate LinkedIn post, links to the article)

> Prospect risking is easy! You estimate four probabilities, multiply them together, and if the result comes out below 25% you revisit your numbers so the managers don't get too concerned.
>
> That is roughly how it was introduced to me. The slow realisation that it might be a bit more complicated eventually turned into a side project: an open tool for evidence-supported prospect risking, an article about what makes assigning a POS genuinely hard, and the suspicion that I may have over-engineered a simple exploration task.
>
> Evidence for / against / don't-know. Two methods that are allowed to disagree. A Bayesian DHI update without the black box. And one plot where a supportive seismic anomaly makes the reservoir *less* likely (yes, really).
>
> Article below. By my own assessment it is 60% complete, 20% incomplete, and the last 20% will have to come from your constructive criticism in the comments. 🇮🇹 👇

*(attach: 01_pos_monster.png)*
