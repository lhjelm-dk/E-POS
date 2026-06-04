"""Shared Risk-Summary helpers — used by ESL (Analysis tab) and P(G, Classic) detail.

Public helpers:

- ``render_pg_ui_trajectory(...)``  — stance-trajectory plot of P(G) vs UI
- ``render_top5_weakest(...)``      — Top-5 lowest Policy P elements with mini Italian Flag bars
- ``compute_esl_envelope_analytical(...)``  — analytical upper & lower envelopes for the (P(G, ESL), UI) plot

Both render helpers are designed to give identical formatting whether called from the ESL or
the Classic page; the caller passes ``method_label`` ("ESL" or "Classic") and
the precomputed trajectory data. The ESL page may also supply ``envelope_data``
to replace the default Rose/Classic envelope with ESL-specific bounds.
"""

from __future__ import annotations

import numpy as np
import streamlit as st

from logic.pos_policy import policy_pos as _policy_pos_canonical


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Stance-trajectory plot (P(G, METHOD) vs UI)
# ─────────────────────────────────────────────────────────────────────────────

# Pre-computed envelope arrays for the **Classic Rose** product P(G) = ∏ pillar Pg.
# Upper:  UI = 2·x^(1/4) − 1   (all 4 pillars equal, Pg = x^(1/4))
# Lower:  UI = 2·√x − 1        (2 pillars at √x, 2 pillars at 1)
# These are exact for the Classic POS plot. For the ESL plot, callers pass a
# different envelope_data to render_pg_ui_trajectory (see compute_esl_envelope_*).
_BU_P = np.array([9.9999e-05, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30,
                  0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80,
                  0.85, 0.90, 0.95, 1.0])
_BU_U = np.array([-0.80, -0.248, -0.054, 0.064, 0.125, 0.245, 0.337, 0.414,
                   0.48,  0.538,  0.591,  0.638,  0.682,  0.722,  0.76,  0.796,
                   0.829, 0.861,  0.891,  0.92,   0.948,  0.975,  1.0])
_BL_P = np.array([1.0, 0.809, 0.639, 0.489, 0.359, 0.25, 0.16, 0.09, 0.04, 0.01, 1e-6])
_BL_U = np.array([1.0, 0.799, 0.599, 0.399, 0.199, -0.001, -0.201, -0.401, -0.601, -0.801, -0.998])


# ─────────────────────────────────────────────────────────────────────────────
# ESL envelope helpers — analytical upper bound and per-stance lower envelopes
# ─────────────────────────────────────────────────────────────────────────────

def _lower_envelope_curve(n_pillars: int, w: float) -> "tuple[np.ndarray, np.ndarray]":
    """Return (x, UI) arrays for the lower envelope at one stance w.

    Configuration: two weakest pillars carry all the uncertainty; the
    remaining N − 2 pillars are committed-positive (1, 0, 0). The piecewise
    formula:

        x ∈ [0, w]:  UI = 2·√(w·x) − 1
        x ∈ [w, 1]:  UI = (2w − 1) + 2·√((x − w)·(1 − w))

    At w = 0 or w = 1 the two segments collapse to the Classic Rose lower
    bound  UI = 2·√x − 1.  For w ∈ (0, 1) the curve sits strictly below the
    Classic bound, with its lowest point at (x = w, UI = 2w − 1) on the
    diagonal UI = 2x − 1.
    """
    if w > 0.0:
        x1  = np.linspace(0.0, w, 100)
        ui1 = 2.0 * np.sqrt(w * x1) - 1.0
    else:
        x1, ui1 = np.array([]), np.array([])
    if w < 1.0:
        x2  = np.linspace(w, 1.0, 100)
        ui2 = (2.0 * w - 1.0) + 2.0 * np.sqrt(np.maximum(0.0, (x2 - w) * (1.0 - w)))
    else:
        x2, ui2 = np.array([]), np.array([])
    return np.concatenate([x1, x2]), np.concatenate([ui1, ui2])


# Standard stance values to plot the lower envelope at. Both endpoints are
# kept even though w = 0 and w = 1 give the identical Classic Rose curve —
# the visual coincidence is itself informative.
_LOWER_W_VALUES: tuple[float, ...] = (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)

# Grey-tone palette, symmetric around w = 0.5 (deepest dip).
# Symmetric pairs share a colour because w and 1−w produce different curves
# but live at the same "distance" from the Classic endpoints. w = 0 and w = 1
# are mathematically identical (both collapse to Classic Rose lower).
_LOWER_COLOURS: dict[float, str] = {
    0.00: "#4b5563",   # medium-dark grey — Classic lower
    0.10: "#9ca3af",   # light grey
    0.25: "#6b7280",   # medium grey
    0.50: "#111827",   # near-black — deepest envelope
    0.75: "#6b7280",   # medium grey (symmetric with w=0.25)
    0.90: "#9ca3af",   # light grey (symmetric with w=0.10)
    1.00: "#4b5563",   # medium-dark grey — Classic lower (same curve as w=0)
}

# Dash styles paired symmetrically too. Each unique pattern identifies the
# (w, 1−w) family member without relying on colour to distinguish curves.
_LOWER_DASH: dict[float, str] = {
    0.00: "dash",
    0.10: "dot",
    0.25: "longdash",
    0.50: "longdashdot",
    0.75: "longdash",
    0.90: "dot",
    1.00: "dash",
}


def compute_esl_envelope_analytical(n_pillars: int, w: float = 0.5) -> list[dict]:
    """Analytical envelopes for the (P(G, ESL), UI) plot — exact, no Monte Carlo.

    Returns one upper envelope plus a family of lower envelopes at seven
    standard stance values w ∈ {0, 0.10, 0.25, 0.50, 0.75, 0.90, 1}.

    **Upper envelope — all pillars equal, no white:**
        N pillars at (S_for=a, S_against=1−a, White=0):
            Policy P = a, UI = 2a − 1, P(G,ESL) = aᴺ
            ⇒  UI = 2·x^(1/N) − 1   (w-independent)

    **Lower envelope family — two weakest pillars, rest committed-positive:**
        For each reference w, the piecewise curve
            x ∈ [0, w]:  UI = 2·√(w·x) − 1
            x ∈ [w, 1]:  UI = (2w − 1) + 2·√((x − w)·(1 − w))
        bounds UI from below. The deepest point of each curve sits on the
        diagonal UI = 2x − 1 at x = w.

    The ``w`` argument is no longer used to pick a single lower envelope —
    it's retained for backward compatibility with callers but ignored.
    """
    # ── Upper envelope (N-dependent, w-independent) ──
    x_upper  = np.linspace(1e-6, 1.0, 200)
    ui_upper = 2.0 * x_upper**(1.0 / n_pillars) - 1.0

    curves: list[dict] = [
        {"x": x_upper * 100, "y": ui_upper * 100,
         "name": f"Upper envelope — all {n_pillars} pillars equal, no white",
         "color": "#374151", "dash": "dash", "width": 2.0},
    ]

    # ── Lower envelope family (seven reference w values) ──
    for w_ref in _LOWER_W_VALUES:
        x_l, ui_l = _lower_envelope_curve(n_pillars, w_ref)
        is_classic = (w_ref == 0.0) or (w_ref == 1.0)
        name = (f"Lower at w = {w_ref:.2f}  (Classic Rose lower)"
                if is_classic
                else f"Lower at w = {w_ref:.2f}")
        curves.append({
            "x": x_l * 100, "y": ui_l * 100,
            "name": name,
            "color": _LOWER_COLOURS[w_ref],
            "dash": _LOWER_DASH[w_ref],
            "width": 1.8 if w_ref == 0.5 else 1.3,
        })

    return curves


def _verdict(bel_y_pct: float, cur_y_pct: float, pl_y_pct: float) -> str:
    """Trajectory-aware status string for the UI banner."""
    if bel_y_pct > 0:
        return "ROBUST — even at most pessimistic stance, two weakest pillars stay viable."
    if pl_y_pct < 0:
        return "RISK-DRIVEN — even at most optimistic stance, compounding risk in two weakest pillars."
    if cur_y_pct >= 0:
        return ("BALANCED at current stance — but the diagnosis flips to risk-driven at the "
                "pessimistic end of the ESL range. Data quality matters.")
    return ("ATTENTION at current stance — but the diagnosis flips to robust at the optimistic "
            "end of the ESL range. Data quality matters.")


def render_pg_ui_trajectory(
    traj_x: list[float],   # P(G, METHOD) % at each w in the sweep
    traj_y: list[float],   # UI % at each w in the sweep
    ws: list[float],       # w values (same length as traj_x / traj_y)
    current_w: float,
    current_x: float,      # P(G, METHOD) % at current_w
    current_y: float,      # UI % at current_w
    method_label: str,     # "ESL" or "Classic"
    extra_caption: str = "",
    envelope_data: "dict | None" = None,
    dfi_overlay: "dict | None" = None,
) -> None:
    """Render the shared stance-trajectory plot for P(G, METHOD) vs UI.

    Renders, in order:
      - Status banner (UI value, defensible range, ROBUST/RISK-DRIVEN/BALANCED/ATTENTION)
      - Plot (red-white-green background, envelope, blue trajectory,
        w-tick markers, UI=0 reference line, red ★ at current stance)
      - Caption explaining the elements
      - Numeric readout table (Bel / Current / Pl)

    ``extra_caption`` is appended to the standard caption — use it for
    method-specific notes (e.g. the operator-choice caveat for Classic).

    ``envelope_data`` overrides the default Classic Rose envelope. When None,
    the dashed Rose curves are drawn (mathematically exact for P(G, Classic)).
    To pass a custom envelope (e.g. the ESL Monte-Carlo region + analytical
    curves), supply::

        {
          "fill":   {"x": [..], "y_upper": [..], "y_lower": [..],
                     "name": "...", "color": "rgba(...)"},   # optional shaded region
          "curves": [{"x": [..], "y": [..], "name": "...",
                      "color": "...", "dash": "dash", "width": 1.5}, ...],  # optional lines
        }

    Either or both keys may be omitted. When envelope_data is provided the
    default Rose dashed curves are suppressed.
    """
    import plotly.graph_objects as go

    bel_y_pct = traj_y[0]
    pl_y_pct  = traj_y[-1]
    bel_x_pct = traj_x[0]
    pl_x_pct  = traj_x[-1]

    # ── Status banner ──────────────────────────────────────────────────────
    ui_color = "#16a34a" if current_y >= 0 else "#dc2626"
    ui_bg    = "#dcfce7" if current_y >= 0 else "#fee2e2"
    status_text = _verdict(bel_y_pct, current_y, pl_y_pct)
    st.markdown(
        f"<div style='background:{ui_bg};border-left:5px solid {ui_color};"
        f"padding:12px 16px;border-radius:6px;margin-bottom:12px;'>"
        f"<b style='color:{ui_color};font-size:1.1rem;'>"
        f"Uncertainty Index ({method_label}): {current_y:+.1f}% &nbsp;"
        f"<small style='color:#6b7280;font-weight:400;'>"
        f"[defensible range: {bel_y_pct:+.1f}% — {pl_y_pct:+.1f}%]</small></b><br>"
        f"<span style='color:#374151;'>{status_text}</span></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"**UI = MIN(P(pillar)) + 2nd-MIN(P(pillar)) − 1.** "
        f"The trajectory curve shows how UI and P(G, {method_label}) co-vary as the "
        f"stance w sweeps from 0 (pessimistic) to 1 (optimistic). The current point is "
        f"the ★; the bracket-marked endpoints are the defensible bounds."
    )

    # ── Build figure ───────────────────────────────────────────────────────
    _xv = np.linspace(0.0001, 1, 60)
    bound_upper_x = _xv * 100
    bound_upper_y = np.interp(_xv, _BU_P, _BU_U) * 100
    bound_lower_x = np.linspace(1, 0.0001, 60) * 100
    bound_lower_y = np.interp(np.linspace(1, 0.0001, 60), _BL_P[::-1], _BL_U[::-1]) * 100

    fig = go.Figure()
    # Red→white→green background
    for i in range(60):
        y0 = -100 + i * (200 / 60)
        y1 = -100 + (i + 1) * (200 / 60)
        t = ((y0 + y1) / 2 + 100) / 200
        if t < 0.5:
            r = int(220 + (255 - 220) * t * 2)
            g = int(38 + (255 - 38) * t * 2)
            b = int(38 + (255 - 38) * t * 2)
        else:
            r = int(255 - (255 - 22) * (t - 0.5) * 2)
            g = int(255 - (255 - 163) * (t - 0.5) * 2)
            b = int(255 - (255 - 74) * (t - 0.5) * 2)
        fig.add_hrect(y0=y0, y1=y1,
                      fillcolor=f"rgba({r},{g},{b},0.35)",
                      line_width=0, layer="below")

    if envelope_data is None:
        # Default: Classic Rose envelope (exact for P(G, Classic))
        fig.add_trace(go.Scatter(
            x=bound_upper_x, y=bound_upper_y, mode="lines",
            line=dict(dash="dash", color="#6b7280", width=1.5),
            name="Rose envelope (∏ pillar Pg)",
        ))
        fig.add_trace(go.Scatter(
            x=bound_lower_x, y=bound_lower_y, mode="lines",
            line=dict(dash="dash", color="#6b7280", width=1.5),
            showlegend=False,
        ))
    else:
        # Custom envelope (used by the ESL plot)
        _fill = envelope_data.get("fill")
        if _fill is not None:
            # Two traces: upper edge (invisible line) then lower edge with fill='tonexty'
            fig.add_trace(go.Scatter(
                x=_fill["x"], y=_fill["y_upper"], mode="lines",
                line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=_fill["x"], y=_fill["y_lower"], mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor=_fill.get("color", "rgba(96,165,250,0.15)"),
                name=_fill.get("name", "Achievable region"),
                hoverinfo="skip",
            ))
        for _curve in envelope_data.get("curves", []):
            fig.add_trace(go.Scatter(
                x=_curve["x"], y=_curve["y"], mode="lines",
                line=dict(
                    dash=_curve.get("dash", "dash"),
                    color=_curve.get("color", "#6b7280"),
                    width=_curve.get("width", 1.5),
                ),
                name=_curve.get("name", "envelope curve"),
                hoverinfo="skip",
            ))

    # Stance trajectory (main blue line)
    fig.add_trace(go.Scatter(
        x=traj_x, y=traj_y, mode="lines",
        line=dict(color="#1e40af", width=3),
        name="Stance trajectory (w: 0 → 1)",
        hovertemplate=(
            f"P(G, {method_label}): %{{x:.1f}}%<br>UI: %{{y:+.1f}}%<extra>trajectory</extra>"
        ),
    ))

    # Tick markers at requested w values — hide any within 0.05 of current_w
    tick_ws_all = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
    tick_ws = [tw for tw in tick_ws_all if abs(tw - current_w) >= 0.05]
    tick_idx = [int(np.argmin(np.abs(np.array(ws) - tw))) for tw in tick_ws]
    tick_x = [traj_x[i] for i in tick_idx]
    tick_y = [traj_y[i] for i in tick_idx]
    tick_lbl = [f"w={tw:.2f}" for tw in tick_ws]
    tick_hov = [f"{traj_y[i]:+.1f}%" for i in tick_idx]
    fig.add_trace(go.Scatter(
        x=tick_x, y=tick_y, mode="markers+text",
        marker=dict(symbol="circle", size=10, color="#1e40af",
                    line=dict(color="white", width=1.5)),
        text=tick_lbl, textposition="bottom right",
        textfont=dict(size=10, color="#1e3a8a"),
        name="Stance ticks", showlegend=False,
        customdata=tick_hov,
        hovertemplate="%{customdata}<extra></extra>",
    ))

    # UI = 0 reference line
    fig.add_hline(
        y=0, line_width=1.5, line_dash="dot", line_color="#1f2937",
        annotation_text="UI = 0  (balanced)", annotation_position="right",
        annotation_font=dict(size=10, color="#1f2937"),
    )

    # Current prospect star
    fig.add_trace(go.Scatter(
        x=[current_x], y=[current_y], mode="markers+text",
        marker=dict(symbol="star", size=22, color="#dc2626",
                    line=dict(color="white", width=2)),
        text=[f"Current  (w={current_w:.2f})"], textposition="top center",
        textfont=dict(size=11, color="#7f1d1d"),
        name="Current (prior)",
        hovertemplate=(
            f"<b>Current stance — prior</b><br>w = {current_w:.2f}<br>"
            f"P(G, {method_label}): %{{x:.1f}}%<br>UI: %{{y:+.1f}}%<extra></extra>"
        ),
    ))

    # ── Optional DFI posterior overlay ─────────────────────────────────────
    if dfi_overlay is not None:
        _dfi_traj_x = dfi_overlay.get("traj_x")
        _dfi_cur_x  = dfi_overlay.get("current_x")
        if _dfi_traj_x is not None and len(_dfi_traj_x) == len(traj_y):
            fig.add_trace(go.Scatter(
                x=_dfi_traj_x, y=traj_y, mode="lines",
                line=dict(color="#f59e0b", width=2.5, dash="dash"),
                name=f"P(G | DFI, {method_label})  — posterior",
                hovertemplate=(
                    f"P(G | DFI, {method_label}): %{{x:.1f}}%<br>UI: %{{y:+.1f}}%"
                    f"<extra>posterior</extra>"
                ),
            ))
        if _dfi_cur_x is not None:
            # Arrow from prior star to posterior diamond
            fig.add_annotation(
                x=_dfi_cur_x, y=current_y, ax=current_x, ay=current_y,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=3, arrowsize=1.2, arrowwidth=2,
                arrowcolor="#b45309",
            )
            fig.add_trace(go.Scatter(
                x=[_dfi_cur_x], y=[current_y], mode="markers+text",
                marker=dict(symbol="diamond", size=18, color="#f59e0b",
                            line=dict(color="white", width=2)),
                text=[f"DFI  (w={current_w:.2f})"], textposition="bottom center",
                textfont=dict(size=11, color="#92400e"),
                name="Current (posterior)",
                hovertemplate=(
                    f"<b>Current stance — DFI posterior</b><br>w = {current_w:.2f}<br>"
                    f"P(G | DFI, {method_label}): %{{x:.1f}}%<br>UI: %{{y:+.1f}}%<extra></extra>"
                ),
            ))

    fig.update_layout(
        title=f"Stance trajectory — P(G, {method_label}) vs Uncertainty Index",
        xaxis_title=f"P(G, {method_label}) (%)",
        yaxis_title="Uncertainty Index (%)",
        xaxis=dict(range=[0, 100], dtick=10),
        yaxis=dict(range=[-100, 100], dtick=20),
        height=760, margin=dict(t=40, b=190, l=50, r=20),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.20,
            xanchor="center", x=0.5,
            font=dict(size=10),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Headline caption (always visible, one line)
    st.caption(
        f"★ = current stance · blue curve = trajectory as w sweeps 0→1 · "
        f"dashed = theoretical envelope · background red→green by UI sign."
    )

    # Compact inline pill readout of the three key points
    st.markdown(
        f"<div style='font-size:0.86rem;color:#374151;margin-top:4px;'>"
        f"<span style='background:#fee2e2;padding:2px 8px;border-radius:10px;'>"
        f"<b>Bel</b> (w=0): P={bel_x_pct:.1f}% · UI={bel_y_pct:+.1f}%</span> &nbsp; "
        f"<span style='background:#fff7ed;padding:2px 8px;border-radius:10px;'>"
        f"<b>Current</b> (w={current_w:.2f}): P={current_x:.1f}% · UI={current_y:+.1f}%</span> &nbsp; "
        f"<span style='background:#dcfce7;padding:2px 8px;border-radius:10px;'>"
        f"<b>Pl</b> (w=1): P={pl_x_pct:.1f}% · UI={pl_y_pct:+.1f}%</span></div>",
        unsafe_allow_html=True,
    )

    # Full reading guide hidden behind expander
    with st.expander("Reading this plot", expanded=False):
        st.markdown(
            "**Blue curve:** stance trajectory — sweeps w from 0 to 1 in 21 steps, each point is "
            f"`(P(G, {method_label}), UI)` at that stance. "
            "★ = current prospect at your stance setting.  \n"
            "**Grey dashed lines:** theoretical envelope.  \n"
            "**Background:** red (UI = −100%) → white (UI = 0) → green (UI = +100%).  \n"
            "**Diagnosis flip:** if the trajectory crosses the `UI = 0` horizontal, the "
            "diagnosis (robust vs risk-driven) depends on the stance choice."
        )
        if extra_caption:
            st.markdown(extra_caption)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Top 5 weakest risk elements (with mini Italian Flag)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Shared sensitivity tornado — used by ESL Analysis and Classic POS detail
# ─────────────────────────────────────────────────────────────────────────────

def render_sensitivity_tornado(
    *,
    method_label: str,
    play: dict,
    conditional: dict,
    uncertainty_weight: float,
    compute_total: "callable",
    pillar_display: "dict[str, str] | None" = None,
    include_cond_aggregate_in_pillars: bool = True,
) -> None:
    """Shared scenario-analysis tornado for both ESL and Classic POS.

    Same logic for both methods (single source of truth):
      - For each element, the white (unknown) mass is reallocated to "all
        against" (low case) and "all for" (high case).
      - Total prospect POS is recomputed via ``compute_total`` — the method-
        specific callback.
      - Range from low to high is plotted as a horizontal bar.

    ``compute_total`` signature::

        compute_total(override, w) -> float

        override is None (no override), or a tuple:
          ("play",     pid, sf, sa)      override play element of pillar pid
          ("cond_agg", pid, sf, sa)      replace pillar pid's cond aggregate
          ("cond_sub", pid, idx, sf, sa) override one sub-element

        w is the stance.  Returns the total POS in [0, 1].

    Each caller provides a ``compute_total`` that knows the method's
    aggregation rules (ESL uses mass-product + policy_pos at the end;
    Classic uses policy_pos per sub-element then classic_pos_product).
    """
    import plotly.graph_objects as go
    from components.colors import bar_color_for_label

    # ── Mode toggles ───────────────────────────────────────────────────────
    uw_pct = uncertainty_weight * 100
    uw_label = (
        "Conservative" if uncertainty_weight < 0.25
        else "Optimistic" if uncertainty_weight > 0.75
        else "Balanced"
    )
    _tag = method_label.lower().replace(" ", "_").replace(",", "").replace("(", "").replace(")", "")
    st.caption(
        f"Stance: **w = {uncertainty_weight:.2f}** ({uw_label}, {uw_pct:.0f}% of white counted as success).",
        help=("Stance (w) controls how much of the unknown (White) evidence counts as success. "
              "0 = pessimistic, 0.5 = balanced (default), 1 = optimistic. "
              "Adjust w on the Dashboard."),
    )
    level = st.radio(
        "Level",
        ["Pillars (default)", "Sub-elements"],
        horizontal=True,
        key=f"tornado_level_{_tag}",
        help=("Pillars: per-pillar Play + Cond. "
              "Sub-elements: individual conditional leaf elements. "
              "Method: for each element, white is reallocated to all-against (low) "
              "and all-for (high), and the total is recomputed."),
    )
    use_sub = level == "Sub-elements"
    sub_mode = None
    if use_sub:
        sub_mode = st.radio(
            "Sub-element mode",
            ["Potential impact (element-only)", "Actual impact (one-at-a-time)"],
            horizontal=True,
            key=f"tornado_sub_mode_{_tag}",
            help=("Potential: range as if this sub-element were the entire "
                  "pillar's conditional aggregate. "
                  "Actual: vary this sub-element with all others fixed; "
                  "the pillar's aggregation is recomputed."),
        )

    # ── Display names ──────────────────────────────────────────────────────
    if pillar_display is None:
        from logic.pos_policy import get_active_pillars
        pillar_display = {p["pillar_id"]: p["display_name"] for p in get_active_pillars()}

    # ── Base values ────────────────────────────────────────────────────────
    base_pos  = compute_total(None, uncertainty_weight)
    base_cons = compute_total(None, 0.0)
    base_opti = compute_total(None, 1.0)

    # ── Build swings list ──────────────────────────────────────────────────
    swings: list[tuple[str, float, float, float]] = []  # (label, low, high, |range|)

    if use_sub:
        use_potential = sub_mode == "Potential impact (element-only)"
        for pid, elements in conditional.items():
            disp = pillar_display.get(pid, pid)
            for idx, elem in enumerate(elements):
                lbl = elem.get("label") or "?"
                sc  = elem.get("success_criteria") or ""
                label = (f"{lbl} — {sc} ({disp})"
                         if sc and lbl != sc else f"{lbl} ({disp})")
                sf = float(elem.get("support_for", 0.5))
                sa = float(elem.get("support_against", 0.1))
                u  = max(0.0, 1.0 - sf - sa)
                low_sf,  low_sa  = sf, min(1.0, sa + u)
                high_sf, high_sa = min(1.0, sf + u), sa
                if use_potential:
                    low_pos  = compute_total(("cond_agg", pid, low_sf,  low_sa),  uncertainty_weight)
                    high_pos = compute_total(("cond_agg", pid, high_sf, high_sa), uncertainty_weight)
                else:
                    low_pos  = compute_total(("cond_sub", pid, idx, low_sf,  low_sa),  uncertainty_weight)
                    high_pos = compute_total(("cond_sub", pid, idx, high_sf, high_sa), uncertainty_weight)
                swings.append((label, low_pos, high_pos, abs(high_pos - low_pos)))
    else:
        # Pillars mode — vary the play element of each pillar (and optionally the cond aggregate)
        for pid, pdata in play.items():
            if not (isinstance(pdata, dict) and "support_for" in pdata):
                continue
            disp = pillar_display.get(pid, pid)
            sf = float(pdata["support_for"])
            sa = float(pdata["support_against"])
            u  = max(0.0, 1.0 - sf - sa)
            low_pos  = compute_total(("play", pid, sf, min(1.0, sa + u)),  uncertainty_weight)
            high_pos = compute_total(("play", pid, min(1.0, sf + u), sa), uncertainty_weight)
            swings.append((f"{disp} (Play)", low_pos, high_pos, abs(high_pos - low_pos)))

            if include_cond_aggregate_in_pillars and conditional.get(pid):
                # Vary the pillar's conditional aggregate by reallocating its white.
                # The callback evaluates the current aggregate internally for the
                # base case; for low/high we pass the extremes of the aggregate.
                # We probe the current aggregate by asking compute_total to give us
                # the "aggregate-equivalent" override that matches the baseline.
                # Practical approach: pass the SUB-ELEMENT extremes ("all sub-elements
                # at white-against" and "all at white-for") via successive cond_sub
                # overrides — but a simpler proxy is to vary an aggregate (sf, sa)
                # equal to the average of sub-element extremes.
                _sf_sum_lo, _sa_sum_lo = 0.0, 0.0
                _sf_sum_hi, _sa_sum_hi = 0.0, 0.0
                _n = 0
                for _e in conditional[pid]:
                    _f = float(_e.get("support_for", 0.5))
                    _a = float(_e.get("support_against", 0.1))
                    _u = max(0.0, 1.0 - _f - _a)
                    _sf_sum_lo += _f;          _sa_sum_lo += min(1.0, _a + _u)
                    _sf_sum_hi += min(1.0, _f + _u); _sa_sum_hi += _a
                    _n += 1
                if _n > 0:
                    avg_lo_sf, avg_lo_sa = _sf_sum_lo / _n, _sa_sum_lo / _n
                    avg_hi_sf, avg_hi_sa = _sf_sum_hi / _n, _sa_sum_hi / _n
                    low_pos_c  = compute_total(("cond_agg", pid, avg_lo_sf, avg_lo_sa), uncertainty_weight)
                    high_pos_c = compute_total(("cond_agg", pid, avg_hi_sf, avg_hi_sa), uncertainty_weight)
                    swings.append((f"{disp} (Cond)", low_pos_c, high_pos_c, abs(high_pos_c - low_pos_c)))

    if not swings:
        st.info("No elements to display — assessment may be empty.")
        return

    # ── Sort by absolute range (largest first), keep top 20 ───────────────
    swings.sort(key=lambda x: x[3], reverse=True)
    swings = swings[:20]
    # Reverse for horizontal bar (largest at top)
    swings_rev = list(reversed(swings))
    labels = [s[0] for s in swings_rev]
    lows   = [s[1] * 100 for s in swings_rev]
    highs  = [s[2] * 100 for s in swings_rev]
    widths = [h - l for l, h in zip(lows, highs)]
    bar_colors = [bar_color_for_label(lbl) for lbl in labels]

    # Method explanation moved to expander to reduce clutter

    # ── Plot ───────────────────────────────────────────────────────────────
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=widths, base=lows, orientation="h",
        marker_color=bar_colors,
        name=f"Range (low → high)",
        hovertemplate="<b>%{y}</b><br>Range: %{base:.1f}% → %{x:.1f}% (then add base)<extra></extra>",
    ))
    fig.add_vline(
        x=base_pos * 100, line_dash="dash", line_color="#1f2937", line_width=2,
        annotation_text=f"Current P(G, {method_label}) ({base_pos*100:.1f}%)",
        annotation_position="top",
    )
    fig.add_vline(
        x=base_cons * 100, line_dash="dot", line_color="#2563eb", line_width=1.5,
        annotation_text=f"Conservative w=0 ({base_cons*100:.1f}%)",
        annotation_position="bottom right",
    )
    fig.add_vline(
        x=base_opti * 100, line_dash="dot", line_color="#16a34a", line_width=1.5,
        annotation_text=f"Optimistic w=1 ({base_opti*100:.1f}%)",
        annotation_position="top right",
    )
    # ── Dynamic x-axis tick spacing — target ~15 ticks (≈ 2× plotly default) ──
    _all_x = lows + highs + [base_pos * 100, base_cons * 100, base_opti * 100]
    _x_min, _x_max = min(_all_x), max(_all_x)
    _x_pad = max(1.0, (_x_max - _x_min) * 0.05)
    _x_lo = max(0.0,   _x_min - _x_pad)
    _x_hi = min(100.0, _x_max + _x_pad)

    def _nice_dtick(span: float, target: int = 15) -> float:
        """Round dtick to a 'nice' number (1, 2, 2.5, 5 × 10^k) targeting ~`target` ticks."""
        import math
        if span <= 0:
            return 1.0
        raw = span / max(1, target - 1)
        mag = 10.0 ** math.floor(math.log10(raw))
        norm = raw / mag
        if norm < 1.5:  nice = 1.0
        elif norm < 3:  nice = 2.0
        elif norm < 4:  nice = 2.5
        elif norm < 7:  nice = 5.0
        else:           nice = 10.0
        return nice * mag

    _dtick = _nice_dtick(_x_hi - _x_lo, target=15)

    fig.update_layout(
        title=f"Sensitivity tornado — P(G, {method_label}) range per element",
        xaxis=dict(
            title=f"P(G, {method_label}) (%)",
            range=[_x_lo, _x_hi],
            dtick=_dtick,
            showgrid=True,
            gridcolor="#e5e7eb",
            zeroline=False,
        ),
        height=max(400, min(len(labels) * 32, 1100)),
        margin=dict(l=120, r=20, t=60, b=40),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Compact toggle for the method explanation. We use a checkbox rather than
    # st.expander because callers may already be inside an expander (Streamlit
    # forbids nesting expanders).
    if st.checkbox("📖 Show how the tornado is computed",
                   value=False, key=f"tornado_explain_{_tag}"):
        st.markdown(
            f"**Scenario analysis (white reallocation):** For each element, the "
            f"uncommitted (white) mass is reallocated to **all against** (low case → minimum "
            f"Policy P) and **all for** (high case → maximum Policy P). Only that element "
            f"changes; all other elements keep their current values. The total "
            f"P(G, {method_label}) is then recomputed using the {method_label} aggregation rule.  \n"
            f"The bar shows the resulting range from low to high. Vertical reference lines: "
            f"**dashed** = current total at your stance, **dotted blue** = conservative (w=0), "
            f"**dotted green** = optimistic (w=1)."
        )


def render_top5_weakest(
    conditional: dict,
    uw: float,
    pillar_display: "dict[str, str] | None" = None,
) -> None:
    """Render Top 5 lowest Policy P risk elements with mini Italian-Flag bars.

    Format matches the ESL Analysis tab inline implementation (mini flags + rank).
    """
    from components.render_helpers import small_flag_html

    display_map = pillar_display or {}
    leaves: list = []
    for cat, elements in conditional.items():
        disp = display_map.get(cat, cat)
        for elem in elements:
            sf = float(elem.get("support_for", 0.5))
            sa = float(elem.get("support_against", 0.1))
            pv = _policy_pos_canonical(sf, sa, uw)
            lbl = elem.get("label", "?")
            sc  = elem.get("success_criteria", "")
            name = f"{disp} / {lbl}" + (f": {sc[:50]}" if sc else "")
            leaves.append((name, pv, sf, sa))
    leaves.sort(key=lambda x: x[1])

    st.markdown("**Top 5 Weakest Risk Elements** (lowest Policy P):")
    for rank, (name, pv, sf, sa) in enumerate(leaves[:5], 1):
        flag_html = small_flag_html(sf, sa)
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:6px;'>"
            f"<span style='font-weight:700;min-width:20px;'>#{rank}</span>"
            f"<span style='min-width:80px;font-size:0.9rem;color:#374151;'>{pv*100:.0f}% Policy P</span>"
            f"{flag_html}"
            f"<span style='font-size:0.85rem;color:#374151;'>{name}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.caption("Candidate show-stoppers. Review evidence notes before finalising the assessment.")


# ─────────────────────────────────────────────────────────────────────────────
# Session-state key helpers (kept for compatibility with elsewhere)
# ─────────────────────────────────────────────────────────────────────────────

def _canonical_play_key(cat: str) -> str:
    """Unified key for play pillar (Charge, Closure, Reservoir, Retention)."""
    return f"play_{cat}"


def _canonical_cond_key(cat: str, flat_idx: int) -> str:
    """Unified key for conditional element."""
    return f"cond_{cat}_{flat_idx}"
