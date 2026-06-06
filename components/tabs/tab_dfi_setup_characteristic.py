"""DFI Setup — characteristic-scoring (Monigle 2025) pathway.
Extracted from ``components.tabs.tab_dfi_setup``.
"""
from __future__ import annotations

import streamlit as st

from logic.dfi_context import (
    esl_prior_pillars_from_ctx as _esl_prior_pillars_from_ctx,
    esl_rollup_prior_at_w      as _esl_rollup_prior_at_w,
)


def _render_dfi_setup_characteristic(ctx) -> None:
    """Six-slider DFI characteristic-scoring panel — Monigle 2025 pathway."""
    import math
    import pandas as pd
    import plotly.graph_objects as go
    from logic.dhi_characteristics import (
        load_characteristic_stats, compute_r_char, compute_r_char_inferred,
        apply_discernibility, simm_bayes_posterior, dhi_score_from_r,
        inferred_success_curve, inferred_success_rate_at, inferred_lr_at,
        SIMM_RULE_OF_THUMB, cap_for_bucket, CHARACTERISTIC_DEFAULT_SELECTIONS,
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
                # Analyst-requested default selection (falls back to the middle category).
                _def_cat = CHARACTERISTIC_DEFAULT_SELECTIONS.get(key)
                if _def_cat not in cats:
                    _def_cat = cats[mid_idx]
                label = attr.display_name + (" 🟡" if attr.placeholder else "")
                if inferred:
                    # Continuous 0..1 slider (100 steps), mode-suffixed key
                    pos_key = f"dhi_char_pos_{key}_{mode_key}"
                    _def_pos = (cats.index(_def_cat) / (K - 1)) if K > 1 else 0.5
                    x = float(st.session_state.get(pos_key, _def_pos))
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
                    value = stored if stored in cats else _def_cat
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
        _cap_lo, _cap_hi = cap_for_bucket(bucket_name, enabled=True)
        apply_cap = st.checkbox(
            f"Apply discernibility-aware cap on R  "
            f"[{_cap_lo:.2f}, {_cap_hi:.1f}] at **{bucket_name}** discernibility",
            value=bool(st.session_state.get("dhi_char_apply_cap", True)),
            key="dhi_char_apply_cap",
            help=(
                "Clamps the naive-product R into a defensible band. **The band now widens "
                "with discernibility** — Simm's [1/3, 3] is calibrated to a *single* DFI "
                "line, but R_char is a *composite* of five attributes, so a single-line cap "
                "is too tight when the geophysics is genuinely discernible:\n\n"
                "• high → [1/10, 10]  • moderate → [1/6, 6]  • low/absent → [1/3, 3]\n\n"
                "This lets a high-discernibility, expected-but-absent DHI produce the strong "
                "downgrade that Monigle 2025 demonstrate (e.g. their Prospect B, GCOS 46% → "
                "iCOS 8%) — which the flat Simm cap cannot express — while keeping low "
                "discernibility conservative.\n\n"
                "**Default ON.** Turn OFF only to inspect the raw, unconstrained product "
                "(the naive independence assumption over-counts correlated attributes)."
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

        st.markdown("---")
        corr_rho = st.slider(
            "Assumed attribute correlation ρ (independence discount)",
            min_value=0.0, max_value=0.8, step=0.05,
            value=float(st.session_state.get("dhi_char_corr_rho", 0.0)),
            key="dhi_char_corr_rho",
            help=(
                "**Corrects the naive-Bayes independence assumption.** R = ∏ LRᵢ "
                "treats the attributes as conditionally independent given class, but "
                "they physically co-vary, so the product double-counts shared signal.\n\n"
                "With average pairwise correlation ρ, the *effective* number of "
                "independent attributes is k_eff = k / (1 + (k−1)·ρ), so the evidence "
                "is discounted as **R_disc = R_raw^f** with **f = 1/(1 + (k−1)·ρ)**.\n\n"
                "ρ = 0 → independent (naive product, unchanged). ρ → 1 → fully "
                "redundant (the k attributes count as one). ρ ≈ 0.3–0.5 is a "
                "reasonable default for seismic amplitude attributes. This is a "
                "*principled* alternative to letting the hard cap do all the work."
            ),
        )
        if corr_rho > 0:
            st.caption(
                f"Independence discount active (ρ = {corr_rho:.2f}). The naive product "
                "is down-weighted before the cap is applied."
            )

    # ── Compute ──
    rel_middle = bool(st.session_state.get("dhi_char_rel_middle", False))
    corr_rho = float(st.session_state.get("dhi_char_corr_rho", 0.0))
    _floor, _hardcap = cap_for_bucket(bucket_name, enabled=apply_cap)
    cap_kw = dict(hard_cap=_hardcap, floor=_floor)
    if inferred:
        r_res = compute_r_char_inferred(cstats, positions, mode_key=mode_key,
                                        relative_to_middle=rel_middle,
                                        corr_rho=corr_rho, **cap_kw)
    else:
        r_res = compute_r_char(cstats, selections, mode_key=mode_key,
                               relative_to_middle=rel_middle,
                               corr_rho=corr_rho, **cap_kw)
    r_char  = r_res["r_char"]                  # capped, after independence discount
    r_raw   = r_res["raw_r"]
    r_disc  = r_res["discounted_r"]
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
            _disc_txt = (f" → independence-discounted (ρ={corr_rho:.2f}, "
                         f"f={r_res['corr_exponent']:.2f}) = {r_disc:.2f}"
                         if corr_rho > 0 else "")
            _rhelp = (f"Naive-independence product of the LRs (raw = {r_raw:.2f}){_disc_txt}. "
                      + (f"Discernibility-aware cap [{_floor:.2f}, {_hardcap:.1f}] "
                         f"at {bucket_name} discernibility."
                         if apply_cap else
                         "Capping is OFF — shown unconstrained. Enable the cap "
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
    with st.expander("Per-attribute success rates — the drilled-prospect data behind each LR",
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
    with st.expander("Simm 2016 R Rule-of-Thumb — sanity-check reference", expanded=False):
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
