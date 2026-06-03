"""Bayesian Network module — DERIVED priors from ESL, CPT elicitation only.

Root node priors come from ESL Policy POS. CPT questions (3–5 per pillar) require input.
P(Discovery) = structural sensitivity check, not independent assessment.
"""

from __future__ import annotations

import streamlit as st

from components.calibration import render_calibration_anchor
from logic.bn_logic import (
    BN_PILLAR_SLOT,
    DEFAULT_CPTS,
    N_BN_ROOT_SLOTS,
    PGMPY_AVAILABLE,
    build_petroleum_bn,
    query_pos,
)
from logic.pos_logic import classic_pos_product
from logic.pos_policy import policy_pos as _policy_pos, resolve_stance, get_active_pillars
from logic.esl_pipeline import (
    group_by_label,
    combine_classic_pos,
    make_session_classic_mode_getter,
)
from components.hierarchy_chart import render_bn_hierarchy
from components.overview_table import render_overview_table


def render_bayesian(models: dict | None = None) -> None:
    """
    Bayesian Network tab — DERIVED priors from ESL Policy POS.
    Root priors = Policy POS per pillar. Only CPT elicitation requires input.
    """
    st.markdown(
        "<div style='background:#1e3a5f;color:#fff;padding:12px 16px;border-radius:6px;margin-bottom:4px;"
        "border-left:6px solid #8b5cf6;'>"
        "<b>Bayesian Network — structural sensitivity</b></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "P(Discovery) from the causal DAG. Root priors come from your ESL Policy POS. "
        "Change values in the ESL tab above. CPT questions below encode geological dependencies."
    )

    if not PGMPY_AVAILABLE:
        st.error("**pgmpy** is not installed. Run: `pip install pgmpy`")
        st.caption("The BN module requires pgmpy for inference.")
        return

    if models is None:
        models = st.session_state.get("models", {})
    play = models.get("play", {})
    conditional = models.get("conditional", {})
    uw = resolve_stance()

    if not play or not conditional:
        st.info("Complete the ESL assessment first. P(Discovery) will appear here automatically.")
        return

    pillars = get_active_pillars()
    get_classic_mode = make_session_classic_mode_getter(st.session_state)

    # Root priors from ESL Policy POS (read-only)
    st.subheader("Root node priors (from ESL Policy POS)")
    st.caption("These values come from your ESL assessment. To change them, edit the ESL tab above.")
    play_probs: list[float] = []
    play_cols = st.columns(max(len(pillars), 1))
    for idx, pdef in enumerate(pillars):
        cat        = pdef["pillar_id"]
        display_cat = pdef["display_name"]
        color      = pdef.get("color", "#e5e7eb")
        el = play.get(cat, {})
        with play_cols[idx]:
            if isinstance(el, dict) and "support_for" in el:
                elem_w = float(st.session_state.get(f"w_esl_play_{cat}", uw))
                p = _policy_pos(el["support_for"], el["support_against"], elem_w)
                play_probs.append(p)
                st.markdown(f"<div style='background:{color};padding:10px;border-radius:6px;text-align:center;'>", unsafe_allow_html=True)
                st.metric(display_cat, f"{p*100:.0f}%", help=f"From ESL: S(H)={el['support_for']:.2f}, S(¬H)={el['support_against']:.2f}, w={elem_w:.2f}")
                st.markdown("</div>", unsafe_allow_html=True)
                render_calibration_anchor(cat, p)
            else:
                play_probs.append(1.0)  # un-assessed pillar → neutral (no restriction)

    play_chance = classic_pos_product(play_probs)

    st.divider()
    st.subheader("Conditional Prospect Chance (derived from ESL)")
    cond_probs: list[float] = []
    for idx, pdef in enumerate(pillars):
        cat   = pdef["pillar_id"]
        elems = conditional.get(cat, [])
        if not elems:
            cond_probs.append(1.0)
            continue

        elem_prob_map: dict[int, float] = {
            id(e): _policy_pos(
                e["support_for"], e["support_against"],
                float(st.session_state.get(f"w_esl_cond_{cat}_{i}", uw)),
            )
            for i, e in enumerate(elems)
        }
        grouped = group_by_label(elems)
        group_results: list[float] = []
        for grp_label, grp_elems in grouped.items():
            group_key = f"cond_{cat}_{grp_label}"
            grp_mode = get_classic_mode(f"classic_mode_group_{group_key}")
            group_results.append(combine_classic_pos(
                [elem_prob_map[id(e)] for e in grp_elems], grp_mode
            ))
        pillar_mode = get_classic_mode(f"classic_mode_cond_{cat}")
        cond_probs.append(combine_classic_pos(group_results, pillar_mode))

    cond_chance = classic_pos_product(cond_probs)

    # CPT elicitation (3–5 questions per pillar)
    st.divider()
    st.subheader("CPT elicitation (geological dependencies)")
    st.caption(
        "Conditional probabilities for derived nodes. Defaults from North Sea analogue data. "
        "Change only if you have basin-specific analogue statistics."
    )
    cpt_overrides = {}
    with st.container(border=True):
        st.caption("Edit CPT values")
        st.markdown("**Charge CPT** — P(Charge=Adequate | SourceMaturity, ClosureGeometry)")
        cc = st.columns(4)
        labels_charge = ["Src✓ Cls✓", "Src✓ Cls✗", "Src✗ Cls✓", "Src✗ Cls✗"]
        defaults_charge = DEFAULT_CPTS["Charge"]
        charge_vals = [
            cc[j].number_input(labels_charge[j], 0.0, 1.0, defaults_charge[j], 0.01, key=f"cpt_charge_{j}")
            for j in range(4)
        ]
        cpt_overrides["Charge"] = charge_vals
        st.markdown("**SealIntegrity CPT** — P(Seal=Adequate | ClosureGeometry)")
        s1, s2 = st.columns(2)
        sv = DEFAULT_CPTS["SealIntegrity"]
        seal_vals = [
            s1.number_input("Closure=Adequate", 0.0, 1.0, sv[0], 0.01, key="cpt_seal_0"),
            s2.number_input("Closure=Inadequate", 0.0, 1.0, sv[1], 0.01, key="cpt_seal_1"),
        ]
        cpt_overrides["SealIntegrity"] = seal_vals
        st.markdown("**ReservoirQuality CPT** — P(Quality=Adequate | ReservoirPresence)")
        r1, r2 = st.columns(2)
        rv = DEFAULT_CPTS["ReservoirQuality"]
        res_vals = [
            r1.number_input("Presence=Adequate", 0.0, 1.0, rv[0], 0.01, key="cpt_res_0"),
            r2.number_input("Presence=Inadequate", 0.0, 1.0, rv[1], 0.01, key="cpt_res_1"),
        ]
        cpt_overrides["ReservoirQuality"] = res_vals

    # Map each active pillar's prior to the correct BN root slot by name, not by
    # enumerate index — so custom or reordered models feed the right network node.
    _play4: list[float] = [0.5] * N_BN_ROOT_SLOTS  # neutral for any unmapped pillar
    for i, pdef in enumerate(pillars):
        slot = BN_PILLAR_SLOT.get(pdef["pillar_id"])
        if slot is not None and i < len(play_probs):
            _play4[slot] = play_probs[i]
    model, inference = build_petroleum_bn(
        p_source=_play4[0],
        p_closure=_play4[1],
        p_reservoir=_play4[2],
        p_retention=_play4[3],
        cpt_overrides=cpt_overrides,
    )
    pos = query_pos(inference) if inference else 0.0
    total_pos = play_chance * cond_chance
    st.session_state["comparison_bn_pos"] = pos

    with st.container(border=True):
        st.caption("Detailed Sub-element Risk Table")
        from components.detail_risk_table import render_detail_risk_table
        render_detail_risk_table("bayesian", play, conditional, {}, uw, tab_key="bn")

    with st.container(border=True):
        st.caption("Combination hierarchy")
        render_bn_hierarchy(play, conditional)

    st.divider()
    st.subheader("Risk Overview")
    pillars_data = [
        {
            "name": pdef["display_name"],
            "play_pos": play_probs[i] if i < len(play_probs) else 1.0,
            "cond_pos": cond_probs[i] if i < len(cond_probs) else 1.0,
        }
        for i, pdef in enumerate(pillars)
    ]
    render_overview_table(
        "bayesian",
        {
            "pillars": pillars_data,
            "total_pos": total_pos,
            "play_pos_pct": play_chance * 100,
            "cond_pos_pct": cond_chance * 100,
            "p_discovery": pos,
            "prospect_title": st.session_state.get("meta_title", "Prospect"),
            "meta_basin": st.session_state.get("meta_basin", ""),
            "meta_analyst": st.session_state.get("meta_analyst", ""),
            "meta_date": st.session_state.get("meta_date", ""),
        },
    )
    st.metric("P(Discovery) — structural sensitivity", f"{pos * 100:.1f}%",
              help="Belief propagation over BN. Root priors from ESL Policy POS.")

    pillar_pg = {
        pdef["display_name"]: (play_probs[i] if i < len(play_probs) else 1.0)
                             * (cond_probs[i] if i < len(cond_probs) else 1.0)
        for i, pdef in enumerate(pillars)
    }
    from components.risk_summary import render_uncertainty_index_and_top5
    render_uncertainty_index_and_top5(
        pillar_pg, conditional, total_pos,
        prospect_title=st.session_state.get("meta_title", "Prospect"),
        method_label="P(Discovery) — BN",
        include_pg_ui_plot=True,
        uw=uw,
    )

    st.divider()
    with st.container(border=True):
        st.caption("Assessment Sign-off & Audit Trail")
        from components.audit import render_audit_panel
        render_audit_panel(
            pos=total_pos,
            method="Bayesian",
            prospect_title=st.session_state.get("meta_title", "Prospect"),
        )

    if inference is not None:
        st.divider()
        st.subheader("What-If Evidence Observation")
        st.markdown(
            "**What this does:** Fix any risk element to *Adequate* or *Inadequate* to simulate "
            "receiving new confirming or disconfirming information. The POS updates instantly."
        )
        base_pos = st.session_state.get("comparison_bn_pos", 0.0)
        with st.container(border=True):
            st.caption("Root-node observations")
            obs_cols = st.columns(4)
            obs_map = {}
            for i, (node, display) in enumerate([
                ("SourceMaturity", "Source Maturity"),
                ("ClosureGeometry", "Closure Geometry"),
                ("ReservoirPresence", "Reservoir Presence"),
                ("Retention", "Retention"),
            ]):
                with obs_cols[i]:
                    sel = st.selectbox(display, ["(unobserved)", "Adequate", "Inadequate"], key=f"bn_obs_{node}")
                    if sel != "(unobserved)":
                        obs_map[node] = sel
            if obs_map:
                pos_obs = query_pos(inference, obs_map)
                delta = pos_obs - base_pos
                st.metric("POS with observation", f"{pos_obs * 100:.1f}%", delta=f"{delta * 100:+.1f}% vs base")
