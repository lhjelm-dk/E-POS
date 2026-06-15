"""Prospect-hub data functions extracted from app.py.

These functions compute and format data for the Dashboard tab's
export, comparison, and risk-data panels.  They have no circular
dependency: they import from logic/ and components/ sub-modules only.
"""
from __future__ import annotations

import csv
import io

import numpy as np
import streamlit as st

from components.colors import COMPANY_DEFAULT_WEIGHT
from components.render_helpers import policy_pos, calculate_flag
from logic.esl_logic import apply_and_logic
from logic.esl_pipeline import (
    DEFAULT_CLASSIC_POS_MODE,
    ESL_MODE_OPTIONS,
    combine_classic_pos,
    combine_with_mode,
    compute_esl_rollup,
    group_by_label,
    make_session_mode_dep_getters,
    make_session_classic_mode_getter,
)
from logic.session_keys import SK


# ---------------------------------------------------------------------------
# Hub computation helpers
# ---------------------------------------------------------------------------

def _compute_esl_for_hub(models: dict, build_logic_table_fn=None) -> "tuple[list[dict], dict, dict, dict] | None":
    """Run ESL computation and build logic table. Returns (logic_rows, node_index, mode_index, dep_index) or None."""
    play = models.get("play", {})
    conditional = models.get("conditional", {})
    if not play or not conditional:
        return None
    combine_mode = "Evidence Support Logic"
    from logic.pos_policy import resolve_stance
    uncertainty_weight = resolve_stance()
    get_mode, get_dep = make_session_mode_dep_getters(st.session_state)
    get_classic_mode = make_session_classic_mode_getter(st.session_state)
    r = compute_esl_rollup(play, conditional, get_mode, get_dep)
    st.session_state["comparison_esl_pos"] = policy_pos(r.total_for, r.total_against, uncertainty_weight)
    st.session_state["comparison_esl_total_for"] = r.total_for
    st.session_state["comparison_esl_total_against"] = r.total_against

    prospect_title = st.session_state.get("meta_title", "Prospect")
    meta_analyst = st.session_state.get("meta_analyst", "")
    meta_basin = st.session_state.get("meta_basin", "")
    meta_date = st.session_state.get("meta_date", "")
    meta_version = st.session_state.get("meta_version", "")

    _blt = build_logic_table_fn if build_logic_table_fn is not None else build_logic_table
    logic_rows, node_index, mode_index, dep_index = _blt(
        play, conditional, r.conditional_results,
        r.play_for, r.play_against, r.conditional_for, r.conditional_against, r.total_for, r.total_against,
        r.pillar_for.get("Charge", 0.5),     r.pillar_against.get("Charge", 0.1),
        r.pillar_for.get("Closure", 0.5),    r.pillar_against.get("Closure", 0.1),
        r.pillar_for.get("Reservoir", 0.5),  r.pillar_against.get("Reservoir", 0.1),
        r.pillar_for.get("Retention", 0.5),  r.pillar_against.get("Retention", 0.1),
        prospect_title, meta_analyst, meta_basin, meta_date, meta_version, uncertainty_weight,
        get_mode_fn=get_mode, get_dependency_fn=get_dep, get_classic_mode_fn=get_classic_mode,
        combine_mode_val=combine_mode, combine_with_mode_fn=combine_with_mode,
    )
    return logic_rows, node_index, mode_index, dep_index


def _compute_classic_pos_with_range_for_hub(models: dict) -> "tuple[float, float, float] | None":
    """Return (point, bel, pl) for Classic POS where bel=∏S_for and pl=∏(1−S_against).

    The three values form the ESL-derived confidence range for Classic POS:
      bel  = product of per-pillar Bel (all white votes against  — pessimistic)
      point = product of per-pillar Policy POS at current stance w
      pl   = product of per-pillar Pl  (all white votes for      — optimistic)
    """
    from logic.pos_policy import resolve_stance, get_active_pillars
    from logic.pos_logic import classic_pos_product
    play = models.get("play", {})
    conditional = models.get("conditional", {})
    if not play or not conditional:
        return None
    uw = resolve_stance()
    get_classic_mode = make_session_classic_mode_getter(st.session_state)
    pillars = get_active_pillars()

    play_pts: list[float] = []
    play_bels: list[float] = []
    play_pls: list[float] = []
    for pdef in pillars:
        pid = pdef["pillar_id"]
        el = play.get(pid, {})
        if isinstance(el, dict) and "support_for" in el:
            elem_w = st.session_state.get(f"w_esl_play_{pid}", uw)
            sf, sa = el["support_for"], el["support_against"]
            play_pts.append(policy_pos(sf, sa, elem_w))
            play_bels.append(sf)
            play_pls.append(1.0 - sa)
        else:
            play_pts.append(1.0)
            play_bels.append(1.0)
            play_pls.append(1.0)

    cond_pts: list[float] = []
    cond_bels: list[float] = []
    cond_pls: list[float] = []
    for pdef in pillars:
        pid = pdef["pillar_id"]
        elems = conditional.get(pid, [])
        if not elems:
            cond_pts.append(1.0)
            cond_bels.append(1.0)
            cond_pls.append(1.0)
            continue
        elem_pts_map = {
            id(e): policy_pos(e["support_for"], e["support_against"],
                              st.session_state.get(f"w_esl_cond_{pid}_{j}", uw))
            for j, e in enumerate(elems)
        }
        elem_bels_map = {id(e): e["support_for"] for e in elems}
        elem_pls_map  = {id(e): 1.0 - e["support_against"] for e in elems}
        grouped = group_by_label(elems)
        grp_pts:  list[float] = []
        grp_bels: list[float] = []
        grp_pls:  list[float] = []
        for grp_label, grp_elems in grouped.items():
            grp_mode = get_classic_mode(SK.classic_group_mode(pid, grp_label))
            grp_pts.append( combine_classic_pos([elem_pts_map[id(e)]  for e in grp_elems], grp_mode))
            grp_bels.append(combine_classic_pos([elem_bels_map[id(e)] for e in grp_elems], grp_mode))
            grp_pls.append( combine_classic_pos([elem_pls_map[id(e)]  for e in grp_elems], grp_mode))
        pil_mode = get_classic_mode(SK.classic_mode(pid))
        cond_pts.append( combine_classic_pos(grp_pts,  pil_mode))
        cond_bels.append(combine_classic_pos(grp_bels, pil_mode))
        cond_pls.append( combine_classic_pos(grp_pls,  pil_mode))

    point = classic_pos_product(play_pts)  * classic_pos_product(cond_pts)
    bel   = classic_pos_product(play_bels) * classic_pos_product(cond_bels)
    pl    = classic_pos_product(play_pls)  * classic_pos_product(cond_pls)
    return point, bel, pl


def _compute_classic_pos_for_hub(models: dict) -> "float | None":
    """Compute Classic POS point estimate from current ESL masses."""
    result = _compute_classic_pos_with_range_for_hub(models)
    return result[0] if result is not None else None


def _compute_p_g_classic_trajectory(models: dict, n_steps: int = 21) -> "dict | None":
    """Sweep stance w from 0 to 1 and return per-pillar + total P(G, Classic) at each w.

    Returns a dict::
        {
            "ws":      [w_0, w_1, ..., w_n]                  (n_steps long)
            "total":   [P(G, Classic) at each w]
            "pillars": {pillar_id: [P(pillar) at each w]}
            "pillar_display": {pillar_id: display_name}
            "pillar_color":   {pillar_id: hex_colour}
        }

    Per-pillar values use the Classic POS combination (Classic operator per group,
    then Classic operator at pillar level) so the trajectory matches what the
    Classic POS detail page reports.
    """
    import numpy as np
    from logic.pos_policy import get_active_pillars
    from logic.pos_logic import classic_pos_product
    play = models.get("play", {})
    conditional = models.get("conditional", {})
    if not play or not conditional:
        return None

    get_classic_mode = make_session_classic_mode_getter(st.session_state)
    pillars = get_active_pillars()
    pillar_ids = [p["pillar_id"] for p in pillars]

    ws = np.linspace(0.0, 1.0, n_steps)
    total_traj: list[float] = []
    per_pillar: dict[str, list[float]] = {pid: [] for pid in pillar_ids}

    for _w_val in ws:
        play_probs: list[float] = []
        cond_probs: list[float] = []
        for pdef in pillars:
            pid = pdef["pillar_id"]

            # Play at this w
            el = play.get(pid, {})
            if isinstance(el, dict) and "support_for" in el:
                play_p = el["support_for"] + _w_val * max(0.0, 1.0 - el["support_for"] - el["support_against"])
            else:
                play_p = 1.0
            play_probs.append(play_p)

            # Cond at this w (Classic combination, same logic as _compute_classic_pos_with_range_for_hub)
            elems = conditional.get(pid, [])
            if not elems:
                cond_p = 1.0
            else:
                elem_pts = {
                    id(e): e["support_for"] + _w_val * max(0.0, 1.0 - e["support_for"] - e["support_against"])
                    for e in elems
                }
                grouped = group_by_label(elems)
                grp_pts: list[float] = []
                for grp_label, grp_elems in grouped.items():
                    grp_mode = get_classic_mode(SK.classic_group_mode(pid, grp_label))
                    grp_pts.append(combine_classic_pos([elem_pts[id(e)] for e in grp_elems], grp_mode))
                pil_mode = get_classic_mode(SK.classic_mode(pid))
                cond_p = combine_classic_pos(grp_pts, pil_mode)
            cond_probs.append(cond_p)

            per_pillar[pid].append(play_p * cond_p)

        total_traj.append(classic_pos_product(play_probs) * classic_pos_product(cond_probs))

    return {
        "ws":             ws.tolist(),
        "total":          total_traj,
        "pillars":        per_pillar,
        "pillar_display": {p["pillar_id"]: p["display_name"] for p in pillars},
        "pillar_color":   {p["pillar_id"]: p.get("color", "#6b7280") for p in pillars},
    }


def _get_esl_overview_data(models: dict) -> "dict | None":
    """Build ESL overview data for render_overview_table."""
    play = models.get("play", {})
    conditional = models.get("conditional", {})
    if not play or not conditional:
        return None
    from logic.pos_policy import resolve_stance
    uncertainty_weight = resolve_stance()
    get_mode, get_dep = make_session_mode_dep_getters(st.session_state)
    r = compute_esl_rollup(play, conditional, get_mode, get_dep)

    method_label = "Evidence Support Logic"
    prospect_title = st.session_state.get("meta_title", "Prospect")
    meta_basin = st.session_state.get("meta_basin", "")
    meta_analyst = st.session_state.get("meta_analyst", "")
    meta_date = st.session_state.get("meta_date", "")

    cr = r.conditional_results
    from logic.pos_policy import get_active_pillars as _gap_overview
    _pillars_ov = _gap_overview()
    slide_rows = []
    for _pdef_ov in _pillars_ov:
        _pid_ov = _pdef_ov["pillar_id"]
        _dn_ov = _pdef_ov["display_name"]
        pf = r.pillar_for.get(_pid_ov, 0.5)
        pa = r.pillar_against.get(_pid_ov, 0.1)
        _cond_ov = cr.get(_pid_ov, {"for": 0.5, "against": 0.1})
        cf, ca = _cond_ov["for"], _cond_ov["against"]
        slide_rows.append({
            "name": _dn_ov,
            "play_pos": policy_pos(pf, pa, uncertainty_weight),
            "play_support_for": pf,
            "play_support_against": pa,
            "cond_pos": policy_pos(cf, ca, uncertainty_weight),
            "cond_support_for": cf,
            "cond_support_against": ca,
        })
    from components.render_helpers import interval_text as _interval_text
    return {
        "pillars": slide_rows,
        "play_for": r.play_for,
        "play_against": r.play_against,
        "cond_for": r.conditional_for,
        "cond_against": r.conditional_against,
        "total_for": r.total_for,
        "total_against": r.total_against,
        "play_pos_pct": policy_pos(r.play_for, r.play_against, uncertainty_weight) * 100,
        "cond_pos_pct": policy_pos(r.conditional_for, r.conditional_against, uncertainty_weight) * 100,
        "total_pos_pct": policy_pos(r.total_for, r.total_against, uncertainty_weight) * 100,
        "interval_text": _interval_text(r.total_for, r.total_against),
        "method_label": method_label,
        "prospect_title": prospect_title,
        "meta_basin": meta_basin,
        "meta_analyst": meta_analyst,
        "meta_date": meta_date,
    }


# ---------------------------------------------------------------------------
# Logic table builders
# ---------------------------------------------------------------------------

def build_logic_table(
    play: dict,
    conditional: dict,
    conditional_results: dict,
    play_for: float,
    play_against: float,
    conditional_for: float,
    conditional_against: float,
    total_for: float,
    total_against: float,
    charge_for: float,
    charge_against: float,
    closure_for: float,
    closure_against: float,
    reservoir_for: float,
    reservoir_against: float,
    retention_for: float,
    retention_against: float,
    meta_title: str,
    meta_analyst: str,
    meta_basin: str,
    meta_date: str,
    meta_version: str = "",
    uncertainty_weight: float = 0.5,
    get_mode_fn=None,
    get_dependency_fn=None,
    get_classic_mode_fn=None,
    combine_mode_val: str = "Evidence Support Logic",
    combine_with_mode_fn=None,
) -> "tuple[list[dict], dict, dict, dict]":
    from logic.esl_logic import apply_and_logic as _apply_and
    get_mode = get_mode_fn if get_mode_fn is not None else (lambda k: "ESL-ALL (min/min)")
    get_dependency = get_dependency_fn if get_dependency_fn is not None else (lambda k: 0.0)
    get_classic_mode = get_classic_mode_fn if get_classic_mode_fn is not None else (lambda k: DEFAULT_CLASSIC_POS_MODE)
    combine_mode = combine_mode_val
    _combine_wm = combine_with_mode_fn if combine_with_mode_fn is not None else (lambda nodes, mode, dep=0.0: _apply_and(nodes))

    rows: list[dict] = []
    node_index: dict[str, dict] = {}
    mode_index: dict[str, str] = {}
    dep_index: dict[str, str] = {}

    def add_row(
        scope: str,
        node_id: str,
        parent_id: str,
        operator: str,
        dependency: "float | None",
        s_for: float,
        s_against: float,
        element: "dict | None" = None,
        suff_for: "float | None" = None,
        suff_against: "float | None" = None,
        mode_key: "str | None" = None,
        dep_key: "str | None" = None,
        classic_pos: "float | None" = None,
        meta_value: "str | None" = None,
    ) -> None:
        est_pos = policy_pos(s_for, s_against, uncertainty_weight)
        methodology_bias = round(est_pos - classic_pos, 4) if classic_pos is not None else ""
        rows.append(
            {
                "scope": scope,
                "node_id": node_id,
                "parent_id": parent_id,
                "operator": operator,
                "dependency": "" if dependency is None else round(dependency, 3),
                "support_for": round(s_for, 4),
                "support_against": round(s_against, 4),
                "uncertainty": round(max(0.0, 1 - s_for - s_against), 4),
                "p_g_esl": round(est_pos, 4),
                "p_g_classic": "" if classic_pos is None else round(classic_pos, 4),
                "methodology_bias": methodology_bias,
                "suff_for": "" if suff_for is None else round(suff_for, 4),
                "suff_against": "" if suff_against is None else round(suff_against, 4),
                "meta_value": "" if meta_value is None else meta_value,
            }
        )
        if element is not None:
            node_index[node_id] = element
        if mode_key:
            mode_index[node_id] = mode_key
        if dep_key:
            dep_index[node_id] = dep_key

    # Metadata rows
    add_row("Meta", "Meta/Title", "", "", None, 0.0, 0.0, meta_value=meta_title)
    add_row("Meta", "Meta/Analyst", "Meta/Title", "", None, 0.0, 0.0, meta_value=meta_analyst)
    add_row("Meta", "Meta/Basin", "Meta/Title", "", None, 0.0, 0.0, meta_value=meta_basin)
    add_row("Meta", "Meta/Date", "Meta/Title", "", None, 0.0, 0.0, meta_value=meta_date)
    add_row("Meta", "Meta/Version", "Meta/Title", "", None, 0.0, 0.0, meta_value=meta_version)

    # Classic POS aggregation
    cond_classic_map: dict[str, float] = {}
    for category, elements in conditional.items():
        grouped = group_by_label(elements)
        group_classic = []
        for group_label, group_elements in grouped.items():
            classic_gmode = get_classic_mode(SK.classic_group_mode(category, group_label))
            probs = [policy_pos(e["support_for"], e["support_against"], uncertainty_weight) for e in group_elements]
            group_classic.append(combine_classic_pos(probs, classic_gmode))
        classic_pillar_mode = get_classic_mode(SK.classic_mode(category))
        cond_classic_map[category] = combine_classic_pos(group_classic, classic_pillar_mode) if group_classic else 0.0

    play_classic = {
        cat: policy_pos(float(pdata.get("support_for", 0.5)), float(pdata.get("support_against", 0.1)), uncertainty_weight)
        for cat, pdata in play.items()
    }

    total_classic = 1.0
    for cat in play_classic:
        total_classic *= play_classic[cat] * cond_classic_map.get(cat, 1.0)

    total_op = "Product (Π)"
    play_op = "Product (Π)"
    cond_op = "Product (Π)"
    add_row(
        "Total", "Total/Pg", "", total_op, get_dependency("dep_total"),
        total_for, total_against,
        classic_pos=total_classic,
        mode_key=None, dep_key="dep_total",
    )
    add_row(
        "Total", "Total/Play", "Total/Pg", play_op, get_dependency("dep_total"),
        play_for, play_against,
        classic_pos=np.prod([play_classic[c] for c in play_classic]),
        mode_key=None, dep_key="dep_total",
    )
    add_row(
        "Total", "Total/Conditional", "Total/Pg", cond_op, get_dependency("dep_total"),
        conditional_for, conditional_against,
        classic_pos=np.prod([cond_classic_map[c] for c in cond_classic_map]),
        mode_key=None, dep_key="dep_total",
    )

    for cat, pdata in play.items():
        s_for = float(pdata.get("support_for", 0.5))
        s_against = float(pdata.get("support_against", 0.1))
        add_row(
            "Play", f"Play/{cat}", "Total/Play", "Direct", None, s_for, s_against,
            element=pdata,
            classic_pos=play_classic.get(cat, policy_pos(s_for, s_against, uncertainty_weight)),
        )

    for category, elements in conditional.items():
        cat_mode = get_mode(SK.esl_mode(category))
        dep_key = SK.esl_dependency(category)
        dep_val = get_dependency(dep_key) if cat_mode.startswith("ESL-IPT") else None
        cat_for = conditional_results[category]["for"]
        cat_against = conditional_results[category]["against"]
        grouped = group_by_label(elements)
        cat_classic = cond_classic_map.get(category, 0.0)
        add_row(
            "Conditional", f"Conditional/{category}", "Total/Conditional",
            cat_mode, dep_val, cat_for, cat_against,
            classic_pos=cat_classic,
            mode_key=SK.esl_mode(category),
            dep_key=dep_key if cat_mode.startswith("ESL-IPT") else None,
        )
        for group_label, group_elements in grouped.items():
            if len(group_elements) == 1:
                element = group_elements[0]
                add_row(
                    "Conditional",
                    f"Conditional/{category}/{group_label}",
                    f"Conditional/{category}",
                    "Leaf", None,
                    element["support_for"], element["support_against"],
                    element=element,
                    classic_pos=policy_pos(element["support_for"], element["support_against"], uncertainty_weight),
                    suff_for=element.get("suff_for", 1.0),
                    suff_against=element.get("suff_against", 1.0),
                )
                continue
            group_mode = get_mode(SK.esl_group_mode(category, group_label))
            dep_group = (
                get_dependency(SK.esl_group_dependency(category, group_label))
                if group_mode.startswith("ESL-IPT")
                else None
            )
            group_for, group_against = _combine_wm(
                group_elements, group_mode, get_dependency(SK.esl_group_dependency(category, group_label))
            )
            _classic_grp_mode = get_classic_mode(SK.classic_group_mode(category, group_label))
            _grp_probs = [policy_pos(e["support_for"], e["support_against"], uncertainty_weight) for e in group_elements]
            group_classic_pos = combine_classic_pos(_grp_probs, _classic_grp_mode)
            add_row(
                "Conditional",
                f"Conditional/{category}/{group_label}",
                f"Conditional/{category}",
                group_mode, dep_group, group_for, group_against,
                classic_pos=group_classic_pos,
                mode_key=SK.esl_group_mode(category, group_label),
                dep_key=SK.esl_group_dependency(category, group_label) if group_mode.startswith("ESL-IPT") else None,
            )
            for element in group_elements:
                add_row(
                    "Conditional",
                    f"Conditional/{category}/{group_label}/{element['success_criteria']}",
                    f"Conditional/{category}/{group_label}",
                    "Leaf", None,
                    element["support_for"], element["support_against"],
                    element=element,
                    classic_pos=policy_pos(element["support_for"], element["support_against"], uncertainty_weight),
                    suff_for=element.get("suff_for", 1.0),
                    suff_against=element.get("suff_against", 1.0),
                )

    return rows, node_index, mode_index, dep_index


def build_prospect_risk_data(
    logic_rows: list[dict],
    classic_pos: "float | None",
    esl_pos: "float | None",
) -> list[dict]:
    """Build Prospect Risk Data table with result summary row."""
    summary = {
        "scope": "Result",
        "node_id": "Summary",
        "parent_id": "",
        "operator": "",
        "dependency": "",
        "support_for": "",
        "support_against": "",
        "uncertainty": "",
        "p_g_esl": round(esl_pos, 4) if esl_pos is not None else "",
        "p_g_classic": round(classic_pos, 4) if classic_pos is not None else "",
        "methodology_bias": "",
        "suff_for": "",
        "suff_against": "",
        "meta_value": "Final POS %",
    }
    return [summary] + logic_rows


def _build_full_export_csv(
    models: dict,
    logic_rows: list[dict],
    classic_pos: float,
    esl_pos: "float | None",
    meta_title: str,
    meta_analyst: str,
    meta_basin: str,
    meta_date: str,
    meta_version: str,
    timestamp: str,
) -> str:
    """Build a comprehensive CSV export covering ESL and Classic POS."""
    buf = io.StringIO()
    w = csv.writer(buf)

    w.writerow(["## E-POS — Evidence supported probability of success for oil and gas prospects."])
    w.writerow(["Prospect", meta_title])
    w.writerow(["Analyst", meta_analyst])
    w.writerow(["Basin/Play", meta_basin])
    w.writerow(["Date", meta_date])
    w.writerow(["Version", meta_version])
    w.writerow(["Export UTC", timestamp])
    w.writerow([])

    w.writerow(["## Method Summary"])
    w.writerow(["method", "p_pct", "note"])
    esl_str = f"{esl_pos*100:.2f}" if esl_pos is not None else "not computed"
    w.writerow(["P(G, ESL)", esl_str, "S_for + w × White on combined masses — primary method"])
    _rose_override = st.session_state.get("rose_classic_pos_entered", False)
    _classic_source = "ROSE override (independently entered)" if _rose_override else "ESL-derived (∏ pillar Policy P combined with Classic operator)"
    w.writerow(["P(G, Classic)", f"{classic_pos*100:.2f}", _classic_source])
    w.writerow([])

    w.writerow(["## Classic POS Source"])
    w.writerow(["field", "value"])
    w.writerow(["source_mode", "ROSE override" if _rose_override else "ESL-derived"])
    if _rose_override:
        _rose_just = st.session_state.get("rose_justification", "")
        w.writerow(["rose_justification", _rose_just])
        for _k, _v in st.session_state.items():
            if isinstance(_k, str) and _k.startswith("classic_") and not _k.startswith("classic_mode") and isinstance(_v, float) and _v > 0.0:
                w.writerow([f"rose_{_k}", f"{_v:.2f}"])
    w.writerow([])

    # ── DFI Bayesian Update (only written when toggled ON) ─────────────────
    _dfi_on = bool(st.session_state.get("dfi_enabled", False))
    w.writerow(["## DFI Bayesian Update"])
    w.writerow(["field", "value"])
    w.writerow(["dfi_enabled", "true" if _dfi_on else "false"])
    if _dfi_on:
        try:
            from logic.dfi_calibration import load_calibration
            from logic.dfi_bayes import compute_dfi_posterior, attribute_classic
            from logic.dfi_context import (
                get_effective_calibration       as _get_effective_calibration,
                esl_prior_pillars_from_ctx_at_w as _esl_prior_pillars_from_ctx_at_w,
                classic_prior_pillars_from_ctx  as _classic_prior_pillars_from_ctx,
                pillar_pairs_from_priorpillars  as _pillar_pairs_from_priorpillars,
                esl_rollup_prior_at_w           as _esl_rollup_prior_at_w,
            )
            class _DFICtx:
                pass
            _dfi_ctx = _DFICtx()
            _dfi_ctx.play                = models.get("play", {})
            _dfi_ctx.conditional         = models.get("conditional", {})
            _dfi_ctx.conditional_results = {
                pid: {"for": st.session_state.get(f"comparison_esl_cond_for_{pid}", 0.5),
                      "against": st.session_state.get(f"comparison_esl_cond_against_{pid}", 0.1)}
                for pid in (_dfi_ctx.conditional or {})
            }
            # Fall back: use logic.esl_pipeline to recompute cond results inline
            from logic.esl_pipeline import compute_conditional_results, make_session_mode_dep_getters
            _gm, _gd = make_session_mode_dep_getters(st.session_state)
            _cond_r = compute_conditional_results(_dfi_ctx.conditional, _gm, _gd)
            _dfi_ctx.conditional_results = _cond_r
            _dfi_ctx.uncertainty_weight  = uncertainty_weight

            _calib = _get_effective_calibration()
            from logic.dfi_inputs import read_dfi_inputs
            _inp = read_dfi_inputs(st.session_state)
            # CSV reports the renormalised fluid weights (sum = 1.0), as before.
            _fw    = _inp.fluid_weights.normalised()
            _dhi   = _inp.dhi
            _sd    = _inp.sd_mode
            _ftyp  = _inp.fluid_type
            _esl_attr = _inp.esl_attribution

            _pri_e = _esl_prior_pillars_from_ctx_at_w(_dfi_ctx, uncertainty_weight)
            _pri_c = _classic_prior_pillars_from_ctx(_dfi_ctx, uncertainty_weight)
            _esl_prior_pg = _esl_rollup_prior_at_w(_dfi_ctx, uncertainty_weight)
            _post_e = compute_dfi_posterior(_pri_e, _dhi, _calib, _fw, _sd, _ftyp,
                                            prior_pg_override=_esl_prior_pg)
            _post_c = compute_dfi_posterior(_pri_c, _dhi, _calib, _fw, _sd, _ftyp)
            _attr_c = attribute_classic(_pri_c, _post_c)

            # Input audit
            w.writerow(["dhi_index",                f"{_dhi:.0f}"])
            w.writerow(["fluid_type",               _ftyp])
            w.writerow(["sd_mode",                  _sd])
            w.writerow(["dfi_prob_water",           f"{_fw.water:.4f}"])
            w.writerow(["dfi_prob_lsg",             f"{_fw.lsg:.4f}"])
            w.writerow(["dfi_prob_other",           f"{_fw.other:.4f}"])
            w.writerow(["esl_attribution_method",   _esl_attr])
            w.writerow(["calibration_version",      _calib.version])
            w.writerow(["calibration_source",       _calib.source])
            w.writerow(["calibration_is_placeholder", "true" if _calib.is_placeholder else "false"])
            # Headline results
            w.writerow(["p_g_esl_prior",            f"{_esl_prior_pg:.6f}"])
            w.writerow(["p_g_esl_prior_init_pg_pillars", f"{_pri_e.prior_pg:.6f}"])
            w.writerow(["p_g_esl_post",             f"{_post_e.posterior_pg:.6f}"])
            w.writerow(["p_g_classic_prior",        f"{_pri_c.prior_pg:.6f}"])
            w.writerow(["p_g_classic_post",         f"{_post_c.posterior_pg:.6f}"])
            w.writerow(["r_dfi_esl",               f"{_post_e.r_dfi:.4f}"])
            w.writerow(["dhi_volume_weight_esl",    f"{_post_e.dhi_volume_weight:.4f}"])
            w.writerow(["r_dfi_classic",           f"{_post_c.r_dfi:.4f}"])
            w.writerow(["dhi_volume_weight_classic", f"{_post_c.dhi_volume_weight:.4f}"])
            w.writerow([])
            # Per-pillar Classic attribution (workbook log-split)
            w.writerow(["## DFI-modified per-pillar Pgs (Classic, reservoir-aware log-split)"])
            w.writerow(["pillar_slot", "prior", "posterior", "delta_pp"])
            for (name, _k, pri_v), (_n2, _k2, post_v) in zip(
                _pillar_pairs_from_priorpillars(_pri_c),
                _pillar_pairs_from_priorpillars(_attr_c),
            ):
                w.writerow([
                    name,
                    f"{pri_v:.6f}",
                    f"{post_v:.6f}",
                    f"{(post_v - pri_v) * 100:+.4f}",
                ])
            # Posterior outcome probabilities (8 mutually-exclusive outcomes)
            w.writerow([])
            w.writerow(["## DFI posterior outcome probabilities (using ESL prior)"])
            w.writerow(["outcome", "P(outcome | DFI)"])
            for _k, _v in _post_e.posterior_outcomes.items():
                w.writerow([_k, f"{_v:.6f}"])
        except Exception as _exc:
            w.writerow(["dfi_export_error", str(_exc)])
    w.writerow([])

    w.writerow(["## ESL Risk Element Detail"])
    if logic_rows:
        w.writerow(list(logic_rows[0].keys()))
        for row in logic_rows:
            w.writerow(list(row.values()))
    w.writerow([])

    w.writerow(["## Classic POS Operators"])
    w.writerow(["node_id", "classic_operator", "note"])
    conditional_m = models.get("conditional", {})
    for _pid_ex in conditional_m:
        _cmk_ex = SK.classic_mode(_pid_ex)
        _cop_ex = st.session_state.get(_cmk_ex, "Min (weakest link)")
        w.writerow([_cmk_ex, _cop_ex, f"Pillar-level Classic POS operator for {_pid_ex}"])
        from logic.esl_pipeline import group_by_label as _gbl_ex
        _elems_ex = conditional_m.get(_pid_ex, [])
        for _grp_label_ex, _ in _gbl_ex(_elems_ex).items():
            _gkey_ex = SK.classic_group_mode(_pid_ex, _grp_label_ex)
            _gop_ex = st.session_state.get(_gkey_ex, "Min (weakest link)")
            w.writerow([_gkey_ex, _gop_ex, f"Group '{_grp_label_ex}' Classic POS operator"])
    w.writerow([])

    w.writerow(["## Classic POS Sub-elements"])
    w.writerow(["pillar", "scope", "label", "success_criteria", "support_for", "support_against"])
    from logic.pos_policy import get_active_pillars as _gap_ex
    play_m = models.get("play", {})
    for _pdef_ex in _gap_ex():
        _pid_ex2 = _pdef_ex["pillar_id"]
        _dn_ex = _pdef_ex["display_name"]
        el = play_m.get(_pid_ex2, {})
        if isinstance(el, dict) and "support_for" in el:
            w.writerow([_dn_ex, "Play", _dn_ex, el.get("success_criteria", ""),
                        el.get("support_for", 0.5), el.get("support_against", 0.1)])
        for elem in conditional_m.get(_pid_ex2, []):
            w.writerow([_dn_ex, "Conditional", elem.get("label", "?"),
                        elem.get("success_criteria", ""),
                        elem.get("support_for", 0.5), elem.get("support_against", 0.1)])
    w.writerow([])

    w.writerow(["## Assessment Sign-off Records"])
    w.writerow(["method", "reviewer", "date", "pos_pct", "confidence", "timestamp"])
    for meth in ["Classic POS", "ESL"]:
        locked = st.session_state.get(f"locked_{meth}")
        if locked:
            w.writerow([
                meth,
                locked.get("reviewer", ""),
                locked.get("date", ""),
                f"{locked.get('pos', 0)*100:.1f}",
                locked.get("confidence", ""),
                locked.get("timestamp", ""),
            ])
    return buf.getvalue()


def _parse_csv_sections(text: str) -> "dict[str, str]":
    """Split a multi-block E-POS export CSV into named sections."""
    sections: dict[str, str] = {}
    current_name = "__preamble__"
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("##"):
            sections[current_name] = "\n".join(current_lines)
            current_name = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections[current_name] = "\n".join(current_lines)
    return sections
