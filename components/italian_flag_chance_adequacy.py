"""
Italian Flag — Chance Adequacy Matrix (POS vs committed evidence).

Policy POS = S(H) + w × White. Y-axis = committed fraction S_p + S_n (can exceed 100% if overcommitted).

For fixed certainty C = S_p + S_n with S_p, S_n ∈ [0,1], Policy POS range:
  C ≤ 1:  min = w(1−C),  max = w + (1−w)C
  C > 1:  white = 0  →  POS = S_p only,  min = C−1,  max = 1

No coloured “adequacy zones” are drawn: POS vs (S_p+S_n) does not appear in Quintessa’s ESL
Guide as a standard zoned chart. Bands are organisation-specific (see expander in UI).
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from logic.pos_policy import (
    COMPANY_DEFAULT_WEIGHT,  # noqa: F401 — single source of truth
    policy_pos,              # noqa: F401 — single source of truth (re-used below)
)

RISK_ELEMENTS = [
    "Risk element Alpha",
    "Reservoir Presence",
    "Charge adequacy",
    "Closure",
    "Seal effectiveness",
    "Retention / preservation",
    "Custom",
]


def _calculate_flag(s_for: float, s_against: float) -> tuple[float, float, float, float]:
    green = max(0.0, min(1.0, float(s_for)))
    red = max(0.0, min(1.0, float(s_against)))
    overlap = max(0.0, green + red - 1.0)
    white = max(0.0, 1.0 - green - red + overlap)
    return green, white, red, overlap


def policy_pos_min_max_for_certainty(c: float, w: float) -> tuple[float, float]:
    """
    Min and max Policy POS over allocations (S_p, S_n) with each in [0,1] and S_p + S_n = c.

    Uses the same flag algebra as the app: white = 0 when c > 1 (overlap absorbs uncommitted).
    """
    w = float(w)
    c = float(c)
    if c <= 1.0:
        lo = w * (1.0 - c)
        hi = w + (1.0 - w) * c
    else:
        lo = max(0.0, c - 1.0)
        hi = 1.0
    return max(0.0, min(1.0, lo)), max(0.0, min(1.0, hi))


def _min_max_pos_curves_y_pct(w: float, y_hi_pct: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (certainty_y_pct, pos_min_pct, pos_max_pct) for plotting."""
    c_max = max(1.001, y_hi_pct / 100.0)
    c_vals = np.linspace(0.0, c_max, 250)
    pmin, pmax = [], []
    for c in c_vals:
        lo, hi = policy_pos_min_max_for_certainty(c, w)
        pmin.append(100.0 * lo)
        pmax.append(100.0 * hi)
    return 100.0 * c_vals, np.array(pmin), np.array(pmax)


def render_italian_flag_chance_adequacy_matrix() -> None:
    st.caption(
        "Policy POS vs certainty **(S_p+S_n)** at your **w**. **Brown / green curves** = min and max Policy POS "
        "for each certainty level (all splits of green vs red). **No fixed coloured zones**; see advisory expander."
    )
    use_hub_w = st.checkbox("Lock uncertainty weight to Prospect Hub value", value=True, key="ifcam_use_hub_w")
    from logic.pos_policy import resolve_stance
    hub_w = resolve_stance()

    ctrl1, ctrl2 = st.columns([1, 2])
    with ctrl1:
        element = st.selectbox(
            "Risk element (label only)",
            RISK_ELEMENTS,
            index=0,
            key="ifcam_element",
        )
        s_p = st.slider("Positive evidence (S_p — Green)", 0.0, 1.0, 0.25, 0.01, key="ifcam_sp")
        s_n = st.slider("Negative evidence (S_n — Red)", 0.0, 1.0, 0.20, 0.01, key="ifcam_sn")
        if use_hub_w:
            w = hub_w
            st.caption(f"Uncertainty weight **w** = {w:.2f} (from Prospect Hub)")
        else:
            w = st.slider("Uncertainty weight (w)", 0.0, 1.0, 0.40, 0.01, key="ifcam_w")

    certainty_frac = s_p + s_n
    certainty_pct = 100.0 * certainty_frac
    green, white, red, overlap = _calculate_flag(s_p, s_n)
    pos = policy_pos(s_p, s_n, w)
    pos_pct = pos * 100.0

    lo_b, hi_b = policy_pos_min_max_for_certainty(certainty_frac, w)
    within = lo_b - 1e-9 <= pos <= hi_b + 1e-9

    with ctrl2:
        st.metric("Probability of Success (Policy POS)", f"{pos_pct:.1f}%")
        st.metric("Certainty (S_p + S_n)", f"{certainty_pct:.1f}%")
        st.metric("Uncertainty (White)", f"{white * 100:.1f}%")
        if overlap > 0:
            st.caption(f"Overcommitment (Yellow): {overlap * 100:.1f}% — conflicting evidence is allowed; document it.")
        w_label = (
            "Cautious / conservative (low w — little white counts as success)"
            if w < 0.35
            else "Optimistic (high w — more white counts as success)"
            if w > 0.65
            else "Balanced mid‑point"
        )
        st.caption(f"w → {w_label}")

    with st.container(border=True):
        st.caption("**How to read w (ranges)**")
        st.markdown(
            """
            - **Low w (≈0–0.35):** Only committed green counts; white barely lifts POS — conservative.
            - **Mid w (≈0.35–0.65):** Standard Policy POS blend (company default often 0.5).
            - **High w (≈0.65–1):** Unknowns largely treated as working in your favour — use with care.
            """
        )

    with st.container(border=True):
        st.caption('**Advisory — how adequacy zones could be defined (ESL, TESLA, Rose)**')
        st.markdown(
            """
            **Why there are no green/red/grey zones on this plot**

            - **Evidence Support Logic (ESL)** is built on **S(H), S(¬H), and white** (and conflict when both are high).
              **Policy POS = S(H) + w × white** is a *deliberate choice of w*, not a unique “correct” probability.
              Quintessa’s materials emphasise **transparent evidence** and **interval-style** thinking more than a
              single traffic-light partition in **POS × (S_p+S_n)** space.
            - **TESLA / Quintessa** often use **ratio-style** views (e.g. support ratio vs **residual uncertainty**),
              not the same axes as here. Any coloured *regions* in such plots are typically **calibration or
              workshop conventions**, not universal constants; see *Evidence Support Logic: A Guide for TESLA Users*
              (e.g. v3.0) and [Quintessa ESL](https://quintessa.org/services/decision-support/evidence-support-logic).
            - **Rose (2001, AAPG Methods 12)** “chance adequacy” is usually framed as **matrix guidance**
              (confidence × geological news → **recommended P ranges**), implemented elsewhere in this app as the
              **Chance Factor Adequacy Matrix** reference table — **orthogonal** to a POS-vs-certainty cross-plot.
              Rose stresses **independent factors**, **analogue calibration**, and **reality checks**, not fixed vertical
              POS cut-offs on this diagram.

            **Defensible ways to define zones later (if your organisation wants them)**

            1. **Feasibility envelope only (current chart):** treat the **brown–green band** as the *mathematical*
               range of Policy POS at fixed **(certainty, w)**. “Adequate” = inside the band; “inadequate” is *not*
               defined without extra rules.
            2. **Calibration to outcomes:** set POS or ratio thresholds from **historical success rates** by play or
               element type (empirical Bayes / reliability diagrams) — requires data and maintenance.
            3. **Company policy:** e.g. flag if Policy POS is below a fixed percentage unless documented — governance, not geology.
            4. **Distance inside the band:** e.g. position between min and max curve (how “for-dominated” vs
               “against-dominated” at this certainty) — still needs agreed interpretation.
            5. **Reuse Rose matrix in another view:** map this assessment into **confidence × news** and read off
               suggested P bands from the matrix — keeps one coherent story.

            **Insufficient-evidence / thin-commitment bands** (low **S_p+S_n**) were removed: they mixed **heuristic
            thresholds** with **w** in a way that is easy to misread as “standard ESL.” If you reintroduce them,
            document the formula and tie them to **analogues or policy**, not to Quintessa/Rose as fixed law.
            """
        )

    # --- Build figure: POS on x, reversed; Certainty on y ---
    y_max = max(105.0, certainty_pct * 1.05, 100.0 * min(s_p + s_n, 1.5))
    fig = go.Figure()

    cy, px_min, px_max = _min_max_pos_curves_y_pct(w, y_max)
    x_max = [float(v) for v in px_max]
    y_cy = [float(v) for v in cy]
    x_min = [float(v) for v in px_min]

    fig.add_trace(
        go.Scattergl(
            x=x_max,
            y=y_cy,
            mode="lines",
            line=dict(color="#15803d", width=4),
            name="Max POS | C and w",
            hovertemplate="Max POS %{x:.1f}%<br>Certainty %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scattergl(
            x=x_min,
            y=y_cy,
            mode="lines",
            line=dict(color="#9a3412", width=4),
            name="Min POS | C and w",
            hovertemplate="Min POS %{x:.1f}%<br>Certainty %{y:.1f}%<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[pos_pct],
            y=[certainty_pct],
            mode="markers+text",
            marker=dict(size=16, color="#1e3a8a", line=dict(color="white", width=2)),
            text=[element[:22] + "…" if len(element) > 22 else element],
            textposition="top center",
            name="Current assessment",
            hovertemplate="POS %{x:.1f}%<br>Certainty %{y:.1f}%<extra></extra>",
        )
    )

    if within:
        st.success(
            f"**Inside feasibility band:** For certainty **{certainty_pct:.1f}%** and this **w**, Policy POS "
            f"lies between **{100*lo_b:.1f}%** and **{100*hi_b:.1f}%** (curves at that height)."
        )
    else:
        st.warning("Assessment is numerically outside the min–max band (unexpected — check inputs).")

    fig.update_layout(
        template="plotly_white",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        title=f"Chance Adequacy Matrix: {element}",
        xaxis_title="Probability of Success (Policy POS %)",
        yaxis_title="Certainty (S_p + S_n) %",
        xaxis=dict(
            range=[100, 0],
            autorange=False,
            showgrid=True,
            gridcolor="rgba(0,0,0,0.08)",
            zeroline=False,
            fixedrange=False,
        ),
        yaxis=dict(
            range=[0, float(y_max)],
            showgrid=True,
            gridcolor="rgba(0,0,0,0.08)",
            zeroline=False,
            fixedrange=False,
        ),
        height=520,
        margin=dict(t=56, b=100, l=56, r=28),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
        hovermode="closest",
        shapes=[],
        annotations=[],
    )
    st.plotly_chart(fig, use_container_width=True, theme=None, key="ifcam_pos_vs_certainty_v8")

    st.caption(
        "Only the **min/max curves** and your point are drawn. Any coloured adequacy zones would be "
        "organisation-specific; see the advisory expander."
    )
    st.markdown(
        """
        **Expert note:** Certainty here is **committed** evidence (S_p+S_n). If S_p+S_n > 1, you are in **conflict**
        (Yellow) — valid ESL; interpret Policy POS together with that conflict.
        """
    )
