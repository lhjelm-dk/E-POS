"""DFI Setup — Custom R tool pathway.
Extracted from ``components.tabs.tab_dfi_setup``.
"""
from __future__ import annotations

import streamlit as st


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

    st.markdown("### Custom R tool — define your own DHI likelihoods")
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
        value=_f("dfi_custom_slider", 7.0), step=1.0, key="dfi_custom_slider",
        help="Where on the DHI-strength axis your prospect sits. R is read off the "
             "bell curves at this point.",
    )
    st.caption(
        "ℹ️ The **DHI strength** scale (−100 … +100) is an **uncalibrated**, relative "
        "measure of how strong/positive your DFI looks — it carries no physical units. It "
        "is read against the equally **uncalibrated** Success and Failure P(DFI | case) "
        "distributions you define below. Only the *shape and separation* of the two curves "
        "matters (R is scale-invariant), so the −100…100 numbers are arbitrary — unlike the "
        "Modified DHI Index (SAAM) pathway, which reads against a SAAM-derived calibration."
    )

    # ── Build the case set ──
    cases: dict = {}
    weights: dict = {}
    plot_specs: list = []   # (case, color, label, weight)

    if not multicase:
        col_hc, col_no = st.columns(2)
        with col_hc:
            st.markdown("##### P(DFI | HC) — success curve")
            hc_p1  = st.number_input("HC min (P1)",  value=_f("dfi_custom_hc_p1",  -50.0),
                                     min_value=-200.0, max_value=200.0, step=5.0, key="dfi_custom_hc_p1")
            hc_p99 = st.number_input("HC max (P99)", value=_f("dfi_custom_hc_p99", 100.0),
                                     min_value=-200.0, max_value=200.0, step=5.0, key="dfi_custom_hc_p99")
        with col_no:
            st.markdown("##### P(DFI | No-HC) — failure curve")
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
        st.markdown("##### Success cases (hydrocarbons present)")
        _case_inputs(SUCCESS_KEYS, green, "Success")
        _succ_sum = sum(max(weights[k], 0.0) for k in SUCCESS_KEYS) or 1.0
        st.caption(
            "Normalised success mix → "
            + ", ".join(f"{CASE_LABELS[k]} **{weights[k]/_succ_sum:.0%}**" for k in SUCCESS_KEYS)
            + f"  *(entered weights sum to {sum(weights[k] for k in SUCCESS_KEYS):.2f})*"
        )
        st.markdown("##### Failure cases (no producible HC)")
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
