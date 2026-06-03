# DEPRECATED — removed from app.py v3. Retained in case future multi-prospect portfolio mode is added.
"""Portfolio analysis — shared play risk, correct vs independent formula."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go


def render_portfolio() -> None:
    """Render portfolio analysis panel for shared-play prospects."""
    st.subheader("Portfolio Analysis — Shared Play Risk")
    st.markdown(
        "When multiple prospects share the same play, their risks are **not independent**. "
        "Use this panel to compute the correct portfolio POS accounting for shared play risk. "
        "The independent formula (1-(1-POS)^N) **overstates** the chance of success."
    )

    p_play = st.slider(
        "Shared play probability P(play)",
        0.0,
        1.0,
        0.5,
        0.05,
        key="port_p_play",
        help="The probability that the shared geological play works at all — "
        "source-migration system active, carrier beds present, etc.",
    )
    n_prospects = st.number_input(
        "Number of prospects in portfolio",
        1,
        20,
        3,
        key="port_n",
    )
    st.markdown("**Individual conditional prospect probabilities** P(cond_i):")
    cond_probs = []
    cols = st.columns(min(n_prospects, 5))
    for i in range(n_prospects):
        with cols[i % 5]:
            cp = st.slider(
                f"Prospect {i+1}",
                0.0,
                1.0,
                0.5,
                0.05,
                key=f"port_cond_{i}",
            )
            cond_probs.append(cp)

    individual_pos = [p_play * cp for cp in cond_probs]
    all_cond_fail = 1.0
    for cp in cond_probs:
        all_cond_fail *= 1.0 - cp
    p_at_least_one_correct = p_play * (1.0 - all_cond_fail)

    all_fail_independent = 1.0
    for pos_i in individual_pos:
        all_fail_independent *= 1.0 - pos_i
    p_at_least_one_wrong = 1.0 - all_fail_independent
    overstatement = p_at_least_one_wrong - p_at_least_one_correct

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Correct portfolio P(≥1 discovery)", f"{p_at_least_one_correct*100:.1f}%")
    c2.metric("Independent formula (overestimates)", f"{p_at_least_one_wrong*100:.1f}%")
    c3.metric("Overstatement", f"{overstatement*100:.1f}%", delta_color="inverse")

    if overstatement > 0.05:
        st.error(
            f"The independent formula overstates portfolio chance by {overstatement*100:.1f}%. "
            f"Use the correct value ({p_at_least_one_correct*100:.1f}%) for portfolio reporting."
        )

    labels = [f"P{i+1}" for i in range(n_prospects)]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Individual POS",
            x=labels,
            y=[p * 100 for p in individual_pos],
            marker_color="#2563eb",
        )
    )
    fig.add_hline(
        y=p_at_least_one_correct * 100,
        line_dash="solid",
        line_color="#16a34a",
        line_width=2,
        annotation_text=f"Portfolio P(≥1): {p_at_least_one_correct*100:.1f}%",
    )
    fig.add_hline(
        y=p_at_least_one_wrong * 100,
        line_dash="dash",
        line_color="#dc2626",
        line_width=1.5,
        annotation_text=f"Independent (wrong): {p_at_least_one_wrong*100:.1f}%",
    )
    fig.update_layout(
        title="Individual Prospect POS vs Portfolio Chance",
        yaxis_title="POS (%)",
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Green line = correct shared-play portfolio POS. Red dashed = wrong independent formula.")
