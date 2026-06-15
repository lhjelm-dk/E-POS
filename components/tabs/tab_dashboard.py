"""Dashboard tab render function."""
from __future__ import annotations

import datetime

import streamlit as st

from components.colors import COMPANY_DEFAULT_WEIGHT
from components.render_helpers import (
    calculate_flag,
    policy_pos,
    render_flag,
    render_flag_stats,
)
from components.prospect_hub import (
    _compute_esl_for_hub,
    _compute_classic_pos_for_hub,
    _compute_classic_pos_with_range_for_hub,
    build_prospect_risk_data,
    _build_full_export_csv,
    _parse_csv_sections,
)
from logic.esl_pipeline import ESL_MODE_OPTIONS


def _render_dashboard_tab(ctx) -> None:
    """Render the Dashboard tab.  Called by _render_tabs."""
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
    _active_model_ref = ctx.active_model
    _pillar_colors = ctx.pillar_colors
    _pillar_display = ctx.pillar_display
    ESL_OPTIONS = MODE_OPTIONS = ctx.esl_options

    # ── Workflow onboarding ──────────────────────────────────────────────────
    st.markdown(
        "<div style='background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;"
        "padding:16px 20px;border-radius:10px;margin-bottom:8px;'>"
        "<b style='font-size:1.15rem;'>E-POS — Evidence-supported Probability of Success</b><br>"
        "<span style='font-size:0.85rem;opacity:0.85;'>"
        "Enter evidence once: ESL and Classic POS update together. "
        "The gap between them is your uncertainty signal."
        "</span></div>",
        unsafe_allow_html=True,
    )

    # Open onboarding automatically when no evidence has been entered yet
    _has_any_evidence = bool(play) and any(
        isinstance(el, dict) and (el.get("support_for", 0) > 0 or el.get("support_against", 0) > 0)
        for el in play.values()
    )
    # A freshly created / blank prospect: the "New" button names it "New Prospect"
    # and clears the loaded-file pointer. (Default models seed non-zero support, so
    # _has_any_evidence alone can't tell "untouched" from "assessed".)
    _is_fresh = (st.session_state.get("meta_title", "") in ("", "New Prospect")
                 and not st.session_state.get("current_prospect_file"))
    _show_getting_started = _is_fresh or not _has_any_evidence
    with st.expander("How E-POS works — workflow overview (click to open)",
                     expanded=_show_getting_started):
        # Concept flowchart as HTML table — no external dependencies
        st.markdown(
            """
<style>
.epos-flow {border-collapse:collapse;width:100%;font-size:0.82rem;}
.epos-flow td {padding:6px 10px;text-align:center;vertical-align:middle;}
.epos-box {background:#1e3a5f;color:#fff;border-radius:6px;padding:8px 12px;font-weight:600;}
.epos-arrow {font-size:1.4rem;color:#6b7280;}
.epos-out {background:#166534;color:#fff;border-radius:6px;padding:8px 12px;font-weight:600;}
</style>
<table class="epos-flow">
<tr>
  <td><div class="epos-box">① Field evidence<br><small style="font-weight:400;">seismic · wells · analogues</small></div></td>
  <td class="epos-arrow">→</td>
  <td><div class="epos-box">② Italian Flag per element<br><small style="font-weight:400;">S_for · White · S_against</small></div></td>
  <td class="epos-arrow">→</td>
  <td><div class="epos-box">③ Policy P<br><small style="font-weight:400;">S_for + w × White</small></div></td>
</tr>
<tr><td colspan="5" style="height:8px;"></td></tr>
<tr>
  <td colspan="2"></td>
  <td class="epos-arrow" style="font-size:1.4rem;">↓</td>
  <td colspan="2"></td>
</tr>
<tr>
  <td><div class="epos-out">P(G, ESL)<br><small style="font-weight:400;">P(Play) × P(Cond)</small></div></td>
  <td class="epos-arrow">←</td>
  <td><div class="epos-box">④ Pillar combination<br><small style="font-weight:400;">ALL · ANY · Product · IPT</small></div></td>
  <td class="epos-arrow">→</td>
  <td><div class="epos-out">P(G, Classic)<br><small style="font-weight:400;">∏ pillar Policy P</small></div></td>
</tr>
</table>
""",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("""
**Five-step workflow**

**① Assess Play pillars** *(Play tab)*
→ Set S_for / S_against for each regional pillar (Charge, Closure, Reservoir, Retention).

**② Assess Conditional elements** *(Conditional tab)*
→ Same evidence inputs, but for prospect-specific sub-elements within each pillar.

**③ Set your stance (w)** *(this panel, below)*
→ Controls how uncommitted (white) evidence maps to POS. Default = 0.5 (neutral).

**④ Review results** *(Geological POS tab)*
→ P(G, ESL), P(G, Classic), sensitivity tornado, and the Chance Adequacy Matrix.

**⑤ Sign off** *(this panel, bottom)*
→ Record analyst name, date, peer review status, and lock the assessment.
""")
        with col_b:
            st.markdown("""
**Coming from ROSE or GeoX?**

E-POS uses the same four pillars you already know.
Your existing probability estimates translate directly:

| Your ROSE input | E-POS equivalent |
|-----------------|-----------------|
| Charge POS = 0.60 | S_for = 0.60, S_against = 0.00 |
| Charge POS = 0.40 (uncertain) | S_for = 0.30, S_against = 0.20 |
| Charge POS = 0.20 (risky) | S_for = 0.10, S_against = 0.60 |

The key difference: E-POS **separates what you know (green/red) from what you don't know (white).**
A single probability of 0.40 could mean "strong evidence both ways" or "no data at all". E-POS makes that distinction explicit and auditable.

→ Use the **ROSE entry panel below** to enter your traditional single probabilities alongside the ESL assessment for a direct comparison.
""")

        st.markdown("---")
        st.markdown(
            "**Why does E-POS show two numbers?**  \n"
            "P(G, ESL) carries the unknown mass through the whole calculation, applying Policy P "
            "once at the end. P(G, Classic) converts each element to a single probability first, "
            "then multiplies, absorbing the unknown mass early. **The spread between them measures "
            "how much uncommitted evidence your assessment contains.** Large spread = data gaps "
            "dominate; small spread = robust evidence. See Theory tab for the full explanation."
        )

    st.divider()

    # ── Empty state — teach the workflow on a fresh / un-assessed prospect ──
    if _show_getting_started:
        st.markdown(
            "<div style='background:linear-gradient(135deg,#1e3a5f,#0f172a);color:#fff;"
            "padding:18px 22px;border-radius:10px;margin-bottom:6px;'>"
            "<div style='font-size:20px;font-weight:800;margin-bottom:4px;'>Getting started</div>"
            "<div style='font-size:14px;opacity:0.92;line-height:1.7;'>"
            "<b>① Assess Play</b> — open the <b>Play</b> tab and set the evidence for / against "
            "each regional pillar (Charge, Closure, Reservoir, Retention).<br>"
            "<b>② Assess Conditional</b> — the <b>Conditional</b> tab, for the prospect-specific "
            "sub-elements.<br>"
            "<b>③ Read your result</b> — your <b>P(G, ESL)</b> and <b>P(G, Classic)</b> appear here "
            "and on the <b>Geological POS</b> tab.</div></div>",
            unsafe_allow_html=True,
        )
        st.caption("▶ Start on the **Play** tab above. The numbers below are **model defaults** "
                   "until you enter evidence.")

    # Italian flags — P(Play) / P(Cond) / P(G, ESL)
    est_pos = policy_pos(total_for, total_against, uncertainty_weight)
    play_pos_val = policy_pos(play_for, play_against, uncertainty_weight)
    cond_pos_val = policy_pos(conditional_for, conditional_against, uncertainty_weight)

    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        st.metric("P(Play)", f"{play_pos_val * 100:.1f}%",
                  help="Play-level geological probability, combined across all pillars at Play scope.")
        render_flag(play_for, play_against, marker=play_pos_val)
        render_flag_stats(play_for, play_against, uncertainty_weight)
    with pc2:
        st.metric("P(Cond)", f"{cond_pos_val * 100:.1f}%",
                  help="Conditional-level geological probability, combined across all pillars at Conditional scope.")
        render_flag(conditional_for, conditional_against, marker=cond_pos_val)
        render_flag_stats(conditional_for, conditional_against, uncertainty_weight)
    with pc3:
        st.metric("P(G, ESL)", f"{est_pos * 100:.1f}%",
                  help="Total prospect probability via ESL = P(Play) × P(Cond), computed on mass pairs.")
        render_flag(total_for, total_against, marker=est_pos)
        render_flag_stats(total_for, total_against, uncertainty_weight)

    g_t, w_t, r_t, _, _ = calculate_flag(total_for, total_against)
    st.markdown(
        f"<div style='display:flex;gap:24px;align-items:baseline;margin:4px 0 2px;"
        f"font-size:0.83rem;color:#374151;'>"
        f"<span><b style='color:#16a34a;'>Bel(G)</b>&nbsp;"
        f"<span style='font-size:1.05rem;font-weight:700;'>{g_t*100:.1f}%</span></span>"
        f"<span style='color:#aaa;'>·</span>"
        f"<span><b style='color:#6b7280;'>White</b>&nbsp;"
        f"<span style='font-size:1.05rem;font-weight:700;'>{w_t*100:.1f}%</span></span>"
        f"<span style='color:#aaa;'>·</span>"
        f"<span><b style='color:#2563eb;'>Pl(G)</b>&nbsp;"
        f"<span style='font-size:1.05rem;font-weight:700;'>{(1-r_t)*100:.1f}%</span></span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    _stance_name = {"neutral": "neutral", "custom": "custom", "base_rate": "base rate"}.get(
        st.session_state.get("stance_mode", "neutral"), "neutral")
    st.caption(f"Stance on unknowns **w = {uncertainty_weight:.2f}** ({_stance_name}) — "
               "change it in **⚙ Advanced** below.")

    st.divider()

    # ── DFI / DHI prospect toggle (Phase 3) — separate section ──────────────
    # Scoped CSS: enlarge *this* toggle (and its label) only. The marker span
    # sits in the element-container immediately before the toggle's container,
    # so the sibling :has() selector targets just this widget, not other toggles.
    _dfi_on_now = bool(st.session_state.get("dfi_enabled", False))
    _accent = "#16a34a" if _dfi_on_now else "#2563eb"
    st.markdown(
        """
        <style>
        /* Enlarge ONLY the DFI toggle: the .dfi-anchor marker sits in the
           element-container immediately before the toggle, so this adjacent
           sibling selector targets just this widget. */
        [data-testid="element-container"]:has(.dfi-anchor)
          + [data-testid="element-container"] [data-baseweb="checkbox"] {
            transform: scale(1.45); transform-origin: left center;
            margin: 8px 0 8px 8px; }
        [data-testid="element-container"]:has(.dfi-anchor)
          + [data-testid="element-container"] [data-baseweb="checkbox"] div[class] {
            font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:10px;"
            f"margin:-2px 0 4px;'>"
            f"<span style='font-size:21px;font-weight:800;color:#0f172a;'>"
            f"Direct Fluid Indicator (DFI)</span>"
            f"<span style='font-size:13px;font-weight:700;color:{_accent};"
            f"border:1.5px solid {_accent};border-radius:10px;padding:1px 9px;'>"
            f"{'ON' if _dfi_on_now else 'OFF'}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<span class='dfi-anchor'></span>", unsafe_allow_html=True)
        _dfi_prev = bool(st.session_state.get("dfi_enabled", False))
        _dfi_new = st.toggle(
            "**DFI-capable prospect?** — apply the Bayesian DFI update",
            value=_dfi_prev,
            key="dfi_enabled",
            help=(
                "**The most decisive evidence switch in the workflow.**\n\n"
                "Turn ON whenever the subsurface is **capable of showing a DFI**, i.e. the "
                "reservoir/fluid contrast and seismic quality are such that a direct fluid "
                "indicator *would* be visible if hydrocarbons were present. This is not just "
                "for prospects where a DFI is seen: a **DFI that is absent when one was "
                "expected is itself evidence**, and the update will then *lower* P(G).\n\n"
                "The update is a true Bayesian conditioning; it can raise **or** lower the "
                "prior. A strong, conformant DFI lifts P(G); a weak/absent DFI on a "
                "DFI-capable prospect downgrades it."
            ),
        )
        # Seed the DFI session-state defaults whenever the toggle is on. The
        # initialiser is idempotent (setdefault), and gating it on the OFF->ON
        # transition alone misses sessions restored with dfi_enabled already
        # true (saved prospects), leaving dfi_source unset and hiding the
        # post-DFI views until DFI Setup was visited.
        if _dfi_new:
            from components.tabs.tab_dfi import initialise_dfi_session_defaults
            initialise_dfi_session_defaults()
        if _dfi_new:
            st.caption(
                f"DFI active — DHI index = **{st.session_state.get('dfi_index', 8):.0f}**, "
                f"water/LSG/other = "
                f"{st.session_state.get('dfi_fluid_water', 0.5):.0%}/"
                f"{st.session_state.get('dfi_fluid_lsg',   0.2):.0%}/"
                f"{st.session_state.get('dfi_fluid_other', 0.3):.0%}. "
                "Edit on the Bayesian DFI Update tab."
            )
        else:
            st.caption("DFI not in use: comparison table will show priors only.")

    st.divider()

    # Uncertainty weight / stance controls — demoted into an Advanced expander
    # (sensible default; most users never change it). A compact read-out sits up
    # top near the headline result.
    with st.expander("⚙ Advanced — stance on unknowns (w)", expanded=False):
        col_w, col_info = st.columns([3, 1])
        with col_w:
            st.markdown("**Stance on unknowns (w)** — Policy P = S_for + w × White")
            st.caption(
                "Every risk element splits into evidence **for** success, evidence "
                "**against**, and an uncommitted **white** band (the unknowns). *Stance* "
                "(w) decides which way that white band leans when we collapse the Italian "
                "Flag to a single POS number: **0** = treat all unknowns as bad news "
                "(pessimistic), **0.5** = stay neutral (recommended), **1** = give the "
                "unknowns the benefit of the doubt (optimistic). It changes only how "
                "unknowns are scored, never the hard evidence itself."
            )
            from components.ui_help import help_popover as _help_popover
            _help_popover("What is Stance on unknowns (w)?", (
                "**Stance (w)** controls how the uncommitted *white* evidence contributes to POS:\n\n"
                "| w | Interpretation |\n|---|---|\n"
                "| **0.0** | All unknowns count against success — pessimistic lower bound (= Belief) |\n"
                "| **0.5** | Unknowns split 50/50 — neutral, Laplace principle (**recommended default**) |\n"
                "| **1.0** | All unknowns count for success — optimistic upper bound (= Plausibility) |\n\n"
                "**Formula:** Policy P = S_for + w × White  \n"
                "This maps the Italian Flag's white segment to a point-estimate POS between Bel (= S_for) "
                "and Pl (= 1 − S_against).  \n\n"
                "Set w once for the whole prospect here. Individual risk elements can override it "
                "in their CAM panel (shown with ⚑ indicator)."))
            from logic.pos_policy import DEFAULT_BASE_RATE
            _stance_lbl = {
                "neutral":   "Neutral — w = 0.5 (split unknowns 50/50, Laplace)",
                "custom":    "Custom stance w",
                "base_rate": "Base rate (revert unknowns to the base rate — Exxon)",
            }
            _modes = ["neutral", "custom", "base_rate"]
            # Migrate the legacy use_policy_weight flag on first render.
            if "stance_mode" not in st.session_state:
                st.session_state["stance_mode"] = (
                    "neutral" if st.session_state.get("use_policy_weight", True) else "custom")
            _sel = st.radio(
                "Stance on unknowns",
                options=_modes,
                format_func=lambda m: _stance_lbl[m],
                key="stance_mode",
                help="How the uncommitted *white* band is scored when the Italian Flag is "
                     "collapsed to a point POS. Neutral treats the unknowns as a coin; "
                     "Base rate reverts them to the prospect base rate (Exxon 2018: "
                     "'geology is not a coin').",
            )
            if _sel == "custom":
                w_curr_dash = float(st.session_state.get("uncertainty_weight_slider", 0.5))
                from components.element_detail_cam import _w_label as _dash_w_label
                st.slider(
                    f"Stance (w) — {_dash_w_label(w_curr_dash)}",
                    0.0, 1.0, w_curr_dash, 0.05,
                    key="uncertainty_weight_slider",
                    help="0 = unknowns vote against success (Bel). 0.5 = neutral. "
                         "1 = unknowns vote for success (Pl). POS = S_for + w × White.",
                )
                st.text_area(
                    "Justification for stance override", key="weight_justification",
                    placeholder="Document why this prospect warrants a stance different from company default...",
                )
            elif _sel == "base_rate":
                _bc1, _bc2 = st.columns([2, 1])
                with _bc1:
                    st.number_input(
                        "Prospect base rate", min_value=0.0, max_value=1.0,
                        value=float(st.session_state.get("stance_base_rate", DEFAULT_BASE_RATE)),
                        step=0.05, key="stance_base_rate",
                        help="Policy P = S_for + base_rate × White. 'Knowing nothing' "
                             "reverts the unknowns to this base rate, not a 50/50 coin.")
                with _bc2:
                    st.write(""); st.write("")

                    def _seed_base_rate():
                        import math
                        from components.calibration import ROSE_RANGES
                        _meds = [v[2] / 100.0 for v in ROSE_RANGES.values()]
                        st.session_state["stance_base_rate"] = (
                            round(math.prod(_meds), 2) if _meds else DEFAULT_BASE_RATE)
                    st.button("↧ Seed from Rose medians", on_click=_seed_base_rate,
                              key="seed_base_rate",
                              help="Product of the per-pillar Rose median POS, the analogue "
                                   "prospect base rate (≈ 18%).")
                st.caption("Exxon 'geology is not a coin': the white band reverts to the base rate.")
            else:
                st.caption(f"Neutral stance w = {COMPANY_DEFAULT_WEIGHT} (unknowns split 50/50).")
        with col_info:
            from components.element_detail_cam import _w_label as _dash_w_label2
            st.metric("Stance (w)", f"{uncertainty_weight:.2f}")
            st.caption(_dash_w_label2(uncertainty_weight))

    st.divider()

    # Per-pillar P(pillar) — colour-coded by risk level
    st.markdown("**Per-pillar P(pillar) = P(pillar, Play) × P(pillar, Cond)** — colour-coded by risk level:")
    # Fallback list is the default 4-pillar set, used only if no active risk model is loaded.
    # Once a model is loaded, _pillar_colors.keys() drives this dynamically.
    _dyn_pillars = list(_pillar_colors.keys()) if _pillar_colors else ["Charge", "Closure", "Reservoir", "Retention"]
    pg_cols = st.columns(max(len(_dyn_pillars), 1))
    _pillar_pg_values: list[tuple[str, float]] = []
    for _i, _pid in enumerate(_dyn_pillars):
        _pdn = _pillar_display.get(_pid, _pid)
        _pf = r.pillar_for.get(_pid, 0.5)
        _pa = r.pillar_against.get(_pid, 0.1)
        _cr = conditional_results.get(_pid, {"for": 0.5, "against": 0.1})
        _pg = (
            policy_pos(_pf, _pa, uncertainty_weight)
            * policy_pos(_cr["for"], _cr["against"], uncertainty_weight)
        )
        _pillar_pg_values.append((_pdn, _pg))
        # Risk-level border colour (left edge) — green/amber/red
        if _pg >= 0.50:
            _risk_border, _risk_label = "#16a34a", "robust"
        elif _pg >= 0.30:
            _risk_border, _risk_label = "#f59e0b", "ambiguous"
        else:
            _risk_border, _risk_label = "#dc2626", "risk driver"
        _col_bg = _pillar_colors.get(_pid, "#e5e7eb")
        pg_cols[_i].markdown(
            f"<div style='background:{_col_bg};padding:10px;border-left:6px solid {_risk_border};"
            f"border-radius:6px;text-align:center;'>"
            f"<b>{_pdn}</b><br>"
            f"<span style='font-size:1.5rem;font-weight:700;'>{_pg * 100:.0f}%</span><br>"
            f"<span style='font-size:0.7rem;color:#374151;text-transform:uppercase;letter-spacing:0.04em;'>"
            f"{_risk_label}</span></div>",
            unsafe_allow_html=True,
        )
    # Highlight the weakest pillar as the key risk driver
    if _pillar_pg_values:
        _weakest = min(_pillar_pg_values, key=lambda x: x[1])
        st.caption(
            f"🎯 **Key risk driver:** {_weakest[0]} ({_weakest[1]*100:.0f}%). "
            f"Improving this pillar has the largest impact on total Pg. "
            f"Colour bands: 🟢 ≥ 50% robust · 🟡 30–50% ambiguous · 🔴 < 30% risk driver."
        )

    st.divider()

    # Classic POS source — ESL-derived (default) or ROSE override
    _esl_classic_range = _compute_classic_pos_with_range_for_hub(models)
    _esl_classic = _esl_classic_range[0] if _esl_classic_range is not None else None
    _esl_bel     = _esl_classic_range[1] if _esl_classic_range is not None else None
    _esl_pl      = _esl_classic_range[2] if _esl_classic_range is not None else None
    _rose_is_active = st.session_state.get("rose_classic_pos_entered", False)
    _mode_badge = (
        "🟡 **OVERRIDE** — sourced from manually entered ROSE values"
        if _rose_is_active
        else "🟢 **ESL-derived** — computed automatically from your evidence"
    )
    with st.expander(
        f"📊 Classic POS — source and optional ROSE override — {_mode_badge}",
        expanded=_rose_is_active,
    ):
        st.caption(
            "**ESL-derived is the default** (Classic POS = ∏ pillar Policy P — fully "
            "traceable to your evidence). Use the **ROSE override** only to display a "
            "pre-existing external estimate alongside it; document its source for audit. "
            "▸ The P(G, Classic) method & the ESL↔Classic bridge: **Theory & Guide → "
            "\"P(G, Classic) — the multiplicative method\"** and **\"Why P(G, ESL) ≠ "
            "P(G, Classic)\"**."
        )

        if _esl_classic is not None and _esl_bel is not None and _esl_pl is not None:
            _esl_display = (
                f"Bel {_esl_bel*100:.1f}% · **POS {_esl_classic*100:.1f}%** · Pl {_esl_pl*100:.1f}%"
            )
        elif _esl_classic is not None:
            _esl_display = f"**{_esl_classic*100:.1f}%**"
        else:
            _esl_display = "—  *(complete Play + Conditional tabs)*"
        st.info(
            f"ESL-derived Classic POS (current): {_esl_display}  \n"
            "This is what the comparison table uses unless a ROSE override is active below."
        )

        st.markdown("---")
        st.markdown(
            "**Enter independent ROSE probabilities per pillar** — set all to 0.00 to deactivate the override:"
        )

        _rose_cols = st.columns(len(_pillar_colors) or 4)
        _rose_vals: list[float] = []
        for _ri, (_rpid, _rpcolor) in enumerate(_pillar_colors.items()):
            _rdn = _pillar_display.get(_rpid, _rpid)
            _rkey = f"classic_{_rpid.lower()}"
            _rdefault = float(st.session_state.get(_rkey, 0.0))
            with _rose_cols[_ri]:
                st.markdown(
                    f"<div style='background:{_rpcolor};padding:4px 8px;"
                    f"border-radius:4px;font-weight:700;margin-bottom:4px;'>{_rdn}</div>",
                    unsafe_allow_html=True,
                )
                _rv = st.slider(
                    f"ROSE POS — {_rdn}",
                    0.0, 1.0, _rdefault, 0.05,
                    key=_rkey,
                    label_visibility="collapsed",
                    help=f"Traditional single probability for {_rdn}. Set to 0.00 to use ESL-derived.",
                )
                st.caption(f"{_rv*100:.0f}%")
                _rose_vals.append(_rv)

        _rose_entered = all(v > 0.0 for v in _rose_vals)

        if _rose_entered:
            from logic.pos_logic import classic_pos_product as _cpp
            _rose_total = _cpp(_rose_vals)
            _diff = (_rose_total - (_esl_classic or 0.0)) * 100
            _diff_str = f"+{_diff:.1f}%" if _diff >= 0 else f"{_diff:.1f}%"

            _rose_justification = st.text_area(
                "Source & justification for this ROSE entry (required for audit trail)",
                key="rose_justification",
                placeholder=(
                    "Example: Pre-drill assessment by [analyst], [date], using GeoX v4. "
                    "Prospect file ref. XX-YYYY. Entered here for comparison only — "
                    "ESL assessment is the primary method."
                ),
            )
            _has_justification = bool(st.session_state.get("rose_justification", "").strip())

            st.warning(
                f"**OVERRIDE ACTIVE** — the comparison table is using your manually entered ROSE values, "
                f"not the ESL-derived estimate. Ensure the justification above is complete before sign-off.\n\n"
                f"| | Classic POS |\n|---|---|\n"
                f"| ROSE (override — shown in table) | **{_rose_total*100:.1f}%** |\n"
                f"| ESL-derived (suppressed) | {(_esl_classic or 0.0)*100:.1f}% |\n"
                f"| Difference | {_diff_str} |"
            )
            if not _has_justification:
                st.error("Justification is empty — document the source of the ROSE estimate above before signing off.")

            st.session_state["comparison_classic_pos"] = _rose_total
            st.session_state["rose_classic_pos_entered"] = True

        else:
            st.session_state["rose_classic_pos_entered"] = False
            st.session_state.pop("rose_justification", None)
            if _esl_classic is not None:
                st.success(
                    f"ESL-derived mode active — Classic POS = **{_esl_classic*100:.1f}%** "
                    f"(∏ pillar Policy P combined with selected Classic operator). Fully traceable to your ESL evidence."
                )
            else:
                st.caption("Complete the ESL assessment (Play + Conditional tabs) to see the ESL-derived Classic POS here.")

    # Comparison table
    # Note: Bel/Pl are passed directly to render_comparison via local vars below,
    # so we deliberately do NOT persist them in session_state (would lag by one render).
    if not st.session_state.get("rose_classic_pos_entered", False):
        if _esl_classic is not None:
            st.session_state["comparison_classic_pos"] = _esl_classic

    _rose_active = st.session_state.get("rose_classic_pos_entered", False)
    _dfi_active = bool(st.session_state.get("dfi_enabled", False))

    if _dfi_active:
        # 2x2 layout: rows = ESL/Classic, columns = prior/posterior
        # Compute posteriors using the current DFI inputs from session state.
        from logic.dfi_context import (
            get_effective_calibration      as _get_effective_calibration,
            esl_prior_pillars_from_ctx_at_w as _esl_prior_pillars_from_ctx_at_w,
            classic_prior_pillars_from_ctx as _classic_prior_pillars_from_ctx,
            esl_rollup_prior_at_w          as _esl_rollup_prior_at_w,
        )
        # Build a thin ctx-like with the attributes _esl_prior_pillars_from_ctx_at_w needs
        class _Ctx:
            pass
        _ctx_lite = _Ctx()
        _ctx_lite.play                = play
        _ctx_lite.conditional         = conditional
        _ctx_lite.conditional_results = conditional_results
        _ctx_lite.uncertainty_weight  = uncertainty_weight
        _ctx_lite.total_for     = st.session_state.get("comparison_esl_total_for")
        _ctx_lite.total_against = st.session_state.get("comparison_esl_total_against")

        _dfi_source = str(st.session_state.get("dfi_source", "dhi_index"))
        try:
            _prior_e = _esl_prior_pillars_from_ctx_at_w(_ctx_lite, uncertainty_weight)
            _prior_c = _classic_prior_pillars_from_ctx(_ctx_lite, uncertainty_weight)
            _esl_prior_pg = _esl_rollup_prior_at_w(_ctx_lite, uncertainty_weight)
            from components.comparison import render_comparison_dfi
            if _dfi_source in ("characteristic", "custom"):
                # Simm 2-state Bayes against the prospect's ESL & Classic priors
                from logic.dhi_characteristics import (
                    simm_bayes_posterior, dhi_score_from_r,
                )
                if _dfi_source == "custom":
                    _r_eff = float(st.session_state.get("dhi_custom_r",     1.0))
                    _score = float(st.session_state.get("dhi_custom_score", 50.0))
                else:
                    _r_eff = float(st.session_state.get("dhi_char_r_eff",  1.0))
                    _score = float(st.session_state.get("dhi_char_score",  50.0))
                _post_e_pg = simm_bayes_posterior(_esl_prior_pg, _r_eff)
                _post_c_pg = simm_bayes_posterior(_prior_c.prior_pg, _r_eff)
                render_comparison_dfi(
                    prior_esl     = _esl_prior_pg,
                    prior_classic = _prior_c.prior_pg,
                    post_esl      = _post_e_pg,
                    post_classic  = _post_c_pg,
                    esl_sf        = st.session_state.get("comparison_esl_total_for"),
                    esl_sa        = st.session_state.get("comparison_esl_total_against"),
                    classic_bel   = None if _rose_active else _esl_bel,
                    classic_pl    = None if _rose_active else _esl_pl,
                    dhi_index     = None,          # not applicable in characteristic mode
                    dhi_strength  = _r_eff,        # R_eff serves the same diagnostic role
                    dhi_volume    = _score / 100.0,
                    prospect_title= prospect_title,
                )
            else:
                from logic.dfi_bayes import compute_dfi_posterior
                from logic.dfi_inputs import read_dfi_inputs
                _calib = _get_effective_calibration()
                _inp = read_dfi_inputs(st.session_state)
                _fw, _dhi, _sd, _ftyp = (_inp.fluid_weights, _inp.dhi,
                                         _inp.sd_mode, _inp.fluid_type)
                _post_e  = compute_dfi_posterior(_prior_e, _dhi, _calib, _fw, _sd, _ftyp,
                                                 prior_pg_override=_esl_prior_pg)
                _post_c  = compute_dfi_posterior(_prior_c, _dhi, _calib, _fw, _sd, _ftyp)
                render_comparison_dfi(
                    prior_esl     = _esl_prior_pg,
                    prior_classic = _prior_c.prior_pg,
                    post_esl      = _post_e.posterior_pg,
                    post_classic  = _post_c.posterior_pg,
                    esl_sf        = st.session_state.get("comparison_esl_total_for"),
                    esl_sa        = st.session_state.get("comparison_esl_total_against"),
                    classic_bel   = None if _rose_active else _esl_bel,
                    classic_pl    = None if _rose_active else _esl_pl,
                    dhi_index     = _dhi,
                    dhi_strength  = _post_e.r_dfi,
                    dhi_volume    = _post_e.dhi_volume_weight,
                    prospect_title= prospect_title,
                )
        except Exception as _e:
            st.error(f"DFI comparison failed: {_e}. Falling back to prior-only view.")
            from components.comparison import render_comparison
            render_comparison(
                classic_pos=st.session_state.get("comparison_classic_pos", 0.0),
                esl_pos=st.session_state.get("comparison_esl_pos"),
                classic_bel=None if _rose_active else _esl_bel,
                classic_pl=None  if _rose_active else _esl_pl,
                prospect_title=prospect_title,
                meta_basin=st.session_state.get("meta_basin", ""),
                meta_analyst=st.session_state.get("meta_analyst", ""),
                meta_date=st.session_state.get("meta_date", ""),
            )
    else:
        from components.comparison import render_comparison
        render_comparison(
            classic_pos=st.session_state.get("comparison_classic_pos", 0.0),
            esl_pos=st.session_state.get("comparison_esl_pos"),
            classic_bel=None if _rose_active else _esl_bel,
            classic_pl=None  if _rose_active else _esl_pl,
            prospect_title=prospect_title,
            meta_basin=st.session_state.get("meta_basin", ""),
            meta_analyst=st.session_state.get("meta_analyst", ""),
            meta_date=st.session_state.get("meta_date", ""),
        )
    if _rose_active:
        st.caption(
            "⚠️ Classic POS shown is your **manually entered ROSE override**, not derived from ESL. "
            "Open the Classic POS source panel above to view or remove the override."
        )
    else:
        st.caption(
            "Classic POS shown is ESL-derived — computed from your evidence, "
            "not a manually entered probability. To compare against an independent ROSE estimate, "
            "expand the Classic POS source panel above."
        )

    st.divider()

    # Prospect Risk Data — export / import
    with st.expander("Prospect Risk Data — export & import", expanded=False):
        _esl_result = _compute_esl_for_hub(models)
        if _esl_result:
            _logic_rows, _node_index, _mode_index, _dep_index = _esl_result
            st.session_state.update({
                "hub_logic_rows": _logic_rows,
                "hub_node_index": _node_index,
                "hub_mode_index": _mode_index,
                "hub_dep_index": _dep_index,
            })
        else:
            _logic_rows = st.session_state.get("hub_logic_rows", [])
            _node_index = st.session_state.get("hub_node_index", {})
            _mode_index = st.session_state.get("hub_mode_index", {})
            _dep_index = st.session_state.get("hub_dep_index", {})

        _prd = (
            build_prospect_risk_data(
                _logic_rows,
                classic_pos=st.session_state.get("comparison_classic_pos"),
                esl_pos=st.session_state.get("comparison_esl_pos"),
            )
            if _logic_rows else []
        )
        if _prd:
            _rose_active = st.session_state.get("rose_classic_pos_entered", False)
            _classic_src = "ROSE entry (independently entered above)" if _rose_active else "ESL-derived (∏ pillar Policy P — enter ROSE values above for a true comparison)"
            st.caption(
                f"First row = summary result per method. "
                f"p_g_classic source: {_classic_src}. "
                "p_g_esl = ESL aggregated point estimate at current stance w."
            )
            st.dataframe(_prd, use_container_width=True, hide_index=True)
            _ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            _full_csv = _build_full_export_csv(
                models=models, logic_rows=_logic_rows,
                classic_pos=st.session_state.get("comparison_classic_pos", 0.0),
                esl_pos=st.session_state.get("comparison_esl_pos"),
                meta_title=prospect_title,
                meta_analyst=st.session_state.get("meta_analyst", ""),
                meta_basin=st.session_state.get("meta_basin", ""),
                meta_date=st.session_state.get("meta_date", ""),
                meta_version=st.session_state.get("meta_version", ""),
                timestamp=_ts,
            )
            _safe = prospect_title.replace(" ", "_")[:24]
            st.download_button(
                "📥 Download Full Assessment CSV", data=_full_csv,
                file_name=f"{_safe}_{_ts}.csv", mime="text/csv",
                key="hub_full_csv_download",
            )
        else:
            st.info("Complete the ESL evaluation (Play + Conditional tabs) to enable export.")

        # CSV import
        _local_mode_opts = list(ESL_MODE_OPTIONS) + [
            "Classic (min/max)", "Classic (max/max)", "Classic (avg)",
        ]
        _meta_map = {
            "Meta/Title": "meta_title",
            "Meta/Analyst": "meta_analyst",
            "Meta/Basin": "meta_basin",
            "Meta/Date": "meta_date",
            "Meta/Version": "meta_version",
        }
        uploaded = st.file_uploader("Import CSV (updates ESL leaf values, operators, dependencies)",
                                    type=["csv"], key="hub_import_csv")
        if uploaded and _node_index:
            import io as _io_mod, csv as _csv_mod
            _sections = _parse_csv_sections(uploaded.getvalue().decode("utf-8"))

            _esl_text = _sections.get("ESL Risk Element Detail", "")
            if _esl_text.strip():
                for row in _csv_mod.DictReader(_io_mod.StringIO(_esl_text)):
                    _nid = (row.get("node_id") or "").strip()
                    if not _nid:
                        continue
                    if _nid in _meta_map:
                        st.session_state[_meta_map[_nid]] = row.get("meta_value", "")
                        continue
                    if _nid in _node_index:
                        _elem = _node_index[_nid]
                        for _k, _v in [
                            ("support_for", row.get("support_for")),
                            ("support_against", row.get("support_against")),
                            ("suff_for", row.get("suff_for")),
                            ("suff_against", row.get("suff_against")),
                        ]:
                            if _v:
                                try:
                                    _elem[_k] = float(_v)
                                except ValueError:
                                    pass
                    if _nid in _mode_index and row.get("operator") in _local_mode_opts:
                        st.session_state[_mode_index[_nid]] = row.get("operator")
                    if _nid in _dep_index and row.get("dependency"):
                        try:
                            st.session_state[_dep_index[_nid]] = float(row.get("dependency"))
                        except ValueError:
                            pass

            _cop_text = _sections.get("Classic POS Operators", "")
            if _cop_text.strip():
                from logic.esl_pipeline import CLASSIC_POS_OPERATOR_OPTIONS as _cv_import
                for row in _csv_mod.DictReader(_io_mod.StringIO(_cop_text)):
                    _nid = (row.get("node_id") or "").strip()
                    _cop_val = row.get("classic_operator", "")
                    if _cop_val in _cv_import and _nid.startswith("classic_mode_"):
                        st.session_state[_nid] = _cop_val

            st.success("Import complete. Data updated.")
            st.rerun()

    # Sign-off + Risk Model
    st.divider()
    with st.expander("Assessment Sign-off & Audit Trail", expanded=False):
        from components.audit import render_audit_panel
        render_audit_panel(
            pos=policy_pos(total_for, total_against, uncertainty_weight),
            method="ESL",
            prospect_title=prospect_title,
        )

    st.divider()
    from components.model_builder import render_model_section
    render_model_section()
