"""Chance Factor Adequacy Matrix - maps evidence quality to probability range. Step 4."""

from __future__ import annotations

import streamlit as st
import numpy as np
import plotly.graph_objects as go

from components.colors import cos_color, COS_SCALE

# Grid: Confidence (row) × Geological News (col) → (low_pct, high_pct) or None (invalid)
MATRIX_GRID = {
    ("High", "Bad News"): (0, 20),
    ("High", "Coin Toss"): None,  # INVALID: excluded from heatmap (no fill)
    ("High", "Good News"): (80, 100),
    ("Medium", "Bad News"): (20, 40),
    ("Medium", "Coin Toss"): (40, 60),
    ("Medium", "Good News"): (60, 80),
    ("Low", "Bad News"): (30, 45),
    ("Low", "Coin Toss"): (45, 55),
    ("Low", "Good News"): (55, 70),
}

CONFIDENCE_OPTIONS = ["High", "Medium", "Low"]
NEWS_OPTIONS = ["Bad News", "Coin Toss", "Good News"]


def _cos_colorscale_discrete(step_pct: int = 10) -> list:
    """Stepped plotly colorscale built from the shared CoS palette, banded at
    ``step_pct`` intervals (default 10 pp) so the heatmap reads as discrete
    probability bands consistent with the reference tables."""
    bounds = list(range(0, 101, step_pct))
    scale = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i] / 100.0, bounds[i + 1] / 100.0
        col = cos_color((bounds[i] + bounds[i + 1]) / 200.0)
        scale.append([lo, col])
        scale.append([hi, col])
    return scale


def _text_on(bg_hex: str) -> str:
    """Pick black/white text for contrast against a hex background."""
    h = bg_hex.lstrip("#")
    if len(h) != 6:
        return "#111827"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#111827" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def _adequacy_table_html() -> str:
    """Build the 3×3 adequacy table, colouring each cell with the shared CoS
    scale at its range midpoint. Single source for both render paths."""
    cells = ""
    for conf in CONFIDENCE_OPTIONS:
        cells += (
            f"<tr><td style='border:1px solid #444; padding:8px; background:#e5e7eb; "
            f"font-weight:600;'>{conf} Confidence</td>"
        )
        for news in NEWS_OPTIONS:
            val = MATRIX_GRID.get((conf, news))
            if val is None:
                cells += ("<td style='border:1px solid #444; padding:8px; background:#ffffff; "
                          "color:#374151; font-style:italic;'>N/A, not valid</td>")
            else:
                lo, hi = val
                bg = cos_color((lo + hi) / 200.0)
                fg = _text_on(bg)
                cells += (f"<td style='border:1px solid #444; padding:8px; background:{bg}; "
                          f"color:{fg}; font-weight:600;'>{lo}% – {hi}%</td>")
        cells += "</tr>"

    # Shared-scale legend strip
    legend = "".join(
        f"<span style='display:inline-block;padding:2px 7px;margin:1px;border-radius:3px;"
        f"background:{col};color:{_text_on(col)};font-size:0.72rem;'>{lbl}</span>"
        for lo, hi, col, lbl in COS_SCALE
    )
    return f"""
    <table style="width:100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem;">
    <tr><th style="border:1px solid #444; padding:8px; background:#1f2937; color:white;"></th>
    <th style="border:1px solid #444; padding:8px; background:#7f1d1d; color:white;">Bad News</th>
    <th style="border:1px solid #444; padding:8px; background:#713f12; color:white;">Coin Toss</th>
    <th style="border:1px solid #444; padding:8px; background:#14532d; color:white;">Good News</th></tr>
    {cells}
    </table>
    <div style="margin:-0.4rem 0 0.6rem;">
      <span style="font-size:0.74rem;color:#6b7280;margin-right:6px;">Probability scale (shared):</span>
      {legend}
    </div>
    """


def _adequacy_heatmap_fig(step_pct: int = 10) -> go.Figure:
    """Continuous heatmap of the matrix, coloured with the shared CoS palette
    banded at ``step_pct`` intervals."""
    xs = np.linspace(0, 100, 100)
    ys = np.linspace(0, 100, 100)
    Z = np.full((len(ys), len(xs)), np.nan)
    for i, y in enumerate(ys):
        conf = "High" if y >= 66 else ("Medium" if y >= 33 else "Low")
        for j, x in enumerate(xs):
            news = "Good News" if x >= 66 else ("Coin Toss" if x >= 33 else "Bad News")
            val = MATRIX_GRID.get((conf, news))
            Z[i, j] = np.nan if val is None else (val[0] + val[1]) / 2
    fig_2d = go.Figure(
        go.Heatmap(
            z=Z, x=xs, y=ys,
            colorscale=_cos_colorscale_discrete(step_pct),
            zmin=0, zmax=100,
            colorbar=dict(title="Recommended P (%)", tickvals=list(range(0, 101, step_pct))),
            hovertemplate="News: %{x:.0f}%<br>Confidence: %{y:.0f}%<br>P: %{z:.0f}%<extra></extra>",
        )
    )
    fig_2d.update_layout(
        template="plotly_white", plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        title=f"Chance Factor Adequacy Matrix — {step_pct} pp bands (shared probability scale)",
        xaxis=dict(
            title="Geological News (0%=Bad → 100%=Good)",
            tickmode="linear", tick0=0, dtick=step_pct, range=[0, 100],
            ticksuffix="%", showgrid=True, gridcolor="rgba(0,0,0,0.08)",
        ),
        yaxis=dict(
            title="Confidence (0%=Low → 100%=High)",
            tickmode="linear", tick0=0, dtick=step_pct, range=[0, 100],
            ticksuffix="%", showgrid=True, gridcolor="rgba(0,0,0,0.08)",
        ),
        height=400, margin=dict(t=50, b=50),
    )
    return fig_2d


def render_adequacy_matrix_reference() -> None:
    """Render the Chance Factor Adequacy Matrix as reference only (no inputs)."""
    st.caption(
        "Reference: Map geological evidence quality to a recommended probability range. "
        "Cells and heatmap use the **shared Probability colour scale** (same as the "
        "Reference Tables and DFI views); the heatmap is banded at 10 pp. "
        "Values are now derived from ESL; use this as calibration guidance."
    )
    st.markdown(_adequacy_table_html(), unsafe_allow_html=True)
    st.plotly_chart(_adequacy_heatmap_fig(10), use_container_width=True,
                    key="adequacy_matrix_ref_v3")
    st.caption("Invalid cell (High confidence × Coin Toss) has no colour on the heatmap; see table above.")


def render_adequacy_matrix() -> None:
    """Render the Chance Factor Adequacy Matrix as HTML table + pillar selectors."""
    st.subheader("Chance Factor Adequacy Matrix")
    st.caption(
        "Map geological evidence quality to a recommended probability range. "
        "Prevents anchoring bias and forces explicit justification."
    )

    st.markdown(_adequacy_table_html(), unsafe_allow_html=True)

    # Pillar ids and display names are now both "Closure" (post-rename, no Trap alias).
    pillars = ["Charge", "Closure", "Reservoir", "Retention"]
    for pillar in pillars:
        key_conf = f"adequacy_conf_{pillar}"
        key_news = f"adequacy_news_{pillar}"
        key_prob = f"adequacy_prob_{pillar}"
        key_just = f"adequacy_just_{pillar}"
        if key_conf not in st.session_state:
            st.session_state[key_conf] = "Medium"
        if key_news not in st.session_state:
            st.session_state[key_news] = "Coin Toss"
        if key_prob not in st.session_state:
            st.session_state[key_prob] = 0.5
        if key_just not in st.session_state:
            st.session_state[key_just] = ""

        with st.expander(f"{pillar} — Adequacy selection", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                conf = st.radio(
                    "Confidence level",
                    CONFIDENCE_OPTIONS,
                    index=CONFIDENCE_OPTIONS.index(st.session_state[key_conf]),
                    key=key_conf,
                    horizontal=True,
                )
            with c2:
                news = st.radio(
                    "Geological news",
                    NEWS_OPTIONS,
                    index=NEWS_OPTIONS.index(st.session_state[key_news]),
                    key=key_news,
                    horizontal=True,
                )
            val = MATRIX_GRID.get((conf, news))
            if val is None:
                st.warning(
                    "High confidence with a coin-toss geological outlook is not a valid combination. "
                    "Please reassess — either confidence is lower, or the news is not truly balanced."
                )
                low, high = 40, 60  # fallback for slider
            else:
                low, high = val
            mid = (low + high) / 200.0
            st.caption(f"Suggested range: {low}% – {high}%")
            st.slider(
                f"P({pillar}) — accept or override",
                0.0,
                1.0,
                mid,
                0.01,
                key=key_prob,
            )
            st.text_area(
                "Justification (required for audit trail)",
                value=st.session_state[key_just],
                key=key_just,
                placeholder="Document evidence quality and geological news...",
            )

    with st.expander("2D Adequacy Matrix Plot", expanded=False):
        st.plotly_chart(_adequacy_heatmap_fig(10), use_container_width=True,
                        key="adequacy_matrix_expander_v3")
        st.caption("Invalid cell (High confidence × Coin Toss) has no colour on the heatmap; see table above.")
