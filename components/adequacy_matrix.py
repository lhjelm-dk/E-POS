"""Chance Factor Adequacy Matrix - maps evidence quality to probability range. Step 4."""

from __future__ import annotations

import streamlit as st

from components.colors import cos_color, COS_SCALE

# Grid: Confidence (row) × Geological News (col) → (low_pct, high_pct) or None (invalid)
MATRIX_GRID = {
    ("High", "Bad News"): (0, 20),
    ("High", "Coin Toss"): None,  # UNUSUAL: flagged for review in the table, not forbidden
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
                cells += ("<td style='border:1px solid #444; padding:8px; background:#fef3c7; "
                          "color:#92400e; font-style:italic;'>⚠ Unusual — review</td>")
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


def render_adequacy_matrix_reference() -> None:
    """Render the Chance Factor Adequacy Matrix as reference only (no inputs)."""
    st.caption(
        "Reference: Map geological evidence quality to a recommended probability range. "
        "Cells use the **shared Probability colour scale** (same as the Reference Tables "
        "and DFI views). Values are now derived from ESL; use this as calibration guidance."
    )
    st.markdown(_adequacy_table_html(), unsafe_allow_html=True)


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
                    "High confidence with a genuine coin-toss outlook is unusual: either the "
                    "confidence is overstated, or the news is not truly balanced. It is permitted, "
                    "but document why."
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
