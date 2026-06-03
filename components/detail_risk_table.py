"""Hierarchical detail risk table — 3-level structure: Play → Conditional → Groups → Leaves.

Used by all three method tabs. Renders inside st.components.v1.html for consistent styling.
Shows: Pillar (Play) → Pillar (Cond) → Group (e.g. Seal effectiveness) → Leaf elements.
"""

from __future__ import annotations

import streamlit as st

from components.colors import PILLAR_COLORS, PILLAR_COLORS_COND
from logic.esl_pipeline import combine_ipt
from logic.pos_policy import get_active_pillars
from logic.session_keys import SK

# Operator options per method
OPERATORS = {
    "esl": [
        "ESL-ALL (min/min)",
        "ESL-ANY (max/max)",
        "ESL-IPT (sufficiency/dependency)",
    ],
    "classic_pos": ["min (weakest link)", "product (multiplicative)", "mean (average)"],
}

# Operator short labels for display in the table header
OP_SHORT = {
    "ESL-ALL (min/min)": "∧ min",
    "ESL-ANY (max/max)": "∨ max",
    "ESL-IPT (sufficiency/dependency)": "IPT",
    "min (weakest link)": "∧ min",
    "product (multiplicative)": "× prod",
    "mean (average)": "≈ avg",
}


def _mini_flag_html(s_for: float, s_against: float, method: str) -> str:
    """Return a mini Italian Flag HTML div.

    Identical for ESL and Classic POS — both use S_for/S_against from the same
    evidence assessment. The method parameter is kept for caller compatibility.
    """
    sf = max(0.0, min(1.0, float(s_for)))
    sa = max(0.0, min(1.0, float(s_against)))
    total = sf + sa
    if total > 1.0:
        overlap = total - 1.0
        g, r, y = sf - overlap, sa - overlap, overlap
        w = 0.0
    else:
        g, r, y = sf, sa, 0.0
        w = max(0.0, 1.0 - sf - sa)
    return (
        "<div style='display:flex;height:12px;width:70px;border:1px solid #555;border-radius:2px;overflow:hidden;'>"
        f"<div style='width:{g*100:.0f}%;background:#2e9d5b;height:100%;'></div>"
        f"<div style='width:{w*100:.0f}%;background:#f3f4f6;height:100%;'></div>"
        f"<div style='width:{y*100:.0f}%;background:#f6c343;height:100%;'></div>"
        f"<div style='width:{r*100:.0f}%;background:#d64545;height:100%;'></div>"
        "</div>"
    )


def _pos_from_element(elem: dict, method: str, uw: float = 0.5) -> tuple[int, int, int]:
    """Return (policy_pos_pct, white_pct, s_against_pct) for display.

    Same formula for ESL and Classic POS — both derive Policy P from the same
    ESL evidence (S_for, S_against, White). The combination operator (ESL vs.
    product/min) only differs at the pillar aggregation step, not per element.
    """
    sf = max(0.0, min(1.0, float(elem.get("support_for", 0.5))))
    sa = max(0.0, min(1.0, float(elem.get("support_against", 0.1))))
    w  = max(0.0, 1.0 - sf - sa)
    return round((sf + uw * w) * 100), round(w * 100), round(sa * 100)


def render_detail_risk_table(
    method: str,
    play: dict,
    conditional: dict,
    cond_results: dict,
    uncertainty_weight: float = 0.5,
    tab_key: str = "",
) -> dict[str, str]:
    """Render the full hierarchical sub-element risk table.

    Returns {cat: selected_operator} for all four pillars.
    """
    ops_available = OPERATORS.get(method, OPERATORS["esl"])
    # Build display name map from active risk model (falls back to legacy 4-pillar names)
    _active_pillars = get_active_pillars()
    display_names: dict[str, str] = {p["pillar_id"]: p["display_name"] for p in _active_pillars}
    pillar_colors: dict[str, str] = {p["pillar_id"]: p.get("color", "#e5e7eb") for p in _active_pillars}
    active_cats: list[str] = [p["pillar_id"] for p in _active_pillars]

    # ── Operator selectors (one per pillar — shown ABOVE the table) ─────────────
    st.markdown("**Combination operators** — how sub-elements are combined within each pillar:")
    op_cols = st.columns(max(len(active_cats), 1))
    selected_ops: dict[str, str] = {}
    for ci, cat in enumerate(active_cats):
        disp = display_names.get(cat, cat)
        color = pillar_colors.get(cat, PILLAR_COLORS.get(cat, "#e5e7eb"))
        with op_cols[ci]:
            st.markdown(
                f"<div style='background:{color};padding:5px 8px;border-radius:4px;"
                f"font-weight:700;font-size:0.85rem;margin-bottom:4px;'>{disp}</div>",
                unsafe_allow_html=True,
            )
            sk = f"detail_op_{method}_{cat}_{tab_key}"
            default_op = ops_available[0]
            if sk not in st.session_state:
                st.session_state[sk] = default_op
            op = st.selectbox(
                "Operator",
                ops_available,
                index=ops_available.index(st.session_state[sk]) if st.session_state[sk] in ops_available else 0,
                key=sk,
                label_visibility="collapsed",
            )
            selected_ops[cat] = op

    def _group_elements(elements: list) -> dict[str, list]:
        """Group elements by label."""
        groups: dict[str, list] = {}
        for e in elements:
            groups.setdefault(e.get("label", "?"), []).append(e)
        return groups

    def _combine_by_op(nodes: list, op: str, dependency: float = 0.0) -> tuple[float, float]:
        """Combine nodes matching esl_pipeline.combine_with_mode semantics.

        ESL-ANY  → max(for), max(against)   [max/max, symmetric]
        ESL-IPT  → combine_ipt interpolation between independent and correlated
        ESL-ALL  → min(for), min(against)   [min/min, symmetric, default]
        """
        supports = [
            (float(n.get("support_for", 0.0)), float(n.get("support_against", 0.0)))
            for n in nodes
        ]
        if not supports:
            return 0.0, 0.0
        if op.startswith("ESL-ANY"):
            return max(s[0] for s in supports), max(s[1] for s in supports)
        if op.startswith("ESL-IPT"):
            return combine_ipt(nodes, dependency)
        # ESL-ALL and all other modes: min/min
        return min(s[0] for s in supports), min(s[1] for s in supports)

    def _policy_pos(s_for: float, s_against: float) -> float:
        w = uncertainty_weight
        g = max(0.0, min(1.0, s_for))
        r = max(0.0, min(1.0, s_against))
        white = max(0.0, 1.0 - g - r)
        return (g + w * white) * 100

    # ── Build HTML table (3-level hierarchy) ────────────────────────────────────
    css = """
    <style>
    .drt-table { width:100%; border-collapse:collapse; font-family:'Segoe UI',sans-serif; font-size:13px; }
    .drt-table th { background:#111827; color:#fff; padding:8px 10px; text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:0.04em; }
    .drt-table td { padding:6px 10px; border-bottom:1px solid #e5e7eb; vertical-align:middle; }
    .drt-pillar-row td { font-weight:700; font-size:13px; }
    .drt-cond-row td { font-weight:600; font-size:12px; padding-left:12px; }
    .drt-group-row td { font-weight:600; font-size:12px; padding-left:24px; }
    .drt-leaf-row td { font-size:12px; padding-left:36px; }
    .drt-num { text-align:center; white-space:nowrap; font-variant-numeric:tabular-nums; }
    .drt-pillar-badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700; }
    </style>
    """

    flag_col = "Italian Flag (G / W / R)"
    header = (
        f"<tr><th>Chance Sub-element</th><th>Success Criteria</th>"
        f"<th class='drt-num'>Pos.%</th><th class='drt-num'>Unc.%</th>"
        f"<th class='drt-num'>Neg.%</th><th class='drt-num'>POS%</th>"
        f"<th>{flag_col}</th><th>Operator</th></tr>"
    )

    rows_html = ""
    n_rows = 0
    for cat in active_cats:
        disp = display_names.get(cat, cat)
        color = pillar_colors.get(cat, PILLAR_COLORS.get(cat, "#e5e7eb"))
        cond_color = PILLAR_COLORS_COND.get(cat, "#f3f4f6")
        op = selected_ops.get(cat, ops_available[0])
        op_badge = OP_SHORT.get(op, op)

        # Level 0: Play pillar row
        play_el = play.get(cat, {})
        if isinstance(play_el, dict) and "support_for" in play_el:
            pp, pu, pn = _pos_from_element(play_el, method, uncertainty_weight)
            flag = _mini_flag_html(
                play_el["support_for"],
                play_el.get("support_against", 0.0),
                method,
            )
            sc = (play_el.get("success_criteria") or "")[:55]
            rows_html += (
                f"<tr class='drt-pillar-row' style='background:{color}30;'>"
                f"<td><span class='drt-pillar-badge' style='background:{color};'>{disp} (Play)</span></td>"
                f"<td style='font-size:11px;color:#374151;'>{sc}</td>"
                f"<td class='drt-num'>{pp}%</td><td class='drt-num'>{pu}%</td>"
                f"<td class='drt-num'>{pn}%</td><td class='drt-num'><b>{pp}%</b></td>"
                f"<td>{flag}</td><td style='font-size:11px;'>×</td></tr>"
            )
            n_rows += 1

        # Level 1: Conditional pillar header
        elems = conditional.get(cat, [])
        if elems:
            grouped = _group_elements(elems)
            # Within each label-group combine with min/min (ESL-ALL default matches main pipeline)
            group_nodes = [
                {
                    "support_for": min(float(e.get("support_for", 0.0)) for e in g),
                    "support_against": min(float(e.get("support_against", 0.0)) for e in g),
                    "suff_for": min(float(e.get("suff_for", 1.0)) for e in g),
                    "suff_against": min(float(e.get("suff_against", 1.0)) for e in g),
                }
                for g in grouped.values()
            ]
            dep = float(st.session_state.get(SK.esl_dependency(cat), 0.0))
            grp_for, grp_against = _combine_by_op(group_nodes, op, dep)
            cond_pos = round(_policy_pos(grp_for, grp_against))
            rows_html += (
                f"<tr class='drt-cond-row' style='background:{cond_color}50;'>"
                f"<td style='color:#374151;font-weight:700;'>{disp} (Cond)</td>"
                f"<td style='font-size:11px;color:#6b7280;'>Combined conditional</td>"
                f"<td class='drt-num'>—</td><td class='drt-num'>—</td>"
                f"<td class='drt-num'>—</td><td class='drt-num'><b>{cond_pos}%</b></td>"
                f"<td></td><td style='font-size:11px;'>{op_badge}</td></tr>"
            )
            n_rows += 1

            # Level 2 & 3: Groups and leaves
            for group_label, group_elements in grouped.items():
                if len(group_elements) == 1:
                    elem = group_elements[0]
                    sc = (elem.get("success_criteria") or "")[:70]
                    pos_v, unc_v, neg_v = _pos_from_element(elem, method, uncertainty_weight)
                    flag = _mini_flag_html(
                        elem.get("support_for", 0.5),
                        elem.get("support_against", 0.1),
                        method,
                    )
                    rows_html += (
                        f"<tr class='drt-leaf-row' style='background:{cond_color}30;'>"
                        f"<td style='color:#374151;'>{elem.get('label', '?')}</td>"
                        f"<td style='font-size:11px;color:#6b7280;'>{sc}</td>"
                        f"<td class='drt-num'>{pos_v}%</td><td class='drt-num'>{unc_v}%</td>"
                        f"<td class='drt-num'>{neg_v}%</td><td class='drt-num'>{pos_v}%</td>"
                        f"<td>{flag}</td>"
                        f"<td style='font-size:11px;color:#6b7280;'>∧ min</td></tr>"
                    )
                    n_rows += 1
                else:
                    # Within-group: min/min (ESL-ALL default, matches main pipeline default)
                    gf = min(float(e.get("support_for", 0.0)) for e in group_elements)
                    ga = min(float(e.get("support_against", 0.0)) for e in group_elements)
                    grp_pos = round(_policy_pos(gf, ga))
                    rows_html += (
                        f"<tr class='drt-group-row' style='background:{cond_color}40;'>"
                        f"<td style='color:#374151;'>{group_label}</td>"
                        f"<td style='font-size:11px;color:#6b7280;'>Group (min of {len(group_elements)} elements)</td>"
                        f"<td class='drt-num'>—</td><td class='drt-num'>—</td>"
                        f"<td class='drt-num'>—</td><td class='drt-num'><b>{grp_pos}%</b></td>"
                        f"<td></td><td style='font-size:11px;'>∧ min</td></tr>"
                    )
                    n_rows += 1
                    for elem in group_elements:
                        sc = (elem.get("success_criteria") or "")[:70]
                        leaf_label = (elem.get("success_criteria") or elem.get("label", "?"))[:55]
                        pos_v, unc_v, neg_v = _pos_from_element(elem, method, uncertainty_weight)
                        flag = _mini_flag_html(
                            elem.get("support_for", 0.5),
                            elem.get("support_against", 0.1),
                            method,
                        )
                        rows_html += (
                            f"<tr class='drt-leaf-row' style='background:{cond_color}20;'>"
                            f"<td style='color:#4b5563;'>↳ {leaf_label}</td>"
                            f"<td style='font-size:11px;color:#6b7280;'>{sc}</td>"
                            f"<td class='drt-num'>{pos_v}%</td><td class='drt-num'>{unc_v}%</td>"
                            f"<td class='drt-num'>{neg_v}%</td><td class='drt-num'>{pos_v}%</td>"
                            f"<td>{flag}</td>"
                            f"<td style='font-size:11px;color:#9ca3af;'>leaf</td></tr>"
                        )
                        n_rows += 1

    html = css + f"<table class='drt-table'><thead>{header}</thead><tbody>{rows_html}</tbody></table>"
    st.components.v1.html(html, height=min(500, int((n_rows * 26 + 80))), scrolling=True)

    return selected_ops
