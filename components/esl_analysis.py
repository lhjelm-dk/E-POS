"""ESL analysis plot functions extracted from app.py.

Contains the three large rendering functions for plots in the Analysis tab:
- render_sensitivity_analysis
- _render_esl_ratio_plot_and_validation
- _render_cam_scatter_plot
"""
from __future__ import annotations

import math as _math

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from components.colors import (
    PILLAR_COLORS as CAT_COLORS,
    PILLAR_COLORS_COND as CAT_COLORS_COND,
    bar_color_for_label,
    COMPANY_DEFAULT_WEIGHT,
)
from components.render_helpers import (
    policy_pos,
    calculate_flag,
    ratio_xy,
    point_in_poly,
    classify_esl_region_by_curves,
    _compute_total_pos_from_pillars,
    _compute_cond_results_with_override,
)
from logic.esl_logic import apply_product_logic
from logic.esl_pipeline import group_by_label, combine_with_mode


# ---------------------------------------------------------------------------
# Sensitivity analysis (tornado chart)
# ---------------------------------------------------------------------------

def render_sensitivity_analysis(
    play: dict,
    conditional: dict,
    conditional_results: dict,
    uncertainty_weight: float,
    get_mode,
    get_dependency,
    combine_with_mode_fn,
) -> None:
    """Tornado chart for ESL — thin wrapper around the shared helper.

    Builds an ESL-specific ``compute_total`` callback that uses mass-product
    logic (apply_product_logic across pillars, then policy_pos at the end).
    """
    play_vals = {
        pid: (float(pdata["support_for"]), float(pdata["support_against"]))
        for pid, pdata in play.items()
        if isinstance(pdata, dict) and "support_for" in pdata
    }
    cond_vals_base = {
        cat: (float(v["for"]), float(v["against"]))
        for cat, v in conditional_results.items()
    }

    def _compute_total_esl(override, w: float) -> float:
        pv = dict(play_vals)
        cv = dict(cond_vals_base)
        if override is None:
            return _compute_total_pos_from_pillars(pv, cv, w)
        kind = override[0]
        if kind == "play":
            _, pid, sf, sa = override
            pv[pid] = (sf, sa)
        elif kind == "cond_agg":
            _, pid, sf, sa = override
            cv[pid] = (sf, sa)
        elif kind == "cond_sub":
            _, pid, idx, sf, sa = override
            new_cond = _compute_cond_results_with_override(
                conditional, {(pid, idx): (sf, sa)},
                get_mode, get_dependency, combine_with_mode_fn,
            )
            cv = {c: (r["for"], r["against"]) for c, r in new_cond.items()}
        return _compute_total_pos_from_pillars(pv, cv, w)

    from components.risk_summary import render_sensitivity_tornado
    render_sensitivity_tornado(
        method_label="ESL",
        play=play,
        conditional=conditional,
        uncertainty_weight=uncertainty_weight,
        compute_total=_compute_total_esl,
        include_cond_aggregate_in_pillars=True,
    )


# ---------------------------------------------------------------------------
# ESL ratio plot
# ---------------------------------------------------------------------------

def _render_esl_ratio_plot_and_validation(
    play: dict,
    conditional: dict,
    conditional_results: dict,
    total_for: float,
    total_against: float,
    uncertainty_weight: float,
    run_input_validation,
    prospect_title: str,
    get_mode,
    get_dependency,
    combine_with_mode_fn,
    leaf_filter: "set | None" = None,
    pillar_display: "dict | None" = None,
    pillar_colors: "dict | None" = None,
) -> None:
    """Render ESL ratio plot, input validation, and sensitivity analysis."""
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        show_total = st.checkbox("P(G, ESL)", value=True, key="rp_show_total")
        show_play = st.checkbox("P(Play)", value=True, key="rp_show_play")
        show_cond = st.checkbox("P(Cond)", value=True, key="rp_show_cond")
    with col_b:
        show_play_cats = st.checkbox("Play: pillars", value=True, key="rp_show_pcats")
        show_cond_cats = st.checkbox("Conditional: pillars", value=True, key="rp_show_ccats")
    with col_c:
        show_all_leaves = st.checkbox("All individual risk elements", value=False, key="rp_show_leaves")
        show_labels = st.checkbox("Show labels", value=True, key="rp_show_labels")
    shading_mode = st.selectbox("Shading", ["Smooth (filled)", "Dense points"], key="rp_shading")
    shading_opacity = st.slider("Shading opacity", 0.1, 1.0, 0.8, 0.05, key="rp_opacity")

    OUTLINE_DATA = [
        (0.01,0.01,0.98,1),(0.02,0.01,0.97,2),(0.03,0.01,0.96,3),(0.04,0.01,0.95,4),
        (0.05,0.01,0.94,5),(0.06,0.01,0.93,6),(0.07,0.01,0.92,7),(0.08,0.01,0.91,8),
        (0.09,0.01,0.9,9),(0.1,0.01,0.89,10),(0.2,0.01,0.79,20),(0.3,0.01,0.69,30),
        (0.4,0.01,0.59,40),(0.5,0.01,0.49,50),(0.6,0.01,0.39,60),(0.7,0.01,0.29,70),
        (0.8,0.01,0.19,80),(0.9,0.01,0.09,90),(1,0.01,-0.01,100),(1,0.02,-0.02,50),
        (1,0.03,-0.03,33.33),(1,0.04,-0.04,25),(1,0.05,-0.05,20),(1,0.1,-0.1,10),
        (1,0.2,-0.2,5),(1,0.3,-0.3,3.33),(1,0.4,-0.4,2.5),(1,0.5,-0.5,2),
        (1,0.6,-0.6,1.67),(1,0.7,-0.7,1.43),(1,0.8,-0.8,1.25),(1,0.9,-0.9,1.11),
        (1,1,-1,1),(0.9,1,-0.9,0.9),(0.8,1,-0.8,0.8),(0.7,1,-0.7,0.7),
        (0.6,1,-0.6,0.6),(0.5,1,-0.5,0.5),(0.4,1,-0.4,0.4),(0.3,1,-0.3,0.3),
        (0.2,1,-0.2,0.2),(0.1,1,-0.1,0.1),(0.05,1,-0.05,0.05),(0.02,1,-0.02,0.02),
        (0.01,1,-0.01,0.01),(0.01,0.9,0.09,0.0111),(0.01,0.8,0.19,0.0125),
        (0.01,0.7,0.29,0.01429),(0.01,0.6,0.39,0.01667),(0.01,0.5,0.49,0.02),
        (0.01,0.4,0.59,0.025),(0.01,0.3,0.69,0.0333),(0.01,0.2,0.79,0.05),
        (0.01,0.1,0.89,0.1),(0.01,0.05,0.94,0.2),(0.01,0.02,0.97,0.5),(0.01,0.01,0.98,1),
    ]
    outline_x = [row[2] * 100 for row in OUTLINE_DATA]
    outline_y = [row[3] for row in OUTLINE_DATA]
    if outline_x and (outline_x[0] != outline_x[-1] or outline_y[0] != outline_y[-1]):
        outline_x.append(outline_x[0])
        outline_y.append(outline_y[0])

    colorscale = [
        [0/7, "#E1FFB4"], [1/7, "#BEF096"], [2/7, "#7DE67D"], [3/7, "#C8FFC8"],
        [4/7, "#FFE0AB"], [5/7, "#FFBE83"], [6/7, "#FF9583"], [7/7, "#FFC7AB"],
    ]
    eps = 0.001
    fig = go.Figure()

    if shading_mode == "Smooth (filled)":
        x_grid = np.linspace(-100, 100, 220)
        y_grid = np.logspace(-2, 2, 220)
        z = np.full((len(y_grid), len(x_grid)), np.nan)

        def fa_from_xy(x_val, r_val):
            if x_val >= 0:
                s = 1 - x_val / 100.0
            else:
                s = 1 + (-x_val) / 100.0
            f_val = (r_val * s) / (1 + r_val)
            a_val = s / (1 + r_val)
            return f_val, a_val

        for yi, yv in enumerate(y_grid):
            for xi, xv in enumerate(x_grid):
                f, a = fa_from_xy(xv, yv)
                if f < 0.01 or a < 0.01 or f > 1 or a > 1:
                    continue
                if not point_in_poly(xv, yv, outline_x, outline_y):
                    continue
                z[yi, xi] = classify_esl_region_by_curves(xv, yv)
        fig.add_trace(go.Heatmap(
            x=x_grid, y=y_grid, z=z,
            colorscale=colorscale, showscale=False, opacity=shading_opacity, hoverinfo="skip",
        ))
    else:
        REGION_COLORS = {
            1: "rgba(210,240,190,0.38)", 2: "rgba(170,220,150,0.38)", 3: "rgba(100,180,80,0.40)",
            4: "rgba(190,230,180,0.38)", 5: "rgba(250,200,160,0.38)", 6: "rgba(240,180,130,0.38)",
            7: "rgba(230,90,70,0.42)", 8: "rgba(240,160,130,0.38)",
        }
        f_vals = np.linspace(eps, 1 - eps, 140)
        a_vals = np.linspace(eps, 1 - eps, 140)
        xs, ys, colors = [], [], []
        for f in f_vals:
            for a in a_vals:
                u = 1 - f - a
                c = f + a - 1
                xv = 100 * u if u >= 0 else -100 * c
                rv = min(max(f, 0.01) / max(a, 0.01), 100.0)
                if not point_in_poly(xv, rv, outline_x, outline_y):
                    continue
                xs.append(xv)
                ys.append(rv)
                colors.append(REGION_COLORS[classify_esl_region_by_curves(xv, rv)])
        fig.add_trace(go.Scattergl(
            x=xs, y=ys, mode="markers",
            marker=dict(color=colors, size=3, symbol="square"),
            hoverinfo="skip", showlegend=False,
        ))

    fig.add_trace(go.Scatter(
        x=outline_x, y=outline_y, mode="lines",
        line=dict(color="#6b7280", width=2), showlegend=False,
    ))
    a_line = np.linspace(0.01, 0.99, 200)
    f_line = np.full_like(a_line, 0.5)
    u_line = 1 - f_line - a_line
    c_line = f_line + a_line - 1
    x_line = np.where(u_line >= 0, 100 * u_line, -100 * c_line)
    y_line = np.maximum(f_line, 0.01) / np.maximum(a_line, 0.01)
    fig.add_trace(go.Scatter(x=x_line, y=y_line, mode="lines", line=dict(color="#2f855a", width=2), name="For = 0.5"))
    f_line2 = np.linspace(0.01, 0.99, 200)
    a_line2 = np.full_like(f_line2, 0.5)
    u_line2 = 1 - f_line2 - a_line2
    c_line2 = f_line2 + a_line2 - 1
    x_line2 = np.where(u_line2 >= 0, 100 * u_line2, -100 * c_line2)
    y_line2 = np.maximum(f_line2, 0.01) / np.maximum(a_line2, 0.01)
    fig.add_trace(go.Scatter(x=x_line2, y=y_line2, mode="lines", line=dict(color="#b45309", width=2), name="Against = 0.5"))
    fig.add_hline(y=1, line_dash="dash", line_color="#6b7280")
    fig.add_vline(x=0, line_dash="dash", line_color="#6b7280")

    MARKER_SIZES = {1: 16, 2: 12, 3: 10, 4: 6}
    category_symbols = {"Charge": "diamond", "Closure": "square", "Reservoir": "triangle-up", "Retention": "circle"}

    def _fmt_label(name, trace_label):
        if trace_label == "Play Chance" and name == "Play":
            return "Play Chance"
        if trace_label == "Prospect Chance" and name == "Conditional":
            return "Prospect Chance"
        if name == "Total":
            return "Total"
        if " (Play)" in name or " (Cond)" in name:
            return name
        if name.startswith("Play "):
            return name[5:] + " (Play)"
        if name.startswith("Cond "):
            return name[5:] + " (Cond)"
        if trace_label == "All leaf elements":
            return name + " (Cond)"
        return name

    def _add_pts(label, points, color, symbol, size_level):
        if not points:
            return
        xs_p, ys_p, texts = [], [], []
        for name, f, a in points:
            xv, yv = ratio_xy(f, a)
            xs_p.append(xv)
            ys_p.append(yv)
            texts.append(_fmt_label(name, label))
        size = MARKER_SIZES.get(size_level, 10)
        mode = "markers+text" if show_labels else "markers"
        kw = dict(x=xs_p, y=ys_p, mode=mode, marker=dict(
            color=color if not isinstance(color, list) else color,
            symbol=symbol, size=size, line=dict(color="black", width=1.5)),
            name=label)
        if show_labels:
            kw["text"] = texts
            kw["textposition"] = "top center"
        fig.add_trace(go.Scatter(**kw))

    _pdisplay = pillar_display or {}
    _pcolors = pillar_colors or {}

    if show_total:
        _add_pts("P(G, ESL)", [("Total", total_for, total_against)], "#111827", "star", 1)
    if show_play:
        play_nodes = [
            {"support_for": el["support_for"], "support_against": el["support_against"]}
            for el in play.values()
            if isinstance(el, dict) and "support_for" in el
        ]
        pf, pa = apply_product_logic(play_nodes)
        _add_pts("Play Chance", [("Play", pf, pa)], "#0f766e", "diamond", 2)
    if show_cond:
        cond_nodes = [
            {"support_for": v["for"], "support_against": v["against"]}
            for v in conditional_results.values()
        ]
        cf, ca = apply_product_logic(cond_nodes)
        _add_pts("Prospect Chance", [("Conditional", cf, ca)], "#7c3aed", "diamond", 2)
    if show_play_cats:
        for pid, el in play.items():
            if not (isinstance(el, dict) and "support_for" in el):
                continue
            disp = _pdisplay.get(pid, pid)
            color = _pcolors.get(pid, CAT_COLORS.get(pid, "#6b7280"))
            _add_pts(
                "Play " + disp,
                [(disp + " (Play)", el["support_for"], el["support_against"])],
                color, category_symbols.get(pid, "circle"), 3,
            )
    if show_cond_cats:
        for pid, cres in conditional_results.items():
            disp = _pdisplay.get(pid, pid)
            color = _pcolors.get(pid, CAT_COLORS_COND.get(pid, "#9ca3af"))
            _add_pts(
                "Cond " + disp,
                [(disp + " (Cond)", cres["for"], cres["against"])],
                color, category_symbols.get(pid, "circle"), 3,
            )
    if show_all_leaves:
        leaf_points, leaf_colors = [], []
        for cat, el in play.items():
            _eid = f"play|{cat}"
            if leaf_filter is not None and _eid not in leaf_filter:
                continue
            if not isinstance(el, dict) or "support_for" not in el:
                continue
            _d = _pdisplay.get(cat, cat)
            leaf_points.append((_d + " ▶ Play", el["support_for"], el["support_against"]))
            leaf_colors.append(_pcolors.get(cat, CAT_COLORS.get(cat, "#6b7280")))
        for category, elements in conditional.items():
            _d = _pdisplay.get(category, category)
            c = _pcolors.get(category, CAT_COLORS_COND.get(category, "#9ca3af"))
            for idx, elem in enumerate(elements):
                _eid = f"cond|{category}|{idx}"
                if leaf_filter is not None and _eid not in leaf_filter:
                    continue
                _sc = (elem.get("success_criteria", "") or elem.get("label", ""))[:35]
                leaf_points.append((f"{_d}: {_sc}", elem["support_for"], elem["support_against"]))
                leaf_colors.append(c)
        if leaf_points:
            _add_pts("All leaf elements", leaf_points, leaf_colors, "x", 4)

    _y_tickvals = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200]
    _y_ticktext = ["0.005", "0.01", "0.02", "0.05", "0.1", "0.2", "0.5", "1", "2", "5", "10", "20", "50", "100", "200"]
    fig.update_layout(
        height=780, margin=dict(l=60, r=50, t=50, b=60),
        xaxis_title="Residual uncertainty (%)",
        yaxis_title="Confidence ratio (For/Against)",
        yaxis_type="log",
        xaxis_range=[-100, 100], xaxis=dict(tick0=-100, dtick=20),
        yaxis_range=[np.log10(0.005), np.log10(200)],
        yaxis_tickmode="array", yaxis_tickvals=_y_tickvals, yaxis_ticktext=_y_ticktext,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Input Validation", expanded=False):
        st.caption("Automated checks for logical consistency and unassessed defaults. Resolve errors before use in any investment decision.")
        validation_issues = run_input_validation(play, conditional, conditional_results, total_for, total_against)
        if not validation_issues:
            st.success("✅ No validation issues found. All elements are within expected ranges.")
        else:
            n_errors = sum(1 for i in validation_issues if i["level"] == "error")
            n_warnings = sum(1 for i in validation_issues if i["level"] == "warning")
            n_info = sum(1 for i in validation_issues if i["level"] == "info")
            st.markdown(f"**{len(validation_issues)} issue(s) found:** {n_errors} error(s), {n_warnings} warning(s), {n_info} info")
            for issue in validation_issues:
                if issue["level"] == "error":
                    st.error(f"🔴 {issue['message']}")
                elif issue["level"] == "warning":
                    st.warning(f"🟠 {issue['message']}")
                else:
                    st.info(f"🔵 {issue['message']}")

    with st.expander("Sensitivity Tornado — P(G, ESL)", expanded=True):
        render_sensitivity_analysis(
            play, conditional, conditional_results, uncertainty_weight,
            get_mode, get_dependency, combine_with_mode_fn
        )


# ---------------------------------------------------------------------------
# Chance Adequacy Matrix scatter plot
# ---------------------------------------------------------------------------

def _render_cam_scatter_plot(
    play: dict,
    conditional: dict,
    conditional_results: dict,
    total_for: float,
    total_against: float,
    uncertainty_weight: float,
    pillar_colors: dict,
    pillar_display: dict,
    leaf_filter: "set | None" = None,
    show_labels: bool = True,
    dfi_overlay: "tuple | None" = None,
) -> None:
    """Chance Adequacy Matrix — all elements on POS × ECI/C axes.

    ``dfi_overlay`` (optional) is ``(prior_pos, post_pos)`` — the prospect-level
    headline P(G, ESL) before and after the DFI update. When supplied, a toggle adds
    two vertical reference lines showing the headline shift against the zone bands.
    """
    _sym = {"Charge": "diamond", "Closure": "square",
            "Reservoir": "triangle-up", "Retention": "circle"}
    w = float(uncertainty_weight)

    _all_pos_vals: list[float] = []
    for _cat, _el in play.items():
        if isinstance(_el, dict) and "support_for" in _el:
            _all_pos_vals.append(policy_pos(float(_el["support_for"]), float(_el["support_against"]), w))
    for _cat, _elems in conditional.items():
        for _elem in _elems:
            _all_pos_vals.append(policy_pos(float(_elem["support_for"]), float(_elem["support_against"]), w))

    if _all_pos_vals:
        _g_default = float(np.clip(round(float(np.percentile(_all_pos_vals, 75)), 2), 0.45, 0.90))
        _r_default = float(np.clip(round(float(np.percentile(_all_pos_vals, 25)), 2), 0.10, 0.55))
        _r_default = min(_r_default, _g_default - 0.10)
    else:
        _g_default, _r_default = 0.60, 0.30

    _rca, _rcb = st.columns([3, 1])
    with _rca:
        _y_mode = st.radio(
            "Y axis",
            options=["Commitment  C = S_for + S_against", "ECI  |S_for − S_against|"],
            horizontal=True, key="cam_scatter_ymode",
        )
    with _rcb:
        _log_y = st.checkbox("Log Y axis", value=False, key="cam_scatter_logy",
                             help="Logarithmic Y axis (≈0.5%–110%). Useful when evidence commitment is concentrated near zero.")
    _use_eci = "ECI" in _y_mode

    _sc1, _sc2, _sc3 = st.columns([5, 5, 2])
    with _sc1:
        _g_th = st.slider("Green boundary (Pg ≥)", 0.30, 0.95, _g_default, 0.05,
                          key="cam_scatter_gth",
                          help="Implied Pg above this → green zone. Auto-set to 75th-percentile POS on first load.")
    with _sc2:
        _r_th = st.slider("Red boundary  (Pg ≤)", 0.05, 0.60, _r_default, 0.05,
                          key="cam_scatter_rth",
                          help="Implied Pg below this → red zone. Auto-set to 25th-percentile POS on first load.")
    with _sc3:
        st.write("")

        def _reset_bounds():
            st.session_state["cam_scatter_gth"] = _g_default
            st.session_state["cam_scatter_rth"] = _r_default
        st.button("↺ Auto", on_click=_reset_bounds, key="cam_reset_bounds",
                  help=f"Reset to data-driven defaults: green={_g_default:.0%}, red={_r_default:.0%}")
    _g_th = max(_r_th + 0.05, _g_th)

    _oc1, _oc2, _oc3, _oc4 = st.columns(4)
    with _oc1:
        _show_iso = st.checkbox("Iso-Pg contours", value=True, key="cam_iso_pg",
                                help="Draw Pg iso-lines at 10%, 30%, 50%, 70%, 90%.")
    with _oc2:
        _show_bel_pl = st.checkbox("Bel / Pl interval", value=False, key="cam_bel_pl",
                                   help="Horizontal bars showing defensible POS range: Bel = S_for (lower bound), Pl = 1 − S_against (upper bound).")
    with _oc3:
        _opacity_by_c = st.checkbox("Opacity ∝ commitment", value=False, key="cam_opacity_c",
                                    help="More transparent = lower total commitment S_for + S_against.")
    with _oc4:
        _show_nogo = st.checkbox("Risking-V no-go", value=False, key="cam_scatter_nogo",
                                 help="Rose / ExxonMobil 'legacy no-go' (high commitment + "
                                      "middling POS). A binary-state reference, superseded for a "
                                      "probability — see Theory & Guide → 'The Risking V'.")

    _C_lo = 0.05 if _log_y else 0.0
    _C = np.linspace(_C_lo, 1.0, 500)
    _pos_min = w * (1.0 - _C)
    _pos_max = _C + w * (1.0 - _C)
    _pos_grn = np.clip(_g_th * _C + w * (1.0 - _C), _pos_min, _pos_max)
    _pos_red = np.clip(_r_th * _C + w * (1.0 - _C), _pos_min, _pos_max)

    def _band(x_lo, x_hi, y_v, fc, nm):
        xs = np.concatenate([x_lo, x_hi[::-1], [x_lo[0]]])
        ys = np.concatenate([y_v, y_v[::-1], [y_v[0]]])
        return go.Scatter(x=xs, y=ys, fill="toself", fillcolor=fc,
                          line=dict(width=0), mode="lines",
                          name=nm, hoverinfo="skip", showlegend=True)

    fig = go.Figure()
    fig.add_trace(_band(_pos_min, _pos_red, _C, "rgba(210,40,40,0.20)", "Negative (Pg ≤ r)"))
    fig.add_trace(_band(_pos_red, _pos_grn, _C, "rgba(250,250,250,0.88)", "Uncertain"))
    fig.add_trace(_band(_pos_grn, _pos_max, _C, "rgba(30,155,60,0.20)", "Positive (Pg ≥ g)"))

    # Risking-V "legacy no-go" — the uncertain band at high commitment (Rose/Exxon).
    # A faint, labelled REFERENCE only: it applies to a binary state of nature, not a
    # probability, so it is superseded for P(G). See Theory & Guide.
    if _show_nogo:
        _ng = _C >= 0.55
        if _ng.sum() >= 2:
            fig.add_trace(_band(_pos_red[_ng], _pos_grn[_ng], _C[_ng],
                                "rgba(124,92,160,0.18)",
                                "Risking-V legacy no-go (binary-state only)"))
            _ci = int(np.argmax(_C >= 0.90))
            fig.add_annotation(
                x=(_pos_red[_ci] + _pos_grn[_ci]) / 2.0, y=0.85,
                text="legacy no-go", showarrow=False,
                font=dict(size=10, color="rgba(95,65,135,0.95)"))

    if _show_iso:
        for _pg_lv in [0.10, 0.30, 0.50, 0.70, 0.90]:
            _pos_iso = np.clip(_pg_lv * _C + w * (1.0 - _C), _pos_min, _pos_max)
            _mask = (_pos_iso > _pos_min + 1e-4) & (_pos_iso < _pos_max - 1e-4)
            if _mask.sum() < 2:
                continue
            if _pg_lv >= _g_th:
                _ic = "rgba(0,130,50,0.50)"
            elif _pg_lv <= _r_th:
                _ic = "rgba(185,35,35,0.50)"
            else:
                _ic = "rgba(130,115,80,0.45)"
            fig.add_trace(go.Scatter(
                x=_pos_iso[_mask], y=_C[_mask], mode="lines",
                line=dict(color=_ic, width=1, dash="dot"),
                showlegend=False,
                hovertemplate=f"Pg = {_pg_lv:.0%}<br>POS=%{{x:.0%}}<br>C=%{{y:.0%}}<extra></extra>",
            ))
            _idx = int(np.argmax(_C >= 0.91))
            if _mask[_idx]:
                fig.add_annotation(x=_pos_iso[_idx], y=_C[_idx],
                                   text=f"{_pg_lv:.0%}", showarrow=False,
                                   font=dict(size=9, color=_ic),
                                   xanchor="left", yanchor="middle", xshift=3)

    fig.add_trace(go.Scatter(
        x=_pos_min, y=_C, mode="lines",
        line=dict(color="rgba(25,80,170,0.65)", width=1.6, dash="dot"),
        name="Min POS (S_for=0)",
        hovertemplate="C=%{y:.0%}<br>Min POS=%{x:.0%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=_pos_max, y=_C, mode="lines",
        line=dict(color="rgba(25,80,170,0.65)", width=1.6, dash="dash"),
        name="Max POS (S_for=C)",
        hovertemplate="C=%{y:.0%}<br>Max POS=%{x:.0%}<extra></extra>",
    ))

    _grn_mask = _pos_grn < _pos_max - 1e-4
    _red_mask = _pos_red > _pos_min + 1e-4
    fig.add_trace(go.Scatter(
        x=_pos_grn[_grn_mask], y=_C[_grn_mask], mode="lines",
        line=dict(color="rgba(0,130,50,0.90)", width=2),
        name=f"Pg = g ({_g_th:.0%})", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=_pos_red[_red_mask], y=_C[_red_mask], mode="lines",
        line=dict(color="rgba(175,30,30,0.90)", width=2),
        name=f"Pg = r ({_r_th:.0%})", hoverinfo="skip",
    ))

    fig.add_annotation(x=(_g_th + 1.0) * 0.5, y=0.88, text="Positive",
                       showarrow=False, font=dict(color="rgba(0,120,45,0.80)", size=13))
    fig.add_annotation(x=_r_th * 0.5, y=0.88, text="Negative",
                       showarrow=False, font=dict(color="rgba(170,30,30,0.80)", size=13))

    # ── Post-DFI headline shift overlay (Plan B / B3) ──────────────────────────
    # The CAM is prior-by-design, so this is an opt-in reference: two vertical lines
    # at the prospect-level P(G, ESL) before and after the DFI update, showing which
    # zone the headline lands in pre vs post.
    if dfi_overlay is not None:
        _pri_pos, _post_pos = float(dfi_overlay[0]), float(dfi_overlay[1])
        _show_dfi = st.checkbox(
            "Show post-DFI headline shift", value=True, key="cam_scatter_dfi_shift",
            help="Vertical lines at the prospect P(G, ESL) before (prior) and after the "
                 "DFI update. The CAM itself stays the geological prior; this is a reference "
                 "overlay of the headline move.")
        if _show_dfi:
            _up = _post_pos >= _pri_pos
            _post_col = "rgba(20,120,70,0.95)" if _up else "rgba(180,40,30,0.95)"
            fig.add_vline(x=_pri_pos, line=dict(color="rgba(80,80,90,0.85)", width=1.6, dash="dot"),
                          annotation_text=f"prior P(G, ESL) {_pri_pos*100:.0f}%",
                          annotation_position="bottom", annotation_font_size=10)
            fig.add_vline(x=_post_pos, line=dict(color=_post_col, width=2.2),
                          annotation_text=f"posterior P(G | DFI, ESL) {_post_pos*100:.0f}%",
                          annotation_position="top", annotation_font_size=10)
            # Arrow from prior to post at mid-height to read direction at a glance.
            fig.add_annotation(x=_post_pos, y=0.5, ax=_pri_pos, ay=0.5,
                               xref="x", yref="y", axref="x", ayref="y",
                               showarrow=True, arrowhead=2, arrowsize=1.1,
                               arrowwidth=1.8, arrowcolor=_post_col, text="")

    def _yv(sf, sa):
        v = abs(float(sf) - float(sa)) if _use_eci else (float(sf) + float(sa))
        return max(v, 0.05) if _log_y else v

    def _mk_opacity(sf, sa):
        return max(0.25, min(1.0, 0.25 + 0.75 * (float(sf) + float(sa)))) if _opacity_by_c else 1.0

    def _err_x(pos, bel, pl):
        return dict(type="data", symmetric=False,
                    array=[max(0.0, pl - pos)], arrayminus=[max(0.0, pos - bel)],
                    thickness=1.2, width=4)

    for _cat, _elements in conditional.items():
        _disp = pillar_display.get(_cat, _cat)
        _col = CAT_COLORS_COND.get(_cat, "#9ca3af")
        _sym_c = _sym.get(_cat, "circle")
        _xs, _ys, _hovers, _texts, _opacities = [], [], [], [], []
        _bel_arr, _pl_arr, _pos_arr = [], [], []
        for _i, _elem in enumerate(_elements):
            _eid = f"cond|{_cat}|{_i}"
            if leaf_filter is not None and _eid not in leaf_filter:
                continue
            _sf = float(_elem["support_for"])
            _sa = float(_elem["support_against"])
            _pos = policy_pos(_sf, _sa, w)
            _sc = (_elem.get("success_criteria", "") or _elem.get("label", ""))[:55]
            _xs.append(_pos); _ys.append(_yv(_sf, _sa))
            _bel_arr.append(_sf); _pl_arr.append(1.0 - _sa); _pos_arr.append(_pos)
            _opacities.append(_mk_opacity(_sf, _sa))
            _hovers.append(
                f"<b>{_disp}</b><br>{_sc}<br>"
                f"POS: {_pos*100:.1f}%  Bel: {_sf*100:.1f}%  Pl: {(1-_sa)*100:.1f}%<br>"
                f"ECI: {abs(_sf-_sa)*100:.1f}%  C: {(_sf+_sa)*100:.1f}%"
            )
            _texts.append((_sc[:22] + "…") if len(_sc) > 22 else _sc)
        if not _xs:
            continue
        _tr_c: dict = dict(
            x=_xs, y=_ys,
            mode="markers+text" if show_labels else "markers",
            marker=dict(color=_col, symbol=_sym_c, size=11,
                        opacity=_opacities if _opacity_by_c else 1.0,
                        line=dict(color="#374151", width=1)),
            name=f"{_disp} (elements)",
            customdata=_hovers,
            hovertemplate="%{customdata}<extra></extra>",
            showlegend=True,
        )
        if _show_bel_pl and len(_xs) == 1:
            _tr_c["error_x"] = dict(type="data", symmetric=False,
                                    array=[max(0.0, _pl_arr[0] - _pos_arr[0])],
                                    arrayminus=[max(0.0, _pos_arr[0] - _bel_arr[0])],
                                    color=_col, thickness=1.2, width=4)
        elif _show_bel_pl:
            _tr_c["error_x"] = dict(type="data", symmetric=False,
                                    array=[max(0.0, pl - p) for pl, p in zip(_pl_arr, _pos_arr)],
                                    arrayminus=[max(0.0, p - b) for b, p in zip(_bel_arr, _pos_arr)],
                                    color=_col, thickness=1.2, width=4)
        if show_labels:
            _tr_c["text"] = _texts
            _tr_c["textposition"] = "top right"
            _tr_c["textfont"] = dict(size=8, color="#374151")
        fig.add_trace(go.Scatter(**_tr_c))

    for _cat, _el in play.items():
        if not isinstance(_el, dict) or "support_for" not in _el:
            continue
        _eid = f"play|{_cat}"
        if leaf_filter is not None and _eid not in leaf_filter:
            continue
        _disp = pillar_display.get(_cat, _cat)
        _col = pillar_colors.get(_cat, "#6b7280")
        _sf = float(_el["support_for"]); _sa = float(_el["support_against"])
        _pos = policy_pos(_sf, _sa, w)
        _hover = (f"<b>{_disp} — Play</b><br>"
                  f"POS: {_pos*100:.1f}%  Bel: {_sf*100:.1f}%  Pl: {(1-_sa)*100:.1f}%<br>"
                  f"ECI: {abs(_sf-_sa)*100:.1f}%  C: {(_sf+_sa)*100:.1f}%")
        _tr: dict = dict(
            x=[_pos], y=[_yv(_sf, _sa)],
            mode="markers+text" if show_labels else "markers",
            marker=dict(color=_col, symbol="diamond", size=18,
                        opacity=_mk_opacity(_sf, _sa),
                        line=dict(color="white", width=2)),
            name=f"{_disp} (Play)",
            customdata=[_hover],
            hovertemplate="%{customdata}<extra></extra>",
            showlegend=True,
        )
        if _show_bel_pl:
            _tr["error_x"] = {**_err_x(_pos, _sf, 1.0 - _sa), "color": _col, "thickness": 1.5, "width": 5}
        if show_labels:
            _tr["text"] = [_disp]; _tr["textposition"] = "top center"
            _tr["textfont"] = dict(size=10, color="#111827")
        fig.add_trace(go.Scatter(**_tr))

    for _cat, _res in conditional_results.items():
        _disp = pillar_display.get(_cat, _cat)
        _col = pillar_colors.get(_cat, "#6b7280")
        _sf = float(_res.get("for", 0.5)); _sa = float(_res.get("against", 0.1))
        _pos = policy_pos(_sf, _sa, w)
        _hover = (f"<b>{_disp} — Conditional agg.</b><br>"
                  f"POS: {_pos*100:.1f}%  Bel: {_sf*100:.1f}%  Pl: {(1-_sa)*100:.1f}%<br>"
                  f"ECI: {abs(_sf-_sa)*100:.1f}%  C: {(_sf+_sa)*100:.1f}%")
        _tr_a: dict = dict(
            x=[_pos], y=[_yv(_sf, _sa)],
            mode="markers+text" if show_labels else "markers",
            marker=dict(color="rgba(255,255,255,0)", symbol="star",
                        size=22, line=dict(color=_col, width=2.5)),
            name=f"{_disp} (Cond agg.)",
            customdata=[_hover],
            hovertemplate="%{customdata}<extra></extra>",
            showlegend=True,
        )
        if _show_bel_pl:
            _tr_a["error_x"] = {**_err_x(_pos, _sf, 1.0 - _sa), "color": _col, "thickness": 1.8, "width": 6}
        if show_labels:
            _tr_a["text"] = [f"⋆{_disp}"]; _tr_a["textposition"] = "bottom center"
            _tr_a["textfont"] = dict(size=9, color=_col)
        fig.add_trace(go.Scatter(**_tr_a))

    _t_sf = float(total_for); _t_sa = float(total_against)
    _t_pos = policy_pos(_t_sf, _t_sa, w)
    _t_hover = (f"<b>P(G, ESL)</b><br>"
                f"Policy P: {_t_pos*100:.1f}%  Bel: {_t_sf*100:.1f}%  Pl: {(1-_t_sa)*100:.1f}%<br>"
                f"ECI: {abs(_t_sf-_t_sa)*100:.1f}%  Commit: {(_t_sf+_t_sa)*100:.1f}%")
    _tr_tot: dict = dict(
        x=[_t_pos], y=[_yv(_t_sf, _t_sa)],
        mode="markers+text",
        marker=dict(color="#1a1a2e", symbol="star", size=28,
                    line=dict(color="white", width=1.5)),
        name="P(G, ESL)",
        customdata=[_t_hover],
        hovertemplate="%{customdata}<extra></extra>",
        showlegend=True,
        text=["P(G, ESL)"], textposition="top center",
        textfont=dict(size=11, color="#1a1a2e"),
    )
    if _show_bel_pl:
        _tr_tot["error_x"] = {**_err_x(_t_pos, _t_sf, 1.0 - _t_sa), "color": "#1a1a2e", "thickness": 2, "width": 7}
    fig.add_trace(go.Scatter(**_tr_tot))

    _y_title = "ECI = |S_for − S_against|" if _use_eci else "Commitment C = S_for + S_against"
    if _log_y:
        _y_ax = dict(title=_y_title, type="log",
                     range=[_math.log10(0.05), _math.log10(1.0)],
                     tickvals=[0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 1.00],
                     ticktext=["5%", "10%", "20%", "30%", "50%", "70%", "100%"],
                     gridcolor="#e5e7eb")
    else:
        _y_ax = dict(title=_y_title, range=[-0.02, 1.08],
                     tickformat=".0%", dtick=0.1, gridcolor="#e5e7eb")

    fig.update_layout(
        height=720,
        margin=dict(l=60, r=210, t=45, b=65),
        xaxis=dict(title="Probability of Success (POS)",
                   range=[1.02, -0.02], tickformat=".0%", dtick=0.1,
                   gridcolor="#e5e7eb"),
        yaxis=_y_ax,
        plot_bgcolor="white",
        legend=dict(orientation="v", font=dict(size=9),
                    yanchor="top", y=1.0, xanchor="left", x=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)
    _y_note = "ECI = |S_for − S_against|" if _use_eci else "Commitment C = S_for + S_against"
    st.caption(
        f"X: Policy P reversed (high confidence left) · Y: {_y_note}. "
        "Zones: green (Policy P ≥ g), red (Policy P ≤ r), white (uncertain). "
        "Blue envelope: feasible Policy P range for current stance w. "
        "Diamonds = play, shapes = conditional sub-elements, "
        "outline stars = conditional pillar aggregates, filled star = P(G, ESL). "
        "Green/red boundaries auto-initialised from element distribution; adjust with sliders."
    )
