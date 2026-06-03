# Archived: Bayesian Network method

Archived on 2026-05-19. Removed from the main E-POS application because:

- The method requires `pgmpy` (a non-trivial dependency not always available)
- It was incomplete — the BN tab was never wired into the 6-tab UI; results only
  appeared as a side-column in the comparison table
- It adds significant cognitive load for oil and gas assessors coming from ROSE/GeoX
  who are not familiar with Bayesian Networks or Conditional Probability Tables
- The causal DAG is hard-coded to 4 pillars and does not respect custom risk models

## Files

| File | Original location | Description |
|------|------------------|-------------|
| `bn_logic.py` | `logic/bn_logic.py` | 8-node causal petroleum DAG, CPT definition, pgmpy inference wrapper |
| `bayesian_tab.py` | `methods/bayesian.py` | Streamlit render function for the BN assessment tab |

## To reinstate

1. Copy `bn_logic.py` back to `logic/bn_logic.py`
2. Copy `bayesian_tab.py` back to `methods/bayesian.py`
3. In `components/comparison.py`, re-add:
   ```python
   from logic.bn_logic import build_petroleum_bn, query_pos
   ```
   and restore the BN computation block in `render_comparison()`.
4. In `components/prospect_hub.py`, re-add `bn_pos_total` to `_compute_esl_for_hub`,
   `build_logic_table`, `build_prospect_risk_data`, and `_build_full_export_csv`.
5. In `components/tabs/tab_dashboard.py`, pass `bn_pos=st.session_state.get("comparison_bn_pos")`
   back to `render_comparison()` and `build_prospect_risk_data()`.
6. In `components/tabs/tab_analysis.py`, restore the Bayesian Network expander section.
7. In `components/tabs/tab_theory.py`, restore the BN theory expander.

## Design notes for future implementation

The current BN is a "soft AND" of the four ROSE pillars through a causal DAG.
It is NOT independent of ESL — root priors are derived from ESL Policy POS values.
This means it is best framed as a **structural sensitivity check**, not an independent
third method.

The hard work for a proper reinstall is:
- Making the DAG topology editable (not hard-coded to 4 pillars)
- Properly eliciting CPTs from analogue data rather than using fixed defaults
- Deciding whether the BN runs on play-level or conditional-level probabilities
