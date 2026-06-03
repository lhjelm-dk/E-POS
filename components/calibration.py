"""Rose calibration anchors for prospect risking sliders.

Reference: Rose, P.R. (2001). Risk Analysis and Management of Petroleum Exploration
Ventures. AAPG Methods in Exploration Series No. 12. American Association of Petroleum
Geologists. ISBN 978-0-89181-663-8.
"""

from __future__ import annotations

import streamlit as st

ROSE_RANGES = {
    "Charge": (20, 85, 55, "Regional source presence, maturity, migration fairway"),
    "Closure": (30, 95, 65, "Structural/stratigraphic trap geometry at target depth"),
    "Reservoir": (40, 95, 72, "Reservoir facies presence and effective porosity"),
    "Retention": (50, 90, 70, "Seal capacity and preservation"),
}


def render_calibration_anchor(category: str, current_p: float) -> None:
    """Show Rose calibration reference and whether current value is within typical range."""
    low, high, median, desc = ROSE_RANGES.get(category, (0, 100, 50, ""))
    pos_pct = current_p * 100
    color = "#16a34a" if low <= pos_pct <= high else "#dc2626"
    if pos_pct > high:
        msg = f"Above typical range ({high}%). Requires exceptional evidence justification."
    elif pos_pct < low:
        msg = f"Below typical range ({low}%). Confirm this is not a default — document rationale."
    else:
        msg = f"Within typical range ({low}–{high}%, median {median}%). Consistent with analogues."
    st.markdown(
        f'<div style="color:{color}; font-size:0.78rem; margin-top:2px;">'
        f"Rose calibration (Rose 2001, AAPG Methods 12): {low}–{high}% (median {median}%) — {msg}"
        f"</div>",
        unsafe_allow_html=True,
    )
