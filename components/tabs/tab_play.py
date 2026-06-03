"""Play tab render function."""
from __future__ import annotations

import streamlit as st

from components.render_helpers import render_summary
from components.element_detail_cam import (
    render_element_cam_panel,
    render_compact_element_row,
)


def _render_play_tab(ctx) -> None:
    """Render the Play tab.  Called by _render_tabs."""

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

    st.caption(
        "Assess the four play-level pillars. "
        "Click **▶ Assess** on any row to open the full CAM evidence panel."
    )

    # Active CAM panel — play scope
    _active_kp = st.session_state.get("active_cam_key_prefix")
    _active_scope = st.session_state.get("active_cam_scope", "cond")
    if _active_kp and _active_scope == "play":
        _active_cat_p = st.session_state.get("active_cam_category", "Charge")
        _active_el_p = play.get(_active_cat_p)
        if _active_el_p is not None:
            with st.container(border=True):
                render_element_cam_panel(
                    _active_el_p, _active_kp, uncertainty_weight, _active_cat_p, "play",
                )
            st.divider()

    render_summary(
        "P(Play) — combined across all play pillars (Product)", play_for, play_against,
        operator="Product (Π)", uncertainty_weight=uncertainty_weight,
    )
    st.divider()

    # Compact grid — one row per play pillar
    with st.container(border=True):
        _ph1, _ph2, _ph3, _ph4, _ph5, _ph6, _ph7 = st.columns([4, 3, 1, 1, 1, 1, 1])
        with _ph1: st.caption("**Pillar — Success criterion**")
        with _ph2: st.caption(
            "**Italian Flag**",
            help="Green = Support For · White = Unknown / uncommitted · Red = Support Against · Yellow = overcommitted (S_for + S_against > 1)",
        )
        with _ph3: st.caption("**Policy P**", help="Per-element point estimate = S_for + w × White")
        with _ph4: st.caption("**ECI**", help="Evidence Clarity Index = |S_for − S_against|")
        with _ph5: st.caption("**Commit**", help="Commitment = S_for + S_against (total evidence volume)")
        with _ph6: st.caption("**w** (stance)", help="Per-element stance override (defaults to global w)")
        with _ph7: st.caption("**Assess**")

        _play_iter = (
            [(p.pillar_id, f"esl_play_{p.pillar_id}") for p in _active_model_ref.pillars]
            if _active_model_ref
            else [("Charge", "esl_play_Charge"), ("Closure", "esl_play_Closure"),
                  ("Reservoir", "esl_play_Reservoir"), ("Retention", "esl_play_Retention")]
        )
        for _p_cat, _p_kp in _play_iter:
            _p_dc = _pillar_display.get(_p_cat, _p_cat)
            _p_color = _pillar_colors.get(_p_cat, "#e5e7eb")
            _p_el = play.get(_p_cat)
            if _p_el is None:
                continue
            _p_el_display = {**_p_el, "label": _p_dc}
            render_compact_element_row(
                _p_el_display, _p_kp, uncertainty_weight, _p_cat, "play", _p_color,
            )
            with st.expander(f"📋 Guidance — {_p_dc}", expanded=False):
                st.info(_p_el.get("considerations", "No guidance available."))
