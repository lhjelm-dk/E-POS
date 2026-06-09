"""Final Prospect POS sub-page — one-page reportable DFI summary.
Extracted from ``components.tabs.tab_dfi``.
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

from logic.dfi_orchestration import (
    _dhi_strength_interpretation,
    _build_decision_narrative,
    _build_summary_text,
)


def _reportable_pos_callout(value_pct: float, *, after_dfi: bool) -> None:
    """Single headline read-out of the one reportable number for this prospect.

    Rendered right under the overview table so a reader gets the answer without
    parsing the grid. ``value_pct`` is P(G, ESL) in percent (0–100).
    """
    label = "Reportable POS (after DFI)" if after_dfi else "Reportable POS (geological)"
    st.markdown(
        "<div style='background:#111827;border-radius:8px;padding:12px 20px;"
        "margin:6px 0 2px;display:flex;justify-content:space-between;"
        "align-items:center;'>"
        f"<span style='color:#9ca3af;font-size:13px;font-weight:600;"
        f"text-transform:uppercase;letter-spacing:0.08em;'>{label}</span>"
        f"<span style='color:#ffffff;font-size:28px;font-weight:800;"
        f"line-height:1;'>{value_pct:.0f}%</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def _classic_bar_legend() -> None:
    """One-line colour key for the 4-segment Classic range bar used in the table.

    Full explanation lives in the Theory & Guide tab ("Reading the 4-segment
    Classic range bar"); this is the at-a-glance reminder next to the bars.
    """
    def _chip(color: str, text: str) -> str:
        return (f"<span style='display:inline-flex;align-items:center;gap:5px;"
                f"margin-right:14px;white-space:nowrap;'>"
                f"<span style='width:11px;height:11px;border-radius:2px;"
                f"background:{color};display:inline-block;"
                f"border:1px solid #d1d5db;'></span>{text}</span>")
    st.markdown(
        "<div style='font-size:11px;color:#6b7280;margin:2px 0 10px;'>"
        "<b>Flag bar:</b> "
        + _chip("#15803d", "Bel — committed success")
        + _chip("#86efac", "stance lift (w×white)")
        + _chip("#f3f4f6", "undecided white")
        + _chip("#b3261e", "committed failure")
        + "<span style='color:#9ca3af;'>· Bel + stance = POS · "
          "+ white = Pl &nbsp;(see Theory &amp; Guide)</span>"
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_dfi_summary(ctx) -> None:
    """Final Prospect POS Summary — reportable one-page view.

    Branches by ``dfi_source``: characteristic-mode renders a slimmed summary
    without per-pillar attribution or fluid-class diagnostics.
    """
    if st.session_state.get("dfi_source") == "characteristic":
        _render_dfi_summary_characteristic(ctx)
        return
    if st.session_state.get("dfi_source") == "custom":
        _render_dfi_summary_custom(ctx)
        return

    import datetime
    from logic.dfi_bayes import compute_dfi_posterior, attribute_classic
    from logic.dfi_calibration import CLASS_DISPLAY
    from logic.dfi_inputs import read_dfi_inputs

    # ── Inputs from session state (single source of truth) ──
    _inp = read_dfi_inputs(st.session_state)
    dhi, sd_mode, fluid_type = _inp.dhi, _inp.sd_mode, _inp.fluid_type
    fw = _inp.fluid_weights.normalised()   # summary displays renormalised weights
    calib       = _get_effective_calibration()
    prospect_title = st.session_state.get("meta_title") or ctx.prospect_title or "Prospect"
    analyst        = st.session_state.get("meta_analyst", "")
    basin          = st.session_state.get("meta_basin", "")
    review_date    = st.session_state.get("meta_date", str(datetime.date.today()))

    # ── Priors and posteriors at current stance ──
    w_cur         = ctx.uncertainty_weight
    prior_esl     = _esl_prior_pillars_from_ctx_at_w(ctx, w_cur)
    prior_classic = _classic_prior_pillars_from_ctx(ctx, w_cur)
    esl_prior_pg  = _esl_rollup_prior_at_w(ctx, w_cur)   # headline mass-rollup P(G, ESL)
    post_esl      = compute_dfi_posterior(prior_esl,     dhi, calib, fw, sd_mode, fluid_type,
                                          prior_pg_override=esl_prior_pg)
    post_classic  = compute_dfi_posterior(prior_classic, dhi, calib, fw, sd_mode, fluid_type)
    classic_attr  = attribute_classic(prior_classic, post_classic)

    delta_esl     = post_esl.posterior_pg     - esl_prior_pg
    delta_classic = post_classic.posterior_pg - prior_classic.prior_pg

    # ── Title block ──
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;"
        f"padding:14px 18px;border-radius:8px;margin-bottom:10px;'>"
        f"<b style='font-size:1.15rem;'>{prospect_title}</b>  "
        f"<span style='opacity:0.7;font-size:0.85rem;'> · Final POS Summary · "
        f"DFI Bayesian update applied · {review_date}</span><br>"
        f"<span style='font-size:0.82rem;opacity:0.85;'>Analyst: {analyst or '—'} · "
        f"Basin: {basin or '—'} · Stance w = {w_cur:.2f}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Risk Overview table (geological prior, identical to Analysis tab) ──
    from components.prospect_hub import _get_esl_overview_data
    from components.overview_table import render_overview_table
    _ov_models = {"play": ctx.play, "conditional": ctx.conditional}
    _ov_data = _get_esl_overview_data(_ov_models)
    if _ov_data:
        st.markdown("##### Risk Overview — geological prior (per-pillar) **+ DFI update**")
        st.caption(
            "Per-pillar breakdown of the geological **prior** P(G, ESL), with the "
            "consolidated **before → after** DFI update (both methods, Δ) appended at "
            "the bottom. The DFI Bayesian update acts on the combined prospect Pg — it "
            "does not change the per-pillar masses above the divider. The prior→posterior "
            "bar visual is in the next block."
        )
        # Posterior Bel/Pl envelope: re-run the 8-outcome update at each ESL extreme
        # so the DFI posterior carries the same uncertainty band as the prior.
        _bel = ctx.total_for
        _pl = 1.0 - ctx.total_against
        _post_bel = compute_dfi_posterior(prior_esl, dhi, calib, fw, sd_mode, fluid_type,
                                          prior_pg_override=_bel).posterior_pg
        _post_pl = compute_dfi_posterior(prior_esl, dhi, calib, fw, sd_mode, fluid_type,
                                         prior_pg_override=_pl).posterior_pg
        _ov_data["dfi"] = {
            "method_label": "Modified DHI Index (SAAM) · 8-outcome Bayes",
            "esl_prior": esl_prior_pg, "esl_post": post_esl.posterior_pg,
            "esl_delta_pp": delta_esl * 100,
            "classic_prior": prior_classic.prior_pg, "classic_post": post_classic.posterior_pg,
            "classic_delta_pp": delta_classic * 100,
            "bel": _bel, "pl": _pl,
            "esl_post_bel": _post_bel, "esl_post_pl": _post_pl,
            "diagnostics": f"DHI Index={dhi:+.0f} · R_SAAM={post_esl.r_saam:.2f} · "
                           f"V={post_esl.dhi_volume_weight:.2f} · "
                           f"∏-pillars Init Pg={prior_esl.prior_pg*100:.1f}% "
                           f"(independent-pillars reference)",
        }
        render_overview_table("esl", _ov_data)
        _classic_bar_legend()
        _reportable_pos_callout(_ov_data["dfi"]["esl_post"] * 100, after_dfi=True)

    # ── DFI Diagnostic Strip (inputs + R + V in one consolidated block) ──
    interp_txt     = _dhi_strength_interpretation(post_esl.r_saam,
                                                  post_esl.dhi_volume_weight)
    st.markdown(
        f"<div style='background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;"
        f"padding:10px 14px;margin:14px 0 6px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"flex-wrap:wrap;gap:10px;'>"
        f"<b style='color:#1e3a8a;font-size:1.0rem;'>DFI Bayesian Update</b>"
        f"<span style='font-size:0.82rem;color:#1e40af;'>"
        f"DHI Index <b>{dhi:+.0f}</b> &nbsp;·&nbsp; "
        f"HC <b>{CLASS_DISPLAY.get(fluid_type, fluid_type)}</b> &nbsp;·&nbsp; "
        f"SD mode <b>{sd_mode}</b> &nbsp;·&nbsp; "
        f"Fluid mix water <b>{fw.water:.0%}</b> · LSG <b>{fw.lsg:.0%}</b> · "
        f"other <b>{fw.other:.0%}</b> &nbsp;·&nbsp; "
        f"Calib <b>v.{calib.version}</b>"
        f"{' (placeholder)' if calib.is_placeholder else ''}"
        f"</span></div>"
        f"<div style='display:flex;gap:18px;margin-top:8px;font-size:0.86rem;color:#1e3a8a;'>"
        f"<div><b>R_SAAM</b> = {post_esl.r_saam:.2f}</div>"
        f"<div><b>DHI Volume Weight V</b> = {post_esl.dhi_volume_weight:.2f}</div>"
        f"<div style='flex:1;text-align:right;color:#374151;font-style:italic;'>{interp_txt}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # ── Final Prospect POS — after DFI (ESL prior → posterior, with delta) ──
    # Prior interval (Bel, Pl) from ESL Italian flag (workspace-wide, not per-method)
    prior_bel = ctx.total_for          # all-against extreme (lower bound, w=0)
    prior_pl  = 1.0 - ctx.total_against  # all-for extreme (upper bound, w=1)

    st.markdown("##### Prospect POS — before → after DFI update")
    from components.dfi_shared import render_prior_post_bar
    render_prior_post_bar(esl_prior_pg, post_esl.posterior_pg, prior_bel, prior_pl)

    st.caption(
        "**Reading guide:** the geological prior carries an uncertainty envelope "
        "(Bel/Pl) from the ESL Italian flag — see the **DFI Update** rows at the bottom "
        "of the Risk Overview table above for the consolidated before → after figures "
        "(both methods, with Δ). The DFI posterior is a **point estimate** — the Bayesian "
        "update collapses the envelope onto a single Pg given the seismic evidence at "
        "this stance. The per-pillar prior→posterior shifts are tabulated below; the "
        "divergence between ESL and Classic posteriors is your data-quality signal."
    )

    # ── Channel-resolved post-DFI pillars (Plan B; parallel — prior inputs unchanged) ──
    from logic.dfi_context import dfi_post_pillars as _dfi_post_pillars
    _pp = _dfi_post_pillars(ctx)
    if _pp is not None and getattr(_pp, "pillar_resolved", False):
        st.markdown("##### Post-DFI pillar attribution (channel-resolved, GeoX-style)")
        from components.dfi_shared import render_pillar_attribution
        render_pillar_attribution(_pp, key="finalpos_dfi_attr")

    st.divider()

    # ── Top movers — pillar slots with biggest absolute DFI impact (Classic table) ──
    st.markdown("##### Top movers — pillars with largest DFI-induced change (Classic attribution)")
    movers = []
    for (n_pri, _, v_pri), (_n_post, _, v_post) in zip(
        _pillar_pairs_from_priorpillars(prior_classic),
        _pillar_pairs_from_priorpillars(classic_attr),
    ):
        movers.append((n_pri, v_pri, v_post, v_post - v_pri))
    movers.sort(key=lambda x: abs(x[3]), reverse=True)
    import pandas as pd
    df_mov = pd.DataFrame([
        {"Pillar / Scope": name,
         "Prior":     f"{pri*100:.1f}%",
         "Posterior": f"{post*100:.1f}%",
         "Δ":         f"{(post - pri)*100:+.1f}%"}
        for (name, pri, post, _d) in movers[:5]
    ])
    st.dataframe(df_mov, hide_index=True, use_container_width=True)

    # ── Top 5 weakest at element level (pre-DFI; DFI attribution stops at pillar) ──
    st.markdown("##### Top 5 weakest risk elements")
    from components.risk_summary import render_top5_weakest
    render_top5_weakest(ctx.conditional, w_cur,
                        pillar_display=ctx.pillar_display)
    st.caption("Per-element Policy P is shown at the current stance w. The DFI "
               "Bayesian update attributes back to per-pillar values (Play+Cond); "
               "individual sub-elements are not directly modified.")

    st.divider()

    # ── Decision narrative ──
    st.markdown("##### Decision narrative")
    narrative = _build_decision_narrative(
        esl_prior_pg, post_esl.posterior_pg,
        prior_classic.prior_pg, post_classic.posterior_pg,
        post_esl.r_saam, post_esl.dhi_volume_weight, dhi,
    )
    st.markdown(narrative)

    st.divider()

    # ── Copy-export text ──
    st.markdown("##### Reportable summary (copy or download)")
    summary_text = _build_summary_text(
        prospect_title, analyst, basin, review_date, w_cur,
        dhi, fluid_type, sd_mode, fw,
        prior_esl, post_esl, prior_classic, post_classic, classic_attr,
        calib.version, calib.is_placeholder,
        esl_prior_override=esl_prior_pg,
    )
    st.text_area(
        "Summary text",
        value=summary_text,
        height=320,
        key="dfi_summary_text_area",
        label_visibility="collapsed",
    )
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in prospect_title)
    st.download_button(
        "📥 Download DFI summary (.txt)",
        data=summary_text,
        file_name=f"{safe_title}_DFI_summary_{review_date}.txt",
        mime="text/plain",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for the summary sub-page
# ─────────────────────────────────────────────────────────────────────────────

def _render_dfi_summary_characteristic(ctx) -> None:
    """Reportable summary when source = characteristic scoring."""
    import datetime
    import pandas as pd
    from logic.dhi_characteristics import (
        load_characteristic_stats, simm_bayes_posterior, dhi_score_from_r,
    )

    cstats = load_characteristic_stats()
    r_eff   = float(st.session_state.get("dhi_char_r_eff",  1.0))
    r_char  = float(st.session_state.get("dhi_char_r_char", 1.0))
    score   = float(st.session_state.get("dhi_char_score",  50.0))
    bucket  = str(st.session_state.get("dhi_char_bucket",   "high"))
    sel     = dict(st.session_state.get("dhi_char_selections", {}))

    w_cur = float(ctx.uncertainty_weight)
    prior_esl     = _esl_prior_pillars_from_ctx_at_w(ctx, w_cur)   # pillars → Init Pg diagnostic
    prior_classic = _classic_prior_pillars_from_ctx(ctx, w_cur)
    esl_prior_pg  = _esl_rollup_prior_at_w(ctx, w_cur)             # headline mass-rollup = DFI prior
    post_esl_pg     = simm_bayes_posterior(esl_prior_pg,           r_eff)
    post_classic_pg = simm_bayes_posterior(prior_classic.prior_pg, r_eff)
    delta_esl     = post_esl_pg     - esl_prior_pg
    delta_classic = post_classic_pg - prior_classic.prior_pg

    prospect_title = st.session_state.get("meta_title") or ctx.prospect_title or "Prospect"
    analyst        = st.session_state.get("meta_analyst", "")
    basin          = st.session_state.get("meta_basin", "")
    review_date    = st.session_state.get("meta_date", str(datetime.date.today()))

    # ── Title block ──
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;"
        f"padding:14px 18px;border-radius:8px;margin-bottom:10px;'>"
        f"<b style='font-size:1.15rem;'>{prospect_title}</b>  "
        f"<span style='opacity:0.7;font-size:0.85rem;'> · Final POS Summary · "
        f"DFI characteristic-scoring update applied · {review_date}</span><br>"
        f"<span style='font-size:0.82rem;opacity:0.85;'>Analyst: {analyst or '—'} · "
        f"Basin: {basin or '—'} · Stance w = {w_cur:.2f}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Risk Overview (geological prior table, unchanged) ──
    from components.prospect_hub import _get_esl_overview_data
    from components.overview_table import render_overview_table
    _ov_models = {"play": ctx.play, "conditional": ctx.conditional}
    _ov_data = _get_esl_overview_data(_ov_models)
    _bel_pct_c = ctx.total_for * 100
    _pl_pct_c  = (1.0 - ctx.total_against) * 100
    if _ov_data:
        st.markdown("##### Risk Overview — geological prior (per-pillar) **+ DFI update**")
        st.caption(
            "Per-pillar breakdown of the geological **prior** P(G, ESL), with the "
            "consolidated **before → after** DFI update appended at the bottom. The DFI "
            "characteristic update acts on the combined prospect Pg (Simm 2-state Bayes) "
            "— it does not change the per-pillar masses above the divider."
        )
        _bel = ctx.total_for
        _pl = 1.0 - ctx.total_against
        _ov_data["dfi"] = {
            "method_label": "Characteristic scoring · Simm 2-state Bayes",
            "esl_prior": esl_prior_pg, "esl_post": post_esl_pg,
            "esl_delta_pp": delta_esl * 100,
            "classic_prior": prior_classic.prior_pg, "classic_post": post_classic_pg,
            "classic_delta_pp": delta_classic * 100,
            "bel": _bel, "pl": _pl,
            "esl_post_bel": simm_bayes_posterior(_bel, r_eff),
            "esl_post_pl": simm_bayes_posterior(_pl, r_eff),
            "diagnostics": f"R_char={r_char:.2f} · R_eff={r_eff:.2f} · "
                           f"DHI Score={score:.0f}% · {bucket} · "
                           f"∏-pillars Init Pg={prior_esl.prior_pg*100:.1f}% "
                           f"(independent-pillars reference)",
        }
        render_overview_table("esl", _ov_data)
        _classic_bar_legend()
        _reportable_pos_callout(_ov_data["dfi"]["esl_post"] * 100, after_dfi=True)

    # ── Diagnostic strip ──
    direction = "uplift" if delta_esl > 0.005 else ("downgrade" if delta_esl < -0.005 else "no change")
    arrow = "↑" if delta_esl > 0.005 else ("↓" if delta_esl < -0.005 else "→")
    st.markdown(
        f"<div style='background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;"
        f"padding:10px 14px;margin:14px 0 8px;'>"
        f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;'>"
        f"<b style='color:#1e3a8a;font-size:1.0rem;'>DFI Update — characteristic scoring</b>"
        f"<span style='font-size:0.82rem;color:#1e40af;'>"
        f"R_char = <b>{r_char:.2f}</b> · R_eff = <b>{r_eff:.2f}</b> · "
        f"DHI Score = <b>{score:.0f}%</b> · "
        f"Discernibility = <b>{bucket}</b> · Calib = <b>{cstats.version}</b>"
        f"</span></div></div>",
        unsafe_allow_html=True,
    )

    # ── Prospect POS before → after DFI (shared bar with Bel/Pl envelope) ──
    from components.dfi_shared import render_prior_post_bar
    from logic.dfi_orchestration import build_simm_decision_narrative
    st.markdown("##### Prospect POS — before → after DFI update")
    render_prior_post_bar(esl_prior_pg, post_esl_pg,
                          ctx.total_for, 1.0 - ctx.total_against)
    st.caption(
        f"Red ● = prior P(G, ESL) {esl_prior_pg*100:.1f}% → Gold ◆ = posterior "
        f"P(G | DFI, ESL) {post_esl_pg*100:.1f}%. The Simm 2-state update collapses the "
        "geological Bel/Pl envelope onto a point estimate given R_eff."
    )

    # ── Decision narrative (shared 2-state generator) ──
    st.markdown("##### Decision narrative")
    st.markdown(build_simm_decision_narrative(
        esl_prior_pg, post_esl_pg, prior_classic.prior_pg, post_classic_pg, r_eff,
        method_label="Characteristic scoring (Monigle 2025)",
        evidence_desc=f"R_char = {r_char:.2f}, discernibility {bucket}",
    ))

    st.divider()

    # ── Characteristic selections table (audit trail) ──
    st.markdown("##### Characteristic selections (audit trail)")
    mode_key_sess = str(st.session_state.get("dhi_char_mode", "5_current"))
    active_attrs_sum = cstats.attributes_for_mode(mode_key_sess)
    rows = []
    for key, attr in active_attrs_sum.items():
        cat = sel.get(key, "—")
        rows.append({"Attribute": attr.display_name, "Selected": cat})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        "**Reading guide:** the geological prior is computed from the ESL evidence and "
        "carries its Bel/Pl envelope. The DFI posterior here is a point estimate via "
        "Simm's 2-state Bayes update (Simm 2016) driven by R_eff. Per-pillar attribution "
        "is not available in characteristic mode because the 6 attributes do not "
        "decompose into per-pillar fluid/reservoir failure modes."
    )

    # ── Reportable summary text (download) ──
    st.markdown("---")
    st.markdown("##### Reportable summary (copy or download)")
    lines = []
    lines.append(f"Prospect: {prospect_title}")
    lines.append(f"Analyst : {analyst or '—'}   Basin: {basin or '—'}   Date: {review_date}")
    lines.append(f"Stance w: {w_cur:.2f}")
    lines.append("")
    lines.append(f"DFI source: Characteristic scoring (Monigle 2025 calibration v.{cstats.version})")
    lines.append(f"  R_char (capped) : {r_char:.3f}")
    lines.append(f"  R_effective     : {r_eff:.3f}   (discernibility = {bucket})")
    lines.append(f"  DHI Score       : {score:.1f}%")
    lines.append("")
    lines.append(f"Attribute set mode: {mode_key_sess}")
    lines.append("Characteristic selections:")
    for key, attr in active_attrs_sum.items():
        lines.append(f"  {attr.display_name:30s} {sel.get(key, '—')}")
    lines.append("")
    lines.append("Headline POS:")
    lines.append(f"  Prior  P(G, ESL)        : {esl_prior_pg*100:.1f}%   (mass-rollup; ∏-pillars Init Pg = {prior_esl.prior_pg*100:.1f}%)")
    lines.append(f"  Post.  P(G | DFI, ESL)  : {post_esl_pg*100:.1f}%   (Δ {delta_esl*100:+.1f} pp)")
    lines.append(f"  Prior  P(G, Classic)    : {prior_classic.prior_pg*100:.1f}%")
    lines.append(f"  Post.  P(G | DFI, Cl.)  : {post_classic_pg*100:.1f}%   (Δ {delta_classic*100:+.1f} pp)")
    lines.append("")
    lines.append("Methodology: Bayesian DFI update via Simm 2016 2-state formula. "
                 "R_char = naive-independence product of 6 attribute LRs from Monigle 2025 "
                 "drilled-prospect statistics, with hard cap at R ∈ [1/3, 3].")
    summary_text = "\n".join(lines)
    st.text_area(
        "Summary text", value=summary_text, height=320,
        key="dfi_summary_text_area_char",
        label_visibility="collapsed",
    )
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in prospect_title)
    st.download_button(
        "📥 Download DFI summary (.txt)",
        data=summary_text,
        file_name=f"{safe_title or 'prospect'}_DFI_characteristic_summary.txt",
        key="dfi_char_summary_dl",
    )


def _render_dfi_summary_custom(ctx) -> None:
    """Reportable summary when source = Custom R tool."""
    import datetime
    from logic.dhi_characteristics import simm_bayes_posterior
    from logic.dfi_custom import gaussian_from_p1_p99

    r_val = float(st.session_state.get("dhi_custom_r",     1.0))
    score = float(st.session_state.get("dhi_custom_score", 50.0))
    slider = float(st.session_state.get("dfi_custom_slider", 25.0))
    hc_p1  = float(st.session_state.get("dfi_custom_hc_p1",  -50.0))
    hc_p99 = float(st.session_state.get("dfi_custom_hc_p99", 100.0))
    no_p1  = float(st.session_state.get("dfi_custom_no_p1",  -100.0))
    no_p99 = float(st.session_state.get("dfi_custom_no_p99",  50.0))
    hc_mean, hc_sd = gaussian_from_p1_p99(hc_p1, hc_p99)
    no_mean, no_sd = gaussian_from_p1_p99(no_p1, no_p99)

    w_cur = float(ctx.uncertainty_weight)
    prior_esl     = _esl_prior_pillars_from_ctx_at_w(ctx, w_cur)
    prior_classic = _classic_prior_pillars_from_ctx(ctx, w_cur)
    esl_prior_pg  = _esl_rollup_prior_at_w(ctx, w_cur)
    post_esl_pg     = simm_bayes_posterior(esl_prior_pg,           r_val)
    post_classic_pg = simm_bayes_posterior(prior_classic.prior_pg, r_val)
    # Multi-case: the ESL headline is the reservoir-driven joint update (keep bar,
    # narrative and per-pillar block consistent).
    from logic.dfi_context import dfi_post_pillars as _dfi_post_pillars
    _pp_custom = _dfi_post_pillars(ctx)
    if _pp_custom is not None and getattr(_pp_custom, "pillar_resolved", False):
        post_esl_pg = _pp_custom.pos_post
    delta_esl     = post_esl_pg     - esl_prior_pg
    delta_classic = post_classic_pg - prior_classic.prior_pg

    prospect_title = st.session_state.get("meta_title") or ctx.prospect_title or "Prospect"
    analyst        = st.session_state.get("meta_analyst", "")
    basin          = st.session_state.get("meta_basin", "")
    review_date    = st.session_state.get("meta_date", str(datetime.date.today()))

    st.markdown(
        f"<div style='background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;"
        f"padding:14px 18px;border-radius:8px;margin-bottom:10px;'>"
        f"<b style='font-size:1.15rem;'>{prospect_title}</b>  "
        f"<span style='opacity:0.7;font-size:0.85rem;'> · Final POS Summary · "
        f"DFI custom-R update applied · {review_date}</span><br>"
        f"<span style='font-size:0.82rem;opacity:0.85;'>Analyst: {analyst or '—'} · "
        f"Basin: {basin or '—'} · Stance w = {w_cur:.2f}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    from components.prospect_hub import _get_esl_overview_data
    from components.overview_table import render_overview_table
    _ov_models = {"play": ctx.play, "conditional": ctx.conditional}
    _ov_data = _get_esl_overview_data(_ov_models)
    if _ov_data:
        st.markdown("##### Risk Overview — geological prior (per-pillar) **+ DFI update**")
        st.caption(
            "Per-pillar breakdown of the geological **prior** P(G, ESL), with the "
            "consolidated **before → after** DFI update appended at the bottom. The custom "
            "DFI update acts on the combined prospect Pg (Simm 2-state Bayes)."
        )
        _bel = ctx.total_for
        _pl = 1.0 - ctx.total_against
        _ov_data["dfi"] = {
            "method_label": "Custom R tool · Simm 2-state Bayes",
            "esl_prior": esl_prior_pg, "esl_post": post_esl_pg,
            "esl_delta_pp": delta_esl * 100,
            "classic_prior": prior_classic.prior_pg, "classic_post": post_classic_pg,
            "classic_delta_pp": delta_classic * 100,
            "bel": _bel, "pl": _pl,
            "esl_post_bel": simm_bayes_posterior(_bel, r_val),
            "esl_post_pl": simm_bayes_posterior(_pl, r_val),
            "diagnostics": f"R={r_val:.2f} · DHI Score={score:.0f}% · "
                           f"slider={slider:+.0f} · "
                           f"∏-pillars Init Pg={prior_esl.prior_pg*100:.1f}% "
                           f"(independent-pillars reference)",
        }
        render_overview_table("esl", _ov_data)
        _classic_bar_legend()
        _reportable_pos_callout(_ov_data["dfi"]["esl_post"] * 100, after_dfi=True)

    st.markdown(
        f"<div style='background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;"
        f"padding:10px 14px;margin:14px 0 8px;'>"
        f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;'>"
        f"<b style='color:#1e3a8a;font-size:1.0rem;'>DFI Update — custom R tool</b>"
        f"<span style='font-size:0.82rem;color:#1e40af;'>"
        f"R = <b>{r_val:.2f}</b> · DHI Score = <b>{score:.0f}%</b> · "
        f"DHI strength = <b>{slider:+.0f}</b>"
        f"</span></div></div>",
        unsafe_allow_html=True,
    )

    # ── Prospect POS before → after DFI (shared bar with Bel/Pl envelope) ──
    import pandas as pd
    from components.dfi_shared import render_prior_post_bar
    from logic.dfi_orchestration import build_simm_decision_narrative
    st.markdown("##### Prospect POS — before → after DFI update")
    render_prior_post_bar(esl_prior_pg, post_esl_pg,
                          ctx.total_for, 1.0 - ctx.total_against)
    st.caption(
        f"Red ● = prior P(G, ESL) {esl_prior_pg*100:.1f}% → Gold ◆ = posterior "
        f"P(G | DFI, ESL) {post_esl_pg*100:.1f}%. The Simm 2-state update collapses the "
        "geological Bel/Pl envelope onto a point estimate given R."
    )

    # ── Channel-resolved post-DFI pillars (Plan B; parallel — prior inputs unchanged) ──
    if _pp_custom is not None and getattr(_pp_custom, "pillar_resolved", False):
        st.markdown("##### Post-DFI pillar attribution (channel-resolved, GeoX-style)")
        from components.dfi_shared import render_pillar_attribution
        render_pillar_attribution(_pp_custom, key="finalpos_custom_attr")

    # ── Decision narrative (shared 2-state generator) ──
    st.markdown("##### Decision narrative")
    st.markdown(build_simm_decision_narrative(
        esl_prior_pg, post_esl_pg, prior_classic.prior_pg, post_classic_pg, r_val,
        method_label="Custom R tool",
        evidence_desc=f"DHI strength = {slider:+.0f}",
    ))

    # ── Case-definition audit table ──
    st.markdown("##### Custom case definitions (audit trail)")
    _audit = pd.DataFrame([
        {"Case": "P(DFI | HC)", "P1": f"{hc_p1:+.0f}", "P99": f"{hc_p99:+.0f}",
         "mean": f"{hc_mean:.1f}", "sd": f"{hc_sd:.2f}"},
        {"Case": "P(DFI | No-HC)", "P1": f"{no_p1:+.0f}", "P99": f"{no_p99:+.0f}",
         "mean": f"{no_mean:.1f}", "sd": f"{no_sd:.2f}"},
    ])
    st.dataframe(_audit, hide_index=True, use_container_width=True)
    st.caption(
        f"Each case is a Gaussian set by its P1/P99 (mean = (P1+P99)/2, "
        f"sd = (P99−P1)/4.6527). At DHI strength **{slider:+.0f}**, "
        f"R = P(DFI|HC)/P(DFI|No-HC) = **{r_val:.2f}**."
    )

    st.divider()

    st.markdown("---")
    st.markdown("##### Reportable summary (copy or download)")
    lines = [
        f"Prospect: {prospect_title}",
        f"Analyst : {analyst or '—'}   Basin: {basin or '—'}   Date: {review_date}",
        f"Stance w: {w_cur:.2f}",
        "",
        "DFI source: Custom R tool (two user-defined Gaussians)",
        f"  P(DFI | HC)    : P1={hc_p1:+.0f}, P99={hc_p99:+.0f}  ->  mean={hc_mean:.1f}, sd={hc_sd:.2f}",
        f"  P(DFI | No-HC) : P1={no_p1:+.0f}, P99={no_p99:+.0f}  ->  mean={no_mean:.1f}, sd={no_sd:.2f}",
        f"  DHI strength   : {slider:+.0f}",
        f"  R = P(DFI|HC)/P(DFI|No-HC) : {r_val:.3f}",
        f"  DHI Score                  : {score:.1f}%",
        "",
        "Headline POS:",
        f"  Prior  P(G, ESL)        : {esl_prior_pg*100:.1f}%",
        f"  Post.  P(G | DFI, ESL)  : {post_esl_pg*100:.1f}%   (Δ {delta_esl*100:+.1f} pp)",
        f"  Prior  P(G, Classic)    : {prior_classic.prior_pg*100:.1f}%",
        f"  Post.  P(G | DFI, Cl.)  : {post_classic_pg*100:.1f}%   (Δ {delta_classic*100:+.1f} pp)",
        "",
        "Methodology: Bayesian DFI update via Simm 2016 2-state formula. R is the ratio of "
        "two user-defined normal likelihoods at the observed DHI strength; each Gaussian is "
        "set by its P1/P99 (mean=(P1+P99)/2, sd=(P99-P1)/4.6527). R capped to [0.02, 50].",
    ]
    summary_text = "\n".join(lines)
    st.text_area(
        "Summary text", value=summary_text, height=300,
        key="dfi_summary_text_area_custom", label_visibility="collapsed",
    )
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in prospect_title)
    st.download_button(
        "📥 Download DFI summary (.txt)", data=summary_text,
        file_name=f"{safe_title or 'prospect'}_DFI_custom_summary.txt",
        key="dfi_custom_summary_dl",
    )


def _render_geological_pos_summary(ctx) -> None:
    """Final Prospect POS when the DFI update is **not** applied.

    Shows the geological prior P(G) (ESL mass-rollup and Classic) with its Bel/Pl
    envelope as the reportable final number, plus a Risk Overview and a copy/export
    block — mirroring the DFI summary's layout minus the posterior. Rendered by the
    top-level Final Prospect POS tab when ``dfi_enabled`` is off.
    """
    import datetime

    w_cur = float(ctx.uncertainty_weight)
    prior_classic = _classic_prior_pillars_from_ctx(ctx, w_cur)
    prior_esl_pillars = _esl_prior_pillars_from_ctx_at_w(ctx, w_cur)
    esl_prior_pg = _esl_rollup_prior_at_w(ctx, w_cur)
    bel = ctx.total_for
    pl = 1.0 - ctx.total_against

    prospect_title = st.session_state.get("meta_title") or ctx.prospect_title or "Prospect"
    analyst = st.session_state.get("meta_analyst", "")
    basin = st.session_state.get("meta_basin", "")
    review_date = st.session_state.get("meta_date", str(datetime.date.today()))

    st.markdown(
        f"<div style='background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;"
        f"padding:14px 18px;border-radius:8px;margin-bottom:10px;'>"
        f"<b style='font-size:1.15rem;'>{prospect_title}</b>  "
        f"<span style='opacity:0.7;font-size:0.85rem;'> · Final POS Summary · "
        f"geological prior (no DFI update) · {review_date}</span><br>"
        f"<span style='font-size:0.82rem;opacity:0.85;'>Analyst: {analyst or '—'} · "
        f"Basin: {basin or '—'} · Stance w = {w_cur:.2f}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.info(
        "The **DFI Bayesian update is not applied**, so the final POS below is the "
        "geological prior. To layer in seismic (DHI) evidence, enable the "
        "**DFI-capable prospect?** toggle on the **Dashboard**, then set up the update "
        "on the **Bayesian DFI Update** tab — the posterior will then appear here."
    )

    # ── Risk Overview — geological prior, no DFI rows ──
    from components.prospect_hub import _get_esl_overview_data
    from components.overview_table import render_overview_table
    _ov_data = _get_esl_overview_data({"play": ctx.play, "conditional": ctx.conditional})
    if _ov_data:
        st.markdown("##### Risk Overview — geological prior (per-pillar)")
        render_overview_table("esl", _ov_data)

    # ── Headline POS ──
    st.markdown("##### Prospect POS (geological prior)")
    c1, c2, c3 = st.columns(3)
    c1.metric("P(G, ESL)", f"{esl_prior_pg*100:.1f}%",
              help=f"Headline ESL mass-rollup at stance w = {w_cur:.2f}. "
                   f"∏-pillars Init Pg = {prior_esl_pillars.prior_pg*100:.1f}%.")
    c2.metric("P(G, Classic)", f"{prior_classic.prior_pg*100:.1f}%",
              help="Total prospect Pg via Classic POS at current stance.")
    c3.metric("ESL Bel–Pl envelope", f"{bel*100:.1f}–{pl*100:.1f}%",
              help="Uncertainty envelope from the ESL Italian flag "
                   "(w=0 lower bound → w=1 upper bound).")

    # ── Top-5 weakest elements ──
    st.markdown("##### Top 5 weakest risk elements")
    from components.risk_summary import render_top5_weakest
    render_top5_weakest(ctx.conditional, w_cur, pillar_display=ctx.pillar_display)

    st.divider()

    # ── Reportable text ──
    st.markdown("##### Reportable summary (copy or download)")
    lines = [
        f"Prospect: {prospect_title}",
        f"Analyst : {analyst or '—'}   Basin: {basin or '—'}   Date: {review_date}",
        f"Stance w: {w_cur:.2f}",
        "",
        "DFI update: NOT APPLIED (geological prior only)",
        "",
        "Headline POS:",
        f"  P(G, ESL)     : {esl_prior_pg*100:.1f}%   "
        f"(mass-rollup; ∏-pillars Init Pg = {prior_esl_pillars.prior_pg*100:.1f}%)",
        f"  P(G, Classic) : {prior_classic.prior_pg*100:.1f}%",
        f"  ESL Bel/Pl    : {bel*100:.1f}% – {pl*100:.1f}%",
        "",
        "To include seismic (DHI) evidence, enable the DFI update on the Dashboard "
        "and configure it on the Bayesian DFI Update tab.",
    ]
    summary_text = "\n".join(lines)
    st.text_area("Summary text", value=summary_text, height=240,
                 key="final_pos_geo_text", label_visibility="collapsed")
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in prospect_title)
    st.download_button(
        "📥 Download POS summary (.txt)", data=summary_text,
        file_name=f"{safe_title or 'prospect'}_POS_summary.txt",
        key="final_pos_geo_dl",
    )


# Workbook scaling: GeoX P(DFI|case) = Gaussian-PDF(DHI/100, mean, sd) × 20/100.
# The factor is a constant across classes so it cancels in our internal posterior,
# but GeoX expects the scaled value entered directly.
