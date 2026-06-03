"""Classic POS module — DERIVED OUTPUT ONLY. No input sliders.

All values computed from ESL sf/sa via policy_pos().
Pillar list, names and colours are read from st.session_state["active_risk_model"]
so the section always reflects the current risk model.
"""

from __future__ import annotations

import streamlit as st

from logic.pos_logic import classic_pos_product
from logic.pos_policy import policy_pos as _policy_pos, resolve_stance, get_active_pillars
from logic.esl_pipeline import (
    group_by_label,
    combine_classic_pos,
    CLASSIC_POS_OPERATOR_OPTIONS,
    ESL_TO_CLASSIC_RECOMMENDATION,
    DEFAULT_CLASSIC_POS_MODE,
    make_session_classic_mode_getter,
)
from logic.session_keys import SK
from components.adequacy_matrix import render_adequacy_matrix_reference
from components.calibration import render_calibration_anchor
from components.hierarchy_chart import render_classic_pos_hierarchy
from components.overview_table import render_overview_table

# Alias kept for local readability — same as canonical _policy_pos from pos_policy
_get_pillars = get_active_pillars


# ── Main render ───────────────────────────────────────────────────────────────

def render_classic_pos(models: dict | None = None) -> None:
    """P(G, Classic) detail tab — derived output only."""
    st.markdown(
        "<div style='background:#1e3a5f;color:#fff;padding:12px 16px;border-radius:6px;"
        "margin-bottom:4px;border-left:6px solid #3b82f6;'>"
        "<b>P(G, Classic) — derived from ESL evidence</b></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Derived from your ESL assessment — no input required here. "
        "Pre-existing ROSE/GeoX estimate? Enter it on Dashboard → Classic POS source."
    )

    with st.expander("📖 Coming from multiplicative risking? Read this first", expanded=False):
        st.markdown(
            "**Your P(G, Classic) number comes from the ESL assessment, not from separate sliders.**\n\n"
            "Policy P = S_for + w × White  \n"
            "where S_for = Support For, w = stance, White = uncommitted evidence.\n\n"
            "At w=0.5 with no counter-evidence: Policy P ≈ midpoint of the ESL interval.\n\n"
            "**Calibration check:** Compare your derived Policy P to the calibration ranges in the "
            "Reference Tables tab."
        )

    with st.expander("Chance Factor Adequacy Matrix — Reference", expanded=False):
        render_adequacy_matrix_reference()

    st.info(
        "**Chance Adequacy Matrix** — available per element in the **Play** and **Conditional** tabs. "
        "Click **▶ Assess** on any row to open the full evidence panel."
    )

    if models is None:
        models = st.session_state.get("models", {})
    play       = models.get("play", {})
    conditional = models.get("conditional", {})
    uw = resolve_stance()
    get_classic_mode = make_session_classic_mode_getter(st.session_state)

    if not play or not conditional:
        st.info("Complete the ESL assessment first. Values will appear here automatically.")
        return

    # ── Dynamic pillar list from active model ─────────────────────────────
    pillars = _get_pillars()
    n = len(pillars)

    # ── Play chance ───────────────────────────────────────────────────────
    st.subheader("P(Play) per pillar — derived from ESL Policy P")
    play_probs: list[float] = []
    play_bels:  list[float] = []
    play_pls:   list[float] = []
    play_cols = st.columns(max(n, 1))
    for i, pdef in enumerate(pillars):
        pid  = pdef["pillar_id"]
        dn   = pdef["display_name"]
        col  = pdef["color"]
        el   = play.get(pid, {})
        with play_cols[i]:
            if isinstance(el, dict) and "support_for" in el:
                elem_w = st.session_state.get(f"w_esl_play_{pid}", uw)
                sf, sa = el["support_for"], el["support_against"]
                p = _policy_pos(sf, sa, elem_w)
                play_probs.append(p)
                play_bels.append(sf)
                play_pls.append(1.0 - sa)
                st.markdown(
                    f"<div style='background:{col};padding:10px;border-radius:6px;"
                    f"text-align:center;'>",
                    unsafe_allow_html=True,
                )
                st.metric(dn, f"{p*100:.0f}%",
                          help=f"S(H)={sf:.2f}, S(¬H)={sa:.2f}, w={elem_w:.2f} | Bel={sf*100:.0f}% Pl={(1-sa)*100:.0f}%")
                st.markdown("</div>", unsafe_allow_html=True)
                render_calibration_anchor(pid, p)
            else:
                play_probs.append(1.0)
                play_bels.append(1.0)
                play_pls.append(1.0)

    play_chance = classic_pos_product(play_probs)

    # ── Conditional chance ─────────────────────────────────────────────────
    st.divider()
    st.subheader("P(Cond) per pillar — derived from ESL Policy P")
    cond_probs: list[float] = []
    cond_bels:  list[float] = []
    cond_pls:   list[float] = []

    for i, pdef in enumerate(pillars):
        pid = pdef["pillar_id"]
        dn  = pdef["display_name"]
        col = pdef["color"]
        elems = conditional.get(pid, [])
        if not elems:
            cond_probs.append(1.0)
            cond_bels.append(1.0)
            cond_pls.append(1.0)
            continue

        elem_prob_map: dict[int, float] = {
            id(e): _policy_pos(
                e["support_for"], e["support_against"],
                st.session_state.get(f"w_esl_cond_{pid}_{j}", uw),
            )
            for j, e in enumerate(elems)
        }
        elem_bel_map: dict[int, float] = {id(e): e["support_for"] for e in elems}
        elem_pl_map:  dict[int, float] = {id(e): 1.0 - e["support_against"] for e in elems}

        grouped = group_by_label(elems)
        group_results: list[float] = []
        group_bels:    list[float] = []
        group_pls:     list[float] = []
        for grp_label, grp_elems in grouped.items():
            classic_group_mode = get_classic_mode(SK.classic_group_mode(pid, grp_label))
            group_probs = [elem_prob_map[id(e)] for e in grp_elems]
            group_results.append(combine_classic_pos(group_probs, classic_group_mode))
            group_bels.append(combine_classic_pos([elem_bel_map[id(e)] for e in grp_elems], classic_group_mode))
            group_pls.append( combine_classic_pos([elem_pl_map[id(e)]  for e in grp_elems], classic_group_mode))

        classic_pillar_mode = get_classic_mode(SK.classic_mode(pid))
        pillar_cond = combine_classic_pos(group_results, classic_pillar_mode)
        cond_probs.append(pillar_cond)
        cond_bels.append(combine_classic_pos(group_bels, classic_pillar_mode))
        cond_pls.append( combine_classic_pos(group_pls,  classic_pillar_mode))

        with st.container(border=True):
            ng = len(grouped)
            nt = len(elems)
            st.markdown(
                f"<span style='background:{col};padding:2px 10px;border-radius:10px;"
                f"font-weight:700;font-size:0.85rem;'>{dn}</span> "
                f"— **{pillar_cond*100:.0f}%**  "
                f"<span style='font-size:0.75rem;color:#6b7280;'>"
                f"({ng} group{'s' if ng!=1 else ''}, {nt} element{'s' if nt!=1 else ''}"
                f" · pillar: {classic_pillar_mode})</span>",
                unsafe_allow_html=True,
            )
            for grp_label, grp_elems in grouped.items():
                grp_mode_disp = get_classic_mode(SK.classic_group_mode(pid, grp_label))
                grp_probs_disp = [elem_prob_map[id(e)] for e in grp_elems]
                grp_combined = combine_classic_pos(grp_probs_disp, grp_mode_disp)
                if len(grp_elems) == 1:
                    e = grp_elems[0]
                    pv = elem_prob_map[id(e)]
                    sc = (e.get("success_criteria", "") or "")[:60]
                    st.markdown(f"`{pv*100:.0f}%` — **{grp_label}**" + (f": {sc}" if sc else ""))
                else:
                    st.markdown(
                        f"`{grp_combined*100:.0f}%` — **{grp_label}** "
                        f"_({grp_mode_disp}, {len(grp_elems)} elements)_"
                    )
                    for e in grp_elems:
                        pv = elem_prob_map[id(e)]
                        sc = (e.get("success_criteria", "") or "")[:60]
                        st.markdown(f"  - `{pv*100:.0f}%` {sc}")

    cond_chance  = classic_pos_product(cond_probs)
    total_pos    = play_chance * cond_chance
    # Persist the derived total P(G, Classic) so the Dashboard's comparison table
    # picks it up. Without this write the comparison panel would show 0 until the
    # user manually entered ROSE values.
    st.session_state["comparison_classic_pos"] = total_pos

    # Compute Classic trajectory once for both downstream plots
    import plotly.graph_objects as go
    from components.prospect_hub import _compute_p_g_classic_trajectory
    _traj = _compute_p_g_classic_trajectory(models, n_steps=21)

    # ── 1. P(G, Classic) vs Uncertainty Index — stance trajectory ───────────
    # (Order matches the ESL Analysis tab: trajectory first, then pillar fan.)
    if _traj is not None:
        st.divider()
        with st.container(border=True):
            st.subheader("P(G, Classic) vs Uncertainty Index — stance trajectory")

            _ws_arr_ui     = _traj["ws"]
            _total_arr_ui  = _traj["total"]
            _per_pillar_ui = _traj["pillars"]

            # UI at each w using Classic per-pillar values
            _ui_traj: list[float] = []
            for _i in range(len(_ws_arr_ui)):
                _pgs_at_w = [_per_pillar_ui[_pid][_i] for _pid in _per_pillar_ui]
                _sorted_w = sorted(_pgs_at_w)
                if len(_sorted_w) < 2:
                    _ui_val = (_sorted_w[0] - (1 - _sorted_w[0])) if _sorted_w else 0.0
                else:
                    _ui_val = _sorted_w[0] + _sorted_w[1] - 1.0
                _ui_traj.append(_ui_val * 100)

            _traj_x_cl = [v * 100 for v in _total_arr_ui]
            _traj_y_cl = _ui_traj
            _idx_cur_cl = min(range(len(_ws_arr_ui)),
                              key=lambda i: abs(_ws_arr_ui[i] - uw))

            # ── Optional DFI posterior overlay ─────────────────────────
            _dfi_overlay_cls = None
            if st.session_state.get("dfi_enabled", False):
                try:
                    from types import SimpleNamespace
                    from logic.dfi_context import (
                        classic_prior_pillars_from_ctx as _classic_prior_pillars_from_ctx,
                        get_effective_calibration      as _get_effective_calibration,
                    )
                    from logic.dfi_bayes import compute_dfi_posterior
                    from logic.dfi_inputs import read_dfi_inputs
                    _ctx_shim = SimpleNamespace(
                        play=models.get("play", {}),
                        conditional=models.get("conditional", {}),
                        uncertainty_weight=uw,
                    )
                    _calib = _get_effective_calibration()
                    # NOTE: previously read dead keys (dfi_w_water / dfi_dhi_index) that
                    # were never written, so this Classic overlay silently ignored
                    # analyst input. Now reads the canonical DFI input bundle.
                    _inp = read_dfi_inputs(st.session_state)
                    _fw, _dhi, _sd_mode, _fluid = (_inp.fluid_weights, _inp.dhi,
                                                   _inp.sd_mode, _inp.fluid_type)
                    _post_traj_cls = []
                    for _w_v in _ws_arr_ui:
                        _ctx_shim.uncertainty_weight = float(_w_v)
                        _pc = _classic_prior_pillars_from_ctx(_ctx_shim, float(_w_v))
                        _pp = compute_dfi_posterior(_pc, _dhi, _calib, _fw, _sd_mode, _fluid)
                        _post_traj_cls.append(_pp.posterior_pg * 100)
                    _ctx_shim.uncertainty_weight = uw
                    _pc_cur = _classic_prior_pillars_from_ctx(_ctx_shim, uw)
                    _pp_cur = compute_dfi_posterior(_pc_cur, _dhi, _calib, _fw, _sd_mode, _fluid)
                    _dfi_overlay_cls = {
                        "traj_x": _post_traj_cls,
                        "current_x": _pp_cur.posterior_pg * 100,
                    }
                except Exception:
                    _dfi_overlay_cls = None

            from components.risk_summary import render_pg_ui_trajectory
            render_pg_ui_trajectory(
                traj_x=_traj_x_cl, traj_y=_traj_y_cl,
                ws=_ws_arr_ui,
                current_w=uw,
                current_x=_traj_x_cl[_idx_cur_cl],
                current_y=_traj_y_cl[_idx_cur_cl],
                method_label="Classic",
                dfi_overlay=_dfi_overlay_cls,
                extra_caption=(
                    "**Caveat:** when the recommended Classic operator (Min) is used for all groups, "
                    "the per-pillar P(pillar) values match the ESL method, so this trajectory looks "
                    "identical to the ESL UI trajectory in the Analysis tab. The two diverge only "
                    "when you pick a non-Min Classic operator (e.g. Product or Mean) at the "
                    "group/pillar level — in which case the difference between this curve and the "
                    "ESL one is itself a diagnostic of how much your operator choice changes the "
                    "diagnosis."
                ),
            )

    # ── 2. Pillar Fan Plot ─────────────────────────────────────────────────
    # Sweep stance w from 0 to 1 and show per-pillar trajectories alongside
    # the total P(G, Classic) — reveals which pillar dominates, how flat or
    # steep each is (data-uncertainty signal), and the compression effect of
    # the multiplicative chain.
    st.divider()
    with st.container(border=True):
        st.subheader("Pillar fan — P(pillar) and P(G, Classic) vs stance w")
        if _traj is not None:
            _ws_arr      = _traj["ws"]
            _total_arr   = _traj["total"]
            _per_pillar  = _traj["pillars"]
            _disp_map    = _traj["pillar_display"]
            _color_map   = _traj["pillar_color"]

            _fig_fan = go.Figure()

            # Per-pillar lines (thin, coloured)
            for _pid, _vals in _per_pillar.items():
                _disp = _disp_map.get(_pid, _pid)
                _col  = _color_map.get(_pid, "#6b7280")
                _fig_fan.add_trace(go.Scatter(
                    x=_ws_arr,
                    y=[v * 100 for v in _vals],
                    mode="lines",
                    line=dict(color=_col, width=2.2),
                    name=f"P({_disp})",
                    hovertemplate=f"<b>P({_disp})</b><br>w = %{{x:.2f}}<br>P = %{{y:.1f}}%<extra></extra>",
                ))

            # Total P(G, Classic) — thick black line on top
            _fig_fan.add_trace(go.Scatter(
                x=_ws_arr,
                y=[v * 100 for v in _total_arr],
                mode="lines",
                line=dict(color="#111827", width=4),
                name="<b>P(G, Classic)</b>",
                hovertemplate="<b>P(G, Classic)</b><br>w = %{x:.2f}<br>P = %{y:.1f}%<extra></extra>",
            ))

            # Current stance marker — vertical dashed line + star at total
            _cur_total_pct = total_pos * 100
            _fig_fan.add_vline(
                x=uw, line_width=1.5, line_dash="dash", line_color="#dc2626",
                annotation_text=f"current w = {uw:.2f}",
                annotation_position="top",
                annotation_font=dict(size=10, color="#dc2626"),
            )
            _fig_fan.add_trace(go.Scatter(
                x=[uw], y=[_cur_total_pct], mode="markers",
                marker=dict(symbol="star", size=20, color="#dc2626",
                            line=dict(color="white", width=2)),
                name="Current P(G, Classic)", showlegend=False,
                hovertemplate=(
                    f"<b>Current</b><br>w = {uw:.2f}<br>"
                    f"P(G, Classic) = {_cur_total_pct:.1f}%<extra></extra>"
                ),
            ))

            # Calibration reference at 50%
            _fig_fan.add_hline(
                y=50, line_width=1, line_dash="dot", line_color="#9ca3af",
                annotation_text="50%", annotation_position="right",
                annotation_font=dict(size=9, color="#6b7280"),
            )

            _fig_fan.update_layout(
                xaxis_title="Stance w  (0 = Bel · 1 = Pl)",
                yaxis_title="Probability (%)",
                xaxis=dict(range=[0, 1], dtick=0.1, tickformat=".2f"),
                yaxis=dict(range=[0, 100], dtick=10),
                height=560, margin=dict(t=40, b=120, l=50, r=20),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="top", y=-0.10,
                    xanchor="center", x=0.5,
                    font=dict(size=10),
                ),
            )
            st.plotly_chart(_fig_fan, use_container_width=True)
            st.caption(
                "Coloured lines = P(pillar) per pillar · black = P(G, Classic) = product of pillars · "
                "red dashed = current stance."
            )
            with st.expander("📖 Reading this plot", expanded=False):
                st.markdown(
                    "**Coloured lines:** each pillar's P(pillar) = P(pillar, Play) × P(pillar, Cond) "
                    "as the stance w sweeps from 0 (Bel — pessimistic) to 1 (Pl — optimistic).  \n"
                    "**Black line:** total P(G, Classic) = product of all pillar values.  \n"
                    "**Diagnostics:** the *flattest* line is your best-committed pillar (low white "
                    "space, stance barely matters); the *steepest* is your largest data gap. "
                    "The gap between the lowest pillar line and the black total line shows the "
                    "compression effect of multiplying probabilities."
                )

            # ── Numeric readout (Bel / current / Pl) ──────────────────────
            _idx0 = 0
            _idx1 = len(_ws_arr) - 1
            _idx_cur = min(range(len(_ws_arr)), key=lambda i: abs(_ws_arr[i] - uw))
            _rows = ""
            for _pid in _per_pillar:
                _disp = _disp_map.get(_pid, _pid)
                _vals = _per_pillar[_pid]
                _rows += (
                    f"<tr><td style='padding:3px 12px 3px 0;font-weight:600;'>{_disp}</td>"
                    f"<td style='padding:3px 12px;color:#7f1d1d;'>{_vals[_idx0]*100:.1f}%</td>"
                    f"<td style='padding:3px 12px;background:#fff7ed;'>"
                    f"<b>{_vals[_idx_cur]*100:.1f}%</b></td>"
                    f"<td style='padding:3px 12px;color:#14532d;'>{_vals[_idx1]*100:.1f}%</td></tr>"
                )
            # Total row
            _rows += (
                f"<tr style='border-top:1px solid #d1d5db;'>"
                f"<td style='padding:6px 12px 3px 0;font-weight:700;'>P(G, Classic)</td>"
                f"<td style='padding:6px 12px;color:#7f1d1d;'><b>{_total_arr[_idx0]*100:.1f}%</b></td>"
                f"<td style='padding:6px 12px;background:#fff7ed;'>"
                f"<b>{_total_arr[_idx_cur]*100:.1f}%</b></td>"
                f"<td style='padding:6px 12px;color:#14532d;'><b>{_total_arr[_idx1]*100:.1f}%</b></td></tr>"
            )
            with st.expander("📊 Range readout — Bel / current / Pl per pillar", expanded=False):
                st.markdown(
                    f"<table style='margin-top:6px;font-size:0.86rem;'>"
                    f"<thead><tr style='border-bottom:1px solid #d1d5db;'>"
                    f"<th style='text-align:left;padding:3px 12px 3px 0;'>Element</th>"
                    f"<th style='text-align:left;padding:3px 12px;color:#7f1d1d;'>Bel (w=0)</th>"
                    f"<th style='text-align:left;padding:3px 12px;'>Current (w={uw:.2f})</th>"
                    f"<th style='text-align:left;padding:3px 12px;color:#14532d;'>Pl (w=1)</th></tr></thead>"
                    f"<tbody>{_rows}</tbody></table>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("Trajectory unavailable — complete the ESL assessment first.")

    # ── Detail table + hierarchy ──────────────────────────────────────────
    with st.container(border=True):
        st.caption("Detailed Sub-element Risk Table")
        from components.detail_risk_table import render_detail_risk_table
        render_detail_risk_table("classic_pos", play, conditional, {}, uw, tab_key="cp")

    with st.container(border=True):
        st.caption("Combination hierarchy")
        render_classic_pos_hierarchy(play, conditional)

    # ── Overview table ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Risk Overview")
    pillars_data = [
        {
            "name":     pdef["display_name"],
            "play_pos": play_probs[i],
            "cond_pos": cond_probs[i],
            "play_bel": play_bels[i] if i < len(play_bels) else None,
            "play_pl":  play_pls[i]  if i < len(play_pls)  else None,
            "cond_bel": cond_bels[i] if i < len(cond_bels) else None,
            "cond_pl":  cond_pls[i]  if i < len(cond_pls)  else None,
        }
        for i, pdef in enumerate(pillars)
        if i < len(play_probs) and i < len(cond_probs)
    ]
    render_overview_table(
        "classic_pos",
        {
            "pillars":        pillars_data,
            "total_pos":      total_pos,
            "play_pos_pct":   play_chance * 100,
            "cond_pos_pct":   cond_chance * 100,
            "prospect_title": st.session_state.get("meta_title", "Prospect"),
            "meta_basin":     st.session_state.get("meta_basin", ""),
            "meta_analyst":   st.session_state.get("meta_analyst", ""),
            "meta_date":      st.session_state.get("meta_date", ""),
        },
    )
    st.metric("Play Chance × Conditional Prospect", f"{total_pos * 100:.1f}%",
              help=f"Play {play_chance*100:.0f}% × Cond {cond_chance*100:.0f}%")

    # Top 5 weakest risk elements (shared helper — same formatting as the ESL Analysis tab)
    st.divider()
    from components.risk_summary import render_top5_weakest
    _disp_for_top5 = {p["pillar_id"]: p["display_name"] for p in pillars}
    render_top5_weakest(conditional, uw, pillar_display=_disp_for_top5)

    # ── Sensitivity (Tornado) — shared helper with Classic-specific compute_total ──
    with st.container(border=True):
        st.caption("Sensitivity Analysis (Tornado) — P(G, Classic)")

        # Build Classic-specific compute_total callback for the shared helper.
        # Classic combination: Policy P per sub-element → Classic operator at group
        # then pillar level → ∏ pillar Policy P across pillars.
        def _compute_total_classic(override, w: float) -> float:
            # Per-pillar Play Policy P at stance w
            _play_p: dict[str, float] = {}
            for _pdef in pillars:
                _pid = _pdef["pillar_id"]
                _el = play.get(_pid, {})
                if isinstance(_el, dict) and "support_for" in _el:
                    _play_p[_pid] = _policy_pos(_el["support_for"], _el["support_against"], w)
                else:
                    _play_p[_pid] = 1.0

            # Apply play override if any
            if override is not None and override[0] == "play":
                _, _pid_ov, _sf_ov, _sa_ov = override
                _play_p[_pid_ov] = _policy_pos(_sf_ov, _sa_ov, w)

            # Per-pillar Cond Policy P at stance w (Classic operator combination)
            _cond_p: dict[str, float] = {}
            for _pdef in pillars:
                _pid = _pdef["pillar_id"]
                _elems = conditional.get(_pid, [])

                # Whole-cond override (Potential mode or Pillars+Cond)?
                if override is not None and override[0] == "cond_agg" and override[1] == _pid:
                    _, _, _sf_ov, _sa_ov = override
                    _cond_p[_pid] = _policy_pos(_sf_ov, _sa_ov, w)
                    continue

                # Single sub-element override (Actual mode)?
                _sub_override_idx = None
                _sub_override_p: float | None = None
                if override is not None and override[0] == "cond_sub" and override[1] == _pid:
                    _, _, _sub_override_idx, _sf_ov, _sa_ov = override
                    _sub_override_p = _policy_pos(_sf_ov, _sa_ov, w)

                if not _elems:
                    _cond_p[_pid] = 1.0
                    continue

                # Compute each sub-element's Policy P (with override if applicable)
                elem_p_map: dict[int, float] = {}
                for _j, _e in enumerate(_elems):
                    if _sub_override_idx is not None and _j == _sub_override_idx:
                        elem_p_map[id(_e)] = _sub_override_p
                    else:
                        elem_p_map[id(_e)] = _policy_pos(_e["support_for"], _e["support_against"], w)

                # Combine sub-elements within each group (Classic group operator), then
                # combine group results at the pillar level (Classic pillar operator).
                grouped = group_by_label(_elems)
                group_results = []
                for _grp_label, _grp_elems in grouped.items():
                    _grp_mode = get_classic_mode(SK.classic_group_mode(_pid, _grp_label))
                    _grp_probs = [elem_p_map[id(_ge)] for _ge in _grp_elems]
                    group_results.append(combine_classic_pos(_grp_probs, _grp_mode))
                _pil_mode = get_classic_mode(SK.classic_mode(_pid))
                _cond_p[_pid] = combine_classic_pos(group_results, _pil_mode)

            # Total = ∏ (play_p × cond_p) across pillars
            _pillar_chances = [_play_p[_pdef["pillar_id"]] * _cond_p[_pdef["pillar_id"]]
                               for _pdef in pillars]
            return classic_pos_product(_pillar_chances)

        from components.risk_summary import render_sensitivity_tornado
        render_sensitivity_tornado(
            method_label="Classic",
            play=play,
            conditional=conditional,
            uncertainty_weight=uw,
            compute_total=_compute_total_classic,
            pillar_display={p["pillar_id"]: p["display_name"] for p in pillars},
            include_cond_aggregate_in_pillars=True,
        )

    # ── Audit ──────────────────────────────────────────────────────────────
    st.divider()
    with st.container(border=True):
        st.caption("Assessment Sign-off & Audit Trail")
        from components.audit import render_audit_panel
        render_audit_panel(
            pos=total_pos,
            method="Classic POS",
            prospect_title=st.session_state.get("meta_title", "Prospect"),
        )
