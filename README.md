# E-POS — Evidence-supported Probability of Success

**Geological risk assessment for oil & gas prospects — with a Bayesian Direct-Fluid-Indicator (DFI) update.**

E-POS is a [Streamlit](https://streamlit.io) application for quantifying a prospect's
**geological chance of success P(G)** from evidence, and then **Bayesian-updating it with
seismic DHI/DFI evidence**. It keeps the assessment fully traceable: you enter evidence once,
and the app reports three numbers side by side — **P(G, ESL)**, **P(G, Classic)**, and the
DFI-conditioned posterior **P(G | DFI)** — so the gap between methods becomes a data-quality
signal rather than a hidden assumption.

![E-POS overview](docs/img/01_app_overview.png)

> All screenshots in this README are generated from the synthetic **`AlphaGammaFoxtrot`**
> prospect using the **placeholder** calibration that ships with the repo (no proprietary
> data). Re-generate them any time with `python scripts/capture_readme_shots.py`.

---

## Contents

- [What E-POS does](#what-e-pos-does)
- [The three headline numbers](#the-three-headline-numbers)
- [Quick start](#quick-start)
- [How to use it — tab by tab](#how-to-use-it--tab-by-tab)
  - [1 · Dashboard](#1--dashboard)
  - [2 · Play](#2--play)
  - [3 · Conditional](#3--conditional)
  - [4 · Geological POS](#4--geological-pos)
  - [5 · Bayesian DFI Update](#5--bayesian-dfi-update)
  - [6 · Final Prospect POS](#6--final-prospect-pos)
  - [7 · Theory & Guide](#7--theory--guide)
- [The methods (math)](#the-methods-math)
- [Reference tables](#reference-tables)
- [Data, calibration & privacy](#data-calibration--privacy)
- [Project structure](#project-structure)
- [Testing](#testing)
- [References](#references)
- [Attribution](#attribution)

---

## What E-POS does

Prospect risking is hard because the factors are **dependent**, the evidence is **incomplete**,
and a single point estimate hides how much of the number rests on assumption. E-POS tackles
this with **Evidence Support Logic (ESL)** — the *Italian Flag*: every risk element carries
three masses, **green** (evidence *for*), **red** (evidence *against*), and **white**
(the uncommitted *unknown*). You never have to pretend the white band is zero.

On top of the geological assessment, E-POS layers a **rigorous Bayesian update** for seismic
**Direct Fluid Indicators (DFI / DHI)**. The DFI is a *fluid discriminator*: a strong,
conformant amplitude raises P(G); an amplitude that is **absent where one was expected** is
itself evidence and *lowers* P(G). The update is a true Bayesian conditioning, so it can move
the prior in **either** direction.

## The three headline numbers

| Number | What it is | Where |
|---|---|---|
| **P(G, ESL)** | Evidence Support Logic mass-rollup at the current stance *w* — the headline geological prior | Geological POS → Result |
| **P(G, Classic)** | Rose-style multiplicative product (∏ pillar Policy P) — an independent cross-check | Geological POS → Result; Dashboard |
| **P(G \| DFI)** | The Bayesian posterior after the seismic DFI update — the *reportable* result | Final Prospect POS |

The **ESL − Classic gap** is a built-in diagnostic: a large divergence flags dependence between
pillars or a data-quality issue, not an error.

![P(G, ESL) vs P(G, Classic)](docs/img/07_geo_esl_vs_classic.png)

---

## Quick start

```bash
# 1. install
pip install -r requirements.txt

# 2. run
streamlit run app.py
```

The app opens in your browser. It ships with a **synthetic placeholder** calibration
(`data/saam_calibration_placeholder.json`) so it runs out of the box. Drop a proprietary
calibration at `data/saam_calibration.json` to override it (that path is git-ignored).

To regenerate the README screenshots after a UI change:

```bash
pip install playwright && playwright install chromium
python scripts/capture_readme_shots.py     # writes docs/img/*.png
```

---

## How to use it — tab by tab

The workflow is a funnel: **set up → assess evidence → geological result → DFI update →
reportable result**, with a **Theory & Guide** tab as the reference.

### 1 · Dashboard

Set the prospect metadata and the **stance on unknowns *w*** (how the white/uncommitted mass
is scored: `0` = pessimistic, `0.5` = neutral/recommended, `1` = optimistic). This is also
where you switch on the **DFI-capable prospect?** toggle — the single most consequential
control in the workflow.

![DFI toggle](docs/img/02_dashboard_dfi_toggle.png)

The Dashboard also hosts the **Classic POS** read-out, with an optional **ROSE override** for
entering a pre-existing external estimate (documented for audit). By default Classic POS is
ESL-derived and fully traceable.

![Classic POS / ROSE override](docs/img/03_dashboard_classic_rose.png)

### 2 · Play

Assess the **play-level** chance of each pillar (Charge, Closure, Reservoir, Retention) — the
regional, shared-across-prospects component. Each element takes evidence **for** and
**against**; the remainder is the white/unknown band.

![Play tab](docs/img/04_play_tab.png)

### 3 · Conditional

Assess the **prospect-given-play** chance — the prospect-specific component, broken into
sub-elements and combined with the chosen ESL operator (weakest-link, product, etc.).

![Conditional tab](docs/img/05_conditional_tab.png)

### 4 · Geological POS

The geological result, split into three sub-tabs.

**Result** — the headline Italian-flag overview table and both P(G) numbers (ESL vs Classic)
with their Bel–Pl envelopes and the gap.

![Geological POS — Result](docs/img/06_geo_result_overview.png)

**Diagnostics** — how the number behaves and what drives it:

- **Pillar fan** — each pillar's P(pillar, ESL) and the total P(G, ESL) across all stances
  *w*. The total is a *straight line* (ESL combines masses first, applies Policy P once) — its
  geometric signature versus the curved Classic fan.

  ![Pillar fan](docs/img/08_geo_pillar_fan.png)

- **ESL Ratio Plot** — evidence ratio (for ÷ against) versus residual uncertainty per element.

  ![ESL ratio plot](docs/img/09_geo_ratio_plot.png)

- **Chance Adequacy Matrix (CAM)** — every element in POS × commitment space, with auto-set
  green/red boundaries.

  ![Chance Adequacy Matrix](docs/img/10_geo_cam.png)

**Detail** — the full risk-element hierarchy, per-element tables, agreement analysis, and the
Classic POS detail.

![Risk element hierarchy](docs/img/11_geo_hierarchy.png)

### 5 · Bayesian DFI Update

Three **mutually-exclusive evidence sources** derive the DFI strength as a likelihood ratio
**R**, then update the geological prior. Pick whichever matches your data:

| Source | Engine | When to use |
|---|---|---|
| **Custom R tool** | Simm 2-state Bayes | You define your own P(DFI \| HC) / P(DFI \| No-HC) bell curves — fully transparent, no external calibration |
| **Characteristic scoring (Monigle 2025)** | naive-Bayes product → Simm 2-state | Score the prospect on 5 DHI attributes; R from a published drilled-prospect database. Stand-alone, no SAAM needed |
| **Modified DHI Index (SAAM)** | 8-outcome Bayes | A conceptual DFI-strength model with per-pillar attribution & fluid-class diagnostics |

**Custom R tool** — define the success/failure curves (multi-case: oil/gas/oil+gas vs
water/LSG/other + non-reservoir, with a DHI-style `P(fluid | failure)` mix), read R off a
DHI-strength slider:

![Custom R tool](docs/img/12_dfi_custom_setup.png)

Every source can export a **GeoX hand-off** — the six `P(DFI | case)` likelihoods for SLB
GeoX's DFI Assessment (the absolute scale is free; GeoX uses only their ratios):

![GeoX hand-off](docs/img/13_dfi_custom_geox.png)

**Characteristic scoring** — five verbal sliders; R is the product of per-attribute likelihood
ratios from the Monigle 2025 database. E-POS also **reverse-engineers the success vs failure
score densities** (the *Raw* toggle shows the exact convolution, *Inferred* a smooth Gaussian
model) so you can see where the prospect sits in the drilled population:

![Characteristic score density + GeoX](docs/img/14_dfi_char_density.png)

![Characteristic per-attribute LR + radar](docs/img/15_dfi_char_lr_radar.png)

**Modified DHI Index (SAAM)** — a conceptual model reverse-engineered from public SAAM
presentation material. It carries a prominent warning: **do not enter a raw SAAM DHI Index** —
that index bundles geology with the seismic signal, and the input here must be a *pure
DFI-strength indicator*:

![Modified DHI Index (SAAM)](docs/img/16_dfi_modified_dhi.png)

### 6 · Final Prospect POS

The reportable one-page view: the Italian-flag overview, the **before → after** DFI update
(both P(G, ESL) and P(G, Classic), with the Δ in percentage points), and the single
**Reportable POS** callout.

![Final Prospect POS](docs/img/17_final_pos.png)

### 7 · Theory & Guide

A complete reference: ESL fundamentals, Policy P & the Bel–Pl envelope, the full Bayesian DFI
derivation, the characteristic-scoring math, the CAM interpretation guide, calibration anchors,
a glossary, and the source papers.

![Theory & Guide](docs/img/18_theory_overview.png)

---

## The methods (math)

### Evidence Support Logic & the Italian Flag

Each element has **green** `S_for`, **red** `S_against`, and **white** `1 − S_for − S_against`.
The point estimate uses **Policy P** with the stance weight *w*:

```
Policy P = S_for + w · White        (w = 0 → Bel, w = 1 → Pl, w = 0.5 → neutral)
```

The **defensible interval** is `[Bel, Pl] = [S_for, 1 − S_against]`. Pillars roll up with the
ESL product operator (`green = ∏ greenᵢ`, `red = 1 − ∏(1 − redᵢ)`), and **P(G, ESL)** is
`Policy P` applied **once** to the consolidated masses.

### P(G, Classic)

The Rose-style multiplicative product — each pillar's Policy P multiplied together. Differs
from P(G, ESL) for four structural reasons (documented in Theory); the gap is informative.

### Bayesian DFI update

The geological **P(G, ESL)** is the **prior**. The DFI supplies a likelihood ratio **R**, and:

```
posterior_odds = R · prior_odds      ⇔      posterior = R·p / (R·p + (1 − p))
```

- **Custom / Characteristic** use this Simm (2016) two-state update directly.
- **Modified DHI Index (SAAM)** uses a full **8-outcome** decomposition (fluid × reservoir
  evaluability) with Gaussian likelihoods over the calibration classes, re-anchored to the same
  P(G, ESL); it additionally produces per-pillar attribution.

`R = 1` is a no-op (posterior = prior); `R > 1` raises P(G); `R < 1` lowers it.

### Characteristic scoring — naive Bayes + correlation discount

`R_char = ∏ LRᵢ` over the scored attributes (each `LRᵢ = odds(category) / odds(base rate)`).
Because the attributes physically correlate, the naive product over-counts; E-POS applies a
**design-effect / effective-sample-size discount**:

```
k_eff = k / (1 + (k−1)·ρ)          R_disc = R_raw ^ (k_eff / k)
```

with `ρ` the assumed average correlation (default 0.3). A **discernibility** weight then squashes
R toward 1 for poor data quality (`R_eff = R^d`).

---

## Reference tables

**Rose (2001) per-pillar calibration anchors** — typical analogue POS ranges:

| Pillar | Typical POS range | Median | Basis |
|---|---|---|---|
| Charge | 20–85 % | 55 % | Source presence, maturity, migration fairway |
| Closure | 30–95 % | 65 % | Trap geometry at target depth |
| Reservoir | 40–95 % | 72 % | Reservoir facies presence & effective porosity |
| Retention | 50–90 % | 70 % | Seal capacity & preservation |

**Fluid-failure mix `P(fluid | failure)`** (DFI default):

| Water | LSG (fizz) | Other | Σ |
|---|---|---|---|
| 0.80 | 0.20 | 0.00 | 1.00 ✓ |

**Discernibility ladder** — the bucket sets *both* the R cap and the squash exponent, giving an
effective ceiling `cap^d`:

| Discernibility | R cap | `d` | Effective max R_eff |
|---|---|---|---|
| high | 10 | 1.0 | 10 |
| moderate | 6 | 0.6 | ≈ 2.9 |
| low | 3 | 0.3 | ≈ 1.4 |
| absent | 3 | 0.0 | 1.0 (no effect) |

**Simm (2016) R rule-of-thumb** (log-symmetric):

| \|R\| | Verdict |
|---|---|
| ≥ 10 | Decisive — rarely justified for one DFI; audit the inputs |
| ≥ 3 | Strong — Simm's practical ceiling for a single DFI |
| ≥ 1.5 | Moderate — credible supportive evidence |
| ≈ 1 | Negligible — barely shifts the prior |
| ≤ 1/1.5 … 1/10 | Mirror-image downgrades |

---

## Data, calibration & privacy

- The app loads `data/saam_calibration.json` if present, otherwise the committed
  `data/saam_calibration_placeholder.json`. **The real calibration is git-ignored** — only the
  synthetic placeholder ships.
- Saved prospects (`data/prospects/*.csv`) and reference documents (`*.pdf`, `*.xlsx`, …) are
  git-ignored and never tracked.
- **"SAAM" is an internal database name** — alias it before any external publication.
- The README screenshots are generated against the placeholder calibration + the synthetic
  `AlphaGammaFoxtrot` prospect, so no proprietary numbers appear in any image.

---

## Project structure

```
app.py                     # Streamlit entry point — builds ctx, lays out the 7 tabs
logic/                     # pure math (no Streamlit): ESL, Policy P, Bayes, calibration
  esl_logic.py             #   AND/OR/product mass operators
  esl_pipeline.py          #   play × conditional mass rollup
  pos_policy.py            #   Policy P = green + w·white
  dfi_bayes.py             #   8-outcome SAAM Bayesian update + per-pillar attribution
  dfi_simm.py              #   Simm 2-state update, DHI score, GeoX hand-off mapping
  dhi_characteristics.py   #   Monigle naive-Bayes product, ρ discount, score densities
  dfi_custom.py            #   user-defined Gaussian likelihoods
  dfi_calibration.py       #   calibration loader (proprietary > placeholder)
components/                # UI building blocks (Streamlit)
  tabs/                    #   one module per tab / sub-page
  overview_table.py        #   the Italian-flag overview table
  dfi_shared.py            #   shared DFI render blocks (verdict, GeoX hand-off, …)
methods/                   # Classic POS rendering
data/                      # calibration JSON (placeholder), characteristic stats, prospects
docs/img/                  # README screenshots
scripts/                   # capture_readme_shots.py
tests/                     # pytest suite
```

## Testing

```bash
python -m pytest -q
```

The suite (**114 tests**) locks the core math: ESL operators, Policy P, the Simm 2-state and
8-outcome Bayes updates, the characteristic naive-Bayes product + correlation discount + score
densities, the GeoX hand-off mapping, the Dempster–Shafer prototype, and prospect save/load
round-trips.

---

## References

- **Quintessa (2022)** — *Evidence Support Logic Guide v3.0* (ESL, Italian Flag, Bel/Pl, Policy P).
- **Rose, P.R. (2001)** — *Risk Analysis and Management of Petroleum Exploration Ventures*, AAPG
  Methods in Exploration 12 (Classic POS, calibration anchors).
- **Simm, R. (2016)** — *Seismic Amplitude and Risk: A Sense Check*, FORCE (the 2-state Bayes
  formulation, the R rule-of-thumb).
- **Monigle et al. (2025)** — *Integrated and Improved Direct Hydrocarbon Indicators*, AAPG
  Bulletin 109/5 (characteristic scoring, discernibility weighting).
- Supporting work: Nosjean et al. (2020), Bond et al. (2022), ExxonMobil *Risking V* (2018).

Full citations and the bundled-PDF list are in the in-app **Theory & Guide → Reference** tab.

---

## Attribution

E-POS — by **Lars Hjelm** (`lhjelm`). Evidence-supported probability of success for oil & gas
prospects.

> **Before any public release:** scrub the proprietary documents from git history, alias the
> internal "SAAM" name, and confirm only the placeholder calibration ships. See
> `data/` and `.gitignore`.
