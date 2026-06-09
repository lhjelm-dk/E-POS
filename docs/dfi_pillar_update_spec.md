# Pillar-resolved Bayesian DFI update — design spec (Phase 0)

**Status:** approved for implementation (Plan A). No code yet beyond this spec.
**Scope decisions (locked):**
1. Implement **Plan A** (attribution read-out) now; **Plan B** (overwrite pillar values everywhere) is deferred — see §9.
2. The DFI reservoir signal updates the **whole Reservoir pillar** (presence + quality lumped).
3. **Dual-case methods** (Characteristic / Custom-dual) are **aggregate-only** by physical necessity.
4. **Failure split is reservoir-driven.** The split between fluid-failure (reservoir
   present) and non-reservoir failure is governed by the **Reservoir pillar prior**
   `(1−P_res)`, NOT by a free user weight. For pillar-resolved methods this makes the
   **engine the source of truth for the headline POS too** — `pos_post` from the joint
   update replaces the old grouped-`R` posterior. Consequence: the `non_reservoir` user
   weight is **deprecated for multi-case** (the split comes from `P_res`), and saved
   prospects may show a slightly different (more correct) DFI posterior that now accounts
   for the reservoir-failure mode. Document in Theory + changelog.

---

## 1. Purpose

Today every DFI method collapses to one scalar `R` applied to the aggregate `P(G, ESL)`
via `simm_bayes_posterior`. That hides *where* the update lands. This spec defines a
method-agnostic engine that additionally resolves the update onto **two geological
channels** and reports per-pillar prior→posterior, **without changing the headline POS**.

The construction is the single-segment case of the GeoX algorithm described in
US 10,451,762 B2 (Martinelli, Stabell, Langlie; Schlumberger, 2019). We reconstruct only
the single-segment Bayes/marginalisation (standard prior art); we do **not** implement the
patent's novel multi-segment DFI-dependency-group correlation. See §8.

---

## 2. The resolution ceiling

A DFI is a *fluid* indicator. It can sense only (a) whether a reservoir/interface exists
and (b) what fluid fills it. It **cannot** tell which of charge / trap / retention failed.
So the maximum resolvable structure is **two channels**:

| Channel | E-POS pillars | Patent risk group |
|---|---|---|
| **Reservoir** | Reservoir (whole) | reservoir presence + quality |
| **HC-system** | Charge · Closure · Retention (combined) | trap & seal + source & migration |

Retention sits on the HC-system side (seal integrity = HC presence, not reservoir).

---

## 3. Outcome tree (single segment)

```
                         ┌─ HC (oil/gas/oil+gas)  → L_HC        SUCCESS
   Reservoir present  ───┤
   P_res                 └─ brine / LSG / other   → L_fluidfail FLUID failure   (reservoir present)
   Reservoir absent  ─────  non-reservoir         → L_nonres    RESERVOIR failure
   (1 − P_res)
```

Multiple fluid sub-cases (oil/gas/oil+gas; water/LSG/other) blend **within** their channel
by the user's weights into one `L_HC` and one `L_fluidfail`. The three "× non-reservoir"
cases collapse to a single `L_nonres` (fluid is moot with no reservoir).

---

## 4. Priors (the residual-`P_hc` trick — guarantees consistency)

Let `POS = P(G, ESL)` (the DFI prior, already carrying the policy weight + discernibility),
and `P_res` = the Reservoir pillar's rolled-up ESL value. Define the HC-system prior
**residually** so the product reconstructs the ESL POS exactly:

```
P_hc := POS / P_res          # so that  P_res · P_hc = POS  (exact, no drift)
```

Leaf priors (sum to 1 by construction):

```
prior(success)        = POS                  = P_res · P_hc
prior(fluidfail&res)  = P_res − POS          = P_res · (1 − P_hc)
prior(nonreservoir)   = 1 − P_res
```

This consumes the ESL machinery **once** — no double-counting of policy weight / discernibility.

---

## 5. Joint update

```
Z          = POS·L_HC + (P_res−POS)·L_fluidfail + (1−P_res)·L_nonres
POS'       = POS·L_HC / Z                                   # new headline P(G,ESL)
P_res'     = [POS·L_HC + (P_res−POS)·L_fluidfail] / Z       # new reservoir marginal
P_hc'      = POS' / P_res'                                  # new HC-system marginal (residual)
```

**In-group redistribution (patent rule):** split `P_hc'` back across Charge / Closure /
Retention by **preserving their pre-DFI log-proportions**:

```
w_i = log(pillar_i) / Σ_j log(pillar_j)         # over {Charge, Closure, Retention}
pillar_i' = (P_hc')^{w_i}                        # multiplicative log-proportion split
```

Reservoir pillar → `P_res'` (whole, per decision 2).

---

## 6. Invariants (enforced by unit tests before any UI)

- **(a) Headline unchanged.** `POS'` from the joint == `simm_bayes_posterior(POS, R)` with
  `R = L_HC / L_failmix`, `L_failmix = [(P_res−POS)·L_fluidfail + (1−P_res)·L_nonres]/(1−POS)`.
  → Plan A never moves any number we already report.
- **(b) Product exact.** `P_res' · P_hc' == POS'` (to 1e-12).
- **(c) Redistribution exact.** `∏ pillar_i' == P_hc'`.
- **(d) Leaf priors normalise.** `prior(success)+prior(fluidfail&res)+prior(nonres) == 1`.

## 6.1 Golden test (patent replication, 3-leaf reduction)

Inputs: `POS=0.072`, `P_res=0.5`, `L_HC=0.8`, `L_fluidfail=0.3`, `L_nonres=0.5`.

| Quantity | Engine | Patent (Table 6) |
|---|---|---|
| COS  | 0.072 → **0.1321** | 0.130 |
| Reservoir | 0.500 → **0.4266** | 0.434 |
| HC-system | 0.144 → 0.3097 | (split across TS/SM) |
| Direction | COS **↑**, Reservoir **↓** | same |

Sub-rounding agreement; small gap = the patent's extra sub-scenarios (oil&non-eval 0.6,
reservoir-quality variant). The **COS-up / reservoir-down** signature is the headline
behaviour and the reason this feature exists: a supportive anomaly can still *degrade*
a specific pillar, which the aggregate-R view cannot show.

---

## 7. Method adapters → `ChannelLikelihoods`

Each method emits `(L_HC, L_fluidfail, L_nonres)` or declares itself aggregate-only:

| Method | Channels | Path |
|---|---|---|
| Modified DHI Index | 3 (fluid × reservoir already present) | pillar-resolved |
| Custom — **multi-case** | 3 (non-reservoir case = `L_nonres`) | pillar-resolved |
| Custom — **dual-case** (new explicit split) | 2 | aggregate-only |
| Characteristic (Monigle 2025) | 2 (single success/failure curve) | aggregate-only |

The Custom tool is split into two named models (dual / multi). Aggregate-only methods show
only the headline move and a note that reservoir attribution is not possible with one
failure curve.

---

## 8. Single-segment scope & patent statement (ships in-app)

E-POS models a **single-segment** prospect ("segment" is a GeoX term). It does **not**
implement multi-segment prospects, DFI dependency groups, the reference-DFI conditional
probability table, or the inter-segment correlation parameter *k* — the novel, claimed
subject matter of US 10,451,762 B2. The single-segment Bayesian scenario update and
risk-factor marginalisation used here are standard Bayes' theorem (prior art). No patent
claim is practised.

> Note: our existing attribute-correlation discount ρ (design-effect exponent on `R`) is a
> different axis (correlation across *characteristic attributes*, not across *segments*) and
> a different mechanism (exponent, not reference-DFI CPT). It is independently derived.

This statement must appear (a) in the Theory section and (b) near the DFI UI, and the patent
must be cited in the References section.

---

## 9. Plan B (DEFERRED — reminder)

Plan B = actually overwrite Reservoir + Charge/Closure/Retention pillar values post-DFI so
the **Overview table, Bel/Pl, sensitivity, comparison** all carry the resolved update.
Until B lands, Plan A's attribution is **display-only**: the per-pillar table stays pre-DFI
while the headline is DFI-updated — a deliberate, documented inconsistency. B must reconcile
the Bayesian point-update with ESL's Italian-flag interval representation (a point vs a
Bel/Pl band) and may refine reservoir to presence-only.

---

## 10. References to add

- Martinelli, G., Stabell, C., Langlie, E. — *Direct Fluid Indicators in Multiple Segment
  Prospects*, US 10,451,762 B2, Schlumberger Technology Corp., 22 Oct 2019.
- Martinelli et al., *Dynamic Decision Making for Graphical Models Applied to Oil
  Exploration*, 2012 (arXiv) — the graphical-model basis cited by the patent.
