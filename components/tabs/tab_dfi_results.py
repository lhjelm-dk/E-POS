"""DFI Results sub-page — DFI-modified per-pillar values, attribution tables,
characteristic-source results + sensitivity. Extracted from ``tab_dfi``.
"""
from __future__ import annotations

import streamlit as st

from logic.dfi_context import (
    esl_prior_pillars_from_ctx_at_w   as _esl_prior_pillars_from_ctx_at_w,
    esl_rollup_prior_at_w             as _esl_rollup_prior_at_w,
    classic_prior_pillars_from_ctx    as _classic_prior_pillars_from_ctx,
    get_effective_calibration         as _get_effective_calibration,
    pillar_pairs_from_priorpillars    as _pillar_pairs_from_priorpillars,
)

from components.tabs.tab_dfi_plots import (
    _render_dfi_trajectory_plot,
    _render_sensitivity_sweep,
    _render_iso_dhi_plot,
)


def _render_dfi_results(ctx) -> None:
    """DFI Results sub-page — per-pillar updates, posterior trajectory.

    Branches by ``dfi_source``: characteristic-mode uses Simm 2-state Bayes,
    DHI Index mode uses the full 8-outcome Bayes (with per-pillar attribution,
    sensitivity sweep, iso-DHI plot, etc.).
    """
    # Characteristic-mode dispatch — no 8-outcome math, simpler displays
    if st.session_state.get("dfi_source") == "characteristic":
        _render_dfi_results_characteristic(ctx)
        return
    # Custom R tool dispatch — two-state Simm Bayes on the user-defined R
    if st.session_state.get("dfi_source") == "custom":
        _render_dfi_results_custom(ctx)
        return

    import numpy as np
    import plotly.graph_objects as go
    from logic.dfi_bayes import (
        FluidWeights, compute_dfi_posterior,
        attribute_classic, attribute_esl_optionA, attribute_esl_optionB,
        ESLMasses, PriorPillars,
    )

    # ── Gather inputs from session state (single source of truth) ──
    from logic.dfi_inputs import read_dfi_inputs
    _inp = read_dfi_inputs(st.session_state)
    dhi, sd_mode, fluid_type = _inp.dhi, _inp.sd_mode, _inp.fluid_type
    fw = _inp.fluid_weights
    esl_attr_mode = _inp.esl_attribution
    calib = _get_effective_calibration()

    # ── Build priors and posteriors at current stance for both methods ──
    w_cur = ctx.uncertainty_weight
    prior_esl     = _esl_prior_pillars_from_ctx_at_w(ctx, w_cur)   # pillars → Init Pg diagnostic
    prior_classic = _classic_prior_pillars_from_ctx(ctx, w_cur)
    esl_prior_pg  = _esl_rollup_prior_at_w(ctx, w_cur)             # headline mass-rollup = DFI prior
    post_esl     = compute_dfi_posterior(prior_esl,     dhi, calib, fw, sd_mode, fluid_type,
                                         prior_pg_override=esl_prior_pg)
    post_classic = compute_dfi_posterior(prior_classic, dhi, calib, fw, sd_mode, fluid_type)

    # ── Headline metrics (4 tiles + 2 diagnostics) ──
    st.markdown("##### Headline numbers")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("P(G, ESL) — prior",
                  f"{esl_prior_pg*100:.2f}%",
                  help="Headline mass-rollup P(G, ESL) at current stance — the number "
                       f"booked elsewhere. (∏-pillars Init Pg = {prior_esl.prior_pg*100:.1f}%, "
                       "used internally for the 8-outcome failure split.)")
    with m2:
        st.metric("P(G | DFI, ESL) — posterior",
                  f"{post_esl.posterior_pg*100:.2f}%",
                  delta=f"{(post_esl.posterior_pg - esl_prior_pg)*100:+.2f}%",
                  help="ESL prior updated by the DFI observation.")
    with m3:
        st.metric("P(G, Classic) — prior",
                  f"{prior_classic.prior_pg*100:.2f}%",
                  help="Total prospect Pg via Classic POS at current stance.")
    with m4:
        st.metric("P(G | DFI, Classic) — posterior",
                  f"{post_classic.posterior_pg*100:.2f}%",
                  delta=f"{(post_classic.posterior_pg - prior_classic.prior_pg)*100:+.2f}%",
                  help="Classic prior updated by the DFI observation.")

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.metric("R_DFI (ESL)",      f"{post_esl.r_dfi:.2f}",
                  help="L_success / E[L | failure] using ESL prior.")
    with d2:
        st.metric("DHI Volume Weight V (ESL)",   f"{post_esl.dhi_volume_weight:.2f}",
                  help="V = L_success / (L_success + E[L|failure]). For the DHI-Index method "
                       "this equals the DHI score, R_DFI/(R_DFI+1).")
    with d3:
        st.metric("R_DFI (Classic)",  f"{post_classic.r_dfi:.2f}")
    with d4:
        st.metric("DHI Volume Weight V (Classic)", f"{post_classic.dhi_volume_weight:.2f}",
                  help="V = L_success / (L_success + E[L|failure]). For the DHI-Index method "
                       "this equals the DHI score, R_DFI/(R_DFI+1).")

    # ── ESL vs Classic gap, before AND after the DFI update (B4) ──
    _gap_pre = (esl_prior_pg - prior_classic.prior_pg) * 100
    _gap_post = (post_esl.posterior_pg - post_classic.posterior_pg) * 100
    st.caption(
        f"**ESL − Classic gap:** prior {_gap_pre:+.1f} pp → post-DFI {_gap_post:+.1f} pp. "
        "The gap is your method-divergence / data-quality signal; watch whether the DFI "
        "update widens or narrows it."
    )

    from components.dfi_shared import render_interval_posterior
    render_interval_posterior(ctx, post_esl.r_dfi, method_label="Conceptual DHI Index",
                              key="ipost_dhi")

    st.divider()

    # ── Channel-resolved post-DFI attribution (GeoX-style, reservoir vs HC-system) ──
    st.markdown("##### DFI pillar attribution (channel-resolved, GeoX-style)")
    from logic.dfi_context import dfi_post_pillars as _dfi_post_pillars
    from components.dfi_shared import render_pillar_attribution
    render_pillar_attribution(_dfi_post_pillars(ctx), key="dfi_dhi_chan_attr")
    st.caption(
        "Reservoir comes from the exact 8-outcome P(reservoir present | DFI); the "
        "HC-system (Charge·Closure·Retention) is split by log-proportion. This replaces "
        "the earlier equal-spread attribution — a supportive anomaly can now correctly "
        "lower the Reservoir marginal while raising POS. The mass-level tables below keep "
        "the play/cond Italian-flag detail."
    )

    st.divider()

    # ── DFI-modified per-pillar tables (mass-level detail) ──
    st.markdown("##### DFI-modified per-pillar values — mass-level detail (at current stance)")

    # Classic attribution: log-split (workbook method)
    classic_attr = attribute_classic(prior_classic, post_classic)

    # ESL attribution: A (equal-multiplicative + mass round-trip) or B (Bel/Pl-preserving)
    # Build per-pillar ESLMasses from ctx (shared helper, keyed Closure → trap)
    esl_masses_keyed = _esl_masses_keyed_from_ctx(ctx)
    if esl_attr_mode == "A":
        esl_attr_masses = attribute_esl_optionA(
            prior_esl, esl_masses_keyed, post_esl.posterior_pg, w_cur,
        )
    else:
        esl_attr_masses = attribute_esl_optionB(
            prior_esl, esl_masses_keyed, dhi, calib, fw, sd_mode, fluid_type,
        )

    # ESL flag table is full-width (two flag bars per row need the room);
    # the Classic table stacks beneath it.
    st.markdown(f"**ESL — prior vs posterior flags** *(attribution: option {esl_attr_mode})*")
    _render_pillar_attribution_table_esl(
        esl_masses_keyed, esl_attr_masses, w_cur, ctx, esl_attr_mode,
    )
    st.markdown("**Classic** *(workbook log-attribution, reservoir-aware)*")
    _render_pillar_attribution_table_classic(prior_classic, classic_attr, ctx)

    st.divider()

    # ── Posterior trajectory plot (4 curves: prior/posterior × ESL/Classic) ──
    st.markdown("##### Posterior trajectory — P(G) vs stance w")
    _render_dfi_trajectory_plot(ctx, dhi, calib, fw, sd_mode, fluid_type)

    st.divider()

    # ── Sensitivity sweep (workbook "Mod POS, wgt & str graphs" generalised) ──
    st.markdown("##### Sensitivity sweep — explore how the posterior moves")
    _render_sensitivity_sweep(ctx, dhi, calib, fw, sd_mode, fluid_type)

    st.divider()

    # ── Prior→Posterior map with iso-DHI curves (workbook "DHI adjustment of POS") ──
    st.markdown("##### Prior → Posterior map — iso-DHI Index curves")
    _render_iso_dhi_plot(ctx, dhi, calib, fw, sd_mode, fluid_type)

    # ── DHI → volumetrics integration recommendation (Monigle 2025) ──
    st.divider()
    from components.dfi_shared import render_volumetrics_recommendation
    from logic.dhi_characteristics import dhi_score_from_r as _dhi_score_from_r
    render_volumetrics_recommendation(
        _dhi_score_from_r(post_esl.r_dfi),
        v_weight=post_esl.dhi_volume_weight,
        discernibility=None,
        key="dfi_vol_dhi",
    )

    st.divider()
    from components.dfi_shared import render_dempster_prototype
    render_dempster_prototype(
        ctx, _dhi_score_from_r(post_esl.r_dfi),
        discernibility=None, simm_posterior=post_esl.posterior_pg, key="ds_dhi",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helper renderers — pillar tables and trajectory
# ─────────────────────────────────────────────────────────────────────────────

def _render_dfi_results_characteristic(ctx) -> None:
    """DFI Results when source = characteristic scoring.

    No 8-outcome decomposition, no per-pillar attribution, no GeoX/fluid-mix.
    Shows: ESL & Classic priors → posteriors via Simm 2-state Bayes, headline
    R/score, prior→posterior trajectory across stance w.
    """
    from logic.dhi_characteristics import simm_bayes_posterior

    r_eff   = float(st.session_state.get("dhi_char_r_eff",   1.0))
    r_char  = float(st.session_state.get("dhi_char_r_char",  1.0))
    score   = float(st.session_state.get("dhi_char_score",   50.0))
    bucket  = str(st.session_state.get("dhi_char_bucket",    "high"))

    # ── Priors at current stance ──
    w_cur = float(ctx.uncertainty_weight)
    prior_esl     = _esl_prior_pillars_from_ctx_at_w(ctx, w_cur)   # pillars → Init Pg diagnostic
    prior_classic = _classic_prior_pillars_from_ctx(ctx, w_cur)
    esl_prior_pg  = _esl_rollup_prior_at_w(ctx, w_cur)             # headline mass-rollup = the DFI prior
    post_esl_pg     = simm_bayes_posterior(esl_prior_pg,           r_eff)
    post_classic_pg = simm_bayes_posterior(prior_classic.prior_pg, r_eff)

    de = (post_esl_pg     - esl_prior_pg)           * 100
    dc = (post_classic_pg - prior_classic.prior_pg) * 100

    # ── Headline numbers ──
    st.markdown("##### Headline numbers (characteristic-scoring source)")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("R_eff",            f"{r_eff:.2f}",
                        help=f"R_char = {r_char:.2f} squashed by discernibility ({bucket}).")
    with c2: st.metric("DHI Char Score",   f"{score:.0f}%",
                        help="R_eff / (R_eff + 1) — Monigle-style 0–100 % score.")
    with c3: st.metric("P(G | DFI, ESL)",
                        f"{post_esl_pg*100:.1f}%",
                        delta=f"{de:+.1f} pp")
    with c4: st.metric("P(G | DFI, Classic)",
                        f"{post_classic_pg*100:.1f}%",
                        delta=f"{dc:+.1f} pp")

    st.info(
        "In characteristic mode the posterior comes from Simm's 2-state Bayes "
        "(R_eff applied to the geological prior). The **channel-resolved** views "
        "(reservoir-vs-HC-system split, fluid-mix sweep, iso-DHI plot, GeoX hand-off) "
        "are not available because the characteristic scoring does not decompose the "
        "failure modes into water/LSG/other × eval/non-eval reservoir. The ESL per-pillar "
        "flag attribution below spreads the single headline R across the pillars."
    )

    _render_esl_flag_table_for_r(ctx, r_eff, w_cur)
    from components.dfi_shared import render_interval_posterior
    render_interval_posterior(ctx, r_eff, method_label="Characteristic scoring", key="ipost_char")
    st.divider()

    # ── Prior → Posterior trajectory across stance w (shared component) ──
    st.markdown("##### Posterior trajectory — P(G) vs stance w")
    from components.dfi_shared import render_simm_trajectory
    render_simm_trajectory(ctx, r_eff, key="dfi_char_trajectory")

    # ── Sensitivity sweep over the 5/10 DHI attributes ──
    _render_characteristic_sensitivity(ctx, esl_prior_pg, w_cur)

    # ── DHI → volumetrics integration recommendation (Monigle 2025) ──
    st.divider()
    from components.dfi_shared import render_volumetrics_recommendation
    render_volumetrics_recommendation(
        score / 100.0, v_weight=None, discernibility=bucket, key="dfi_vol_char",
    )

    st.divider()
    from components.dfi_shared import render_dempster_prototype
    _bucket_d = {"high": 1.0, "moderate": 0.6, "low": 0.3, "absent": 0.0}.get(bucket, 1.0)
    render_dempster_prototype(
        ctx, score / 100.0, discernibility=_bucket_d,
        simm_posterior=post_esl_pg, key="ds_char",
    )


def _render_dfi_results_custom(ctx) -> None:
    """DFI Results when source = Custom R tool.

    Two-state Simm Bayes on the user-defined R (stored as ``dhi_custom_r`` by the
    setup page). Mirrors the characteristic results, minus the attribute sweep.
    """
    from logic.dhi_characteristics import simm_bayes_posterior

    r_val = float(st.session_state.get("dhi_custom_r",     1.0))
    score = float(st.session_state.get("dhi_custom_score", 50.0))

    w_cur = float(ctx.uncertainty_weight)
    prior_classic = _classic_prior_pillars_from_ctx(ctx, w_cur)
    esl_prior_pg  = _esl_rollup_prior_at_w(ctx, w_cur)
    post_esl_pg     = simm_bayes_posterior(esl_prior_pg,           r_val)
    post_classic_pg = simm_bayes_posterior(prior_classic.prior_pg, r_val)

    # Pillar-resolved (multi-case): the headline ESL posterior comes from the joint
    # engine (reservoir-driven failure split), not the grouped-R two-state value.
    from logic.dfi_context import resolve_dfi_custom
    _resolved = resolve_dfi_custom(ctx)
    if _resolved is not None and _resolved.pillar_resolved:
        post_esl_pg = _resolved.pos_post

    de = (post_esl_pg     - esl_prior_pg)           * 100
    dc = (post_classic_pg - prior_classic.prior_pg) * 100

    st.markdown("##### Headline numbers (custom R tool)")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("R", f"{r_val:.2f}",
                       help="P(DFI|HC) / P(DFI|No-HC) at the DHI-strength slider "
                            "(set on the DFI Setup sub-tab).")
    with c2: st.metric("DHI score", f"{score:.0f}%",
                       help="R / (R + 1) — Monigle-style 0–100 score.")
    with c3: st.metric("P(G | DFI, ESL)", f"{post_esl_pg*100:.1f}%", delta=f"{de:+.1f} pp")
    with c4: st.metric("P(G | DFI, Classic)", f"{post_classic_pg*100:.1f}%", delta=f"{dc:+.1f} pp")

    _gap_pre = (esl_prior_pg - prior_classic.prior_pg) * 100
    _gap_post = (post_esl_pg - post_classic_pg) * 100
    st.caption(
        f"**ESL − Classic gap:** prior {_gap_pre:+.1f} pp → post-DFI {_gap_post:+.1f} pp "
        "(method-divergence / data-quality signal)."
    )

    # ── Pillar-resolved DFI attribution (multi-case) / aggregate note (dual-case) ──
    st.markdown("##### DFI pillar attribution (GeoX-style, single-segment)")
    from components.dfi_shared import render_pillar_attribution
    render_pillar_attribution(_resolved, key="dfi_custom_attr")

    st.info(
        "In custom mode the posterior comes from Bayes on your user-defined bell curves "
        "(DFI Setup sub-tab). **Multi-case** resolves the update onto the Reservoir pillar "
        "and the combined Charge·Closure·Retention (HC-system) — the headline ESL posterior "
        "above is the reservoir-driven joint update. **Dual-case** updates only the headline. "
        "The **DHI-strength sweep** and **iso-R prior→posterior map** below are the custom-tool "
        "analogues of the conceptual DHI model sensitivity and iso-DHI plots."
    )

    _render_esl_flag_table_for_r(ctx, r_val, w_cur)
    from components.dfi_shared import render_interval_posterior
    render_interval_posterior(ctx, r_val, method_label="Custom R tool", key="ipost_custom")
    st.divider()

    st.markdown("##### Posterior trajectory — P(G) vs stance w")
    from components.dfi_shared import render_simm_trajectory
    render_simm_trajectory(ctx, r_val, key="dfi_custom_trajectory")

    # ── Reconstruct R(DHI strength) from the persisted custom setup (shared
    #    single-source helper, same one the Setup page uses) so the Results tab
    #    can sweep strength without re-entering the curves. ──
    import numpy as np
    import plotly.graph_objects as go
    from logic.dfi_custom import custom_config_from_state
    _cfg = custom_config_from_state(st.session_state)
    slider = _cfg.slider
    _R_at = _cfg.r_at

    # ── Sensitivity sweep — explore how the posterior moves (custom-tool analogue
    #    of the conceptual DHI model sweep: curve families, method prior, stacked Y) ──
    st.divider()
    st.markdown("##### Sensitivity sweep — explore how the posterior moves")
    from plotly.subplots import make_subplots
    from logic.dfi_simm import dhi_score_from_r
    from logic.dfi_custom import grouped_r

    _multi = bool(_cfg.multicase)
    _cs1, _cs2 = st.columns([1.5, 1])
    with _cs1:
        _fam = st.selectbox(
            "Curve family (11 curves)",
            ["None (single curve)", "Water failure fraction", "LSG failure fraction", "Stance w"],
            key="custom_sens_family",
            help="Fan out 11 curves. Water / LSG fraction re-weight the failure cases "
                 "(multi-case mode only); Stance w sweeps the prior (R is unchanged by stance).",
        )
    with _cs2:
        _method = st.radio("Method prior", ["ESL", "Classic"], horizontal=True,
                           key="custom_sens_method",
                           help="Which prior the posterior row updates. R and V are prior-independent.")
    _y_opts = st.multiselect(
        "Y outputs (stacked)",
        ["Posterior P(G)", "R", "DHI Volume Weight V"],
        default=["Posterior P(G)"],
        key="custom_sens_y_outputs",
        help="Posterior P(G), the likelihood ratio R, and the DHI Volume Weight "
             "V = R/(R+1) (the 0–1 DHI strength; identical definition to the Conceptual "
             "DHI Index method).",
    )

    _fluid_fam = _fam in ("Water failure fraction", "LSG failure fraction")
    if _fluid_fam and not _multi:
        st.info("**Water / LSG failure-fraction families need multi-case mode** — dual-case "
                "has no fluid mix, so R does not depend on it. Showing the single curve.")
        _fam, _fluid_fam = "None (single curve)", False

    if not _y_opts:
        st.info("Pick at least one Y output.")
    else:
        xs = np.linspace(-100.0, 100.0, 201)

        # Family values + the value matching the current prospect
        if _fam == "Water failure fraction":
            fam_vals, fam_cur, fam_lbl = [i / 10 for i in range(11)], _cfg.weights.get("water", 0.5), "water frac"
        elif _fam == "LSG failure fraction":
            fam_vals, fam_cur, fam_lbl = [i / 10 for i in range(11)], _cfg.weights.get("lsg", 0.2), "LSG frac"
        elif _fam == "Stance w":
            fam_vals, fam_cur, fam_lbl = [i / 10 for i in range(11)], w_cur, "w"
        else:
            fam_vals, fam_cur, fam_lbl = [None], None, ""

        def _r_curve_for(fv):
            """R(strength) and R(current) for one family value."""
            if _fluid_fam and fv is not None:
                w = dict(_cfg.weights)
                if _fam == "Water failure fraction":
                    w["water"], w["lsg"], w["other"] = float(fv), 1.0 - float(fv), 0.0
                else:
                    w["water"], w["lsg"], w["other"] = 1.0 - float(fv), float(fv), 0.0
                return [grouped_r(float(x), _cfg.cases, w) for x in xs], grouped_r(float(slider), _cfg.cases, w)
            return [_R_at(float(x)) for x in xs], _R_at(float(slider))

        def _prior_for(fv):
            """Prior P(G) for one family value (Stance w sweeps it; else current)."""
            if _fam == "Stance w" and fv is not None:
                wv = float(fv)
                return (_esl_rollup_prior_at_w(ctx, wv) if _method == "ESL"
                        else _classic_prior_pillars_from_ctx(ctx, wv).prior_pg)
            return esl_prior_pg if _method == "ESL" else prior_classic.prior_pg

        n_fam = len(fam_vals)
        _base = "#16a34a" if _method == "ESL" else "#1e40af"

        def _color(i):
            if n_fam <= 1:
                return _base
            t = i / max(1, n_fam - 1)
            return f"rgb({int(40 + 200 * t)},{int(40 + 200 * t)},{int(150 + 70 * t)})"

        figs = make_subplots(rows=len(_y_opts), cols=1, shared_xaxes=True,
                             subplot_titles=_y_opts, vertical_spacing=0.09)
        for i_fam, fv in enumerate(fam_vals):
            rcurve, _ = _r_curve_for(fv)
            prior = _prior_for(fv)
            legend_name = (f"{fv*100:.0f}% {fam_lbl}" if fam_lbl.endswith("frac")
                           else (f"w = {fv:.1f}" if _fam == "Stance w" else f"{_method} sweep"))
            for _ri, _yo in enumerate(_y_opts, start=1):
                if _yo == "Posterior P(G)":
                    ys = [simm_bayes_posterior(prior, R) * 100 for R in rcurve]
                    figs.update_yaxes(title_text=f"P(G | DFI, {_method}) %", range=[0, 100], row=_ri, col=1)
                elif _yo == "R":
                    ys = rcurve
                    figs.update_yaxes(title_text="R", row=_ri, col=1)
                else:  # DHI Volume Weight V = R/(R+1)
                    ys = [dhi_score_from_r(R) for R in rcurve]
                    figs.update_yaxes(title_text="V = R/(R+1)", range=[0, 1], row=_ri, col=1)
                figs.add_trace(go.Scatter(x=xs, y=ys, mode="lines",
                                          line=dict(color=_color(i_fam), width=2),
                                          name=legend_name, legendgroup=legend_name,
                                          showlegend=(_ri == 1 and n_fam > 1)), row=_ri, col=1)

        # Reference lines + ★ current prospect (on the family curve closest to current)
        i_close = (int(np.argmin([abs(fv - fam_cur) for fv in fam_vals]))
                   if (fam_cur is not None and n_fam > 1) else 0)
        _, r_star = _r_curve_for(fam_vals[i_close])
        prior_star = _prior_for(fam_vals[i_close])
        for _ri, _yo in enumerate(_y_opts, start=1):
            if _yo == "Posterior P(G)":
                figs.add_hline(y=prior_star * 100, line_dash="dot", line_color=_base, row=_ri, col=1)
                star_y = simm_bayes_posterior(prior_star, r_star) * 100
            elif _yo == "R":
                figs.add_hline(y=1.0, line_dash="dot", line_color="#6b7280", row=_ri, col=1)
                star_y = r_star
            else:
                star_y = dhi_score_from_r(r_star)
            figs.add_trace(go.Scatter(x=[slider], y=[star_y], mode="markers",
                                      marker=dict(symbol="star", size=15, color="#dc2626",
                                      line=dict(color="white", width=1.5)),
                                      name="Current", showlegend=False, hoverinfo="skip"), row=_ri, col=1)
            figs.add_vline(x=slider, line_dash="dash", line_color="#6b7280", row=_ri, col=1)
        figs.update_xaxes(title_text="DHI strength", row=len(_y_opts), col=1)
        # Match the DHI-Index sensitivity sweep exactly (same per-row height and a
        # compact vertical right-side legend, so the 11-curve family does not balloon
        # the plot height).
        figs.update_layout(
            height=480 * len(_y_opts),
            margin=dict(t=40, b=60, l=60, r=20),
            legend=dict(orientation="v", x=1.02, y=1.0,
                        bordercolor="#e5e7eb", borderwidth=1, font=dict(size=10)),
        )
        st.plotly_chart(figs, use_container_width=True)
        st.caption(
            f"Posterior on the **{_method}** prior, the likelihood ratio **R**, and the "
            "**DHI Volume Weight V = R/(R+1)** (the 0–1 DHI strength — same definition as the "
            "Conceptual DHI Index method) as the **DHI-strength reading** changes, with your "
            f"curves held fixed. {('Family: ' + _fam + '. ') if _fam != 'None (single curve)' else ''}"
            f"Dotted line = the {_method} prior (crossed where R = 1, the neutral strength); the "
            f"★ marks the current reading ({slider:+.0f})."
        )

    # ── Prior → Posterior map — iso-R curves (analogue of the iso-DHI plot) ──
    st.divider()
    st.markdown("##### Prior → Posterior map — iso-R curves")
    ISO_R = [1/3, 1/1.5, 1.0, 1.5, 3.0, 10.0]
    pg_grid = np.linspace(0.0, 1.0, 51)
    figm = go.Figure()
    figm.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines",
                              line=dict(color="#9ca3af", width=1, dash="dot"),
                              name="no change (y = x)", hoverinfo="skip"))
    _n = len(ISO_R)
    def _iso_col(i: int) -> str:
        t = i / max(1, _n - 1)
        r = int(30 + (180 - 30) * t); g = int(60 + (190 - 60) * t); b = int(160 + (230 - 160) * t)
        return f"rgb({r},{g},{b})"
    for i, R in enumerate(ISO_R):
        ys = [simm_bayes_posterior(float(p), R) * 100 for p in pg_grid]
        figm.add_trace(go.Scatter(
            x=[p * 100 for p in pg_grid], y=ys, mode="lines",
            line=dict(color=_iso_col(i), width=1.8),
            name=f"R = {R:.2f}".rstrip("0").rstrip("."),
            hovertemplate=f"R = {R:.2f}<br>prior %{{x:.0f}}%% → posterior %{{y:.1f}}%%<extra></extra>"))
    # Current-R curve highlighted in violet (matches the Setup R-curve colour)
    ys_cur = [simm_bayes_posterior(float(p), r_val) * 100 for p in pg_grid]
    figm.add_trace(go.Scatter(
        x=[p * 100 for p in pg_grid], y=ys_cur, mode="lines",
        line=dict(color="#7c3aed", width=3), name=f"current R = {r_val:.2f}",
        hovertemplate=f"current R = {r_val:.2f}<br>prior %{{x:.0f}}%% → posterior %{{y:.1f}}%%<extra></extra>"))
    # ★ prospect at (ESL prior, posterior at current R)
    figm.add_trace(go.Scatter(
        x=[esl_prior_pg * 100], y=[post_esl_pg * 100], mode="markers+text",
        marker=dict(symbol="star", size=18, color="#dc2626", line=dict(color="white", width=1.5)),
        text=[f"  ★ {post_esl_pg*100:.1f}%"], textposition="middle right",
        textfont=dict(size=11, color="#7f1d1d"), name="this prospect (ESL)",
        hovertemplate="<b>This prospect</b><br>prior %{x:.1f}%% → posterior %{y:.1f}%%<extra></extra>"))
    figm.add_trace(go.Scatter(
        x=[esl_prior_pg * 100, esl_prior_pg * 100],
        y=[esl_prior_pg * 100, post_esl_pg * 100], mode="lines",
        line=dict(color="#dc2626", width=1, dash="dot"), showlegend=False, hoverinfo="skip"))
    figm.update_xaxes(title_text="Initial Pg (geological prior) %", range=[0, 100])
    figm.update_yaxes(title_text="DFI-modified posterior POS %", range=[0, 100])
    figm.update_layout(height=460, margin=dict(t=20, b=55, l=60, r=20),
                       legend=dict(orientation="v", x=1.02, y=1.0,
                                   bordercolor="#e5e7eb", borderwidth=1, font=dict(size=10)))
    st.plotly_chart(figm, use_container_width=True)
    st.caption(
        "Each curve is one fixed likelihood ratio R; the dotted diagonal is the no-change "
        "line (posterior = prior). Curves **above** the diagonal raise P(G), **below** lower "
        "it. The violet curve is your **current R**; the ★ is this prospect at its ESL prior. "
        "Because R is a constant multiplicative shift in log-odds, every curve has the "
        "characteristic S-shape — the update bites hardest near a 50 % prior and vanishes at "
        "the 0 %/100 % extremes. This is the custom-tool analogue of the conceptual DHI model iso-DHI map "
        "(R replaces the DHI Index as the family parameter)."
    )

    # ── DHI → volumetrics integration recommendation (Monigle 2025) ──
    st.divider()
    from components.dfi_shared import render_volumetrics_recommendation
    render_volumetrics_recommendation(
        score / 100.0, v_weight=None, discernibility=None, key="dfi_vol_custom",
    )

    st.divider()
    from components.dfi_shared import render_dempster_prototype
    render_dempster_prototype(
        ctx, score / 100.0, discernibility=None,
        simm_posterior=post_esl_pg, key="ds_custom",
    )


def _render_characteristic_sensitivity(ctx, prior_pg: float, w_cur: float) -> None:
    """How does the posterior move as each DHI attribute is swept across its
    categories? Two views: a tornado (posterior swing per attribute, others held
    at current) and a single-attribute line sweep."""
    import plotly.graph_objects as go
    from components.colors import cos_color
    from logic.dhi_characteristics import (
        load_characteristic_stats, compute_r_char, compute_r_char_inferred,
        apply_discernibility, simm_bayes_posterior, cap_for_bucket,
    )

    cstats   = load_characteristic_stats()
    mode_key = str(st.session_state.get("dhi_char_mode", "5_current"))
    _bucket_name = str(st.session_state.get("dhi_char_bucket", "high"))
    bucket   = cstats.buckets[_bucket_name]
    sel_cur  = dict(st.session_state.get("dhi_char_selections", {}))
    pos_cur  = dict(st.session_state.get("dhi_char_positions", {}))
    inferred = bool(st.session_state.get("dhi_char_inferred", False))
    apply_cap = bool(st.session_state.get("dhi_char_apply_cap", True))
    rel_middle = bool(st.session_state.get("dhi_char_rel_middle", False))
    corr_rho = float(st.session_state.get("dhi_char_corr_rho", 0.3))
    _floor, _hardcap = cap_for_bucket(_bucket_name, enabled=apply_cap)
    cap_kw = dict(hard_cap=_hardcap, floor=_floor)

    # only attributes that actually move R (display-only confidence excluded)
    r_attrs = cstats.attributes_in_r_for_mode(mode_key)
    if not r_attrs:
        return

    def _posterior_for(selections: dict) -> float:
        r = compute_r_char(cstats, selections, mode_key=mode_key,
                           relative_to_middle=rel_middle, corr_rho=corr_rho,
                           **cap_kw)["r_char"]
        r_eff = apply_discernibility(r, bucket)
        return simm_bayes_posterior(prior_pg, r_eff) * 100.0

    def _posterior_for_pos(positions: dict) -> float:
        r = compute_r_char_inferred(cstats, positions, mode_key=mode_key,
                                    relative_to_middle=rel_middle, corr_rho=corr_rho,
                                    **cap_kw)["r_char"]
        r_eff = apply_discernibility(r, bucket)
        return simm_bayes_posterior(prior_pg, r_eff) * 100.0

    st.markdown("##### Sensitivity sweep, which DHI attributes move the posterior?")
    st.caption(
        "Each attribute is swept across **all its categories** while the others stay "
        "at your current slider positions. The bar spans the resulting posterior P(G) "
        "from the worst to the best category — longer bars = the prospect's posterior "
        "is more sensitive to that attribute (given the current scores). The ◆ marks "
        "your current selection."
    )

    base_post = _posterior_for_pos(pos_cur) if inferred else _posterior_for(sel_cur)
    x_grid = [j / 20.0 for j in range(21)]   # 0..1 fine sweep for inferred
    rows = []
    for key, attr in r_attrs.items():
        cats = attr.categories(mode_key)
        if inferred:
            posts = []
            for xv in x_grid:
                trial = dict(pos_cur); trial[key] = xv
                posts.append(_posterior_for_pos(trial))
            cur_post = _posterior_for_pos(pos_cur)
        else:
            posts = []
            for c in cats:
                trial = dict(sel_cur); trial[key] = c
                posts.append(_posterior_for(trial))
            cur_cat = sel_cur.get(key, cats[len(cats) // 2])
            cur_post = posts[cats.index(cur_cat)] if cur_cat in cats else base_post
        lo, hi = min(posts), max(posts)
        rows.append({
            "attr": attr.display_name, "lo": lo, "hi": hi,
            "cur": cur_post, "swing": hi - lo,
        })
    rows.sort(key=lambda r: r["swing"])   # smallest at bottom → largest on top

    fig = go.Figure()
    for r in rows:
        fig.add_trace(go.Scatter(
            x=[r["lo"], r["hi"]], y=[r["attr"], r["attr"]],
            mode="lines", line=dict(color="#9ca3af", width=8),
            hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=[r["lo"], r["hi"]], y=[r["attr"], r["attr"]],
            mode="markers",
            marker=dict(size=11, color=[cos_color(r["lo"] / 100), cos_color(r["hi"] / 100)],
                        line=dict(color="#111827", width=0.7)),
            customdata=[r["swing"], r["swing"]],
            hovertemplate="%{y}<br>P(G)=%{x:.1f}%  (swing %{customdata:.1f} pp)<extra></extra>",
            showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=[r["cur"]], y=[r["attr"]], mode="markers",
            marker=dict(symbol="diamond", size=12, color="#111827"),
            hovertemplate="%{y}<br>current: %{x:.1f}%<extra></extra>",
            showlegend=False,
        ))
    fig.add_vline(x=base_post, line_dash="dot", line_color="#1f2937",
                  annotation_text=f"current P(G,ESL) = {base_post:.1f}%",
                  annotation_position="top")
    fig.update_xaxes(title_text="Posterior P(G | DFI, ESL) (%)", range=[0, 100])
    fig.update_layout(height=max(240, 60 + 42 * len(rows)),
                      margin=dict(t=30, b=40, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

    # Single-attribute line sweep (the closest analogue to the DHI-Index sweep)
    attr_names = [a.display_name for a in r_attrs.values()]
    name_to_key = {a.display_name: k for k, a in r_attrs.items()}
    pick = st.selectbox("Sweep one attribute in detail", attr_names, index=0,
                        key="dhi_char_sweep_pick")
    pk = name_to_key[pick]
    pattr = cstats.attributes[pk]
    pcats = pattr.categories(mode_key)
    Kp = len(pcats)
    fig2 = go.Figure()
    if inferred:
        # near-continuous sweep across x∈[0,1]
        xs = [j / 100.0 for j in range(101)]
        pposts = []
        for xv in xs:
            trial = dict(pos_cur); trial[pk] = xv
            pposts.append(_posterior_for_pos(trial))
        x_plot = [x * (Kp - 1) for x in xs]   # 0..K-1 axis aligned with categories
        fig2.add_trace(go.Scatter(
            x=x_plot, y=pposts, mode="lines",
            line=dict(color="#1e40af", width=2),
            hovertemplate="pos %{x:.2f}<br>P(G)=%{y:.1f}%<extra></extra>",
        ))
        cur_x = float(pos_cur.get(pk, 0.5)) * (Kp - 1)
        cur_post = _posterior_for_pos(pos_cur)
        fig2.add_trace(go.Scatter(
            x=[cur_x], y=[cur_post], mode="markers",
            marker=dict(symbol="diamond", size=16, color="#111827"),
            name="current", showlegend=False, hoverinfo="skip",
        ))
        fig2.update_xaxes(title_text=f"{pick} — continuous position",
                          tickmode="array", tickvals=list(range(Kp)), ticktext=pcats)
    else:
        pposts = []
        for c in pcats:
            trial = dict(sel_cur); trial[pk] = c
            pposts.append(_posterior_for(trial))
        cur_cat = sel_cur.get(pk, pcats[len(pcats) // 2])
        fig2.add_trace(go.Scatter(
            x=pcats, y=pposts, mode="lines+markers",
            line=dict(color="#1e40af", width=2),
            marker=dict(size=12, color=[cos_color(p / 100) for p in pposts],
                        line=dict(color="#111827", width=0.7)),
            text=[f"{p:.1f}%" for p in pposts], textposition="top center",
            hovertemplate="%{x}<br>P(G)=%{y:.1f}%<extra></extra>",
        ))
        if cur_cat in pcats:
            fig2.add_trace(go.Scatter(
                x=[cur_cat], y=[pposts[pcats.index(cur_cat)]], mode="markers",
                marker=dict(symbol="diamond-open", size=20, color="#111827",
                            line=dict(width=2.5)),
                name="current", showlegend=False, hoverinfo="skip",
            ))
        fig2.update_xaxes(title_text=f"{pick} category")
    fig2.add_hline(y=prior_pg * 100, line_dash="dot", line_color="#6b7280",
                   annotation_text=f"prior {prior_pg*100:.1f}%", annotation_position="right")
    fig2.update_yaxes(title_text="Posterior P(G | DFI, ESL) (%)", range=[0, 100])
    fig2.update_layout(height=320, margin=dict(t=20, b=40, l=50, r=10))
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Marker colour uses the shared Probability scale. Where the curve is **flat**, "
        "the prospect's posterior barely depends on that attribute given the other "
        "scores; where it's **steep**, that attribute is pivotal. Non-monotonic dips "
        "(e.g. a mid category outperforming a 'better' one) reflect genuine small-N "
        "structure in Monigle's drilled-prospect histograms."
    )


def _render_pillar_attribution_table_classic(prior, posterior, ctx) -> None:
    """Side-by-side prior vs posterior table with delta column for Classic."""
    import pandas as pd
    rows = []
    for (name, _key, pri_v), (_n2, _k2, post_v) in zip(
        _pillar_pairs_from_priorpillars(prior),
        _pillar_pairs_from_priorpillars(posterior),
    ):
        rows.append({
            "Pillar / Scope": name,
            "Prior":     f"{pri_v*100:.1f}%",
            "Posterior": f"{post_v*100:.1f}%",
            "Δ":         f"{(post_v - pri_v)*100:+.1f}%",
        })
    rows.append({
        "Pillar / Scope": "**Product = P(G, Classic)**",
        "Prior":     f"**{prior.prior_pg*100:.2f}%**",
        "Posterior": f"**{posterior.prior_pg*100:.2f}%**",
        "Δ":         f"**{(posterior.prior_pg - prior.prior_pg)*100:+.2f}%**",
    })
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, use_container_width=True)


def _render_pillar_attribution_table_esl(masses_prior, masses_post, w, ctx,
                                         attr_mode: str = "A") -> None:
    """ESL per-pillar table: prior & posterior **Italian flags** alongside the
    (S_for, S_against, Policy P) masses, for all 8 play/cond slots.

    The posterior flag is an *attribution* of the headline Bayesian update, not a
    measurement: under Option A the incompleteness (White) is held fixed and only
    green/red rebalance; under Option B the Bel and Pl edges move.
    """
    from components.render_helpers import small_flag_html

    def _disp(pillar: str, scope: str) -> str:
        name = ("Charge" if pillar == "charge" else
                "Closure" if pillar == "trap" else
                "Reservoir" if pillar == "reservoir" else "Retention")
        return f"{name} / {'Play' if scope == 'play' else 'Cond'}"

    hdr = (
        "<tr style='background:#f3f4f6;'>"
        "<th style='text-align:left;padding:4px 8px;'>Pillar / Scope</th>"
        "<th style='padding:4px 8px;'>Prior flag</th>"
        "<th style='padding:4px 8px;'>Posterior flag</th>"
        "<th style='padding:4px 8px;'>S_for</th>"
        "<th style='padding:4px 8px;'>S_against</th>"
        "<th style='padding:4px 8px;'>Policy P</th>"
        "<th style='padding:4px 8px;'>ΔP</th>"
        "</tr>"
    )
    body = ""
    for pillar in ("charge", "trap", "reservoir", "retention"):
        for scope in ("play", "cond"):
            mp = masses_prior[pillar][scope]
            mn = masses_post[pillar][scope]
            pri_p = mp.s_for + w * max(0.0, 1 - mp.s_for - mp.s_against)
            post_p = mn.s_for + w * max(0.0, 1 - mn.s_for - mn.s_against)
            dP = (post_p - pri_p) * 100
            dcol = "#16a34a" if dP > 0.05 else ("#dc2626" if dP < -0.05 else "#6b7280")
            arr = "▲" if dP > 0.05 else ("▼" if dP < -0.05 else "■")
            body += (
                "<tr style='border-top:1px solid #e5e7eb;'>"
                f"<td style='text-align:left;padding:4px 8px;white-space:nowrap;'>{_disp(pillar, scope)}</td>"
                f"<td style='padding:4px 8px;'>{small_flag_html(mp.s_for, mp.s_against)}</td>"
                f"<td style='padding:4px 8px;'>{small_flag_html(mn.s_for, mn.s_against)}</td>"
                f"<td style='padding:4px 8px;text-align:center;'>{mp.s_for:.3f} → {mn.s_for:.3f}</td>"
                f"<td style='padding:4px 8px;text-align:center;'>{mp.s_against:.3f} → {mn.s_against:.3f}</td>"
                f"<td style='padding:4px 8px;text-align:center;'>{pri_p*100:.1f}% → {post_p*100:.1f}%</td>"
                f"<td style='padding:4px 8px;text-align:center;color:{dcol};'>{arr} {dP:+.1f}</td>"
                "</tr>"
            )
    st.markdown(
        "<table style='width:100%;border-collapse:collapse;font-size:0.82rem;'>"
        f"<thead>{hdr}</thead><tbody>{body}</tbody></table>",
        unsafe_allow_html=True,
    )
    conv = ("Option A holds **White fixed** (preserve C = S_for + S_against); only green/red "
            "rebalance to hit the posterior."
            if attr_mode == "A" else
            "Option B moves the **Bel and Pl** edges, so White can change between prior and posterior.")
    st.caption(
        "Flag colours: green = S_for (support for), red = S_against (support against), "
        "white = incompleteness (what you don't yet know). "
        f"{conv} The posterior flag is an **attribution** of the Bayesian headline update, "
        "not a measurement — a sharp Bayesian posterior has no intrinsic incompleteness, so the "
        "posterior White is a modelling convention."
    )


def _esl_masses_keyed_from_ctx(ctx):
    """Per-pillar prior ESL masses from ctx, keyed the way the attribution
    functions expect (Closure → ``trap`` to match ``PriorPillars``)."""
    from logic.dfi_bayes import ESLMasses
    by_pillar = {}
    for pid in ("Charge", "Closure", "Reservoir", "Retention"):
        play_el = ctx.play.get(pid, {})
        cond_r = ctx.conditional_results.get(pid, {"for": 0.5, "against": 0.1})
        by_pillar[pid.lower()] = {
            "play": ESLMasses(s_for=float(play_el.get("support_for", 0.5)),
                              s_against=float(play_el.get("support_against", 0.1))),
            "cond": ESLMasses(s_for=float(cond_r["for"]),
                              s_against=float(cond_r["against"])),
        }
    return {
        "charge":    by_pillar["charge"],
        "trap":      by_pillar["closure"],   # PriorPillars uses 'trap' for Closure
        "reservoir": by_pillar["reservoir"],
        "retention": by_pillar["retention"],
    }


def _render_esl_flag_table_for_r(ctx, r_val: float, w_cur: float) -> None:
    """Prior/posterior ESL flag table for a single-R source (Custom R tool and
    Characteristic). Uses the active A/B attribution: A via the generic
    equal-multiplicative scaling, B via the scalar-R interval update."""
    from logic.dfi_bayes import attribute_esl_optionA, attribute_esl_optionB_r
    from logic.dfi_simm import simm_bayes_posterior

    masses_prior = _esl_masses_keyed_from_ctx(ctx)
    prior_pillars = _esl_prior_pillars_from_ctx_at_w(ctx, w_cur)
    esl_prior_pg = _esl_rollup_prior_at_w(ctx, w_cur)
    posterior_pg = simm_bayes_posterior(esl_prior_pg, r_val)
    attr_mode = st.session_state.get("dfi_esl_attribution", "B")
    if attr_mode == "A":
        masses_post = attribute_esl_optionA(prior_pillars, masses_prior, posterior_pg, w_cur)
    else:
        masses_post = attribute_esl_optionB_r(masses_prior, r_val)

    st.markdown("##### DFI-modified per-pillar values — mass-level detail (at current stance)")
    st.markdown(f"**ESL — prior vs posterior flags** *(attribution: option {attr_mode})*")
    _render_pillar_attribution_table_esl(masses_prior, masses_post, w_cur, ctx, attr_mode)
    st.caption(
        "Set the attribution method (A / B) in **Dashboard → ⚙ Advanced — DFI → ESL "
        "per-pillar attribution**."
    )


