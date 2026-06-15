"""DFI side panels — GeoX P(DFI|case) likelihoods, posterior-class readout,
calibration editor. Extracted from ``components.tabs.tab_dfi``.
"""
from __future__ import annotations

import streamlit as st

from logic.dfi_orchestration import geox_pdfi_value, _GEOX_PDFI_SCALE


def _render_geox_pdfi_panel(dhi, calib, sd_mode, fluid_type) -> None:
    """Pin out the six P(DFI|case) likelihoods that SLB GeoX's DFI Assessment needs.

    GeoX's DFI Assessment tab takes six conditional probabilities P(DFI | case),
    one per (fluid × reservoir-evaluability) outcome. They map onto the DHI
    calibration classes as below; the three non-evaluable-reservoir cases all share
    the Reservoir_failure class, so they take the same value.
    """
    import pandas as pd
    from logic.dfi_calibration import CLASS_DISPLAY

    succ_disp = CLASS_DISPLAY.get(fluid_type, fluid_type)
    v_hc  = geox_pdfi_value(dhi, calib, fluid_type,          sd_mode)
    v_wat = geox_pdfi_value(dhi, calib, "H2O_failure",       sd_mode)
    v_lsg = geox_pdfi_value(dhi, calib, "LSG_failure",       sd_mode)
    v_res = geox_pdfi_value(dhi, calib, "Reservoir_failure", sd_mode)

    # GeoX accepts a single decimal place on input — round display to 1 dp.
    rows = [
        ("Oil & Eval. Res.",          f"{v_hc*100:.1f}%",  f"Success class · {succ_disp}"),
        ("Oil & Non. Eval. Res.",     f"{v_res*100:.1f}%", "Reservoir_failure"),
        ("Water & Eval. Res.",        f"{v_wat*100:.1f}%", "H2O_failure"),
        ("Water & Non. Eval. Res.",   f"{v_res*100:.1f}%", "Reservoir_failure"),
        ("Low Sat. Gas & Eval. Res.", f"{v_lsg*100:.1f}%", "LSG_failure"),
        ("Low Sat. Gas & Non. Eval. Res.", f"{v_res*100:.1f}%", "Reservoir_failure"),
    ]
    df = pd.DataFrame(rows, columns=["GeoX case label", "P(DFI | case)", "DHI class used"])

    st.markdown("##### 📤 GeoX hand-off — the 6 P(DFI | case) inputs")
    st.caption(
        f"Type these six values into the **DFI Assessment** tab of SLB **GeoX** "
        f"(at DHI Index = **{dhi:+.0f}**, SD mode = **{sd_mode}**, "
        f"success class = **{succ_disp}**). Values are shown to **one decimal place** — "
        f"GeoX accepts a single decimal on input. The three non-evaluable-reservoir cases "
        f"share the Reservoir_failure class, so they take the same value."
    )
    st.dataframe(df, hide_index=True, use_container_width=True)

    # Concrete numbers for the explainer (raw density vs ×20-scaled value)
    raw_hc  = v_hc  / _GEOX_PDFI_SCALE   # = Gaussian density (un-scaled)
    raw_res = v_res / _GEOX_PDFI_SCALE
    ratio_hc_res = (v_hc / v_res) if v_res > 0 else float("inf")

    with st.expander("What these values are, and why only their *relative* size matters", expanded=False):
        st.markdown(
            "**What the six cases mean in the geological risk model**  \n"
            "A \"case\" is one possible *ground truth* the prospect could turn out to be — a "
            "combination of **which fluid fills the trap** and **whether the reservoir is "
            "evaluable** (developed enough to show a DFI at all). They line up with the "
            "geological risk pillars like this:  \n\n"
            "| GeoX case | Ground truth it represents | Risk pillar it tests |\n"
            "|---|---|---|\n"
            "| Oil & Eval. Res. | **Success** — hydrocarbons in a real reservoir | Charge **and** reservoir present (P(G)) |\n"
            "| Water & Eval. Res. | Reservoir there, but **brine-filled** | Charge/seal failure |\n"
            "| Low Sat. Gas & Eval. Res. | Reservoir there, but **fizz / residual gas** | Charge-quality failure (LSG) |\n"
            "| *…* & Non. Eval. Res. | **No effective reservoir** — fluid is then moot | Reservoir-presence failure |\n\n"
            "The **success** case is the numerator of P(G); the others are the mutually-exclusive "
            "ways the prospect can fail. The fluid label only changes the *prior weight* of each "
            "failure (via the fluid-failure weights), not the bell curve once the reservoir is "
            "non-evaluable, which is why the three Non. Eval. Res. rows share one likelihood.  \n\n"
            "---\n"
            "**What is P(DFI | case)?**  \n"
            "For each possible outcome (\"case\"), the conceptual DHI model database gives a bell curve (Gaussian) "
            "describing *what DHI Index that kind of prospect tends to produce*. **P(DFI | case)** is "
            "simply the **height of that bell curve at your observed DHI Index** — how well your DHI "
            "score \"fits\" each case. A high value means *\"a prospect of this type would readily "
            "produce the DHI I'm seeing\"*; a low value means *\"this type rarely looks like this\"*.  \n\n"
            f"So at DHI = **{dhi:+.0f}**, the success (HC) curve is much taller than the water curve → "
            "the observation fits *success* far better than *water*, which is what pushes P(G) up."
        )
        st.markdown(
            "**Why aren't these just the raw Gaussian PDF heights?**  \n"
            "The raw Gaussian PDF is a *probability density*, not a probability — its units are "
            "\"per unit DHI\", it peaks around 3–4 and can exceed 1. GeoX (and the conceptual DHI model workbook) "
            "rescale it into a percentage-like number by multiplying by **20**:"
        )
        st.latex(r"P(\text{DFI} \mid \text{case}) \;=\; \text{Gaussian density} \times 20")
        st.markdown(
            "The factor 20 corresponds to a ≈ 5 %-wide DHI-Index bin (1 ÷ 0.05 = 20): it turns the "
            "*density* into the *probability mass in a small bin around the observed DHI*. For the two "
            "cases above:  \n"
            f"- HC density ≈ **{raw_hc:.2f}**  → × 20 =  **{v_hc*100:.1f}%**  (the GeoX number)  \n"
            f"- reservoir-failure density ≈ **{raw_res:.2f}**  → × 20 =  **{v_res*100:.1f}%**"
        )
        st.markdown(
            "**Why only the *relative* differences matter (the ×20 is irrelevant to the answer):**  \n"
            "Bayes' theorem normalises — the posterior depends only on the **ratios** of these "
            "likelihoods, because any constant multiplying *all* of them cancels top-and-bottom:"
        )
        st.latex(
            r"P(G\mid\text{DFI}) = \frac{L_\text{succ}\,\pi_\text{succ}}{\sum_k L_k\,\pi_k}"
            r" = \frac{(c\,L_\text{succ})\,\pi_\text{succ}}{\sum_k (c\,L_k)\,\pi_k}"
            r"\quad\text{for any }c"
        )
        st.markdown(
            "So whether you enter the raw densities, the ×20 GeoX values, or any other common multiple, "
            "**the posterior is identical**. What drives the update is how much *taller* the success "
            f"curve is than the failure curves at your DHI — here the HC : reservoir-failure ratio is "
            f"about **{ratio_hc_res:.2f} : 1**. That ratio is the real \"DHI Strength\" signal; the "
            "absolute percentages are just a convenient scale for data entry."
        )

    # Copy-friendly block + download
    txt = (
        f"GeoX P(DFI|case) inputs — DHI Index {dhi:+.0f}, SD mode {sd_mode}, "
        f"success class {succ_disp}, calibration v.{calib.version}"
        f"{' (placeholder)' if calib.is_placeholder else ''}\n"
        + "\n".join(f"  {lbl:<32} {val}" for lbl, val, _src in rows)
    )
    with st.expander("Copy / download these values", expanded=False):
        st.code(txt, language="text")
        st.download_button(
            "📥 Download GeoX P(DFI|case) (.txt)", data=txt,
            file_name=f"geox_pdfi_DHI{int(round(dhi))}.txt",
            key="geox_pdfi_dl",
        )
    st.caption(
        "ℹ️ Each value = per-class Gaussian density × 20 (the GeoX convention, "
        "expressed as a percentage). This constant scaling cancels inside E-POS's own "
        "posterior, so the numbers here are for GeoX entry only — the P(G | DFI) on the "
        "other sub-tabs is unaffected."
    )


def _render_posterior_class_panel(post, fluid_weights) -> None:
    """Horizontal bar chart of posterior outcome probabilities."""
    import plotly.graph_objects as go
    labels = [
        "Oil & eval-res (SUCCESS)",
        "Oil & non-eval-res (fail)",
        "Water & eval-res (fail)",
        "Water & non-eval-res (fail)",
        "LSG & eval-res (fail)",
        "LSG & non-eval-res (fail)",
        "Other & eval-res (fail)",
        "Other & non-eval-res (fail)",
    ]
    keys = [
        "oil_eval_success",
        "oil_noneval_failure",
        "water_eval_failure",
        "water_noneval_failure",
        "lsg_eval_failure",
        "lsg_noneval_failure",
        "other_eval_failure",
        "other_noneval_failure",
    ]
    colors = [
        "#16a34a",  # success — green
        "#fb923c",  # oil & non-eval — orange (reservoir failure)
        "#2563eb",  # water eval — blue
        "#1e40af",  # water non-eval — darker blue
        "#eab308",  # LSG eval — yellow
        "#a16207",  # LSG non-eval — darker yellow
        "#9333ea",  # other eval — purple
        "#581c87",  # other non-eval — darker purple
    ]
    values = [post.posterior_outcomes[k] * 100 for k in keys]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in values],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>P = %{x:.2f}%<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="P(outcome | DFI)  [%]", range=[0, max(values) * 1.20]),
        yaxis=dict(autorange="reversed"),  # success at top
        height=320, margin=dict(t=10, b=40, l=200, r=60),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Prior P(G, ESL)",  f"{post.prior_outcomes.oil_eval_success*100:.2f}%")
    col_b.metric("Posterior P(G | DFI, ESL)", f"{post.posterior_pg*100:.2f}%",
                 delta=f"{(post.posterior_pg - post.prior_outcomes.oil_eval_success)*100:+.2f}%")
    col_c.metric("R_DFI", f"{post.r_dfi:.2f}",
                 help="R_DFI (DHI-Index strength) = L_success / E[L | failure] — the "
                      "likelihood ratio from the Conceptual DHI Index (experimental) calibration. How much the "
                      "DFI evidence shifts the odds. Distinct from R_char on the "
                      "characteristic-scoring pathway.")


def _render_calibration_editor(calib) -> None:
    """Editable table + reset + JSON upload."""
    import pandas as pd
    import json
    from logic.dfi_calibration import ALL_CLASSES, CLASS_DISPLAY

    st.markdown("**Per-class calibration parameters** *(units: DHI Index / 100)*")

    rows = []
    for cn in ALL_CLASSES:
        s = calib.classes[cn]
        rows.append({
            "Class": CLASS_DISPLAY.get(cn, cn),
            "_class_id": cn,
            "Mean": float(s.mean),
            "SD (calc)": float(s.sd_calculated),
            "SD (upper)": float(s.sd_upper),
            "N": int(s.n),
        })
    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_class_id"])

    edited = st.data_editor(
        display_df,
        column_config={
            "Class":      st.column_config.TextColumn("Class",   disabled=True, width="medium"),
            "Mean":       st.column_config.NumberColumn("Mean",       format="%.4f", min_value=-0.5, max_value=1.0, step=0.001),
            "SD (calc)":  st.column_config.NumberColumn("SD (calc)",  format="%.4f", min_value=0.001, max_value=1.0, step=0.001),
            "SD (upper)": st.column_config.NumberColumn("SD (upper)", format="%.4f", min_value=0.001, max_value=1.0, step=0.001),
            "N":          st.column_config.NumberColumn("N",          format="%d",    min_value=1,     max_value=10000),
        },
        hide_index=True,
        use_container_width=True,
        key="dfi_calibration_editor_widget",
    )

    # Detect changes vs the base values and store as override dict
    overrides: dict[str, dict] = {}
    for i, cn in enumerate(ALL_CLASSES):
        base = calib.classes[cn]
        row  = edited.iloc[i]
        changes = {}
        if abs(float(row["Mean"])       - base.mean)          > 1e-6: changes["mean"]          = float(row["Mean"])
        if abs(float(row["SD (calc)"])  - base.sd_calculated) > 1e-6: changes["sd_calculated"] = float(row["SD (calc)"])
        if abs(float(row["SD (upper)"]) - base.sd_upper)      > 1e-6: changes["sd_upper"]      = float(row["SD (upper)"])
        if int(row["N"])                != base.n:                   changes["n"]              = int(row["N"])
        if changes:
            overrides[cn] = changes

    if overrides:
        st.session_state["dfi_calibration_override"] = overrides
    elif st.session_state.get("dfi_calibration_override"):
        st.session_state["dfi_calibration_override"] = None

    col_reset, col_upload = st.columns([1, 2])
    with col_reset:
        if st.button("↺ Reset to calibration defaults", help="Discard all in-UI edits"):
            st.session_state["dfi_calibration_override"] = None
            # Clear the data_editor widget state too
            st.session_state.pop("dfi_calibration_editor_widget", None)
            st.rerun()
    with col_upload:
        uploaded = st.file_uploader(
            "Upload calibration JSON (replaces in-UI edits)",
            type=["json"], key="dfi_calibration_upload",
            help="JSON schema: see data/dhi_calibration_placeholder.json",
        )
        if uploaded is not None:
            try:
                data = json.loads(uploaded.read().decode("utf-8"))
                # Validate minimal structure
                if "classes" not in data:
                    raise ValueError("Missing 'classes' key in uploaded JSON")
                from logic.dfi_calibration import ALL_CLASSES as _AC
                # Convert uploaded values into an override dict (every class fully replaces base)
                new_override: dict[str, dict] = {}
                for cn in _AC:
                    if cn not in data["classes"]:
                        raise ValueError(f"Missing class '{cn}' in uploaded JSON")
                    src = data["classes"][cn]
                    new_override[cn] = {
                        "mean":          float(src["mean"]),
                        "sd_calculated": float(src["sd_calculated"]),
                        "sd_upper":      float(src["sd_upper"]),
                        "n":             int(src.get("n", 1)),
                    }
                st.session_state["dfi_calibration_override"] = new_override
                st.session_state.pop("dfi_calibration_editor_widget", None)
                st.success(f"Uploaded calibration applied (version: {data.get('version','?')}).")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to load calibration JSON: {e}")


