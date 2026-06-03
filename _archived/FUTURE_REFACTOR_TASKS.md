# Future refactor — code-level adoption of the new P(...) nomenclature

**Status:** PENDING — UI/documentation rename has been applied (Phase 3).
**Code-level rename has NOT been done — variable names and session-state keys
still use the legacy "pos / pg / total_for" vocabulary.**

This document is the brief for a future session that will propagate the new
nomenclature down into Python identifiers, session-state keys, and CSV column
headers (where they have not already been migrated).

---

## Background — the new nomenclature

The user established a scope-aware probability notation. Decisions taken:

- `POS` is **reserved** for the future DHI Bayesian-uplift result. Do not use
  this term for anything else.
- `P(...)` with parenthetical qualifiers is the unified notation for every
  derived probability in the app.
- Comma-separated qualifiers inside `P(...)`:
  - **Scope:** `Play`, `Cond`
  - **Pillar:** `Charge`, `Closure`, `Reservoir`, `Retention`
  - **Method:** `ESL`, `Classic` (future: `DHI`)
  - **Combinations:** `P(Reservoir, Cond)`, `P(G, ESL)`, `P(G, Classic)`,
    `P(Reservoir, Cond, "Net-to-gross")`
- `G` = "geological success" — total prospect-level result.
- Per-element ESL formula output `S_for + w × White` is renamed from
  "Policy POS" to **"Policy P"** in prose, `P_policy` in formulas.
- ESL Italian Flag masses `S_for`, `S_against`, `White` are unchanged
  (standard Quintessa terms).
- Stance `w` is unchanged.
- Bel / Pl bounds are unchanged: `Bel(X)`, `Pl(X)`,
  `P(X) ∈ [Bel(X), Pl(X)]`.

## Canonical entity list

| Notation | Meaning |
|----------|---------|
| `P(G)` | Total geological probability of success (prospect-level) |
| `P(G, ESL)` | Total Pg via ESL method (current `comparison_esl_pos`) |
| `P(G, Classic)` | Total Pg via Classic POS (current `comparison_classic_pos`) |
| `P(Play)` | Play-level chance (current `play_pos_val`, `play_pos`) |
| `P(Cond)` | Conditional-level chance (current `cond_pos_val`) |
| `P(G, Play)` | Alias for `P(Play)` |
| `P(G, Cond)` | Alias for `P(Cond)` |
| `P(Charge)` ... `P(Retention)` | Per-pillar combined chance (Play × Cond) |
| `P(Charge, Play)` ... | Per-pillar Play-level chance |
| `P(Charge, Cond)` ... | Per-pillar Conditional-level chance |
| `P(Reservoir, Cond, "Net-to-gross")` | Sub-element (Q-B: fully qualified) |
| `Bel(X)`, `Pl(X)` | ESL bounds (lower / upper) |
| `Policy P` / `P_policy` | Per-element value `S_for + w × White` |

---

## Files & symbols that still use legacy names (code level)

These are NOT renamed by the Phase-3 UI/docs pass. Each needs a code-level
rename in a future refactor:

### 1. `logic/esl_pipeline.py` — `ESLRollup` dataclass fields
Current fields:
- `play_for`, `play_against`              → conceptually `S_for/Against (Play)`
- `conditional_for`, `conditional_against`→ conceptually `S_for/Against (Cond)`
- `total_for`, `total_against`            → conceptually `S_for/Against (G)`
- `pillar_for[pid]`, `pillar_against[pid]`→ `S_for/Against (pillar, Play)`
- `conditional_results[pid] = {for, against}` → `S_for/Against (pillar, Cond)`

Suggested rename to fit new notation:
- `s_for_play`, `s_against_play` (and `_cond`, `_total`)
- `s_for_pillar_play[pid]`, etc.

### 2. `components/render_helpers.py` — `policy_pos`
- Keep function name for compatibility OR rename to `policy_p`.
- Recommendation: add `policy_p = policy_pos` alias; keep both.

### 3. `components/prospect_hub.py`
- `_compute_classic_pos_for_hub` → `_compute_p_g_classic`
- `_compute_classic_pos_with_range_for_hub` → `_compute_p_g_classic_with_range`
- `_compute_esl_for_hub` → `_compute_p_g_esl`
- `build_prospect_risk_data` keeps name; column headers update inside.

### 4. `components/comparison.py`
- `render_comparison(classic_pos=, esl_pos=, classic_bel=, classic_pl=)`
  → `render_comparison(p_g_classic=, p_g_esl=, classic_bel=, classic_pl=)`

### 5. `methods/classic_pos.py`
- `render_classic_pos` → `render_p_g_classic_detail`
- Local vars `play_chance`, `cond_chance`, `total_pos`
  → `p_play_classic`, `p_cond_classic`, `p_g_classic`
- Pillar lists `play_probs`, `cond_probs`
  → `p_pillar_play[pid]`, `p_pillar_cond[pid]` (dicts, not lists)

### 6. Session-state keys (logic/session_keys.py + raw f-strings)
Decision required: rename or leave alone?
- `comparison_esl_pos` → `p_g_esl` (breaks any saved CSV that references this key)
- `comparison_classic_pos` → `p_g_classic`
- `comparison_classic_bel`, `comparison_classic_pl` → `p_g_classic_bel`, `_pl`
- `classic_charge`, `classic_closure`, ... → ROSE override input slots,
   could become `rose_input_charge`, etc.
- `locked_ESL`, `locked_Classic POS` → `locked_p_g_esl`, `locked_p_g_classic`

**Recommendation:** rename session keys ONLY if/when CSV import is also
versioned (so old exports can be migrated). Otherwise leave session keys
intact and update only the human-facing constants.

### 7. CSV export column headers (`_build_full_export_csv`)
Currently writes:
- `## Method Summary` → keep section name, change row labels:
  - `ESL`  → `P(G, ESL)`
  - `Classic POS` → `P(G, Classic)`
- `## ESL Risk Element Detail` columns:
  - `estimated_pos` → `p_g_esl`
  - `classic_pos`   → `p_g_classic`
- `## Classic POS Source` and `## Classic POS Operators` keep names.

**Bump CSV format version** when this is done (`Meta/Version` row) so importer
can detect old format and apply migration.

### 8. `components/detail_risk_table.py`
- Columns `Pos.%`, `Unc.%`, `Neg.%`, `POS%` → rename to use Policy P:
  - `Pos.%` → `Policy P %` (the point estimate per element)
  - keep `Unc.%`, `Neg.%` (these are White and S_against shown for context)

### 9. `components/audit.py`
- `render_audit_panel(pos=, method=, ...)` — `method` is passed as "ESL" or
  "Classic POS" today. Future: `"P(G, ESL)"`, `"P(G, Classic)"`.
- `locked_{method}` session key changes accordingly.

### 10. `components/element_detail_cam.py`
- The CAM panel's POS readouts should switch from "Policy POS" caption to
  "Policy P" or `P_policy(element)`.
- Element-level value displayed inside the panel: presented today as plain
  POS. Future label: `P_policy(element)`.

### 11. `components/esl_analysis.py`
- `_render_esl_ratio_plot_and_validation` — axes labelled "POS", "Pg",
  "log(For/Against)" — update axis labels to `Policy P`, `P(pillar)`, etc.
- Sensitivity tornado uses `Total Pg` label — change to `P(G, ESL)`.

### 12. `components/tabs/tab_analysis.py`
- "Uncertainty Index" UI math labels — keep `UI` symbol but update underlying
  references from "Pg" to `P(pillar)`.

### 13. Tab labels in `app.py` `_render_tabs`
- "Classic POS" tab name → `P(G, Classic) — detail`
- "ESL Pg" → `P(G, ESL) — primary` (if a tab name)

---

## Migration considerations

1. **Hard break on CSV import:** any pre-rename CSV will fail to import after
   session-state keys change. Document this and bump `Meta/Version` to mark
   the format change.

2. **Saved prospect templates:** the default templates in `app.py`
   `build_models()` use the same pillar-id keys. No code change needed
   there — pillar ids stay as `"Charge"`, `"Closure"`, etc.

3. **Test coverage:** after rename, run the full prospect flow end-to-end
   (Play → Cond → Analysis → Dashboard → CSV export → CSV reimport) and
   verify every column matches the spec above.

4. **One-shot rename script:** consider writing a sed/Python script that does
   the bulk identifier substitution rather than doing it by hand across ~20
   files. Apply the script, then run the app and fix what breaks.

---

## When to do this

This refactor adds zero user-visible value on its own — the UI already speaks
the new vocabulary after Phase 3. The code rename is for *future maintainers*
to keep symbols consistent with the spoken vocabulary, and to prepare for the
DHI uplift work where `POS` enters as a first-class concept.

Recommended trigger: do it as the first step when DHI uplift work begins, so
the new code can introduce `POS` cleanly alongside the renamed `P(G, ESL)` /
`P(G, Classic)` / `P(G, DHI)` family.
