"""Analysis tab render function."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from components.colors import lighten_hex
from components.render_helpers import (
    policy_pos,
    small_flag_html,
)
from components.prospect_hub import _get_esl_overview_data
from components.esl_analysis import (
    _render_esl_ratio_plot_and_validation,
    _render_cam_scatter_plot,
)
from logic.esl_pipeline import group_by_label, combine_with_mode
from logic.session_keys import SK


def _render_analysis_tab(ctx) -> None:
    """Render the Analysis tab.  Called by _render_tabs."""

    models = ctx.models
    play = ctx.play
    conditional = ctx.conditional
    r = ctx.rollup
    total_for = ctx.total_for
    total_against = ctx.total_against
    play_for = ctx.play_for
    play_against = ctx.play_against
    conditional_for = ctx.conditional_for
    conditional_against = ctx.conditional_against
    conditional_results = ctx.conditional_results
    uncertainty_weight = ctx.uncertainty_weight
    prospect_title = ctx.prospect_title
    get_mode = ctx.get_mode
    get_dependency = ctx.get_dependency
    _active_model_ref = ctx.active_model
    _pillar_colors = ctx.pillar_colors
    _pillar_display = ctx.pillar_display
    ESL_OPTIONS = MODE_OPTIONS = ctx.esl_options

    # Tab-level scope note: this tab analyses the GEOLOGICAL chance P(G) / gPOS.
    st.markdown(
        "<div style='background:#f0f9ff;border-left:4px solid #0ea5e9;"
        "padding:8px 14px;border-radius:6px;margin-bottom:10px;'>"
        "<b>Geological chance analysis — P(G)</b> "
        "<span style='font-size:0.85rem;color:#475569;'>(a.k.a. <i>Pg</i> / geological POS, gPOS). "
        "Everything on this tab characterises the <b>geological prior</b> probability "
        "of success and its uncertainty <i>before</i> any DFI/seismic update. "
        "ESL values appear as <b>P(G, ESL)</b>; the Classic product as <b>P(G, Classic)</b>. "
        "The DFI-conditioned posterior P(G | DFI) lives on the <b>Bayesian DFI Update</b> "
        "tab; the reportable result is on the <b>Final Prospect POS</b> tab.</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Risk Overview
    _ov = _get_esl_overview_data(models)
    if _ov:
        from components.overview_table import render_overview_table
        st.subheader("Risk Overview — geological prior P(G, ESL)")
        render_overview_table("esl", _ov)
        st.divider()

    # ── Uncertainty Index as an ESL-derived range ────────────────────────────
    # For each pillar compute three P(pillar) values:
    #   point = Policy P at current stance w (= classical UI input)
    #   bel   = S_for product  (w=0 — all white votes against, lower bound)
    #   pl    = 1 − S_against product  (w=1 — all white votes for, upper bound)
    # Then derive UI three times and present the range.
    _pillar_pg_point: dict[str, float] = {}
    _pillar_pg_bel:   dict[str, float] = {}
    _pillar_pg_pl:    dict[str, float] = {}
    for _pid_ui in r.pillar_for:
        _dn_ui = _pillar_display.get(_pid_ui, _pid_ui)
        _pf_ui = r.pillar_for[_pid_ui]      # play S_for
        _pa_ui = r.pillar_against[_pid_ui]  # play S_against
        _cr_ui = conditional_results.get(_pid_ui, {"for": 0.5, "against": 0.1})
        _cf_ui = _cr_ui["for"]       # cond S_for (aggregated)
        _ca_ui = _cr_ui["against"]   # cond S_against (aggregated)
        _pillar_pg_point[_dn_ui] = (
            policy_pos(_pf_ui, _pa_ui, uncertainty_weight)
            * policy_pos(_cf_ui, _ca_ui, uncertainty_weight)
        )
        _pillar_pg_bel[_dn_ui] = _pf_ui * _cf_ui                       # Bel(pillar)
        _pillar_pg_pl[_dn_ui]  = (1.0 - _pa_ui) * (1.0 - _ca_ui)       # Pl(pillar)

    def _ui_from(pgs: dict[str, float]) -> float:
        s = sorted(pgs.values())
        if len(s) < 2:
            return (s[0] - (1 - s[0])) if s else 0.0
        return s[0] + s[1] - 1.0   # = min + 2nd_min − 1 = min − (1 − 2nd_min)

    _ui_point = _ui_from(_pillar_pg_point)
    _ui_low   = _ui_from(_pillar_pg_bel)    # pessimistic UI (all unknowns against)
    _ui_high  = _ui_from(_pillar_pg_pl)     # optimistic UI (all unknowns for)
    _ui_pct        = _ui_point * 100
    _ui_low_pct    = _ui_low   * 100
    _ui_high_pct   = _ui_high  * 100

    st.subheader("Risk Summary: Uncertainty Index & Key Drivers")

    # ── Stance trajectory sweep: 21 points w = 0.00 … 1.00 ──────────────────
    # At each w, compute (P(G, ESL), UI) for the prospect. The curve passes
    # through the current point and shows the defensible trajectory.
    _pillar_masses = []   # list of (play_for, play_against, cond_for, cond_against)
    for _pid_sw in r.pillar_for:
        _cr_sw = conditional_results.get(_pid_sw, {"for": 0.5, "against": 0.1})
        _pillar_masses.append((
            r.pillar_for[_pid_sw],
            r.pillar_against[_pid_sw],
            _cr_sw["for"],
            _cr_sw["against"],
        ))

    _ws_sweep = np.linspace(0.0, 1.0, 21)
    _traj_pg: list[float] = []
    _traj_ui: list[float] = []
    for _w_val in _ws_sweep:
        _pg_w = (total_for + _w_val * (1 - total_for - total_against)) * 100
        _pillar_pgs_w = []
        for _pf, _pa, _cf, _ca in _pillar_masses:
            _pl_play = _pf + _w_val * max(0.0, 1 - _pf - _pa)
            _pl_cond = _cf + _w_val * max(0.0, 1 - _cf - _ca)
            _pillar_pgs_w.append(_pl_play * _pl_cond)
        _sorted_w = sorted(_pillar_pgs_w)
        if len(_sorted_w) < 2:
            _ui_w_val = (_sorted_w[0] - (1 - _sorted_w[0])) if _sorted_w else 0.0
        else:
            _ui_w_val = _sorted_w[0] + _sorted_w[1] - 1.0
        _traj_pg.append(_pg_w)
        _traj_ui.append(_ui_w_val * 100)

    _cur_pg_pct = policy_pos(total_for, total_against, uncertainty_weight) * 100
    _cur_ui_pct = _ui_pct

    # ── ESL theoretical envelopes (analytical upper & lower) ───────────────
    from components.risk_summary import (
        render_pg_ui_trajectory, render_top5_weakest,
        compute_esl_envelope_analytical,
    )
    _n_pillars = len(r.pillar_for)
    _esl_envelope_curves = compute_esl_envelope_analytical(
        n_pillars=_n_pillars, w=uncertainty_weight,
    )
    _esl_envelope = {
        "curves": [
            {"x": c["x"].tolist(), "y": c["y"].tolist(),
             "name": c["name"], "color": c["color"],
             "dash": c["dash"], "width": c["width"]}
            for c in _esl_envelope_curves
        ],
    }

    # ── Optional DFI posterior overlay ─────────────────────────────────────
    _dfi_overlay_esl = None
    if st.session_state.get("dfi_enabled", False):
        try:
            from logic.dfi_context import (
                esl_prior_pillars_from_ctx_at_w as _esl_prior_pillars_from_ctx_at_w,
                esl_rollup_prior_at_w           as _esl_rollup_prior_at_w,
                get_effective_calibration       as _get_effective_calibration,
            )
            from logic.dfi_bayes import compute_dfi_posterior
            from logic.dfi_inputs import read_dfi_inputs
            _calib = _get_effective_calibration()
            # NOTE: previously read dead keys (dfi_w_water / dfi_dhi_index) that were
            # never written, so this overlay silently ignored analyst input. Now reads
            # the canonical bundle, so it tracks the DFI Setup tab.
            _inp = read_dfi_inputs(st.session_state)
            _fw, _dhi, _sd_mode, _fluid = (_inp.fluid_weights, _inp.dhi,
                                           _inp.sd_mode, _inp.fluid_type)
            _post_traj = []
            for _w_v in _ws_sweep:
                _pe = _esl_prior_pillars_from_ctx_at_w(ctx, float(_w_v))
                _pp = compute_dfi_posterior(
                    _pe, _dhi, _calib, _fw, _sd_mode, _fluid,
                    prior_pg_override=_esl_rollup_prior_at_w(ctx, float(_w_v)),
                )
                _post_traj.append(_pp.posterior_pg * 100)
            _pe_cur  = _esl_prior_pillars_from_ctx_at_w(ctx, uncertainty_weight)
            _pp_cur  = compute_dfi_posterior(
                _pe_cur, _dhi, _calib, _fw, _sd_mode, _fluid,
                prior_pg_override=_esl_rollup_prior_at_w(ctx, uncertainty_weight),
            )
            _dfi_overlay_esl = {
                "traj_x": _post_traj,
                "current_x": _pp_cur.posterior_pg * 100,
            }
        except Exception:
            _dfi_overlay_esl = None

    render_pg_ui_trajectory(
        traj_x=_traj_pg, traj_y=_traj_ui,
        ws=_ws_sweep.tolist(),
        current_w=uncertainty_weight,
        current_x=_cur_pg_pct, current_y=_cur_ui_pct,
        method_label="ESL",
        envelope_data=_esl_envelope,
        dfi_overlay=_dfi_overlay_esl,
        extra_caption=(
            f"**Theoretical envelopes** ({_n_pillars}-pillar, exact). "
            f"Dark-grey dashed curve `UI = 2·x^(1/{_n_pillars}) − 1` is the upper bound "
            "(all pillars equal, no white). "
            "Grey curves are the analytical lower bounds at w ∈ {0, 0.10, 0.25, 0.50, 0.75, 0.90, 1} — "
            "two weakest pillars carry all uncertainty, rest committed-positive. "
            "Each lower curve's vertex sits at `(x = w, UI = 2w − 1)` on the diagonal. "
            "At w = 0 and w = 1 the lower bound collapses to the Classic Rose bound `UI = 2·√x − 1`. "
            "The trajectory star must lie inside the envelope at its current stance."
        ),
    )

    # ── Pillar fan — P(pillar, ESL) and P(G, ESL) vs stance w ──────────────
    st.divider()
    with st.container(border=True):
        st.subheader("Pillar fan — P(pillar, ESL) and P(G, ESL) vs stance w")

        _ws_fan = np.linspace(0.0, 1.0, 51)  # smooth curve

        _fig_fan_esl = go.Figure()

        # ── Per-pillar curves (quadratic in w) ──
        for _pid_fan in r.pillar_for:
            _disp_fan = _pillar_display.get(_pid_fan, _pid_fan)
            _col_fan  = _pillar_colors.get(_pid_fan, "#6b7280")
            _sf_play  = r.pillar_for[_pid_fan]
            _sa_play  = r.pillar_against[_pid_fan]
            _cr_fan   = conditional_results.get(_pid_fan, {"for": 0.5, "against": 0.1})
            _sf_cond  = _cr_fan["for"]
            _sa_cond  = _cr_fan["against"]
            _white_play = max(0.0, 1.0 - _sf_play - _sa_play)
            _white_cond = max(0.0, 1.0 - _sf_cond - _sa_cond)

            _p_play_w  = _sf_play + _ws_fan * _white_play
            _p_cond_w  = _sf_cond + _ws_fan * _white_cond
            _p_pil_w   = _p_play_w * _p_cond_w

            _bel_pil = _sf_play * _sf_cond
            _pl_pil  = (1.0 - _sa_play) * (1.0 - _sa_cond)

            # Quadratic curve
            _fig_fan_esl.add_trace(go.Scatter(
                x=_ws_fan, y=_p_pil_w * 100,
                mode="lines",
                line=dict(color=_col_fan, width=2.2),
                name=f"P({_disp_fan}, ESL)",
                hovertemplate=(
                    f"<b>P({_disp_fan}, ESL)</b><br>w = %{{x:.2f}}<br>"
                    "P = %{y:.1f}%<extra></extra>"
                ),
            ))
            # Bel / Pl tick markers at endpoints
            _fig_fan_esl.add_trace(go.Scatter(
                x=[0.0, 1.0],
                y=[_bel_pil * 100, _pl_pil * 100],
                mode="markers",
                marker=dict(symbol="circle-open", size=10, color=_col_fan,
                            line=dict(color=_col_fan, width=2)),
                showlegend=False,
                customdata=[f"Bel({_disp_fan})", f"Pl({_disp_fan})"],
                hovertemplate="<b>%{customdata}</b><br>P = %{y:.1f}%<extra></extra>",
            ))

        # ── Total P(G, ESL) — LINEAR in w (mass-product then Policy P once) ──
        _p_g_esl_w = total_for + _ws_fan * (1.0 - total_for - total_against)
        _fig_fan_esl.add_trace(go.Scatter(
            x=_ws_fan, y=_p_g_esl_w * 100,
            mode="lines",
            line=dict(color="#111827", width=4),
            name="<b>P(G, ESL)</b>",
            hovertemplate="<b>P(G, ESL)</b><br>w = %{x:.2f}<br>P = %{y:.1f}%<extra></extra>",
        ))
        # Bel(G) / Pl(G) tick markers
        _bel_g = total_for
        _pl_g  = 1.0 - total_against
        _fig_fan_esl.add_trace(go.Scatter(
            x=[0.0, 1.0], y=[_bel_g * 100, _pl_g * 100],
            mode="markers",
            marker=dict(symbol="circle-open", size=12, color="#111827",
                        line=dict(color="#111827", width=2.5)),
            showlegend=False,
            customdata=["Bel(G)", "Pl(G)"],
            hovertemplate="<b>%{customdata}</b><br>P = %{y:.1f}%<extra></extra>",
        ))

        # Current stance marker
        _cur_w_fan    = uncertainty_weight
        _cur_total_w  = total_for + _cur_w_fan * (1.0 - total_for - total_against)
        _fig_fan_esl.add_vline(
            x=_cur_w_fan, line_width=1.5, line_dash="dash", line_color="#dc2626",
            annotation_text=f"current w = {_cur_w_fan:.2f}",
            annotation_position="top",
            annotation_font=dict(size=10, color="#dc2626"),
        )
        _fig_fan_esl.add_trace(go.Scatter(
            x=[_cur_w_fan], y=[_cur_total_w * 100], mode="markers",
            marker=dict(symbol="star", size=20, color="#dc2626",
                        line=dict(color="white", width=2)),
            name="Current P(G, ESL)", showlegend=False,
            hovertemplate=(
                f"<b>Current</b><br>w = {_cur_w_fan:.2f}<br>"
                f"P(G, ESL) = {_cur_total_w*100:.1f}%<extra></extra>"
            ),
        ))

        # 50% calibration reference
        _fig_fan_esl.add_hline(
            y=50, line_width=1, line_dash="dot", line_color="#9ca3af",
            annotation_text="50%", annotation_position="right",
            annotation_font=dict(size=9, color="#6b7280"),
        )

        _fig_fan_esl.update_layout(
            xaxis_title="Stance w  (0 = Bel, 1 = Pl)",
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
        st.plotly_chart(_fig_fan_esl, use_container_width=True)
        st.caption(
            "Coloured lines = P(pillar, ESL) per pillar (quadratic in w). "
            "Black line = P(G, ESL) — straight, because ESL applies Policy P once at the end. "
            "○ = pillar Bel/Pl endpoints · red dashed = current stance."
        )
        with st.expander("📖 Reading this plot", expanded=False):
            st.markdown(
                "**Coloured lines:** each pillar's P(pillar, ESL) = Policy P(Play, w) × Policy P(Cond, w), "
                "where Cond uses the ESL-aggregated mass pair across that pillar's sub-elements. "
                "These curves are **quadratic in w** (product of two linear Policy P factors).  \n"
                "**Black line:** total P(G, ESL, w) — a **straight line**, because ESL combines "
                "(S_for, S_against) masses across pillars first and applies Policy P only once at the end.  \n"
                "**○ markers** at w=0 and w=1 mark each pillar's Bel and Pl (defensible endpoints).  \n"
                "**Diagnostic:** the linear total is ESL's geometric signature — contrast with the Classic POS "
                "fan where the total is a curved polynomial. The total does **NOT** equal the product of "
                "per-pillar curves (that would be the Classic combination, not ESL)."
            )

    st.divider()
    render_top5_weakest(conditional, uncertainty_weight, pillar_display=_pillar_display)

    st.divider()

    # Risk Element Hierarchy
    def _shorten(_text: str, _max_len: int, _suffix: str = "") -> str:
        if not _text:
            return _suffix.strip()
        _full = _text + _suffix
        if len(_full) <= _max_len:
            return _full
        _cut = _text[: _max_len - len(_suffix) - 1]
        _sp = _cut.rfind(" ")
        if _sp > _max_len // 2:
            _cut = _cut[:_sp]
        return (_cut.rstrip(" -") + "…" + _suffix) if _cut else (_text[: _max_len - len(_suffix) - 1] + "…" + _suffix)

    def _build_icicle():
        _ids, _labels, _parents, _values, _colors, _hovers = [], [], [], [], [], []

        def _add(_id, _lbl, _par, _val, _col, _hover=None):
            _ids.append(_id); _labels.append(_lbl); _parents.append(_par)
            _values.append(max(0.01, _val)); _colors.append(_col)
            _hovers.append(_hover or _lbl)

        _total_pv = policy_pos(total_for, total_against, uncertainty_weight)
        _add("Total", f"Total Prospect  {_total_pv*100:.0f}%", "", 1.0, "#374151",
             f"<b>Total Prospect</b><br>Pg: {_total_pv*100:.0f}%")

        if not _active_model_ref:
            return _ids, _labels, _parents, _values, _colors, _hovers

        _rt_lookup: dict = {}
        for _pid_rt, _elems_rt in conditional.items():
            for _e_rt in (_elems_rt if isinstance(_elems_rt, list) else []):
                if "node_id" in _e_rt:
                    _rt_lookup[_e_rt["node_id"]] = _e_rt

        for _pillar in _active_model_ref.pillars:
            _pid = _pillar.pillar_id
            _pcol = _pillar.color or "#6b7280"
            _pcol_cond = lighten_hex(_pcol, 0.38)
            _pcol_grp = lighten_hex(_pcol, 0.55)
            _pcol_elem = lighten_hex(_pcol, 0.70)

            _play_rt = play.get(_pid, {})
            if isinstance(_play_rt, dict) and "support_for" in _play_rt:
                _w_pl = float(st.session_state.get(f"w_esl_play_{_pid}", uncertainty_weight))
                _play_pv = policy_pos(float(_play_rt["support_for"]),
                                      float(_play_rt["support_against"]), _w_pl)
                _play_sc = (_play_rt.get("success_criteria") or
                            _pillar.play.success_criteria or "")[:60]
            else:
                _play_pv = policy_pos(_pillar.play.default_s_n,
                                      _pillar.play.default_s_neg, uncertainty_weight)
                _play_sc = (_pillar.play.success_criteria or "")[:60]

            _add(
                f"Play/{_pid}",
                f"{_pillar.display_name} (Play)  {_play_pv*100:.0f}%",
                "Total", _play_pv, _pcol,
                f"<b>{_pillar.display_name} — Play</b><br>{_play_sc}<br>POS: {_play_pv*100:.0f}%",
            )

            _cr = conditional_results.get(_pid, {
                "for": _pillar.play.default_s_n,
                "against": _pillar.play.default_s_neg,
            })
            _cond_pv = policy_pos(_cr["for"], _cr["against"], uncertainty_weight)
            _add(
                f"Cond/{_pid}",
                f"{_pillar.display_name} (Cond)  {_cond_pv*100:.0f}%",
                f"Play/{_pid}", _cond_pv, _pcol_cond,
                (f"<b>{_pillar.display_name} — Conditional</b><br>"
                 f"Operator: {_pillar.conditional_operator}<br>POS: {_cond_pv*100:.0f}%"),
            )

            for _gi, _grp in enumerate(_pillar.conditional_groups):
                _gid = f"Cond/{_pid}/G{_gi}"
                _elem_pvs: list[float] = []
                for _elem in _grp.elements:
                    _rt = _rt_lookup.get(_elem.node_id)
                    if _rt:
                        _ep = policy_pos(float(_rt["support_for"]),
                                         float(_rt["support_against"]),
                                         uncertainty_weight)
                    else:
                        _ep = policy_pos(_elem.default_s_n,
                                         _elem.default_s_neg,
                                         uncertainty_weight)
                    _elem_pvs.append(_ep)

                _grp_pv = min(_elem_pvs) if _elem_pvs else 0.5

                if len(_grp.elements) == 1:
                    _elem = _grp.elements[0]
                    _sc = (_elem.success_criteria or _elem.name)[:60]
                    _add(
                        _gid,
                        f"{_grp.group_label}  {_elem_pvs[0]*100:.0f}%",
                        f"Cond/{_pid}", _elem_pvs[0], _pcol_grp,
                        f"<b>{_grp.group_label}</b><br>{_sc}<br>POS: {_elem_pvs[0]*100:.0f}%",
                    )
                else:
                    _add(
                        _gid,
                        f"{_grp.group_label}  {_grp_pv*100:.0f}%",
                        f"Cond/{_pid}", _grp_pv, _pcol_grp,
                        (f"<b>Group: {_grp.group_label}</b><br>"
                         f"Operator: {_grp.aggregation_rule}<br>POS: {_grp_pv*100:.0f}%"),
                    )
                    for _ei, (_elem, _ep) in enumerate(zip(_grp.elements, _elem_pvs)):
                        _sc = (_elem.success_criteria or _elem.name)[:60]
                        _add(
                            f"{_gid}/E{_ei}",
                            f"{_sc}  {_ep*100:.0f}%",
                            _gid, _ep, _pcol_elem,
                            f"<b>{_elem.name}</b><br>{_sc}<br>POS: {_ep*100:.0f}%",
                        )

        return _ids, _labels, _parents, _values, _colors, _hovers

    def _build_merged_hierarchy() -> tuple:
        _mids, _mlbls, _mpars, _mvals, _mcolors, _mhovers = [], [], [], [], [], []

        def _madd(_id, _lbl, _par, _val, _col, _hover=None):
            _mids.append(_id); _mlbls.append(_lbl); _mpars.append(_par)
            _mvals.append(max(0.01, _val)); _mcolors.append(_col)
            _mhovers.append(_hover or _lbl)

        _total_pv = policy_pos(total_for, total_against, uncertainty_weight)
        _madd("Total", f"Total  {_total_pv*100:.0f}%", "", 1.0, "#374151",
              f"<b>Total Prospect</b><br>Pg: {_total_pv*100:.0f}%")

        for _cat, _elems in conditional.items():
            _disp = _pillar_display.get(_cat, _cat)
            _pcol = _pillar_colors.get(_cat, "#6b7280")
            _pcol_cond = lighten_hex(_pcol, 0.38)
            _pcol_elem = lighten_hex(_pcol, 0.60)

            _play_rt = play.get(_cat, {})
            if isinstance(_play_rt, dict) and "support_for" in _play_rt:
                _play_pv = policy_pos(float(_play_rt["support_for"]),
                                      float(_play_rt["support_against"]), uncertainty_weight)
            else:
                _play_pv = 0.5

            _cr = conditional_results.get(_cat, {"for": 0.5, "against": 0.1})
            _cond_pv = policy_pos(_cr["for"], _cr["against"], uncertainty_weight)

            _merged = _play_pv * _cond_pv
            _hover_pillar = (
                f"<b>{_disp}</b><br>"
                f"Pg = Play × Cond = {_play_pv*100:.0f}% × {_cond_pv*100:.0f}% = {_merged*100:.0f}%"
            )
            _madd(f"Pillar/{_cat}", f"{_disp}  {_merged*100:.0f}%",
                  "Total", _merged, _pcol, _hover_pillar)

            _grouped = group_by_label(_elems)
            for _gi, (_glbl, _gelems) in enumerate(_grouped.items()):
                _safe = (_glbl.replace("/", "_").replace(" ", "_")[:40]) or f"G{_gi}"
                _gid = f"Pillar/{_cat}/{_safe}"

                if len(_gelems) == 1:
                    _e = _gelems[0]
                    _ep = policy_pos(float(_e["support_for"]),
                                     float(_e["support_against"]), uncertainty_weight)
                    _sc = _e.get("success_criteria", "")
                    _madd(_gid, f"{_glbl}  {_ep*100:.0f}%",
                          f"Pillar/{_cat}", _ep, _pcol_cond,
                          f"<b>{_glbl}</b><br>{_sc[:80]}<br>POS: {_ep*100:.0f}%" if _sc
                          else f"<b>{_glbl}</b><br>POS: {_ep*100:.0f}%")
                else:
                    _gf, _ga = combine_with_mode(
                        _gelems,
                        get_mode(SK.esl_group_mode(_cat, _glbl)),
                        get_dependency(SK.esl_group_dependency(_cat, _glbl)),
                    )
                    _grp_pv = policy_pos(_gf, _ga, uncertainty_weight)
                    _madd(_gid, f"{_glbl}  {_grp_pv*100:.0f}%",
                          f"Pillar/{_cat}", _grp_pv, _pcol_cond,
                          f"<b>Group: {_glbl}</b><br>POS: {_grp_pv*100:.0f}%")
                    for _ei, _e in enumerate(_gelems):
                        _ep = policy_pos(float(_e["support_for"]),
                                         float(_e["support_against"]), uncertainty_weight)
                        _sc = _e.get("success_criteria", "") or _e.get("label", "")
                        _madd(f"{_gid}/E{_ei}", f"{_sc[:50]}  {_ep*100:.0f}%",
                              _gid, _ep, _pcol_elem,
                              f"<b>{_e.get('label','')}</b><br>{_sc[:80]}<br>POS: {_ep*100:.0f}%")

        return _mids, _mlbls, _mpars, _mvals, _mcolors, _mhovers

    st.divider()
    st.subheader("Risk Element Hierarchy")
    _hier_col1, _hier_col2 = st.columns([2, 1])
    with _hier_col1:
        _chart_type = st.radio(
            "Chart type",
            options=["Horizontal icicle", "Vertical icicle", "Sunburst"],
            horizontal=True,
            key="hierarchy_chart_type",
            help=(
                "Horizontal icicle: root left → leaves right. "
                "Vertical icicle: root top → leaves down (original). "
                "Sunburst: radial / ring layout."
            ),
        )
    with _hier_col2:
        _merge_play_cond = st.toggle(
            "Merge Play × Conditional",
            value=False,
            key="hierarchy_merge_play_cond",
            help=(
                "OFF: shows Play and Conditional as separate levels. "
                "ON: collapses each pillar into one node at Pg = Play × Cond, "
                "then shows conditional sub-elements underneath."
            ),
        )

    if _merge_play_cond:
        _h_ids, _h_labels, _h_parents, _h_values, _h_colors, _h_hover = _build_merged_hierarchy()
        _hier_caption = (
            "Merged view: each pillar Pg = Play_POS × Cond_POS. "
            "Sub-elements are the conditional risk factors. Hover for details."
        )
    else:
        _h_ids, _h_labels, _h_parents, _h_values, _h_colors, _h_hover = _build_icicle()
        _hier_caption = (
            "Expanded view: Play and Conditional are separate levels. "
            "Block sizes reflect Estimated POS. Hover for details. "
            "Labels hidden when tile is too small — hover to read."
        )

    _font_kwargs = dict(
        textfont=dict(size=13, family="'Segoe UI', Arial, sans-serif"),
        insidetextfont=dict(size=13, family="'Segoe UI', Arial, sans-serif"),
        outsidetextfont=dict(size=11, family="'Segoe UI', Arial, sans-serif"),
    )
    _common_trace = dict(
        ids=_h_ids, labels=_h_labels, parents=_h_parents, values=_h_values,
        marker=dict(colors=_h_colors, line=dict(width=1.5, color="white")),
        maxdepth=5,
        textinfo="label",
        customdata=_h_hover,
        hovertemplate="%{customdata}<extra></extra>",
    )

    if _chart_type == "Vertical icicle":
        _fig_hier = go.Figure(go.Icicle(
            **_common_trace, **_font_kwargs,
            tiling=dict(orientation="v"),
        ))
        _fig_hier.update_layout(
            margin=dict(t=10, l=10, r=10, b=10), height=800,
            uniformtext=dict(minsize=10, mode="hide"),
        )
    elif _chart_type == "Horizontal icicle":
        _fig_hier = go.Figure(go.Icicle(
            **_common_trace, **_font_kwargs,
            tiling=dict(orientation="h"),
        ))
        _fig_hier.update_layout(
            margin=dict(t=10, l=10, r=10, b=10), height=800,
            uniformtext=dict(minsize=10, mode="hide"),
        )
    else:
        _fig_hier = go.Figure(go.Sunburst(
            ids=_h_ids, labels=_h_labels, parents=_h_parents,
            values=_h_values,
            marker=dict(colors=_h_colors),
            maxdepth=4,
            textinfo="label",
            customdata=_h_hover,
            hovertemplate="%{customdata}<extra></extra>",
            insidetextorientation="radial",
        ))
        _fig_hier.update_layout(
            margin=dict(t=10, l=10, r=10, b=10), height=700,
        )

    st.plotly_chart(_fig_hier, use_container_width=True)
    st.caption(_hier_caption)

    # Model Structure Table
    if _active_model_ref:
        st.markdown("**Risk Model Element Hierarchy**")
        st.caption(
            "Full hierarchy for the active risk model. "
            "POS column shows current estimated value (model default if not yet assessed)."
        )
        import pandas as _pd_mod

        _rt_lookup2: dict = {}
        for _pid_rt2, _elems_rt2 in conditional.items():
            for _e_rt2 in (_elems_rt2 if isinstance(_elems_rt2, list) else []):
                if "node_id" in _e_rt2:
                    _rt_lookup2[_e_rt2["node_id"]] = _e_rt2

        _tbl_rows: list[dict] = []
        for _pillar in _active_model_ref.pillars:
            _pid = _pillar.pillar_id
            _play_rt2 = play.get(_pid, {})
            if isinstance(_play_rt2, dict) and "support_for" in _play_rt2:
                _play_pv2 = policy_pos(float(_play_rt2["support_for"]),
                                        float(_play_rt2["support_against"]), uncertainty_weight)
                _play_sc2 = _play_rt2.get("success_criteria") or _pillar.play.success_criteria or ""
            else:
                _play_pv2 = policy_pos(_pillar.play.default_s_n, _pillar.play.default_s_neg, uncertainty_weight)
                _play_sc2 = _pillar.play.success_criteria or ""

            if not _pillar.conditional_groups:
                _tbl_rows.append({
                    "Pillar": _pillar.display_name,
                    "Play POS": f"{_play_pv2*100:.0f}%",
                    "Play criteria": _play_sc2[:80],
                    "Group": "—",
                    "Element": "—",
                    "Success criteria": "—",
                    "Est. POS": "—",
                })
            else:
                _first_grp = True
                for _grp in _pillar.conditional_groups:
                    _first_elem = True
                    for _elem in _grp.elements:
                        _rt2 = _rt_lookup2.get(_elem.node_id)
                        if _rt2:
                            _ep2 = policy_pos(float(_rt2["support_for"]),
                                              float(_rt2["support_against"]), uncertainty_weight)
                            _assessed = True
                        else:
                            _ep2 = policy_pos(_elem.default_s_n, _elem.default_s_neg, uncertainty_weight)
                            _assessed = False
                        _tbl_rows.append({
                            "Pillar": _pillar.display_name if _first_grp and _first_elem else "",
                            "Play POS": f"{_play_pv2*100:.0f}%" if _first_grp and _first_elem else "",
                            "Play criteria": _play_sc2[:80] if _first_grp and _first_elem else "",
                            "Group": _grp.group_label if _first_elem else "",
                            "Element": _elem.name,
                            "Success criteria": _elem.success_criteria[:80] if _elem.success_criteria else "",
                            "Est. POS": f"{_ep2*100:.0f}%" + ("" if _assessed else " *"),
                        })
                        _first_elem = False
                    _first_grp = False

        if _tbl_rows:
            _df_hier = _pd_mod.DataFrame(_tbl_rows)
            st.dataframe(
                _df_hier,
                use_container_width=True,
                hide_index=True,
                height=min(600, 35 * len(_tbl_rows) + 40),
            )
            st.caption("\\* Est. POS marked with * uses model default (element not yet assessed).")

    st.divider()

    # ESL Ratio Plot
    st.subheader("Evidence Support Logic Ratio Plot")
    st.caption("Ratio = max(For,0.01) / max(Against,0.01); X = residual uncertainty (%).")

    def _local_validation(_play_d, _conditional_d, _cond_results, _tf, _ta):
        _issues = []
        for _cat, _el in _play_d.items():
            if not (isinstance(_el, dict) and "support_for" in _el):
                continue
            _f, _a = float(_el["support_for"]), float(_el["support_against"])
            if _f + _a > 1.0:
                _issues.append({"level": "warning", "message": f"Play {_cat}: overcommitted ({_f:.2f}+{_a:.2f}={_f+_a:.2f})."})
            if _f == 0.0 and _a == 0.0:
                _issues.append({"level": "error", "message": f"Play {_cat}: not assessed (both 0.0)."})
        for _cat, _elements in _conditional_d.items():
            for _elem in _elements:
                _f, _a = float(_elem["support_for"]), float(_elem["support_against"])
                _n = f"{_cat}/{_elem.get('label', '?')}"
                if _f + _a > 1.0:
                    _issues.append({"level": "warning", "message": f"Conditional {_n}: overcommitted."})
                if _f == 0.0 and _a == 0.0:
                    _issues.append({"level": "error", "message": f"Conditional {_n}: not assessed."})
        if _tf + _ta > 1.0:
            _issues.append({"level": "warning", "message": f"Total overcommitted (For={_tf:.3f}, Against={_ta:.3f})."})
        if _tf < 0.01:
            _issues.append({"level": "error", "message": f"P(G, ESL) lower bound near zero ({_tf*100:.1f}%)."})
        _cpl = min(_v["for"] for _v in _cond_results.values()) if _cond_results else 0.0
        if _cpl < 0.05:
            _issues.append({"level": "warning", "message": f"Conditional min lower bound = {_cpl*100:.1f}%."})
        return _issues

    _all_play_eids = [f"play|{c}" for c in play if isinstance(play[c], dict) and "support_for" in play[c]]
    _all_cond_eids = [f"cond|{cat}|{i}" for cat, elems in conditional.items() for i, _ in enumerate(elems)]
    _all_eids = _all_play_eids + _all_cond_eids

    def _eid_label(_eid: str) -> str:
        parts = _eid.split("|")
        if parts[0] == "play":
            _cat = parts[1]
            return f"★ {_pillar_display.get(_cat, _cat)} (Play)"
        _cat, _idx = parts[1], int(parts[2])
        _disp = _pillar_display.get(_cat, _cat)
        _elems = conditional.get(_cat, [])
        if _idx < len(_elems):
            _sc = (_elems[_idx].get("success_criteria", "") or _elems[_idx].get("label", ""))[:45]
            return f"{_disp} / {_sc}"
        return f"{_disp} / elem {_idx}"

    _all_eid_labels = [_eid_label(e) for e in _all_eids]
    _lbl_to_eid = dict(zip(_all_eid_labels, _all_eids))

    with st.expander("Element filter (applies to both plots below)", expanded=False):
        _sel_labels = st.multiselect(
            "Show elements",
            options=_all_eid_labels,
            default=_all_eid_labels,
            key="analysis_leaf_filter",
            help="Select / deselect individual risk elements. Changes apply to both the Ratio Plot and the CAM scatter.",
        )
    _sel_eids = {_lbl_to_eid[lb] for lb in _sel_labels} if len(_sel_labels) < len(_all_eids) else None

    _render_esl_ratio_plot_and_validation(
        play, conditional, conditional_results, total_for, total_against,
        uncertainty_weight, _local_validation, prospect_title,
        get_mode, get_dependency, combine_with_mode,
        leaf_filter=_sel_eids,
        pillar_display=_pillar_display,
        pillar_colors=_pillar_colors,
    )

    # Chance Adequacy Matrix
    st.divider()
    st.subheader("Chance Adequacy Matrix — All Elements")
    st.caption(
        "Each risk element plotted in POS × Commitment / ECI space. "
        "Green / red boundaries are auto-set from the element POS distribution. "
        "Use the Element filter above to show/hide individual elements."
    )
    _cam_show_labels = st.checkbox("Show labels", value=True, key="cam_all_show_labels")
    _render_cam_scatter_plot(
        play, conditional, conditional_results,
        total_for, total_against, uncertainty_weight,
        _pillar_colors, _pillar_display,
        leaf_filter=_sel_eids,
        show_labels=_cam_show_labels,
    )

    st.divider()

    with st.expander("Detailed Sub-element Risk Table", expanded=True):
        from components.detail_risk_table import render_detail_risk_table
        render_detail_risk_table(
            "esl", play, conditional, conditional_results,
            uncertainty_weight, tab_key="esl",
        )

    with st.expander("Combination hierarchy", expanded=False):
        from components.hierarchy_chart import render_esl_hierarchy
        render_esl_hierarchy(play, conditional)

    with st.expander("Agreement Analysis & Download Summary", expanded=False):
        from components.comparison import render_comparison_agreement
        from components.audit import render_summary_report
        render_comparison_agreement(
            classic_pos=st.session_state.get("comparison_classic_pos"),
            esl_pos=st.session_state.get("comparison_esl_pos"),
        )
        st.divider()
        render_summary_report(
            prospect_title=prospect_title,
            models=models,
            classic_pos=st.session_state.get("comparison_classic_pos"),
            esl_pos=st.session_state.get("comparison_esl_pos"),
            uw=uncertainty_weight,
        )

    # Classic POS derived view
    st.divider()
    st.markdown(
        "<div style='background:linear-gradient(135deg,#1e3a5f,#0f172a);color:#fff;"
        "padding:14px 18px;border-radius:8px;margin-bottom:8px;'>"
        "<b style='font-size:1.05rem;'>🔢 Classic POS — derived from ESL</b><br>"
        "<span style='font-size:0.82rem;opacity:0.85;'>"
        "Each pillar's Policy P is multiplied together (Rose &amp; Associates method). "
        "No extra input needed — updates automatically as you refine your ESL assessment."
        "</span></div>",
        unsafe_allow_html=True,
    )
    # Gated with a checkbox (not an expander) because render_classic_pos
    # itself uses expanders for its sub-sections, and Streamlit forbids
    # nesting expanders.
    if st.checkbox("Show full P(G, Classic) detail",
                   value=False, key="show_classic_pos_detail",
                   help="Renders the dedicated P(G, Classic) detail page below "
                        "(per-pillar cards, pillar fan, trajectory, detail table, "
                        "hierarchy, sensitivity tornado, sign-off)."):
        from methods.classic_pos import render_classic_pos
        render_classic_pos(models=models)
