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


def resolve_stance() -> float:
    """Return the effective global stance weight from Streamlit session state.

    Reads the same keys as the ESL tab in app.py:
      use_policy_weight = True  → company default (COMPANY_DEFAULT_WEIGHT)
      use_policy_weight = False → user's slider value (uncertainty_weight_slider)
    """
    if st.session_state.get("use_policy_weight", True):
        return COMPANY_DEFAULT_WEIGHT
    return float(st.session_state.get("uncertainty_weight_slider", COMPANY_DEFAULT_WEIGHT))


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
