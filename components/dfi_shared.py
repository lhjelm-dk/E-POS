"""Shared UI components for the three DFI evidence sources.

The DFI Update tab hosts three evidence sources that arrive at the same endpoint
— a likelihood ratio **R** that updates the geological prior via Simm's two-state
Bayes:

  • DHI Index (SAAM)            — calibrated 8-outcome model
  • Characteristic (Monigle 2025) — uncalibrated naive-independence product
  • Custom R tool               — uncalibrated user-defined Gaussians

This module holds the **method-agnostic** render blocks so all three present R,
its Simm verdict, the prior→posterior move, and the stance trajectory the same
way. Method-specific views (per-pillar attribution, radar, iso-DHI, the custom
R(strength) curve) stay in their own renderers.

All functions take plain scalars (R, prior, posterior …) so they are decoupled
from any one pathway's data classes. Heavy imports (plotly/pandas) are local to
each function, matching the rest of the components layer.
"""
from __future__ import annotations

import streamlit as st

from logic.dfi_simm import simm_rule_of_thumb, SIMM_R_BANDS


# Simm rule-of-thumb shaded bands for an R log-axis: (hi, lo, fill, label).
# Single source of truth — the scalar band-strip and the custom R(strength)
# curve both shade against these.
SIMM_BAND_EDGES: tuple[tuple[float, float, str, str], ...] = (
    (50.0,  10.0,  "rgba(21,128,61,0.10)",  "decisive ↑"),
    (10.0,   3.0,  "rgba(22,163,74,0.10)",  "strong ↑"),
    ( 3.0,   1.5,  "rgba(101,163,13,0.10)", "moderate ↑"),
    ( 1.5, 1/1.5,  "rgba(107,114,128,0.08)", "≈ no change"),
    (1/1.5,  1/3,  "rgba(217,119,6,0.10)",  "moderate ↓"),
    (1/3,   1/10,  "rgba(220,38,38,0.10)",  "strong ↓"),
    (1/10,  0.02,  "rgba(153,27,27,0.10)",  "decisive ↓"),
)

# R-axis tick positions shared by every Simm band plot.
SIMM_R_TICKS: tuple[float, ...] = (0.02, 0.1, 1/3, 1/1.5, 1.0, 1.5, 3.0, 10.0, 50.0)


# ─────────────────────────────────────────────────────────────────────────────
# R + score metric tiles
# ─────────────────────────────────────────────────────────────────────────────

def render_rscore_metrics(
    r: float,
    score_pct: float,
    *,
    r_label: str = "R",
    r_help: str = "Likelihood ratio feeding Simm 2-state Bayes.",
    score_help: str = "R / (R + 1) — Monigle-style 0–100 score.",
    columns=None,
) -> None:
    """Two standard tiles — ``R`` and the 0–100 ``DHI score`` — shown identically
    on every pathway. ``columns`` may be a pair of pre-made ``st.columns`` to drop
    the tiles into an existing row; otherwise a fresh 2-column row is created."""
    c1, c2 = columns if columns is not None else st.columns(2)
    c1.metric(r_label, f"{r:.2f}", help=r_help)
    c2.metric("DHI score", f"{score_pct:.0f}%", help=score_help)


# ─────────────────────────────────────────────────────────────────────────────
# Simm rule-of-thumb verdict banner
# ─────────────────────────────────────────────────────────────────────────────

def render_simm_verdict_banner(r: float) -> tuple[str, str, str]:
    """Coloured verdict banner for a likelihood ratio ``R``.

    Renders the Simm rule-of-thumb label, direction, and comment as a left-bordered
    callout. Returns ``(label, comment, color)`` so the caller can reuse the label
    in nearby captions/legends.
    """
    label, comment, color = simm_rule_of_thumb(r)
    direction = "↑ uplift" if r > 1.0 else ("↓ downgrade" if r < 1.0 else "→ no change")
    st.markdown(
        f"<div style='background:{color}1a;border-left:5px solid {color};"
        f"border-radius:6px;padding:8px 12px;margin:6px 0;'>"
        f"<b style='color:{color};'>Simm rule of thumb — {label}</b> "
        f"&nbsp;(R = {r:.2f}, {direction}) &nbsp; "
        f"<span style='color:#374151;'>{comment}</span></div>",
        unsafe_allow_html=True,
    )
    return label, comment, color


# ─────────────────────────────────────────────────────────────────────────────
# Scalar Simm band strip — where does a single R land among the bands?
# ─────────────────────────────────────────────────────────────────────────────

def render_simm_band_strip(r: float, *, height: int = 120, key: str | None = None) -> None:
    """Compact horizontal strip showing a single ``R`` against the Simm bands.

    Method-agnostic: any pathway with one scalar R (characteristic, custom, or
    DHI-Index R_SAAM) can show where it sits. The R axis is log-scaled and the
    seven shaded bands match :data:`SIMM_BAND_EDGES`; band names sit horizontally
    above the strip and a star marks the current R (the value/verdict are in the
    banner above and the caption below, so the marker carries no text).
    """
    import numpy as np
    import plotly.graph_objects as go

    label, _comment, color = simm_rule_of_thumb(r)
    r_clamped = float(min(max(r, 0.02), 50.0))

    fig = go.Figure()
    # Shade bands as vertical rectangles across the (single) row.
    for hi, lo, fill, _lbl in SIMM_BAND_EDGES:
        fig.add_vrect(x0=lo, x1=hi, fillcolor=fill, line_width=0, layer="below")
    for thr in SIMM_R_BANDS:
        fig.add_vline(x=thr, line_dash="dot", line_color="#cbd5e1", line_width=1)
    fig.add_vline(x=1.0, line_dash="dot", line_color="#6b7280")
    # Band names — horizontal, above the strip, centred on each band's geometric
    # mean (log axis → pass log10 of the centre for the x position).
    for hi, lo, _fill, lbl in SIMM_BAND_EDGES:
        fig.add_annotation(
            x=float(0.5 * np.log10(hi * lo)), y=1.02, xref="x", yref="paper",
            yanchor="bottom", text=lbl, showarrow=False,
            font=dict(size=9, color="#64748b"),
        )
    # The R marker (no text — value & verdict live in the banner/caption).
    fig.add_trace(go.Scatter(
        x=[r_clamped], y=[0], mode="markers",
        marker=dict(symbol="star", size=20, color=color, line=dict(color="white", width=1.5)),
        showlegend=False, hovertemplate=f"R = {r:.2f} ({label})<extra></extra>",
    ))
    fig.update_xaxes(
        title_text="R = P(DFI | HC) / P(DFI | No-HC)", type="log",
        range=[np.log10(0.02), np.log10(50.0)],
        tickmode="array", tickvals=list(SIMM_R_TICKS),
        ticktext=[f"{t:.2f}" for t in SIMM_R_TICKS],
    )
    fig.update_yaxes(visible=False, range=[-0.5, 0.5])
    fig.update_layout(height=height, margin=dict(t=22, b=38, l=10, r=10),
                      showlegend=False)
    st.plotly_chart(fig, use_container_width=True, key=key)
    st.caption(
        f"Current **R = {r:.2f} → {label}**. Simm rule of thumb: |R| ≈ 1.5 moderate, "
        "≈ 3 strong (his practical ceiling for a single DFI), ≥ 10 decisive — audit the "
        "inputs. Bands are symmetric in log-odds (R and 1/R mirror)."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Prior → Posterior bar (Bel/Pl envelope) — one shared visual for all methods
# ─────────────────────────────────────────────────────────────────────────────

def render_prior_post_bar(
    prior: float,
    post: float,
    bel: float,
    pl: float,
    *,
    view_label: str = "ESL view — prior ● → posterior ◆",
) -> None:
    """Shared before→after DFI bar with the geological Bel/Pl envelope.

    ``prior``/``post``/``bel``/``pl`` are fractions in [0, 1]. Renders the bordered
    card (delta pill + gradient bar + dots + ticks + legend) used on the Final
    Prospect POS summary, so characteristic and custom summaries match the
    DHI-Index one.
    """
    prior_pct, post_pct = prior * 100, post * 100
    bel_pct, pl_pct = bel * 100, pl * 100
    delta = post - prior
    delta_color = "#16a34a" if delta >= 0 else "#dc2626"
    delta_bg    = "#dcfce7" if delta >= 0 else "#fee2e2"
    direction   = "UPLIFT" if delta >= 0.005 else ("DOWNGRADE" if delta <= -0.005 else "NO CHANGE")
    arrow       = "↑" if delta >= 0.005 else ("↓" if delta <= -0.005 else "→")

    def _pos(p_pct: float) -> str:
        return f"{max(0.0, min(100.0, p_pct)):.1f}%"

    bar_html = (
        f"<div style='position:relative;height:34px;background:linear-gradient("
        f"to right,#fee2e2 0%,#fff7ed 50%,#dcfce7 100%);"
        f"border:1px solid #d1d5db;border-radius:6px;margin:6px 0;'>"
        f"<div style='position:absolute;left:{_pos(bel_pct)};top:0;bottom:0;"
        f"width:0;border-left:1px dashed #6b7280;'></div>"
        f"<div style='position:absolute;left:{_pos(pl_pct)};top:0;bottom:0;"
        f"width:0;border-left:1px dashed #6b7280;'></div>"
        f"<div style='position:absolute;left:{_pos(prior_pct)};top:7px;"
        f"transform:translateX(-50%);width:18px;height:18px;background:#dc2626;"
        f"border-radius:50%;border:2px solid white;box-shadow:0 0 3px rgba(0,0,0,.35);'></div>"
        f"<div style='position:absolute;left:{_pos(post_pct)};top:5px;"
        f"width:22px;height:22px;background:#f59e0b;"
        f"border:3px solid white;box-shadow:0 0 4px rgba(0,0,0,.4);"
        f"transform-origin:center;transform:translateX(-50%) rotate(45deg);'></div>"
        f"<div style='position:absolute;left:{_pos(prior_pct)};top:-22px;"
        f"transform:translateX(-50%);font-size:0.72rem;color:#7f1d1d;white-space:nowrap;'>"
        f"prior {prior_pct:.1f}%</div>"
        f"<div style='position:absolute;left:{_pos(post_pct)};bottom:-22px;"
        f"transform:translateX(-50%);font-size:0.78rem;color:#92400e;font-weight:600;"
        f"white-space:nowrap;'>posterior {post_pct:.1f}%</div>"
        f"</div>"
    )

    st.markdown(
        f"<div style='background:#fff;border:2px solid {delta_color};border-radius:10px;"
        f"padding:14px 18px;margin:8px 0 16px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<b style='font-size:1.05rem;color:#111827;'>{view_label}</b>"
        f"<span style='background:{delta_bg};color:{delta_color};font-weight:700;"
        f"padding:4px 12px;border-radius:999px;font-size:0.92rem;'>"
        f"{arrow} {direction} &nbsp;Δ {delta*100:+.1f} pp</span>"
        f"</div>"
        f"<div style='margin:14px 0 2px;'>{bar_html}</div>"
        f"<div style='font-size:0.78rem;color:#6b7280;margin-top:24px;'>"
        f"Red ● = prior P(G, ESL) &nbsp;·&nbsp; Gold ◆ = posterior P(G | DFI, ESL) &nbsp;·&nbsp; "
        f"dashed ticks = ESL Bel/Pl envelope ({bel_pct:.1f}% – {pl_pct:.1f}%)"
        f"</div></div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Posterior trajectory vs stance w (2-state Simm) — shared by char + custom
# ─────────────────────────────────────────────────────────────────────────────

def render_simm_trajectory(ctx, r: float, *, key: str | None = None) -> None:
    """Four-curve P(G) vs stance ``w`` plot for the 2-state Simm pathways.

    Solid = ESL/Classic priors across w; dashed = their Simm posteriors at the
    given ``r``. Stars mark the values at the current stance. Identical for the
    characteristic and custom sources (the DHI-Index pathway uses its own richer
    8-outcome trajectory in ``tab_dfi_plots``).
    """
    import numpy as np
    import plotly.graph_objects as go
    from logic.dfi_simm import simm_bayes_posterior
    from logic.dfi_context import (
        esl_rollup_prior_at_w as _esl_rollup_prior_at_w,
        classic_prior_pillars_from_ctx as _classic_prior_pillars_from_ctx,
    )

    w_cur = float(ctx.uncertainty_weight)
    w_grid = list(np.linspace(0.0, 1.0, 21))
    esl_prior_w, esl_post_w, cls_prior_w, cls_post_w = [], [], [], []
    for w in w_grid:
        p_e = _esl_rollup_prior_at_w(ctx, w)
        p_c = _classic_prior_pillars_from_ctx(ctx, w).prior_pg
        esl_prior_w.append(p_e * 100); esl_post_w.append(simm_bayes_posterior(p_e, r) * 100)
        cls_prior_w.append(p_c * 100); cls_post_w.append(simm_bayes_posterior(p_c, r) * 100)

    esl_prior_cur = _esl_rollup_prior_at_w(ctx, w_cur)
    cls_prior_cur = _classic_prior_pillars_from_ctx(ctx, w_cur).prior_pg

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=w_grid, y=esl_prior_w, mode="lines", name="P(G, ESL) prior",
                             line=dict(color="#16a34a", width=2)))
    fig.add_trace(go.Scatter(x=w_grid, y=esl_post_w,  mode="lines", name="P(G | DFI, ESL)",
                             line=dict(color="#16a34a", width=2, dash="dash")))
    fig.add_trace(go.Scatter(x=w_grid, y=cls_prior_w, mode="lines", name="P(G, Classic) prior",
                             line=dict(color="#1e40af", width=2)))
    fig.add_trace(go.Scatter(x=w_grid, y=cls_post_w,  mode="lines", name="P(G | DFI, Classic)",
                             line=dict(color="#1e40af", width=2, dash="dash")))
    fig.add_vline(x=w_cur, line_dash="dot", line_color="#6b7280",
                  annotation_text=f"current w = {w_cur:.2f}", annotation_position="top right")
    for px, py, col in [
        (w_cur, esl_prior_cur                       * 100, "#16a34a"),
        (w_cur, simm_bayes_posterior(esl_prior_cur, r) * 100, "#16a34a"),
        (w_cur, cls_prior_cur                       * 100, "#1e40af"),
        (w_cur, simm_bayes_posterior(cls_prior_cur, r) * 100, "#1e40af"),
    ]:
        fig.add_trace(go.Scatter(x=[px], y=[py], mode="markers",
                                 marker=dict(symbol="star", size=14, color=col,
                                             line=dict(color="white", width=1)),
                                 showlegend=False, hoverinfo="skip"))
    fig.update_xaxes(title_text="Stance w", range=[0, 1])
    fig.update_yaxes(title_text="P(G) (%)", range=[0, 100])
    fig.update_layout(height=380, margin=dict(t=10, b=40, l=50, r=10),
                      legend=dict(orientation="h", x=0.5, y=-0.15, xanchor="center"))
    st.plotly_chart(fig, use_container_width=True, key=key)
    st.caption(
        f"Solid = priors, dashed = posteriors after the DFI update (R = {r:.2f}). "
        "Stars = values at the current stance. The DFI evidence is a constant "
        "multiplicative shift in log-odds — its effect is largest where the prior is "
        "near 50 % and smallest at the extremes."
    )


# ─────────────────────────────────────────────────────────────────────────────
# DHI → volumetrics integration recommendation (Monigle 2025)
# ─────────────────────────────────────────────────────────────────────────────

def render_volumetrics_recommendation(
    dhi_score: float,
    *,
    v_weight: float | None = None,
    discernibility: str | None = None,
    key: str = "dfi_vol",
) -> None:
    """Recommend how to join geological vs DFI-defined volumes (Monigle 2025).

    Shows the two "trust" measures side by side — E-POS's SAAM **DHI Volume Weight
    V** (when available) and Monigle's **column-height trial weight** — then a
    concrete blend recommendation, the Fig. 8 weighting curve, and the paper's
    volumetric consistency gates (discernibility, FCR→NTG, porosity floor).

    ``dhi_score`` is the 0–1 DHI score (all pathways). ``v_weight`` is the SAAM
    DHI Volume Weight (DHI-Index pathway only). ``discernibility`` ∈
    {high, moderate, low, absent}.
    """
    import numpy as np
    import plotly.graph_objects as go
    from logic.dfi_volumetrics import (
        volumetrics_recommendation, column_height_weight, HIGH_DHI_TRIAL_WEIGHT,
    )

    st.markdown("##### Volumetrics integration — joining geological & DFI-defined volumes")
    st.caption(
        "Risk is only half the story: a DHI should also constrain the **volume** "
        "distribution. Below are two measures of *how much to trust the DFI for volumes*, "
        "and a recommended blend (Monigle 2025, Figs. 8 & 10)."
    )

    # FCR present/absent refines the NTG note.
    fcr_choice = st.radio(
        "Fluid contact reflection (FCR) observed?",
        options=["Unknown", "Present", "Absent"], horizontal=True,
        key=f"{key}_fcr",
        help="FCR presence constrains net-to-gross (Monigle Fig. 10).",
    )
    fcr_present = {"Present": True, "Absent": False, "Unknown": None}[fcr_choice]

    rec = volumetrics_recommendation(
        dhi_score, discernibility=discernibility, v_weight=v_weight,
        fcr_present=fcr_present,
    )

    # ── Two methods, side by side ──
    c1, c2, c3 = st.columns(3)
    c1.metric("DHI score", f"{rec.dhi_score*100:.0f}%",
              help="0–1 DHI score driving the column-height weighting.")
    c2.metric("Column-height trial weight",
              f"{rec.w_ch*100:.0f}%",
              help="Monigle 2025 (Fig. 8): w = min(95%, 2 × DHI score). Fraction of "
                   "volumetric trials placing the HCWC at the DFI-rated elevation.")
    if v_weight is not None:
        c3.metric("DHI Volume Weight V (SAAM)", f"{v_weight*100:.0f}%",
                  help="E-POS SAAM byproduct: L_success / (L_success + E[L|failure]) — "
                       "calibrated confidence the anomaly is a true HC response. "
                       "An independent cross-check on the column-height weight.")
    else:
        c3.metric("DHI Volume Weight V (SAAM)", "—",
                  help="Only available in the DHI-Index (SAAM) pathway.")

    # ── Headline recommendation ──
    st.markdown(
        f"<div style='background:#ecfeff;border-left:5px solid #0891b2;border-radius:6px;"
        f"padding:10px 14px;margin:6px 0;'>"
        f"<b style='color:#0e7490;'>Recommended blend:</b> {rec.headline}</div>",
        unsafe_allow_html=True,
    )
    if v_weight is not None:
        # Cross-check the two independent *strength* readouts (both 0–1): SAAM's
        # calibrated V and the R-derived DHI score. (The column-height weight is a
        # transform of the score, so it is not an independent estimate.)
        _spread = abs(v_weight - rec.dhi_score)
        _msg = ("the SAAM-calibrated confidence and the R-derived score agree closely — "
                "high confidence in the volume blend."
                if _spread < 0.15 else
                "they diverge — the SAAM likelihoods and the DHI score disagree on anomaly "
                "strength; reconcile before committing the volume distribution.")
        st.caption(f"DHI Volume Weight V = {v_weight*100:.0f}% vs DHI score "
                   f"{rec.dhi_score*100:.0f}% → {_msg}")

    # ── Monigle Fig. 8 weighting curve ──
    xs = np.linspace(0.0, 1.0, 101)
    ys = [column_height_weight(x) * 100 for x in xs]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[x*100 for x in xs], y=ys, mode="lines",
                             line=dict(color="#0891b2", width=2.5), name="w_ch"))
    fig.add_hline(y=HIGH_DHI_TRIAL_WEIGHT*100, line_dash="dot", line_color="#94a3b8",
                  annotation_text="95% cap", annotation_position="right")
    fig.add_vline(x=50, line_dash="dot", line_color="#94a3b8")
    fig.add_trace(go.Scatter(
        x=[rec.dhi_score*100], y=[rec.w_ch*100], mode="markers",
        marker=dict(symbol="star", size=16, color="#0e7490",
                    line=dict(color="white", width=1.5)),
        name="this prospect", hoverinfo="skip", showlegend=False))
    fig.update_xaxes(title_text="DHI score (%)", range=[0, 100])
    fig.update_yaxes(title_text="HCWC-at-DFI-elevation trial weight (%)", range=[0, 100])
    fig.update_layout(height=300, margin=dict(t=10, b=40, l=55, r=20), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, key=f"{key}_curve")

    # ── Consistency gates ──
    st.markdown("**Volumetric consistency checks**")
    for note in rec.consistency_notes:
        st.markdown(f"- {note}")
    st.caption(
        "Source: Monigle et al. (2025), Figs. 8 & 10 and the porosity discussion. "
        "This is interpretive guidance for building the volumetric distribution, not a "
        "Monte-Carlo engine — enter the resulting ranges in your volumetrics tool."
    )
