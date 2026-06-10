# LinkedIn article — master draft

> **Assembly notes (not part of the article):**
> - Paste section by section into LinkedIn's article editor; insert each image at its `[IMAGE: …]` slot and copy the caption text under it.
> - Images live in `docs/img/`. All screenshots use a synthetic prospect and the placeholder calibration. Nothing proprietary.
> - ⚠️ **The repo link must not go live until the git-history scrub is done** (old commits still contain reference PDFs and the real calibration file). The app link has the same prerequisite, since Streamlit Cloud deploys from the repo.
> - Word count ≈ 2,000. Cut candidates if it feels long: the Risking-V paragraph in section 5, or image 8.

---

## Prospect risking is easy. (It took me a tool, three textbooks and a patent to understand why it isn't.)

Early in my career I learned how to assign a probability of success to an exploration prospect, and the good news was that it was easy.

You estimate the probability that there is a source rock, a trap, a reservoir and a top seal. You multiply the four numbers together. And if the product comes out below 25%, you go back and revisit your numbers.

At some point I asked about timing: what about the risk that the trap formed *after* the hydrocarbons had already migrated through? The answer was pragmatic. Adding more factors just multiplies in more numbers below one, the product gets too small, and no manager will drill a 6% prospect. So we kept it at four.

I have since come to suspect that the method was not measuring the probability of geological success. It was measuring the number of factors we were willing to multiply.

That slow realisation, that maybe prospect risking isn't easy at all, eventually turned into a side project: **E-POS**, an open tool for evidence-based prospect risk assessment. This article is about what makes risking genuinely hard, what I built to cope with it, and a few things the building taught me that I did not expect.

[IMAGE: 01_app_overview.png — E-POS: evidence in once, three headline numbers out. The gap between methods is information, not an error.]

---

## Why assigning a POS is harder than multiplying four numbers

**1. We are biased, and we know it.** Bond and co-workers have documented how anchoring, availability and motivated reasoning shape interpretation and risk assessment, and why independent assurance processes exist (Bond et al., 2022, *Recommended practices in exploration assurance*). The uncomfortable part is that knowing about bias does not remove it. Structure and documentation help more than good intentions.

**2. You rarely live long enough to be calibrated.** The honest test of a risking process is hindsight: did the prospects you called 20% come in about one time in five? That requires a large drilled portfolio, a stable method, and assessors who stay put. Most of us learn on moving targets, with portfolios too small for the statistics to bite. Rose built a whole discipline around this problem; it remains the hardest one.

**3. The arithmetic stops being innocent the moment elements are dependent.** Multiplying probabilities assumes independence. But is reservoir presence independent of seal presence in the same depositional system? If you risk "migration" in one factor and "charge timing" in another, have you counted the same uncertainty twice? Double-counting dependent evidence systematically *understates* POS, and the worst part is that we often cannot say, geologically, which elements are dependent.

**4. Putting a number on deep uncertainty is its own problem.** How do you know that 40% rather than 50% of reservoir units in this setting, at these depths, will have sufficient permeability? Often you don't. A single number like 0.4 silently claims more knowledge than you have. There is a real difference between "the evidence is split" and "we have no evidence", and classical probability has no way to write it down.

**5. And then your friendly geophysicist leans over.** "It looks OK on the AVO, by the way." How much should that move your number? Five points? Fifteen? Direct fluid indicators carry real information, but folding them in by gut feel is how the same anomaly gets counted twice, once in the reservoir factor and once as a bonus on top.

Each of these challenges has a literature behind it. What I wanted was a place where they meet a working tool.

---

## So I built one

E-POS (Evidence-supported Probability of Success) is a Streamlit app I built to make my own assessments traceable, and it grew into a small laboratory for the methods themselves. The design goals, mapped against the problems above:

**Document evidence, not just numbers.** The core method is Evidence Support Logic (ESL), built on David Blockley's interval probability and the "Italian Flag": every risk element carries evidence *for* (green), evidence *against* (red), and an explicit *don't know* (white). A probability of 0.40 backed by strong conflicting evidence and a 0.40 that is mostly white are different geological situations, and the tool keeps them distinguishable.

[IMAGE: 06_geo_result_overview.png — Every element as an Italian Flag: green for, red against, white for what we genuinely don't know. The point estimate and the defensible interval travel together.]

**Let two methods disagree, visibly.** The app computes the classic multiplicative POS *and* the ESL roll-up from the same evidence, side by side. They differ for structural reasons, and the gap is a data-quality signal: large spread usually means conflicting or thin evidence somewhere that the multiplication quietly absorbed.

[IMAGE: 07_geo_esl_vs_classic.png — Two methods, one set of evidence. When they diverge, that is the assessment telling you where to look.]

**Diagnose, don't just compute.** Tornado plots of risk-element sensitivity, an uncertainty index, and a chance-adequacy view that plots every element by chance vs evidential commitment. The chance-adequacy matrix is an old industry workhorse with known conceptual problems, and I have tried to keep what works (you see your conflicted elements instantly) while being explicit about what doesn't.

[IMAGE: 10_geo_cam.png — Every risk element in chance vs commitment space. The interesting elements are the confident-but-middling ones: that is usually conflict, and conflict is geologically significant.]

**Open the geophysics black box.** The DFI/DHI update is a Bayesian conditioning: the seismic evidence enters as a likelihood ratio R, fully visible, with the success and failure populations drawn on screen. You can see exactly why the number moved, and by how much, instead of nodding at a percentage that fell out of a workflow.

[IMAGE: 12_dfi_custom_setup.png — The DFI update without the black box: success and failure likelihood curves, a strength reading, and a likelihood ratio you can defend in a peer review.]

**Keep the reportable number honest.** One page collects the prior, the update, the posterior and the defensible interval, ready for a review meeting.

[IMAGE: 17_final_pos.png — The reportable page: prior, DFI update, posterior, interval. The whole chain on one screen, reproducible from the saved evidence.]

---

## Three things building it taught me

**1. Classical probability cannot say "don't know", and that matters more than I thought.** Blockley's 2013 paper makes a point that sounds philosophical and turns out to be intensely practical: standard probability forces p(not-H) = 1 − p(H), so all your belief is always committed somewhere. The Italian Flag drops that axiom. Belief becomes an interval, and the white in the middle is incompleteness you can carry through the whole assessment instead of hiding it inside a falsely precise point. Once you have seen your portfolio's white, you cannot unsee it.

**2. The Bayesian update quietly eats your "don't know".** Here is the tension nobody warned me about: the geological prior in E-POS is interval-valued, proudly carrying its incompleteness. Then the seismic evidence arrives, Bayes' theorem does its thing, and the output is a single point. The update is mathematically correct and epistemically lossy at the same time. The tool's answer is to keep the interval visible next to the posterior, but the deeper lesson is that hybrid methods have seams, and you should know where yours are.

**3. A supportive anomaly can make your reservoir *less* likely.** This one came from an unexpected source: a patent by Martinelli, Stabell and Langlie describing the Bayesian machinery behind a well-known commercial tool. Work the numbers on their example and something counterintuitive falls out. A bright amplitude raises the overall POS, *and at the same time lowers the probability that the reservoir is present*, because part of what could produce that anomaly is a non-reservoir lithology. A single likelihood ratio applied to the headline number can never show you this; you have to resolve the update onto the geological factors. I rebuilt that single-segment logic in E-POS, and watching the headline go up while the reservoir marginal goes down remains my favourite plot in the app.

[IMAGE: 21_dfi_pillar_attribution.png — The update resolved per pillar: the headline rises 3 points while the Reservoir marginal falls 4. An aggregate likelihood ratio hides this; the joint update exposes it.]

There is also a historical aside I enjoyed: the old "no-go zone" of the industry's risk matrix, the forbidden region where you are confident but the chance is middling. It turns out to be an artefact of treating geology as a binary state of nature; for a probability it simply does not apply, a point made in an operator's own internal review. E-POS keeps it as a labelled historical reference, not a rule.

[IMAGE: 20_theory_risking_v.png — The Risking V: chance vs confidence, pinned to the base rate when you know nothing, opening toward 0 and 1 as evidence accumulates. The grey region is the old binary-era "no-go", kept for the history lesson.]

---

## What this is not

In the spirit of challenge 1 (bias) and challenge 2 (calibration), some honesty:

- E-POS is **not calibrated against drilled outcomes**. It structures judgement; it does not replace the long, humbling feedback loop of post-drill reviews.
- It models a **single prospect segment**, not multi-segment dependencies or portfolio effects.
- All screenshots here use a **synthetic prospect** and a synthetic calibration. No proprietary data is included or implied.
- It is an educational and personal tool, not a substitute for any company's assurance process.

The theory section in the app cites its sources throughout: Rose (2001), Milkov (2015), Blockley (2013), Simm (2016), Bond et al. (2022), Monigle et al. (2025), and others. Standing on shoulders, all the way down.

---

## Try it

The app runs in the browser: **e-pos.streamlit.app** *(⚠️ placeholder — do not publish before deployment + history scrub)*

Source code and the full theory write-up: **github.com/<user>/e-pos** *(⚠️ placeholder — scrub first)*

If you risk prospects for a living, I would genuinely value your criticism. The tool got better every time someone told me why my numbers were wrong, and I have no reason to believe that process is finished.

*What were you taught about prospect risking that turned out to be less simple than advertised?*

---
---

## Teaser post (separate LinkedIn post, links to the article)

> "Prospect risking is easy: multiply source × trap × reservoir × seal, and if it's below 25%, revisit your numbers."
>
> That is how I learned it. It took me years, a stack of papers and building an entire app to understand everything wrong with that sentence (including the part where it was sometimes me doing the revisiting).
>
> I wrote up what makes assigning a probability of success genuinely hard, and the open tool I built to cope: evidence for / against / don't-know, two methods that are allowed to disagree, and a Bayesian DHI update without the black box.
>
> Article below. Criticism from people who do this for a living is the most useful thing you can leave in the comments. 👇

*(attach: 01_app_overview.png)*
