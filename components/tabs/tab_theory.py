"""Theory & Guide tab render function."""
from __future__ import annotations

import streamlit as st


def _risking_v_schematic():
    """Schematic Risking-V diagram for the Theory section (conceptual, not a prospect).

    The apex is the *symmetric* original Risk Matrix at 0.5 (the "coin") — the model
    the no-go zone belongs to; a marker shows where the base-rate-aware Referenced V
    shifts it. X-axis reversed (100%→0%) to match the app's Chance Adequacy Matrix;
    the feasible region is coloured by the shared CoS probability scale.
    """
    import plotly.graph_objects as go
    import streamlit as st
    from components.colors import cos_color

    apex = 0.5  # original symmetric Risk Matrix: "no data" = the coin (0.5)
    br = max(0.03, min(0.97, float(st.session_state.get("stance_base_rate", 0.30))))
    fig = go.Figure()

    def _ylow(x):
        return abs(2.0 * x - 1.0)   # lower edge of the feasible V at chance x

    # ── Feasible V coloured by chance-of-adequacy (shared CoS scale) ──
    N = 48
    for i in range(N):
        x0, x1 = i / N, (i + 1) / N
        col = cos_color((x0 + x1) / 2.0)
        rr, gg, bb = int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16)
        fig.add_trace(go.Scatter(
            x=[x0, x1, x1, x0], y=[_ylow(x0), _ylow(x1), 1.0, 1.0],
            mode="lines", fill="toself", fillcolor=f"rgba({rr},{gg},{bb},0.22)",
            line=dict(width=0), hoverinfo="skip", showlegend=False))

    # Arms — coloured at the CoS-scale extremes (success green, failure red)
    fig.add_trace(go.Scatter(x=[apex, 1.0], y=[0, 1], mode="lines",
        line=dict(color="#1A7A4A", width=3), hoverinfo="skip", showlegend=False))   # → success(1)
    fig.add_trace(go.Scatter(x=[apex, 0.0], y=[0, 1], mode="lines",
        line=dict(color="#C00000", width=3), hoverinfo="skip", showlegend=False))   # → failure(0)

    # Legacy no-go — high confidence + middling chance; tapered trapezoid, neutral
    # grey overlay (the zones are already coloured), dashed border.
    _y0, _w_lo, _w_hi = 0.45, 0.05, 0.16
    fig.add_trace(go.Scatter(
        x=[0.5 - _w_lo, 0.5 + _w_lo, 0.5 + _w_hi, 0.5 - _w_hi, 0.5 - _w_lo],
        y=[_y0,         _y0,         1.0,         1.0,         _y0],
        fill="toself", fillcolor="rgba(55,55,65,0.13)",
        line=dict(color="rgba(55,55,65,0.55)", width=1, dash="dash"),
        hoverinfo="skip", showlegend=False))
    fig.add_annotation(x=0.5, y=0.82, showarrow=False, font=dict(size=12, color="#374151"),
        text="legacy NO-GO<br><span style='font-size:10px'>high confidence + middling chance<br>"
             "(binary state only — superseded)</span>")

    # Apex = the coin (0.5); base-rate marker = where the Referenced V shifts it
    fig.add_annotation(x=apex, y=0.04, text="neutral 0.5 (the “coin”)", showarrow=False,
                       font=dict(size=10, color="#475569"), yanchor="bottom")
    fig.add_trace(go.Scatter(x=[br], y=[0.0], mode="markers",
        marker=dict(symbol="diamond", size=10, color="#6d28d9",
                    line=dict(color="white", width=1)),
        hoverinfo="skip", showlegend=False))
    fig.add_annotation(x=br, y=0.16, text="base rate<br>(Referenced-V shift)", showarrow=True,
                       arrowhead=2, ax=0, ay=-18, font=dict(size=9, color="#6d28d9"))

    # Corner labels (axis reversed → success on the left, failure on the right)
    fig.add_annotation(x=0.97, y=1.06, text="Success (1)", showarrow=False, xanchor="left",
                       font=dict(size=11, color="#1A7A4A"))
    fig.add_annotation(x=0.03, y=1.06, text="Failure (0)", showarrow=False, xanchor="right",
                       font=dict(size=11, color="#C00000"))

    fig.update_xaxes(title="Chance of adequacy", range=[1.02, -0.02], tickformat=".0%",
                     gridcolor="#eee")   # reversed to match the app CAM
    fig.update_yaxes(title="Confidence", range=[-0.05, 1.12],
                     tickvals=[0, 0.5, 1], ticktext=["Low", "Med", "High"], gridcolor="#eee")
    fig.update_layout(height=340, margin=dict(t=20, b=44, l=58, r=14),
                      plot_bgcolor="white", showlegend=False)
    return fig

# Header-style Italian-flag chip (HTML, Windows-safe — country-flag emoji render as
# bare letters like "IT" on Windows). Matches the flag beside the app subtitle.
_ITALIAN_FLAG_HTML = (
    "<span style='display:inline-flex;align-items:center;height:13px;width:33px;"
    "border:1px solid #6B7280;border-radius:2px;overflow:hidden;vertical-align:middle;"
    "margin-right:8px;'>"
    "<span style='width:33%;background:#2e9d5b;height:100%;display:inline-block;'></span>"
    "<span style='width:34%;background:#f5f5f5;height:100%;display:inline-block;'></span>"
    "<span style='width:33%;background:#d64545;height:100%;display:inline-block;'></span></span>"
)


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
        "<b style='font-size:1.2rem;'>Theory & Guide</b><br>"
        "<span style='font-size:0.85rem;opacity:0.85;'>"
        "Everything you need to understand how E-POS works — the reasoning, the maths, the workflow, and the references."
        "</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;"
        "padding:10px 14px;margin-bottom:12px;font-size:0.9rem;color:#334155;'>"
        "<b>Where to start:</b> &nbsp;<b>Start here</b> if you're new · "
        "<b>Concepts</b> for the reasoning · <b>The maths</b> for full derivations "
        "(optional) · <b>In practice</b> when writing up · <b>Reference</b> to look up "
        "a term or paper.</div>",
        unsafe_allow_html=True,
    )

    (_tab_start, _tab_concepts, _tab_maths,
     _tab_practice, _tab_ref) = st.tabs([
        "Start here",
        "Concepts",
        "The maths",
        "In practice",
        "Reference",
    ])

    with _tab_start.expander("Quick-start: how to use E-POS in 5 steps", expanded=False):
        st.markdown("""
**E-POS is built around one insight:** the quality of your evidence matters more than your point-estimate probability.
The Italian Flag makes that quality visible. You enter evidence once, and three methods update automatically.

---

**Step 1 — Set your stance (Dashboard tab, top)**
> Choose **w** (0.0 = pessimistic, 0.5 = neutral / recommended, 1.0 = optimistic).
> This controls how the uncommitted *white* evidence contributes to POS.
> Use the company default (w = 0.5) unless you have a specific reason to deviate, and document it.

**Step 2 — Assess the Play pillars (Play tab)**
> For each pillar (Charge, Closure, Reservoir, Retention):
> - Set **S_for** = fraction of evidence supporting adequacy.
> - Set **S_against** = fraction of evidence against adequacy.
> - White = 1 − S_for − S_against (uncommitted / unknown).
> - Open **▶ Assess** for the full Chance Adequacy Matrix panel per element.

**Step 3 — Assess the Conditional elements (Conditional tab)**
> Same inputs, but now for prospect-specific sub-elements within each pillar.
> Set combination operators (ESL-ALL / ESL-ANY / ESL-IPT) per pillar group.

**Step 4 — Review results (Geological POS tab)**
> P(G, ESL), Uncertainty Index, CAM scatter, and the P(G, Classic) derived view
> all update here — no extra work required.

**Step 5 — Sign off (Dashboard tab, bottom)**
> Record analyst, date and QC review in the Audit Trail before exporting.
""")

    with _tab_concepts.expander("Why prospect risking is hard — independence, double-dipping & conditional risk",
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

### The independence assumption, and where it breaks

The classic POS multiplication

$$P(G) = P(\text{Charge}) \times P(\text{Reservoir}) \times P(\text{Closure}) \times P(\text{Retention})$$

is only valid if the pillars are **statistically independent**. In real geology they
rarely are; they share a common burial, structural and depositional history, so the
true joint probability can be **higher or lower** than the naive product. Treating
correlated risks as independent is one of the most common ways a prospect portfolio
ends up mis-calibrated.

Risks fall on a spectrum:

| Type | Example | Consequence for the product rule |
|------|---------|----------------------------------|
| **Truly independent** | Charge from an entirely separate kitchen vs. a structural-only closure risk | Product rule is fair |
| **Partially dependent** | Reservoir *presence* and reservoir *quality* (same depositional system drives both) | Product over-penalises; you risk the same geology twice |
| **Strongly conditional** | Source maturity → expulsion → migration path → trap charge | Must be chained as conditional probabilities, not multiplied as if separate |

---

### Double-dipping (risking the same geology twice)

The subtlest error is **semantic overlap** between elements. If "Reservoir presence"
already docks the score for a high-risk depositional setting, and "Reservoir quality"
then docks it *again* for the same lithological uncertainty, the prospect is penalised
twice for one underlying fact. The product rule has no way to know the two factors are
correlated; it just multiplies. Good practice:

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
  it from the others' justification text, so the audit trail shows the doubt was counted
  **once**.
""")

    with _tab_concepts.expander("Evidence Support Logic (ESL) — fundamentals", expanded=False):
        st.markdown(
            f"<div style='font-size:1.15rem;font-weight:600;margin-bottom:4px;'>"
            f"{_ITALIAN_FLAG_HTML}Evidence Support Logic (ESL)</div>",
            unsafe_allow_html=True,
        )
        st.markdown(r"""
### The Italian Flag

Each risk element is represented by three quantities that must sum to ≤ 1:

| Symbol | Name | Interpretation |
|--------|------|---------------|
| **S(H)** / S_for | Support For | Fraction of evidence actively supporting adequacy |
| **S(¬H)** / S_against | Support Against | Fraction of evidence actively contradicting adequacy |
| **W** = 1 − S_for − S_against | White / uncommitted | Evidence present but unresolved, or simply absent |

If S_for + S_against > 1 the element is **over-committed** (yellow flag). This is not an error; it means
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
> (= S_for + w × White) and **P(...)** for aggregated values: **P(G, ESL)** for the
> total prospect probability via ESL, **P(G, Classic)** for the Rose-style
> multiplicative result, **P(pillar)** for per-pillar combined chance, and
> **P(G | DFI, ESL)** for the Bayesian DFI-updated posterior. The bare term **POS**
> appears informally on plot axes and captions as shorthand for whichever point
> probability the plot shows; the precise reportable quantities are always one of
> the P(...) forms above.

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

    with _tab_concepts.expander("Theoretical foundations — Blockley (2013) & the Bayes / Italian-Flag hybrid", expanded=False):
        st.markdown(r"""
E-POS is not an ad-hoc scheme — its core is grounded in peer-reviewed uncertainty theory.
The Italian Flag comes from **David Blockley** (the originator), most directly:

- **Blockley, D.I. (2013)** — *Analysing uncertainties: Towards comparing Bayesian and
  interval probabilities.* Mechanical Systems and Signal Processing 37, 30–42.
- **Blockley, D.I. & Godfrey, P. (2000)** — *Doing it Differently.* Thomas Telford.
- **Cui, W.C. & Blockley, D.I. (1990)** — *Interval probability theory for evidential support.*
- **Shafer, G. (1976)** — *A Mathematical Theory of Evidence* (Bel/Pl, Dempster's rule).

### 1 · FIR — three orthogonal kinds of uncertainty
Blockley argues the usual *aleatory vs epistemic* split is too coarse. Uncertainty has
three independent axes — **F**uzziness, **I**ncompleteness, **R**andomness. E-POS spans all
three:

| Axis | Blockley | In E-POS |
|---|---|---|
| **F** — fuzziness (vagueness of definition) | verbal "levels of definition" | verbal categories, discernibility buckets, the CoS scale |
| **I** — incompleteness ("don't know") | the **white** of the flag | `White`, the stance `w`, the Bel/Pl envelope, the Uncertainty Index |
| **R** — randomness | classical probability | the Bayes DFI likelihoods (Gaussian densities), volumetrics |

### 2 · Why the Italian Flag (not plain probability)
Classical probability carries a **completeness axiom**: beliefs on the sample space must sum
to 1, forcing $p(\neg H) = 1 - p(H)$; there is no way to say *"don't know."* Blockley drops
completeness and represents a belief as an **interval**:

$$p(H) = [\,g,\; 1-r\,] = [\text{Bel},\;\text{Pl}], \qquad p(H)\neq 1-p(\neg H)$$

with **g** (green) = support *for*, **r** (red) = support *against*, **w** (white)
$= 1-g-r$ = incompleteness. **This is exactly E-POS's flag** (`S_for`, `S_against`, `White`).

### 3 · The Rosetta Stone — Blockley's Table 5, mapped to E-POS
E-POS uses **both** frameworks the paper compares, in different places:

| | **Bayesian** | **Italian Flag** | **Where E-POS uses it** |
|---|---|---|---|
| Measure | one number | interval `[g, 1−r]` | ESL gives the interval; **Policy P** reads a point |
| Negation | $p(\neg H)=1-p(H)$ | $p(\neg E)\neq 1-p(E)$ | White decouples; `S_against` assessed separately |
| Output | $p(H\mid E)=\dfrac{p(E\mid H)\,p(H)}{p(E)}$ | $p(H)=p(H\mid E)\,p(E)+(1-p(\neg H\mid\neg E))(1-p(E))$ | **DFI update** = Bayes row; **ESL rollup** = Flag row |

### 4 · E-POS is a deliberate hybrid
The geological **prior** is pure Italian-Flag (incompleteness-aware: `S_for/S_against/White`,
Bel/Pl, stance `w`). The **DFI update** is Bayesian (the likelihood ratio R). The stance
slider is literally *where in Blockley's interval you read the point*: `w=0` → Bel,
`w=1` → Pl, `w=0.5` → midpoint.

> **The key tension Blockley names:** a Bayesian update "does not allow the decision maker to
> acknowledge incompleteness explicitly." So the DFI update **collapses the Bel/Pl envelope
> onto a point** — the white is lost. That is why E-POS keeps showing the Bel/Pl band beside
> the posterior and offers the **Dempster–Shafer prototype** (which carries the interval
> through the update). Both are conscious answers to this paper.

### 5 · The dependence warning — the root of E-POS's caution
Blockley stresses that **Dempster's rule = multiplication = an assumption of independence**,
"not warranted except where independence is known," and that it mishandles **conflict** (the
Zadeh problem). His practical answer is **pairwise-comparison** combination. This single
warning is the intellectual root of E-POS's whole anti-double-counting posture: the
characteristic-attribute correlation discount **ρ**, the ESL dependency modes, the
Dempster–Shafer conflict-**K** warning, and the *"why risking is hard — double-dipping"*
section all descend from it.

### 6 · Suggested for a future update — the *fuzzy* Italian Flag
Blockley's final idea (his Fig. 5) is a **fuzzy Italian Flag**: when several *disagreeing*
evidence sources each imply a different `[Bel, Pl]`, shade the flag with **gradations** of
green→white→red built from the multiple pairwise bounds, rather than a single hard interval.
E-POS currently uses one `[Bel, Pl]` per element. **A graded/fuzzy flag (and optionally the
full pairwise-comparison combination operator) is logged as a candidate for a future
release** — useful where one pillar is informed by multiple conflicting lines of evidence.
""")

    with _tab_concepts.expander("Bayesian updating in 2 minutes — a non-geological primer", expanded=False):
        st.markdown(r"""
Before the DFI maths, the **one idea** behind every probability update in E-POS:

> **A Bayesian update revises a prior belief in light of new evidence; it does
> not replace it.** Strong evidence on top of a weak prior still gives a guarded
> answer. Evidence acts as a *multiplier on the odds*, not a verdict.

The cleanest form uses **odds** and a **likelihood ratio (LR)**:
""")
        st.latex(r"\underbrace{\text{posterior odds}}_{\text{after evidence}}"
                 r"\;=\;\underbrace{\text{prior odds}}_{\text{before evidence}}"
                 r"\;\times\;\underbrace{\text{LR}}_{\text{strength of evidence}}")
        st.markdown(r"""
**LR** = how much more likely the observation is if the hypothesis is true than if
it is false. LR > 1 pushes the belief up; LR < 1 pushes it down; LR = 1 changes
nothing.

#### Worked example — a medical test (the classic base-rate lesson)
A disease affects **1 %** of people (the *prior*). A test is **99 %** sensitive
(detects true cases) and has a **5 %** false-positive rate. You test **positive** —
what is the chance you actually have it?

| Step | Value |
|------|-------|
| Prior odds | 0.01 / 0.99 ≈ **0.0101** |
| Likelihood ratio | 0.99 / 0.05 ≈ **19.8** |
| Posterior odds | 0.0101 × 19.8 ≈ **0.20** |
| **Posterior probability** | 0.20 / 1.20 ≈ **17 %** |

A *99 % accurate* test still leaves you **~17 %** likely to have the disease — because
the **base rate was low**. The evidence multiplied the odds ~20×, but starting from a
tiny prior. **The prior matters as much as the evidence.**

#### How this maps to E-POS
| Medical example | E-POS DFI update |
|---|---|
| Disease prevalence (prior) | Geological **P(G)** (ESL or Classic) |
| Test result (evidence) | The **DHI / DFI** observation |
| Likelihood ratio | **R** (= R_DFI / R_char / custom R) |
| Post-test probability | **P(G \| DFI)** posterior |

This is *exactly* the engine behind the DFI update — only the likelihood ratio is
computed from seismic amplitude statistics instead of a clinical trial.

➡️ *For the full geological derivation (how R comes from the likelihoods), see the
**The maths** tab.*

---

#### A note for the Bayesian purist: are the prior and the likelihood independent?

A fair objection is that the geological prior P(G) and the DFI likelihood P(DFI | HC)
both describe the same rock, so they are not independent. The answer has two parts.

**Bayes does not require them to be independent.** If the DHI were independent of whether
hydrocarbons are present it would carry no information. The geology *creating* the seismic
response is the very reason a DHI is diagnostic. What Bayes actually requires is
**conditional independence given the true state**. Writing $S$ for the underlying state
(hydrocarbons in an effective reservoir), updating the geological prior by a DHI likelihood
is valid when

$$P(\text{DFI}\mid S,\ \text{geological evidence}) = P(\text{DFI}\mid S),$$

that is, once the true state is known the seismic and the geological evidence tell you
nothing further about each other. This is the same naive-Bayes / conditional-independence
assumption that governs the characteristic-attribute discount **ρ** and Blockley's
dependence warning.

**Two ways it can fail, and these are the real risks:**

1. **Using the DHI twice (avoidable).** If a bright amplitude has already raised a
   geological pillar (Charge or Reservoir), then applying the DHI again as a likelihood
   counts the same observation twice and inflates the posterior. E-POS treats the DHI as
   *Auxiliary evidence* held out of the geological pillars, and warns when DHI-type rows are
   embedded inside a pillar. Use the DHI in the Bayesian update only.
2. **A population-calibrated likelihood that is not transportable (subtle, partly
   unavoidable).** The calibration gives a population-average P(DFI bright | HC), but
   brightness within "HC" depends on reservoir quality, depth, lithology and tuning, the
   same factors that drive the geological prior. A good-reservoir prospect tends to give a
   brighter DHI when charged, so a bright DHI there is *less surprising* than the population
   number implies. A flat likelihood then over-credits the evidence and the posterior is
   mildly overconfident, the same direction of error as ρ double-counting.

**What keeps it valid in practice:**

- Build the geological prior from evidence orthogonal to amplitude (trap geometry, regional
  charge and migration, source maturity) so the residual coupling is small.
- Prefer the **case-conditioned** likelihood P(DFI | case) of the conceptual DHI model and Custom multi-case
  methods. Conditioning on reservoir evaluability and fluid is exactly conditioning on the
  covariates that couple the prior and the likelihood, which is the principled fix for
  risk (2), rather than a flat P(DFI | HC).
- Down-weight strong DHIs with the Volume Weight V, discernibility, and the R cap.

**Standing caution:** when reservoir risk is low (so amplitude and reservoir co-vary), read a
strong DFI posterior as a slight upper bound on confidence, and never let the bright spot
leak back into the geological pillars.

*Theoretical backing:* Pearl (causal Bayesian networks: the common-cause structure and
conditional independence / d-separation); the naive-Bayes conditional-independence
assumption and its tendency to overconfidence; likelihood transportability and external
validity (Pearl and Bareinboim); Simm (2016) on amplitude reliability being rock and fluid
dependent; Blockley (2013) on managing dependence.
""")

    with _tab_concepts.expander("Chance Adequacy Matrix (CAM) — interpretation guide", expanded=False):
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

### Reading the 4-segment Classic range bar

The **Final Prospect POS** table draws each ESL probability as a 4-segment horizontal
bar that decomposes the `[Bel, Pl]` envelope. Left → right:

| Segment | Colour | Width | Meaning |
|---|---|---|---|
| 1 | **dark green** | `Bel = S_for` | **committed success** — the floor, regardless of stance |
| 2 | **light green** | `Policy P − Bel` | **stance contribution** — white evidence credited to success at the current `w` |
| 3 | **light grey** | `Pl − Policy P` | **undecided white** still available if `w → 1` |
| 4 | **dark red** | `1 − Pl = S_against` | **committed failure** — lost even at the most optimistic stance |

- dark green **+** light green **= Policy P** (the point estimate shown above the bar)
- dark green **+** light green **+** light grey **= Pl** (plausibility / optimistic ceiling)
- A larger light-green + grey block means more of the result rests on **stance and unknowns**,
  not on hard evidence. The same colour key appears as a one-line legend beneath the
  Final POS table.

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
        st.info("Open the **Geological POS tab → Chance Adequacy Matrix** to interact with the live plot.")

    with _tab_concepts.expander("The Risking V & the \"no-go\" zone (Rose / ExxonMobil)", expanded=False):
        st.plotly_chart(_risking_v_schematic(), use_container_width=True)
        st.caption(
            "**Schematic Risking V.** Apex at the original symmetric **neutral 0.5 — the “coin”** "
            "(no data); rising confidence lets the estimate move out to the **success (1)** or "
            "**failure (0)** corners — the two arms. The fill is coloured by chance on the shared "
            "CoS scale; the **x-axis is reversed (100%→0%)** to match the app's CAM. The grey "
            "upper-centre is the classic **no-go** (confident but middling) — superseded for a "
            "probability. The purple ◆ marks where ExxonMobil's base-rate-aware **Referenced V** "
            "shifts the apex (here, the current base-rate stance)."
        )
        st.markdown(r"""
### The Risk Matrix idea, and why it looks like ESL

Rose's *chance-adequacy* matrix and ExxonMobil's **Risk Matrix → Risking V** both start from the
same insight E-POS is built on: **separate the favourability of the *known* geology from the
*confidence* you have in it**, i.e. separate committed evidence (green / red) from the
uncommitted **white** band. Plotting *chance of adequacy* against *confidence* (≈ commitment **C**)
produces a **V**: at low confidence you are pinned near the base rate (the apex); as confidence
rises you may move out toward the **success (1)** or **failure (0)** corners — the two arms of the V.

### The classic "no-go" zone

In the original Risk Matrix the **upper-centre is forbidden**: *with high confidence you "cannot sit
on the fence; you must be close to 0 (failure) or 1 (success)."* A confident-but-middling estimate
was treated as internally inconsistent.

### Why it is a concept to challenge — ExxonMobil retired it themselves

ExxonMobil's own 2018 review flags the limitation directly: the no-go rule is **"only applicable if
the state of nature is 0 or 1."** It holds for a **single binary outcome** (this trap either has
reservoir or it does not), but **not for a probability / success-ratio**: a high-confidence estimate
of a *chance* can legitimately be **any value in [0, 1]**; you can be highly confident the success
ratio of a play is 67 % (8 of 12 analogues worked). Their slide 11 makes the deeper point — *"why do
we assume geology is like a coin?"* Knowing nothing, you should revert to the **base rate
(generally ≠ 0.5)**, not to a neutral 50/50.

**Because E-POS reports P(G) — a probability, not a binary state — the strict no-go zone does not
apply.** It is shown on the CAM only as a *faint, labelled reference region* ("legacy no-go —
binary-outcome only"), never as a forbidden area.

### How ESL supersedes the no-go

ESL replaces the binary boundary with a **continuous, visible representation**:

- The **Bel–Pl envelope** `[S_for, 1 − S_against]` **is the pair of V arms** — the defensible POS
  bounds at the current commitment, drawn directly on the CAM.
- The **white fraction** and the **stance _w_** make explicit *how much of the point estimate rests
  on the unknown*. A confident-but-middling element simply has a **narrow** interval centred on a
  mid value (a genuine, well-evidenced "uncertain"); a low-commitment element has a **wide**
  interval — the same information the no-go was groping for, but quantified rather than forbidden.

The CAM's **"Risking-V overlay"** toggle draws the V arms, the labelled legacy-no-go reference, and a
**stance-driven flag** on elements whose POS sits far above Bel (the number leans on the white band).

> **Base rate as the neutral (forward link).** ExxonMobil's "geology is not a coin" critique applies
> directly to the default stance **w = 0.5**, which splits the white band 50/50. The **Base-rate
> stance** (Dashboard → Stance) reverts the white band to the prospect base rate instead —
> `Policy P = S_for + base_rate · White`, so "knowing nothing" defaults to the base rate, not a coin.

### References

- **Hood, K. & Steffen, K. (2018)** — *The Risking V: One Company's Evolution of Risking Concepts and
  Applications.* ExxonMobil Risk Coordinator Workshop. *(Internal/conference presentation — cited for
  its concepts; not bundled with E-POS.)*
- **Rose, P.R. (2001)** — *Risk Analysis and Management of Petroleum Exploration Ventures*, AAPG
  Methods in Exploration 12.
- **Otis, R.M. & Schneidermann, N. (1997)** — A process for evaluating exploration prospects
  (the ROSE chance-adequacy matrix).
""")

    with _tab_concepts.expander("P(G, Classic) — the multiplicative method", expanded=False):
        st.markdown(r"""
### What P(G, Classic) does

P(G, Classic) — the Rose-style probability — is the **product of all pillar values**:

$$P(G, \text{Classic}) = P(\text{Charge}) \times P(\text{Closure}) \times P(\text{Reservoir}) \times P(\text{Retention})$$

Within each pillar, sub-elements are combined using the **minimum** (weakest link) or a product,
depending on the Classic operator setting.

> **What the probability is conditional on.** Throughout E-POS, P(G) is the probability of a
> discovery of **at least a minimum testable prospect volume** (the smallest accumulation worth
> completing and testing), not the probability of *any* hydrocarbons at all. Two prospects with
> the same geology can carry a different P(G) if they set that minimum volume differently, so the
> threshold should be stated alongside the number.

### Relationship to ESL

E-POS derives P(G, Classic) **directly from your ESL evidence**; you do not enter separate
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

See results in **Geological POS tab → Derived Methods → P(G, Classic)**.
""")

    with _tab_concepts.expander("Why P(G, ESL) ≠ P(G, Classic) — the four structural reasons", expanded=False):
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

Same data. Same operator intent. **0.585 vs 0.563**, and the gap widens with more elements
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
between them is the quantified evidence of your uncertainty, and that belongs
in the risk narrative, not hidden in a single number.
""")

    with _tab_concepts.expander("Current assessment — ESL combination hierarchy", expanded=False):
        st.caption(
            "Visual representation of how evidence flows from sub-elements through pillar combinations to P(G)."
        )
        from components.hierarchy_chart import render_esl_hierarchy
        render_esl_hierarchy(play, conditional)

    # ═══════════════════════════════════════════════════════════════════════
    # 🌊 BAYESIAN DFI UPLIFT — full theory + workflow + pitfalls + reporting
    # ═══════════════════════════════════════════════════════════════════════
    with _tab_maths:
        st.markdown(
            "<div style='background:linear-gradient(135deg,#1e3a8a,#3b82f6);color:#fff;"
            "padding:14px 18px;border-radius:8px;margin:4px 0 10px;'>"
            "<b style='font-size:1.05rem;'>Bayesian DFI Update — the maths</b><br>"
            "<span style='font-size:0.82rem;opacity:0.9;'>"
            "How a seismic Direct Fluid Indicator updates the geological prior via Bayes' "
            "theorem — the two full derivations below. Workflow & decision tree are under "
            "<b>Start here</b>; pitfalls & reporting under <b>In practice</b>."
            "</span></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "🔎 All DFI abbreviations (DFI, DHI Index, R, V, LSG, Eval-Res, …) "
            "are defined in the unified **📖 Glossary & Abbreviations** on the "
            "**📖 Reference** sub-tab."
        )

    with _tab_maths.expander("Bayesian DFI — full derivation (light-stats friendly)", expanded=False):
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

> **What is the prior $P(G)$ here?** It is *not* a fresh number; it is the geological result
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

### Step 4 — Likelihood per outcome (the conceptual DHI model Gaussians)

Each of the 8 outcomes maps to one **DHI calibration class**. Each class has a calibrated **mean** $\mu_k$
and **standard deviation** $\sigma_k$ for the DHI Index distribution. The likelihood of observing
DHI Index $x$ given outcome $k$ is the Gaussian PDF:

$$
L_k(x) \;=\; \frac{1}{\sigma_k\sqrt{2\pi}}\;\exp\!\left[-\,\frac{(x-\mu_k)^2}{2\sigma_k^2}\right]
$$

The outcome-to-class mapping mirrors the workbook:

| Outcome | DHI class |
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

> **One sigma per class.** Each outcome class carries a single conceptual mean and sigma
> (round, illustrative values, not fitted to any dataset). They are editable on the Setup page.

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

### Step 7 — R_DFI (DHI-Index strength) and DHI Volume Weight V

We define two diagnostic ratios that summarise *how strong the DFI evidence is*, independently of the prior:

$$
E[L \mid \text{failure}] \;=\; \frac{\sum_{k\ne 1} L_k\cdot \pi_k}{\sum_{k\ne 1} \pi_k}
\quad\text{(failure-weighted average likelihood)}
$$

$$
\boxed{\;R_\text{DFI} \;=\; \frac{L_\text{succ}}{E[L \mid \text{failure}]}\;}
\qquad
\boxed{\;V \;=\; \frac{L_\text{succ}}{L_\text{succ}+E[L\mid\text{failure}]}\;}
$$

**R_DFI** (DHI-Index strength) is a likelihood ratio:
- **R_DFI > 1** → observation favours success (uplift expected)
- **R_DFI = 1** → neutral
- **R_DFI < 1** → observation favours failure (downgrade expected)
- **R_DFI ≫ 1** (e.g. 5+) → strong evidence; large uplift even with weak priors

> **Two different R's — don't conflate them.** `R_DFI` here is the likelihood ratio from the
> **Conceptual DHI Index (experimental)** Gaussian calibration — a conceptual model reverse-engineered
> from public public presentation material; it expects a *pure DFI-strength* input, not a raw
> raw composite DHI score (see the warning on that Setup page). The
> **characteristic-scoring** pathway computes a *different* ratio, `R_char` = ∏ LRᵢ, as a naive
> product of per-attribute likelihood ratios (Monigle 2025). Both feed the same Simm 2-state
> Bayes update, but they are computed on different scales and are **not** interchangeable.

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
the geology is right (with probability 1−V), and produces a **bimodal** posterior (a sharp peak at
the DFI pick sitting on top of a broad geological pedestal).

That's the wrong cognitive model:
- The geology is not "right or wrong"; it just provides a defensible range that includes the answer.
- The DFI is not "right or wrong" either; it provides a more precise indication, partially trustworthy.
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

**Bottom line:** one number, V, does two jobs; it updates P(G) on the risk side and weights the
volume blend on the resource side. Record the V used (shown on the DFI Results tab) in the same
audit-trail line as P(G | DFI).

---

### Step 8 — Why the posterior collapses the Bel/Pl envelope

The geological prior P(G, ESL) carries an uncertainty envelope `[Bel, Pl]` derived from the Italian-flag
white mass. After the DFI update, that envelope is gone — the posterior is a **point estimate**.

Why? The Bayes update conditions on observed evidence: *given this DFI, the answer is one number*.
Carrying the white uncertainty through Bayes would require defining a likelihood over the white mass
itself (a prior on the prior — possible but adds another layer of subjective input). E-POS adopts the
pragmatic convention used in the conceptual DHI model workbook: update the point-estimate prior, report the posterior
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

For **ESL attribution** — the prior vs posterior **Italian-flag** view shown on every DFI source —
there are two modes, chosen in **Dashboard → ⚙ Advanced — DFI → ESL per-pillar attribution**:

- **Option A** preserves each pillar's commitment $C = S_\text{for}+S_\text{against}$ (the **White is
  held fixed**) and only rebalances green/red to hit the new pillar Pg. Simple and conservative, but a
  *heuristic*: it does not correspond to a coherent update of the belief interval.
- **Option B** (default) updates the belief interval $[\text{Bel},\text{Pl}]$ itself — it recomputes the
  posterior separately at $w=0$ (Bel side) and $w=1$ (Pl side), so the whole interval moves and the
  White can legitimately change.

**Which is mathematically most correct? → B.** The Italian Flag is an *interval* (imprecise) probability
with $\text{Bel}=S_\text{for}$ and $\text{Pl}=1-S_\text{against}$. With a precise likelihood ratio $R$,
the coherent (generalised-Bayes) update of an interval is exactly
$[\,\text{update}(\text{Bel}),\ \text{update}(\text{Pl})\,]$ — which is what B computes. A is a defensible
simplification, not a coherent interval update. *(Caveat: a sharp Bayesian posterior has no intrinsic
incompleteness, so any posterior White is a modelling convention — see Step 8.)*

The flags are shown for **all** DFI sources. The DHI-Index path uses the 8-outcome posterior; the
single-R sources (**Custom R tool** and **Characteristic**) update through one likelihood ratio, so
Option B for them updates the Bel and Pl headline products by $R$ and spreads each endpoint change across
the 8 pillar slots by equal log-share (the scalar-R interval update).
""")

    with _tab_maths.expander("Pillar-resolved DFI, which pillar does the anomaly move? (GeoX / Martinelli)", expanded=False):
        st.markdown(r"""
A single likelihood ratio R moves the **headline** P(G, ESL), but it hides *where* the
update lands. A DFI is a **fluid** indicator: it can only sense (a) whether a reservoir
exists and (b) what fluid fills it. It can **never** tell which of charge / trap /
retention failed. So the most a DFI can resolve is **two geological channels**:

| Channel | E-POS pillars |
|---|---|
| **Reservoir** | Reservoir (whole pillar) |
| **HC-system** | Charge · Closure · Retention (combined — never separable by a DFI) |

#### The outcome tree (single segment)

```
   Reservoir present (P_res):  HC          → L_HC        SUCCESS
                               brine/LSG   → L_fluidfail FLUID failure
   Reservoir absent (1−P_res): non-reservoir → L_nonres  RESERVOIR failure
```

The **fluid** update is a clean likelihood ratio $L_{HC}/L_{fluidfail}$ acting on the
combined Charge·Closure·Retention. The **reservoir** update is *coupled*; it compares
the non-reservoir curve against the *whole* reservoir-present branch, so the two cannot
be done as independent 1-D steps. The correct device is a **joint update over the three
leaves**, from which the pillar marginals fall out (exactly GeoX's "DFI modified risk").

Two design choices make it consistent with ESL:
- **Residual HC-system prior:** $P_{hc} := P(G,ESL)/P_{res}$, so $P_{res}\cdot P_{hc}$
  reconstructs the headline exactly (no drift, no double-counting of stance/discernibility).
- **In-group split (Martinelli rule):** the updated HC-system marginal is shared back onto
  Charge / Closure / Retention by **preserving their pre-DFI log-proportions**.

The **failure split** (fluid-failure vs non-reservoir) is governed by the **Reservoir
pillar** $(1-P_{res})$, *not* a free weight, so for the pillar-resolved path the joint
engine is the source of truth for the headline too.

#### Why this matters — a supportive anomaly can still *degrade* reservoir

Worked example (the patent's, 3-leaf reduction): prior P(G)=**7.2%**, P_res=**0.50**,
likelihoods $L_{HC}=0.8,\ L_{fluidfail}=0.3,\ L_{nonres}=0.5$.

> **P(G) rises 7.2% → 13.2%**, yet **Reservoir falls 0.50 → 0.43**.

The anomaly is *partly explained by a possible non-reservoir cause*, so the headline
up-move masks a reservoir down-move. The aggregate-R view cannot show this — the
pillar-resolved panel can.

#### Where E-POS applies it
- **Custom multi-case** → full two-channel attribution on the **DFI Results**, **Result**
  and **Final Prospect POS** pages (prior→posterior per channel/pillar). It is a *parallel*
  post-DFI view: the per-pillar **prior inputs are never overwritten**, so the geological
  prior the analyst books stays intact.
- **DHI-Index ** keeps its richer **8-outcome** headline, and its per-pillar
  attribution is now the **channel-resolved** split too — the Reservoir marginal is the
  exact `P(reservoir present | DFI)` from the 8 outcomes, replacing the earlier
  *equal-spread* attribution (which moved every pillar the same way and could not show a
  reservoir falling while POS rose). The mass-level play/cond Italian-flag tables remain
  below it for detail.
- **Characteristic / Custom dual-case** are single-curve models, so they have **no channel-resolved**
  (reservoir vs HC-system) split — the headline updates as one number. The mass-level ESL **flag**
  attribution is still shown for them (the single $R$ spread across the 8 pillars, Option A or B).

#### Scope (single segment) & IP
This is the **single-segment** case of US 10,451,762 B2 (Martinelli, Stabell, Langlie;
GeoX) — standard Bayes + marginalisation. E-POS does **not** implement the patent's novel
**multi-segment** DFI-dependency-group / reference-DFI correlation method. *"Segment"* is a
GeoX term; E-POS is single-segment only. **No patent claim is practised.**
""")

    with _tab_maths.expander("Alternative: Characteristic scoring (Simm 2016 + Monigle 2025)", expanded=False):
        st.markdown(
            "The 8-outcome Bayes above is one of **two** pathways the app supports "
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
            "Monigle reports a **success rate** per verbal category, e.g. 82 % of drilled prospects "
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
            "**Caveat (independence assumption).** The six attributes correlate in reality, e.g. "
            "a prospect with a strong anomaly tends also to show good amplitude terminations. "
            "Treating them as independent over-counts the evidence and can push R far above what "
            "the joint data support. Monigle 2025 moved to a Supervised Machine Learning model "
            "precisely to capture these correlations. **E-POS cannot replicate their proprietary "
            "ML** (185-prospect training set); the naive product is a transparent, fully-auditable "
            "analyst-grade proxy — accuracy traded for reproducibility. To guard the over-count it "
            "uses a **discernibility-aware cap**:"
        )
        st.markdown(
            "| Discernibility | R_char cap | Rationale |\n"
            "|---|---|---|\n"
            "| high | [1/10, 10] | composite of 5 attributes, trustworthy geophysics — wide |\n"
            "| moderate | [1/6, 6] | intermediate |\n"
            "| low / absent | [1/3, 3] | Simm 2016 single-DFI bound |\n"
        )
        st.markdown(
            "Simm's [1/3, 3] is calibrated to a *single* DFI line of evidence, but R_char is a "
            "*composite* of five attributes — effectively several lines, so a flat single-line "
            "cap is too tight when the data is genuinely discernible. Widening it with "
            "discernibility lets an expected-but-absent DHI produce the strong downgrade that is "
            "Monigle 2025's signature result (their **Prospect B: GCOS 46% → iCOS 8%**), which the "
            "flat cap cannot express — while keeping low-discernibility prospects conservative. "
            "*(Caveat: the low-DHI region is poorly constrained — Monigle drilled <10 weak-DHI "
            "successes, so treat strong downgrades as directional.)*"
        )
        st.markdown("---")
        st.markdown("#### Step C4b — Independence discount ρ (a principled alternative to the cap)")
        st.markdown(
            "The cap is a *blunt* guard: it lets the naive product run unchecked until it hits a "
            "hard wall. A more principled correction discounts the evidence **continuously** by an "
            "assumed average pairwise correlation ρ between the attributes, using the classic "
            "**design-effect / effective-sample-size** argument. For *k* attributes with average "
            "correlation ρ, the effective number of *independent* attributes is"
        )
        st.latex(r"k_\text{eff} \;=\; \frac{k}{1 + (k-1)\,\rho}")
        st.markdown(
            "so the log-evidence is scaled by the **effective-evidence exponent** "
            "f = k_eff / k, giving a discounted ratio:"
        )
        st.latex(r"f \;=\; \frac{1}{1 + (k-1)\,\rho}, \qquad "
                 r"R_\text{disc} \;=\; \exp\!\big(f \textstyle\sum_k \ln \text{LR}_k\big) \;=\; R_\text{raw}^{\,f}")
        st.markdown(
            "**ρ = 0 → f = 1** → independent attributes, naive product unchanged. **ρ → 1 → f → 1/k** "
            "→ fully redundant, the *k* attributes count as a single line of evidence. The app "
            "**defaults to ρ = 0.3** — a mild, conservative discount appropriate for correlated "
            "seismic-amplitude attributes; set it to 0 to recover the pure naive product. Note this "
            "is an exponent on R, exactly "
            "like the discernibility squash below — the two compose as "
            "$R_\\text{eff} = R_\\text{raw}^{\\,f \\cdot d}$ before the cap. The discount is exposed "
            "as the **Assumed attribute correlation ρ** slider in the DFI Setup advanced controls; "
            "with ρ > 0 the cap rarely binds, because the statistics, not a hard wall — are doing "
            "the work."
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
        st.info(
            "**Note — discernibility acts twice, and that is deliberate.** The bucket sets *both* "
            "the cap width (Step C4) *and* the exponent d here. Composed, they give a smooth, "
            "monotone ceiling on how far the DFI can ever move the prior — the *effective* maximum "
            "R_eff per bucket is **cap^d**:\n\n"
            "| Discernibility | cap | d | effective max R_eff |\n"
            "|---|---|---|---|\n"
            "| high | 10 | 1.0 | 10 |\n"
            "| moderate | 6 | 0.6 | 6^0.6 ≈ **2.9** |\n"
            "| low | 3 | 0.3 | 3^0.3 ≈ **1.4** |\n"
            "| absent | 3 | 0.0 | **1.0** (no effect) |\n\n"
            "So the headline strength a DFI can ever reach is governed by this single ladder; "
            "the cap and the squash are two facets of one discernibility control, not two "
            "independent assumptions."
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
        st.markdown("#### When to use this path vs Conceptual DHI Index (experimental)")
        st.markdown(
            "| Use case | Choose | Why |\n"
            "|---|---|---|\n"
            "| You have a **pure DFI-strength index** (geology neutralised) | **Modified DHI "
            "Index ** | 8-outcome decomposition gives per-pillar attribution + fluid-class "
            "diagnostics. *Do not feed a raw composite DHI index; see the warning on that page.* |\n"
            "| You don't have a calibrated DHI database or want a stand-alone assessment | **Characteristic scoring** | "
            "Six verbal sliders + public Monigle 2025 calibration; no external tool required. |\n"
            "| You want a sanity check on a conceptual R | Run both; compare | The two R values "
            "should be of similar magnitude. Large disagreement = investigate which attributes / "
            "fluid mix is driving the gap. |\n"
            "| Reservoir-presence is the dominant risk (e.g. wildcat sub-salt) | Either | Both "
            "pathways give muted updates in this case, correctly reflecting that the DFI can't see "
            "what isn't there. |"
        )


    with _tab_start.expander("How to use this tool — step-by-step workflow", expanded=False):
        st.markdown(r"""
### Prerequisites

Before opening the Bayesian DFI Update tab you should have:

1. **A complete ESL assessment** — Play and Conditional tabs filled in, P(G, ESL) showing on the Dashboard.
2. **A DHI Index value** for the prospect, computed from the DHI/amplitude scoring workflow (typically a single integer in the range −23 to +50).
3. **A view on the fluid-failure split** — what fraction of failed-prospect outcomes (in your basin/play) is water vs LSG vs other fluids? Defaults are 80/20/0 if you have no calibration.
4. **A fluid type** — does the prospect target oil, gas, oil+gas, or generic hydrocarbons?

> If you don't have a DHI Index, **don't toggle DFI on**. The Bayes update assumes the DHI Index is a
> calibrated number from a consistent scoring system. Without that, the posterior is meaningless.

---

### Step 1 — Toggle DFI on (Dashboard tab)

Find the **"DHI prospect?"** toggle just below the Stance slider. Default is OFF.

When you toggle ON for the first time, E-POS sets defaults: DHI Index = 8, water = 0.50, LSG = 0.20, other = 0.30, fluid type = Success, ESL attribution = B, SD mode = upper. These are **session-sticky** — your subsequent edits persist for this prospect.

---

### Step 2 — DFI Setup sub-page

Navigate to the **Bayesian DFI Update** tab → **DFI Setup**. You'll see four panels:

**A. DHI Index input**
> Enter the integer score from your your DHI-scoring workflow scoring sheet. Hover the help icon for the typical reference table.

**B. Fluid mix**
> Three sliders summing to 100%. Set:
> - **Water** = expected fraction of failures that are wet.
> - **LSG** = expected fraction that are low-saturation gas (mimic DFIs).
> - **Other** = residual (CO₂, residual oil, brine inversion, etc.).
> If unsure, leave defaults. Document your choice in the audit trail.

**C. Fluid type & SD mode**
> - Fluid type: `Success` (pooled), `Oil`, `Oil+Gas`, `Gas` — pick the closest match to your prospect's primary target. The Bayes update uses the corresponding DHI class for the success-likelihood Gaussian.
> - SD mode: leave `upper` unless you have a specific reason to tighten the likelihoods.

**D. Bell-curve preview**
> Visual check of the five Gaussian likelihoods overlaid with your DHI Index as a vertical line. **Sanity check:** is your DHI Index in a region where the Success curve is meaningfully above the failure curves? If not, the update will be small.

> 🛈 **Tip:** if you don't know what to put for fluid mix, just toggle the **Sensitivity Sweep** on the DFI Results tab and look at how much the posterior moves across the 100%/0% water family. If the family is tight, your choice doesn't matter much.

---

### Step 3 — DFI Results sub-page

Four blocks, top to bottom:

1. **Headline tiles** — prior vs posterior, ESL and Classic.
2. **Per-pillar attribution**, which pillar the update raised or lowered the most — including the
   prior vs posterior **Italian-flag** table (S_for / S_against / Policy P per pillar, Option A or B).
3. **Posterior trajectory plot** — 4 curves: P(G, ESL) prior/posterior and P(G, Classic) prior/posterior, swept across stance w. The vertical dashed line is your current stance.
4. **Sensitivity sweep** — configurable: pick X-axis variable (DHI Index, Reservoir Pg, stance w, etc.) and curve family (water fraction, LSG fraction, etc.). Use this to *stress-test* the posterior against assumptions.

---

### Step 4 — Final Prospect POS (top-level tab)

This is the **reportable view**, now its own **top-level tab** (no longer under the Bayesian DFI Update tab): pillar table (prior), DFI diagnostic strip (DHI + R + V + mix), posterior bar with prior→posterior shift, and a 2×2 method×prior/posterior table. With the DFI update disabled it shows the geological POS instead, so it is always your single sign-off page. Download as a text summary for inclusion in your prospect write-up.

---

### Step 5 — Document and sign off

In the Audit Trail:
- DHI Index value and source (scoring method, calibration version, date, who scored it).
- Fluid mix percentages and their justification.
- Stance w and SD mode used.
- Final P(G | DFI, ESL) and P(G | DFI, Classic), plus the spread between them.
""")

    with _tab_start.expander("DFI decision tree — should I apply the update?", expanded=False):
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
              Q2.  Has someone scored the prospect using the your DHI-scoring workflow
                   rubric to produce a numeric DHI Index?
                    │
                    ├─ No  → Either (a) score it yourself using the
                    │        DHI-scoring checklist, or (b) skip DFI Bayes.
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

You can still use E-POS — just **leave the toggle OFF**. The dashboard will show only the ESL and Classic priors. The audit trail should record *why* DFI was not applied (no seismic, no DHI score, or judgement that it is uninformative).
""")

    with _tab_practice.expander("DFI pitfalls & calibration tips", expanded=False):
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

If the prospect's main risk is reservoir presence (e.g., wildcat in a poorly-imaged sub-salt setting), the DHI signature is dominated by the `Reservoir_failure` and `Non-Eval-Res` classes, which look very similar to many failure modes. The Bayes update will produce a small uplift even at high DHI Index, which is **correct behaviour**: the DFI can't tell you about something it can't see.

---

### Pitfall 6 — Calibration drift

A conceptual calibration is bundled by default. If you are working in a basin not well represented by your own calibration (e.g. a new frontier), the Gaussians are extrapolations. **Document the calibration source and version** in every report.

---

### Calibration tip — anchor to analogues

After computing the posterior, ask: *does this number match what I'd expect from the play's discovery rate?* If your posterior P(G | DFI) = 65% but the play's analogue success rate (post-DHI screening) is 25%, something is over-tuned. Trace it back: too-high water fraction? Wrong fluid type? Over-aggressive prior?

---

### Calibration tip — invert R for sanity

R = 3 means *the observation is 3× more likely under success than under failure*. Ask: *is this seismic anomaly really 3× more diagnostic than my prior suggests?* If you can't articulate the answer in geophysical terms, R is probably overstated and the DHI class assignment may be wrong.
""")

    with _tab_practice.expander("DFI reporting — what to include in a prospect write-up", expanded=False):
        st.markdown(r"""
### Minimum reportable set

For a DFI-updated prospect, every write-up should contain — at minimum; these eight numbers and three plots:

| # | Quantity | Symbol |
|---|----------|--------|
| 1 | Prior, ESL | P(G, ESL) |
| 2 | Prior, Classic | P(G, Classic) |
| 3 | Posterior, ESL | P(G \| DFI, ESL) |
| 4 | Posterior, Classic | P(G \| DFI, Classic) |
| 5 | DHI Index | (integer) |
| 6 | DHI-Index strength | R_DFI |
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
> *A conceptual scored DHI Index of **{dhi_index}** was applied as a Bayesian update, with fluid failure mix
> Water {wat}% / LSG {lsg}% / Other {oth}%, fluid type {hc_type}, SD mode {sd}, calibration {cal_version}.*
>
> *The resulting posterior is **P(G | DFI, ESL) = {post_esl}%** (Δ {delta_esl:+} pp vs prior), with
> the Classic method posterior at **{post_classic}%** (Δ {delta_classic:+} pp).*
>
> *Diagnostic values: R_DFI = {R}, DHI Volume Weight V = {V}. The Bayesian update is
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
- R_DFI < 1.2 (very weak DFI evidence — uplift is mostly prior-driven).
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
| ESL prior, Bel, Pl | from Geological POS tab |
| Classic prior | from Geological POS tab |
| DHI Index, scorer, scoring date | manual + DHI scoring sheet |
| calibration version | from app |
| SD mode | from app |
| Fluid mix (water/LSG/other) | from app |
| Fluid type | from app |
| Posterior ESL, Classic | from app |
| R, V | from app |
| Sensitivity sweep range | from app |
| Decision recommendation | manual |

The Final Prospect POS Summary's **download (.txt)** button produces this audit trail in a copy-paste-ready format.
""")

    with _tab_practice.expander("DHI → volumetrics: joining geological & DFI-defined volumes",
                                expanded=False):
        st.markdown(r"""
A DHI doesn't only change **risk** — Monigle 2025 stress it should also constrain the
**volume** distribution. The geophysically-defined volume (contact, edges, NTG) must be
joined with the geologically/structurally-defined volume **in proportion to how much the
DHI can be trusted**. E-POS surfaces *two* trust measures, then recommends a blend on the
**DFI Results** tab (this is interpretive guidance, not a Monte-Carlo engine).

### Two measures of "how much to trust the DFI for volumes"

| | What it is | Input | Availability |
|---|---|---|---|
| **DHI Volume Weight (V)** | DHI-Index byproduct $V = L_\text{success} / (L_\text{success} + E[L\mid\text{failure}])$ — the calibrated probability the anomaly is a *true HC response* | conceptual DHI likelihoods | DHI-Index pathway only |
| **Column-height weight ($w_{ch}$)** | Monigle 2025, Fig. 8 — fraction of volumetric trials placing the HCWC at the DFI-rated elevation | 0–1 DHI score | every pathway |

Both answer the same operational question from different inputs, so the app shows them
side by side. When both are available, a large divergence is a flag to reconcile the DHI-Index
likelihoods against the DHI score before committing the volume distribution.

### The column-height weighting rule (Monigle Fig. 8)
""")
        st.latex(r"w_{ch} \;=\; \min\!\big(0.95,\; 2 \cdot \text{DHI score}\big)")
        st.markdown(r"""
- **DHI score > ~0.50** → place the HCWC at the DFI-rated elevation in **95%** of trials
  (never 100% — the weak-DHI database is thin, <10 drilled successes).
- **DHI score < 0.50** → honour the DFI contact in proportion to **twice** the score; the
  remaining trials follow the deeper geological/structural spill estimate.

### Consistency gates (Monigle Figs. 6, 10; porosity discussion)
- **Discernibility gates the whole blend:** *high/moderate* → volumetric ranges must be
  fully consistent with the geophysics; *low* → only the most-likely parameters need be
  permissible; *none* → no geophysical tie required (but don't violate the no-discernibility
  root cause).
- **Fluid contact reflection (FCR) → NTG:** an FCR present implies **NTG > ~50%** (observed
  40–85%) and precludes *low* NTG; FCR absent does not preclude moderate NTG.
- **Porosity floor:** a DHI implies porosity above **~14%** (DHIs are essentially never
  observed below this).

*Source: Monigle et al. (2025), Figures 8 & 10. See the **DFI Results** tab for the live
recommendation on the current prospect.*
""")

    with _tab_practice.expander("Calibration guidance", expanded=False):
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

Per-pillar **Rose (2001) calibration anchors** — typical POS ranges observed across
analogue prospect populations — for sense-checking each pillar against the literature:
""")
        from components.calibration import ROSE_RANGES as _ROSE
        st.markdown(
            "| Pillar | Typical POS range | Median | Basis |\n|---|---|---|---|\n"
            + "\n".join(f"| {k} | {lo}–{hi} % | {med} % | {desc} |"
                        for k, (lo, hi, med, desc) in _ROSE.items())
        )
        st.caption(
            "Source: Rose, P.R. (2001), *Risk Analysis and Management of Petroleum "
            "Exploration Ventures*, AAPG Methods in Exploration 12. A pillar POS far "
            "outside its range isn't wrong, but it should carry an explicit rationale."
        )
        st.markdown("""
---

### Key references

See the dedicated **📚 Key references & source papers** section below for the full,
grouped list (ESL, Classic POS, DHI/DFI, characteristic scoring, and assurance).
""")
        from components.adequacy_matrix import render_adequacy_matrix_reference
        render_adequacy_matrix_reference()

    # ═══════════════════════════════════════════════════════════════════════
    # 📚 KEY REFERENCES & SOURCE PAPERS
    # ═══════════════════════════════════════════════════════════════════════
    with _tab_ref.expander("Key references & source papers", expanded=False):
        st.markdown("""
The methods in E-POS are grounded in published literature. References are grouped
by the part of the tool they underpin. Consult each source through its publisher
or your own library.

#### 1 · Evidence Support Logic (ESL) & the Italian Flag
- **Quintessa (2022)** — *Evidence Support Logic Guide, v3.0.* Quintessa Ltd.
  The definitive technical reference for ESL, the Italian Flag, Bel/Pl intervals
  and Policy P (the stance *w*).
- **Blockley, D.I. & Godfrey, P. (2000)** — *Doing It Differently: Systems for
  Rethinking Construction.* Thomas Telford, London. Origin of the interval-probability
  reasoning the Italian Flag is built on.
- *Analysing Uncertainties: Bayes and Italian Flags* (2013) — links Italian-Flag
  belief masses to Bayesian updating.
- **Hall, J.W., Blockley, D.I. & Davis, J.P. (1998)** — *Uncertain inference using
  interval probability theory.* Int. J. Approximate Reasoning 19(3–4):247–264.
  DOI 10.1016/S0888-613X(98)10010-5. The interval-probability inference rule behind
  the Italian-Flag combination.
- **Dempster, A.P. (1967)** — *Upper and lower probabilities induced by a multivalued
  mapping.* Annals of Mathematical Statistics 38(2):325–339. Origin of the Bel/Pl
  (lower/upper probability) pair.
- **Shafer, G. (1976)** — *A Mathematical Theory of Evidence.* Princeton University
  Press. Dempster–Shafer belief functions and Dempster's rule (used in the
  experimental DFI-fusion prototype).
- **Walley, P. (1991)** — *Statistical Reasoning with Imprecise Probabilities.*
  Chapman & Hall. Imprecise-probability foundation of the Bel/Pl envelope.
- **Smets, P. (1990, 2005)** — the Transferable Belief Model and the pignistic
  transformation (kin to the stance *w*). Smets (1990), IEEE Trans. PAMI 12(5):447–458;
  Smets (2005), Int. J. Approximate Reasoning 38(2):133–147.
#### 2 · Geological probability of success (Classic / multiplicative POS)
- **Rose, P.R. (2001)** — *Risk Analysis and Management of Petroleum Exploration
  Ventures.* AAPG Methods in Exploration 12. The industry-standard multiplicative
  POS framework used for the **P(G, Classic)** view.
- **Milkov, A.V. (2015)** — *Risk tables for less biased and more consistent
  estimation of the probability of geological success.* Earth-Science Reviews, v. 150.
  Basis of the Milkov reference-table scheme on the **Reference Tables** tab.
- Reference-table schemes also implemented in E-POS: **Malvić (2009)** and the
  **CCOP (2000)** guidelines; see the **Reference Tables** tab.
- **Otis, R.M. & Schneidermann, N. (1997)** — *A process for evaluating exploration
  prospects.* AAPG Bulletin 81(7):1087–1109. Basis of the chance-of-adequacy
  (confidence × geological-news) matrix.
- **SPE/WPC/AAPG/SPEE (2018)** — *Petroleum Resources Management System (PRMS),*
  revised June 2018. Source of the verbal probability scale.

#### 3 · DHI / DFI & seismic-amplitude risking (the Bayesian update)
- **Simm, R. (2016)** — *Seismic Amplitude and Risk: A Sense Check.* FORCE seminar,
  *Underexplored Plays — Part II*, Nov 2016. Source of the **two-state Bayesian DFI
  update** and the **R rule-of-thumb bands** used throughout the DFI tab.
- **Nosjean, N. et al. (2021)** — *Geological probability of success assessment for
  amplitude-driven prospects: a Nile Delta case study.* J. Petroleum Science &
  Engineering 202:108515. DOI 10.1016/j.petrol.2021.108515. A worked field example of
  folding DHI evidence into POS.
- **Forrest, M., Roden, R. & Holeywell, R. (2010)** — *Risking seismic amplitude
  anomaly prospects based on database trends.* The Leading Edge 29(5):570–574.
  DOI 10.1190/1.3422455. The Rose & Associates DHI-consortium database trends.
- **Pettingill, H.S. & Roden, R. (2022)** — *Integrated DHI Prospect Evaluation:
  lessons learned from 3 generations of explorers.* Discovery Thinking Forum,
  IMAGE 2022 (SEG/AAPG), Houston.
- *"DHIs work well for de-risking prospects"* — *GeoExpro* feature. Accessible
  overview of DHI performance statistics.
- **Martinelli, G., Stabell, C. & Langlie, E. (2019)** — *Direct Fluid Indicators in
  Multiple Segment Prospects*, US Patent 10,451,762 B2 (Schlumberger). The GeoX
  single-segment fluid×reservoir scenario Bayes and the **risk-factor (pillar)
  marginalisation** behind the **Custom multi-case pillar-attribution** view. Its
  novel *multi-segment* DFI-dependency / reference-DFI correlation method is **not**
  implemented (see scope note below).
- **Martinelli, G., Eidsvik, J. & Hauge, R. (2012)** — *Dynamic Decision Making for
  Graphical Models Applied to Oil Exploration* (arXiv:1201.4239; later in Eur. J.
  Operational Research, 2013). Graphical-model basis cited by the patent.

#### 4 · Characteristic / direct-hydrocarbon-indicator scoring
- **Monigle, P.W., Hedayati, T.S. & Goulding, F.J. (2025)** — *Integrated and improved
  direct hydrocarbon indicators: a step forward in petroleum risk discrimination.*
  AAPG Bulletin 109(5):617–636. DOI 10.1306/04042524030. Source of the
  per-characteristic success-rate statistics and discernibility weighting behind the
  **characteristic-scoring** pathway.
#### 5 · Calibration, assurance & general practice
- **Bond, C.E. et al. (2022)** — *Recommended practices in exploration assurance.*
  Guidance on independent review / QC of prospect risk assessments.
- **ExxonMobil (2018)** — *Risking V* (Risk Coordinator Meeting). Operator
  perspective on consistent, calibrated risking.
- **MacKay, J.A. (1995)** — *Evaluating risk and checking consistency in exploration
  portfolios.* Amoco Exploration Assurance / AAPG extended abstracts. Early operator
  treatment of risk consistency and of the **uncertainty-index** idea (separating the
  probability estimate from the analyst's confidence in it), conceptual kin to the
  Italian-Flag **White (incompleteness)** band used in E-POS.
---

*The **Conceptual DHI Index (experimental)** pathway is exactly that — conceptual. Its likelihood
curves are round, hand-set illustrative values, **not calibrated to any dataset or study**, and
are editable on the Setup page. It expects a **pure DFI-strength input**, not a raw composite DHI
index that bundles geology with the seismic signal (see the warning on that Setup page). For a
decision-grade update, replace the conceptual curves with your own calibrated likelihoods.*

#### Scope & intellectual-property note (single-segment only)
E-POS models a **single-segment** prospect. *"Segment"* is a **GeoX** term for one
fault/reservoir compartment within a multi-segment prospect. E-POS does **not**
implement multi-segment prospects, **DFI dependency groups**, a **reference-DFI**
conditional-probability table, or the inter-segment **correlation parameter *k*** —
the novel, claimed subject matter of **US 10,451,762 B2**. The single-segment
fluid×reservoir Bayes and the pillar (risk-factor) marginalisation E-POS uses are
**standard Bayes' theorem** (prior art). **No patent claim is practised.** *(This is an
engineering rationale, not legal advice; a commercial release should obtain a
professional claims review.)* E-POS's separate **attribute-correlation discount ρ**
is a different axis (correlation across characteristic attributes, not segments) and a
different mechanism (a design-effect exponent on R), independently derived.
""")

    # ═══════════════════════════════════════════════════════════════════════
    # UNIFIED GLOSSARY — ESL/Classic + DFI in one place
    # ═══════════════════════════════════════════════════════════════════════
    with _tab_ref.expander("Glossary & Abbreviations (ESL + DFI)", expanded=False):
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
| **DHI Index** | Composite DHI score | A single scalar (typical range −23 … +50) summarising the strength and consistency of all observed DFIs for one prospect. Computed by the DHI/amplitude scoring workflow. |
| **DFI update** | Bayesian update | Conditioning the prior on the DFI observation. Can **raise or lower** P(G) — a strong DFI lifts it; an absent/weak DFI where one was expected lowers it. |
| **R_DFI** | DHI-Index strength | Likelihood ratio = $L_\text{success} / E[L \mid \text{failure}]$. R_DFI > 1 favours success; R_DFI < 1 against. |
| **V** | DHI Volume Weight | Bounded version of R = $L_\text{success}/(L_\text{success}+E[L\mid\text{failure}])$. Range 0..1; 0.5 = neutral. Also the weight on a DFI-derived volume constraint. |
| **L** | Likelihood | Probability *density* of observing the DHI Index given a specific outcome class (a Gaussian PDF value, not a probability; can exceed 1). |
| **π** (pi) | Outcome prior | Prior probability of one of the 8 mutually-exclusive outcomes (categorical-prior convention, kept distinct from P(·) and pillar Pgs). |
| **HC** | Hydrocarbon | Catch-all for oil and/or gas. |
| **LSG** | Low-Saturation Gas | A failed-prospect outcome where reservoir contains gas at saturation too low to produce — generates DFIs that mimic commercial gas. |
| **HCWC** | Hydrocarbon–Water Contact | Depth of the fluid contact; a flat spot may indicate it more precisely than geology. |
| **Eval-Res** | Evaluable Reservoir | Reservoir present and detectable on seismic. The DFI is informative. |
| **Non-Eval-Res** | Non-Evaluable Reservoir | Reservoir failure (absent / sub-resolution / wrong facies). The DFI is uninformative — defaults to a failure-class likelihood. |
| **SD mode** | Standard-deviation mode | Gaussian width: `upper` (conservative, wider) or `calculated` (tighter). E-POS defaults to `upper`. |
| **Fluid weights** | Water / LSG / Other failure fractions | How failure mass is partitioned among the three non-HC outcomes. Must sum to 1. |
| **Fluid type** | HC class selector | Which DHI success class supplies the success likelihood: *Success* (pooled), *Oil*, *Oil+Gas*, *Gas*. |
| **Calibration version** | your DHI-scoring workflow release | Versioned snapshot of the database statistics. Current: v.16a. |

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

    # ── Reference probability tables (folded in from the former top-level tab) ──
    # Rendered directly (not inside an expander) because render_reference_tables()
    # contains its own expanders — Streamlit forbids expander-in-expander.
    with _tab_ref:
        st.divider()
        from methods.reference_tables import render_reference_tables
        render_reference_tables()
