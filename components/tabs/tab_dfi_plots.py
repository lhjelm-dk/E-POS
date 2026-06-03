"""DFI plots — posterior trajectory, sensitivity sweep, iso-DHI surface.
Extracted from ``components.tabs.tab_dfi``.
"""
from __future__ import annotations

import streamlit as st

from logic.dfi_context import (
    esl_prior_pillars_from_ctx_at_w   as _esl_prior_pillars_from_ctx_at_w,
    esl_rollup_prior_at_w             as _esl_rollup_prior_at_w,
    classic_prior_pillars_from_ctx    as _classic_prior_pillars_from_ctx,
)

from logic.dfi_orchestration import _pillars_at_w, _set_pillar_combined


def _render_dfi_trajectory_plot(ctx, dhi, calib, fw, sd_mode, fluid_type) -> None:
    """Four curves: P(G, ESL) prior/posterior and P(G, Classic) prior/posterior, vs w.

    Also drops a vertical dashed line at the current stance and stars showing the
    current values for both methods (prior + posterior).
    """
    import numpy as np
    import plotly.graph_objects as go
    from logic.dfi_bayes import compute_dfi_posterior

    ws = np.linspace(0.0, 1.0, 21)
    esl_prior_arr, esl_post_arr = [], []
    cls_prior_arr, cls_post_arr = [], []
    for w in ws:
        pe = _esl_prior_pillars_from_ctx_at_w(ctx, float(w))
        pc = _classic_prior_pillars_from_ctx(ctx, float(w))
        esl_rollup = _esl_rollup_prior_at_w(ctx, float(w))
        post_e = compute_dfi_posterior(pe, dhi, calib, fw, sd_mode, fluid_type,
                                       prior_pg_override=esl_rollup)
        post_c = compute_dfi_posterior(pc, dhi, calib, fw, sd_mode, fluid_type)
        esl_prior_arr.append(esl_rollup * 100)
        esl_post_arr.append(post_e.posterior_pg * 100)
        cls_prior_arr.append(pc.prior_pg * 100)
        cls_post_arr.append(post_c.posterior_pg * 100)

    fig = go.Figure()
    # Priors — solid
    fig.add_trace(go.Scatter(
        x=ws, y=esl_prior_arr, mode="lines",
        line=dict(color="#16a34a", width=2.5),
        name="P(G, ESL)  — prior",
        hovertemplate="ESL prior<br>w=%{x:.2f}<br>P=%{y:.2f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=ws, y=cls_prior_arr, mode="lines",
        line=dict(color="#2563eb", width=2.5),
        name="P(G, Classic) — prior",
        hovertemplate="Classic prior<br>w=%{x:.2f}<br>P=%{y:.2f}%<extra></extra>",
    ))
    # Posteriors — dashed thicker
    fig.add_trace(go.Scatter(
        x=ws, y=esl_post_arr, mode="lines",
        line=dict(color="#16a34a", width=3.5, dash="dash"),
        name="P(G | DFI, ESL)  — posterior",
        hovertemplate="ESL posterior<br>w=%{x:.2f}<br>P=%{y:.2f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=ws, y=cls_post_arr, mode="lines",
        line=dict(color="#2563eb", width=3.5, dash="dash"),
        name="P(G | DFI, Classic) — posterior",
        hovertemplate="Classic posterior<br>w=%{x:.2f}<br>P=%{y:.2f}%<extra></extra>",
    ))

    # Vertical marker at current stance
    w_cur = ctx.uncertainty_weight
    fig.add_vline(
        x=w_cur, line_width=1.5, line_dash="dot", line_color="#dc2626",
        annotation_text=f"current w = {w_cur:.2f}",
        annotation_position="top",
        annotation_font=dict(size=10, color="#dc2626"),
    )

    # Stars at current stance
    idx_cur = int(np.argmin(np.abs(ws - w_cur)))
    fig.add_trace(go.Scatter(
        x=[w_cur, w_cur, w_cur, w_cur],
        y=[esl_prior_arr[idx_cur], esl_post_arr[idx_cur],
           cls_prior_arr[idx_cur], cls_post_arr[idx_cur]],
        mode="markers",
        marker=dict(symbol="star", size=14, color="#dc2626",
                    line=dict(color="white", width=1.5)),
        showlegend=False, hoverinfo="skip",
    ))

    fig.update_layout(
        xaxis=dict(title="Stance w  (0 = Bel · 1 = Pl)", range=[0, 1], dtick=0.1,
                   tickformat=".2f", showgrid=True, gridcolor="#e5e7eb"),
        yaxis=dict(title="P(G) (%)", range=[0, 100], dtick=10,
                   showgrid=True, gridcolor="#e5e7eb"),
        height=520, margin=dict(t=20, b=120, l=50, r=20),
        legend=dict(orientation="h", yanchor="top", y=-0.12,
                    xanchor="center", x=0.5, font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Solid** = priors, **dashed** = posteriors. **Green** = ESL, **blue** = Classic. "
        "Star markers = values at the current stance. The DFI observation (DHI = "
        f"{dhi:.0f}) shifts both posteriors away from their priors; the gap "
        "between solid and dashed for each method visualises the strength of the "
        "Bayesian update at that stance."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sensitivity sweep — generalises the workbook "Mod POS, wgt & str" charts
# ─────────────────────────────────────────────────────────────────────────────

def _render_sensitivity_sweep(ctx, dhi_cur, calib, fw_cur, sd_mode, fluid_type) -> None:
    """Generalised 2-D sweep: X-axis variable × curve-family parameter.

    Reproduces the four workbook charts on "Mod POS, wgt & str Graphs" and
    "INEOS DHI Prospect inputs (2)" (Reservoir-POS sweep) as configurable
    instances of one panel.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from logic.dfi_bayes import FluidWeights, compute_dfi_posterior

    # ── Controls ────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([1.1, 1.1, 1.1])
    with c1:
        x_var = st.selectbox(
            "X-axis (sweep variable)",
            ["DHI Index",
             "Reservoir P(combined)", "Charge P(combined)",
             "Closure P(combined)",   "Retention P(combined)",
             "Stance w"],
            key="sens_x_var",
        )
    with c2:
        family_var = st.selectbox(
            "Curve family (11 curves)",
            ["Water failure fraction", "LSG failure fraction",
             "Stance w", "DHI Index", "None (single curve)"],
            key="sens_family_var",
        )
    with c3:
        method = st.radio(
            "Method prior",
            ["ESL", "Classic"],
            horizontal=True, key="sens_method",
            help="Which prior to update — ESL (primary) or Classic (Rose-style).",
        )

    y_outputs = st.multiselect(
        "Y outputs (stacked)",
        ["Posterior P(G)", "R_SAAM", "DHI Volume Weight"],
        default=["Posterior P(G)"],
        key="sens_y_outputs",
    )
    if not y_outputs:
        st.info("Pick at least one Y output.")
        return
    if x_var == family_var:
        st.warning("X-axis and curve family must differ. Pick different variables.")
        return

    w_cur = float(ctx.uncertainty_weight)
    pillars_cur = _pillars_at_w(ctx, w_cur, method)

    # Build X sweep values + current-X marker value
    def _x_values(var: str) -> tuple[list[float], float, str]:
        if var == "DHI Index":
            return list(np.linspace(-23, 50, 30)), float(dhi_cur), "DHI Index"
        if var == "Stance w":
            return list(np.linspace(0.0, 1.0, 21)), w_cur, "Stance w"
        # Combined pillar Pg sweep — start at the current prior_pg (workbook style)
        pillar_map = {
            "Reservoir P(combined)": ("reservoir", pillars_cur.reservoir_play * pillars_cur.reservoir_cond),
            "Charge P(combined)":    ("charge",    pillars_cur.charge_play    * pillars_cur.charge_cond),
            "Closure P(combined)":   ("trap",      pillars_cur.trap_play      * pillars_cur.trap_cond),
            "Retention P(combined)": ("retention", pillars_cur.retention_play * pillars_cur.retention_cond),
        }
        pn, cur = pillar_map[var]
        lo = min(max(0.05, pillars_cur.prior_pg), cur)
        return list(np.linspace(lo, 1.0, 21)), cur, f"{var}"

    x_vals, x_cur, x_label = _x_values(x_var)

    # Build family values + current-family value
    def _family_values(var: str) -> tuple[list[float], float, str]:
        if var == "None (single curve)":
            return [None], None, ""
        if var == "Water failure fraction":
            return [i / 10 for i in range(11)], fw_cur.water, "water frac"
        if var == "LSG failure fraction":
            return [i / 10 for i in range(11)], fw_cur.lsg, "LSG frac"
        if var == "Stance w":
            return [i / 10 for i in range(11)], w_cur, "w"
        if var == "DHI Index":
            return list(np.linspace(-20, 50, 11)), float(dhi_cur), "DHI"
        return [None], None, ""

    fam_vals, fam_cur, fam_label = _family_values(family_var)

    # Helper: apply (x_var, x_val, family_var, fam_val) to (pillars, dhi, fw, w)
    def _eval_point(x_val, fam_val):
        # Start from current; mutate based on X and family
        pillars = pillars_cur
        dhi_v   = float(dhi_cur)
        fw_v    = fw_cur
        w_v     = w_cur

        def _apply(var, val):
            nonlocal pillars, dhi_v, fw_v, w_v
            if val is None or var == "None (single curve)":
                return
            if var == "DHI Index":
                dhi_v = float(val)
            elif var == "Stance w":
                w_v = float(val)
                pillars_new = _pillars_at_w(ctx, w_v, method)
                # If X-pillar sweep already applied a pillar override, preserve it
                pillars = pillars_new
            elif var == "Water failure fraction":
                # water=val, LSG=1-val, other=0 (matches workbook)
                fw_v = FluidWeights(water=float(val), lsg=1.0 - float(val), other=0.0).normalised()
            elif var == "LSG failure fraction":
                fw_v = FluidWeights(water=1.0 - float(val), lsg=float(val), other=0.0).normalised()
            elif var.endswith("P(combined)"):
                pmap = {"Reservoir P(combined)": "reservoir",
                        "Charge P(combined)":    "charge",
                        "Closure P(combined)":   "trap",
                        "Retention P(combined)": "retention"}
                pillars = _set_pillar_combined(pillars, pmap[var], float(val))

        # Stance-w must be applied BEFORE pillar overrides, so order matters
        if x_var == "Stance w":
            _apply(x_var, x_val); _apply(family_var, fam_val)
        elif family_var == "Stance w":
            _apply(family_var, fam_val); _apply(x_var, x_val)
        else:
            _apply(family_var, fam_val); _apply(x_var, x_val)

        post = compute_dfi_posterior(pillars, dhi_v, calib, fw_v, sd_mode, fluid_type)
        return post.posterior_pg, post.r_saam, post.dhi_volume_weight

    # Build subplots — one row per selected Y
    fig = make_subplots(rows=len(y_outputs), cols=1, shared_xaxes=True,
                        subplot_titles=y_outputs, vertical_spacing=0.08)

    # Color ramp for 11 curves (or 1 grey)
    def _color(i, n):
        if n <= 1:
            return "#1e40af"
        # purple-ish dark→light, matching the workbook
        t = i / max(1, n - 1)
        r = int(40 + (200 - 40) * t)
        g = int(40 + (200 - 40) * t)
        b = int(140 + (220 - 140) * t)
        return f"rgb({r},{g},{b})"

    # Sweep
    n_fam = len(fam_vals)
    y_keys = []
    for yo in y_outputs:
        y_keys.append({"Posterior P(G)": 0, "R_SAAM": 1, "DHI Volume Weight": 2}[yo])

    for i_fam, fv in enumerate(fam_vals):
        ys_per_y = [[] for _ in y_outputs]
        for xv in x_vals:
            yvals = _eval_point(xv, fv)
            for k, yk in enumerate(y_keys):
                ys_per_y[k].append(yvals[yk] * (100.0 if yk == 0 else 1.0))
        legend_name = (f"{fv*100:.0f}% {fam_label}"
                       if fam_label.endswith("frac") else
                       (f"{fam_label} = {fv:.2f}" if fv is not None else "sweep"))
        for k, yo in enumerate(y_outputs):
            fig.add_trace(go.Scatter(
                x=[xv * (100.0 if x_var.endswith("(combined)") or x_var == "Stance w" else 1.0)
                   for xv in x_vals],
                y=ys_per_y[k], mode="lines",
                line=dict(color=_color(i_fam, n_fam), width=2),
                name=legend_name,
                legendgroup=legend_name,
                showlegend=(k == 0),
                hovertemplate=f"{yo}: %{{y:.3f}}<br>{x_label}: %{{x:.2f}}<extra>{legend_name}</extra>",
            ), row=k + 1, col=1)

    # ★ marker at current prospect (closest family curve, current X)
    if fam_cur is not None and n_fam > 1:
        i_close = int(np.argmin([abs(fv - fam_cur) for fv in fam_vals]))
    else:
        i_close = 0
    star_yvals = _eval_point(x_cur, fam_vals[i_close])
    x_cur_disp = x_cur * (100.0 if x_var.endswith("(combined)") or x_var == "Stance w" else 1.0)
    for k, yk in enumerate(y_keys):
        yv = star_yvals[yk] * (100.0 if yk == 0 else 1.0)
        fig.add_trace(go.Scatter(
            x=[x_cur_disp], y=[yv], mode="markers+text",
            marker=dict(symbol="star", size=18, color="#dc2626",
                        line=dict(color="white", width=1.5)),
            text=[f"  ★ {yv:.2f}{'%' if yk == 0 else ''}"], textposition="middle right",
            textfont=dict(size=11, color="#7f1d1d"),
            name="Current prospect", legendgroup="current",
            showlegend=(k == 0),
            hovertemplate=(f"<b>Current prospect</b><br>{x_label}: %{{x:.2f}}<br>"
                           f"value: %{{y:.3f}}<extra></extra>"),
        ), row=k + 1, col=1)

    # Reference line: Initial Pg (prior P(G)) on the Posterior P(G) row
    if "Posterior P(G)" in y_outputs:
        row_idx = y_outputs.index("Posterior P(G)") + 1
        fig.add_hline(
            y=pillars_cur.prior_pg * 100,
            line_dash="dot", line_color="#f59e0b", line_width=1.5,
            annotation_text=f"Initial Pg = {pillars_cur.prior_pg*100:.1f}%",
            annotation_position="top left",
            annotation_font=dict(size=10, color="#92400e"),
            row=row_idx, col=1,
        )

    # Axis labels
    x_axis_label = ("Reservoir POS (combined) %"   if x_var == "Reservoir P(combined)" else
                    "Charge POS (combined) %"     if x_var == "Charge P(combined)" else
                    "Closure POS (combined) %"    if x_var == "Closure P(combined)" else
                    "Retention POS (combined) %"  if x_var == "Retention P(combined)" else
                    "Stance w (%)"                if x_var == "Stance w" else
                    "DHI Index")
    fig.update_xaxes(title_text=x_axis_label, row=len(y_outputs), col=1)
    for k, yo in enumerate(y_outputs):
        fig.update_yaxes(title_text=(yo + (" (%)" if yo == "Posterior P(G)" else "")),
                         row=k + 1, col=1)

    fig.update_layout(
        height=480 * len(y_outputs),
        margin=dict(t=40, b=60, l=60, r=20),
        legend=dict(orientation="v", x=1.02, y=1.0,
                    bordercolor="#e5e7eb", borderwidth=1,
                    font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Auto-interpretation caption
    cur_post_pg = star_yvals[0] * 100
    prior_pg_pct = pillars_cur.prior_pg * 100
    direction = "uplift" if cur_post_pg > prior_pg_pct else "downgrade"
    delta = cur_post_pg - prior_pg_pct
    st.caption(
        f"★ = current prospect at ({x_label} = {x_cur:.2f}, {fam_label or 'fixed'}"
        f"{(' = ' + format(fam_cur, '.2f')) if fam_cur is not None else ''}). "
        f"At this point the DFI observation produces a **{direction} of {delta:+.1f} pp** "
        f"(prior {prior_pg_pct:.1f}% → posterior {cur_post_pg:.1f}%). "
        f"Curves spreading apart = high sensitivity to that family choice; "
        f"curves bunching = robust to it."
    )


def _render_iso_dhi_plot(ctx, dhi_cur, calib, fw, sd_mode, fluid_type) -> None:
    """Initial Pg (x) vs DFI-modified posterior POS (y), one curve per DHI Index.

    Reproduces the workbook "DHI adjustment of POS" chart. The prospect's
    failure-mode mix (water/LSG/other × eval/non-eval reservoir) is held fixed;
    only the overall prior Pg is swept 0→1, so each curve shows how *any* prior
    of a given quality would be updated at that DHI Index.
    """
    import numpy as np
    import plotly.graph_objects as go
    from logic.dfi_bayes import (decompose_prior, rescale_outcomes_to_success,
                                 posterior_pg_from_outcomes)

    ISO_DHI = [-10, 0, 10, 13, 20, 30, 40, 50]

    # Prospect's current decomposition supplies the failure-mode template
    w_cur = float(ctx.uncertainty_weight)
    prior_pillars = _esl_prior_pillars_from_ctx_at_w(ctx, w_cur)
    base_outcomes = decompose_prior(prior_pillars, fw).as_dict()
    # Star sits at the booked headline mass-rollup P(G, ESL) so its posterior
    # matches the Results metric (∏-pillars Init Pg only supplies the failure mix).
    prospect_prior_pg = _esl_rollup_prior_at_w(ctx, w_cur)

    pg_grid = list(np.linspace(0.0, 1.0, 51))

    fig = go.Figure()
    # y = x reference (no modification)
    fig.add_trace(go.Scatter(
        x=[0, 100], y=[0, 100], mode="lines",
        line=dict(color="#9ca3af", width=1, dash="dot"),
        name="no change (y = x)", hoverinfo="skip",
    ))

    # Colour ramp dark→light across the iso-DHI list
    n = len(ISO_DHI)
    def _col(i):
        t = i / max(1, n - 1)
        r = int(30 + (180 - 30) * t); g = int(60 + (190 - 60) * t); b = int(160 + (230 - 160) * t)
        return f"rgb({r},{g},{b})"

    for i, d in enumerate(ISO_DHI):
        ys = []
        for T in pg_grid:
            oc = rescale_outcomes_to_success(base_outcomes, T)
            ys.append(posterior_pg_from_outcomes(oc, d, calib, sd_mode, fluid_type) * 100)
        fig.add_trace(go.Scatter(
            x=[p * 100 for p in pg_grid], y=ys, mode="lines",
            line=dict(color=_col(i), width=2.4 if d == 13 else 1.8),
            name=f"DHI {d:+d}",
            hovertemplate=f"DHI {d:+d}<br>prior %{{x:.0f}}%% → posterior %{{y:.1f}}%%<extra></extra>",
        ))

    # ★ prospect marker at (prior_pg, posterior at current DHI)
    star_post = posterior_pg_from_outcomes(
        rescale_outcomes_to_success(base_outcomes, prospect_prior_pg),
        dhi_cur, calib, sd_mode, fluid_type) * 100
    fig.add_trace(go.Scatter(
        x=[prospect_prior_pg * 100], y=[star_post], mode="markers+text",
        marker=dict(symbol="star", size=18, color="#dc2626",
                    line=dict(color="white", width=1.5)),
        text=[f"  ★ {star_post:.1f}%"], textposition="middle right",
        textfont=dict(size=11, color="#7f1d1d"),
        name=f"this prospect (DHI {dhi_cur:+.0f})",
        hovertemplate=(f"<b>This prospect</b><br>prior %{{x:.1f}}%% → "
                       f"posterior %{{y:.1f}}%%<extra></extra>"),
    ))
    # Dotted guide from prior on the x-axis up to the prospect marker
    fig.add_trace(go.Scatter(
        x=[prospect_prior_pg * 100, prospect_prior_pg * 100],
        y=[prospect_prior_pg * 100, star_post], mode="lines",
        line=dict(color="#dc2626", width=1, dash="dot"),
        showlegend=False, hoverinfo="skip",
    ))

    fig.update_xaxes(title_text="Initial Pg (geological prior) %", range=[0, 100])
    fig.update_yaxes(title_text="DFI-modified posterior POS %", range=[0, 100])
    fig.update_layout(
        height=460, margin=dict(t=20, b=55, l=60, r=20),
        legend=dict(orientation="v", x=1.02, y=1.0,
                    bordercolor="#e5e7eb", borderwidth=1, font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Each curve is one DHI Index value; the dotted diagonal is the no-change line "
        "(posterior = prior). Curves **above** the diagonal mean that DHI value *raises* "
        "P(G); curves **below** mean it *lowers* it. The ★ is this prospect at its current "
        f"DHI Index ({dhi_cur:+.0f}). The failure-mode mix (water/LSG/other) is held at the "
        "prospect's current values, so the curves show how a prior of any quality would be "
        "updated by the same seismic evidence. Note the curves cross the diagonal at low "
        "DHI — a weak DHI Index downgrades an otherwise-strong prior."
    )


