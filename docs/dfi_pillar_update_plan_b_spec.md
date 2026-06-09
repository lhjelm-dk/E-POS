# Plan B — post-DFI pillar values in the tables (design spec)

**Status:** approved for implementation pending "go". Builds on Plan A (`dfi_pillar_update_spec.md`).

**Locked decisions:**
1. **Parallel post-DFI view** — the prior pillar inputs are NOT overwritten. The app's
   frame ("pillars = geological prior, before DFI") is preserved; post-DFI values appear
   as a separate column/row alongside the prior.
2. **Both methods, channel-resolved** — Custom *and* DHI-Index. This **upgrades DHI-Index**
   from its current *equal-spread* attribution (`ratio^(1/8)` across 8 slots, which cannot
   show reservoir divergence) to the geologically-correct channel-resolved split.
3. **Surfaces:** Final Prospect POS table · Sensitivity & CAM · Comparison (ESL vs Classic).
   *(Risk Overview / Bel-Pl per-pillar flags were NOT selected → out of scope, so the full
   masses→Bel/Pl round-trip is not required for v1.)*

---

## 1. Key findings that shape this

- **The representation bridge already exists:** `reverse_engineer_masses_preserving_commitment(pg_new, masses, w)` turns a point Pg back into an Italian flag. Only needed if a surface shows post-DFI *flags/Bel-Pl* — none of the selected v1 surfaces do, so v1 is **point-level**.
- **Existing DHI-Index attribution is equal-spread, not channel-resolved.** `attribute_esl_optionA/B` distribute the log-ratio uniformly (`ratio^(1/8)`), so all pillars move the same direction — they cannot show "POS up / Reservoir down". Plan B replaces this with the channel split.
- **No forced product identity needed.** Pillar values are *marginals*; the headline is the ESL *mass-rollup* (≠ ∏ marginals). For a parallel display we show each pillar's prior→post marginal AND the headline prior→post separately — no round-trip, no anchoring correction required at point level.

---

## 2. Per-pillar post-DFI marginals — the two methods

A unified accessor returns, at the current stance, `{pillar: (prior_point, post_point)}` for
Reservoir / Charge / Closure / Retention plus the headline:

- **Custom multi-case:** straight from `resolve_dfi_custom(ctx)` → `ResolvedDfi`
  (`p_res_prior/post`, `hc_pillars_prior/post`). *(already built in Plan A)*
- **DHI-Index (SAAM):** derive from the **8-outcome** posterior (`compute_dfi_posterior`):
  - `P_res' =` Σ posterior over **reservoir-present** outcomes  (= the patent's exact
    `P(RP | DFI)` marginal — *more* correct than the 3-leaf reduction);
  - headline `POS' =` success-outcome posterior (unchanged — keep the richer 8-outcome);
  - `P_hc' = POS'/P_res'` residual; split across Charge/Closure/Retention by
    `redistribute_log_proportion` (shared with Custom).
  This **replaces** the equal-spread `ratio^(1/8)` for the per-pillar split while keeping the
  8-outcome headline. Aggregate-only methods (Characteristic / Custom-dual) → headline only.

Golden test: DHI-Index path must reproduce the patent's `P(RP|DFI)` direction
(reservoir down while POS up) on the worked example.

---

## 3. Surfaces (v1 = point-level)

### 3a. Final Prospect POS table
Extend the existing DFI posterior row into a **per-pillar post-DFI block**: for each pillar a
`prior → posterior (Δ pp)` line, with the reservoir-vs-HC divergence visible. Prior pillar
rows stay exactly as they are (parallel, not overwrite). Headline post-DFI row already present.

### 3b. Sensitivity & CAM  — **DEFERRED (B3)**
The post-DFI position is already visible on the DFI Results **sensitivity sweep** (the
posterior curve) and the iso-R / iso-DHI prior→posterior maps. The remaining piece — a
post-DFI marker overlaid on the **Chance Adequacy Matrix canvas** (Geological POS tab) —
is deferred: it is a larger JS change on a tab that is *prior-by-design*, with low
incremental value given the post-DFI position already appears on the DFI pages. Pick up
later if a single combined prior+posterior CAM view is wanted.

### 3c. Comparison (ESL vs Classic)
Add **post-DFI P(G, ESL)** vs **post-DFI P(G, Classic)** alongside the prior comparison, so the
ESL-vs-Classic gap is shown before *and* after the DFI update.

---

## 4. DHI-Index attribution upgrade (the one behaviour change)

The DFI Results per-pillar tables for DHI-Index currently use equal-spread `attribute_esl_optionA/B`.
Plan B switches the **point** attribution to the channel-resolved split (§2). If a table shows
flags/Bel-Pl, reuse `reverse_engineer_masses_preserving_commitment` per slot to render them;
otherwise points + Δ. This is the only place existing numbers change — document in Theory +
changelog (the new split is more correct; it can show a pillar moving opposite to POS).

---

## 5. Consequences & risks

- **Prior inputs never change** (parallel view) → nothing booked today shifts silently. ✔
- **DHI-Index per-pillar tables change** (equal-spread → channel-resolved). Headline unchanged
  (still 8-outcome). Reservoir/HC pillars may now move in opposite directions — that's the fix.
- **Stance-aware:** all post-DFI pillars recompute at the current `w` (no frozen numbers).
- **CAM/sensitivity** gain a post-DFI overlay; must stay visually distinct from the prior.
- **Masses/Bel-Pl per post-DFI pillar** deferred (not in selected surfaces) — a Plan B.2 if
  the Risk Overview flags are wanted later.

---

## 6. Phases

- **B1 — logic:** unified `dfi_post_pillars(ctx)` accessor (Custom via ResolvedDfi; DHI-Index via
  8-outcome marginal + log-split). Unit tests incl. patent `P(RP|DFI)` golden.
- **B2 — Final Prospect POS table:** per-pillar post-DFI block (parallel).
- **B3 — Sensitivity & CAM:** post-DFI overlay.
- **B4 — Comparison (ESL vs Classic):** post-DFI pair.
- **B5 — DHI-Index attribution upgrade:** channel-resolved replaces equal-spread on DFI Results.
- **B6 — Theory + changelog + verify:** document the channel-resolved upgrade; pytest/compile/preview.

No multi-segment / correlation method (single-segment only; no patent claim practised).
