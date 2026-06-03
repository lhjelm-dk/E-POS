"""Theory & Guide tab render function."""
from __future__ import annotations

import streamlit as st


def _render_theory_tab(ctx) -> None:
    """Render the Theory tab.  Called by _render_tabs."""

    models = ctx.models
    play = ctx.play
    conditional = ctx.conditional
    r = ctx.rollup
    total_for = ctx.total_for
    total_against = ctx.total_against
    play_for = ctx.play_for
    play_against = ctx.play_against
    conditional_for = ctx.conditional_for
    conditional_against = ctx.conditional_against
    conditional_results = ctx.conditional_results
    uncertainty_weight = ctx.uncertainty_weight
    prospect_title = ctx.prospect_title
    _active_model_ref = ctx.active_model
    _pillar_colors = ctx.pillar_colors
    _pillar_display = ctx.pillar_display
    ESL_OPTIONS = MODE_OPTIONS = ctx.esl_options

    st.markdown(
        "<div style='background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;"
        "padding:16px 20px;border-radius:10px;margin-bottom:12px;'>"
        "<b style='font-size:1.2rem;'>📚 Theory & Guide</b><br>"
        "<span style='font-size:0.85rem;opacity:0.85;'>"
        "Everything you need to understand how E-POS works — the reasoning, the maths, the workflow, and the references."
        "</span></div>",
        unsafe_allow_html=True,
    )

    with st.expander("🚀 Quick-start: how to use E-POS in 5 steps", expanded=False):
        st.markdown("""
**E-POS is built around one insight:** the quality of your evidence matters more than your point-estimate probability.
The Italian Flag makes that quality visible. You enter evidence once, and three methods update automatically.

---

**Step 1 — Set your stance (Dashboard tab, top)**
> Choose **w** (0.0 = pessimistic, 0.5 = neutral / recommended, 1.0 = optimistic).
> This controls how the uncommitted *white* evidence contributes to POS.
> Use the company default (w = 0.5) unless you have a specific reason to deviate — and document it.

**Step 2 — Assess the Play pillars (Play tab)**
> For each pillar (Charge, Closure, Reservoir, Retention):
> - Set **S_for** = fraction of evidence supporting adequacy.
> - Set **S_against** = fraction of evidence against adequacy.
> - White = 1 − S_for − S_against (uncommitted / unknown).
> - Open **▶ Assess** for the full Chance Adequacy Matrix panel per element.

**Step 3 — Assess the Conditional elements (Conditional tab)**
> Same inputs, but now for prospect-specific sub-elements within each pillar.
> Set combination operators (ESL-ALL / ESL-ANY / ESL-IPT) per pillar group.

**Step 4 — Review results (Analysis tab)**
> P(G, ESL), Uncertainty Index, CAM scatter, and the P(G, Classic) derived view
> all update here — no extra work required.

**Step 5 — Sign off (Dashboard tab, bottom)**
> Record analyst, date and QC review in the Audit Trail before exporting.
""")

    with st.expander("🎯 Why prospect risking is hard — independence, double-dipping & conditional risk",
                     expanded=False):
        st.markdown(r"""
### Risk probabilities are genuinely difficult to assess

A prospect chance-of-success is a **subjective probability** about a one-off, partly
unobservable geological system. There is no long-run frequency to calibrate against on
a single prospect, the evidence is incomplete and noisy, and well-documented cognitive
biases (anchoring, motivated reasoning, overconfidence) pull estimates around. Two
competent geoscientists looking at the same dataset can defensibly land on very
different numbers. That irreducible difficulty is *why* this app insists on making the
**evidence quality** visible (the Italian Flag) rather than pretending a single point
estimate is the whole story.

---

### The independence assumption — and where it breaks

The classic POS multiplication

$$P(G) = P(\text{Charge}) \times P(\text{Reservoir}) \times P(\text{Closure}) \times P(\text{Retention})$$

is only valid if the pillars are **statistically independent**. In real geology they
rarely are — they share a common burial, structural and depositional history, so the
true joint probability can be **higher or lower** than the naive product. Treating
correlated risks as independent is one of the most common ways a prospect portfolio
ends up mis-calibrated.

Risks fall on a spectrum:

| Type | Example | Consequence for the product rule |
|------|---------|----------------------------------|
| **Truly independent** | Charge from an entirely separate kitchen vs. a structural-only closure risk | Product rule is fair |
| **Partially dependent** | Reservoir *presence* and reservoir *quality* (same depositional system drives both) | Product over-penalises — you risk the same geology twice |
| **Strongly conditional** | Source maturity → expulsion → migration path → trap charge | Must be chained as conditional probabilities, not multiplied as if separate |

---

### Double-dipping (risking the same geology twice)

The subtlest error is **semantic overlap** between elements. If "Reservoir presence"
already docks the score for a high-risk depositional setting, and "Reservoir quality"
then docks it *again* for the same lithological uncertainty, the prospect is penalised
twice for one underlying fact. The product rule has no way to know the two factors are
correlated — it just multiplies. Good practice:

- **Define each element by what it adds**, not what it overlaps. Write down the precise
  question each pillar answers so two pillars never answer the same question.
- If two factors are driven by one geological cause, either **merge them** or score one
  of them **conditional on** the other (not marginally).
- Use the **White (uncommitted)** mass for genuine ignorance — don't convert "I'm not
  sure" into "Support Against," which silently double-counts uncertainty.

---

### Source, charge and migration — the hardest case

The petroleum-system elements are **inherently sequential and conditional**, which makes
them the easiest place to double-dip:

> **P(charge at trap)** = P(mature source) × P(expulsion | mature) ×
> P(migration reaches trap | expelled) × P(retention of charge | arrived)

Each term is conditional on the previous one. Problems arise when an analyst scores, say,
"Source" pessimistically *and* "Migration" pessimistically for what is really the **same**
doubt ("I'm not sure this kitchen ever charged anything up-dip"). The doubt gets
multiplied in twice and the prospect is over-risked. Conversely, scoring them as fully
independent when they share one kitchen **under-represents** the common-cause risk that
*all* of them fail together.

**Practical guidance in E-POS:**
- Decide up front whether charge/migration are **one combined element** or a **conditional
  chain**, and keep the wording of each element disjoint.
- Make the dependency explicit in the **Conditional tab** (ESL-ALL / ESL-ANY / ESL-IPT
  operators) rather than hiding it inside a single fudged number.
- When in doubt, put the shared uncertainty in **one** element's White mass and reference
  it from the others' justification text — so the audit trail shows the doubt was counted
  **once**.
""")

    with st.expander("🟩⬜🟥 Evidence Support Logic (ESL) — fundamentals", expanded=False):
        st.markdown(r"""
### The Italian Flag

Each risk element is represented by three quantities that must sum to ≤ 1:

| Symbol | Name | Interpretation |
|--------|------|---------------|
| **S(H)** / S_for | Support For | Fraction of evidence actively supporting adequacy |
| **S(¬H)** / S_against | Support Against | Fraction of evidence actively contradicting adequacy |
| **W** = 1 − S_for − S_against | White / uncommitted | Evidence present but unresolved, or simply absent |

If S_for + S_against > 1 the element is **over-committed** (yellow flag). This is not an error — it means
two bodies of evidence are in direct conflict. Document the conflict; it is geologically significant.

---

### Policy P

$$\text{Policy P} = S_{for} + w \times (1 - S_{for} - S_{against})$$

- At **w = 0**: Policy P = S_for → Belief (lower bound, all unknowns vote against)
- At **w = 0.5**: Policy P = midpoint of [Bel, Pl] → Laplace principle (recommended default)
- At **w = 1**: Policy P = 1 − S_against → Plausibility (upper bound, all unknowns vote for)

The interval **[Bel, Pl]** = [S_for, 1 − S_against] is the defensible range for the element.
The wider the interval, the more uncertain the element.

> **Vocabulary in this app:** use **Policy P** for the per-element point estimate
> (= S_for + w × White) and **P(...)** for aggregated values — for example
> **P(G, ESL)** for the total prospect probability via ESL, **P(G, Classic)** for the
> Rose-style multiplicative result, **P(pillar)** for per-pillar combined chance.
> The bare term **POS** is intentionally *not* used in this app: it is reserved as
> the symbol for the future DHI-updated Bayesian-conditioned probability. Until
> that release ships, all current values are expressed as Policy P or P(...).

---

### Evidence Clarity Index (ECI)

$$\text{ECI} = |S_{for} - S_{against}|$$

High ECI = clear evidence (strongly for or against). Low ECI = conflicted or uncommitted evidence.
Commitment C = S_for + S_against measures total evidence volume regardless of direction.

---

### Combination operators

| Operator | Formula | Use when |
|----------|---------|----------|
| **ESL-ALL** | min(S_for), min(S_against) | All sub-elements required (weakest link) |
| **ESL-ANY** | max(S_for), max(S_against) | Any one sub-element is sufficient |
| **ESL-IPT** | Sufficiency-weighted | Strong confirmatory evidence propagates strongly |
| **Product (Π)** | ∏ Policy_P_i | Independent pillars combined multiplicatively |
| **Mean** | average Policy P | Equal-weight ensemble |

---

### Hierarchy of combination

```
P(G) = P(Play) × P(Cond)
     = [∏ P(pillar, Play)] × [∏ P(pillar, Cond)]
       P(pillar, Play) = Policy P(play element S_for, S_against, w)
       P(pillar, Cond) = ESL-combination of sub-element Policy P values
```
""")

    with st.expander("📐 Chance Adequacy Matrix (CAM) — interpretation guide", expanded=False):
        st.markdown(r"""
### What the CAM shows

The Chance Adequacy Matrix plots each risk element in **(POS × Commitment)** or **(POS × ECI)** space.

- **X axis (reversed):** Probability of Success — high confidence on the **left**, low on the **right**.
- **Y axis:** Commitment C = S_for + S_against, or ECI = |S_for − S_against|.

### Background zones

The zones are computed from the implied Pg at a given (POS, C) coordinate:

$$P_g = \frac{\text{POS} - w(1-C)}{C} \quad \text{(for C > 0)}$$

| Zone | Condition | Meaning |
|------|-----------|---------|
| 🟩 Green | Pg ≥ g_threshold | Element is adequately supported |
| ⬜ White | r_threshold < Pg < g_threshold | Assessment is ambiguous — gather more data |
| 🟥 Red | Pg ≤ r_threshold | Element is inadequately supported — risk driver |

### Feasibility envelope

The blue dashed lines bound the **feasible region** for a given commitment C at stance w:

- **Min POS line:** S_for = 0 → POS = w(1 − C)
- **Max POS line:** S_for = C → POS = C + w(1 − C)

An element **cannot plot outside the envelope** given its C value. If it appears to, check for
S_for + S_against > 1 (over-commitment).

### Bel / Pl error bars (optional)

Enable *Bel / Pl interval* to show the defensible range as a horizontal bar:
- Left end = Bel = S_for (all unknowns against)
- Right end = Pl = 1 − S_against (all unknowns for)
- The dot = Policy P at current stance w

Wide bars = uncertain element (much white evidence). Narrow bars = committed assessment.

### Iso-Pg lines

Dashed iso-probability lines at 10/30/50/70/90 % Pg show where in the CAM different probability
levels lie. Use these to read off the implied Pg for any (POS, C) position.

### Marker types

| Symbol | Meaning |
|--------|---------|
| ◆ Large diamond | Play pillar element |
| ● / ▲ / ■ Small shapes | Conditional sub-elements (shape = pillar) |
| ☆ Outline star | Conditional pillar aggregate (combined ESL) |
| ★ Filled star | P(G, ESL) (the prospect result) |
""")
        st.info("Open the **Analysis tab → Chance Adequacy Matrix** to interact with the live plot.")

    with st.expander("🔢 P(G, Classic) — the multiplicative method", expanded=False):
        st.markdown(r"""
### What P(G, Classic) does

P(G, Classic) — the Rose-style probability — is the **product of all pillar values**:

$$P(G, \text{Classic}) = P(\text{Charge}) \times P(\text{Closure}) \times P(\text{Reservoir}) \times P(\text{Retention})$$

Within each pillar, sub-elements are combined using the **minimum** (weakest link) or a product,
depending on the Classic operator setting.

### Relationship to ESL

E-POS derives P(G, Classic) **directly from your ESL evidence** — you do not enter separate
ROSE numbers (unless you explicitly override on the Dashboard). The per-element value used in
the Classic chain is the **Policy P**:

$$\text{Policy P}_i = S_{for,i} + w \times \text{White}_i$$

This means:
- You need **zero extra input** beyond the ESL assessment.
- P(G, Classic) and P(G, ESL) will often be close but rarely identical — see
  "Why P(G, ESL) ≠ P(G, Classic)" for the four structural reasons.
- The **difference** is informative: if P(G, Classic) >> P(G, ESL), your evidence is more
  optimistic than the uncertainty structure suggests.

### When to use

P(G, Classic) is the standard language of the industry (AAPG/Rose). Present it alongside
P(G, ESL) so decision-makers familiar with either method can read the assessment.

See results in **Analysis tab → Derived Methods → P(G, Classic)**.
""")

    with st.expander("⚖️ Why P(G, ESL) ≠ P(G, Classic) — the four structural reasons", expanded=False):
        st.markdown(r"""
### The core question

Both methods use exactly the same raw inputs — your S_for, S_against, and White per element,
and the same Policy P formula. So why do they produce different numbers?

The answer is **when and how uncertainty (White) is handled during aggregation**.

---

### Reason 1 — Order of operations: when is Policy P applied?

This is the most important difference.

**P(G, ESL) path:**
```
(S_for, S_against) per element
   → combine pairs using ESL operator   ← operates on masses, not probabilities
   → one (S_for_combined, S_against_combined) per pillar
   → apply Policy P = S_for + w × White ONCE at the end
```

**P(G, Classic) path:**
```
(S_for, S_against) per element
   → apply Policy P FIRST → Policy_P_i per element
   → combine the Policy_P_i values using Classic operator
```

These are mathematically different. A worked example with two elements,
both with S_for = 0.60, S_against = 0.10, w = 0.5, using a **Product** operator:

| Step | P(G, ESL) (Product on masses) | P(G, Classic) (Product on probabilities) |
|------|------------------------------|------------------------------------------|
| Per-element Policy P | — | Policy_P₁ = Policy_P₂ = 0.60 + 0.5 × 0.30 = **0.75** |
| Combine S_for | 0.60 × 0.60 = **0.36** | — |
| Combine S_against | 1 − (0.90 × 0.90) = **0.19** | — |
| Residual White | 1 − 0.36 − 0.19 = **0.45** | (absorbed — unavailable) |
| Final value | 0.36 + 0.5 × 0.45 = **0.585** | 0.75 × 0.75 = **0.563** |

Same data. Same operator intent. **0.585 vs 0.563** — and the gap widens with more elements
and more White.

---

### Reason 2 — White space compounds differently

In ESL, the uncommitted White of every element is carried through the aggregation hierarchy
as a live mass. After combining across all elements and pillars, the resulting total White
represents the **joint residual uncertainty** — larger than any single element's White because
uncertainty compounds.

Policy P is then applied to this joint White once:

$$P(G, \text{ESL}) = S_{for,\,total} + w \times (1 - S_{for,\,total} - S_{against,\,total})$$

In P(G, Classic), each element's White is absorbed into its own policy estimate immediately.
That information is gone — the combination step sees only point probabilities.

**Consequence:** When data is sparse (large White), P(G, ESL) will tend to be
**higher** than P(G, Classic) at w = 0.5, because ESL still counts half the
joint uncertainty as support. P(G, Classic) has already compressed that uncertainty into
moderate per-element probabilities that then multiply down.

---

### Reason 3 — Cross-pillar product operates on different quantities

**P(G, ESL)** applies the mass-product rule to (S_for, S_against) pairs:

$$S_{for,\,total} = \prod_i S_{for,\,i}$$
$$S_{against,\,total} = 1 - \prod_i (1 - S_{against,\,i})$$

Then:

$$P(G, \text{ESL}) = \prod S_{for,\,i} \;+\; w \times \left[\prod(1-S_{against,\,i}) - \prod S_{for,\,i}\right]$$

**P(G, Classic)** multiplies the point estimates directly:

$$P(G, \text{Classic}) = \prod_i \left(S_{for,\,i} + w \times White_i\right) = \prod_i \text{Policy P}_i$$

These are only equal when all $White_i = 0$ (fully committed evidence everywhere).

A single-pillar example with S_for = 0.70, S_against = 0.10, w = 0.5:

$$P(G, \text{ESL}) = 0.70 + 0.5 \times (1 - 0.70 - 0.10) = 0.70 + 0.10 = 0.80$$
$$P(G, \text{Classic}) = 0.70 + 0.5 \times 0.20 = 0.80 \quad \checkmark$$

They agree at single-element level. With two identical pillars:

$$P(G, \text{ESL}): S_{for,\,total} = 0.49,\; S_{against,\,total} = 0.19,\; P(G) = 0.49 + 0.5\times0.32 = \mathbf{0.65}$$
$$P(G, \text{Classic}): 0.80 \times 0.80 = \mathbf{0.64}$$

Small difference here. With four pillars and larger White, the gap is material.

---

### Reason 4 — Default operators differ at the group level

| Level | ESL default | Classic default |
|-------|------------|-----------------|
| Within label-group | ESL-ALL: min(S_for), min(S_against) | Min: min(Policy P) |
| Across groups in pillar | ESL-ALL | Min (weakest link) |
| Across pillars | Product on mass pairs | Product on probabilities |

**ESL-ALL** takes the minimum support FOR and the minimum support AGAINST —
meaning only the evidence that applies weakly to all elements is carried forward.

**Classic Min** takes the element with the lowest Policy P —
which could have very different S_for and S_against combinations.

They frequently agree in direction but differ in magnitude.

---

### When do they converge?

P(G, ESL) and P(G, Classic) produce **identical results** only when:

1. Every element has **White = 0** (S_for + S_against = 1 exactly — fully committed evidence).
2. There is exactly **one element** in the entire assessment.

In practice, the closer your evidence is to fully committed (small White), the
closer the two methods will be. A large spread is a data-quality signal, not an error.

---

### What the spread tells you

| Spread (P(G, ESL) − P(G, Classic)) | Interpretation |
|------------------------------------|----------------|
| < 2% | Robust — evidence is well-committed. Either number is defensible to report. |
| 2–5% | Moderate uncertainty. Small data gaps present. Document the key unknowns. |
| 5–10% | Significant uncertainty. Identify which pillar drives the White — gather data before reporting. |
| > 10% | Evidence is largely uncommitted. The assessment is exploratory; do not report a single number without documenting the uncertainty range. |

**Reporting guidance:** Report both P(G, ESL) and P(G, Classic). Classic is the
industry-standard language (AAPG/Rose). ESL is the primary method. The difference
between them is the quantified evidence of your uncertainty — and that belongs
in the risk narrative, not hidden in a single number.
""")

    with st.expander("🌳 Current assessment — ESL combination hierarchy", expanded=False):
        st.caption(
            "Visual representation of how evidence flows from sub-elements through pillar combinations to P(G)."
        )
        from components.hierarchy_chart import render_esl_hierarchy
        render_esl_hierarchy(play, conditional)

    # ═══════════════════════════════════════════════════════════════════════
    # 🌊 BAYESIAN DFI UPLIFT — full theory + workflow + pitfalls + reporting
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown(
        "<div style='background:linear-gradient(135deg,#1e3a8a,#3b82f6);color:#fff;"
        "padding:14px 18px;border-radius:8px;margin:18px 0 8px;'>"
        "<b style='font-size:1.05rem;'>🌊 Bayesian DFI Update — full guide</b><br>"
        "<span style='font-size:0.82rem;opacity:0.9;'>"
        "How a seismic Direct Fluid Indicator updates the geological prior via Bayes' theorem — "
        "theory, formulas, workflow, pitfalls, and reporting templates."
        "</span></div>",
        unsafe_allow_html=True,
    )

    st.caption(
        "🔎 All DFI abbreviations (DFI, DHI Index, SAAM, R, V, LSG, Eval-Res, …) "
        "are defined in the unified **📖 Glossary & Abbreviations** at the bottom of this tab."
    )

    with st.expander("📐 Bayesian DFI — full derivation (light-stats friendly)", expanded=False):
        st.markdown(r"""
### Why use Bayes for DFI at all?

A traditional geological assessment gives you a prior probability **P(G)**. When the seismic shows a
direct fluid indicator (bright spot, flat spot, favourable AVO), you want to **update** that prior to
reflect this new evidence. The intuitive question is:

> *Given that I observed this DHI Index, what is the new probability the prospect works?*

Bayes' theorem is the rigorous answer. It accepts:
- the prior **P(G)**,
- a model of how likely the observed DHI is **if the prospect succeeds** (call it $L_\text{success}$), and
- a model of how likely that same DHI is **if it fails** (call it $L_\text{failure}$),

and returns the posterior **P(G | DFI)**.

---

### Step 1 — Bayes in the simplest possible form

For two outcomes (success vs failure):

$$
P(G \mid \text{DFI}) \;=\; \frac{L_\text{success}\,\cdot\,P(G)}
{L_\text{success}\,\cdot\,P(G) \;+\; L_\text{failure}\,\cdot\,[1-P(G)]}
$$

In words: *posterior = (how well the observation fits success × prior) / (how well it fits anything at all)*.

If $L_\text{success} = L_\text{failure}$, the observation tells us nothing and the posterior equals the prior.
If $L_\text{success} \gg L_\text{failure}$, the posterior moves toward 1.
If $L_\text{success} \ll L_\text{failure}$, the posterior moves toward 0.

This is the entire intuition. Everything that follows is just figuring out **what to plug in** for $L_\text{success}$ and $L_\text{failure}$.

> **What is the prior $P(G)$ here?** It is *not* a fresh number — it is the geological result
> **P(G, ESL)** (or P(G, Classic)), which is itself a **Policy P**: a stance-weighted point
> $P = S_\text{for} + w\cdot\text{White}$ chosen from inside the Bel/Pl envelope. So the stance $w$
> is baked into the prior, and the Bayesian update inherits it: a more optimistic stance (higher $w$)
> feeds a higher prior, which produces a higher posterior. The posterior $P(G \mid \text{DFI})$ is
> therefore conditional on the same stance as the prior — change $w$ and *both* prior and posterior
> move together (this is exactly what the stance-trajectory plot on DFI Results shows). The DFI update
> does **not** introduce a new subjective dial; it conditions the existing stance-weighted point on the
> observed seismic evidence.

---

### Step 2 — Why "failure" is not one thing

For oil & gas prospects, a "failure" is not a single homogeneous category. The well can fail because:
- the **reservoir** wasn't there or wasn't producible (non-evaluable reservoir),
- the trap was charged but with **water** (no HC),
- the reservoir had **LSG** — low-saturation gas that mimics a real DFI on seismic,
- the trap had **other fluids** (CO₂, residual oil, brine inversion, etc.).

Each of these failure modes generates a **different seismic signature** — different distribution of DHI Index values.
Lumping them together with one $L_\text{failure}$ would average over those distributions and erase information.

So instead we decompose into **8 mutually exclusive outcomes** (this is the workbook's column V..AC):

| # | Outcome | Symbol |
|---|---------|--------|
| 1 | Oil + Eval-Res — **success** | $\pi_\text{succ}$ |
| 2 | Oil + Non-Eval-Res — failure | $\pi_\text{oil/NR}$ |
| 3 | Water + Eval-Res — failure | $\pi_\text{wat/R}$ |
| 4 | Water + Non-Eval-Res — failure | $\pi_\text{wat/NR}$ |
| 5 | LSG + Eval-Res — failure | $\pi_\text{lsg/R}$ |
| 6 | LSG + Non-Eval-Res — failure | $\pi_\text{lsg/NR}$ |
| 7 | Other + Eval-Res — failure | $\pi_\text{oth/R}$ |
| 8 | Other + Non-Eval-Res — failure | $\pi_\text{oth/NR}$ |

These 8 probabilities sum to **1**. Outcome 1 *is* the prior P(G).

---

### Step 3 — Where the 8 outcome probabilities come from

We build them from the pillar Pgs and the analyst-supplied fluid mix. Let:

- $\pi_\text{res}$ = reservoir-pillar combined Pg (play × cond for Reservoir)
- $\pi_\text{nonres}$ = product of the six non-reservoir sub-pillar Pgs (Charge, Closure, Retention × play+cond, plus Reservoir/Play if you keep them separate)
- $w_\text{wat}, w_\text{lsg}, w_\text{oth}$ = fluid failure weights (sum to 1)

Then:

$$
\begin{aligned}
\pi_\text{succ}      &= \text{P(G)} = \pi_\text{nonres}\cdot\pi_\text{res} \\
\pi_\text{oil/NR}    &= \pi_\text{nonres}\cdot(1-\pi_\text{res}) \\
\pi_\text{wat/R}     &= (1-\pi_\text{nonres})\cdot\pi_\text{res}\cdot w_\text{wat} \\
\pi_\text{wat/NR}    &= (1-\pi_\text{nonres})\cdot(1-\pi_\text{res})\cdot w_\text{wat} \\
\pi_\text{lsg/R}     &= (1-\pi_\text{nonres})\cdot\pi_\text{res}\cdot w_\text{lsg} \\
\pi_\text{lsg/NR}    &= (1-\pi_\text{nonres})\cdot(1-\pi_\text{res})\cdot w_\text{lsg} \\
\pi_\text{oth/R}     &= (1-\pi_\text{nonres})\cdot\pi_\text{res}\cdot w_\text{oth} \\
\pi_\text{oth/NR}    &= (1-\pi_\text{nonres})\cdot(1-\pi_\text{res})\cdot w_\text{oth}
\end{aligned}
$$

You can verify they sum to 1: factor out and the structure collapses to $1\cdot 1\cdot(w_\text{wat}+w_\text{lsg}+w_\text{oth}) = 1$.

---

### Step 4 — Likelihood per outcome (the SAAM Gaussians)

Each of the 8 outcomes maps to one **SAAM calibration class**. Each class has a calibrated **mean** $\mu_k$
and **standard deviation** $\sigma_k$ for the DHI Index distribution. The likelihood of observing
DHI Index $x$ given outcome $k$ is the Gaussian PDF:

$$
L_k(x) \;=\; \frac{1}{\sigma_k\sqrt{2\pi}}\;\exp\!\left[-\,\frac{(x-\mu_k)^2}{2\sigma_k^2}\right]
$$

The outcome-to-class mapping mirrors the workbook:

| Outcome | SAAM class |
|---------|-----------|
| Oil + Eval-Res (success) | `Success` (or `Oil` / `Oil+Gas` / `Gas` per analyst choice) |
| Oil + Non-Eval-Res | `Reservoir_failure` |
| Water + Eval-Res | `H2O_failure` |
| Water + Non-Eval-Res | `Reservoir_failure` |
| LSG + Eval-Res | `LSG_failure` |
| LSG + Non-Eval-Res | `Reservoir_failure` |
| Other + Eval-Res | `LSG_failure` *(same class — LSG and Other share)* |
| Other + Non-Eval-Res | `Reservoir_failure` |

Note that **Reservoir_failure** and **Non-Eval-Res** share one class — geophysically this makes sense
because both produce a seismic signature dominated by the absence of producible reservoir, regardless of the
pore fluid that *would* have been there.

> **SD mode:** SAAM publishes two sigma values per class. `upper` uses the larger of the two
> (wider, more conservative — preferred default). `calculated` uses the empirical sample sigma
> (tighter). Always state which mode you used in your report.

---

### Step 5 — Joint posterior over the 8 outcomes

Bayes generalises to many outcomes naturally:

$$
P(\text{outcome}_k \mid x) \;=\; \frac{L_k(x)\cdot \pi_k}{\sum_{j=1}^{8} L_j(x)\cdot \pi_j}
$$

The denominator $\sum_j L_j\pi_j$ is the **evidence** — the unconditional probability of observing
DHI $= x$, summed over all the ways it could have happened.

---

### Step 6 — Marginalise to get P(G | DFI)

The posterior probability of success is just the first outcome's posterior:

$$
\boxed{\;P(G \mid \text{DFI}) \;=\; P(\text{outcome}_1 \mid x) \;=\; \frac{L_\text{succ}\cdot \pi_\text{succ}}{\sum_{j=1}^{8} L_j\cdot \pi_j}\;}
$$

This is the headline number you see in the **DFI Results** tab.

---

### Step 7 — R_SAAM (DHI-Index strength) and DHI Volume Weight V

We define two diagnostic ratios that summarise *how strong the DFI evidence is*, independently of the prior:

$$
E[L \mid \text{failure}] \;=\; \frac{\sum_{k\ne 1} L_k\cdot \pi_k}{\sum_{k\ne 1} \pi_k}
\quad\text{(failure-weighted average likelihood)}
$$

$$
\boxed{\;R_\text{SAAM} \;=\; \frac{L_\text{succ}}{E[L \mid \text{failure}]}\;}
\qquad
\boxed{\;V \;=\; \frac{L_\text{succ}}{L_\text{succ}+E[L\mid\text{failure}]}\;}
$$

**R_SAAM** (DHI-Index strength) is a likelihood ratio:
- **R_SAAM > 1** → observation favours success (uplift expected)
- **R_SAAM = 1** → neutral
- **R_SAAM < 1** → observation favours failure (downgrade expected)
- **R_SAAM ≫ 1** (e.g. 5+) → strong evidence; large uplift even with weak priors

> **Two different R's — don't conflate them.** `R_SAAM` here is the likelihood ratio from the
> **SAAM DHI-Index** Gaussian calibration (this pathway, the method of record). The
> **characteristic-scoring** pathway computes a *different* ratio, `R_char` = ∏ LRᵢ, as a naive
> product of per-attribute likelihood ratios (Monigle 2025). Both feed the same Simm 2-state
> Bayes update, but they are computed on different scales and are **not** interchangeable.
> *(Note for external write-ups: "SAAM" is an internal database name; alias it before publishing.)*

**V** (DHI Volume Weight) is R squashed into [0, 1]:
- **V > 0.5** → success-aligned
- **V = 0.5** → neutral
- **V < 0.5** → failure-aligned

Both are computed for the workbook's "success vs all-failure" view (1 vs aggregate of 2..8). They are
the same R and V plotted on the **DFI Setup → DFI Results** diagnostic strip.

---

### Step 7b — V as a *volume-risking weight* (operational interpretation)

The likelihood-ratio reading of V above (Step 7) tells you whether the DFI favours success or failure.
But V has a second, equally useful reading that matters when you move downstream into **volumetrics**:

> **V tells you how much to trust a DFI-derived volume constraint against your purely geological one.**

The set-up: a prospect is mapped geologically from apex to structural spill, with an HCWC (hydrocarbon–water
contact) depth that has some uncertainty range — typically broad, because nothing on the seismic *directly*
sees the contact. A bright spot, flat spot or AVO conformance may then suggest a **DFI-implied HCWC** at
some depth with smaller positional uncertainty. The question is: how much should we trust the DFI's contact
pick versus the geological range?

V is the natural weight. The right way to apply it is **directly to the distribution parameters** —
*not* as a mixture of distributions (see the side-bar "Why not a mixture model?" below).

#### The V-weighted blend (direct form)

For any HCWC summary statistic — mean, sd, P10, P50, P90 — combine the geology-only and DFI-only
values as a convex combination:

$$
\boxed{\;\mu_\text{posterior} \;=\; V\cdot\mu_\text{DFI} \;+\; (1-V)\cdot\mu_\text{geo}\;}
\qquad
\boxed{\;\sigma_\text{posterior} \;=\; V\cdot\sigma_\text{DFI} \;+\; (1-V)\cdot\sigma_\text{geo}\;}
$$

or equivalently, working percentile-by-percentile (which is more practical for volumetric Monte Carlo):

$$
\boxed{\;X_p^\text{posterior} \;=\; V\cdot X_p^\text{DFI} \;+\; (1-V)\cdot X_p^\text{geo}\;,\quad p \in \{10, 50, 90\}\;}
$$

The same form propagates to GRV, STOIIP/GIIP, and any contact-driven volumetric quantity — replace `X`
above with the parameter of interest.

#### Small example — the HCWC distribution as a blend

Concretely, think of the prospect's HCWC as a blend of two pictures:

- **(a) the geological case** — a *broad* distribution spanning apex to spill (you don't directly see the contact), and
- **(b) the DFI case** — a *narrow* distribution centred on the flat-spot pick (tight depth uncertainty).

Say geology puts the contact at P50 = −2,775 m (broad), and a flat spot picks −2,840 m (tight). With **V = 0.76**:

$$\text{HCWC}_{50} = 0.76\,(-2840) + 0.24\,(-2775) = -2{,}824\ \text{m}$$

The blended contact sits close to the DFI pick but is pulled 16 m shallower by the residual geological weight,
and its spread is 76 % of the way from the broad geological range toward the tight DFI range. Lower V → the
blend slides back toward the geological picture; V = 0.5 → exactly halfway.

#### Why this is the right form

- **Unimodal posterior.** The blended distribution has a single central tendency that shifts smoothly
  with V from the geological centroid (V = 0) to the DFI pick (V = 1). No artificial bimodality.
- **Spread contracts smoothly.** The posterior σ is a linear blend of the two input σ's. High V
  ⇒ tight (DFI-dominated). Low V ⇒ broad (geology-dominated). At V = 0.5 the spread is the simple
  average — neither view alone owns the uncertainty.
- **Volume range scales correctly.** Linear in V at the percentile level means the P10–P90 width
  shrinks linearly with V, which is the operational intuition: a stronger DFI should narrow the
  range, not just shift it.
- **Honest about partial information.** Both inputs are treated as *partially correct descriptions*
  rather than competing hypotheses. That matches reality: the geology really does know the column,
  and the DFI really does see a more precise indication — they're complementary, not exclusive.

#### Reading the V slider for volumetrics

| V | Operational behaviour of the volume range |
|---|---|
| **V ≈ 0.9** | DFI dominates. HCWC pulled tightly to the flat-spot pick; volume P10–P90 shrinks to roughly the DFI-only range plus a 10% geological residual. |
| **V ≈ 0.7** | DFI-leaning blend. P50 settles ~70% of the way from the geological centroid to the DFI pick; range contracts to ~70% of the DFI-only width plus 30% of the geological-only width. |
| **V ≈ 0.5** | Equal weight. P50 sits at the midpoint; range is the average of the two. Use this when you can't justify trusting either side more. |
| **V ≈ 0.3** | Geology-leaning blend. DFI shifts the centre only modestly; range stays broad. |
| **V ≈ 0.1** | DFI is suspect (likely LSG, residual gas, lithology effect). Geology owns the volume; the DFI contributes essentially nothing. The same low V is what drives the P(G \| DFI) downgrade on the risk side. |

#### Why not a mixture model?

You might be tempted to write $p_\text{posterior} = V\cdot p_\text{DFI} + (1-V)\cdot p_\text{geo}$
(probability-weighted mixture of the two distributions). Don't. That formulation treats the two
descriptions as **mutually exclusive hypotheses** — either the DFI is right (with probability V) or
the geology is right (with probability 1−V) — and produces a **bimodal** posterior (a sharp peak at
the DFI pick sitting on top of a broad geological pedestal).

That's the wrong cognitive model:
- The geology is not "right or wrong" — it just provides a defensible range that includes the answer.
- The DFI is not "right or wrong" either — it provides a more precise indication, partially trustworthy.
- Both are partially correct and *complementary*. You want to combine them, not switch between them.

Direct V-weighting (above) treats them as complementary measurements of the same underlying quantity.
The result is a single, unimodal posterior whose centre and spread are honest convex combinations.
This is the formulation used in E-POS and recommended for reporting.

#### Caveats (unchanged from likelihood-ratio reading)

1. V applied to volumetrics is **rigorous only when you've already conditioned on success** —
   i.e., "given the prospect works, where is the contact and how big is the volume?". The P(G | DFI)
   update (Step 6) handles the *whether* question separately.
2. The DFI-only volumetrics ($\mu_\text{DFI}$, $\sigma_\text{DFI}$, $X_p^\text{DFI}$) must be
   supplied by the geophysicist from the flat-spot pick depth, inversion uncertainty, and processing
   tolerance. V tells you the *weight* to apply, not the *content* of that input.
3. The convex-combination form is an analyst-grade decision tool, not a full Bayes-derived posterior
   over HCWC depth. A rigorous treatment would require a likelihood model linking the DFI waveform
   to depth — beyond what a single composite DHI Index can deliver. For decision-grade volumetric
   ranges, direct V-weighting is the right level of rigour.

---

### Step 7c — Worked example: V applied to GRV

Take the HCWC example above ($V = 0.76$) and carry it through to gross rock volume.
Apply the **same per-percentile blend** to the two volumetric cases:

| | P10 | P50 | P90 | P10–P90 width |
|---|---|---|---|---|
| Geology-only | 70 | **140** | 245 | 175 MMm³ |
| DFI-only (tight) | 238 | **252** | 267 | 29 MMm³ |
| **V-weighted (V = 0.76)** | **198** | **225** | **262** | 64 MMm³ |

The DFI pulls the P50 from 140 → 225 MMm³ and narrows the range from 175 → 64 MMm³, while the
residual 24 % geological weight keeps the lower tail honest.

**Sensitivity to V** (same inputs, different DFI strength):

- **V = 0.5** (uninformative) → P50 ≈ 196 MMm³, the simple midpoint; range = average of the two.
- **V = 0.1** (DFI suggests failure) → volumes fall back to ~geology, *and* the same low V drives a
  P(G | DFI) **downgrade** on the risk side (Step 6) — treat the anomaly as a likely LSG/lithology artefact.

**Bottom line:** one number, V, does two jobs — it updates P(G) on the risk side and weights the
volume blend on the resource side. Record the V used (shown on the DFI Results tab) in the same
audit-trail line as P(G | DFI).

---

### Step 8 — Why the posterior collapses the Bel/Pl envelope

The geological prior P(G, ESL) carries an uncertainty envelope `[Bel, Pl]` derived from the Italian-flag
white mass. After the DFI update, that envelope is gone — the posterior is a **point estimate**.

Why? The Bayes update conditions on observed evidence: *given this DFI, the answer is one number*.
Carrying the white uncertainty through Bayes would require defining a likelihood over the white mass
itself (a prior on the prior — possible but adds another layer of subjective input). E-POS adopts the
pragmatic convention used in the SAAM workbook: update the point-estimate prior, report the posterior
as a point estimate, and report the prior's Bel/Pl alongside so the reader sees the *original*
defensible envelope.

---

### Step 9 — Attribution back to pillars (Classic)

The Bayes math returns one number — the new P(G). For reporting, you often want to know *which pillars
moved*. The **Classic attribution** redistributes the posterior across the 8 pillar slots
(Charge/Closure/Reservoir/Retention × Play/Cond) using a reservoir-aware log-split:

$$
\Delta \log = \log\!\left(\frac{P(G\mid \text{DFI})}{P(G)}\right)
$$

is split between:
- the **reservoir contribution** $\sum$ (eval-res posteriors) / $\pi_\text{res}$
- and the **non-reservoir contribution** $1 -$ that

then the non-reservoir share is divided equally (in log-space) across the 6 non-reservoir slots.
This **preserves the multiplicative product** ($\prod$ posterior Pgs = posterior P(G)) and matches
the spreadsheet exactly.

For **ESL attribution** there are two modes:
- **Option A** (default) preserves each pillar's commitment $C = S_\text{for}+S_\text{against}$ and shifts
  the mass split to match the new pillar Pg.
- **Option B** preserves the Bel/Pl envelope by recomputing the posterior separately at w=0 and w=1,
  then redistributing — useful when you want each pillar's defensible range to remain meaningful after the update.
""")

    with st.expander("🧮 Alternative: Characteristic scoring (Simm 2016 + Monigle 2025)", expanded=False):
        st.markdown(
            "The 8-outcome SAAM Bayes above is one of **two** pathways the app supports "
            "for deriving the DHI strength R. The second pathway — **characteristic "
            "scoring** — is grounded in two foundational papers:"
        )
        st.markdown(
            "- **Simm (2016)** *Seismic Amplitude and Risk: A Sense Check* — FORCE, Nov 2016.\n"
            "  Establishes R as the likelihood ratio P(DFI | hc) / P(DFI | nohc) and provides "
            "a rule-of-thumb framework where R ≈ 1 (single anomaly), R ≈ 2 (two first-order effects), "
            "R ≈ 3 (multiple effects + contact + consistency).\n\n"
            "- **Monigle et al. (2025)** *Integrated and Improved Direct Hydrocarbon Indicators*, "
            "*AAPG Bulletin* **109/5** pp. 617–636.\n"
            "  Modern ExxonMobil iCOS dataset — ~120 drilled prospects scored against six "
            "DHI attributes (5-category verbal scale per attribute). The histograms of success/failure "
            "counts per category supply the per-category likelihood ratios used below. Critically: "
            "*the lack of DHI attributes on a DFI-capable prospect is integrated as a negative line of "
            "evidence and would reduce the prior* — the update is bidirectional."
        )
        st.markdown("---")
        st.markdown("#### Step C1 — Simm's 2-state Bayes formula")
        st.markdown(
            "When the failure modes are not decomposed by fluid type (the case for characteristic "
            "scoring), the Bayesian update collapses to a single likelihood-ratio relation:"
        )
        st.latex(r"P(G\mid \text{DFI}) \;=\; \frac{R \cdot P(G)}{R \cdot P(G) + (1 - P(G))}")
        st.markdown(
            "Solving for R given a prior/posterior pair (useful for back-calibration):"
        )
        st.latex(r"R \;=\; \frac{P(G)\,(1-P(G\mid\text{DFI}))}{(1-P(G))\,P(G\mid\text{DFI})}")
        st.markdown("---")
        st.markdown("#### Step C2 — Per-attribute likelihood ratio from the Monigle histograms")
        st.markdown(
            "For each of the six DHI attributes (anomaly strength, amplitude terminations, fit to "
            "structure, anomaly consistency, lateral amplitude contrast, fluid contact reflection), "
            "Monigle 2025 publishes the count of successful and failed prospects in each of 5 verbal "
            "categories. The per-category likelihood ratio is:"
        )
        st.latex(
            r"\text{LR}_k(c) \;=\; \frac{P(c \mid \text{success})}{P(c \mid \text{failure})}"
            r" \;=\; \frac{(\text{succ}_{k,c} + \alpha)/(N_k^{\text{succ}} + 5\alpha)}"
            r"{(\text{fail}_{k,c} + \alpha)/(N_k^{\text{fail}} + 5\alpha)}"
        )
        st.markdown(
            "where $\\alpha = 0.5$ is a Laplace-smoothing prior that keeps the LR finite for "
            "zero-count cells (e.g. 'very high lateral contrast' has 0 failures in the database "
            "— without smoothing the LR would be infinite)."
        )
        st.markdown("---")
        st.markdown("#### Step C3 — Convert each success rate to a likelihood ratio")
        st.markdown(
            "Monigle reports a **success rate** per verbal category — e.g. 82 % of drilled prospects "
            "with a *Fair* fluid-contact reflection found hydrocarbons. That figure is "
            "$P(\\text{HC}\\,|\\,\\text{category})$ *inside Monigle's drilled population*, so it "
            "already carries that population's overall base rate. To use it as evidence on **your** "
            "prospect (which has its own ESL prior), strip the base rate out and keep only the "
            "evidential strength — the **likelihood ratio**:"
        )
        st.latex(r"\text{LR}_k(c) \;=\; \frac{\text{odds}\big(\text{SR}_k(c)\big)}{\text{odds}(\text{base rate})}"
                 r" \;=\; \frac{\text{SR}_k(c)/\big(1-\text{SR}_k(c)\big)}{N_\text{HC}/N_\text{dry}}")
        st.markdown(
            "A category whose success rate **equals the dataset's overall rate** contributes "
            "LR = 1 (no information); above it lifts R, below it lowers R. This is the "
            "**base-rate-relative** convention — the conceptually correct Bayesian likelihood "
            "ratio, and the **default** in E-POS. Worked example (fluid contact reflection, "
            "base rate 56 %): *Fair* at 82 % → LR = (0.82/0.18) ÷ (67/52) ≈ **3.25** (a genuine "
            "strong-uplift signal), *Good* at 67 % → LR ≈ **1.51**, *None* at 16 % → LR ≈ **0.17**."
        )
        st.info(
            "**Optional legacy anchoring — *scale-middle* (off by default).** A toggle on the "
            "DFI Setup page re-anchors every attribute so its **middle verbal category** is forced "
            "to LR = 1, by dividing through by the middle-category LR:  \n"
            "$\\text{LR}_k^{\\text{mid}}(c) = \\text{LR}_k(c)\\,/\\,\\text{LR}_k(c_\\text{mid})$  \n"
            "so an all-middle slider configuration yields $R_\\text{char}=1$ by construction. The "
            "rationale is that *if* your ESL prior is implicitly conditioned on a 'typical scored-DHI "
            "prospect', the middle category carries no information beyond that prior. The pitfall — "
            "and why it is **no longer the default** — is that it discards real evidence whenever the "
            "middle category is itself far from the base rate. The non-monotonic fluid-contact case is "
            "the cautionary example: *Fair* (82 %) is the middle, so scale-middle anchoring reports it "
            "as **neutral** and even paints *Good* (67 %, genuinely LR 1.51) as a downgrade. Use it "
            "only if your prior elicitation explicitly assumes a typical DHI is already present."
        )
        st.markdown("---")
        st.markdown("#### Step C4 — Combine the six LRs (naive conditional independence)")
        st.markdown(
            "Assuming the six attributes contribute independently — *which is not strictly true; "
            "see the caveat below* — the prospect-level R_char is the product of the per-attribute "
            "likelihood ratios (base-rate-relative by default, or scale-middle if that toggle is on):"
        )
        st.latex(r"R_\text{char} \;=\; \prod_{k=1}^{6} \text{LR}_k(c_k)")
        st.markdown(
            "**Caveat (independence assumption).** The six attributes correlate in reality — e.g. "
            "a prospect with a strong anomaly tends also to show good amplitude terminations. "
            "Treating them as independent over-counts the evidence and can push R far above what "
            "the joint data support. Monigle 2025 moved to a Supervised Machine Learning model "
            "precisely to capture these correlations. As a defensible analyst-grade simplification, "
            "E-POS uses the naive product with a **hard cap at R = 3** (Simm 2016's empirical "
            "SAAM maximum) and a symmetric floor at R = 1/3."
        )
        st.markdown("---")
        st.markdown("#### Step C5 — Discernibility (Monigle weighting)")
        st.markdown(
            "Discernibility asks *how much should the DFI evidence be allowed to move the prior, "
            "given expectations and data quality?* It is a combination of:\n\n"
            "- **Expectations** — is a DFI plausibly visible on this prospect type? (likely / "
            "more likely / less likely / unlikely)\n"
            "- **Confidence** — is the seismic data quality good enough to discriminate a real "
            "DFI? (high / moderate / low / no)\n\n"
            "Following Monigle (Figure 6), the two ratings are combined by **least common "
            "denominator** to give a single discernibility bucket (high / moderate / low / "
            "absent) with weight d ∈ {1.0, 0.6, 0.3, 0.0}. The bucket squashes R toward 1:"
        )
        st.latex(r"R_\text{effective} \;=\; R_\text{char}^{\;d}")
        st.markdown(
            "**d = 1** (high discernibility) → R unchanged; **d = 0** (absent) → R = 1, posterior = prior. "
            "Intermediate values exponentially squash R toward 1 in log-space, gracefully reducing "
            "the DFI's influence as discernibility falls."
        )
        st.markdown("---")
        st.markdown("#### Step C6 — DHI Characteristic Score (Monigle's 0–100 % readout)")
        st.markdown(
            "Monigle 2025 reports a single **DHI score** in 0–100 %. The same number falls out of "
            "R_eff under a 50/50 neutral prior:"
        )
        st.latex(r"\text{DHI score} \;=\; \frac{R_\text{eff}}{R_\text{eff} + 1}")
        st.markdown(
            "**R = 1 → score = 50 %** (neutral); **R = 3 → score = 75 %** (strong-positive cap); "
            "**R = 1/3 → score = 25 %** (strong-negative cap). The score is a *display* metric — "
            "the actual Bayes update uses R_eff applied to the prospect's geological prior, not "
            "to a 50/50 generic."
        )
        st.markdown("---")
        st.markdown("#### Step C7 — The current 5-attribute set")
        st.markdown(
            "E-POS scores the prospect on the **current 5 attributes (post-2021 iCOS)**: "
            "Anomaly strength, Lateral amplitude contrast, Fit to structure, Amplitude "
            "terminations, Fluid contact reflection. Internal benchmarking (Monigle 2025) "
            "found these five are the predictive subset, and they are the production "
            "scoring system since 2021. Stats come from Monigle Figure 4 (185 re-scored "
            "prospects).\n\n"
            "The earlier **pre-2020 legacy system** scored 6 quality + 4 confidence "
            "attributes (AVO class, amplitude strength, plus data density, data "
            "processing, well calibration, impedance fit). Monigle 2025 demonstrated that "
            "*the four confidence attributes were not predictive of success* and that AVO "
            "class / amplitude strength did not generalise globally — all six were dropped "
            "from the scoring process. E-POS follows the current system and does **not** "
            "expose the legacy set."
        )
        st.markdown("---")
        st.markdown("#### Step C8 — Radar plot of slider positions")
        st.markdown(
            "Below the per-attribute LR bar chart, a polar (radar) plot shows the "
            "analyst's **slider positions** on each axis — 1 (worst / most failure-like) "
            "out to 5 (best / most success-like). The plot style follows Monigle 2025 "
            "Figure 11, where the radar visualises the scored attribute profile of a "
            "prospect at a glance.\n\n"
            "E-POS uses a **single series** (this prospect) rather than Monigle's "
            "quality-vs-confidence two-series style. The reason: E-POS sliders capture "
            "both kinds of information mixed together in each attribute, so an honest "
            "single series of slider positions is more truthful to the input than a "
            "synthetic split. A larger filled polygon = a stronger DHI profile."
        )
        st.markdown("---")
        st.markdown("#### When to use this path vs DHI Index (SAAM)")
        st.markdown(
            "| Use case | Choose | Why |\n"
            "|---|---|---|\n"
            "| You have a SAAM DHI Index from an external scoring sheet | **DHI Index (SAAM)** | "
            "8-outcome decomposition gives per-pillar attribution + fluid-class diagnostics. |\n"
            "| You don't have SAAM access or want a stand-alone assessment | **Characteristic scoring** | "
            "Six verbal sliders + public Monigle 2025 calibration; no external tool required. |\n"
            "| You want a sanity check on a SAAM-derived R | Run both; compare | The two R values "
            "should be of similar magnitude. Large disagreement = investigate which attributes / "
            "fluid mix is driving the gap. |\n"
            "| Reservoir-presence is the dominant risk (e.g. wildcat sub-salt) | Either | Both "
            "pathways give muted updates in this case, correctly reflecting that the DFI can't see "
            "what isn't there. |"
        )


    with st.expander("🛠 How to use this tool — step-by-step workflow", expanded=False):
        st.markdown(r"""
### Prerequisites

Before opening the DFI Update tab you should have:

1. **A complete ESL assessment** — Play and Conditional tabs filled in, P(G, ESL) showing on the Dashboard.
2. **A DHI Index value** for the prospect, computed from the SAAM/SaRA scoring rubric (typically a single integer in the range −23 to +50).
3. **A view on the fluid-failure split** — what fraction of failed-prospect outcomes (in your basin/play) is water vs LSG vs other fluids? Defaults are 80/20/0 if you have no calibration.
4. **A fluid type** — does the prospect target oil, gas, oil+gas, or generic hydrocarbons?

> If you don't have a DHI Index, **don't toggle DFI on**. The Bayes update assumes the DHI Index is a
> calibrated number from a consistent scoring system. Without that, the posterior is meaningless.

---

### Step 1 — Toggle DFI on (Dashboard tab)

Find the **"DHI prospect?"** toggle just below the Stance slider. Default is OFF.

When you toggle ON for the first time, E-POS sets defaults: DHI Index = 19, water = 0.80, LSG = 0.20, other = 0.00, fluid type = Success, SD mode = upper. These are **session-sticky** — your subsequent edits persist for this prospect.

---

### Step 2 — DFI Setup sub-page

Navigate to the **DFI Update** tab → **DFI Setup**. You'll see four panels:

**A. DHI Index input**
> Enter the integer score from your SAAM/SaRA scoring sheet. Hover the help icon for the typical reference table.

**B. Fluid mix**
> Three sliders summing to 100%. Set:
> - **Water** = expected fraction of failures that are wet.
> - **LSG** = expected fraction that are low-saturation gas (mimic DFIs).
> - **Other** = residual (CO₂, residual oil, brine inversion, etc.).
> If unsure, leave defaults. Document your choice in the audit trail.

**C. Fluid type & SD mode**
> - Fluid type: `Success` (pooled), `Oil`, `Oil+Gas`, `Gas` — pick the closest match to your prospect's primary target. The Bayes update uses the corresponding SAAM class for the success-likelihood Gaussian.
> - SD mode: leave `upper` unless you have a specific reason to tighten the likelihoods.

**D. Bell-curve preview**
> Visual check of the five Gaussian likelihoods overlaid with your DHI Index as a vertical line. **Sanity check:** is your DHI Index in a region where the Success curve is meaningfully above the failure curves? If not, the uplift will be small.

> 🛈 **Tip:** if you don't know what to put for fluid mix, just toggle the **Sensitivity Sweep** on the DFI Results tab and look at how much the posterior moves across the 100%/0% water family. If the family is tight, your choice doesn't matter much.

---

### Step 3 — DFI Results sub-page

Four blocks, top to bottom:

1. **Headline tiles** — prior vs posterior, ESL and Classic.
2. **Per-pillar attribution tables** — which pillar absorbed the most uplift/downgrade.
3. **Posterior trajectory plot** — 4 curves: P(G, ESL) prior/posterior and P(G, Classic) prior/posterior, swept across stance w. The vertical dashed line is your current stance.
4. **Sensitivity sweep** — configurable: pick X-axis variable (DHI Index, Reservoir Pg, stance w, etc.) and curve family (water fraction, LSG fraction, etc.). Use this to *stress-test* the posterior against assumptions.

---

### Step 4 — Final Prospect POS Summary

This is the **reportable view**: pillar table (prior), DFI diagnostic strip (DHI + R + V + mix), posterior bar with prior→posterior shift, and a 2×2 method×prior/posterior table. Download as a text summary for inclusion in your prospect write-up.

---

### Step 5 — Document and sign off

In the Audit Trail:
- DHI Index value and source (SAAM version, date, who scored it).
- Fluid mix percentages and their justification.
- Stance w and SD mode used.
- Final P(G | DFI, ESL) and P(G | DFI, Classic), plus the spread between them.
""")

    with st.expander("🌳 DFI decision tree — should I apply the update?", expanded=False):
        st.markdown(r"""
Use this tree before turning on the DFI toggle. **Stop and reconsider** at any 'No' branch.

```
Q1.  Do you have seismic coverage of the prospect with adequate
     processing quality (preserved-amplitude, AVO-compliant)?
        │
        ├─ No  → Do NOT use DFI Bayes. Document that no DFI was applied.
        │
        └─ Yes ─────────────────────────────────────────────────────────
              │
              Q2.  Has someone scored the prospect using the SAAM/SaRA
                   rubric to produce a numeric DHI Index?
                    │
                    ├─ No  → Either (a) score it yourself using the
                    │        SAAM checklist, or (b) skip DFI Bayes.
                    │        Don't guess a DHI Index from a screenshot.
                    │
                    └─ Yes ─────────────────────────────────────────────
                          │
                          Q3.  Is the prospect's primary risk a reservoir
                               failure (no producible rock) rather than
                               an HC failure (water, LSG, other)?
                                │
                                ├─ Yes → The DFI is uninformative about
                                │        reservoir presence. Bayes will
                                │        produce only a small uplift even
                                │        with a strong DHI Index. Apply
                                │        the update but expect a muted ∆.
                                │
                                └─ No  ───────────────────────────────────
                                      │
                                      Q4.  Are LSG / residual gas pitfalls
                                           a known concern in this basin?
                                            │
                                            ├─ Yes → Set LSG fraction
                                            │        > 30%. Cross-check
                                            │        the posterior against
                                            │        analogue dry-hole rate.
                                            │
                                            └─ No  → Default LSG = 20%.
                                                      │
                                                      Apply the DFI update.
                                                      Report prior + posterior
                                                      + R + V + spread.
```

### What to do when the decision tree says "skip DFI"

You can still use E-POS — just **leave the toggle OFF**. The dashboard will show only the ESL and Classic priors. The audit trail should record *why* DFI was not applied (no seismic, no SAAM score, or judgement that it is uninformative).
""")

    with st.expander("⚠️ DFI pitfalls & calibration tips", expanded=False):
        st.markdown(r"""
### Pitfall 1 — Over-confident water fraction

The water fraction $w_\text{wat}$ controls how much of the failure mass is "informative water" vs "informative LSG/other". If you set water = 100% with LSG = 0%, the Bayes update assumes all failed traps are wet — meaning a DFI is *strong* evidence of HC (because if it failed, it would have looked seismically quiet). This produces a large uplift.

**In reality**, in basins where LSG is common (e.g., overpressured Tertiary clastic plays), 100% water is wildly optimistic. Setting LSG = 30–50% is typical for HC-prone DFI-rich basins.

> **Sanity check:** run the Sensitivity Sweep with X = DHI Index and family = Water fraction. If the curves spread by more than 5 pp across the family, the fluid mix choice is material and must be justified.

---

### Pitfall 2 — Wrong fluid type

The four success classes (`Success`, `Oil`, `Oil+Gas`, `Gas`) have *different* mean DHI Indices and sigmas. Picking `Gas` for an oil-prone target overstates the success likelihood at moderate DHI Index values. The `Success` (pooled) class is the safest default if you genuinely don't know.

---

### Pitfall 3 — Treating the posterior as the "right" answer

The posterior is conditional on your prior, your fluid mix, your calibration version, your SD-mode choice, and your DHI Index scoring. None of those are exact. Always report:
- Prior P(G, ESL) **and** P(G, Classic) — the geological assessment.
- Posterior P(G | DFI, ESL) **and** P(G | DFI, Classic) — the DFI-updated value.
- The **spread between ESL and Classic posteriors** — your data-quality signal.
- The R and V diagnostic values.

A single posterior number is not the answer.

---

### Pitfall 4 — Ignoring SD mode

`upper` and `calculated` can change the posterior by 5–15 pp on borderline DHI Indices. The workbook convention (and E-POS default) is `upper` — wider, more conservative. **Always state which mode** you used in your write-up.

---

### Pitfall 5 — Using DFI when reservoir risk dominates

If the prospect's main risk is reservoir presence (e.g., wildcat in a poorly-imaged sub-salt setting), the DHI signature is dominated by the `Reservoir_failure` and `Non-Eval-Res` classes — which look very similar to many failure modes. The Bayes update will produce a small uplift even at high DHI Index, which is **correct behaviour**: the DFI can't tell you about something it can't see.

---

### Pitfall 6 — Calibration drift

SAAM/SaRA updates its database periodically. v.16a (used here by default) is one snapshot. If you're working in a basin not well-represented in the consortium dataset (e.g., new frontier), the Gaussians are extrapolations. **Document the calibration version** in every report.

---

### Calibration tip — anchor to analogues

After computing the posterior, ask: *does this number match what I'd expect from the play's discovery rate?* If your posterior P(G | DFI) = 65% but the play's analogue success rate (post-DHI screening) is 25%, something is over-tuned. Trace it back: too-high water fraction? Wrong fluid type? Over-aggressive prior?

---

### Calibration tip — invert R for sanity

R = 3 means *the observation is 3× more likely under success than under failure*. Ask: *is this seismic anomaly really 3× more diagnostic than my prior suggests?* If you can't articulate the answer in geophysical terms, R is probably overstated and the SAAM class assignment may be wrong.
""")

    with st.expander("📋 DFI reporting — what to include in a prospect write-up", expanded=False):
        st.markdown(r"""
### Minimum reportable set

For a DFI-updated prospect, every write-up should contain — at minimum — these eight numbers and three plots:

| # | Quantity | Symbol |
|---|----------|--------|
| 1 | Prior, ESL | P(G, ESL) |
| 2 | Prior, Classic | P(G, Classic) |
| 3 | Posterior, ESL | P(G \| DFI, ESL) |
| 4 | Posterior, Classic | P(G \| DFI, Classic) |
| 5 | DHI Index | (integer) |
| 6 | DHI-Index strength | R_SAAM |
| 7 | DHI Volume Weight | V |
| 8 | Prior Bel–Pl envelope | [bel%, pl%] |

Plus three plots:
- The **Risk Overview table** (geological prior, per-pillar Italian flags).
- The **prior→posterior bar** with delta annotation.
- The **stance-trajectory** plot showing how the posterior moves with stance w.

---

### Template language

> *"The geological prior for {prospect_name} was assessed at **P(G, ESL) = {prior_esl}%**
> (defensible range {bel}%–{pl}%) and P(G, Classic) = {prior_classic}%.*
>
> *A SAAM-scored DHI Index of **{dhi_index}** was applied as a Bayesian update, with fluid failure mix
> Water {wat}% / LSG {lsg}% / Other {oth}%, fluid type {hc_type}, SD mode {sd}, calibration {cal_version}.*
>
> *The resulting posterior is **P(G | DFI, ESL) = {post_esl}%** (Δ {delta_esl:+} pp vs prior), with
> the Classic method posterior at **{post_classic}%** (Δ {delta_classic:+} pp).*
>
> *Diagnostic values: R_SAAM = {R}, DHI Volume Weight V = {V}. The Bayesian update is
> [robust / sensitive] to fluid-mix assumptions — sensitivity sweep showed posterior variation of
> {sweep_pp} pp across 100%–0% water fraction.*
>
> *The {posterior_method} posterior is recommended for booking. The spread between ESL and Classic
> posteriors ({spread} pp) is documented as the data-quality signal."*

---

### When to NOT lead with the posterior

If any of the following are true, lead with the **prior** and present the posterior as a sensitivity case:

- The spread between ESL and Classic posteriors > 10 pp (methodological disagreement).
- The fluid-mix sensitivity sweep > 5 pp (input-driven, not data-driven uplift).
- R_SAAM < 1.2 (very weak DFI evidence — uplift is mostly prior-driven).
- The prospect failed Q1/Q2/Q3 of the decision tree (the update shouldn't have been applied at all).

In these cases the audit trail must state: *"Posterior shown for completeness; risk decision is based on the geological prior."*

---

### What to put in the Audit Trail

| Field | Source |
|-------|--------|
| Analyst name | manual |
| Review date | manual |
| Basin | manual |
| Stance w | from dashboard |
| ESL prior, Bel, Pl | from Analysis tab |
| Classic prior | from Analysis tab |
| DHI Index, scorer, scoring date | manual + SAAM sheet |
| SAAM calibration version | from app (e.g. v.16a) |
| SD mode | from app |
| Fluid mix (water/LSG/other) | from app |
| Fluid type | from app |
| Posterior ESL, Classic | from app |
| R, V | from app |
| Sensitivity sweep range | from app |
| Decision recommendation | manual |

The Final Prospect POS Summary's **download (.txt)** button produces this audit trail in a copy-paste-ready format.
""")

    with st.expander("📏 Calibration guidance & key references", expanded=False):
        st.markdown("""
### Calibration — what do the numbers mean?

| POS range | Interpretation | Typical analogue base-rate |
|-----------|---------------|---------------------------|
| > 70% | High confidence — strong evidence for adequacy | Proven play, appraisal well |
| 50–70% | Positive — balance of evidence favours adequacy | Mature exploration |
| 30–50% | Ambiguous — material uncertainty remains | Frontier exploration |
| 10–30% | Negative — evidence tilts against adequacy | Speculative play |
| < 10% | High risk — strong evidence against adequacy | Long-shot / concept well |

Calibrate your POS numbers against **analogue discovery rates** from the same play/basin.
Use the calibration anchors in the Play and Classic POS sections.

---

### Key references

1. **Quintessa ESL Guide v3.0** (2022) — [Download PDF](https://quintessa.org/repository/files/Evidence_Support_Logic_Guide_v3.0.pdf)
   The definitive technical reference for ESL, Italian Flag and Policy P.

2. **Blockley, D.I. & Godfrey, P. (2000)** — *Doing it Differently: Systems for Rethinking Infrastructure*.
   Thomas Telford. [Original Blockley formulation of ESL.]

3. **Rose, P.R. (2001)** — *Risk Analysis and Management of Petroleum Exploration Ventures*.
   AAPG Methods in Exploration 12. [Classic POS / multiplicative risking.]

4. **Milkov, A.V. (2015)** — "Probability of success and confidence in chance factor assessment for
   petroleum prospects." Earth-Science Reviews 150: 191–208.
   [Comparison of methods; calibration data.]

5. **Hjelm, L. (this tool)** — E-POS integrates ESL with Classic POS to provide a
   dual-method view with a single evidence entry, bridging Italian Flag rigour with
   the industry-standard multiplicative risking framework.
""")
        from components.adequacy_matrix import render_adequacy_matrix_reference
        render_adequacy_matrix_reference()

    # ═══════════════════════════════════════════════════════════════════════
    # 📖 UNIFIED GLOSSARY — ESL/Classic + DFI in one place
    # ═══════════════════════════════════════════════════════════════════════
    with st.expander("📖 Glossary & Abbreviations (ESL + DFI)", expanded=False):
        st.markdown(r"""
A single reference for every term in E-POS — the ESL/Classic core and the Bayesian DFI workflow.

### ESL evidence (per-element inputs)

| Term | Definition |
|------|-----------|
| **S_for** | Support For — evidence actively favouring adequacy. *(Also written S(H) in Quintessa literature.)* |
| **S_against** | Support Against — evidence actively disfavouring adequacy. *(Also written S(¬H).)* |
| **White** | 1 − S_for − S_against — uncommitted or absent evidence |
| **w** | Stance — how white space maps to point estimates (0=Bel, 0.5=neutral, 1=Pl) |
| **ECI** | Evidence Clarity Index = \\|S_for − S_against\\| |
| **Commit (C)** | Commitment = S_for + S_against — total evidence volume |

### ESL per-element computed values

| Term | Definition |
|------|-----------|
| **Policy P** | Per-element point estimate = S_for + w × White. *(Was called "Policy POS" before; renamed to keep `POS` reserved for future DHI update.)* |
| **Bel(element)** | Belief = S_for — lower bound on defensible P |
| **Pl(element)** | Plausibility = 1 − S_against — upper bound on defensible P |

### Aggregated probabilities — the P(...) notation

`P(qualifier1, qualifier2, ...)` is the unified notation. Qualifiers can be a **pillar** (Charge, Closure, Reservoir, Retention), a **scope** (Play, Cond), or a **method** (ESL, Classic).

| Notation | Meaning |
|----------|---------|
| **P(G)** | Total prospect geological probability of success — the prospect-level result (the **prior**, before DFI) |
| **P(G, ESL)** | P(G) computed via ESL method (primary) — combines mass pairs through the hierarchy |
| **P(G, Classic)** | P(G) computed via Classic POS — multiplies per-element Policy P values |
| **P(G \| DFI)** | **Posterior** P(G) after the Bayesian DFI update (can be higher *or* lower than the prior) |
| **P(G \| DFI, ESL)**, **P(G \| DFI, Classic)** | Posterior P(G) by method |
| **P(Play)**  /  **P(G, Play)** | Play-level chance combined across all pillars |
| **P(Cond)**  /  **P(G, Cond)** | Conditional-level chance combined across all pillars |
| **P(Charge)**, **P(Closure)**, **P(Reservoir)**, **P(Retention)** | Per-pillar combined chance = P(pillar, Play) × P(pillar, Cond) |
| **P(Charge, Play)**, **P(Charge, Cond)**, … | Per-pillar value at one scope |
| **P(Reservoir, Cond, "Net-to-gross")** | Sub-element value — full qualification (pillar, scope, label) |
| **Bel(X)**, **Pl(X)** | Aggregated bounds — lower / upper on any P(X) |
| **Δ pp** | Posterior − prior, in **percentage points** (40% → 45% is +5 pp, not +5%) |

**Reserved term:** `POS` will denote the DHI-updated Bayesian-conditioned probability in a future release. Until then, do not use `POS` for any current quantity — use `P(...)` or `P(G | DFI)` instead.

### DFI / Bayesian workflow

| Abbrev. | Full term | Meaning |
|---------|-----------|---------|
| **DFI** | Direct Fluid Indicator | Any seismic attribute that responds directly to hydrocarbons (AVO, flat spot, dim/bright spot, etc.). Umbrella term. |
| **DHI** | Direct Hydrocarbon Indicator | Synonym for DFI, more common in older literature. |
| **DHI Index** | Composite DHI score | A single scalar (typical range −23 … +50) summarising the strength and consistency of all observed DFIs for one prospect. Computed by the SAAM/SaRA scoring rubric. |
| **SAAM** | Seismic Amplitude Analysis Module | Rose & Associates DHI consortium database (now **SaRA** — *Seismic Amplitude Risk Assessment*) of drilled prospects with calibrated DHI Index → outcome statistics. |
| **SaRA** | Seismic Amplitude Risk Assessment | Renamed/successor to SAAM. Same database lineage. |
| **DFI update** | Bayesian update | Conditioning the prior on the DFI observation. Can **raise or lower** P(G) — a strong DFI lifts it; an absent/weak DFI where one was expected lowers it. |
| **R_SAAM** | DHI-Index strength | Likelihood ratio = $L_\text{success} / E[L \mid \text{failure}]$. R_SAAM > 1 favours success; R_SAAM < 1 against. |
| **V** | DHI Volume Weight | Bounded version of R = $L_\text{success}/(L_\text{success}+E[L\mid\text{failure}])$. Range 0..1; 0.5 = neutral. Also the weight on a DFI-derived volume constraint. |
| **L** | Likelihood | Probability *density* of observing the DHI Index given a specific outcome class (a Gaussian PDF value — not a probability; can exceed 1). |
| **π** (pi) | Outcome prior | Prior probability of one of the 8 mutually-exclusive outcomes (categorical-prior convention, kept distinct from P(·) and pillar Pgs). |
| **HC** | Hydrocarbon | Catch-all for oil and/or gas. |
| **LSG** | Low-Saturation Gas | A failed-prospect outcome where reservoir contains gas at saturation too low to produce — generates DFIs that mimic commercial gas. |
| **HCWC** | Hydrocarbon–Water Contact | Depth of the fluid contact; a flat spot may indicate it more precisely than geology. |
| **Eval-Res** | Evaluable Reservoir | Reservoir present and detectable on seismic. The DFI is informative. |
| **Non-Eval-Res** | Non-Evaluable Reservoir | Reservoir failure (absent / sub-resolution / wrong facies). The DFI is uninformative — defaults to a failure-class likelihood. |
| **SD mode** | Standard-deviation mode | Gaussian width: `upper` (conservative, wider) or `calculated` (tighter). E-POS defaults to `upper`. |
| **Fluid weights** | Water / LSG / Other failure fractions | How failure mass is partitioned among the three non-HC outcomes. Must sum to 1. |
| **Fluid type** | HC class selector | Which SAAM success class supplies the success likelihood: *Success* (pooled), *Oil*, *Oil+Gas*, *Gas*. |
| **Calibration version** | SAAM/SaRA release | Versioned snapshot of the database statistics. Current: v.16a. |

### Other terms

| Term | Definition |
|------|-----------|
| **CAM** | Chance Adequacy Matrix — POS × Commitment scatter plot |
| **ESL-ALL** | Combination where all elements must be adequate (min/min) |
| **ESL-ANY** | Combination where any element suffices (max/max) |
| **ESL-IPT** | Imprecise Probability Theory sufficiency combination (dependency-weighted) |

### Notation: why P, L, and π are different letters

- **P** — a *probability* (sums to 1 over its sample space; never exceeds 1). Used for outcomes and for P(G).
- **L** — a *likelihood* (a density evaluated at the observed DHI, viewed as a function of the outcome class). Not a probability; only its ratios carry meaning.
- **π** — a *categorical prior* over the 8 outcomes. Kept visually distinct from P(·) and from pillar Pgs (p_res, p_nonres, …).
""")
