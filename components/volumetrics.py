"""Volumetrics and EMV component — Expected Resource, EMV, break-even POS."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import numpy as np


def render_volumetrics(pos: float, prospect_title: str = "Prospect", key_prefix: str = "") -> None:
    """Render volumetrics section: NRV inputs, Expected Resource, EMV, sensitivity chart."""
    k = key_prefix or "vol"
    st.subheader("Volumetrics & Expected Resource")
    st.caption("Enter unrisked resource estimates to compute Expected Resource and EMV.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Unrisked Resource Estimates (MMboe or Bscf)**")
        nrv_p90 = st.number_input("NRV P90 (low case)", 0.0, 10000.0, 50.0, key=f"{k}_p90")
        nrv_p50 = st.number_input("NRV P50 (base case)", 0.0, 10000.0, 150.0, key=f"{k}_p50")
        nrv_p10 = st.number_input("NRV P10 (high case)", 0.0, 10000.0, 400.0, key=f"{k}_p10")
    with col2:
        st.markdown("**Economics (optional)**")
        netback = st.number_input("Netback (USD/BOE)", 0.0, 200.0, 25.0, key=f"{k}_netback")
        rec_fac = st.number_input("Recovery factor (%)", 0.0, 100.0, 35.0, key=f"{k}_recfac")
        drill_cost = st.number_input("Dry hole cost (MUSD)", 0.0, 5000.0, 50.0, key=f"{k}_drill")

    er_p50 = pos * nrv_p50
    er_p90 = pos * nrv_p90
    er_p10 = pos * nrv_p10

    recoverable_p50 = nrv_p50 * (rec_fac / 100.0)
    gross_value = recoverable_p50 * netback
    emv = pos * gross_value - (1 - pos) * drill_cost

    st.divider()
    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("POS", f"{pos*100:.1f}%")
    rc2.metric("Expected Resource (P50)", f"{er_p50:.0f} MMboe")
    rc3.metric("ER range", f"{er_p90:.0f}–{er_p10:.0f}")
    rc4.metric(
        "EMV",
        f"{emv:.0f} MUSD",
        delta="Attractive" if emv > 0 else "Negative EMV",
        delta_color="normal" if emv > 0 else "inverse",
    )

    pos_range = np.linspace(max(0.01, pos - 0.15), min(0.99, pos + 0.15), 30)
    emv_range = pos_range * gross_value - (1 - pos_range) * drill_cost
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=pos_range * 100,
            y=emv_range,
            mode="lines",
            line=dict(color="#2563eb", width=2),
            name="EMV",
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#dc2626", line_width=1)
    fig.add_vline(
        x=pos * 100,
        line_dash="dash",
        line_color="#1f2937",
        line_width=1.5,
        annotation_text=f"Current POS {pos*100:.1f}%",
    )
    fig.update_layout(
        title="EMV vs POS sensitivity",
        xaxis_title="POS (%)",
        yaxis_title="EMV (MUSD)",
        height=280,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    if gross_value > drill_cost:
        breakeven_pos = drill_cost / gross_value
        st.caption(
            f"Break-even POS: {breakeven_pos*100:.1f}% — drill if POS > {breakeven_pos*100:.1f}% and EMV > 0."
        )
    else:
        st.warning(
            "Gross value < dry hole cost — negative EMV at all POS values. "
            "Reconsider commercial terms or resource estimate."
        )
