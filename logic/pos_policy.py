"""Canonical POS policy helpers — single source of truth.

All modules should import from here rather than redefining the formula.

policy_pos()     : ESL → POS conversion (returns 0-1)
resolve_stance() : read effective global w from Streamlit session state
"""
from __future__ import annotations

import streamlit as st

# Company-default stance (neutral: unknowns split 50/50)
COMPANY_DEFAULT_WEIGHT: float = 0.5


def policy_pos(s_for: float, s_against: float, w: float = COMPANY_DEFAULT_WEIGHT) -> float:
    """Estimated POS = Green + w × White  (ESL midpoint formula, 0-1 scale).

    Args:
        s_for:     Support For  (green mass, 0 ≤ s_for ≤ 1)
        s_against: Support Against (red mass, 0 ≤ s_against ≤ 1)
        w:         Stance / uncertainty weight (0 = pessimistic, 1 = optimistic)

    Returns:
        POS ∈ [0, 1]
    """
    green = max(0.0, min(1.0, float(s_for)))
    red   = max(0.0, min(1.0, float(s_against)))
    white = max(0.0, 1.0 - green - red)
    return green + float(w) * white


# Default prospect base rate used by the "base rate" stance (Exxon 2018: "geology
# is not a coin — revert the unknowns to the base rate, generally ≠ 0.5").
DEFAULT_BASE_RATE: float = 0.30


def resolve_stance() -> float:
    """Return the effective global stance weight *w* from Streamlit session state.

    Three modes, logged in ``stance_mode``:
      ``neutral``    → company default 0.5 (unknowns split 50/50 — a coin)
      ``custom``     → the user's ``uncertainty_weight_slider``
      ``base_rate``  → ``stance_base_rate`` — reverts the white band to the prospect
                       base rate instead of a coin (Policy P = S_for + base_rate·White)

    Legacy fallback: if ``stance_mode`` is unset, derive it from the old
    ``use_policy_weight`` flag so existing sessions and saved prospects keep working.
    """
    mode = st.session_state.get("stance_mode")
    if mode is None:
        mode = "neutral" if st.session_state.get("use_policy_weight", True) else "custom"
    if mode == "custom":
        return float(st.session_state.get("uncertainty_weight_slider", COMPANY_DEFAULT_WEIGHT))
    if mode == "base_rate":
        return max(0.0, min(1.0, float(st.session_state.get("stance_base_rate", DEFAULT_BASE_RATE))))
    return COMPANY_DEFAULT_WEIGHT


def get_active_pillars() -> list[dict]:
    """Return [{pillar_id, display_name, color}] from the active risk model.

    Falls back to the legacy 4-pillar structure when no model is loaded.
    """
    model = st.session_state.get("active_risk_model")
    if model is not None:
        return [
            {"pillar_id": p.pillar_id, "display_name": p.display_name, "color": p.color}
            for p in model.pillars
        ]
    return [
        {"pillar_id": "Charge",    "display_name": "Charge",    "color": "#F69292"},
        {"pillar_id": "Closure",   "display_name": "Closure",   "color": "#8CB7FC"},
        {"pillar_id": "Reservoir", "display_name": "Reservoir", "color": "#FFD44B"},
        {"pillar_id": "Retention", "display_name": "Retention", "color": "#B5E6A2"},
    ]
