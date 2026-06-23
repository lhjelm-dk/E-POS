"""DFI Setup sub-page — inputs, calibration, bell curves, characteristic
scoring. Extracted from ``components.tabs.tab_dfi``.
"""
from __future__ import annotations

import streamlit as st

from logic.dfi_inputs import (
    DEFAULT_DHI, DEFAULT_FLUID_TYPE, DEFAULT_FLUID_WATER,
    DEFAULT_FLUID_LSG, DEFAULT_FLUID_OTHER, DEFAULT_ESL_ATTR,
)
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
        st.markdown("### DFI evidence source")
        _src_options = ["Custom R tool", "Characteristic scoring (Monigle 2025)",
                        "Conceptual DHI Index (experimental)"]
        # Migrate any persisted selection (old labels / order) onto the new option
        # list so st.radio never sees a stored value that isn't in `options`.
        _src_map = {"custom": _src_options[0], "characteristic": _src_options[1],
                    "dhi_index": _src_options[2]}
        if st.session_state.get("dfi_source_radio") not in _src_options:
            st.session_state["dfi_source_radio"] = _src_map.get(
                st.session_state.get("dfi_source"), _src_options[0])
        source = st.radio(
            "Choose how the DHI strength R is derived:",
            options=_src_options,
            horizontal=True,
            key="dfi_source_radio",
            label_visibility="visible",
            help=(
                "Three mutually-exclusive ways to derive the DHI strength R:\n\n"
                "• **Custom R tool** — define your own two bell curves for P(DFI | HC) and "
                "P(DFI | No-HC) by their min/max (P1/P99), read R off a DHI-strength slider. "
                "Fully transparent, no external calibration. Two-state Bayes.\n\n"
                "• **Characteristic scoring (Monigle 2025)** — score the prospect on five DHI "
                "attributes using a 5-step verbal scale; R is the product of per-attribute "
                "likelihood ratios from the Monigle 2025 drilled-prospect database. Simpler "
                "two-state Bayes; no per-pillar attribution. Stand-alone — no calibration needed.\n\n"
                "• **Conceptual DHI Index (experimental)** — a *conceptual*, illustrative DFI-strength "
                "model with editable likelihood curves (not calibrated to any dataset). Enter a "
                "**pure DFI-strength index**, not a raw composite DHI index that bundles geology; "
                "see the warning on that page. 8-outcome Bayes, per-pillar attribution available."
            ),
        )
    # Persist for downstream pages
    if source.startswith("Characteristic"):
        st.session_state["dfi_source"] = "characteristic"
    elif source.startswith("Custom"):
        st.session_state["dfi_source"] = "custom"
    else:
        st.session_state["dfi_source"] = "dhi_index"

    # ── DFI prior provenance (documented in-app) ──
    st.caption(
        "**DFI prior = P(G, ESL)** — the stance-weighted ESL mass-rollup (your headline "
        "geological number). The update always refines this ESL prior; switching the Classic "
        "POS view does not change it."
    )

    # ── Triage: which source, when (all three converge on the same R → Simm update) ──
    with st.expander("Which source should I use?", expanded=False):
        st.markdown(
            "All three pathways end in the **same R → Simm Bayesian update**; they differ only "
            "in how R is *sourced and justified*.\n\n"
            "| Source | You supply | Use when | Decision-grade? |\n"
            "|---|---|---|---|\n"
            "| **Conceptual DHI Index** | one DFI-strength slider vs illustrative curves | "
            "teaching / quick-look, no real DHI work yet | No (curves uncalibrated) |\n"
            "| **Characteristic scoring (Monigle 2025)** | scores for the DHI characteristics | "
            "you have a qualitative QI / DHI interpretation | Yes (literature-calibrated R) |\n"
            "| **Custom R tool** | your own strength→fluid curves (single or multi-case) | "
            "you have a calibrated / bespoke view, or need full control | Yes (if curves are calibrated) |\n\n"
            "Conceptual is **illustrative only**; use Characteristic or a calibrated Custom for decisions."
        )

    # Branch — Characteristic / Custom modes handled by their own renderers.
    if st.session_state["dfi_source"] == "characteristic":
        _render_dfi_setup_characteristic(ctx)
        return
    if st.session_state["dfi_source"] == "custom":
        _render_dfi_setup_custom(ctx)
        return

    # ── Method warning: conceptual model; needs a *pure* DFI-strength input ──
    st.markdown("### Conceptual DHI Index (experimental)")
    st.error(
        "⚠️ **Conceptual model. Do not enter a raw composite DHI index here.**\n\n"
        "The **DHI Index** in this pathway is a *conceptual* index: it is built to behave like "
        "the industry **DHI Consortium** calibrated DHI Index, but it is **not** that index. Its "
        "likelihood curves are round, hand-set values, **not calibrated to any dataset**, and are "
        "editable below. A raw composite DHI index (the kind a scoring workflow books for a "
        "prospect) **cannot be used directly** in this Bayesian update, because such an index "
        "bundles the *geological* chance together with the seismic signal. The geology must be "
        "**stripped out** before the number is valid here, otherwise it is double-counted "
        "against the ESL prior, which already carries it.\n\n"
        "The input below must therefore be a **pure DFI-strength indicator** (seismic amplitude "
        "evidence only). Treat it as an *illustrative* strength. **For a decision-grade update, "
        "replace the conceptual curves with your own calibrated likelihoods.**"
    )

    # ── Header strip: calibration source + override status ──
    src_text = f"**Calibration:** v.{calib.version}"
    if calib.is_placeholder:
        st.warning(
            f"{src_text} — ⚠️ **placeholder values in use**. "
            "Replace with your own calibrated likelihoods at `data/dhi_calibration.json` for production use."
        )
    else:
        st.caption(f"{src_text} (source: {calib.source}). "
                   f"Override active: {'yes' if st.session_state.get('dfi_calibration_override') else 'no'}")

    # ── Stacked full-width sections: Inputs (top) → Likelihood curves →
    #    R(DHI) panel below. Containers (not columns) so each spans full width
    #    and renders top-to-bottom, leaving room for the R-vs-DHI plot.
    col_inputs = st.container()
    col_viz = st.container()

    # ─── Section A: Inputs ───────────────────────────────────────────────
    with col_inputs:
        st.markdown("##### Inputs")

        # Key-only widgets: seed the default once, then let Streamlit own the
        # widget state via `key`. Passing both `value=`/`index=` AND `key=` when the
        # default is read from the *same* session key makes the widget snap back to
        # the default on rerun (the DHI-Index "stuck at 19" desync) — so don't.
        st.session_state.setdefault("dfi_index", int(DEFAULT_DHI))
        dhi = st.slider(
            "**Conceptual DHI Index**",
            min_value=DHI_INDEX_MIN_INT,
            max_value=DHI_INDEX_MAX_INT,
            step=1, key="dfi_index",
            help=(f"Conceptual DHI Index (range {DHI_INDEX_MIN_INT} to {DHI_INDEX_MAX_INT}): an "
                  "illustrative DFI-strength reading, not the DHI Consortium's calibrated index. "
                  "Higher = stronger DFI signal supporting HC presence."),
        )
        st.caption(
            "A **high** index is a strong supportive signal (R > 1, raises POS). A **low or "
            "negative** index represents a weak or **expected-but-absent** response (R < 1) and "
            "legitimately *lowers* POS: a flat spot the geology predicts but the seismic does not "
            "show is evidence too. The update works both ways."
        )

        st.session_state.setdefault("dfi_fluid_type", DEFAULT_FLUID_TYPE)
        fluid_type = st.selectbox(
            "**Expected HC fluid type**",
            options=list(SUCCESS_CLASSES),
            format_func=lambda x: CLASS_DISPLAY.get(x, x),
            key="dfi_fluid_type",
            help=("DHI class supplying the success-side likelihood. "
                  "'HC Success' is the aggregate (default); pick Oil/Gas/OilGas if "
                  "the prospect has a specific expected fluid type."),
        )

        # ── Advanced / Research controls (demoted — sensible defaults apply) ──
        st.caption(
            "Standard inputs above drive the update. The defaults below "
            "(water-dominated failure mix, attribution A) suit "
            "most prospects — open **Advanced** only to override them."
        )
        with st.expander("Advanced / Research inputs — fluid mix · attribution",
                         expanded=False):

            st.markdown("**Fluid failure probabilities**  *P(fluid | failure)*")
            col_w, col_l, col_o = st.columns(3)
            with col_w:
                st.session_state.setdefault("dfi_fluid_water", DEFAULT_FLUID_WATER)
                water = st.number_input(
                    "Water", min_value=0.0, max_value=1.0,
                    step=0.05, format="%.2f", key="dfi_fluid_water",
                )
            with col_l:
                st.session_state.setdefault("dfi_fluid_lsg", DEFAULT_FLUID_LSG)
                lsg = st.number_input(
                    "LSG", min_value=0.0, max_value=1.0,
                    step=0.05, format="%.2f", key="dfi_fluid_lsg",
                )
            with col_o:
                st.session_state.setdefault("dfi_fluid_other", DEFAULT_FLUID_OTHER)
                other = st.number_input(
                    "Other", min_value=0.0, max_value=1.0,
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
            st.session_state.setdefault("dfi_esl_attribution", DEFAULT_ESL_ATTR)
            _attr_now = st.session_state.get("dfi_esl_attribution", "B")
            _attr_lbl = ("A: equal multiplicative (preserve commitment C)"
                         if _attr_now == "A" else "B: Bel/Pl update")
            st.caption(
                f"Current: **{_attr_lbl}**. Choose A or B — with the full explanation and the "
                "math behind each — in **Dashboard → ⚙ Advanced — DFI → ESL per-pillar attribution**."
            )

        # Defaults so downstream code works whether or not the drawer was opened.
        sd_mode = str(st.session_state.get("dfi_sd_mode", "upper"))
        water = float(st.session_state.get("dfi_fluid_water", 0.50))
        lsg   = float(st.session_state.get("dfi_fluid_lsg",   0.20))
        other = float(st.session_state.get("dfi_fluid_other", 0.30))

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
            "Five outcome-class likelihoods. **LSG and Other share the same class "
            "distribution** (LSG/other failure column) — the dotted purple curve "
            "for Other overlays the yellow LSG curve. The Gaussian PDF is used "
            "rigorously (no frequency scaling)."
        )

        # ── R_DFI across the DHI-Index axis (Simm bands) — parallel to the custom tool ──
        st.markdown("##### R_DFI vs DHI Index")
        from components.dfi_shared import render_r_strength_plot as _render_r_plot
        from logic.dfi_bayes import compute_dfi_posterior as _cdp, FluidWeights as _FW
        _fw_sweep = _FW(water=water, lsg=lsg, other=other)
        _prior_sweep = _esl_prior_pillars_from_ctx(ctx)
        _xr = list(range(DHI_INDEX_MIN_INT, DHI_INDEX_MAX_INT + 1))
        _rr = [_cdp(_prior_sweep, _xi, calib, _fw_sweep, sd_mode, fluid_type).r_dfi
               for _xi in _xr]
        _r_now = _cdp(_prior_sweep, dhi, calib, _fw_sweep, sd_mode, fluid_type).r_dfi
        _render_r_plot(
            _xr, _rr, dhi, _r_now,
            x_label="DHI Index",
            y_label="R_DFI = L(success) / E[L | failure]",
            caption=(
                "R_DFI across the DHI-Index axis with the **Simm rule-of-thumb bands**. "
                "The ★ is your current DHI reading — the same R_DFI shown in the metrics "
                "below. Holds the fluid mix fixed; only the DHI Index varies. Capped to "
                "[0.02, 50]."
            ),
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
    #    two evidence sources). R_DFI is the 8-outcome likelihood ratio. ──
    from components.dfi_shared import (
        render_rscore_metrics, render_simm_verdict_banner, render_simm_band_strip,
    )
    from logic.dfi_simm import dhi_score_from_r as _dhi_score_from_r
    st.divider()
    st.markdown("##### DHI strength R — Simm rule-of-thumb verdict")
    _r_dfi = float(post_esl.r_dfi)
    render_rscore_metrics(
        _r_dfi, _dhi_score_from_r(_r_dfi) * 100.0,
        r_label="R_DFI",
        r_help="L_success / E[L | failure] from the 8-outcome likelihoods (ESL prior).",
    )
    render_simm_verdict_banner(_r_dfi)
    render_simm_band_strip(_r_dfi, key="dfi_dhiindex_band_strip")

    # ── GeoX hand-off: the 6 P(DFI|case) values to type into SLB GeoX ──
    st.divider()
    _render_geox_pdfi_panel(dhi, calib, sd_mode, fluid_type)

    # ── Calibration editor (collapsed by default) ──
    with st.expander("Edit calibration values (live update affects bell curves and posteriors)", expanded=False):
        _render_calibration_editor(calib)


# ─────────────────────────────────────────────────────────────────────────────
# Characteristic-scoring DFI Setup (Monigle 2025 — alternative to the conceptual DHI Index)
# ─────────────────────────────────────────────────────────────────────────────


# Characteristic-scoring and Custom-R setup pathways live in sibling modules.
from components.tabs.tab_dfi_setup_characteristic import _render_dfi_setup_characteristic
from components.tabs.tab_dfi_setup_custom import _render_dfi_setup_custom
