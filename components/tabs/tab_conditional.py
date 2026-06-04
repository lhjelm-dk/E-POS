"""Conditional tab render function."""
from __future__ import annotations

import streamlit as st

from components.render_helpers import render_summary
from components.element_detail_cam import (
    render_element_cam_panel,
    render_compact_element_row,
)
from logic.esl_pipeline import (
    DEFAULT_ESL_MODE,
    ESL_MODE_OPTIONS,
    group_by_label,
    combine_with_mode,
)
from logic.session_keys import SK


def _render_conditional_tab(ctx) -> None:
    """Render the Conditional tab.  Called by _render_tabs."""

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
    get_mode = ctx.get_mode
    get_dependency = ctx.get_dependency
    _active_model_ref = ctx.active_model
    _pillar_colors = ctx.pillar_colors
    _pillar_display = ctx.pillar_display
    ESL_OPTIONS = MODE_OPTIONS = ctx.esl_options

    st.caption(
        "Assess conditional risk elements. "
        "Click **Assess** on any row to open the full CAM detail panel."
    )

    # Active CAM panel — conditional scope
    _active_kp = st.session_state.get("active_cam_key_prefix")
    _active_scope = st.session_state.get("active_cam_scope", "cond")
    if _active_kp and _active_scope == "cond":
        _active_cat_c = st.session_state.get("active_cam_category", "Charge")
        _active_idx_c = st.session_state.get("active_cam_idx")
        _active_el_c = None
        if _active_idx_c is not None and _active_cat_c in conditional:
            _elems_c = conditional[_active_cat_c]
            if 0 <= int(_active_idx_c) < len(_elems_c):
                _active_el_c = _elems_c[int(_active_idx_c)]
        if _active_el_c is not None:
            with st.container(border=True):
                render_element_cam_panel(
                    _active_el_c, _active_kp, uncertainty_weight, _active_cat_c, "cond",
                )
            st.divider()

    from logic.esl_pipeline import (
        CLASSIC_POS_OPERATOR_OPTIONS as _CLASSIC_OP_OPTS,
        ESL_TO_CLASSIC_RECOMMENDATION as _ESL2CLASSIC,
        DEFAULT_CLASSIC_POS_MODE as _DEF_CLASSIC_MODE,
    )
    with st.expander("Operator Settings — how sub-elements are combined", expanded=False):
        _cond_cats = list(conditional.keys())
        _all_op_opts = list(ESL_MODE_OPTIONS) + ["Product (Π)", "Mean"]
        _classic_op_opts = list(_CLASSIC_OP_OPTS)

        op_c = st.columns(max(len(_cond_cats), 1))
        for _i, _cat in enumerate(_cond_cats):
            _display = _pillar_display.get(_cat, _cat)
            with op_c[_i]:
                st.markdown(
                    f'<div style="background:{_pillar_colors.get(_cat,"#e5e7eb")};'
                    f'padding:6px 8px;border-radius:4px;font-weight:700;">{_display}</div>',
                    unsafe_allow_html=True,
                )
                _mk = SK.esl_mode(_cat)
                if _mk not in st.session_state:
                    st.session_state[_mk] = DEFAULT_ESL_MODE
                _cur_esl_op = st.session_state[_mk]
                _idx_esl = _all_op_opts.index(_cur_esl_op) if _cur_esl_op in _all_op_opts else 0
                st.caption("**ESL operator** (combines evidence masses)")
                st.selectbox(
                    "ESL operator", options=_all_op_opts, index=_idx_esl,
                    key=_mk, label_visibility="collapsed",
                    help=(
                        "ESL-ALL (min/min): all sub-elements required — weakest evidence wins.\n"
                        "ESL-ANY (max/max): any sub-element sufficient — strongest evidence wins.\n"
                        "ESL-IPT: sub-elements partially correlated — set Dependency slider "
                        "(0 = independent ≈ Product, 1 = fully correlated ≈ ALL).\n"
                        "Product (Π): independent multiplicative combination on mass pairs.\n"
                        "Mean: arithmetic average of masses."
                    ),
                )
                _cmk = SK.classic_mode(_cat)
                _esl_now = st.session_state.get(_mk, DEFAULT_ESL_MODE)
                _recommended_classic = _ESL2CLASSIC.get(_esl_now, _DEF_CLASSIC_MODE)
                if _cmk not in st.session_state:
                    st.session_state[_cmk] = _recommended_classic
                _cur_classic_op = st.session_state[_cmk]
                _idx_cl = _classic_op_opts.index(_cur_classic_op) if _cur_classic_op in _classic_op_opts else 0
                st.caption("**Classic POS operator** (combines Policy POS probabilities)")
                st.selectbox(
                    "Classic POS op.", options=_classic_op_opts, index=_idx_cl,
                    key=_cmk, label_visibility="collapsed",
                )
                if _cur_classic_op != _recommended_classic:
                    st.caption(
                        f"ℹ️ ESL uses *{_esl_now}* → recommended Classic POS: "
                        f"**{_recommended_classic}**"
                    )

    render_summary(
        "P(Cond) — combined across all conditional pillars (Product)", conditional_for, conditional_against,
        operator="Product (Π)", uncertainty_weight=uncertainty_weight,
    )
    st.divider()

    for _category, _elements in conditional.items():
        _display_cat = _pillar_display.get(_category, _category)
        _cat_color = _pillar_colors.get(_category, "#e5e7eb")
        with st.container(border=True):
            _op_label = get_mode(SK.esl_mode(_category))
            _dep_cat = None
            if _op_label.startswith("ESL-IPT"):
                st.caption("Dependency: 0 = independent evidence, 1 = fully overlapping evidence.")
                _dep_cat = st.number_input(
                    f"Dependency ({_display_cat})", 0.0, 1.0,
                    get_dependency(SK.esl_dependency(_category)), 0.01,
                    key=SK.esl_dependency(_category),
                )
            _cr = conditional_results.get(_category, {"for": 0.5, "against": 0.1})
            render_summary(
                f"P({_display_cat}, Cond) — {_op_label}",
                _cr["for"], _cr["against"],
                operator=_op_label, dependency=_dep_cat,
                uncertainty_weight=uncertainty_weight,
                category=_display_cat, scope="cond",
            )

            _elem_to_flat = {id(_e): _i for _i, _e in enumerate(_elements)}
            _grouped = group_by_label(_elements)

            _h1, _h2, _h3, _h4, _h5, _h6, _h7 = st.columns([4, 3, 1, 1, 1, 1, 1])
            with _h1: st.caption("**Element — Success criterion**")
            with _h2: st.caption(
                "**Italian Flag**",
                help="Green = Support For · White = Unknown / uncommitted · Red = Support Against · Yellow = overcommitted (S_for + S_against > 1)",
            )
            with _h3: st.caption("**Policy P**", help="Per-element point estimate = S_for + w × White")
            with _h4: st.caption("**ECI**", help="Evidence Clarity Index = |S_for − S_against|")
            with _h5: st.caption("**Commit**", help="Commitment = S_for + S_against (total evidence volume)")
            with _h6: st.caption("**w** (stance)", help="Per-element stance override (defaults to global w)")
            with _h7: st.caption("**Assess**")

            for _group_label, _group_elements in _grouped.items():
                if len(_group_elements) == 1:
                    _element = _group_elements[0]
                    _flat_idx = _elem_to_flat.get(id(_element), 0)
                    render_compact_element_row(
                        _element, f"esl_cond_{_category}_{_flat_idx}",
                        uncertainty_weight, _category, "cond", _cat_color,
                    )
                    continue

                _mode_key = SK.esl_group_mode(_category, _group_label)
                if _category == "Retention" and _group_label in (
                    "Preservation from post-charge events",
                    "Preservation from degradation",
                ):
                    if _mode_key not in st.session_state:
                        st.session_state[_mode_key] = "ESL-ANY (max/max)"

                st.markdown(
                    f"<div style='font-size:0.8rem;font-weight:700;color:#374151;"
                    f"border-left:3px solid {_cat_color};padding:3px 8px;"
                    f"background:#f9fafb;border-radius:0 4px 4px 0;margin:4px 0;'>"
                    f"{_group_label}</div>",
                    unsafe_allow_html=True,
                )
                _op_col, _cl_col, _ = st.columns([2, 2, 2])
                with _op_col:
                    st.caption("ESL op.")
                    st.selectbox(
                        f"{_group_label} ESL operator", MODE_OPTIONS,
                        index=MODE_OPTIONS.index(get_mode(_mode_key)),
                        key=_mode_key, label_visibility="collapsed",
                        help=(
                            "ESL-ALL: all required (min/min, weakest link).\n"
                            "ESL-ANY: any sufficient (max/max).\n"
                            "ESL-IPT: partially correlated — Dependency 0=independent, 1=correlated.\n"
                            "Product (Π): independent multiplicative."
                        ),
                    )
                with _cl_col:
                    _grp_classic_key = SK.classic_group_mode(_category, _group_label)
                    _esl_grp_now = get_mode(_mode_key)
                    _rec_grp = _ESL2CLASSIC.get(_esl_grp_now, _DEF_CLASSIC_MODE)
                    if _grp_classic_key not in st.session_state:
                        st.session_state[_grp_classic_key] = _rec_grp
                    _cur_grp_cl = st.session_state[_grp_classic_key]
                    _classic_op_opts_grp = list(_CLASSIC_OP_OPTS)
                    _idx_grp_cl = _classic_op_opts_grp.index(_cur_grp_cl) if _cur_grp_cl in _classic_op_opts_grp else 0
                    st.caption("Classic POS op.")
                    st.selectbox(
                        f"{_group_label} Classic POS op.", _classic_op_opts_grp,
                        index=_idx_grp_cl,
                        key=_grp_classic_key, label_visibility="collapsed",
                    )
                    if _cur_grp_cl != _rec_grp:
                        st.caption(f"ℹ️ Rec: **{_rec_grp}**")
                _dep_group = None
                if get_mode(_mode_key).startswith("ESL-IPT"):
                    st.caption("Dependency: 0 = independent evidence, 1 = fully overlapping.")
                    _dep_group = st.number_input(
                        f"Dependency ({_group_label})", 0.0, 1.0,
                        get_dependency(SK.esl_group_dependency(_category, _group_label)), 0.01,
                        key=SK.esl_group_dependency(_category, _group_label),
                    )
                _gf, _ga = combine_with_mode(
                    _group_elements,
                    get_mode(_mode_key),
                    get_dependency(SK.esl_group_dependency(_category, _group_label)),
                )
                render_summary(
                    f"{_group_label} summary", _gf, _ga, level=1,
                    operator=get_mode(_mode_key), dependency=_dep_group,
                    uncertainty_weight=uncertainty_weight,
                    category=_display_cat, scope="cond",
                )
                for _element in _group_elements:
                    _flat_idx = _elem_to_flat.get(id(_element), 0)
                    render_compact_element_row(
                        _element, f"esl_cond_{_category}_{_flat_idx}",
                        uncertainty_weight, _category, "cond", _cat_color,
                    )
                st.divider()
