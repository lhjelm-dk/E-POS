"""DFI Setup sub-page — inputs, calibration, bell curves, characteristic
scoring. Extracted from ``components.tabs.tab_dfi``.
"""
from __future__ import annotations

import streamlit as st

from logic.dfi_context import (
    esl_prior_pillars_from_ctx        as _esl_prior_pillars_from_ctx,
    esl_rollup_prior_at_w             as _esl_rollup_prior_at_w,
    get_effective_calibration         as _get_effective_calibration,
)

from components.tabs.tab_dfi_panels import (
    _render_geox_pdfi_panel,
    _render_posterior_class_panel,
    _render_calibration_editor,
)


def _render_dfi_setup(ctx) -> None:
    """DFI Setup sub-page — inputs, calibration, 5 bell curves, posterior class panel."""
    import numpy as np
    import plotly.graph_objects as go
    from logic.dfi_calibration import (
        ALL_CLASSES, SUCCESS_CLASSES, CLASS_DISPLAY,
        DHI_INDEX_MIN_INT, DHI_INDEX_MAX_INT,
    )
    from logic.dfi_bayes import (
        FluidWeights, gaussian_pdf, compute_dfi_posterior,
    )

    calib = _get_effective_calibration()

    # ── Top-level: which DFI evidence source drives R? ──
    # Scoped CSS: enlarge this one radio group (marked by the anchor div below).
    st.markdown(
        """
        <style>
        div[data-dfi-source-anchor] + div div[role="radiogroup"] label p {
            font-size: 1.15rem !important; font-weight: 600 !important;
        }
        div[data-dfi-source-anchor] + div div[role="radiogroup"] {
            gap: 2.0rem !important;
        }
        </style>
        <div data-dfi-source-anchor></div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown("### 🔀 DFI evidence source")
        source = st.radio(
            "Choose how the DHI strength R is derived:",
            options=["DHI Index (SAAM)", "Characteristic scoring (Monigle 2025)",
                     "Custom R tool"],
            horizontal=True,
            key="dfi_source_radio",
            label_visibility="visible",
            help=(
                "Three mutually-exclusive ways to derive the DHI strength R:\n\n"
                "• **DHI Index (SAAM)** — enter the composite DHI Index from an external "
                "SAAM/SaRA scoring sheet; the app computes R via Gaussian likelihoods over "
                "the SAAM calibration classes (8-outcome Bayes, per-pillar attribution available).\n\n"
                "• **Characteristic scoring (Monigle 2025)** — score the prospect on five DHI "
                "attributes using a 5-step verbal scale; R is the product of per-attribute "
                "likelihood ratios from the Monigle 2025 drilled-prospect database. Simpler "
                "two-state Bayes; no per-pillar attribution. Stand-alone — no SAAM needed.\n\n"
                "• **Custom R tool** — define your own two bell curves for P(DFI | HC) and "
                "P(DFI | No-HC) by their min/max (P1/P99), read R off a DHI-strength slider. "
                "Fully transparent, no external calibration. Two-state Bayes."
            ),
        )
    # Persist for downstream pages
    if source.startswith("Characteristic"):
        st.session_state["dfi_source"] = "characteristic"
    elif source.startswith("Custom"):
        st.session_state["dfi_source"] = "custom"
    else:
        st.session_state["dfi_source"] = "dhi_index"

    # Branch — Characteristic / Custom modes handled by their own renderers.
    if st.session_state["dfi_source"] == "characteristic":
        _render_dfi_setup_characteristic(ctx)
        return
    if st.session_state["dfi_source"] == "custom":
        _render_dfi_setup_custom(ctx)
        return

    # ── Header strip: calibration source + override status ──
    src_text = f"**Calibration:** v.{calib.version}"
    if calib.is_placeholder:
        st.warning(
            f"{src_text} — ⚠️ **placeholder values in use**. "
            "Replace with proprietary calibration at `data/saam_calibration.json` for production use."
        )
    else:
        st.caption(f"{src_text} (source: {calib.source}). "
                   f"Override active: {'yes' if st.session_state.get('dfi_calibration_override') else 'no'}")

    # ── INPUTS (left) | LIKELIHOOD CURVES (right) ──
    col_inputs, col_viz = st.columns([1, 2])

    # ─── Column A: Inputs ────────────────────────────────────────────────
    with col_inputs:
        st.markdown("##### Inputs")

        dhi = st.slider(
            "**DHI Index**",
            min_value=DHI_INDEX_MIN_INT,
            max_value=DHI_INDEX_MAX_INT,
            value=int(st.session_state.get("dfi_index", 19)),
            step=1, key="dfi_index",
            help=(f"DHI Index from SAAM scoring "
                  f"(range {DHI_INDEX_MIN_INT} to {DHI_INDEX_MAX_INT}). "
                  "Higher = stronger DFI signal supporting HC presence."),
        )

        fluid_type = st.selectbox(
            "**Expected HC fluid type**",
            options=list(SUCCESS_CLASSES),
            format_func=lambda x: CLASS_DISPLAY.get(x, x),
            index=list(SUCCESS_CLASSES).index(
                st.session_state.get("dfi_fluid_type", "Success")
            ),
            key="dfi_fluid_type",
            help=("SAAM class supplying the success-side likelihood. "
                  "'HC Success' is the aggregate (default); pick Oil/Gas/OilGas if "
                  "the prospect has a specific expected fluid type."),
        )

        # ── Advanced / Research controls (demoted — sensible defaults apply) ──
        st.caption(
            "Standard inputs above drive the update. The defaults below "
            "(conservative SD, water-dominated failure mix, attribution A) suit "
            "most prospects — open **Advanced** only to override them."
        )
        with st.expander("⚙️ Advanced / Research inputs — SD mode · fluid mix · attribution",
                         expanded=False):
            sd_mode = st.radio(
                "**SD mode**",
                options=["upper", "calculated"],
                format_func=lambda x: ("Upper (conservative)" if x == "upper"
                                       else "Calculated (sample SD)"),
                index=0 if st.session_state.get("dfi_sd_mode", "upper") == "upper" else 1,
                key="dfi_sd_mode",
                horizontal=True,
                help=("Upper = chi-squared upper-confidence-bound SD (default — widens "
                      "the likelihoods and is conservative). Calculated = the raw sample SD."),
            )

            st.markdown("**Fluid failure probabilities**  *P(fluid | failure)*")
            col_w, col_l, col_o = st.columns(3)
            with col_w:
                water = st.number_input(
                    "Water", min_value=0.0, max_value=1.0,
                    value=float(st.session_state.get("dfi_fluid_water", 0.80)),
                    step=0.05, format="%.2f", key="dfi_fluid_water",
                )
            with col_l:
                lsg = st.number_input(
                    "LSG", min_value=0.0, max_value=1.0,
                    value=float(st.session_state.get("dfi_fluid_lsg", 0.20)),
                    step=0.05, format="%.2f", key="dfi_fluid_lsg",
                )
            with col_o:
                other = st.number_input(
                    "Other", min_value=0.0, max_value=1.0,
                    value=float(st.session_state.get("dfi_fluid_other", 0.00)),
                    step=0.05, format="%.2f", key="dfi_fluid_other",
                )
            total_w = water + lsg + other
            if abs(total_w - 1.0) > 0.001:
                st.caption(f"⚠️ Sum = **{total_w:.2f}** — will be auto-normalised to 1.00 in the Bayesian calc.")
            else:
                st.caption(f"Sum = {total_w:.2f} ✓")
            st.caption(
                "💡 Not sure about the fluid mix? Use the **Sensitivity sweep** on the "
                "**DFI Results** tab (X = DHI Index, family = Water failure fraction) to "
                "stress-test it — if the curves bunch together, your choice barely matters; "
                "if they fan out, justify it in the audit trail."
            )

            st.markdown("**ESL per-pillar attribution method**")
            esl_attr = st.radio(
                "Attribution",
                options=["A", "B"],
                format_func=lambda x: ("A: equal multiplicative (preserve commitment C)"
                                       if x == "A"
                                       else "B: Bel/Pl-preserving"),
                index=0 if st.session_state.get("dfi_esl_attribution", "A") == "A" else 1,
                key="dfi_esl_attribution",
                label_visibility="collapsed",
                help=("How the posterior P(G | DFI, ESL) is distributed back to per-pillar "
                      "(S_for, S_against) masses. A = simpler, scales each pillar Pg by "
                      "ratio^(1/8) and round-trips the masses keeping commitment C fixed. "
                      "B = computes posterior at w=0 and w=1 separately to update Bel/Pl."),
            )

        # Defaults so downstream code works whether or not the drawer was opened.
        sd_mode = str(st.session_state.get("dfi_sd_mode", "upper"))
        water = float(st.session_state.get("dfi_fluid_water", 0.80))
        lsg   = float(st.session_state.get("dfi_fluid_lsg",   0.20))
        other = float(st.session_state.get("dfi_fluid_other", 0.00))

    # ─── Column B: 5 bell curves ─────────────────────────────────────────
    with col_viz:
        st.markdown("##### Likelihood distributions — P(DFI Index | outcome class)")

        # Curve definitions (5 outcome categories; Other shares LSG_failure stats)
        curves = [
            ("HC Success",          fluid_type,           "#16a34a", "solid"),
            ("Water failure",       "H2O_failure",        "#2563eb", "solid"),
            ("LSG failure",         "LSG_failure",        "#eab308", "solid"),
            ("Other failure",       "LSG_failure",        "#9333ea", "dot"),
            ("Reservoir failure",   "Reservoir_failure",  "#dc2626", "solid"),
        ]

        x_int = np.arange(DHI_INDEX_MIN_INT, DHI_INDEX_MAX_INT + 1)
        x_fine = np.linspace(DHI_INDEX_MIN_INT - 1, DHI_INDEX_MAX_INT + 1, 400)
        fig = go.Figure()
        for label, class_name, color, dash in curves:
            stats = calib.classes[class_name]
            mu, sigma = stats.mean, stats.sd(sd_mode)
            y = np.array([gaussian_pdf(xi / 100.0, mu, sigma) for xi in x_fine])
            fig.add_trace(go.Scatter(
                x=x_fine, y=y, mode="lines",
                line=dict(color=color, width=2.2, dash=dash),
                name=f"{label}  (μ={mu*100:.1f}, σ={sigma*100:.1f})",
                hovertemplate=f"<b>{label}</b><br>DHI=%{{x:.0f}}<br>P(DFI|class)=%{{y:.3f}}<extra></extra>",
            ))
        # Vertical marker at the current DHI Index
        fig.add_vline(
            x=dhi, line_width=2, line_dash="dash", line_color="#1f2937",
            annotation_text=f"DHI = {dhi}", annotation_position="top",
            annotation_font=dict(size=11, color="#1f2937"),
        )
        fig.update_layout(
            xaxis=dict(title="DHI Index", range=[DHI_INDEX_MIN_INT - 1, DHI_INDEX_MAX_INT + 1],
                       dtick=5, showgrid=True, gridcolor="#e5e7eb"),
            yaxis=dict(title="P(DFI | class) — Gaussian PDF",
                       showgrid=True, gridcolor="#e5e7eb"),
            height=380, margin=dict(t=10, b=40, l=50, r=20),
            legend=dict(orientation="h", yanchor="top", y=-0.18,
                        xanchor="center", x=0.5, font=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Five outcome-class likelihoods. **LSG and Other share the same SAAM "
            "distribution** (LSG/other failure column) — the dotted purple curve "
            "for Other overlays the yellow LSG curve. The Gaussian PDF is used "
            "rigorously (no frequency scaling)."
        )

    # ── Posterior class panel (using ESL prior) ──
    st.divider()
    st.markdown("##### Posterior outcome probabilities at current DHI  *(using ESL prior)*")
    fluid_weights = FluidWeights(water=water, lsg=lsg, other=other)
    prior_esl = _esl_prior_pillars_from_ctx(ctx)
    _esl_rollup = _esl_rollup_prior_at_w(ctx, float(ctx.uncertainty_weight))
    post_esl = compute_dfi_posterior(prior_esl, dhi, calib, fluid_weights, sd_mode,
                                     fluid_type, prior_pg_override=_esl_rollup)
    _render_posterior_class_panel(post_esl, fluid_weights)

    # ── DHI strength R — shared verdict + Simm band strip (parity with the other
    #    two evidence sources). R_SAAM is the SAAM 8-outcome likelihood ratio. ──
    from components.dfi_shared import (
        render_rscore_metrics, render_simm_verdict_banner, render_simm_band_strip,
    )
    from logic.dfi_simm import dhi_score_from_r as _dhi_score_from_r
    st.divider()
    st.markdown("##### DHI strength R — Simm rule-of-thumb verdict")
    _r_saam = float(post_esl.r_saam)
    render_rscore_metrics(
        _r_saam, _dhi_score_from_r(_r_saam) * 100.0,
        r_label="R_SAAM",
        r_help="L_success / E[L | failure] from the SAAM 8-outcome likelihoods (ESL prior).",
    )
    render_simm_verdict_banner(_r_saam)
    render_simm_band_strip(_r_saam, key="dfi_dhiindex_band_strip")

    # ── GeoX hand-off: the 6 P(DFI|case) values to type into SLB GeoX ──
    st.divider()
    _render_geox_pdfi_panel(dhi, calib, sd_mode, fluid_type)

    # ── Calibration editor (collapsed by default) ──
    with st.expander("📐 Edit calibration values (live update affects bell curves and posteriors)", expanded=False):
        _render_calibration_editor(calib)


# ─────────────────────────────────────────────────────────────────────────────
# Characteristic-scoring DFI Setup (Monigle 2025 — alternative to SAAM DHI Index)
# ─────────────────────────────────────────────────────────────────────────────

def _render_dfi_setup_characteristic(ctx) -> None:
    """Six-slider DFI characteristic-scoring panel — Monigle 2025 pathway."""
    import math
    import pandas as pd
    import plotly.graph_objects as go
    from logic.dhi_characteristics import (
        load_characteristic_stats, compute_r_char, compute_r_char_inferred,
        apply_discernibility, simm_bayes_posterior, dhi_score_from_r,
        inferred_success_curve, inferred_success_rate_at, inferred_lr_at,
        SIMM_RULE_OF_THUMB, R_HARD_CAP, R_FLOOR,
    )

    try:
        cstats = load_characteristic_stats()
    except FileNotFoundError as e:
        st.error(f"DHI characteristic stats file missing: {e}")
        return

    # ── Attribute set (Monigle 2025) ──
    # The app ships the current 5-attribute set (2021+ production iCOS). The code
    # stays mode-generic: if the stats file ever defines more than one mode, a
    # selector is shown; with a single mode the choice is fixed (no toggle).
    mode_options = list(cstats.modes.values())
    mode_keys    = [m.key for m in mode_options]
    default_key  = "5_current" if "5_current" in mode_keys else mode_keys[0]
    if len(mode_options) > 1:
        mode_labels = [m.label for m in mode_options]
        sess_key = st.session_state.get("dhi_char_mode", default_key)
        idx = mode_keys.index(sess_key) if sess_key in mode_keys \
            else mode_keys.index(default_key)
        chosen_label = st.radio(
            "**Attribute set**",
            options=mode_labels,
            index=idx,
            horizontal=True,
            key="dhi_char_mode_radio",
            help="Monigle 2025 attribute set used for characteristic scoring.",
        )
        mode_key = mode_keys[mode_labels.index(chosen_label)]
    else:
        mode_key = default_key
    st.session_state["dhi_char_mode"] = mode_key
    mode_info = cstats.modes[mode_key]

    active_attrs = cstats.attributes_for_mode(mode_key)
    n_total     = len(active_attrs)
    n_in_r      = sum(1 for a in active_attrs.values() if a.in_r_calc)
    placeholder_count = sum(1 for a in active_attrs.values() if a.placeholder)

    if placeholder_count > 0:
        st.warning(
            f"⚠️ {placeholder_count} of {n_total} attributes use **placeholder counts** "
            "(flat LR ≈ 1 across categories) pending ingestion of Monigle Figure 3. "
            "R will only respond to attributes with real data — score them all anyway so "
            "the radar reflects the full assessment."
        )

    st.caption(
        f"**Mode:** {mode_info.label}. **Calibration:** {cstats.version}. "
        f"{n_total} attributes visible · {n_in_r} contribute to R "
        f"(confidence attributes are display-only per Monigle 2025 finding)."
    )

    # ── Statistics interpretation: Raw discrete vs Inferred (smoothed) ──
    interp_label = st.radio(
        "**Statistics interpretation**",
        options=["Raw (discrete categories)", "Inferred (smoothed · seamless)"],
        index=1 if st.session_state.get("dhi_char_inferred", False) else 0,
        horizontal=True,
        key="dhi_char_interp_radio",
        help=(
            "**Raw** uses Monigle's per-category counts verbatim — faithful to the "
            "data, including genuine non-monotonic quirks (e.g. *Fair* out-performing "
            "*Good* on fluid-contact-reflection because of small-N).\n\n"
            "**Inferred** treats the five verbal categories as ordinal anchors of an "
            "underlying success-rate curve. It Laplace-smooths each category rate, then "
            "applies **weighted isotonic regression** (pool-adjacent-violators) so the "
            "rate never decreases Poor→Excellent (Good ≥ Fair), and interpolates a "
            "near-continuous slider. The likelihood ratio at any position comes from the "
            "monotone success-rate odds — so the slider is seamless and the evidence "
            "behaves monotonically."
        ),
    )
    inferred = interp_label.startswith("Inferred")
    st.session_state["dhi_char_inferred"] = inferred

    # ─── Two-column layout: sliders | results ───────────────────────────────
    col_in, col_out = st.columns([1.2, 1])

    # ── Column A: attribute sliders (filtered by mode) + discernibility ──
    selections: dict[str, str] = {}   # nearest verbal category (display/radar/plots)
    positions:  dict[str, float] = {}  # continuous slider position x∈[0,1]
    with col_in:
        st.markdown(f"##### Score the prospect on {n_total} DHI attributes")
        _rel_mid_now = bool(st.session_state.get("dhi_char_rel_middle", False))
        _anchor_caption = (
            "Each slider's **middle** position is the neutral / non-informative baseline "
            "(LR = 1); moving toward the ends pushes R up or down. *(Scale-middle anchoring "
            "is ON — see the controls below.)*"
            if _rel_mid_now else
            "Each category maps to a likelihood ratio measured **vs the dataset base rate**: "
            "a category whose success rate equals the overall base rate gives LR = 1, above "
            "it lifts R, below it lowers R. So the *middle* category is **not** automatically "
            "neutral — its own success rate decides. *(Switch to scale-middle anchoring in the "
            "controls below if you want the middle category pinned to LR = 1.)*"
        )
        st.caption(
            _anchor_caption
            + ("  \n*Inferred mode:* the slider is continuous; the verbal category and "
               "monotone success rate under the handle are shown beneath each slider."
               if inferred else "")
        )

        # Group attributes by role for visual organisation
        groups = [
            ("Quality (drives R)",       [k for k, a in active_attrs.items() if a.in_r_calc]),
            ("Confidence (radar only)",  [k for k, a in active_attrs.items() if not a.in_r_calc]),
        ]
        both_populated = all(len(gk) > 0 for _g, gk in groups)
        for grp_label, grp_keys in groups:
            if not grp_keys:
                continue
            if both_populated:
                st.markdown(f"**{grp_label}**")
            for key in grp_keys:
                attr = active_attrs[key]
                cats = attr.categories(mode_key)
                K = len(cats)
                mid_idx = K // 2
                label = attr.display_name + (" 🟡" if attr.placeholder else "")
                if inferred:
                    # Continuous 0..1 slider (100 steps), mode-suffixed key
                    pos_key = f"dhi_char_pos_{key}_{mode_key}"
                    x = float(st.session_state.get(pos_key, 0.5))
                    x = st.slider(
                        label, 0.0, 1.0, x, 0.01, key=pos_key,
                        help=attr.comment if attr.comment else None,
                    )
                    idx = int(round(x * (K - 1)))
                    positions[key] = x
                    selections[key] = cats[idx]
                    sr = inferred_success_rate_at(attr, mode_key, x) * 100.0
                    st.caption(
                        f"↳ nearest category **{cats[idx]}** · monotone success rate "
                        f"≈ **{sr:.0f}%**"
                        + ("" if attr.in_r_calc else " · *display only*")
                    )
                else:
                    # Mode-suffixed session key so user keeps separate settings per mode
                    sess_key = f"dhi_char_{key}_{mode_key}"
                    stored = st.session_state.get(sess_key)
                    value = stored if stored in cats else cats[mid_idx]
                    sel = st.select_slider(
                        label,
                        options=cats,
                        value=value,
                        key=sess_key,
                        help=attr.comment if attr.comment else None,
                    )
                    selections[key] = sel
                    positions[key] = (cats.index(sel) / (K - 1)) if K > 1 else 0.5

        st.markdown("---")
        st.markdown("##### Discernibility (Monigle weighting)")
        st.caption(
            "How much should the DFI evidence be allowed to move the prior? "
            "Low discernibility (poor data quality or DFI not plausibly visible) "
            "squashes R toward 1 — the absence of effect."
        )
        cE, cC = st.columns(2)
        with cE:
            expectation = st.selectbox(
                "Expectations",
                ["likely", "more likely than not", "less likely than not", "unlikely"],
                index=0, key="dhi_char_expectation",
                help="Would we *expect* to see a DFI on this prospect type, given "
                     "container, rock properties, fluid contrast?",
            )
        with cC:
            confidence = st.selectbox(
                "Confidence",
                ["high", "moderate", "low", "no"],
                index=0, key="dhi_char_confidence",
                help="Is the seismic data quality sufficient to discriminate a real "
                     "DFI from artefact?",
            )
        # Combine to one bucket — least common denominator (per Monigle Fig.6 matrix)
        rank = {"likely": 3, "more likely than not": 2, "less likely than not": 1, "unlikely": 0,
                "high": 3, "moderate": 2, "low": 1, "no": 0}
        bucket_index = min(rank[expectation], rank[confidence])
        bucket_name = ["absent", "low", "moderate", "high"][bucket_index]
        bucket = cstats.buckets[bucket_name]
        st.caption(f"→ Combined discernibility: **{bucket_name}** (d = {bucket.d:.1f}) "
                   f"— {bucket.description}")

        st.markdown("---")
        apply_cap = st.checkbox(
            f"Apply Simm 2016 cap on R  [{R_FLOOR:.2f}, {R_HARD_CAP:.1f}]",
            value=bool(st.session_state.get("dhi_char_apply_cap", True)),
            key="dhi_char_apply_cap",
            help=(
                "Simm (2016) found empirically that SAAM-style R rarely exceeds ~3 "
                "(or falls below ~1/3) for real prospects. Enabling this clamps the "
                "naive-product R into that band as a guard against implausible values.\n\n"
                "**Default ON.** The per-attribute LRs are multiplied under a naive "
                "conditional-independence assumption, but the DHI attributes are strongly "
                "correlated (the reason Monigle 2025 moved to ML). The uncapped product "
                "therefore over-counts evidence — it can run to R≈270+ or collapse to 0 "
                "from a single DHI. The cap is the defensible default; turn it OFF only "
                "to inspect the raw, unconstrained product."
            ),
        )
        if not apply_cap:
            st.warning(
                "⚠️ **Capping is OFF.** The naive-independence product can produce "
                "implausible R (very large, or →0) because the DHI attributes are "
                "correlated and the product double-counts shared evidence. Treat the "
                "uncapped posterior as a diagnostic, not a reportable result."
            )

        st.markdown("---")
        rel_middle = st.checkbox(
            "Anchor R to the scale-middle category (legacy)",
            value=bool(st.session_state.get("dhi_char_rel_middle", False)),
            key="dhi_char_rel_middle",
            help=(
                "**Default OFF — base-rate-relative (recommended).** Each attribute's "
                "likelihood ratio is odds(category) / odds(base rate): a category whose "
                "success rate equals the dataset's overall rate contributes LR = 1, above "
                "it lifts, below it downgrades. This is the conceptually correct Bayesian "
                "evidential strength.\n\n"
                "**ON — scale-middle anchoring (legacy UX).** Re-anchors so the *middle "
                "verbal category* of each scale is forced to LR = 1 (an all-middle "
                "selection then yields R = 1). Convenient for the slider, but it discards "
                "real evidence when the middle category is itself far from the base rate "
                "— e.g. fluid-contact-reflection 'Fair' (82 % vs a 56 % base) is the "
                "middle, so this mode reports it as neutral instead of a 3.25× uplift."
            ),
        )
        if rel_middle:
            st.info(
                "ℹ️ **Scale-middle anchoring is ON (legacy).** R is measured relative to "
                "each attribute's middle category, not the base rate. A 'Fair' fluid "
                "contact reflection (82 % success) will read as **neutral** here because "
                "Fair is the middle. Turn this OFF for the base-rate-relative Bayesian LR."
            )

    # ── Compute ──
    rel_middle = bool(st.session_state.get("dhi_char_rel_middle", False))
    cap_kw = (dict(hard_cap=R_HARD_CAP, floor=R_FLOOR) if apply_cap
              else dict(hard_cap=float("inf"), floor=0.0))
    if inferred:
        r_res = compute_r_char_inferred(cstats, positions, mode_key=mode_key,
                                        relative_to_middle=rel_middle, **cap_kw)
    else:
        r_res = compute_r_char(cstats, selections, mode_key=mode_key,
                               relative_to_middle=rel_middle, **cap_kw)
    r_char  = r_res["r_char"]                  # capped, before discernibility
    r_raw   = r_res["raw_r"]
    r_eff   = apply_discernibility(r_char, bucket)
    score   = dhi_score_from_r(r_eff) * 100.0
    # Use the prospect's headline ESL prior (mass-rollup P(G, ESL) at current stance)
    # as the prior for the Simm 2-state Bayes update — the same number booked elsewhere,
    # NOT the ∏-pillars Init Pg (kept separately below for the 8-outcome diagnostic).
    prior_esl_pillars = _esl_prior_pillars_from_ctx(ctx)
    init_pg_unscaled  = prior_esl_pillars.prior_pg
    prior_pg = _esl_rollup_prior_at_w(ctx, float(ctx.uncertainty_weight))
    post_pg = simm_bayes_posterior(prior_pg, r_eff)

    # Persist for downstream pages
    st.session_state["dhi_char_r_char"]     = r_char
    st.session_state["dhi_char_r_eff"]      = r_eff
    st.session_state["dhi_char_score"]      = score
    st.session_state["dhi_char_posterior"]  = post_pg
    st.session_state["dhi_char_prior"]      = prior_pg
    st.session_state["dhi_char_bucket"]     = bucket_name
    st.session_state["dhi_char_selections"] = dict(selections)
    st.session_state["dhi_char_positions"]  = dict(positions)
    st.session_state["dhi_char_inferred"]   = inferred

    # ── Column B: Results & diagnostics ──
    with col_out:
        st.markdown("##### Results")
        m1, m2 = st.columns(2)
        with m1:
            _rlabel = "R_char (capped)" if apply_cap else "R_char"
            _rhelp = (f"Naive-independence product of the LRs (raw = {r_raw:.2f}). "
                      + (f"Hard-capped to [{R_FLOOR:.2f}, {R_HARD_CAP:.1f}] per Simm 2016."
                         if apply_cap else
                         "Capping is OFF — shown unconstrained. Enable the Simm cap "
                         "below the sliders for a bounded value."))
            st.metric(_rlabel, f"{r_char:.2f}", help=_rhelp)
            st.metric("R_effective", f"{r_eff:.2f}",
                      delta=f"d = {bucket.d:.1f}",
                      help="R_char after discernibility squash: R_eff = R_char^d. "
                           "Drives the Bayes update.")
        with m2:
            st.metric("DHI Characteristic Score", f"{score:.0f}%",
                      help="Monigle-style 0–100 % score = R_eff / (R_eff + 1). "
                           "Equivalent to Bayes posterior at a 50/50 neutral prior.")
            st.metric("Prior → Posterior",
                      f"{post_pg*100:.1f}%",
                      delta=f"{(post_pg - prior_pg)*100:+.1f} pp",
                      help=f"Simm 2-state Bayes update of the ESL prior "
                           f"({prior_pg*100:.1f}%) using R_eff.")
        if r_res["was_capped"]:
            st.caption(f"⚠️ Raw product was {r_raw:.2f} — capped to {r_char:.2f} "
                       f"(Simm 2016 empirical maximum).")
        st.caption(
            "**Conditional-independence caveat:** these six attributes correlate in "
            "reality (which is why Monigle 2025 moved to ML for their iCOS score). "
            "The naive product is an *upper-bound-ish* estimate; the cap protects "
            "against implausible R values."
        )

    # ── DHI strength R — shared verdict + Simm band strip (parity across sources).
    #    R_eff is the post-discernibility ratio that drives the Bayes update. ──
    from components.dfi_shared import (
        render_simm_verdict_banner as _render_simm_verdict_banner,
        render_simm_band_strip as _render_simm_band_strip,
    )
    st.markdown("##### DHI strength R — Simm rule-of-thumb verdict")
    _render_simm_verdict_banner(r_eff)
    _render_simm_band_strip(r_eff, key="dfi_char_band_strip")

    # ── Per-attribute LR bars (only attributes active in current mode) ──
    st.markdown("##### Per-attribute LR contributions")
    _anchor_lbl = "vs scale-middle" if rel_middle else "vs base rate"
    # Fixed symmetric log₁₀(LR) frame so bars don't rescale as sliders move. Bars
    # beyond the frame are clamped to the edge and flagged with a ‹/› caret + their
    # true value, so a strong attribute is never silently hidden.
    _LR_LOG_RANGE = 0.6           # LR ∈ [10^-0.6, 10^0.6] ≈ [0.25, 3.98]
    bar_data = []
    for key, attr in active_attrs.items():
        lr = r_res["per_attribute_lr"].get(key, 1.0)
        sel = selections.get(key, "—")
        log_lr = math.log10(max(lr, 1e-6))
        clamped = max(-_LR_LOG_RANGE, min(_LR_LOG_RANGE, log_lr))
        over = abs(log_lr) > _LR_LOG_RANGE + 1e-9
        caret = ("›" if log_lr > 0 else "‹") if over else ""
        bar_data.append({
            "Attribute": attr.display_name + (" (display only)" if not attr.in_r_calc else ""),
            "Selected": sel, "LR": lr, "log10 LR": log_lr,
            "clamped": clamped, "over": over, "caret": caret,
        })
    bar_df = pd.DataFrame(bar_data)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=bar_df["clamped"], y=bar_df["Attribute"],
        orientation="h",
        marker=dict(
            color=["#16a34a" if v > 0 else "#dc2626" for v in bar_df["log10 LR"]],
            line=dict(color="#111827", width=0.5),
        ),
        text=[f"{caret}{lr:.2f} ({sel})"
              for caret, lr, sel in zip(bar_df["caret"], bar_df["LR"], bar_df["Selected"])],
        textposition="outside", cliponaxis=False,
        customdata=bar_df["log10 LR"],
        hovertemplate="%{y}<br>LR = %{text}<br>log₁₀ = %{customdata:.2f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#6b7280", line_width=1)
    # Simm threshold guides at ±log10(1.5) and ±log10(3) (within the ±0.6 frame).
    for _thr in (1.5, 3.0):
        for _s in (1.0, -1.0):
            fig.add_vline(x=_s * math.log10(_thr), line_dash="dot",
                          line_color="#cbd5e1", line_width=1)
    _ticks = [(1/3, "0.33"), (1/1.5, "0.67"), (1.0, "1"), (1.5, "1.5"), (3.0, "3")]
    fig.update_xaxes(
        range=[-_LR_LOG_RANGE, _LR_LOG_RANGE],
        tickmode="array",
        tickvals=[math.log10(v) for v, _ in _ticks],
        ticktext=[t for _, t in _ticks],
        title_text=f"LR ({_anchor_lbl}) — left = unfavourable, right = favourable  "
                   f"[fixed log₁₀ scale ±{_LR_LOG_RANGE}]",
    )
    fig.update_layout(height=260, margin=dict(t=10, b=40, l=10, r=10),
                      yaxis_title=None, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Green bars favour success (LR > 1); red bars favour failure (LR < 1), measured "
        f"**{_anchor_lbl}**. The axis is a **fixed** log₁₀ frame (±{_LR_LOG_RANGE}, i.e. "
        f"LR 0.25–3.98) so bars stay comparable as you move sliders; a **‹/› caret** marks "
        "an attribute whose LR runs past the frame (its true value is still labelled). The "
        "total R_char is the product — the sum on this log scale. Confidence attributes (if "
        "shown) are pinned to LR = 1 and do not move R."
    )

    # ── Per-attribute success-rate "small multiples" (the data behind each LR) ──
    from components.colors import cos_color as _cos
    with st.expander("📊 Per-attribute success rates — the drilled-prospect data behind each LR",
                     expanded=False):
        st.caption(
            "For each attribute: the **observed success rate** of every verbal category "
            "in Monigle's drilled-prospect database (bar height & colour on the shared "
            "Probability scale). The outlined bar with the ▲ marker is your current "
            "slider position. This is the empirical signal the likelihood ratios are "
            "built from — note that it is **not always monotonic** (small-N categories "
            "can buck the trend; see the fluid-contact-reflection note)."
            + ("  \n\n**Inferred mode is ON:** the **dark line** is the *monotone "
               "(isotonic) success-rate curve* actually used for scoring — it pools any "
               "out-of-order categories (e.g. Fair/Good) so the rate never decreases."
               if inferred else
               "  \n\nThe **dotted grey line** is the *monotone (isotonic) fit* for "
               "reference — it is **not** used while Raw scoring is selected, but shows "
               "what would change if you toggled Inferred on (it removes non-monotonic "
               "dips like Fair > Good).")
        )
        attr_items = list(active_attrs.items())
        per_row = 3
        for row_start in range(0, len(attr_items), per_row):
            row_items = attr_items[row_start:row_start + per_row]
            cols = st.columns(len(row_items))
            for (key, attr), col in zip(row_items, cols):
                ms = attr.stats_for(mode_key)
                cats = ms.categories
                sel = selections.get(key, cats[len(cats) // 2])
                sel_idx = cats.index(sel) if sel in cats else len(cats) // 2
                rates, labels, colors, widths = [], [], [], []
                for i, c in enumerate(cats):
                    s, f = ms.success[i], ms.failure[i]
                    n = s + f
                    rate = (s / n) if n > 0 else 0.0
                    rates.append(rate * 100.0)
                    labels.append(f"{rate*100:.0f}%<br><span style='font-size:9px'>n={n}</span>")
                    colors.append(_cos(rate))
                    widths.append(2.4 if i == sel_idx else 0.5)
                figm = go.Figure()
                figm.add_trace(go.Bar(
                    x=cats, y=rates,
                    marker=dict(color=colors,
                                line=dict(color=["#111827" if i == sel_idx else "#cbd5e1"
                                                 for i in range(len(cats))],
                                          width=widths)),
                    text=[f"{r:.0f}%" for r in rates],
                    textposition="outside", cliponaxis=False,
                    hovertemplate="%{x}<br>Success rate %{y:.0f}%<extra></extra>",
                ))
                # Always overlay the monotone (isotonic) inferred success-rate curve.
                # Dark/solid when Inferred scoring is ON (it's the curve actually used);
                # greyed/dashed when OFF (shown for reference — Raw bars drive scoring).
                mono = inferred_success_curve(attr, mode_key)
                if inferred:
                    _curve_line = dict(color="#1f2937", width=2)
                    _curve_mark = dict(size=6, color="#1f2937")
                    _curve_name = "Monotone (inferred — in use)"
                else:
                    _curve_line = dict(color="#9ca3af", width=1.5, dash="dot")
                    _curve_mark = dict(size=5, color="#9ca3af")
                    _curve_name = "Monotone (inferred — reference, off)"
                figm.add_trace(go.Scatter(
                    x=cats, y=[m * 100.0 for m in mono],
                    mode="lines+markers",
                    line=_curve_line, marker=_curve_mark,
                    name=_curve_name,
                    hovertemplate="%{x}<br>Inferred rate %{y:.0f}%<extra></extra>",
                    showlegend=False,
                ))
                # ▲ marker over the selected category
                figm.add_trace(go.Scatter(
                    x=[cats[sel_idx]], y=[rates[sel_idx] + 9],
                    mode="markers", marker=dict(symbol="triangle-down", size=12,
                                                color="#111827"),
                    hoverinfo="skip", showlegend=False,
                ))
                placeholder_tag = " 🟡" if attr.placeholder else ""
                figm.update_layout(
                    title=dict(text=attr.display_name + placeholder_tag,
                               font=dict(size=12), x=0.0),
                    height=240, margin=dict(t=34, b=60, l=30, r=10),
                    yaxis=dict(title=None, range=[0, 112], ticksuffix="%",
                               showgrid=True, gridcolor="#eef2f7"),
                    xaxis=dict(tickangle=-35, tickfont=dict(size=9)),
                    showlegend=False, bargap=0.25,
                )
                col.plotly_chart(figm, use_container_width=True)

    # ── Radar plot of slider positions (Monigle-style) ──
    _ptitle = st.session_state.get("meta_title") or getattr(ctx, "prospect_title", None) or "prospect"
    st.markdown(f"##### Radar of slider positions — {_ptitle}")
    from components.colors import cos_color
    radar_attrs = list(active_attrs.values())
    # Map each selection to its 1-N category index (then displayed as the integer)
    radar_axis_labels = [a.display_name for a in radar_attrs]
    radar_values = []
    radar_rates  = []     # per-attribute success rate of the selected category
    radar_colors = []     # cos-scale colour for that success rate
    n_cats = max((len(a.categories(mode_key)) for a in radar_attrs), default=5)
    for a in radar_attrs:
        cats = a.categories(mode_key)
        K = len(cats)
        if inferred:
            x = float(positions.get(a.key, 0.5))
            radar_values.append(1.0 + x * (K - 1))   # continuous 1..N
            rate = inferred_success_rate_at(a, mode_key, x)
        else:
            sel = selections.get(a.key, cats[K // 2])
            idx = cats.index(sel) if sel in cats else K // 2
            radar_values.append(idx + 1)   # 1-based: 1=worst, N=best
            ms = a.stats_for(mode_key)
            s, f = ms.success[idx], ms.failure[idx]
            rate = (s / (s + f)) if (s + f) > 0 else 0.5
        radar_rates.append(rate)
        radar_colors.append(cos_color(rate))
    # Close the polygon
    radar_values_closed = radar_values + radar_values[:1]
    radar_axis_closed   = radar_axis_labels + radar_axis_labels[:1]
    radar_colors_closed = radar_colors + radar_colors[:1]
    radar_rates_closed  = radar_rates + radar_rates[:1]

    fig_r = go.Figure()
    # Base polygon (neutral grey fill) so the overall shape/area is still readable…
    fig_r.add_trace(go.Scatterpolar(
        r=radar_values_closed,
        theta=radar_axis_closed,
        fill="toself",
        line=dict(color="#9ca3af", width=1.5),
        fillcolor="rgba(156,163,175,0.18)",
        mode="lines",
        name="Slider positions",
        hoverinfo="skip",
    ))
    # …then per-attribute markers coloured red→green by the empirical success rate
    fig_r.add_trace(go.Scatterpolar(
        r=radar_values,
        theta=radar_axis_labels,
        mode="markers",
        marker=dict(size=15, color=radar_colors,
                    line=dict(color="#111827", width=1)),
        name="Success rate of selection",
        customdata=[f"{rt*100:.0f}%" for rt in radar_rates],
        hovertemplate="<b>%{theta}</b><br>Position: %{r} of " + str(n_cats)
                      + "<br>Success rate of this category: %{customdata}<extra></extra>",
    ))
    fig_r.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, n_cats],
                            tickvals=list(range(0, n_cats + 1)),
                            ticktext=[str(i) for i in range(0, n_cats + 1)]),
            angularaxis=dict(direction="clockwise"),
        ),
        showlegend=False,
        height=420, margin=dict(t=30, b=30, l=20, r=20),
    )
    st.plotly_chart(fig_r, use_container_width=True)
    st.caption(
        "Each axis = one DHI attribute scored on its 5-position scale (1 = worst / most "
        "DFI-failure-like, 5 = best / most DFI-success-like). The **marker colour** uses "
        "the shared Probability (CoS) scale — red→green = the empirical **success rate** "
        "of the category you selected on that axis (drilled-prospect histogram). So a "
        "marker can sit far out (high position) yet be amber/green depending on how that "
        "category actually performed in Monigle's data. A larger grey area = more "
        "positive positions overall. Style follows Monigle 2025 Fig 11."
    )

    # ── Simm 2016 Rule-of-Thumb reference tile ──
    with st.expander("📖 Simm 2016 R Rule-of-Thumb — sanity-check reference", expanded=False):
        st.markdown(
            "Independent reference scale from **Simm (2016)** — uncalibrated R values "
            "for typical prospect scenarios. Compare your R_eff above against this "
            "framework to sanity-check whether the result is in a defensible range "
            "for the geological evidence you have."
        )
        rot_rows = [
            {"R ≈": f"{r:.1f}", "Interpretation": txt}
            for r, txt in SIMM_RULE_OF_THUMB
        ]
        st.dataframe(pd.DataFrame(rot_rows), hide_index=True, use_container_width=True)
        st.caption(
            "Reference: Simm, R. (2016) *Seismic Amplitude and Risk: A Sense Check*, "
            "FORCE — Underexplored Plays Part II, Nov 2016."
        )


def _render_dfi_setup_custom(ctx) -> None:
    """DFI Setup when source = Custom R tool.

    The user defines two Gaussians — P(DFI | HC) and P(DFI | No-HC) — by their
    P1/P99 (min/max). A DHI-strength slider reads off R = pdf_HC / pdf_NoHC, which
    feeds the Simm two-state Bayesian update (same plumbing as the characteristic
    pathway). Plots both bell curves with a marker at the slider, plus R(strength).
    """
    import numpy as np
    import plotly.graph_objects as go
    import pandas as pd
    from logic.dfi_custom import (
        CustomCase, custom_r, grouped_r, dhi_score_from_r,
        SUCCESS_KEYS, FAILURE_KEYS, CASE_LABELS, CASE_GEO_LINK,
        CASE_DEFAULTS, CASE_WEIGHT_DEFAULTS, SIMM_R_BANDS,
    )
    from components.dfi_shared import (
        render_simm_verdict_banner, SIMM_BAND_EDGES, SIMM_R_TICKS,
    )

    st.markdown("### 🛠️ Custom R tool — define your own DHI likelihoods")
    st.info(
        "**What the curves mean in the geological risk model.**  \n"
        "• **Success cases** (Oil / Gas / Oil+Gas in an evaluable reservoir) describe how a "
        "*hydrocarbon-bearing* prospect tends to look on the DHI — the numerator of P(G).  \n"
        "• **Failure cases** (Water / Low-sat gas / Non-reservoir) describe how a "
        "*non-producing* outcome tends to look — the denominator.  \n\n"
        "R = P(DFI | HC) / P(DFI | No-HC) at your DHI reading is the **likelihood ratio** — "
        "how many times more consistent your DHI is with success than with failure. R > 1 "
        "lifts the geological prior P(G); R < 1 lowers it; R ≈ 1 leaves it unchanged."
    )

    # ── Persist / seed inputs ──
    def _f(key, default):
        return float(st.session_state.get(key, default))

    multicase = st.checkbox(
        "**Multi-case mode** — define each fluid / failure case separately",
        value=bool(st.session_state.get("dfi_custom_multicase", False)),
        key="dfi_custom_multicase",
        help="OFF: one success curve P(DFI|HC) vs one failure curve P(DFI|No-HC).  \n"
             "ON: set Oil / Gas / Oil+Gas and Water / LSG / Non-reservoir individually, "
             "each with a prior weight. Defaults keep all success cases identical and all "
             "failure cases identical, so R is unchanged until you edit a case.",
    )

    # ── DHI-strength slider (shared by both modes) ──
    slider = st.slider(
        "**DHI strength** (your observed reading on the −100…+100 axis)",
        min_value=-100.0, max_value=100.0,
        value=_f("dfi_custom_slider", 25.0), step=1.0, key="dfi_custom_slider",
        help="Where on the DHI-strength axis your prospect sits. R is read off the "
             "bell curves at this point.",
    )
    st.caption(
        "ℹ️ The **DHI strength** scale (−100 … +100) is an **uncalibrated**, relative "
        "measure of how strong/positive your DFI looks — it carries no physical units. It "
        "is read against the equally **uncalibrated** Success and Failure P(DFI | case) "
        "distributions you define below. Only the *shape and separation* of the two curves "
        "matters (R is scale-invariant), so the −100…100 numbers are arbitrary — unlike the "
        "SAAM DHI-Index pathway, which is calibrated to a drilled-prospect database."
    )

    # ── Build the case set ──
    cases: dict = {}
    weights: dict = {}
    plot_specs: list = []   # (case, color, label, weight)

    if not multicase:
        col_hc, col_no = st.columns(2)
        with col_hc:
            st.markdown("##### 🟢 P(DFI | HC) — success curve")
            hc_p1  = st.number_input("HC min (P1)",  value=_f("dfi_custom_hc_p1",  -50.0),
                                     min_value=-200.0, max_value=200.0, step=5.0, key="dfi_custom_hc_p1")
            hc_p99 = st.number_input("HC max (P99)", value=_f("dfi_custom_hc_p99", 100.0),
                                     min_value=-200.0, max_value=200.0, step=5.0, key="dfi_custom_hc_p99")
        with col_no:
            st.markdown("##### 🔴 P(DFI | No-HC) — failure curve")
            no_p1  = st.number_input("No-HC min (P1)",  value=_f("dfi_custom_no_p1",  -100.0),
                                     min_value=-200.0, max_value=200.0, step=5.0, key="dfi_custom_no_p1")
            no_p99 = st.number_input("No-HC max (P99)", value=_f("dfi_custom_no_p99", 50.0),
                                     min_value=-200.0, max_value=200.0, step=5.0, key="dfi_custom_no_p99")
        hc   = CustomCase("hc",   "P(DFI | HC)",    hc_p1, hc_p99)
        nohc = CustomCase("nohc", "P(DFI | No-HC)", no_p1, no_p99)
        for k in SUCCESS_KEYS: cases[k] = hc;   weights[k] = 1.0
        for k in FAILURE_KEYS: cases[k] = nohc; weights[k] = 1.0
        r_val = custom_r(slider, hc, nohc)
        plot_specs = [(hc, "#16a34a", "P(DFI | HC)", 1.0, "Success"),
                      (nohc, "#dc2626", "P(DFI | No-HC)", 1.0, "Failure")]
        st.markdown("##### Derived Gaussian parameters")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("HC mean / SD",    f"{hc.mean:.1f} / {hc.sd:.2f}")
        c2.metric("No-HC mean / SD", f"{nohc.mean:.1f} / {nohc.sd:.2f}")
        c3.metric("R @ slider",      f"{r_val:.2f}",
                  help="R = P(DFI|HC) / P(DFI|No-HC) at the slider. Feeds Simm 2-state Bayes.")
        c4.metric("DHI score",       f"{dhi_score_from_r(r_val)*100:.0f}%",
                  help="R / (R + 1) — Monigle-style 0–100 score.")
    else:
        green = {"oil": "#15803d", "gas": "#22c55e", "oil_gas": "#4ade80"}
        red   = {"water": "#dc2626", "lsg": "#f59e0b", "non_reservoir": "#7f1d1d"}

        def _case_inputs(keys, color_map, group):
            for k in keys:
                d_p1, d_p99 = CASE_DEFAULTS[k]
                cc1, cc2, cc3 = st.columns([2, 2, 1])
                p1 = cc1.number_input(f"{CASE_LABELS[k]} — P1",
                                      value=_f(f"dfi_custom_{k}_p1", d_p1),
                                      min_value=-200.0, max_value=200.0, step=5.0,
                                      key=f"dfi_custom_{k}_p1")
                p99 = cc2.number_input(f"{CASE_LABELS[k]} — P99",
                                       value=_f(f"dfi_custom_{k}_p99", d_p99),
                                       min_value=-200.0, max_value=200.0, step=5.0,
                                       key=f"dfi_custom_{k}_p99")
                wt = cc3.number_input(f"{CASE_LABELS[k]} — weight",
                                      value=_f(f"dfi_custom_{k}_w", CASE_WEIGHT_DEFAULTS[k]),
                                      min_value=0.0, max_value=100.0, step=0.1,
                                      key=f"dfi_custom_{k}_w")
                cc1.caption(CASE_GEO_LINK[k])
                cc = CustomCase(k, CASE_LABELS[k], p1, p99)
                cases[k] = cc; weights[k] = wt
                plot_specs.append((cc, color_map[k], CASE_LABELS[k], wt, group))

        st.info(
            "**Weights = a prior probability mix, exactly like the DHI-Index method.**  \n"
            "Within each group the weights are **normalised to sum to 100 %**:  \n"
            "• Success: P(oil) + P(gas) + P(oil+gas) = 100 % *(given the prospect succeeds)*  \n"
            "• Failure: P(water) + P(LSG) + P(non-reservoir) = 100 % *(given it fails)*  \n"
            "This mirrors the DHI-Index fluid-failure weights (water + LSG + other = 1). "
            "You can type any positive numbers — they are converted to percentages internally, "
            "so only their *ratios* matter. The normalised mix is shown below each group."
        )
        st.markdown("##### 🟢 Success cases (hydrocarbons present)")
        _case_inputs(SUCCESS_KEYS, green, "Success")
        _succ_sum = sum(max(weights[k], 0.0) for k in SUCCESS_KEYS) or 1.0
        st.caption(
            "Normalised success mix → "
            + ", ".join(f"{CASE_LABELS[k]} **{weights[k]/_succ_sum:.0%}**" for k in SUCCESS_KEYS)
            + f"  *(entered weights sum to {sum(weights[k] for k in SUCCESS_KEYS):.2f})*"
        )
        st.markdown("##### 🔴 Failure cases (no producible HC)")
        _case_inputs(FAILURE_KEYS, red, "Failure")
        _fail_sum = sum(max(weights[k], 0.0) for k in FAILURE_KEYS) or 1.0
        st.caption(
            "Normalised failure mix → "
            + ", ".join(f"{CASE_LABELS[k]} **{weights[k]/_fail_sum:.0%}**" for k in FAILURE_KEYS)
            + f"  *(entered weights sum to {sum(weights[k] for k in FAILURE_KEYS):.2f})*"
        )

        r_val = grouped_r(slider, cases, weights)
        st.markdown("##### Aggregate")
        c1, c2 = st.columns(2)
        c1.metric("R @ slider", f"{r_val:.2f}",
                  help="R = Σ wₛ·pdfₛ / Σ w_f·pdf_f at the slider (weighted within "
                       "each group). Feeds Simm 2-state Bayes.")
        c2.metric("DHI score",  f"{dhi_score_from_r(r_val)*100:.0f}%",
                  help="R / (R + 1) — Monigle-style 0–100 score.")

    score = dhi_score_from_r(r_val) * 100.0
    # ── Persist for Results / Summary (reuses the characteristic Simm plumbing) ──
    st.session_state["dhi_custom_r"]     = float(r_val)
    st.session_state["dhi_custom_score"] = float(score)

    # ── Simm rule-of-thumb verdict on the R result (shared component) ──
    _simm_label, _simm_comment, _simm_color = render_simm_verdict_banner(r_val)

    # ── P(DFI | case) table with the R verdict ──
    _grp_sum = {
        "Success": sum(max(s[3], 0.0) for s in plot_specs if s[4] == "Success") or 1.0,
        "Failure": sum(max(s[3], 0.0) for s in plot_specs if s[4] == "Failure") or 1.0,
    }
    _rows = []
    for cc, _color, label, wt, group in plot_specs:
        _rows.append({
            "Case": label, "Group": group,
            "P1": f"{cc.p1:+.0f}", "P99": f"{cc.p99:+.0f}",
            "Weight": f"{wt:.2f}",
            "Prior mix": f"{wt / _grp_sum[group]:.0%}",
            "P(DFI | case)": f"{cc.pdf(slider):.4f}",
        })
    _df = pd.DataFrame(_rows)
    st.markdown("##### P(DFI | case) at the current DHI strength")
    st.dataframe(_df, hide_index=True, use_container_width=True)
    st.caption(
        f"P(DFI | case) = bell-curve density at DHI = **{slider:+.0f}**. "
        f"R = (weighted success ÷ weighted failure) = **{r_val:.2f}** → "
        f"**{_simm_label}**. Only the *ratio* matters — a common scale factor cancels "
        "in the Bayesian update."
    )

    # ── R-at-x helper (shared single-source reconstruction, also used by DFI
    #    Results). ``cases``/``weights`` are keyed per success/failure outcome in
    #    both modes, so grouped_r evaluates R identically (and reduces to custom_r
    #    in the linked case). ──
    def _r_at(x):
        return grouped_r(x, cases, weights)

    # ── Bell-curve plot ──
    all_p1  = [spec[0].p1  for spec in plot_specs]
    all_p99 = [spec[0].p99 for spec in plot_specs]
    lo = min(all_p1 + [-100.0])
    hi = max(all_p99 + [100.0])
    xs = np.linspace(lo, hi, 400)
    fig = go.Figure()
    for cc, color, label, _wt, _grp in plot_specs:
        fig.add_trace(go.Scatter(x=xs, y=[cc.pdf(x) for x in xs], mode="lines", name=label,
                                 line=dict(color=color, width=2.2)))
        fig.add_trace(go.Scatter(x=[slider], y=[cc.pdf(slider)], mode="markers",
                                 marker=dict(symbol="circle", size=10, color=color,
                                             line=dict(color="white", width=1.2)),
                                 showlegend=False,
                                 hovertemplate=f"{label}<br>pdf=%{{y:.4f}}<extra></extra>"))
    fig.add_vline(x=slider, line_dash="dash", line_color="#6b7280",
                  annotation_text=f"DHI = {slider:+.0f}", annotation_position="top")
    fig.update_xaxes(title_text="DHI strength")
    fig.update_yaxes(title_text="Probability density")
    fig.update_layout(height=400, margin=dict(t=30, b=50, l=50, r=10),
                      legend=dict(orientation="h", x=0.5, y=-0.18, xanchor="center"))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"At DHI strength = **{slider:+.0f}** the markers show each curve's density; "
        f"R ≈ **{r_val:.2f}**. Absolute density units are arbitrary — only the *ratio* "
        "(weighted success ÷ weighted failure) drives the update."
    )

    # ── R across the strength axis (with Simm rule-of-thumb bands) ──
    r_curve = [_r_at(x) for x in xs]
    figr = go.Figure()
    # Shade the Simm strength bands behind the curve (shared band definitions).
    # Shade only — labels are added separately, inside the plot on the right.
    for _hi, _lo, _col, _lbl in SIMM_BAND_EDGES:
        figr.add_hrect(y0=_lo, y1=_hi, fillcolor=_col, line_width=0, layer="below")
    for _thr in SIMM_R_BANDS:
        figr.add_hline(y=_thr, line_dash="dot", line_color="#cbd5e1", line_width=1)
    figr.add_hline(y=1.0, line_dash="dot", line_color="#6b7280")
    figr.add_trace(go.Scatter(x=xs, y=r_curve, mode="lines", name="R(strength)",
                              line=dict(color="#7c3aed", width=2.5)))
    figr.add_vline(x=slider, line_dash="dash", line_color="#6b7280")
    figr.add_trace(go.Scatter(x=[slider], y=[r_val], mode="markers",
                              marker=dict(symbol="star", size=15, color="#7c3aed",
                                          line=dict(color="white", width=1.5)),
                              name=f"R = {r_val:.2f} ({_simm_label})"))
    # Band labels placed *inside* the plot, just inside the right edge and
    # centred on each band (geometric-mean centre because the y-axis is log).
    # NOTE: on a log axis Plotly expects annotation y as log10(value), unlike
    # shapes which auto-convert — so we pass the log of the geometric-mean centre.
    for _hi, _lo, _col, _lbl in SIMM_BAND_EDGES:
        figr.add_annotation(xref="paper", x=0.99, xanchor="right",
                            yref="y", y=float(0.5 * np.log10(_hi * _lo)),
                            text=_lbl, showarrow=False, align="right",
                            font=dict(size=10, color="#475569"))
    figr.update_xaxes(title_text="DHI strength")
    figr.update_yaxes(title_text="R = P(DFI|HC) / P(DFI|No-HC)", type="log",
                      range=[np.log10(0.02), np.log10(50.0)],
                      tickmode="array", tickvals=list(SIMM_R_TICKS),
                      ticktext=[f"{t:.2f}" for t in SIMM_R_TICKS])
    figr.update_layout(height=510, margin=dict(t=20, b=40, l=50, r=10),
                       legend=dict(orientation="h", x=0.5, y=-0.18, xanchor="center"))
    st.plotly_chart(figr, use_container_width=True)
    st.caption(
        "R on a **log** axis with the **Simm rule-of-thumb bands**: |R| ≈ 1.5 moderate, "
        "≈ 3 strong (Simm's practical ceiling for a single DFI), ≥ 10 decisive (audit the "
        "inputs). R is capped to [0.02, 50]. The posterior P(G | DFI) appears on the "
        "**DFI Results** sub-tab."
    )


