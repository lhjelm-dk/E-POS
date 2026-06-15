"""Pure DFI orchestration helpers extracted from ``components.tabs.tab_dfi``.

These are stance/pillar math and report-text builders with no Streamlit
rendering of their own; the DFI UI submodules import them.
"""
from __future__ import annotations

from logic.dfi_context import (
    esl_prior_pillars_from_ctx_at_w   as _esl_prior_pillars_from_ctx_at_w,
    classic_prior_pillars_from_ctx    as _classic_prior_pillars_from_ctx,
    pillar_pairs_from_priorpillars    as _pillar_pairs_from_priorpillars,
)


_GEOX_PDFI_SCALE = 20.0 / 100.0


def geox_pdfi_value(dhi_index: float, calib, class_name: str, sd_mode: str) -> float:
    """P(DFI|case) for one DHI class, scaled to match the SLB GeoX input convention."""
    from logic.dfi_bayes import gaussian_pdf
    cl = calib.classes[class_name]
    return gaussian_pdf(dhi_index / 100.0, cl.mean, cl.sd(sd_mode)) * _GEOX_PDFI_SCALE


def dhi_index_channel_likelihoods(dhi_index: float, calib, sd_mode: str,
                                  fluid_type: str = "Success",
                                  fluid_weights: dict | None = None):
    """Express the Conceptual DHI Index (experimental) evidence in the shared channel language.

    The DHI class names encode the channels directly: the success class
    (``fluid_type`` in Success/Oil/Gas/OilGas) is L_HC; the ``Reservoir_failure``
    class is the reservoir-failure channel (L_nonres); ``H2O_failure`` and
    ``LSG_failure`` are blended by the fluid-failure weights P(fluid|failure) into
    the fluid-failure channel (``other`` shares the LSG class). This makes the
    method pillar-resolved (3-channel), parallel to the Custom multi-case tool.
    """
    from logic.dfi_pillar_update import ChannelLikelihoods
    fluid_weights = fluid_weights or {"water": 0.80, "lsg": 0.20, "other": 0.00}
    v_hc = geox_pdfi_value(dhi_index, calib, fluid_type, sd_mode)
    v_wat = geox_pdfi_value(dhi_index, calib, "H2O_failure", sd_mode)
    v_lsg = geox_pdfi_value(dhi_index, calib, "LSG_failure", sd_mode)
    v_res = geox_pdfi_value(dhi_index, calib, "Reservoir_failure", sd_mode)
    w_w = max(float(fluid_weights.get("water", 0.0)), 0.0)
    w_l = max(float(fluid_weights.get("lsg", 0.0)), 0.0)
    w_o = max(float(fluid_weights.get("other", 0.0)), 0.0)   # 'other' shares LSG_failure
    tot = w_w + w_l + w_o
    l_ff = (w_w * v_wat + (w_l + w_o) * v_lsg) / tot if tot > 0 else v_wat
    return ChannelLikelihoods(l_hc=v_hc, l_fluidfail=l_ff, l_nonres=v_res,
                              method_label="Conceptual DHI Index (experimental)")


def _set_pillar_combined(pillars, pillar_name: str, target: float):
    """Return a new PriorPillars with one pillar's combined Pg set to `target`.

    Strategy: put all uncertainty into the cond slot (play = 1) so the
    combined product equals `target` exactly. This matches the workbook's
    reservoir-sweep behaviour and keeps the Bayes decomposition clean (the
    8-outcome math only sees the pillar product anyway).
    """
    from dataclasses import replace
    target = max(0.0, min(1.0, target))
    play_key = f"{pillar_name}_play"
    cond_key = f"{pillar_name}_cond"
    return replace(pillars, **{play_key: 1.0, cond_key: target})


def _pillars_at_w(ctx, w: float, method: str):
    if method == "ESL":
        return _esl_prior_pillars_from_ctx_at_w(ctx, w)
    return _classic_prior_pillars_from_ctx(ctx, w)


def _dhi_strength_interpretation(r: float, v: float) -> str:
    """One-line plain-English read of the DHI Strength + Volume Weight pair."""
    if r >= 3.0 and v >= 0.70:
        verdict = "**Strong DFI signal in favour of HC** — the DHI Index is far more probable under HC success than under any failure mode."
    elif r >= 1.5 and v >= 0.55:
        verdict = "**Moderate DFI signal in favour of HC** — the DHI Index is more probable under success than failure, but not decisively so."
    elif 0.7 <= r < 1.5:
        verdict = "**Weak / ambiguous DFI signal** — the DHI Index is roughly equally probable under success and failure; the posterior is only marginally shifted from the prior."
    elif r < 0.7:
        verdict = "**DFI signal against HC** — the DHI Index is more probable under failure than success; the posterior is shifted **down** from the prior."
    else:
        verdict = ""
    return (f"{verdict}  *Interpretation thresholds: R≥3.0 strong, R≥1.5 moderate, "
            f"R<1 against. Volume Weight: V≥0.7 high confidence the signal genuinely "
            f"indicates HC.*")


def _build_decision_narrative(prior_e, post_e, prior_c, post_c,
                              r, v, dhi) -> str:
    """Auto-generated paragraph summarising the DFI update for sign-off."""
    de = (post_e - prior_e) * 100
    dc = (post_c - prior_c) * 100
    direction = ("upward" if de > 0 and dc > 0 else
                 "downward" if de < 0 and dc < 0 else
                 "mixed (ESL and Classic in opposite directions — investigate)")
    magnitude = (
        "substantial" if max(abs(de), abs(dc)) > 10 else
        "moderate"    if max(abs(de), abs(dc)) > 3  else
        "marginal"
    )
    method_agreement = (
        "Both methods agree on the direction and magnitude of the update "
        f"(ESL Δ = {de:+.1f}pp, Classic Δ = {dc:+.1f}pp)."
        if (de * dc > 0 and abs(de - dc) < 5)
        else
        f"The two methods give different magnitudes — ESL Δ = {de:+.1f}pp, "
        f"Classic Δ = {dc:+.1f}pp. The spread reflects how each method's "
        "uncertainty propagation responds to the DFI evidence."
    )
    return (
        f"At DHI Index = **{dhi:+.0f}**, the DFI evidence produces a **{magnitude} "
        f"{direction}** update of the geological prior.  \n"
        f"- **P(G, ESL)** moved from {prior_e*100:.1f}% to **{post_e*100:.1f}%** ({de:+.1f}pp)\n"
        f"- **P(G, Classic)** moved from {prior_c*100:.1f}% to **{post_c*100:.1f}%** ({dc:+.1f}pp)\n\n"
        f"R_DFI = **{r:.2f}**, DHI Volume Weight = **{v:.2f}**. "
        f"{method_agreement}"
    )


def build_simm_decision_narrative(prior_e, post_e, prior_c, post_c, r,
                                  *, method_label, evidence_desc) -> str:
    """Decision narrative for the 2-state Simm pathways (characteristic / custom).

    Mirrors :func:`_build_decision_narrative` but is method-agnostic: instead of
    the DHI-Index method's R_DFI / Volume-Weight it reports a single likelihood ratio
    ``r`` plus a free-text ``evidence_desc`` (e.g. "DHI strength = +25" or
    "R_char = 2.4, discernibility high"). ``method_label`` names the source.
    """
    de = (post_e - prior_e) * 100
    dc = (post_c - prior_c) * 100
    direction = ("upward" if de > 0 and dc > 0 else
                 "downward" if de < 0 and dc < 0 else
                 "mixed (ESL and Classic in opposite directions — investigate)")
    magnitude = (
        "substantial" if max(abs(de), abs(dc)) > 10 else
        "moderate"    if max(abs(de), abs(dc)) > 3  else
        "marginal"
    )
    method_agreement = (
        "Both methods agree on the direction and magnitude of the update "
        f"(ESL Δ = {de:+.1f}pp, Classic Δ = {dc:+.1f}pp)."
        if (de * dc > 0 and abs(de - dc) < 5)
        else
        f"The two methods give different magnitudes — ESL Δ = {de:+.1f}pp, "
        f"Classic Δ = {dc:+.1f}pp. The spread reflects how each method's "
        "uncertainty propagation responds to the DFI evidence."
    )
    return (
        f"Using **{method_label}** ({evidence_desc}), the DFI evidence produces a "
        f"**{magnitude} {direction}** update of the geological prior via Simm's "
        f"two-state Bayes.  \n"
        f"- **P(G, ESL)** moved from {prior_e*100:.1f}% to **{post_e*100:.1f}%** ({de:+.1f}pp)\n"
        f"- **P(G, Classic)** moved from {prior_c*100:.1f}% to **{post_c*100:.1f}%** ({dc:+.1f}pp)\n\n"
        f"R = **{r:.2f}**. {method_agreement}"
    )


def _build_summary_text(prospect_title, analyst, basin, review_date, w_cur,
                        dhi, fluid_type, sd_mode, fw,
                        prior_e, post_e, prior_c, post_c, classic_attr,
                        cal_version, cal_is_placeholder,
                        esl_prior_override=None) -> str:
    """Plain-text reportable summary suitable for copy/paste."""
    import datetime
    from logic.dfi_calibration import CLASS_DISPLAY
    esl_prior_pg = prior_e.prior_pg if esl_prior_override is None else esl_prior_override
    de = (post_e.posterior_pg - esl_prior_pg) * 100
    dc = (post_c.posterior_pg - prior_c.prior_pg) * 100
    lines = []
    lines.append("=" * 72)
    lines.append(f"E-POS — DFI Bayesian Posterior Summary")
    lines.append(f"Prospect: {prospect_title}")
    lines.append(f"Date:     {review_date}    Analyst: {analyst or '-'}    "
                 f"Basin: {basin or '-'}")
    lines.append("=" * 72)
    lines.append("")
    lines.append("DFI INPUTS")
    lines.append(f"  DHI Index:                  {dhi:+.0f}")
    lines.append(f"  HC fluid type (DHI class): {CLASS_DISPLAY.get(fluid_type, fluid_type)}")
    lines.append(f"  SD mode:                    {sd_mode}")
    lines.append(f"  Fluid failure weights:      water {fw.water:.0%},  "
                 f"LSG {fw.lsg:.0%},  other {fw.other:.0%}")
    lines.append(f"  Calibration:                v.{cal_version}"
                 f"{' (PLACEHOLDER — replace for production)' if cal_is_placeholder else ''}")
    lines.append(f"  Stance w:                   {w_cur:.2f}")
    lines.append("")
    lines.append("RESULTS — TOTAL P(G)")
    lines.append(f"  P(G, ESL)              :  {esl_prior_pg*100:7.2f}%   "
                 f"(mass-rollup; ∏-pillars Init Pg = {prior_e.prior_pg*100:.1f}%)")
    lines.append(f"  P(G | DFI, ESL)        :  {post_e.posterior_pg*100:7.2f}%  ({de:+.2f}pp)")
    lines.append(f"  P(G, Classic)          :  {prior_c.prior_pg*100:7.2f}%")
    lines.append(f"  P(G | DFI, Classic)    :  {post_c.posterior_pg*100:7.2f}%  ({dc:+.2f}pp)")
    lines.append("")
    lines.append("DIAGNOSTICS")
    lines.append(f"  R_DFI (ESL)         : {post_e.r_dfi:6.2f}")
    lines.append(f"  DHI Volume Weight (ESL)      : {post_e.dhi_volume_weight:6.2f}")
    lines.append(f"  R_DFI (Classic)     : {post_c.r_dfi:6.2f}")
    lines.append(f"  DHI Volume Weight (Classic)  : {post_c.dhi_volume_weight:6.2f}")
    lines.append("")
    lines.append("PER-PILLAR DFI-MODIFIED VALUES (Classic, reservoir-aware log split)")
    rows_classic = list(zip(
        _pillar_pairs_from_priorpillars(prior_c),
        _pillar_pairs_from_priorpillars(classic_attr),
    ))
    for (name, _k, pri), (_n2, _k2, post) in rows_classic:
        lines.append(f"  {name:22s}: {pri*100:6.2f}%  ->  {post*100:6.2f}%   "
                     f"({(post-pri)*100:+.2f}pp)")
    lines.append("")
    lines.append("=" * 72)
    lines.append("Generated by E-POS (Evidence-supported Probability of Success).")
    lines.append("Methodology: Bayesian DFI update with Gaussian likelihoods from the conceptual DHI calibration.")
    return "\n".join(lines)
